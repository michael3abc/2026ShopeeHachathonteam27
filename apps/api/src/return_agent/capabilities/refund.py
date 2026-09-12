"""Authorized, idempotent refund execution owned by the API service."""

from __future__ import annotations
from return_agent_contracts.user_risk import UserRiskConfig, evaluate_user_risk
from return_agent.capabilities.user_risk import SqlAlchemyUserRiskProvider, append_risk_event, validate_persisted_dossier_snapshot
from return_agent.db.case import CaseRecord
from return_agent_contracts.review_gates import ReviewerGateConfig, evaluate_review_gate
from return_agent_contracts.validation import validate_human_review_entry

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from hashlib import sha256

from pydantic import TypeAdapter, ValidationError
from return_agent_contracts.enums import (
    OutcomeSource,
    RefundApplicationStatus,
    RefundExecutionStatus,
    ResolutionAction,
    ReviewVerdict,
    VerificationStatus,
)
from return_agent_contracts.interfaces import (
    CaseContextProvider,
    RefundApplicationProvider,
    RefundExecutionProvider,
)
from return_agent_contracts.models import (
    REVIEW_REVISION_LIMIT,
    AgentFullRefundFinalDecision,
    AppliedRefundApplicationResult,
    ApplyRefundRequest,
    ExecuteRefundRequest,
    HumanEditedFullRefundFinalDecision,
    HumanReviewDossier,
    HumanReviewResult,
    OrderSnapshot,
    ProposedDecisionHandoff,
    RefundApplicationResult,
    RefundExecutionRecord,
    RejectedRefundApplicationResult,
    ResolutionHandoff,
    VerificationResult,
)
from return_agent_contracts.validation import (
    ContractInvariantError,
    human_corrected_decision,
    validate_case_context_load_result,
    validate_human_decision,
    validate_proposed_decision_handoff,
    validate_review_result,
)
from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session, sessionmaker

from return_agent.capabilities.safety import SqlAlchemyPolicyBundleRepository
from return_agent.db.models import (
    HandoffVerificationRecord,
    HumanReviewRecord,
    RefundExecutionItemRecord,
    RefundItemReservation,
)
from return_agent.db.models import (
    RefundExecutionRecord as RefundExecutionRow,
)

_EXECUTE_REQUEST_ADAPTER = TypeAdapter(ExecuteRefundRequest)
_APPLICATION_RESULT_ADAPTER = TypeAdapter(RefundApplicationResult)
_EXECUTION_RECORD_ADAPTER = TypeAdapter(RefundExecutionRecord)
_HANDOFF_ADAPTER = TypeAdapter(ProposedDecisionHandoff)
_HUMAN_RESULT_ADAPTER = TypeAdapter(HumanReviewResult)
_VERIFICATION_RESULT_ADAPTER = TypeAdapter(VerificationResult)


class RefundExecutionConflictError(ValueError):
    """A handoff ID was replayed with different execution content."""


class RefundExecutionUnavailableError(RuntimeError):
    """An execution may have reached Allen but has no terminal local result yet."""


class RefundExecutionDataIntegrityError(RuntimeError):
    """A persisted refund execution cannot satisfy its shared contract."""


class _ReservationConflict(Exception):
    """Another execution already owns a requested item."""


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _as_utc(timestamp: datetime) -> datetime:
    if timestamp.tzinfo is None:
        return timestamp.replace(tzinfo=UTC)
    return timestamp.astimezone(UTC)


def _canonical_hash(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256(payload.encode("utf-8")).hexdigest()


def _execution_ref(handoff_id: str) -> str:
    return f"refund:{sha256(handoff_id.encode('utf-8')).hexdigest()}"


@dataclass(frozen=True, slots=True)
class PersistedRefundExecution:
    execution_ref: str
    handoff_id: str
    case_ref: str
    payload_hash: str
    request_payload: dict[str, object]
    order_ref: str | None
    application_result_payload: dict[str, object] | None
    state: str
    created_at: datetime
    updated_at: datetime
    application_started_at: datetime | None


@dataclass(frozen=True, slots=True)
class PersistedAuthorization:
    handoff: ProposedDecisionHandoff
    payload_hash: str
    verification: VerificationResult
    human_record: HumanReviewRecord | None


class SqlAlchemyRefundExecutionRepository:
    """Own only the local execution ledger; never query Allen's tables."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def find(self, execution_ref: str) -> PersistedRefundExecution | None:
        with self._session_factory() as session:
            record = session.get(RefundExecutionRow, execution_ref)
            return self._snapshot(record) if record is not None else None

    def find_by_handoff(
        self,
        handoff_id: str,
        payload_hash: str,
    ) -> PersistedRefundExecution | None:
        with self._session_factory() as session:
            record = session.scalar(
                select(RefundExecutionRow).where(
                    RefundExecutionRow.handoff_id == handoff_id
                )
            )
            if record is None:
                return None
            self._require_matching_payload(
                record.payload_hash,
                payload_hash,
                handoff_id,
            )
            return self._snapshot(record)

    def load_authorization(self, handoff_id: str) -> PersistedAuthorization | None:
        with self._session_factory() as session:
            verification_record = session.scalar(
                select(HandoffVerificationRecord).where(
                    HandoffVerificationRecord.handoff_id == handoff_id
                )
            )
            if verification_record is None:
                return None
            handoff = self._parse_handoff(verification_record.handoff_payload)
            payload_hash = _canonical_hash(handoff.model_dump(mode="json"))
            if (
                handoff.handoff_id != verification_record.handoff_id
                or payload_hash != verification_record.payload_hash
            ):
                raise RefundExecutionDataIntegrityError(
                    "persisted verification handoff disagrees with its metadata"
                )
            verification = self._parse_verification(
                verification_record.result_payload,
                verification_record.verification_status,
            )
            human_record = session.scalar(
                select(HumanReviewRecord).where(HumanReviewRecord.handoff_id == handoff_id)
            )
            return PersistedAuthorization(
                handoff=handoff,
                payload_hash=payload_hash,
                verification=verification,
                human_record=human_record,
            )

    def start_pending(
        self,
        *,
        execution_ref: str,
        request: ExecuteRefundRequest,
        payload_hash: str,
        order_ref: str,
    ) -> PersistedRefundExecution:
        now = _now_utc()
        handoff = request.resolution_handoff
        values = {
            "execution_ref": execution_ref,
            "handoff_id": handoff.handoff_id,
            "case_ref": handoff.case_ref,
            "payload_hash": payload_hash,
            "request_payload": request.model_dump(mode="json"),
            "order_ref": order_ref,
            "application_result_payload": None,
            "state": "IN_PROGRESS",
            "created_at": now,
            "application_started_at": None,
            "completed_at": None,
            "updated_at": now,
        }
        with self._session_factory.begin() as session:
            self._insert_do_nothing(session, RefundExecutionRow, values)
            record = session.scalar(
                select(RefundExecutionRow).where(
                    RefundExecutionRow.handoff_id == handoff.handoff_id
                )
            )
            if record is None:
                raise RefundExecutionDataIntegrityError(
                    "refund execution insert completed without a canonical record"
                )
            self._require_matching_payload(
                record.payload_hash,
                payload_hash,
                handoff.handoff_id,
            )
            return self._snapshot(record)

    def create_rejected(
        self,
        request: ExecuteRefundRequest,
        payload_hash: str,
        reason_codes: list[str],
    ) -> PersistedRefundExecution:
        now = _now_utc()
        handoff = request.resolution_handoff
        result = RejectedRefundApplicationResult(
            status=RefundApplicationStatus.REJECTED,
            reason_codes=reason_codes,
            rejected_at=now,
        )
        values = {
            "execution_ref": _execution_ref(handoff.handoff_id),
            "handoff_id": handoff.handoff_id,
            "case_ref": handoff.case_ref,
            "payload_hash": payload_hash,
            "request_payload": request.model_dump(mode="json"),
            "order_ref": None,
            "application_result_payload": result.model_dump(mode="json"),
            "state": "REJECTED",
            "created_at": now,
            "application_started_at": None,
            "completed_at": now,
            "updated_at": now,
        }
        with self._session_factory.begin() as session:
            self._insert_do_nothing(session, RefundExecutionRow, values)
            record = session.scalar(
                select(RefundExecutionRow).where(
                    RefundExecutionRow.handoff_id == handoff.handoff_id
                )
            )
            if record is None:
                raise RefundExecutionDataIntegrityError(
                    "refund rejection insert completed without a canonical record"
                )
            self._require_matching_payload(
                record.payload_hash,
                payload_hash,
                handoff.handoff_id,
            )
            if record.state == "IN_PROGRESS" and record.application_started_at is None:
                record.state = "REJECTED"
                record.application_result_payload = result.model_dump(mode="json")
                record.completed_at = now
                record.updated_at = now
            return self._snapshot(record)

    def mark_application_started(
        self,
        execution_ref: str,
        payload_hash: str,
    ) -> PersistedRefundExecution:
        with self._session_factory.begin() as session:
            record = self._locked_execution(session, execution_ref, payload_hash)
            if record.state != "IN_PROGRESS":
                return self._snapshot(record)
            if record.order_ref is None:
                raise RefundExecutionDataIntegrityError("execution has no order reference")
            request = self._parse_execute_request(record.request_payload)
            scope = request.resolution_handoff.final_decision.refund_scope.line_item_ids
            try:
                # Roll back every new item if any part of this scope conflicts.
                with session.begin_nested():
                    for item_ref in sorted(scope):
                        self._insert_do_nothing(session, RefundItemReservation, {
                            "order_ref": record.order_ref,
                            "line_item_ref": item_ref,
                            "execution_ref": execution_ref,
                            "reserved_at": _now_utc(),
                        })
                        reservation = session.get(
                            RefundItemReservation, (record.order_ref, item_ref)
                        )
                        if reservation is None:
                            raise RefundExecutionDataIntegrityError("missing reservation")
                        if reservation.execution_ref != execution_ref:
                            raise _ReservationConflict
            except _ReservationConflict:
                if record.application_started_at is not None:
                    raise RefundExecutionDataIntegrityError(
                        "previously attempted execution lost reservation ownership"
                    ) from None
                now = _now_utc()
                result = RejectedRefundApplicationResult(
                    status=RefundApplicationStatus.REJECTED,
                    reason_codes=["REFUND_ITEM_RESERVED"],
                    rejected_at=now,
                )
                record.state = "REJECTED"
                record.application_result_payload = result.model_dump(mode="json")
                record.completed_at = now
                record.updated_at = now
                return self._snapshot(record)
            if record.state == "IN_PROGRESS" and record.application_started_at is None:
                now = _now_utc()
                record.application_started_at = now
                record.updated_at = now
            return self._snapshot(record)

    def complete(
        self,
        execution_ref: str,
        payload_hash: str,
        application_result: RefundApplicationResult,
    ) -> PersistedRefundExecution:
        with self._session_factory.begin() as session:
            record = self._locked_execution(session, execution_ref, payload_hash)
            if record.state != "IN_PROGRESS":
                return self._snapshot(record)

            now = _now_utc()
            record.application_result_payload = application_result.model_dump(
                mode="json"
            )
            record.state = (
                "SUCCEEDED"
                if application_result.status is RefundApplicationStatus.APPLIED
                else "REJECTED"
            )
            record.completed_at = now
            record.updated_at = now
            if application_result.status is RefundApplicationStatus.APPLIED:
                self._store_successful_items(session, record, application_result)
                resolution = self._parse_execute_request(record.request_payload).resolution_handoff
                case = session.get(CaseRecord, resolution.case_ref)
                if case is not None and case.policy_schema_version == "v2":
                    from return_agent_contracts.completion import RefundAppliedEvent
                    from return_agent_contracts.policy_v2 import content_hash
                    from return_agent.db.models import RefundCompletionOutboxRecord
                    event = RefundAppliedEvent(case_ref=case.case_ref,resolution_ref=resolution.handoff_id,
                        authorization_ref=f"authorization:{resolution.handoff_id}",resolution_hash=content_hash(resolution),
                        execution_ref=record.execution_ref,application_ref=application_result.application_ref,
                        applied_at=application_result.applied_at)
                    session.add(RefundCompletionOutboxRecord(resolution_ref=resolution.handoff_id,
                        payload=event.model_dump(mode="json"),published=False))
                    case = session.get(CaseRecord, resolution.case_ref)
                    if case is None:
                        raise RefundExecutionDataIntegrityError("risk success event requires case owner")
                    append_risk_event(session,user_ref=case.user_ref,case_ref=case.case_ref,order_ref=case.order_ref,
                        event_type="REFUND_SUCCEEDED",reason_code=resolution.final_decision.reason_code.value,occurred_at=application_result.applied_at)
            else:
                session.execute(delete(RefundItemReservation).where(
                    RefundItemReservation.execution_ref == execution_ref
                ))
            return self._snapshot(record)

    def _store_successful_items(
        self,
        session: Session,
        record: RefundExecutionRow,
        application_result: AppliedRefundApplicationResult,
    ) -> None:
        if record.order_ref is None:
            raise RefundExecutionDataIntegrityError(
                "a successful execution is missing its order reference"
            )
        request = self._parse_execute_request(record.request_payload)
        line_item_refs = (
            request.resolution_handoff.final_decision.refund_scope.line_item_ids
        )
        for line_item_ref in line_item_refs:
            values = {
                "execution_ref": record.execution_ref,
                "line_item_ref": line_item_ref,
                "order_ref": record.order_ref,
                "applied_at": application_result.applied_at,
            }
            self._insert_do_nothing(session, RefundExecutionItemRecord, values)
            item = session.scalar(
                select(RefundExecutionItemRecord).where(
                    RefundExecutionItemRecord.order_ref == record.order_ref,
                    RefundExecutionItemRecord.line_item_ref == line_item_ref,
                )
            )
            if item is None or item.execution_ref != record.execution_ref:
                raise RefundExecutionDataIntegrityError(
                    "order line item is already assigned to another refund execution"
                )

    def _locked_execution(
        self,
        session: Session,
        execution_ref: str,
        payload_hash: str,
    ) -> RefundExecutionRow:
        if session.get_bind().dialect.name == "sqlite":
            # SQLite ignores FOR UPDATE; take the writer lock before reading.
            session.execute(update(RefundExecutionRow).where(
                RefundExecutionRow.execution_ref == execution_ref
            ).values(updated_at=RefundExecutionRow.updated_at))
        record = session.scalar(
            select(RefundExecutionRow)
            .where(RefundExecutionRow.execution_ref == execution_ref)
            .with_for_update()
        )
        if record is None:
            raise RefundExecutionDataIntegrityError("unknown refund execution")
        self._require_matching_payload(
            record.payload_hash,
            payload_hash,
            record.handoff_id,
        )
        return record

    @staticmethod
    def _insert_do_nothing(
        session: Session,
        model: type[RefundExecutionRow] | type[RefundExecutionItemRecord] | type[RefundItemReservation],
        values: dict[str, object],
    ) -> None:
        dialect = session.get_bind().dialect.name
        if dialect == "postgresql":
            statement = postgresql_insert(model).values(**values)
        elif dialect == "sqlite":
            statement = sqlite_insert(model).values(**values)
        else:
            raise RefundExecutionDataIntegrityError(
                f"unsupported refund persistence dialect: {dialect}"
            )
        session.execute(statement.on_conflict_do_nothing())

    @staticmethod
    def _require_matching_payload(
        stored_hash: str,
        payload_hash: str,
        handoff_id: str,
    ) -> None:
        if stored_hash != payload_hash:
            raise RefundExecutionConflictError(
                f"handoff_id {handoff_id!r} is associated with different content"
            )

    @staticmethod
    def _parse_handoff(payload: dict[str, object]) -> ProposedDecisionHandoff:
        try:
            return _HANDOFF_ADAPTER.validate_python(payload)
        except ValidationError as error:
            raise RefundExecutionDataIntegrityError(
                "persisted verification handoff violates its contract"
            ) from error

    @staticmethod
    def _parse_verification(
        payload: dict[str, object],
        status: str,
    ) -> VerificationResult:
        try:
            result = _VERIFICATION_RESULT_ADAPTER.validate_python(payload)
        except ValidationError as error:
            raise RefundExecutionDataIntegrityError(
                "persisted verification result violates its contract"
            ) from error
        if result.status.value != status:
            raise RefundExecutionDataIntegrityError(
                "persisted verification status disagrees with its result"
            )
        return result

    @staticmethod
    def _parse_execute_request(payload: dict[str, object]) -> ExecuteRefundRequest:
        try:
            return _EXECUTE_REQUEST_ADAPTER.validate_python(payload)
        except ValidationError as error:
            raise RefundExecutionDataIntegrityError(
                "persisted refund request violates its contract"
            ) from error

    @staticmethod
    def _snapshot(record: RefundExecutionRow) -> PersistedRefundExecution:
        return PersistedRefundExecution(
            execution_ref=record.execution_ref,
            handoff_id=record.handoff_id,
            case_ref=record.case_ref,
            payload_hash=record.payload_hash,
            request_payload=record.request_payload,
            order_ref=record.order_ref,
            application_result_payload=record.application_result_payload,
            state=record.state,
            created_at=_as_utc(record.created_at),
            updated_at=_as_utc(record.updated_at),
            application_started_at=_as_utc(record.application_started_at) if record.application_started_at else None,
        )


class SqlAlchemyRefundExecutionProvider(RefundExecutionProvider):
    """Execute only authorized refunds through Allen's idempotent mutation port."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        case_context_provider: CaseContextProvider,
        refund_application_provider: RefundApplicationProvider,
        reviewer_gate_config: ReviewerGateConfig | None = None,
        user_risk_config: UserRiskConfig | None = None,
        user_risk_provider: SqlAlchemyUserRiskProvider | None = None,
    ) -> None:
        self._repository = SqlAlchemyRefundExecutionRepository(session_factory)
        self._session_factory = session_factory
        self._reviewer_gate_config = reviewer_gate_config or ReviewerGateConfig()
        self._user_risk_config = user_risk_config or UserRiskConfig()
        self._user_risk_provider = user_risk_provider or SqlAlchemyUserRiskProvider(session_factory,case_context_provider)
        self._policy_bundles = SqlAlchemyPolicyBundleRepository(session_factory)
        self._case_context_provider = case_context_provider
        self._refund_application_provider = refund_application_provider

    def execute(self, request: ExecuteRefundRequest) -> RefundExecutionRecord:
        payload_hash = _canonical_hash(request.model_dump(mode="json"))
        handoff = request.resolution_handoff
        existing = self._repository.find_by_handoff(handoff.handoff_id, payload_hash)
        if existing is not None and (existing.state != "IN_PROGRESS" or existing.application_started_at is not None):
            return self._terminal_or_resume(existing)

        if handoff.policy_evaluation is not None:
            import os
            from return_agent_contracts.review_gates import load_reviewer_gate_config
            from return_agent_contracts.user_risk import load_user_risk_config
            try:
                if path := os.environ.get("RETURN_AGENT_REVIEW_GATE_CONFIG"):
                    self._reviewer_gate_config = load_reviewer_gate_config(path)
                if path := os.environ.get("RETURN_AGENT_USER_RISK_CONFIG"):
                    self._user_risk_config = load_user_risk_config(path)
            except (ValueError,OSError):
                return self._terminal_or_resume(self._repository.create_rejected(request,payload_hash,["AUTHORIZATION_CONFIG_UNAVAILABLE"]))

        authorization = self._repository.load_authorization(handoff.handoff_id)
        rejection = self._authorization_rejection(request, authorization)
        if rejection is not None:
            rejected = self._repository.create_rejected(
                request,
                payload_hash,
                rejection,
            )
            return self._terminal_or_resume(rejected)

        assert authorization is not None
        if authorization.handoff.handoff_version == "2.0":
            from .fulfillment import check_release
            try:
                with self._session_factory() as session:
                    check_release(session,handoff,self._reviewer_gate_config,self._user_risk_config)
            except ValueError as error:
                if str(error) == "RETURN_FULFILLMENT_PENDING":
                    raise RefundExecutionUnavailableError(str(error)) from error
                return self._terminal_or_resume(self._repository.create_rejected(request,payload_hash,[str(error)]))
        order_snapshot = self._load_order_snapshot(request.resolution_handoff)
        bundle = self._policy_bundles.get_persisted_bundle(
            authorization.handoff.policy_bundle_version
        )
        try:
            if bundle is None:
                raise ContractInvariantError("policy bundle unavailable")
            validate_proposed_decision_handoff(authorization.handoff, bundle, order_snapshot)
            if handoff.outcome_source in (OutcomeSource.HUMAN_EDIT, OutcomeSource.HUMAN_APPROVE):
                record = authorization.human_record
                if record is None or record.dossier_payload is None:
                    raise ContractInvariantError("human dossier unavailable")
                dossier = HumanReviewDossier.model_validate(record.dossier_payload)
                claimed_items = dossier.claimed_line_item_ids
            else:
                # Structural validation of an already approved machine review,
                # not the source of authority for human scope expansion.
                claimed_items = sorted({
                    finding.subject for finding in handoff.review_result.reviewer_claim_findings
                    if finding.subject != "ORDER"
                })
                if not claimed_items:
                    claimed_items = authorization.handoff.proposed_decision.refund_scope.line_item_ids
            validate_review_result(
                handoff.review_result, authorization.handoff, bundle,
                order_snapshot, claimed_items,
            )
        except (ContractInvariantError, ValueError, LookupError):
            rejected = self._repository.create_rejected(
                request, payload_hash, ["CURRENT_HANDOFF_INVALID"]
            )
            return self._terminal_or_resume(rejected)
        if handoff.outcome_source in (OutcomeSource.HUMAN_EDIT, OutcomeSource.HUMAN_APPROVE):
            record = authorization.human_record
            try:
                if record is None or record.dossier_payload is None:
                    raise ContractInvariantError("human dossier unavailable")
                dossier = HumanReviewDossier.model_validate(record.dossier_payload)
                result = _HUMAN_RESULT_ADAPTER.validate_python(record.result_payload)
                amount = validate_human_decision(
                    human_corrected_decision(result, authorization.handoff),
                    dossier, order_snapshot, bundle,
                )
                if handoff.outcome_source is OutcomeSource.HUMAN_APPROVE and handoff.final_decision.amount != amount:
                    raise ContractInvariantError("human refund amount mismatch")
            except (ContractInvariantError, ValueError):
                rejected = self._repository.create_rejected(
                    request, payload_hash, ["HUMAN_DECISION_INVALID"]
                )
                return self._terminal_or_resume(rejected)
        if handoff.outcome_source is OutcomeSource.HUMAN_EDIT:
            edit_rejection = self._validate_human_edit(
                request.resolution_handoff,
                order_snapshot,
                dossier.claimed_line_item_ids,
            )
            if edit_rejection is not None:
                rejected = self._repository.create_rejected(
                    request,
                    payload_hash,
                    edit_rejection,
                )
                return self._terminal_or_resume(rejected)

        pending = self._repository.start_pending(
            execution_ref=_execution_ref(handoff.handoff_id),
            request=request,
            payload_hash=payload_hash,
            order_ref=order_snapshot.order_ref,
        )
        return self._resume(pending,authorization_checked=True)

    def get_status(self, execution_ref: str) -> RefundExecutionRecord | None:
        existing = self._repository.find(execution_ref)
        if existing is None:
            return None
        if existing.state == "IN_PROGRESS":
            raise RefundExecutionUnavailableError(
                "refund execution is still awaiting an application result"
            )
        return self._terminal_record(existing)

    def _terminal_or_resume(
        self,
        execution: PersistedRefundExecution,
    ) -> RefundExecutionRecord:
        if execution.state == "IN_PROGRESS":
            return self._resume(execution)
        return self._terminal_record(execution)

    def _resume(self, execution: PersistedRefundExecution, *, authorization_checked: bool = False) -> RefundExecutionRecord:
        request = self._repository._parse_execute_request(execution.request_payload)
        if request.resolution_handoff.policy_evaluation is not None and execution.application_started_at is None and not authorization_checked:
            return self.execute(request)
        try:
            execution = self._repository.mark_application_started(
                execution.execution_ref,
                execution.payload_hash,
            )
        except Exception as error:  # noqa: BLE001 - retry is safe before mutation
            raise RefundExecutionUnavailableError(
                "refund execution could not record its application attempt"
            ) from error
        if execution.state != "IN_PROGRESS":
            return self._terminal_record(execution)
        try:
            application_result = _APPLICATION_RESULT_ADAPTER.validate_python(
                self._refund_application_provider.apply(
                    ApplyRefundRequest(
                        execution_ref=execution.execution_ref,
                        resolution_handoff=request.resolution_handoff,
                    )
                )
            )
        except Exception as error:  # noqa: BLE001 - outcome is unknown until replay
            raise RefundExecutionUnavailableError(
                "refund application outcome is unavailable"
            ) from error
        try:
            completed = self._repository.complete(
                execution.execution_ref,
                execution.payload_hash,
                application_result,
            )
        except Exception as error:  # noqa: BLE001 - outcome is recoverable by replay
            raise RefundExecutionUnavailableError(
                "refund application result could not be persisted"
            ) from error
        return self._terminal_record(completed)

    def _terminal_record(
        self,
        execution: PersistedRefundExecution,
    ) -> RefundExecutionRecord:
        if execution.application_result_payload is None:
            raise RefundExecutionUnavailableError(
                "refund execution has no terminal application result"
            )
        try:
            application_result = _APPLICATION_RESULT_ADAPTER.validate_python(
                execution.application_result_payload
            )
            payload = {
                "execution_ref": execution.execution_ref,
                "handoff_id": execution.handoff_id,
                "case_ref": execution.case_ref,
                "status": (
                    RefundExecutionStatus.SUCCEEDED
                    if execution.state == "SUCCEEDED"
                    else RefundExecutionStatus.REJECTED
                ),
                "application_result": application_result,
                "created_at": execution.created_at,
                "updated_at": execution.updated_at,
            }
            record = _EXECUTION_RECORD_ADAPTER.validate_python(payload)
        except ValidationError as error:
            raise RefundExecutionDataIntegrityError(
                "persisted refund execution violates its public contract"
            ) from error
        if (
            record.status is RefundExecutionStatus.SUCCEEDED
            and application_result.status is not RefundApplicationStatus.APPLIED
        ) or (
            record.status is RefundExecutionStatus.REJECTED
            and application_result.status is not RefundApplicationStatus.REJECTED
        ):
            raise RefundExecutionDataIntegrityError(
                "refund execution status disagrees with its application result"
            )
        return record

    def _authorization_rejection(
        self,
        request: ExecuteRefundRequest,
        authorization: PersistedAuthorization | None,
    ) -> list[str] | None:
        resolution = request.resolution_handoff
        if resolution.execution_blocked:
            return ["EXECUTION_BLOCKED"]
        if resolution.final_decision.action is ResolutionAction.DECLINE:
            return ["FINAL_DECISION_DECLINED"]
        if authorization is None:
            return ["AUTHORIZATION_NOT_FOUND"]
        if resolution.case_ref != authorization.handoff.case_ref:
            return ["CASE_REF_MISMATCH"]
        if (
            authorization.handoff.proposed_decision.action
            is not ResolutionAction.FULL_REFUND
            and resolution.outcome_source is not OutcomeSource.HUMAN_EDIT
        ):
            return ["ORIGINAL_PROPOSAL_NOT_REFUND"]
        if authorization.verification.status is not VerificationStatus.PASS:
            return ["VERIFICATION_NOT_PASSED"]

        source = resolution.outcome_source
        if source is OutcomeSource.REVIEWER_APPROVE:
            if resolution.review_result.verdict is not ReviewVerdict.APPROVE:
                return ["REVIEW_NOT_APPROVED"]
            if not self._matches_original_proposal(resolution, authorization.handoff):
                return ["FINAL_DECISION_MISMATCH"]
            decision = authorization.handoff.proposed_decision
            gate = evaluate_review_gate(decision.action, decision.amount, decision.currency, self._reviewer_gate_config)
            if resolution.review_gate != gate:
                return ["REVIEW_GATE_INVALID"]
            if gate.status != "PASS":
                return ["HUMAN_AUTHORIZATION_REQUIRED"]
            if authorization.handoff.handoff_version == "2.0":
                risk = resolution.user_risk_gate
                if risk is None or risk.snapshot_ref is None:
                    return ["USER_RISK_GATE_MISSING"]
                try:
                    snapshot = self._user_risk_provider.load_snapshot(risk.snapshot_ref)
                    if snapshot.case_ref != resolution.case_ref or snapshot.reason_code != decision.reason_code:
                        return ["USER_RISK_SNAPSHOT_INVALID"]
                    expected_risk = evaluate_user_risk(decision.action,snapshot,self._user_risk_config)
                except (ValueError,LookupError):
                    return ["USER_RISK_SNAPSHOT_INVALID"]
                if risk != expected_risk:
                    return ["USER_RISK_GATE_INVALID"]
                if expected_risk.status != "PASS":
                    return ["HUMAN_AUTHORIZATION_REQUIRED"]
            return None
        if source is OutcomeSource.HUMAN_APPROVE:
            if not self._matches_human_authorization(resolution, authorization):
                return ["HUMAN_REVIEW_NOT_AUTHORIZED"]
            if not self._matches_original_proposal(resolution, authorization.handoff):
                return ["FINAL_DECISION_MISMATCH"]
            return None
        if source is OutcomeSource.HUMAN_EDIT:
            if not self._matches_human_authorization(resolution, authorization):
                return ["HUMAN_REVIEW_NOT_AUTHORIZED"]
            return None
        return ["OUTCOME_SOURCE_NOT_EXECUTABLE"]

    def _matches_human_authorization(
        self, resolution: ResolutionHandoff, authorization: PersistedAuthorization,
    ) -> bool:
        record = authorization.human_record
        if record is None or record.result_payload is None or record.reviewed_at is None:
            return False
        if (record.handoff_payload != authorization.handoff.model_dump(mode="json")
                or record.review_payload != resolution.review_result.model_dump(mode="json")):
            return False
        try:
            dossier = HumanReviewDossier.model_validate(record.dossier_payload)
            validate_human_review_entry(authorization.handoff, resolution.review_result, dossier, self._reviewer_gate_config, self._user_risk_config)
            with self._session_factory() as session:
                validate_persisted_dossier_snapshot(session, dossier, resolution.case_ref)
            if resolution.review_gate != dossier.review_gate:
                return False
            if resolution.user_risk_gate != dossier.user_risk_gate:
                return False
        except ValueError:
            return False
        expected_hash = _canonical_hash({
            "handoff": record.handoff_payload, "review": record.review_payload,
            **({"dossier": record.dossier_payload} if record.dossier_payload else {}),
        })
        if record.payload_hash != expected_hash or record.case_ref != resolution.case_ref:
            raise RefundExecutionDataIntegrityError("human authorization metadata mismatch")
        try:
            result = _HUMAN_RESULT_ADAPTER.validate_python(record.result_payload)
        except ValidationError as error:
            raise RefundExecutionDataIntegrityError("invalid human authorization result") from error
        if resolution.outcome_source is OutcomeSource.HUMAN_APPROVE:
            return result.decision.value == "APPROVE"
        if resolution.outcome_source is OutcomeSource.HUMAN_EDIT:
            if result.decision.value != "EDIT":
                return False
            correction = result.corrected_decision
            decision = resolution.final_decision
            return (
                correction.action == decision.action
                and correction.refund_scope == decision.refund_scope
                and correction.return_decision == decision.return_decision
            )
        return False

    def _load_order_snapshot(self, resolution: ResolutionHandoff) -> OrderSnapshot:
        try:
            context = self._case_context_provider.load_case_context(resolution.case_ref)
            validate_case_context_load_result(resolution.case_ref, context)
        except Exception as error:  # noqa: BLE001 - authoritative context is required
            raise RefundExecutionUnavailableError(
                "refund execution could not load current case context"
            ) from error
        return context.order_snapshot

    @staticmethod
    def _matches_original_proposal(
        resolution: ResolutionHandoff,
        handoff: ProposedDecisionHandoff,
    ) -> bool:
        decision = handoff.proposed_decision
        if decision.action is not ResolutionAction.FULL_REFUND:
            return False
        expected = AgentFullRefundFinalDecision(
            action=decision.action,
            refund_scope=decision.refund_scope,
            amount=decision.amount,
            currency=decision.currency,
            return_decision=decision.return_decision,
            reason_code=decision.reason_code,
        )
        return resolution.final_decision.model_dump(mode="json") == expected.model_dump(
            mode="json"
        )

    @staticmethod
    def _validate_human_edit(
        resolution: ResolutionHandoff,
        order_snapshot: OrderSnapshot,
        claimed_line_item_ids: list[str],
    ) -> list[str] | None:
        decision = resolution.final_decision
        if not isinstance(decision, HumanEditedFullRefundFinalDecision):
            return ["HUMAN_EDIT_DECISION_INVALID"]
        line_items = {item.line_item_id: item for item in order_snapshot.line_items}
        scope = decision.refund_scope.line_item_ids
        if not set(scope).issubset(
            claimed_line_item_ids
        ):
            return ["REFUND_SCOPE_NOT_AUTHORIZED"]
        if not set(scope).issubset(line_items):
            return ["REFUND_SCOPE_UNAVAILABLE"]
        expected_amount = sum(
            (line_items[line_item_ref].refundable_amount for line_item_ref in scope),
            Decimal(0),
        )
        if decision.amount != expected_amount:
            return ["REFUND_AMOUNT_MISMATCH"]
        if decision.amount > order_snapshot.refundable_amount_max:
            return ["REFUND_AMOUNT_EXCEEDS_MAXIMUM"]
        if decision.currency != order_snapshot.currency:
            return ["REFUND_CURRENCY_MISMATCH"]
        return None
