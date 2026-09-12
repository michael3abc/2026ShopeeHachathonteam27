from __future__ import annotations

import pytest
from return_agent_contracts.enums import ClaimId, ClaimStatus, OutcomeSource
from return_agent_contracts.models import (
    ApprovedHumanReviewResult,
    EditedHumanReviewResult,
    EvidenceRequest,
    HumanReviewReturnDecision,
    InsufficientEvidenceAssessment,
    MissingClaim,
    RejectedHumanReviewResult,
    RequiredReturnRequirement,
    UserTurn,
)
from return_agent_contracts.runtime import (
    AgentInterruptKind,
    AgentRunStatus,
    ClarificationResume,
    EvidenceResume,
    HumanReviewPollResume,
)
from return_agent_runtime.errors import ResumeMismatchError, ThreadAlreadyExistsError
from return_agent_runtime.model import ModelTask

from .conftest import (
    TIME,
    queue_human_review,
    four_verifications,
    approved_review,
    case_load,
    evidence_item,
    findings,
    make_runtime,
    proposal_output,
    supported_assessment,
    user_turn,
)
from .fakes import QueuedModel


def complete_intake(*, claimed=()):
    return {
        "completeness": "COMPLETE",
        "order_ref": "ORDER-001",
        "reason_code": "ITEM_DAMAGED",
        "reason_summary": "Speaker arrived damaged.",
        "requested_action": "REFUND",
        "claimed_line_item_ids": list(claimed),
        "missing_fields": [],
        "clarification_question": None,
    }


def incomplete_intake(*, question="請提供訂單編號"):
    return {
        "completeness": "INCOMPLETE",
        "order_ref": None,
        "reason_code": "ITEM_DAMAGED",
        "reason_summary": "Speaker arrived damaged.",
        "requested_action": "REFUND",
        "claimed_line_item_ids": [],
        "missing_fields": ["order_ref"],
        "clarification_question": question,
    }


def insufficient_assessment(request_id="EREQ-001"):
    unsupported = findings(item_status=ClaimStatus.UNSUPPORTED)
    return InsufficientEvidenceAssessment(
        evidence_status="INSUFFICIENT",
        claim_registry_version="claim-registry:1.0",
        claim_findings=unsupported,
        missing_evidence_request=EvidenceRequest(
            request_id=request_id,
            missing_claims=[
                MissingClaim(
                    claim_id=ClaimId.ITEM_PHYSICALLY_DAMAGED,
                    subject="LI-002",
                ),
                MissingClaim(
                    claim_id=ClaimId.DAMAGE_PRESENT_ON_ARRIVAL,
                    subject="LI-002",
                ),
            ],
            accepted_evidence_types=["IMAGE", "VIDEO"],
            user_message="請提供同時顯示外箱與商品損壞的照片。",
            policy_refs=["POLICY-12:v3#4.2"],
        ),
    )


def queue_resolution(model: QueuedModel, *, intake=None) -> None:
    model.queue(ModelTask.INTAKE, intake or complete_intake())
    model.queue(ModelTask.ASSESS, supported_assessment())
    model.queue(ModelTask.PROPOSE_OR_REVISE, proposal_output())
    model.queue(ModelTask.REVIEW, approved_review())


def test_clarification_resume_then_multi_item_binding_and_initial_evidence():
    model = QueuedModel()
    model.queue(
        ModelTask.INTAKE,
        incomplete_intake(),
        complete_intake(),
        complete_intake(claimed=["LI-002"]),
    )
    model.queue(ModelTask.ASSESS, supported_assessment())
    model.queue(ModelTask.PROPOSE_OR_REVISE, proposal_output())
    model.queue(ModelTask.REVIEW, approved_review())
    evidence = evidence_item()
    runtime, providers = make_runtime(
        model=model,
        case_result=case_load(multi=True),
        evidence_items={evidence.artifact_ref: evidence},
    )

    paused = runtime.start(
        thread_id="THREAD-CLARIFY",
        case_ref="CASE-001",
        initial_turn=user_turn(text="Speaker 到貨時破損"),
    )

    assert paused.status is AgentRunStatus.INTERRUPTED
    assert paused.interrupt_kind is AgentInterruptKind.CLARIFICATION
    assert paused.interrupt_payload.request.clarification_round == 1

    completed = runtime.resume(
        thread_id="THREAD-CLARIFY",
        payload=ClarificationResume(
            kind="CLARIFICATION",
            turn=UserTurn(
                turn_id="TURN-002",
                role="USER",
                text="訂單是 ORDER-001，要退 Speaker",
                attached_artifact_refs=[evidence.artifact_ref],
                received_at="2026-09-01T10:05:00Z",
            ),
        ),
    )

    assert completed.status is AgentRunStatus.COMPLETED
    assert providers["policy"].calls[0][3] == ("LI-002",)
    assert providers["evidence"].calls == [evidence.artifact_ref]


def test_evidence_interrupt_resolves_refs_and_resumes_assessment():
    model = QueuedModel()
    model.queue(ModelTask.INTAKE, complete_intake())
    model.queue(
        ModelTask.ASSESS,
        insufficient_assessment(),
        supported_assessment(),
    )
    model.queue(ModelTask.PROPOSE_OR_REVISE, proposal_output())
    model.queue(ModelTask.REVIEW, approved_review())
    evidence = evidence_item()
    runtime, providers = make_runtime(
        model=model,
        evidence_items={evidence.artifact_ref: evidence},
    )

    paused = runtime.start(
        thread_id="THREAD-EVIDENCE",
        case_ref="CASE-001",
        initial_turn=user_turn(artifacts=[]),
    )

    assert paused.interrupt_kind is AgentInterruptKind.EVIDENCE_REQUEST
    assert paused.interrupt_payload.request.request_id.startswith("EVIDENCE-REQUEST-")
    assert paused.interrupt_payload.request.request_id != "EREQ-001"
    state = runtime.graph.get_state(
        {"configurable": {"thread_id": "THREAD-EVIDENCE"}}
    ).values
    assert state["evidence_round"] == 1

    completed = runtime.resume(
        thread_id="THREAD-EVIDENCE",
        payload=EvidenceResume(
            kind="EVIDENCE_REQUEST",
            artifact_refs=[evidence.artifact_ref],
        ),
    )

    assert completed.status is AgentRunStatus.COMPLETED
    assert providers["evidence"].calls == [evidence.artifact_ref]
    assert completed.resolution_handoff.final_decision.amount == 1200


@pytest.mark.asyncio
async def test_observed_evidence_resume_reports_paired_tasks():
    model = QueuedModel()
    model.queue(ModelTask.INTAKE, complete_intake())
    model.queue(
        ModelTask.ASSESS,
        insufficient_assessment(),
        supported_assessment(),
    )
    model.queue(ModelTask.PROPOSE_OR_REVISE, proposal_output())
    model.queue(ModelTask.REVIEW, approved_review())
    evidence = evidence_item()
    runtime, _ = make_runtime(
        model=model,
        evidence_items={evidence.artifact_ref: evidence},
    )
    paused = runtime.start(
        thread_id="THREAD-OBSERVED-EVIDENCE",
        case_ref="CASE-001",
        initial_turn=user_turn(artifacts=[]),
    )
    assert paused.interrupt_kind is AgentInterruptKind.EVIDENCE_REQUEST
    observations = []

    completed = await runtime.aresume(
        thread_id="THREAD-OBSERVED-EVIDENCE",
        payload=EvidenceResume(
            kind="EVIDENCE_REQUEST",
            artifact_refs=[evidence.artifact_ref],
        ),
        observer=observations.append,
    )

    assert completed.status is AgentRunStatus.COMPLETED
    assert observations
    enters = {item.task_ref for item in observations if item.phase == "ENTER"}
    exits = {item.task_ref for item in observations if item.phase == "EXIT"}
    assert enters == exits


def test_clarification_budget_fails_closed_after_two_resumes():
    model = QueuedModel()
    model.queue(
        ModelTask.INTAKE,
        incomplete_intake(),
        incomplete_intake(),
        incomplete_intake(),
    )
    runtime, _ = make_runtime(model=model)

    result = runtime.start(
        thread_id="THREAD-CLARIFY-BUDGET",
        case_ref="CASE-001",
        initial_turn=user_turn(text="商品有問題"),
    )
    for index in (2, 3):
        assert result.interrupt_kind is AgentInterruptKind.CLARIFICATION
        result = runtime.resume(
            thread_id="THREAD-CLARIFY-BUDGET",
            payload=ClarificationResume(
                kind="CLARIFICATION",
                turn=UserTurn(
                    turn_id=f"TURN-00{index}",
                    role="USER",
                    text="我還是不知道",
                    attached_artifact_refs=[],
                    received_at=f"2026-09-01T10:0{index}:00Z",
                ),
            ),
        )

    assert result.status is AgentRunStatus.COMPLETED
    assert result.manual_escalation.escalation_reason == "CLARIFICATION_BUDGET_EXCEEDED"
    assert result.manual_escalation.accumulated_context.clarification_round == 2


def test_evidence_budget_fails_closed_after_two_evidence_rounds():
    model = QueuedModel()
    model.queue(ModelTask.INTAKE, complete_intake())
    model.queue(
        ModelTask.ASSESS,
        insufficient_assessment("EREQ-1"),
        insufficient_assessment("EREQ-2"),
        insufficient_assessment("EREQ-3"),
    )
    first = evidence_item("artifact://evidence/1", evidence_id="EV-1")
    second = evidence_item("artifact://evidence/2", evidence_id="EV-2")
    runtime, _ = make_runtime(
        model=model,
        evidence_items={first.artifact_ref: first, second.artifact_ref: second},
    )

    result = runtime.start(
        thread_id="THREAD-EVIDENCE-BUDGET",
        case_ref="CASE-001",
        initial_turn=user_turn(artifacts=[]),
    )
    for item in (first, second):
        assert result.interrupt_kind is AgentInterruptKind.EVIDENCE_REQUEST
        result = runtime.resume(
            thread_id="THREAD-EVIDENCE-BUDGET",
            payload=EvidenceResume(
                kind="EVIDENCE_REQUEST", artifact_refs=[item.artifact_ref]
            ),
        )

    assert result.status is AgentRunStatus.COMPLETED
    assert result.manual_escalation.escalation_reason == "EVIDENCE_BUDGET_EXCEEDED"
    assert result.manual_escalation.accumulated_context.evidence_round == 2


def test_human_review_submit_once_and_poll_until_result():
    model = QueuedModel()
    queue_resolution(model)
    queue_human_review(model)
    evidence = evidence_item()
    human_result = ApprovedHumanReviewResult(
        decision="APPROVE",
        review_note="Approved after manual review.",
        final_resolution_ref="RES-001",
        reviewed_at=TIME,
    )
    runtime, providers = make_runtime(
        model=model,
        verification_results=four_verifications(),
        human_results=[None, human_result],
        evidence_items={evidence.artifact_ref: evidence},
    )

    paused = runtime.start(
        thread_id="THREAD-HUMAN",
        case_ref="CASE-001",
        initial_turn=user_turn(artifacts=[evidence.artifact_ref]),
    )
    assert paused.interrupt_kind is AgentInterruptKind.HUMAN_REVIEW
    assert (
        paused.interrupt_payload.handoff.handoff_id
        == paused.interrupt_payload.handoff_id
    )
    assert paused.interrupt_payload.review_result.verdict == "REVISE"
    assert paused.interrupt_payload.routing_reason == "REVISION_BUDGET_EXCEEDED"
    assert len([call for call in model.calls if call.task is ModelTask.REVIEW]) == 4
    assert paused.interrupt_payload.policy_bundle.clauses
    snapshot = runtime.graph.get_state({"configurable": {"thread_id": "THREAD-HUMAN"}})
    assert "handoff" not in snapshot.interrupts[0].value
    assert len(providers["human"].submit_calls) == 1

    completed = runtime.resume(
        thread_id="THREAD-HUMAN",
        payload=HumanReviewPollResume(kind="HUMAN_REVIEW"),
    )

    assert completed.resolution_handoff.outcome_source is OutcomeSource.HUMAN_APPROVE
    assert len(providers["human"].submit_calls) == 1
    assert providers["human"].fetch_calls == ["HUMAN-REVIEW-001"] * 2


@pytest.mark.parametrize(
    ("human_result", "expected_source", "expected_action"),
    [
        (
            EditedHumanReviewResult(
                decision="EDIT",
                review_note="Return is required.",
                generalizable=True,
                corrected_decision={
                    "action": "FULL_REFUND",
                    "refund_scope": {"line_item_ids": ["LI-002"]},
                    "return_decision": HumanReviewReturnDecision(
                        source="HUMAN_REVIEW",
                        requirement=RequiredReturnRequirement(
                            required=True,
                            reason_code="RETURN_REQUIRED_FOR_INSPECTION",
                        ),
                    ),
                },
                correction_reason_code="RETURN_REQUIREMENT_INCORRECT",
                final_resolution_ref="RES-EDIT",
                reviewed_at=TIME,
            ),
            OutcomeSource.HUMAN_EDIT,
            "FULL_REFUND",
        ),
        (
            RejectedHumanReviewResult(
                decision="REJECT",
                review_note="Manual review rejected the proposal.",
                final_resolution_ref="RES-REJECT",
                reviewed_at=TIME,
            ),
            OutcomeSource.HUMAN_REJECT,
            "DECLINE",
        ),
    ],
)
def test_human_edit_and_reject_map_to_terminal_contract(
    human_result, expected_source, expected_action
):
    model = QueuedModel()
    queue_resolution(model)
    queue_human_review(model)
    evidence = evidence_item()
    runtime, _ = make_runtime(
        model=model,
        verification_results=four_verifications(),
        human_results=[None, human_result],
        evidence_items={evidence.artifact_ref: evidence},
    )
    paused = runtime.start(
        thread_id=f"THREAD-{expected_source.value}",
        case_ref="CASE-001",
        initial_turn=user_turn(artifacts=[evidence.artifact_ref]),
    )
    completed = runtime.resume(
        thread_id=f"THREAD-{expected_source.value}",
        payload=HumanReviewPollResume(kind="HUMAN_REVIEW"),
    )

    assert paused.interrupt_kind is AgentInterruptKind.HUMAN_REVIEW
    assert completed.resolution_handoff.outcome_source is expected_source
    assert completed.resolution_handoff.final_decision.action == expected_action
    if expected_action == "FULL_REFUND":
        assert completed.resolution_handoff.final_decision.amount == 1200
    state = runtime.graph.get_state(
        {"configurable": {"thread_id": f"THREAD-{expected_source.value}"}}
    ).values
    assert state["memory_distillation_input"] is not None
    assert state["memory_distillation_input"].human_review_result == human_result


def test_runtime_rejects_reused_thread_and_wrong_resume_kind():
    model = QueuedModel()
    model.queue(ModelTask.INTAKE, incomplete_intake())
    runtime, _ = make_runtime(model=model)
    turn = user_turn(text="商品有問題")
    paused = runtime.start(
        thread_id="THREAD-GUARDS", case_ref="CASE-001", initial_turn=turn
    )
    assert paused.interrupt_kind is AgentInterruptKind.CLARIFICATION

    with pytest.raises(ThreadAlreadyExistsError):
        runtime.start(thread_id="THREAD-GUARDS", case_ref="CASE-001", initial_turn=turn)
    with pytest.raises(ResumeMismatchError):
        runtime.resume(
            thread_id="THREAD-GUARDS",
            payload=EvidenceResume(
                kind="EVIDENCE_REQUEST", artifact_refs=["artifact://unused"]
            ),
        )
