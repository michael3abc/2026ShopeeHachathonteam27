from __future__ import annotations

import pytest
from return_agent_contracts.enums import (
    ClaimId,
    ClaimStatus,
    OutcomeSource,
    ReturnDecisionSource,
    ReturnPolicy,
)
from return_agent_contracts.models import (
    ApplicableConditions,
    ApprovedReviewResult,
    DeclineEvidenceAssessment,
    DeclineProposedDecisionDraft,
    EmptyRefundScope,
    EvidenceRequest,
    InsufficientEvidenceAssessment,
    MissingClaim,
    PolicyBundle,
    PolicyClause,
    PolicyReturnDecisionDraft,
    ResolverDraftOutput,
)
from return_agent_contracts.runtime import EvidenceResume
from return_agent_runtime.model import ModelTask

from .conftest import (
    TIME,
    evidence_item,
    findings,
    make_runtime,
    policy_bundle,
    supported_assessment,
    user_turn,
)
from .fakes import QueuedModel
from .test_interrupt_resume import complete_intake, insufficient_assessment


def _queue_static_policy_resolution(
    model: QueuedModel,
    *,
    return_policy: ReturnPolicy,
    reason_code: str,
) -> None:
    model.queue(ModelTask.INTAKE, complete_intake())
    model.queue(ModelTask.ASSESS, supported_assessment())
    model.queue(
        ModelTask.PROPOSE_OR_REVISE,
        ResolverDraftOutput(
            result_type="DRAFT",
            draft={
                "action": "FULL_REFUND",
                "refund_scope": {"line_item_ids": ["LI-002"]},
                "reason_code": "ITEM_DAMAGED",
                "return_decision": PolicyReturnDecisionDraft(
                    source="POLICY", reason_code=reason_code
                ),
                "policy_refs": ["POLICY-12:v3#4.2"],
                "evidence_refs": ["EV-002"],
                "rationale_summary": "The applicable policy determines the return requirement.",
            },
        ),
    )
    model.queue(
        ModelTask.REVIEW,
        ApprovedReviewResult(
            verdict="APPROVE",
            reviewer_claim_findings=findings(),
            revision_reasons=[],
            reviewer_prompt_version="reviewer:1.0",
            reviewed_at=TIME,
        ),
    )


@pytest.mark.parametrize(
    ("return_policy", "reason_code", "required"),
    [
        (ReturnPolicy.REQUIRED, "RETURN_REQUIRED_FOR_INSPECTION", True),
        (ReturnPolicy.NOT_REQUIRED, "ITEM_UNSALVAGEABLE", False),
    ],
)
def test_graph_completes_static_policy_return_requirement(
    return_policy, reason_code, required
):
    model = QueuedModel()
    _queue_static_policy_resolution(
        model, return_policy=return_policy, reason_code=reason_code
    )
    evidence = evidence_item()
    runtime, _ = make_runtime(
        model=model,
        policy_result=policy_bundle(return_policy=return_policy),
        evidence_items={evidence.artifact_ref: evidence},
    )

    result = runtime.start(
        thread_id=f"THREAD-RETURN-{return_policy.value}",
        case_ref="CASE-001",
        initial_turn=user_turn(artifacts=[evidence.artifact_ref]),
    )

    decision = result.resolution_handoff.final_decision
    assert decision.return_decision.source is ReturnDecisionSource.POLICY
    assert decision.return_decision.requirement.required is required


def _decline_assessment():
    contradicted = findings(item_status=ClaimStatus.CONTRADICTED)
    return DeclineEvidenceAssessment(
        evidence_status="SUFFICIENT_FOR_DECLINE",
        claim_registry_version="claim-registry:1.0",
        claim_findings=contradicted,
    )


def _decline_output():
    return ResolverDraftOutput(
        result_type="DRAFT",
        draft=DeclineProposedDecisionDraft(
            action="DECLINE",
            refund_scope=EmptyRefundScope(line_item_ids=[]),
            reason_code="ITEM_DAMAGED",
            policy_refs=["POLICY-12:v3#4.2"],
            evidence_refs=["EV-002"],
            rationale_summary="The required item claims are contradicted.",
        ),
    )


def _queue_decline(model: QueuedModel) -> None:
    model.queue(ModelTask.INTAKE, complete_intake())
    model.queue(ModelTask.ASSESS, _decline_assessment())
    model.queue(ModelTask.PROPOSE_OR_REVISE, _decline_output())
    model.queue(
        ModelTask.REVIEW,
        ApprovedReviewResult(
            verdict="APPROVE",
            reviewer_claim_findings=findings(item_status=ClaimStatus.CONTRADICTED),
            revision_reasons=[],
            reviewer_prompt_version="reviewer:1.0",
            reviewed_at=TIME,
        ),
    )


@pytest.mark.parametrize("return_policy", list(ReturnPolicy))
def test_reviewer_approved_decline_is_valid(return_policy):
    evidence = evidence_item()
    auto_model = QueuedModel()
    _queue_decline(auto_model)
    auto_runtime, _ = make_runtime(
        model=auto_model,
        policy_result=policy_bundle(return_policy=return_policy),
        evidence_items={evidence.artifact_ref: evidence},
    )
    auto = auto_runtime.start(
        thread_id="THREAD-DECLINE-AUTO",
        case_ref="CASE-001",
        initial_turn=user_turn(artifacts=[evidence.artifact_ref]),
    )
    assert auto.resolution_handoff.outcome_source is OutcomeSource.REVIEWER_APPROVE
    assert auto.resolution_handoff.final_decision.action == "DECLINE"
    assert auto.resolution_handoff.final_decision.amount == 0
    assert auto.resolution_handoff.final_decision.refund_scope.line_item_ids == []
    assert "return_decision" not in auto.resolution_handoff.final_decision.model_dump()
    state = auto_runtime.graph.get_state(
        {"configurable": {"thread_id": "THREAD-DECLINE-AUTO"}}
    ).values
    trace = state["memory_distillation_input"].learning_trace
    assert trace.status == "COMPLETE"
    decisions = [event.decision for event in trace.events if event.decision]
    assert len(decisions) == 2
    assert all(decision.action == "DECLINE" and decision.return_decision is None
               for decision in decisions)
    review_call = next(call for call in auto_model.calls if call.task is ModelTask.REVIEW)
    assert "Do not request return_decision" in review_call.system_prompt
    assert "operational_memory" not in review_call.payload



def test_reviewer_invalid_approve_fails_closed():
    model = QueuedModel()
    model.queue(ModelTask.INTAKE, complete_intake())
    model.queue(ModelTask.ASSESS, supported_assessment())
    from .conftest import proposal_output

    model.queue(ModelTask.PROPOSE_OR_REVISE, proposal_output())
    reviewer_findings = findings()
    reviewer_findings[-1] = reviewer_findings[-1].model_copy(
        update={"status": ClaimStatus.UNSUPPORTED, "supporting_evidence_refs": []}
    )
    model.queue(
        ModelTask.REVIEW,
        ApprovedReviewResult(
            verdict="APPROVE",
            reviewer_claim_findings=reviewer_findings,
            revision_reasons=[],
            reviewer_prompt_version="reviewer:1.0",
            reviewed_at=TIME,
        ),
    )
    evidence = evidence_item()
    runtime, providers = make_runtime(
        model=model,
        evidence_items={evidence.artifact_ref: evidence},
    )

    result = runtime.start(
        thread_id="THREAD-BAD-APPROVE",
        case_ref="CASE-001",
        initial_turn=user_turn(artifacts=[evidence.artifact_ref]),
    )

    assert result.manual_escalation.escalation_reason == "CONTRACT_VIOLATION"


def test_system_fact_only_gap_does_not_ask_user_for_evidence():
    system_policy = PolicyBundle(
        policy_bundle_version="bundle:system",
        retrieval_status="OK",
        retrieved_at=TIME,
        clauses=[
            PolicyClause(
                clause_id="POLICY-SYSTEM#1",
                policy_version="POLICY-SYSTEM:v1",
                effective_from="2026-01-01T00:00:00Z",
                applicable_conditions=ApplicableConditions(
                    markets=["TW"], reason_codes=["ITEM_DAMAGED"], categories=[]
                ),
                required_claim_ids=[ClaimId.ORDER_WITHIN_RETURN_WINDOW],
                allowed_actions=["FULL_REFUND", "DECLINE"],
                return_policy="MODEL_JUDGMENT",
                text="Order must be inside the return window.",
            )
        ],
    )
    assessment = InsufficientEvidenceAssessment(
        evidence_status="INSUFFICIENT",
        claim_registry_version="claim-registry:1.0",
        claim_findings=[
            {
                "claim_id": "ORDER_WITHIN_RETURN_WINDOW",
                "subject": "ORDER",
                "status": "UNSUPPORTED",
                "supporting_evidence_refs": [],
                "explanation": "No system fact establishes the window.",
            }
        ],
        missing_evidence_request=EvidenceRequest(
            request_id="EREQ-SYSTEM",
            missing_claims=[
                MissingClaim(
                    claim_id=ClaimId.ORDER_WITHIN_RETURN_WINDOW,
                    subject="ORDER",
                )
            ],
            accepted_evidence_types=["TEXT"],
            user_message="Please prove the system return window.",
            policy_refs=["POLICY-SYSTEM#1"],
        ),
    )
    model = QueuedModel()
    model.queue(ModelTask.INTAKE, complete_intake())
    model.queue(ModelTask.ASSESS, assessment)
    runtime, _ = make_runtime(model=model, policy_result=system_policy)

    result = runtime.start(
        thread_id="THREAD-SYSTEM-GAP",
        case_ref="CASE-001",
        initial_turn=user_turn(artifacts=[]),
    )

    assert result.manual_escalation.escalation_reason == "CONTRACT_VIOLATION"


def test_evidence_resume_subject_mismatch_fails_closed():
    model = QueuedModel()
    model.queue(ModelTask.INTAKE, complete_intake())
    model.queue(ModelTask.ASSESS, insufficient_assessment())
    wrong = evidence_item(subject="ORDER")
    runtime, _ = make_runtime(
        model=model,
        evidence_items={wrong.artifact_ref: wrong},
    )
    paused = runtime.start(
        thread_id="THREAD-EVIDENCE-MISMATCH",
        case_ref="CASE-001",
        initial_turn=user_turn(artifacts=[]),
    )
    completed = runtime.resume(
        thread_id="THREAD-EVIDENCE-MISMATCH",
        payload=EvidenceResume(
            kind="EVIDENCE_REQUEST", artifact_refs=[wrong.artifact_ref]
        ),
    )
    assert paused.interrupt_kind == "EVIDENCE_REQUEST"
    assert completed.manual_escalation.escalation_reason == "CONTRACT_VIOLATION"


def test_llm_cannot_emit_graph_owned_amount_or_counter():
    model = QueuedModel()
    model.queue(ModelTask.INTAKE, complete_intake())
    model.queue(ModelTask.ASSESS, supported_assessment())
    invalid_output = {
        "result_type": "DRAFT",
        "draft": {
            "action": "FULL_REFUND",
            "refund_scope": {"line_item_ids": ["LI-002"]},
            "amount": "1200",
            "revision_round": 4,
            "reason_code": "ITEM_DAMAGED",
            "return_decision": {
                "source": "MODEL_JUDGMENT",
                "requirement": {
                    "required": False,
                    "reason_code": "ITEM_UNSALVAGEABLE",
                },
            },
            "policy_refs": ["POLICY-12:v3#4.2"],
            "evidence_refs": ["EV-002"],
            "rationale_summary": "Claims supported.",
        },
    }
    model.queue(ModelTask.PROPOSE_OR_REVISE, invalid_output)
    evidence = evidence_item()
    runtime, providers = make_runtime(
        model=model,
        evidence_items={evidence.artifact_ref: evidence},
    )
    result = runtime.start(
        thread_id="THREAD-GRAPH-FIELDS",
        case_ref="CASE-001",
        initial_turn=user_turn(artifacts=[evidence.artifact_ref]),
    )
    assert result.manual_escalation.escalation_reason == "CONTRACT_VIOLATION"
    assert providers["verification"].calls == []
