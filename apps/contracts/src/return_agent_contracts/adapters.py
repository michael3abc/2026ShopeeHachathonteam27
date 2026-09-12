"""Explicit projections between core Agent DTOs and Demo/UI contracts."""

from __future__ import annotations

from .models import ReviewResult

from collections.abc import Sequence

from .base import UTCDateTime
from .enums import HumanDecision, ResolutionAction
from .models import (
    ApprovedHumanReviewResult,
    ApprovedMemory,
    ClarificationRequest,
    EditedHumanReviewResult,
    EvidenceRequest,
    HumanReviewDossier,
    HumanReviewResult,
    MemoryCandidate,
    MemoryRetrievalObservation,
    MemoryScope,
    PolicyBundle,
    ProposedDecisionHandoff,
    RejectedHumanReviewResult,
    RevisedReviewResult,
)
from .ui import (
    ApprovedMemoryRecordView,
    ClarificationInterruptPayload,
    DeclineHumanReviewPayload,
    EvidenceDisplayRef,
    EvidenceRequestView,
    FullRefundHumanReviewPayload,
    HumanReviewPayload,
    MemoryRecordView,
    MemoryRetrievalPayload,
    PolicyDisplayRef,
    ReviewDecision,
)


class UIAdapterError(ValueError):
    """Raised when a core value cannot safely be projected to a UI contract."""


def to_clarification_interrupt_payload(
    case_ref: str, request: ClarificationRequest
) -> ClarificationInterruptPayload:
    return ClarificationInterruptPayload(
        interrupt_kind="CLARIFICATION",
        case_ref=case_ref,
        request=request,
    )


def to_evidence_request_view(
    case_ref: str, evidence_request: EvidenceRequest
) -> EvidenceRequestView:
    return EvidenceRequestView(
        case_ref=case_ref,
        request_id=evidence_request.request_id,
        user_message=evidence_request.user_message,
        missing_claims=evidence_request.missing_claims,
        accepted_evidence_types=evidence_request.accepted_evidence_types,
        policy_refs=evidence_request.policy_refs,
    )


def to_human_review_payload(
    handoff: ProposedDecisionHandoff,
    review: ReviewResult,
    policy_bundle: PolicyBundle,
    memory_ids: Sequence[str] = (),
    dossier: HumanReviewDossier | None = None,
) -> HumanReviewPayload:
    """Show the unresolved Reviewer objections after the revision budget ends."""

    if dossier is None and not isinstance(review, RevisedReviewResult):
        raise UIAdapterError("Approved human review requires an amount-gate dossier")
    clauses = {clause.clause_id: clause for clause in policy_bundle.clauses}
    try:
        policy_hits = [
            PolicyDisplayRef(
                clause_id=policy_ref,
                policy_version=clauses[policy_ref].policy_version,
                title=policy_ref,
                excerpt=clauses[policy_ref].text,
            )
            for policy_ref in handoff.policy_refs
        ]
    except KeyError as error:
        raise UIAdapterError(
            f"handoff policy reference is absent from PolicyBundle: {error.args[0]}"
        ) from error

    decision = handoff.proposed_decision
    common = {
        "case_ref": handoff.case_ref,
        "handoff_id": handoff.handoff_id,
        "review_result": review,
        "routing_reason": dossier.routing_reason if dossier else "REVISION_BUDGET_EXCEEDED",
        "dossier": dossier,
        "action": decision.action,
        "refund_scope": decision.refund_scope,
        "amount": decision.amount,
        "currency": decision.currency,
        "rationale_summary": handoff.rationale_summary,
        "evidence_refs": [
            EvidenceDisplayRef(
                evidence_id=item.evidence_id,
                type=item.type,
                subject=item.subject,
                artifact_ref=item.artifact_ref,
                caption=item.extracted_summary,
            )
            for item in handoff.evidence_bundle
        ],
        "policy_hits": policy_hits,
        "memories_used": list(memory_ids),
    }
    if decision.action is ResolutionAction.FULL_REFUND:
        return FullRefundHumanReviewPayload(
            **common,
            return_decision=decision.return_decision,
        )
    return DeclineHumanReviewPayload(**common)


def to_human_review_result(
    review_decision: ReviewDecision,
    final_resolution_ref: str,
    reviewed_at: UTCDateTime,
) -> HumanReviewResult:
    """Add Backend-owned audit fields to an accepted UI resume payload."""

    if review_decision.decision is HumanDecision.EDIT:
        return EditedHumanReviewResult(
            decision=HumanDecision.EDIT,
            review_note=review_decision.review_note,
            reviewer_id=review_decision.reviewer_id,
            generalizable=review_decision.generalizable,
            corrected_decision=review_decision.corrected_decision,
            correction_reason_code=review_decision.correction_reason_code,
            final_resolution_ref=final_resolution_ref,
            reviewed_at=reviewed_at,
        )
    if review_decision.decision is HumanDecision.APPROVE:
        return ApprovedHumanReviewResult(
            decision=HumanDecision.APPROVE,
            review_note=review_decision.review_note,
            reviewer_id=review_decision.reviewer_id,
            generalizable=review_decision.generalizable,
            final_resolution_ref=final_resolution_ref,
            reviewed_at=reviewed_at,
        )
    return RejectedHumanReviewResult(
        decision=HumanDecision.REJECT,
        review_note=review_decision.review_note,
        reviewer_id=review_decision.reviewer_id,
        generalizable=review_decision.generalizable,
        final_resolution_ref=final_resolution_ref,
        reviewed_at=reviewed_at,
    )


def to_memory_record_view(
    memory: MemoryCandidate | ApprovedMemory,
    *,
    observed_at: str | None = None,
    hit_count: int | None = None,
) -> MemoryRecordView:
    """Render candidate/approved memory without turning a candidate into retrievable data."""

    if isinstance(memory, MemoryCandidate):
        if observed_at is None:
            raise UIAdapterError("candidate memory display requires observed_at")
        created_at = observed_at
        source_case_refs = memory.source_case_refs
        view_type = MemoryRecordView
    else:
        created_at = memory.approved_at
        source_case_refs = []
        view_type = ApprovedMemoryRecordView

    return view_type(
        memory_id=memory.memory_id,
        status=memory.status,
        trigger="；".join(memory.trigger_conditions),
        boundary=_memory_boundary(memory.scope),
        action=memory.recommended_behavior,
        scope=memory.scope,
        source_case_refs=source_case_refs,
        created_at=created_at,
        hit_count=hit_count,
    )


def to_memory_retrieval_payload(
    result: MemoryRetrievalObservation,
) -> MemoryRetrievalPayload:
    return MemoryRetrievalPayload.model_validate(result.model_dump(mode="json"))


def _memory_boundary(scope: MemoryScope) -> str:
    parts = [f"market={scope.market}"]
    if scope.reason_codes:
        parts.append(
            "reason_codes=" + ",".join(code.value for code in scope.reason_codes)
        )
    if scope.claim_ids:
        parts.append("claim_ids=" + ",".join(claim.value for claim in scope.claim_ids))
    if scope.categories:
        parts.append("categories=" + ",".join(scope.categories))
    return "; ".join(parts)
