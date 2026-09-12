from __future__ import annotations

import pytest
from pydantic import TypeAdapter, ValidationError
from return_agent_contracts.models import ClarificationRequest, UserTurn
from return_agent_contracts.runtime import (
    AgentInterruptPayload,
    AgentResumeRequest,
    AgentRunResult,
    AgentStartRequest,
    ClarificationInterruptPayload,
    ClarificationResume,
    InterruptedAgentRunResult,
    NodeExecutionObservation,
)

TIME = "2026-09-06T12:00:00Z"


def _turn() -> UserTurn:
    return UserTurn(
        turn_id="TURN-001",
        role="USER",
        text="耳機到貨時損壞",
        received_at=TIME,
    )


def test_start_and_resume_requests_are_strict_shared_contracts() -> None:
    start = AgentStartRequest(
        thread_id="THREAD-001",
        case_ref="CASE-001",
        order_ref="ORDER-001",
        initial_turn=_turn(),
    )
    resume = AgentResumeRequest(
        thread_id=start.thread_id,
        payload=ClarificationResume(kind="CLARIFICATION", turn=_turn()),
    )
    assert resume.payload.kind == "CLARIFICATION"

    with pytest.raises(ValidationError):
        AgentStartRequest.model_validate(
            {**start.model_dump(mode="json"), "unexpected": True}
        )


def test_interrupt_and_run_result_are_discriminated_and_typed() -> None:
    interrupt = ClarificationInterruptPayload(
        kind="CLARIFICATION",
        case_ref="CASE-001",
        request=ClarificationRequest(
            request_id="CLARIFICATION-001",
            missing_fields=["claimed_line_item_ids"],
            clarification_question="是哪一個商品？",
            clarification_round=1,
        ),
    )
    parsed_interrupt = TypeAdapter(AgentInterruptPayload).validate_python(
        interrupt.model_dump(mode="json")
    )
    result = InterruptedAgentRunResult(
        result_type="INTERRUPTED",
        status="INTERRUPTED",
        interrupt_payload=parsed_interrupt,
    )
    parsed_result = TypeAdapter(AgentRunResult).validate_python(
        result.model_dump(mode="json")
    )
    assert parsed_result.interrupt_payload.request.clarification_round == 1

    invalid = result.model_dump(mode="json")
    invalid["interrupt_payload"]["request"] = {}
    with pytest.raises(ValidationError):
        TypeAdapter(AgentRunResult).validate_python(invalid)


def test_node_observation_requires_error_only_for_error_phase() -> None:
    entered = NodeExecutionObservation(
        phase="ENTER", node="assess_case", task_ref="TASK-001"
    )
    assert entered.error_message is None

    failed = NodeExecutionObservation(
        phase="ERROR",
        node="assess_case",
        task_ref="TASK-001",
        error_message="RuntimeError: failed",
    )
    assert failed.error_message == "RuntimeError: failed"

    with pytest.raises(ValidationError):
        NodeExecutionObservation(phase="ERROR", node="assess_case", task_ref="TASK-001")
    with pytest.raises(ValidationError):
        NodeExecutionObservation(
            phase="EXIT",
            node="assess_case",
            task_ref="TASK-001",
            error_message="not allowed",
        )


def test_evidence_reply_requires_matching_artifact_provenance():
    from return_agent_contracts.runtime import EvidenceResume
    turn = {"turn_id": "TURN-REPLY", "role": "USER", "text": "補件",
                "attached_artifact_refs": ["artifact://one"], "received_at": "2026-09-12T00:00:00Z"}
    assert EvidenceResume(kind="EVIDENCE_REQUEST", artifact_refs=["artifact://one"], turn=turn).turn.turn_id == "TURN-REPLY"
    assert EvidenceResume(kind="EVIDENCE_REQUEST", artifact_refs=["artifact://one"]).turn is None
    with pytest.raises(ValidationError, match="submitted artifacts"):
        EvidenceResume(kind="EVIDENCE_REQUEST", artifact_refs=["artifact://two"], turn=turn)
