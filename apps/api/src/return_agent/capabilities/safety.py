"""Deterministic handoff verification capability."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
import json

from pydantic import TypeAdapter, ValidationError
from return_agent_contracts.enums import (
    VerificationStatus,
)
from return_agent_contracts.interfaces import (
    CaseContextProvider,
    EvidenceProvider,
    VerificationProvider,
)
from return_agent_contracts.models import (
    FailedVerificationResult,
    PolicyBundle,
    ProposedDecisionHandoff,
    UnavailableVerificationResult,
    VerificationIssue,
    VerificationResult,
)
from return_agent_contracts.validation import (
    ContractInvariantError,
    validate_applicable_policy_bundle,
    validate_case_context_load_result,
    validate_proposed_decision_handoff,
)
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session, sessionmaker

from return_agent.capabilities.evidence import SqlAlchemyEvidenceProvider
from return_agent.db.models import (
    HandoffVerificationRecord,
    PolicyRetrievalRecord,
)

_VERIFICATION_ADAPTER = TypeAdapter(VerificationResult)


class SafetyConflictError(ValueError):
    """Raised when a stable handoff ID is reused with different content."""


class SafetyDataIntegrityError(RuntimeError):
    """Raised when a persisted safety record cannot satisfy its contract."""


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _canonical_hash(value: object) -> str:
    canonical = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256(canonical.encode("utf-8")).hexdigest()


def _handoff_payload(handoff: ProposedDecisionHandoff) -> dict[str, object]:
    return handoff.model_dump(mode="json")


def _issue(code: str, message: str, field_path: str) -> VerificationIssue:
    return VerificationIssue(code=code, message=message, field_path=field_path)


class SqlAlchemyPolicyBundleRepository:
    """Read the exact persisted bundle referenced by a proposed handoff."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def get_persisted_bundle(self, bundle_version: str) -> PolicyBundle | None:
        with self._session_factory() as session:
            record = session.scalar(
                select(PolicyRetrievalRecord).where(
                    PolicyRetrievalRecord.bundle_version == bundle_version
                )
            )
        if record is None:
            return None
        try:
            bundle = PolicyBundle.model_validate(record.bundle_payload)
        except ValidationError as error:
            raise SafetyDataIntegrityError(
                "persisted policy bundle violates its contract"
            ) from error
        if (
            bundle.policy_bundle_version != record.bundle_version
            or bundle.retrieval_status.value != record.retrieval_status
        ):
            raise SafetyDataIntegrityError(
                "persisted policy bundle metadata disagrees with its payload"
            )
        return bundle


class SqlAlchemySafetyRepository:
    """Idempotent canonical persistence for safety decisions."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def verification_for(
        self,
        handoff_id: str,
        payload_hash: str,
    ) -> VerificationResult | None:
        with self._session_factory() as session:
            record = session.scalar(
                select(HandoffVerificationRecord).where(
                    HandoffVerificationRecord.handoff_id == handoff_id
                )
            )
        if record is None:
            return None
        self._require_matching_payload(record.payload_hash, payload_hash, handoff_id)
        return self._verification_result(record)

    def persist_verification(
        self,
        handoff: ProposedDecisionHandoff,
        payload_hash: str,
        result: VerificationResult,
    ) -> VerificationResult:
        payload = _handoff_payload(handoff)
        now = _now_utc()
        values = {
            "verification_id": f"verification:{payload_hash[:32]}",
            "handoff_id": handoff.handoff_id,
            "payload_hash": payload_hash,
            "handoff_payload": payload,
            "result_payload": result.model_dump(mode="json"),
            "verification_status": result.status.value,
            "verification_version": result.verification_version,
            "created_at": now,
            "updated_at": now,
        }
        with self._session_factory.begin() as session:
            record = session.scalar(
                select(HandoffVerificationRecord)
                .where(HandoffVerificationRecord.handoff_id == handoff.handoff_id)
                .with_for_update()
            )
            if record is not None:
                self._require_matching_payload(
                    record.payload_hash, payload_hash, handoff.handoff_id
                )
                if record.verification_status != VerificationStatus.UNAVAILABLE.value:
                    return self._verification_result(record)
                record.result_payload = values["result_payload"]
                record.verification_status = values["verification_status"]
                record.verification_version = values["verification_version"]
                record.updated_at = now
                return self._verification_result(record)

            self._insert_do_nothing(session, HandoffVerificationRecord, values)
            canonical = session.scalar(
                select(HandoffVerificationRecord).where(
                    HandoffVerificationRecord.handoff_id == handoff.handoff_id
                )
            )
            if canonical is None:
                raise SafetyDataIntegrityError(
                    "verification insert completed without a canonical record"
                )
            self._require_matching_payload(
                canonical.payload_hash, payload_hash, handoff.handoff_id
            )
            return self._verification_result(canonical)

    @staticmethod
    def _insert_do_nothing(
        session: Session,
        model: type[HandoffVerificationRecord],
        values: dict[str, object],
    ) -> None:
        dialect = session.get_bind().dialect.name
        if dialect == "postgresql":
            statement = postgresql_insert(model).values(**values)
        elif dialect == "sqlite":
            statement = sqlite_insert(model).values(**values)
        else:
            raise SafetyDataIntegrityError(
                f"unsupported safety persistence dialect: {dialect}"
            )
        session.execute(statement.on_conflict_do_nothing())

    @staticmethod
    def _require_matching_payload(
        stored_hash: str,
        payload_hash: str,
        handoff_id: str,
    ) -> None:
        if stored_hash != payload_hash:
            raise SafetyConflictError(
                f"handoff_id {handoff_id!r} is associated with different content"
            )

    @staticmethod
    def _verification_result(
        record: HandoffVerificationRecord,
    ) -> VerificationResult:
        try:
            result = _VERIFICATION_ADAPTER.validate_python(record.result_payload)
        except ValidationError as error:
            raise SafetyDataIntegrityError(
                "persisted verification result violates its contract"
            ) from error
        if result.status.value != record.verification_status:
            raise SafetyDataIntegrityError(
                "persisted verification status disagrees with its result"
            )
        return result

class SqlAlchemyVerificationProvider(VerificationProvider):
    """Validate a proposed handoff against authoritative capability facts."""

    def __init__(
        self,
        repository: SqlAlchemySafetyRepository,
        case_context_provider: CaseContextProvider,
        policy_bundles: SqlAlchemyPolicyBundleRepository,
        evidence_provider: EvidenceProvider,
        *,
        verification_version: str = "verification:1.0",
    ) -> None:
        self._repository = repository
        self._case_context_provider = case_context_provider
        self._policy_bundles = policy_bundles
        self._evidence_provider = evidence_provider
        self._verification_version = verification_version

    def verify(self, handoff: ProposedDecisionHandoff) -> VerificationResult:
        payload_hash = _canonical_hash(_handoff_payload(handoff))
        existing = self._repository.verification_for(handoff.handoff_id, payload_hash)
        if (
            existing is not None
            and existing.status is not VerificationStatus.UNAVAILABLE
        ):
            return existing
        result = self._evaluate(handoff)
        return self._repository.persist_verification(handoff, payload_hash, result)

    def _evaluate(self, handoff: ProposedDecisionHandoff) -> VerificationResult:
        try:
            context = self._case_context_provider.load_case_context(handoff.case_ref)
            validate_case_context_load_result(handoff.case_ref, context)
            bundle = self._policy_bundles.get_persisted_bundle(
                handoff.policy_bundle_version
            )
            if bundle is None:
                return self._failed(
                    _issue(
                        "POLICY_BUNDLE_NOT_FOUND",
                        "The referenced policy bundle is unavailable.",
                        "policy_bundle_version",
                    )
                )
            validate_applicable_policy_bundle(context.case_context, bundle)
            validate_proposed_decision_handoff(
                handoff,
                bundle,
                context.order_snapshot,
            )
            if handoff.handoff_version == "2.0":
                from return_agent_contracts.policy_v2 import evaluate_policy, content_hash
                from .fulfillment import save_evaluation
                from return_agent.db.models import PolicyConfirmationRecord
                evaluation = handoff.policy_evaluation
                expected = evaluate_policy(context=context.case_context,order=context.order_snapshot,bundle=bundle,
                    claimed_line_item_ids=list(dict.fromkeys(x.line_item_id for x in evaluation.item_evaluations)),
                    findings=handoff.assessment_findings,evidence=handoff.evidence_bundle,selection=handoff.policy_selection,
                    evaluated_at=evaluation.evaluated_at)
                if evaluation != expected:
                    raise ContractInvariantError("policy evaluator recomputation mismatch")
                with self._repository._session_factory.begin() as session:
                    confirmation = handoff.policy_confirmation
                    if confirmation is not None:
                        record = session.get(PolicyConfirmationRecord,confirmation.request.request_ref)
                        if record is None or record.response_payload != confirmation.model_dump(mode="json") or not confirmation.accepted:
                            raise ContractInvariantError("policy confirmation is not canonical")
                        if confirmation.request.case_ref != handoff.case_ref or confirmation.request.path_id is not handoff.policy_selection.selected_path_id or confirmation.request.original_scope_hash != content_hash(list(dict.fromkeys(x.line_item_id for x in evaluation.item_evaluations))):
                            raise ContractInvariantError("policy confirmation binding mismatch")
                    save_evaluation(session,evaluation)
            evidence_issues = self._evidence_issues(handoff)
            return self._failed(*evidence_issues) if evidence_issues else self._passed()
        except (ContractInvariantError, LookupError, ValueError) as error:
            return self._failed(
                _issue("HANDOFF_INVALID", str(error), "handoff")
            )
        except Exception:  # noqa: BLE001 - dependency unavailability is a DTO result
            return UnavailableVerificationResult(
                status=VerificationStatus.UNAVAILABLE,
                issues=[],
                verification_version=self._verification_version,
            )

    def _evidence_issues(
        self,
        handoff: ProposedDecisionHandoff,
    ) -> list[VerificationIssue]:
        issues: list[VerificationIssue] = []
        for evidence in handoff.evidence_bundle:
            resolved = self._evidence_provider.resolve(evidence.artifact_ref)
            if resolved.model_dump(mode="json") != evidence.model_dump(mode="json"):
                issues.append(
                    _issue(
                        "EVIDENCE_METADATA_MISMATCH",
                        "The referenced evidence does not match persisted metadata.",
                        f"evidence_bundle[{evidence.evidence_id}]",
                    )
                )
        return issues

    def _passed(self) -> VerificationResult:
        return _VERIFICATION_ADAPTER.validate_python(
            {
                "status": VerificationStatus.PASS,
                "issues": [],
                "verification_version": self._verification_version,
            }
        )

    def _failed(self, *issues: VerificationIssue) -> VerificationResult:
        return FailedVerificationResult(
            status=VerificationStatus.FAIL,
            issues=list(issues),
            verification_version=self._verification_version,
        )


@dataclass(frozen=True, slots=True)
class SafetyProviders:
    """Verification provider installed by API's integration owner."""

    verification_provider: VerificationProvider


def compose_safety_providers(
    *,
    session_factory: sessionmaker[Session],
    case_context_provider: CaseContextProvider,
    evidence_provider: EvidenceProvider | None = None,
) -> SafetyProviders:
    """Compose API-local data capabilities around Allen's context provider."""

    repository = SqlAlchemySafetyRepository(session_factory)
    return SafetyProviders(
        verification_provider=SqlAlchemyVerificationProvider(
            repository,
            case_context_provider,
            SqlAlchemyPolicyBundleRepository(session_factory),
            evidence_provider or SqlAlchemyEvidenceProvider(session_factory),
        ),
    )
