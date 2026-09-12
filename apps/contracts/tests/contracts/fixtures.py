"""Small valid fixtures derived from the contract examples."""

from __future__ import annotations

from return_agent_contracts.enums import (
    ClaimId,
    ClaimStatus,
    EvidenceStatus,
    EvidenceType,
    MemoryStatus,
    ReasonCode,
    ResolutionAction,
    ReturnPolicy,
)
from return_agent_contracts.models import (
    ApplicableConditions,
    ApprovalEvidenceAssessment,
    CaseContext,
    CaseContextLoadResult,
    ClaimFinding,
    EvidenceItem,
    EvidenceRequest,
    FullRefundProposedDecision,
    FullRefundProposedDecisionDraft,
    MemoryCandidate,
    MemoryScope,
    MissingClaim,
    ModelJudgmentReturnDecision,
    NonEmptyRefundScope,
    OrderLineItem,
    OrderSnapshot,
    PolicyBundle,
    PolicyClause,
    ProposedDecisionHandoff,
    WaivedReturnRequirement,
)

TIME = "2026-09-01T10:00:00Z"


def order_snapshot() -> OrderSnapshot:
    return OrderSnapshot(
        order_snapshot_ref="ORDER-001@12",
        order_ref="ORDER-001",
        snapshot_version=12,
        captured_at=TIME,
        currency="TWD",
        delivered_at="2026-08-25T09:00:00Z",
        line_items=[
            OrderLineItem(
                line_item_id="LI-001",
                sku_ref="SKU-A",
                category_ref="CAT-AUDIO-HEADPHONES",
                title="Headphones",
                quantity=1,
                refundable_amount="700",
            ),
            OrderLineItem(
                line_item_id="LI-002",
                sku_ref="SKU-B",
                category_ref="CAT-AUDIO-SPEAKERS",
                title="Speaker",
                quantity=1,
                refundable_amount="1200",
            ),
        ],
        refundable_amount_max="1900",
        already_refunded_amount="0",
    )


def case_context() -> CaseContext:
    return CaseContext(
        case_ref="CASE-001",
        order_ref="ORDER-001",
        market="TW",
        case_opened_at=TIME,
        snapshot_version=3,
    )


def case_context_load_result() -> CaseContextLoadResult:
    return CaseContextLoadResult(
        case_context=case_context(), order_snapshot=order_snapshot()
    )


def policy_bundle(
    return_policy: ReturnPolicy = ReturnPolicy.MODEL_JUDGMENT,
) -> PolicyBundle:
    return PolicyBundle(
        policy_bundle_version="bundle:2026-09-01T10:00:05Z",
        retrieval_status="OK",
        retrieved_at="2026-09-01T10:00:05Z",
        clauses=[
            PolicyClause(
                clause_id="POLICY-12:v3#4.2",
                policy_version="POLICY-12:v3",
                effective_from="2026-01-01T00:00:00Z",
                effective_to=None,
                applicable_conditions=ApplicableConditions(
                    markets=["TW"],
                    reason_codes=[ReasonCode.ITEM_DAMAGED],
                    categories=["CAT-AUDIO-SPEAKERS"],
                ),
                required_claim_ids=[
                    ClaimId.DELIVERY_CONFIRMED,
                    ClaimId.ORDER_WITHIN_RETURN_WINDOW,
                    ClaimId.ITEM_PHYSICALLY_DAMAGED,
                    ClaimId.DAMAGE_PRESENT_ON_ARRIVAL,
                ],
                allowed_actions=[
                    ResolutionAction.FULL_REFUND,
                    ResolutionAction.DECLINE,
                ],
                return_policy=return_policy,
                text="Delivered-damaged items may be refunded.",
            )
        ],
    )


def evidence_item() -> EvidenceItem:
    return EvidenceItem(
        evidence_id="EV-002",
        type="IMAGE",
        source="USER",
        subject="LI-002",
        artifact_ref="artifact://evidence/EV-002",
        extracted_summary="Packaging damage and item crack are both visible.",
        collected_at="2026-09-01T10:40:00Z",
    )


def supported_assessment() -> ApprovalEvidenceAssessment:
    return ApprovalEvidenceAssessment(
        evidence_status=EvidenceStatus.SUFFICIENT_FOR_APPROVAL,
        claim_registry_version="claim-registry:1.0",
        claim_findings=[
            ClaimFinding(
                claim_id=ClaimId.DELIVERY_CONFIRMED,
                subject="ORDER",
                status=ClaimStatus.SUPPORTED,
                supporting_evidence_refs=["EV-SYS-001"],
                explanation="Delivered.",
            ),
            ClaimFinding(
                claim_id=ClaimId.ORDER_WITHIN_RETURN_WINDOW,
                subject="ORDER",
                status=ClaimStatus.SUPPORTED,
                supporting_evidence_refs=["EV-SYS-002"],
                explanation="Within window.",
            ),
            ClaimFinding(
                claim_id=ClaimId.ITEM_PHYSICALLY_DAMAGED,
                subject="LI-002",
                status=ClaimStatus.SUPPORTED,
                supporting_evidence_refs=["EV-002"],
                explanation="Damage visible.",
            ),
            ClaimFinding(
                claim_id=ClaimId.DAMAGE_PRESENT_ON_ARRIVAL,
                subject="LI-002",
                status=ClaimStatus.SUPPORTED,
                supporting_evidence_refs=["EV-002"],
                explanation="Packaging and damage match.",
            ),
        ],
    )


def evidence_request() -> EvidenceRequest:
    return EvidenceRequest(
        request_id="EREQ-001",
        missing_claims=[
            MissingClaim(claim_id=ClaimId.DAMAGE_PRESENT_ON_ARRIVAL, subject="LI-002")
        ],
        accepted_evidence_types=[EvidenceType.IMAGE, EvidenceType.VIDEO],
        user_message="Show the packaging and damaged item together.",
        policy_refs=["POLICY-12:v3#4.2"],
    )


def proposed_decision_draft() -> FullRefundProposedDecisionDraft:
    return FullRefundProposedDecisionDraft(
        action=ResolutionAction.FULL_REFUND,
        refund_scope=NonEmptyRefundScope(line_item_ids=["LI-002"]),
        reason_code=ReasonCode.ITEM_DAMAGED,
        return_decision=ModelJudgmentReturnDecision(
            source="MODEL_JUDGMENT",
            requirement=WaivedReturnRequirement(
                required=False,
                reason_code="ITEM_UNSALVAGEABLE",
            ),
        ),
        policy_refs=["POLICY-12:v3#4.2"],
        evidence_refs=["EV-002"],
        rationale_summary="The required claims are supported.",
    )


def proposed_handoff() -> ProposedDecisionHandoff:
    return ProposedDecisionHandoff(
        handoff_version="1.0",
        handoff_id="HANDOFF-001",
        case_ref="CASE-001",
        order_snapshot_ref="ORDER-001@12",
        policy_bundle_version="bundle:2026-09-01T10:00:05Z",
        claim_registry_version="claim-registry:1.0",
        proposed_decision=FullRefundProposedDecision(
            action=ResolutionAction.FULL_REFUND,
            refund_scope=NonEmptyRefundScope(line_item_ids=["LI-002"]),
            amount="1200",
            currency="TWD",
            reason_code=ReasonCode.ITEM_DAMAGED,
            return_decision=ModelJudgmentReturnDecision(
                source="MODEL_JUDGMENT",
                requirement=WaivedReturnRequirement(
                    required=False,
                    reason_code="ITEM_UNSALVAGEABLE",
                ),
            ),
            policy_refs=["POLICY-12:v3#4.2"],
            evidence_refs=["EV-002"],
        ),
        evidence_bundle=[evidence_item()],
        policy_refs=["POLICY-12:v3#4.2"],
        rationale_summary="The required claims are supported.",
        revision_round=0,
        agent_prompt_version="resolver:1.0",
    )


def memory_candidate() -> MemoryCandidate:
    return MemoryCandidate(
        memory_id="MEM-001",
        retrieval_summary="Damaged-item evidence is incomplete; request the required evidence together.",
        trigger_conditions=[
            "Only a product close-up is available and two user-evidence claims are missing."
        ],
        recommended_behavior="Request all missing evidence in one EvidenceRequest.",
        rationale="A human correction showed this reduces repeated evidence rounds.",
        source_case_refs=["CASE-005"],
        source_revision_event_refs=["REV-001"],
        policy_version="POLICY-12:v3",
        claim_registry_version="claim-registry:1.0",
        scope=MemoryScope(
            market="TW",
            reason_codes=[ReasonCode.ITEM_DAMAGED],
            claim_ids=[ClaimId.DAMAGE_PRESENT_ON_ARRIVAL],
            categories=["CAT-AUDIO-SPEAKERS"],
        ),
        confidence=0.72,
        status=MemoryStatus.CANDIDATE,
    )


def approved_review():
    from return_agent_contracts.models import ApprovedReviewResult
    return ApprovedReviewResult(
        verdict="APPROVE", reviewer_claim_findings=supported_assessment().claim_findings,
        revision_reasons=[], reviewer_prompt_version="reviewer:2.0", reviewed_at=TIME,
    )


def revised_review():
    from return_agent_contracts.models import RevisedReviewResult
    return RevisedReviewResult(
        verdict="REVISE", reviewer_claim_findings=supported_assessment().claim_findings,
        revision_reasons=[{"code": "DECISION_INCONSISTENT", "subject": "LI-002",
            "message": "The return explanation is not supported.",
            "required_change": "Explain the return requirement using cited facts.",
            "policy_refs": [policy_bundle().clauses[0].clause_id], "evidence_refs": []}],
        reviewer_prompt_version="reviewer:2.0", reviewed_at=TIME,
    )
