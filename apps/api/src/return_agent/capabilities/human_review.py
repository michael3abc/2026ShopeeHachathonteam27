"""Durable Human Review submission, completion, and polling capability."""

from __future__ import annotations
from return_agent_contracts.user_risk import UserRiskConfig
from return_agent_contracts.review_gates import ReviewerGateConfig
from return_agent_contracts.validation import validate_human_review_entry

from return_agent_contracts.models import ReviewResult

import json
from datetime import UTC, datetime
from hashlib import sha256

from pydantic import TypeAdapter, ValidationError
from return_agent_contracts.adapters import to_human_review_result
from return_agent_contracts.enums import ReviewVerdict
from return_agent_contracts.interfaces import CaseContextProvider, HumanReviewProvider
from return_agent_contracts.models import (
    REVIEW_REVISION_LIMIT,
    HumanReviewDossier,
    HumanReviewResult,
    ProposedDecisionHandoff,
)
from return_agent_contracts.ui import ReviewDecision
from return_agent_contracts.validation import (
    ContractInvariantError,
    human_corrected_decision,
    validate_applicable_policy_bundle,
    validate_case_context_load_result,
    validate_human_decision,
    validate_proposed_decision_handoff,
)
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from return_agent.capabilities.safety import SqlAlchemyPolicyBundleRepository
from return_agent.db.models import HandoffVerificationRecord, HumanReviewRecord
from .user_risk import validate_persisted_dossier_snapshot

_RESULT_ADAPTER = TypeAdapter(HumanReviewResult)


class HumanReviewConflictError(ValueError):
    """A stable handoff or pending review was reused inconsistently."""


class HumanReviewNotFoundError(LookupError):
    """No pending review exists for the supplied reference or case."""


class HumanReviewDataIntegrityError(RuntimeError):
    """Persisted review data cannot satisfy the shared DTO."""


def _canonical_hash(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256(payload.encode("utf-8")).hexdigest()


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class SqlAlchemyHumanReviewProvider(HumanReviewProvider):
    """Store an unresolved Reviewer request once and expose its eventual result."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        case_context_provider: CaseContextProvider | None = None,
        reviewer_gate_config: ReviewerGateConfig | None = None,
        user_risk_config: UserRiskConfig | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._reviewer_gate_config = reviewer_gate_config or ReviewerGateConfig()
        self._user_risk_config = user_risk_config or UserRiskConfig()
        self._case_context_provider = case_context_provider
        self._policy_bundles = SqlAlchemyPolicyBundleRepository(session_factory)

    def submit_for_review(
        self,
        handoff: ProposedDecisionHandoff,
        review: ReviewResult,
        dossier: HumanReviewDossier | None = None,
    ) -> str:
        if dossier is not None and (
            dossier.proposal_history[-1] != handoff
            or dossier.review_history[-1] != review
        ):
            raise HumanReviewConflictError("dossier does not match the final review")
        if dossier is not None:
            try:
                validate_human_review_entry(handoff, review, dossier, self._reviewer_gate_config, self._user_risk_config)
            except ValueError as error:
                raise HumanReviewConflictError(str(error)) from error
        elif review.verdict is not ReviewVerdict.REVISE or handoff.revision_round < REVIEW_REVISION_LIMIT:
            raise HumanReviewConflictError(
                f"Human Review requires REVISE after {REVIEW_REVISION_LIMIT} completed revisions"
            )
        payload_hash = _canonical_hash(
            {
                "handoff": handoff.model_dump(mode="json"),
                "review": review.model_dump(mode="json"),
                **({"dossier": dossier.model_dump(mode="json")} if dossier else {}),
            }
        )
        review_ref = f"human-review:{handoff.handoff_id}"
        with self._session_factory.begin() as session:
            if dossier is not None:
                try:
                    validate_persisted_dossier_snapshot(session, dossier, handoff.case_ref)
                except ValueError as error:
                    raise HumanReviewConflictError(str(error)) from error
            existing = session.scalar(
                select(HumanReviewRecord)
                .where(HumanReviewRecord.handoff_id == handoff.handoff_id)
                .with_for_update()
            )
            if existing is not None:
                if existing.payload_hash != payload_hash:
                    raise HumanReviewConflictError(
                        "handoff_id is already associated with another review payload"
                    )
                if existing.dossier_payload != (
                    dossier.model_dump(mode="json") if dossier else None
                ):
                    raise HumanReviewConflictError("handoff dossier changed")
                return existing.review_ref
            session.add(
                HumanReviewRecord(
                    review_ref=review_ref,
                    handoff_id=handoff.handoff_id,
                    case_ref=handoff.case_ref,
                    payload_hash=payload_hash,
                    handoff_payload=handoff.model_dump(mode="json"),
                    review_payload=review.model_dump(mode="json"),
                    dossier_payload=dossier.model_dump(mode="json")
                    if dossier
                    else None,
                    result_payload=None,
                    submitted_at=datetime.now(UTC),
                    reviewed_at=None,
                )
            )
        return review_ref

    def fetch_result(self, review_ref: str) -> HumanReviewResult | None:
        with self._session_factory() as session:
            record = session.get(HumanReviewRecord, review_ref)
        if record is None:
            raise HumanReviewNotFoundError(review_ref)
        if record.result_payload is None:
            return None
        try:
            return _RESULT_ADAPTER.validate_python(record.result_payload)
        except ValidationError as error:
            raise HumanReviewDataIntegrityError(
                f"review {review_ref} has an invalid result"
            ) from error

    def complete_for_case(
        self,
        session: Session,
        *,
        case_ref: str,
        decision: ReviewDecision,
    ) -> HumanReviewResult:
        record = session.scalar(
            select(HumanReviewRecord)
            .where(HumanReviewRecord.case_ref == case_ref)
            .order_by(HumanReviewRecord.submitted_at.desc())
            .with_for_update()
            .limit(1)
        )
        if record is None:
            raise HumanReviewNotFoundError(case_ref)
        if record.result_payload is not None:
            raise HumanReviewConflictError("Human Review result is already final")
        if decision.handoff_id != record.handoff_id:
            raise HumanReviewConflictError(
                "Review handoff is missing or stale; refresh the case"
            )
        reviewed_at = datetime.now(UTC)
        result = to_human_review_result(
            decision,
            final_resolution_ref=f"resolution:{record.review_ref}",
            reviewed_at=reviewed_at,
        )
        if record.dossier_payload is None:
            raise HumanReviewConflictError(
                "Historical review lacks original scope and history; cannot adjudicate"
            )
        dossier = HumanReviewDossier.model_validate(record.dossier_payload)
        try:
            validate_persisted_dossier_snapshot(session, dossier, case_ref)
            validate_human_review_entry(
                ProposedDecisionHandoff.model_validate(record.handoff_payload),
                TypeAdapter(ReviewResult).validate_python(record.review_payload),
                dossier, self._reviewer_gate_config, self._user_risk_config,
            )
        except ValueError as error:
            raise HumanReviewConflictError(str(error)) from error
        if record.payload_hash != _canonical_hash(
            {
                "handoff": record.handoff_payload,
                "review": record.review_payload,
                "dossier": record.dossier_payload,
            }
        ):
            raise HumanReviewConflictError("Stored review dossier integrity mismatch")
        verification = session.scalar(
            select(HandoffVerificationRecord).where(
                HandoffVerificationRecord.handoff_id == record.handoff_id
            )
        )
        if (
            verification is None
            or verification.verification_status != "PASS"
            or verification.handoff_payload != record.handoff_payload
        ):
            raise HumanReviewConflictError(
                "Original handoff verification is unavailable or invalid"
            )
        if self._case_context_provider is None:
            raise HumanReviewConflictError("Current order verification is unavailable")
        try:
            context = self._case_context_provider.load_case_context(case_ref)
            validate_case_context_load_result(case_ref, context)
            bundle = self._policy_bundles.get_persisted_bundle(
                dossier.policy_bundle.policy_bundle_version
            )
            if bundle is None:
                raise ContractInvariantError("Policy bundle unavailable")
            validate_applicable_policy_bundle(context.case_context, bundle)
            validate_proposed_decision_handoff(
                dossier.proposal_history[-1], bundle, context.order_snapshot
            )
            validate_human_decision(
                human_corrected_decision(result, dossier.proposal_history[-1]),
                dossier,
                context.order_snapshot,
                bundle,
            )
            if bundle.schema_version == "v2" and result.decision.value != "REJECT":
                from return_agent_contracts.policy_v2 import evaluate_policy
                from .fulfillment import save_evaluation
                corrected = human_corrected_decision(result,dossier.proposal_history[-1])
                if corrected.action.value == "FULL_REFUND":
                    findings = corrected.policy_findings if result.decision.value == "EDIT" else dossier.review_history[-1].reviewer_claim_findings
                    if findings is None:
                        raise ContractInvariantError("v2 Human EDIT requires explicit policy findings")
                    evaluation = evaluate_policy(context=context.case_context,order=context.order_snapshot,bundle=bundle,
                        claimed_line_item_ids=dossier.claimed_line_item_ids,findings=findings,
                        evidence=dossier.proposal_history[-1].evidence_bundle,selection=dossier.proposal_history[-1].policy_selection,evaluated_at=reviewed_at)
                    if any(item.status != "ELIGIBLE" for item in evaluation.item_evaluations if item.path_id is bundle.selected_path_id):
                        raise ContractInvariantError("human findings do not establish the selected path")
                    result = result.model_copy(update={"policy_evaluation":evaluation})
                    save_evaluation(session,evaluation)
        except (ContractInvariantError, ValueError, LookupError, RuntimeError) as error:
            raise HumanReviewConflictError(str(error)) from error
        record.result_payload = result.model_dump(mode="json")
        record.reviewed_at = reviewed_at
        return result

    def pending_review_ref(self, session: Session, case_ref: str) -> str:
        record = session.scalar(
            select(HumanReviewRecord)
            .where(
                HumanReviewRecord.case_ref == case_ref,
                HumanReviewRecord.result_payload.is_(None),
            )
            .order_by(HumanReviewRecord.submitted_at.desc())
            .limit(1)
        )
        if record is None:
            raise HumanReviewNotFoundError(case_ref)
        return record.review_ref
