from __future__ import annotations

from copy import deepcopy

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from pydantic import TypeAdapter, ValidationError
from return_agent_contracts.adapters import to_evidence_request_view
from return_agent_contracts.models import (
    EvidenceAssessment,
    HumanReviewResult,
    ProposedDecision,
    ResolutionHandoff,
    ReviewResult,
    VerificationResult,
)
from return_agent_contracts.runtime import NodeExecutionObservation
from return_agent_contracts.ui import AgentEvent, MemoryRetrievalPayload, ReviewDecision

from .fixtures import (
    TIME,
    approved_review,
    evidence_request,
    proposed_handoff,
    revised_review,
    supported_assessment,
)


def _pydantic_accepts(contract: object, payload: object) -> bool:
    try:
        TypeAdapter(contract).validate_python(payload)
    except ValidationError:
        return False
    return True


def _schema_accepts(contract: object, payload: object) -> bool:
    schema = TypeAdapter(contract).json_schema(mode="validation")
    return Draft202012Validator(schema, format_checker=FormatChecker()).is_valid(
        payload
    )


def _assert_parity(contract: object, payload: object, expected: bool) -> None:
    assert _pydantic_accepts(contract, payload) is expected
    assert _schema_accepts(contract, payload) is expected


def test_core_union_and_scalar_wire_schema_parity() -> None:
    proposed = proposed_handoff().proposed_decision.model_dump(mode="json")
    assessment = supported_assessment().model_dump(mode="json")
    review = {
        "verdict": "APPROVE",
        "reviewer_claim_findings": assessment["claim_findings"],
        "revision_reasons": [],
        "reviewer_prompt_version": "reviewer:1.0",
        "reviewed_at": TIME,
    }
    verification = {
        "status": "PASS",
        "issues": [],
        "verification_version": "verification:1.0",
    }
    human = {
        "decision": "EDIT",
        "review_note": "The evidence does not establish the claim.",
        "corrected_decision": {
            "action": "DECLINE",
            "refund_scope": {"line_item_ids": []},
        },
        "correction_reason_code": "CLAIM_NOT_ESTABLISHED",
        "final_resolution_ref": "RES-001",
        "reviewed_at": TIME,
    }
    resolution = {
        "case_ref": "CASE-001",
        "handoff_id": "HANDOFF-001",
        "outcome_source": "REVIEWER_APPROVE",
        "final_decision": {
            "action": "FULL_REFUND",
            "refund_scope": {"line_item_ids": ["LI-002"]},
            "amount": "1200",
            "currency": "TWD",
            "return_decision": proposed["return_decision"],
            "reason_code": "ITEM_DAMAGED",
        },
        "review_result": approved_review().model_dump(mode="json"),
        "execution_blocked": False,
        "emitted_at": TIME,
    }

    for contract, payload in (
        (ProposedDecision, proposed),
        (EvidenceAssessment, assessment),
        (ReviewResult, review),
        (VerificationResult, verification),
        (HumanReviewResult, human),
        (ResolutionHandoff, resolution),
    ):
        _assert_parity(contract, payload, True)

    invalid_proposed = deepcopy(proposed)
    invalid_proposed.pop("return_decision")
    _assert_parity(ProposedDecision, invalid_proposed, False)

    numeric_money = deepcopy(proposed)
    numeric_money["amount"] = 1200
    _assert_parity(ProposedDecision, numeric_money, False)

    exponent_money = deepcopy(proposed)
    exponent_money["amount"] = "1.2e3"
    _assert_parity(ProposedDecision, exponent_money, False)

    wrong_reason = deepcopy(proposed)
    wrong_reason["return_decision"]["requirement"] = {
        "required": True,
        "reason_code": "ITEM_UNSALVAGEABLE",
    }
    _assert_parity(ProposedDecision, wrong_reason, False)

    invalid_assessment = deepcopy(assessment)
    invalid_assessment["evidence_status"] = "INSUFFICIENT"
    _assert_parity(EvidenceAssessment, invalid_assessment, False)

    invalid_review = deepcopy(review)
    invalid_review["verdict"] = "REVISE"
    _assert_parity(ReviewResult, invalid_review, False)

    invalid_verification = deepcopy(verification)
    invalid_verification["status"] = "FAIL"
    _assert_parity(VerificationResult, invalid_verification, False)

    invalid_human = deepcopy(human)
    invalid_human.pop("corrected_decision")
    _assert_parity(HumanReviewResult, invalid_human, False)

    approve_without_note = {
        "decision": "APPROVE",
        "final_resolution_ref": "RES-002",
        "reviewed_at": TIME,
    }
    _assert_parity(HumanReviewResult, approve_without_note, False)

    non_utc_human = deepcopy(human)
    non_utc_human["reviewed_at"] = "2026-09-01T18:00:00+08:00"
    _assert_parity(HumanReviewResult, non_utc_human, False)

    invalid_resolution = deepcopy(resolution)
    invalid_resolution["outcome_source"] = "RISK_BLOCK"
    _assert_parity(ResolutionHandoff, invalid_resolution, False)

    invalid_auto_source = deepcopy(resolution)
    invalid_auto_source["final_decision"]["return_decision"]["source"] = "HUMAN_REVIEW"
    _assert_parity(ResolutionHandoff, invalid_auto_source, False)

    valid_human_edit = deepcopy(invalid_auto_source)
    valid_human_edit["outcome_source"] = "HUMAN_EDIT"
    valid_human_edit["review_result"] = revised_review().model_dump(mode="json")
    _assert_parity(ResolutionHandoff, valid_human_edit, True)

    human_edit_with_agent_source = deepcopy(resolution)
    human_edit_with_agent_source["outcome_source"] = "HUMAN_EDIT"
    _assert_parity(ResolutionHandoff, human_edit_with_agent_source, False)


def test_sse_payload_wire_schema_parity() -> None:
    token_event = {
        "type": "token",
        "case_ref": "CASE-001",
        "seq": 1,
        "ts": TIME,
        "node": "propose_decision",
        "payload": {"text": "Working"},
    }
    _assert_parity(AgentEvent, token_event, True)

    malformed = deepcopy(token_event)
    malformed["payload"] = {}
    _assert_parity(AgentEvent, malformed, False)

    wrong_payload = deepcopy(token_event)
    wrong_payload["payload"] = {
        "call_id": "CALL-1",
        "tool_name": "order",
        "arguments": {},
    }
    _assert_parity(AgentEvent, wrong_payload, False)

    interrupt_event = {
        "type": "interrupt",
        "case_ref": "CASE-001",
        "seq": 2,
        "ts": TIME,
        "node": "request_evidence",
        "payload": {
            "interrupt_kind": "EVIDENCE_REQUEST",
            "request": to_evidence_request_view(
                "CASE-001", evidence_request()
            ).model_dump(mode="json"),
        },
    }
    _assert_parity(AgentEvent, interrupt_event, True)
    mismatched_interrupt = deepcopy(interrupt_event)
    mismatched_interrupt["payload"]["interrupt_kind"] = "HUMAN_REVIEW"
    _assert_parity(AgentEvent, mismatched_interrupt, False)

    non_utc = deepcopy(token_event)
    non_utc["ts"] = "2026-09-01T18:00:00+08:00"
    _assert_parity(AgentEvent, non_utc, False)

    edit_without_correction = {
        "decision": "EDIT",
        "review_note": "Change required.",
    }
    _assert_parity(ReviewDecision, edit_without_correction, False)


def test_node_observation_python_and_json_schema_parity() -> None:
    entered = {
        "phase": "ENTER",
        "node": "parse_request",
        "task_ref": "TASK-001",
        "error_message": None,
    }
    _assert_parity(NodeExecutionObservation, entered, True)

    missing_error = {
        "phase": "ERROR",
        "node": "parse_request",
        "task_ref": "TASK-001",
        "error_message": None,
    }
    _assert_parity(NodeExecutionObservation, missing_error, False)


def test_memory_hit_rejects_candidate_in_python_and_json_schema() -> None:
    candidate_view = {
        "memory_id": "MEM-001",
        "status": "CANDIDATE",
        "trigger": "Two evidence requirements are missing.",
        "boundary": "market=TW",
        "action": "Request both evidence items together.",
        "scope": {
            "market": "TW",
            "reason_codes": [],
            "claim_ids": [],
            "categories": [],
        },
        "source_case_refs": ["CASE-001"],
        "created_at": TIME,
        "hit_count": None,
    }
    payload = {
        "status": "OK",
        "hits": [{"memory": candidate_view, "similarity": 0.8}],
        "query_summary": "matched memory",
    }
    _assert_parity(MemoryRetrievalPayload, payload, False)


@pytest.mark.parametrize("payload,valid", [
    ({"status": "OK", "query_summary": "current evidence", "hits": []}, True),
    ({"status": "OK", "hits": []}, False),
    ({"status": "OK", "query_summary": "current evidence", "error_code": "SUMMARY_UNAVAILABLE"}, False),
    ({"status": "UNAVAILABLE", "error_code": "SUMMARY_UNAVAILABLE", "hits": []}, True),
    ({"status": "UNAVAILABLE", "hits": []}, False),
])
def test_memory_result_state_schema_parity(payload, valid):
    _assert_parity(MemoryRetrievalPayload, payload, valid)


def test_memory_observation_phase_schema_parity():
    for phase, node, valid in [("EXIT", "retrieve_memory", True), ("ENTER", "retrieve_memory", False), ("EXIT", "reviewer", False)]:
        _assert_parity(NodeExecutionObservation, {
            "phase": phase, "node": node, "task_ref": "TASK-MEMORY", "memory_retrieval": {
                "status": "OK", "query_summary": "current evidence", "hits": [],
            },
        }, valid)
