"""Reusable runtime fixtures."""

from __future__ import annotations

from collections import deque
from datetime import UTC, datetime

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from return_agent_contracts.enums import (
    ClaimId,
    ClaimStatus,
    EvidenceStatus,
    ResolutionAction,
    ReturnPolicy,
)
from return_agent_contracts.models import (
    ApplicableConditions,
    ApprovalEvidenceAssessment,
    ApprovedReviewResult,
    CaseContext,
    CaseContextLoadResult,
    ClaimFinding,
    EvidenceItem,
    FullRefundProposedDecisionDraft,
    ModelJudgmentReturnDecision,
    NonEmptyRefundScope,
    OrderLineItem,
    OrderSnapshot,
    PassedVerificationResult,
    PolicyBundle,
    PolicyClause,
    ResolverDraftOutput,
    UserTurn,
    WaivedReturnRequirement,
)
from return_agent_runtime import (
    AgentDependencies,
    ReturnAgentRuntime,
    create_checkpoint_serializer,
)
from return_agent_runtime.model import ModelTask

from .fakes import (
    CaseProviderFake,
    EvidenceProviderFake,
    FrozenClock,
    HumanReviewProviderFake,
    MemoryStoreFake,
    PolicyProviderFake,
    QueuedModel,
    VerificationProviderFake,
)

TIME = "2026-09-01T10:00:00Z"


def user_turn(*, text: str = "ORDER-001 的 Speaker 到貨時破損", artifacts=()):
    return UserTurn(
        turn_id="TURN-001",
        role="USER",
        text=text,
        attached_artifact_refs=list(artifacts),
        received_at=TIME,
    )


def order_snapshot(*, multi: bool = False) -> OrderSnapshot:
    items = []
    if multi:
        items.append(
            OrderLineItem(
                line_item_id="LI-001",
                sku_ref="SKU-A",
                category_ref="CAT-AUDIO-HEADPHONES",
                title="Headphones",
                quantity=1,
                refundable_amount="700",
            )
        )
    items.append(
        OrderLineItem(
            line_item_id="LI-002",
            sku_ref="SKU-B",
            category_ref="CAT-AUDIO-SPEAKERS",
            title="Speaker",
            quantity=1,
            refundable_amount="1200",
        )
    )
    return OrderSnapshot(
        order_snapshot_ref="ORDER-001@12",
        order_ref="ORDER-001",
        snapshot_version=12,
        captured_at=TIME,
        currency="TWD",
        delivered_at="2026-08-25T09:00:00Z",
        line_items=items,
        refundable_amount_max="1900" if multi else "1200",
        already_refunded_amount="0",
    )


def case_load(*, multi: bool = False) -> CaseContextLoadResult:
    return CaseContextLoadResult(
        case_context=CaseContext(
            case_ref="CASE-001",
            order_ref="ORDER-001",
            market="TW",
            case_opened_at=TIME,
            snapshot_version=3,
        ),
        order_snapshot=order_snapshot(multi=multi),
    )


def policy_bundle(
    *, return_policy: ReturnPolicy = ReturnPolicy.MODEL_JUDGMENT
) -> PolicyBundle:
    return PolicyBundle(
        policy_bundle_version="bundle:1",
        retrieval_status="OK",
        retrieved_at=TIME,
        clauses=[
            PolicyClause(
                clause_id="POLICY-12:v3#4.2",
                policy_version="POLICY-12:v3",
                effective_from="2026-01-01T00:00:00Z",
                applicable_conditions=ApplicableConditions(
                    markets=["TW"],
                    reason_codes=["ITEM_DAMAGED"],
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
                text="Delivered damaged items may be refunded.",
            )
        ],
    )


def evidence_item(
    artifact_ref: str = "artifact://evidence/EV-002",
    *,
    evidence_id: str = "EV-002",
    subject: str = "LI-002",
) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=evidence_id,
        type="IMAGE",
        source="USER",
        subject=subject,
        artifact_ref=artifact_ref,
        extracted_summary="Packaging damage and item crack are both visible.",
        collected_at="2026-09-01T10:40:00Z",
    )


def findings(*, item_status: ClaimStatus = ClaimStatus.SUPPORTED) -> list[ClaimFinding]:
    return [
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
            explanation="Within the return window.",
        ),
        ClaimFinding(
            claim_id=ClaimId.ITEM_PHYSICALLY_DAMAGED,
            subject="LI-002",
            status=item_status,
            supporting_evidence_refs=["EV-002"]
            if item_status is ClaimStatus.SUPPORTED
            else [],
            explanation="Physical condition assessed.",
        ),
        ClaimFinding(
            claim_id=ClaimId.DAMAGE_PRESENT_ON_ARRIVAL,
            subject="LI-002",
            status=item_status,
            supporting_evidence_refs=["EV-002"]
            if item_status is ClaimStatus.SUPPORTED
            else [],
            explanation="Arrival condition assessed.",
        ),
    ]


def supported_assessment() -> ApprovalEvidenceAssessment:
    return ApprovalEvidenceAssessment(
        evidence_status=EvidenceStatus.SUFFICIENT_FOR_APPROVAL,
        claim_registry_version="claim-registry:1.0",
        claim_findings=findings(),
    )


def proposal_output(*, rationale: str = "All required claims are supported."):
    return ResolverDraftOutput(
        result_type="DRAFT",
        draft=FullRefundProposedDecisionDraft(
            action="FULL_REFUND",
            refund_scope=NonEmptyRefundScope(line_item_ids=["LI-002"]),
            reason_code="ITEM_DAMAGED",
            return_decision=ModelJudgmentReturnDecision(
                source="MODEL_JUDGMENT",
                requirement=WaivedReturnRequirement(
                    required=False,
                    reason_code="ITEM_UNSALVAGEABLE",
                ),
            ),
            policy_refs=["POLICY-12:v3#4.2"],
            evidence_refs=["EV-002"],
            rationale_summary=rationale,
        ),
    )


def approved_review() -> ApprovedReviewResult:
    return ApprovedReviewResult(
        verdict="APPROVE",
        reviewer_claim_findings=findings(),
        revision_reasons=[],
        reviewer_prompt_version="reviewer:1.0",
        reviewed_at=TIME,
    )


def make_runtime(
    *,
    model: QueuedModel,
    case_result=None,
    policy_result=None,
    verification_results=None,
    human_results=None,
    memory_results=(),
    evidence_items=None,
    reviewer_gate_config=None,
):
    case_provider = CaseProviderFake(case_result or case_load())
    policy_provider = PolicyProviderFake(policy_result or policy_bundle())
    verification_provider = VerificationProviderFake(
        deque(
            verification_results
            or [
                PassedVerificationResult(
                    status="PASS", issues=[], verification_version="verify:1"
                )
            ]
        )
    )
    human_provider = HumanReviewProviderFake(deque(human_results if human_results is not None else [None]))
    memory_provider = MemoryStoreFake(memory_results)
    evidence_provider = EvidenceProviderFake(evidence_items or {})
    providers = {
        "case": case_provider,
        "policy": policy_provider,
        "verification": verification_provider,
        "human": human_provider,
        "memory": memory_provider,
        "evidence": evidence_provider,
    }
    dependencies = AgentDependencies(
        **({"reviewer_gate_config": reviewer_gate_config} if reviewer_gate_config is not None else {}),
        model=model,
        case_context_provider=case_provider,
        policy_provider=policy_provider,
        verification_provider=verification_provider,
        human_review_provider=human_provider,
        operational_memory_store=memory_provider,
        evidence_provider=evidence_provider,
        clock=FrozenClock(datetime(2026, 9, 1, 10, 0, tzinfo=UTC)),
    )
    return (
        ReturnAgentRuntime(
            dependencies,
            InMemorySaver(serde=create_checkpoint_serializer()),
        ),
        providers,
    )


@pytest.fixture
def happy_runtime():
    model = QueuedModel()
    model.queue(
        ModelTask.INTAKE,
        {
            "completeness": "COMPLETE",
            "order_ref": "ORDER-001",
            "reason_code": "ITEM_DAMAGED",
            "reason_summary": "Speaker arrived damaged.",
            "requested_action": "REFUND",
            "claimed_line_item_ids": [],
            "missing_fields": [],
            "clarification_question": None,
        },
    )
    model.queue(ModelTask.ASSESS, supported_assessment())
    model.queue(ModelTask.PROPOSE_OR_REVISE, proposal_output())
    model.queue(ModelTask.REVIEW, approved_review())
    evidence = evidence_item()
    runtime, providers = make_runtime(
        model=model,
        evidence_items={evidence.artifact_ref: evidence},
    )
    return runtime, model, providers


def queue_human_review(model):
    from return_agent_contracts.models import RevisedReviewResult
    result = RevisedReviewResult(
        verdict="REVISE", reviewer_claim_findings=findings(),
        revision_reasons=[dict(code="DECISION_INCONSISTENT", subject="LI-002",
            message="The return explanation is unsupported.",
            required_change="Support the return requirement with cited facts.",
            policy_refs=["POLICY-12:v3#4.2"], evidence_refs=["EV-002"])],
        reviewer_prompt_version="reviewer:2.0", reviewed_at=TIME,
    )
    model.outputs[ModelTask.REVIEW].clear()
    model.queue(ModelTask.REVIEW, result, result, result, result)
    model.queue(ModelTask.PROPOSE_OR_REVISE,
                proposal_output(rationale="First correction based on the evidence."),
                proposal_output(rationale="Second correction based on the evidence."),
                proposal_output(rationale="Third correction based on the evidence."))


def four_verifications():
    return [dict(status="PASS", issues=[], verification_version="verify:1")
            for _ in range(4)]
