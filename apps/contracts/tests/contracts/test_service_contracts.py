from __future__ import annotations

import pytest
from jsonschema import Draft202012Validator
from pydantic import TypeAdapter, ValidationError
from return_agent_contracts.models import (
    MemoryCandidateOutput,
    MemoryDistillationInput,
    MemorySkipOutput,
    UserTurn,
)
from return_agent_contracts.service import (
    AGENT_COMMAND_STREAM,
    AGENT_EVENT_STREAM,
    MEMORY_JOB_STREAM,
    REDIS_BODY_FIELD,
    AgentCommand,
    AgentResumeCommand,
    AgentRunFailedEvent,
    AgentServiceEvent,
    AgentStartCommand,
    MemoryDistillationCompletedEvent,
    MemoryDistillationJob,
)

from .fixtures import approved_review, memory_candidate, memory_reflection

TIME = "2026-09-06T12:00:00Z"


def _memory_input() -> MemoryDistillationInput:
    proposal = {
        "handoff_version": "1.0",
        "handoff_id": "HANDOFF-001",
        "case_ref": "CASE-001",
        "order_snapshot_ref": "ORDER-001@1",
        "policy_bundle_version": "bundle:1",
        "claim_registry_version": "claim-registry:1.0",
        "proposed_decision": {
            "action": "DECLINE",
            "refund_scope": {"line_item_ids": []},
            "amount": "0",
            "currency": "TWD",
            "reason_code": "ITEM_DAMAGED",
            "policy_refs": ["POLICY-1#1"],
            "evidence_refs": [],
        },
        "evidence_bundle": [],
        "policy_refs": ["POLICY-1#1"],
        "rationale_summary": "The required claim was contradicted.",
        "revision_round": 1,
        "agent_prompt_version": "resolver:1.0",
    }
    finding = {
        "claim_id": "DELIVERY_CONFIRMED",
        "subject": "ORDER",
        "status": "CONTRADICTED",
        "supporting_evidence_refs": [],
        "explanation": "Delivery could not be confirmed.",
    }
    return MemoryDistillationInput.model_validate(
        {
            "case_context": {
                "case_ref": "CASE-001",
                "order_ref": "ORDER-001",
                "market": "TW",
                "case_opened_at": TIME,
                "snapshot_version": 1,
            },
            "policy_bundle": {
                "policy_bundle_version": "bundle:1",
                "retrieval_status": "OK",
                "retrieved_at": TIME,
                "clauses": [
                    {
                        "clause_id": "POLICY-1#1",
                        "policy_version": "POLICY-1",
                        "effective_from": "2026-01-01T00:00:00Z",
                        "applicable_conditions": {
                            "markets": ["TW"],
                            "reason_codes": ["ITEM_DAMAGED"],
                            "categories": [],
                        },
                        "required_claim_ids": ["DELIVERY_CONFIRMED"],
                        "allowed_actions": ["DECLINE"],
                        "return_policy": "NOT_REQUIRED",
                        "text": "Delivery must be confirmed.",
                    }
                ],
            },
            "evidence_assessment": {
                "evidence_status": "SUFFICIENT_FOR_DECLINE",
                "claim_registry_version": "claim-registry:1.0",
                "claim_findings": [finding],
            },
            "proposal_history": [proposal],
            "revision_events": [
                {
                    "event_id": "REVISION-001",
                    "case_ref": "CASE-001",
                    "handoff_before_ref": "HANDOFF-001",
                    "review_result": {
                        "verdict": "REVISE",
                        "reviewer_claim_findings": [finding],
                        "revision_reasons": [
                            {
                                "code": "DECISION_INCONSISTENT",
                                "message": "The original decision was unsupported.",
                                "policy_refs": ["POLICY-1#1"],
                                "evidence_refs": [],
                                "subject": "ORDER",
                                "required_change": "Decline the unsupported request.",
                            }
                        ],
                        "reviewer_prompt_version": "reviewer:1.0",
                        "reviewed_at": TIME,
                    },
                    "revision_round": 1,
                    "created_at": TIME,
                }
            ],
            "final_resolution": {
                "case_ref": "CASE-001",
                "handoff_id": "HANDOFF-001",
                "emitted_at": TIME,
                "outcome_source": "REVIEWER_APPROVE",
                "final_decision": {
                    "action": "DECLINE",
                    "refund_scope": {"line_item_ids": []},
                    "amount": "0",
                    "currency": "TWD",
                    "reason_code": "ITEM_DAMAGED",
                },
                "review_result": approved_review().model_dump(mode="json"),
                "execution_blocked": False,
            },
            "claimed_categories": [],
        }
    )


def _start_payload() -> dict[str, object]:
    return {
        "schema_version": "v1",
        "command_type": "START",
        "command_id": "COMMAND-001",
        "case_ref": "CASE-001",
        "thread_id": "THREAD-001",
        "issued_at": TIME,
        "payload": {
            "order_ref": "ORDER-001",
            "initial_turn": UserTurn(
                turn_id="TURN-001",
                role="USER",
                text="商品到貨時損壞",
                received_at=TIME,
            ).model_dump(mode="json")
        },
    }


def test_agent_command_is_strict_discriminated_union() -> None:
    command = TypeAdapter(AgentCommand).validate_python(_start_payload())
    assert isinstance(command, AgentStartCommand)
    assert command.payload.initial_turn.text == "商品到貨時損壞"
    assert AGENT_COMMAND_STREAM == "return-agent.commands.v1"
    assert AGENT_EVENT_STREAM == "return-agent.events.v1"
    assert REDIS_BODY_FIELD == "body"

    invalid = _start_payload()
    invalid["unexpected"] = True
    with pytest.raises(ValidationError):
        TypeAdapter(AgentCommand).validate_python(invalid)


def test_start_command_requires_user_role_in_python_and_json_schema() -> None:
    payload = _start_payload()
    payload["payload"]["initial_turn"]["role"] = "AGENT"
    adapter = TypeAdapter(AgentCommand)
    validator = Draft202012Validator(adapter.json_schema(mode="validation"))

    with pytest.raises(ValidationError):
        adapter.validate_python(payload)
    assert list(validator.iter_errors(payload))


@pytest.mark.parametrize(
    "resume",
    [
        {"kind": "CLARIFICATION", "turn": _start_payload()["payload"]["initial_turn"]},
        {"kind": "EVIDENCE_REQUEST", "artifact_refs": ["artifact://EV-002"]},
        {"kind": "HUMAN_REVIEW"},
    ],
)
def test_resume_command_supports_every_interrupt_kind(
    resume: dict[str, object],
) -> None:
    command = AgentResumeCommand(
        command_type="RESUME",
        command_id="COMMAND-RESUME",
        case_ref="CASE-001",
        thread_id="THREAD-001",
        issued_at=TIME,
        payload={"resume": resume},
    )
    parsed = TypeAdapter(AgentCommand).validate_python(command.model_dump(mode="json"))
    assert isinstance(parsed, AgentResumeCommand)


def test_service_event_is_strict_discriminated_union() -> None:
    event = AgentRunFailedEvent(
        schema_version="v1",
        event_type="RUN_FAILED",
        event_id="EVENT-001",
        command_id="COMMAND-001",
        case_ref="CASE-001",
        thread_id="THREAD-001",
        event_index=1,
        occurred_at=TIME,
        payload={
            "code": "AGENT_RUN_FAILED",
            "message": "Provider contract failed",
            "retryable": False,
            "failed_node": "retrieve_policy",
        },
    )
    parsed = TypeAdapter(AgentServiceEvent).validate_python(
        event.model_dump(mode="json")
    )
    assert parsed.payload.retryable is False

    invalid = event.model_dump(mode="json")
    invalid["event_type"] = "NODE_OBSERVED"
    validator = Draft202012Validator(
        TypeAdapter(AgentServiceEvent).json_schema(mode="validation")
    )
    with pytest.raises(ValidationError):
        TypeAdapter(AgentServiceEvent).validate_python(invalid)
    assert list(validator.iter_errors(invalid))


def test_memory_job_is_typed_and_case_bound() -> None:
    job = MemoryDistillationJob(
        job_id="MEMORY-JOB-001",
        source_command_id="COMMAND-001",
        case_ref="CASE-001",
        thread_id="THREAD-001",
        issued_at=TIME,
        payload={"input": _memory_input()},
    )
    assert MEMORY_JOB_STREAM == "return-agent.memory-jobs.v2"
    parsed = MemoryDistillationJob.model_validate(job.model_dump(mode="json"))
    assert parsed.payload.input.final_resolution.handoff_id == "HANDOFF-001"

    invalid = job.model_dump(mode="json")
    invalid["case_ref"] = "CASE-OTHER"
    with pytest.raises(ValidationError):
        MemoryDistillationJob.model_validate(invalid)


def test_memory_completion_submission_invariant_is_schema_visible() -> None:
    event = MemoryDistillationCompletedEvent(
        event_type="COMPLETED",
        event_id="MEMORY-EVENT-001",
        job_id="MEMORY-JOB-001",
        source_command_id="COMMAND-001",
        case_ref="CASE-001",
        thread_id="THREAD-001",
        occurred_at=TIME,
        payload={
            "result": MemoryCandidateOutput(
                result_type="CREATE_CANDIDATE", candidate=memory_candidate(), **memory_reflection()
            ),
            "submission_ref": "SUBMISSION-001",
            "distiller_prompt_version": "memory-distiller:1.0",
        },
    )
    adapter = TypeAdapter(MemoryDistillationCompletedEvent)
    validator = Draft202012Validator(adapter.json_schema(mode="validation"))
    payload = event.model_dump(mode="json")
    assert not list(validator.iter_errors(payload))

    invalid = event.model_dump(mode="json")
    invalid["payload"]["result"] = MemorySkipOutput(
        result_type="SKIP",
        reason_code="NO_CONFIRMED_GENERALIZABLE_CORRECTION",
    ).model_dump(mode="json")
    with pytest.raises(ValidationError):
        adapter.validate_python(invalid)
    assert list(validator.iter_errors(invalid))


@pytest.mark.parametrize("field", ["issued_at"])
def test_command_python_and_json_schema_both_reject_non_utc(field: str) -> None:
    payload = _start_payload()
    payload[field] = "2026-09-06T20:00:00+08:00"
    adapter = TypeAdapter(AgentCommand)
    validator = Draft202012Validator(adapter.json_schema(mode="validation"))

    with pytest.raises(ValidationError):
        adapter.validate_python(payload)
    assert list(validator.iter_errors(payload))
