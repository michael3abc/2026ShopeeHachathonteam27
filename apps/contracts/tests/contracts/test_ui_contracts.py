from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import TypeAdapter, ValidationError
from return_agent_contracts.adapters import (
    UIAdapterError,
    to_clarification_interrupt_payload,
    to_evidence_request_view,
    to_human_review_payload,
    to_human_review_result,
    to_memory_record_view,
    to_memory_retrieval_payload,
)
from return_agent_contracts.models import (
    ApprovedMemory,
    ClarificationRequest,
    CorrectedDeclineDecision,
    DeclineProposedDecision,
)
from return_agent_contracts.ui import (
    AgentEvent,
    ApproveReviewDecision,
    CaseDetail,
    EditReviewDecision,
    HumanReviewPayload,
    MemoryRetrievalPayload,
    NodeEnterEvent,
    RejectReviewDecision,
    ReviewDecision,
    TokenEvent,
)

from .fixtures import (
    TIME,
    approved_review,
    evidence_request,
    memory_candidate,
    policy_bundle,
    proposed_handoff,
    revised_review,
)


def _human_review():
    return revised_review()


def test_sse_event_union_uses_real_nodes_sequence_utc_and_typed_payload() -> None:
    event = NodeEnterEvent(
        type="node_enter",
        case_ref="CASE-001",
        seq=1,
        ts=TIME,
        node="assess_case",
    )
    assert (
        TypeAdapter(AgentEvent).validate_python(event.model_dump(mode="json")).node
        == "assess_case"
    )

    invalid_node = event.model_dump(mode="json")
    invalid_node["node"] = "DECIDE"
    with pytest.raises(ValidationError):
        TypeAdapter(AgentEvent).validate_python(invalid_node)

    missing_seq = event.model_dump(mode="json")
    missing_seq.pop("seq")
    with pytest.raises(ValidationError):
        TypeAdapter(AgentEvent).validate_python(missing_seq)

    non_utc = event.model_dump(mode="json")
    non_utc["ts"] = "2026-09-01T18:00:00+08:00"
    with pytest.raises(ValidationError):
        TypeAdapter(AgentEvent).validate_python(non_utc)

    malformed_token = TokenEvent(
        type="token",
        case_ref="CASE-001",
        seq=2,
        ts=TIME,
        node="propose_decision",
        payload={"text": "Working"},
    ).model_dump(mode="json")
    malformed_token["payload"] = {}
    with pytest.raises(ValidationError):
        TypeAdapter(AgentEvent).validate_python(malformed_token)


def test_human_review_projection_only_accepts_core_decisions_and_human_review() -> None:
    payload = to_human_review_payload(
        proposed_handoff(), _human_review(), policy_bundle(), memory_ids=["MEM-001"]
    )
    assert payload.action == "FULL_REFUND"
    assert payload.amount == Decimal(1200)
    assert payload.memories_used == ["MEM-001"]
    assert payload.policy_hits[0].clause_id == "POLICY-12:v3#4.2"
    assert (
        TypeAdapter(HumanReviewPayload)
        .validate_python(payload.model_dump(mode="json"))
        .action
        == "FULL_REFUND"
    )

    decline_handoff = proposed_handoff().model_copy(
        update={
            "proposed_decision": DeclineProposedDecision(
                action="DECLINE",
                refund_scope={"line_item_ids": []},
                amount="0",
                currency="TWD",
                reason_code="ITEM_DAMAGED",
                policy_refs=["POLICY-12:v3#4.2"],
                evidence_refs=["EV-002"],
            )
        }
    )
    decline_payload = to_human_review_payload(
        decline_handoff, _human_review(), policy_bundle()
    )
    assert decline_payload.action == "DECLINE"
    assert decline_payload.amount == Decimal(0)

    invalid = payload.model_dump(mode="json")
    invalid["action"] = "PARTIAL_REFUND"
    with pytest.raises(ValidationError):
        TypeAdapter(HumanReviewPayload).validate_python(invalid)
    with pytest.raises(ValidationError):
        TypeAdapter(HumanReviewPayload).validate_python(
            {**payload.model_dump(mode="json"), "confidence": 0.9}
        )
    with pytest.raises(UIAdapterError):
        to_human_review_payload(
            proposed_handoff(),
            approved_review(),
            policy_bundle(),
        )


def test_human_review_resume_preserves_notes_for_all_decisions() -> None:
    approve = ApproveReviewDecision(
        decision="APPROVE", review_note="Checked all evidence and approved."
    )
    approve_result = to_human_review_result(
        approve, "RESOLUTION-001", "2026-09-01T11:00:00Z"
    )
    assert approve_result.review_note == approve.review_note

    edit = EditReviewDecision(
        decision="EDIT",
        review_note="The claim was not established.",
        corrected_decision=CorrectedDeclineDecision(
            action="DECLINE", refund_scope={"line_item_ids": []}
        ),
        correction_reason_code="CLAIM_NOT_ESTABLISHED",
        generalizable=True,
    )
    edit_result = to_human_review_result(
        edit, "RESOLUTION-002", "2026-09-01T11:00:00+00:00"
    )
    assert edit_result.review_note == edit.review_note
    assert edit_result.generalizable is True
    assert edit_result.corrected_decision.action == "DECLINE"

    reject = RejectReviewDecision(
        decision="REJECT", review_note="Rejected after manual inspection."
    )
    reject_result = to_human_review_result(
        reject, "RESOLUTION-003", "2026-09-01T11:00:00Z"
    )
    assert reject_result.review_note == reject.review_note

    invalid = approve.model_dump(mode="json")
    invalid["corrected_decision"] = edit.corrected_decision.model_dump(mode="json")
    with pytest.raises(ValidationError):
        TypeAdapter(ReviewDecision).validate_python(invalid)


def test_evidence_and_human_review_interrupt_inputs_are_separate() -> None:
    evidence_view = to_evidence_request_view("CASE-001", evidence_request())
    assert evidence_view.request_id == "EREQ-001"
    assert evidence_view.missing_claims[0].subject == "LI-002"


def test_clarification_interrupt_and_case_status_are_public_ui_contracts() -> None:
    payload = to_clarification_interrupt_payload(
        "CASE-001",
        ClarificationRequest(
            request_id="CLARIFICATION-001",
            missing_fields=["claimed_line_item_ids"],
            clarification_question="是哪一個商品？",
            clarification_round=1,
        ),
    )
    detail = CaseDetail(
        case_ref="CASE-001",
        order_ref="ORDER-001",
        user_ref="USER-001",
        status="AWAITING_CLARIFICATION",
        clarification_request=payload.request,
        created_at=TIME,
        updated_at=TIME,
    )
    assert detail.status == "AWAITING_CLARIFICATION"


def test_memory_candidate_is_display_only_until_approved() -> None:
    candidate = memory_candidate()
    candidate_view = to_memory_record_view(candidate, observed_at=TIME)
    assert candidate_view.status == "CANDIDATE"
    with pytest.raises(ValidationError):
        MemoryRetrievalPayload(
            memories=[candidate_view], query_summary="matched memory"
        )

    approved = ApprovedMemory(
        memory_id=candidate.memory_id,
        retrieval_summary=candidate.retrieval_summary,
        status="APPROVED",
        recommended_behavior=candidate.recommended_behavior,
        trigger_conditions=candidate.trigger_conditions,
        policy_version=candidate.policy_version,
        claim_registry_version=candidate.claim_registry_version,
        scope=candidate.scope,
        confidence=candidate.confidence,
        approved_at=TIME,
    )
    from return_agent_contracts.models import (
        MemoryRetrievalObservation,
        MemorySearchHit,
    )

    hit = to_memory_retrieval_payload(
        MemoryRetrievalObservation(
            status="OK",
            query_summary="matched approved operational memory",
            hits=[MemorySearchHit(memory=approved, similarity=0.8)],
        )
    )
    assert hit.hits[0].memory.status == "APPROVED"
