from datetime import datetime
from typing import Any

from return_agent_contracts.registry import REGISTRY, REGISTRY_VERSION
from return_agent_contracts.validation import expected_pairs

from .state import RuntimeState

PROMPT_VERSIONS = {"INTAKE": "intake:1.1", "MEMORY_QUERY_SUMMARY": "memory-query:1.0", "ASSESS": "resolver:1.1", "PROPOSE_OR_REVISE": "resolver:1.1", "REVIEW": "reviewer:2.1", "MEMORY_DISTILL": "memory-distiller:2.0", "ACTIVITY_NARRATION": "narration:1.0"}


def dump(value):
    return value.model_dump(mode="json") if value is not None else None


def registry_input(state: RuntimeState) -> dict[str, Any]:
    claims = sorted({claim for clause in state.policy_bundle.clauses for claim in clause.required_claim_ids})
    return {"claim_registry_version": REGISTRY_VERSION, "claim_registry": [dump(REGISTRY[claim]) for claim in claims], "expected_claim_subject_pairs": [{"claim_id": claim, "subject": subject} for claim, subject in sorted(expected_pairs(state.policy_bundle, state.order_snapshot, state.claimed_line_item_ids))]}


def intake_input(state: RuntimeState) -> dict[str, Any]:
    fields = {"line_item_id", "sku_ref", "category_ref", "title", "quantity"}
    return {"prompt_version": PROMPT_VERSIONS["INTAKE"], "trusted_order_ref": state.trusted_order_ref, "conversation_turns": [dump(turn) for turn in state.conversation_turns], "existing_intent": dump(state.normalized_intent), "order_line_items": [item.model_dump(mode="json", include=fields) for item in state.order_snapshot.line_items] if state.order_snapshot else None}


def memory_query_input(state: RuntimeState) -> dict[str, Any]:
    return {"prompt_version": PROMPT_VERSIONS["MEMORY_QUERY_SUMMARY"], "reason": state.normalized_intent.reason_summary, "reason_code": state.normalized_intent.reason_code, "market": state.case_context.market, "case_opened_at": state.case_context.case_opened_at.isoformat(), "delivered_at": state.order_snapshot.delivered_at.isoformat(), "claimed_items": [{"title": item.title, "category": item.category_ref} for item in state.order_snapshot.line_items if item.line_item_id in state.claimed_line_item_ids], "evidence": [{"subject": item.subject, "type": item.type, "source": item.source, "summary": item.extracted_summary} for item in state.evidence_bundle]}


def resolver_input(state: RuntimeState) -> dict[str, Any]:
    order = state.order_snapshot.model_dump(mode="json", exclude={"currency", "refundable_amount_max", "already_refunded_amount"})
    for item in order["line_items"]:
        item.pop("refundable_amount")
    return {"prompt_version": PROMPT_VERSIONS["ASSESS"], "normalized_intent": dump(state.normalized_intent), "claimed_line_item_ids": state.claimed_line_item_ids, "case_context": dump(state.case_context), "order_facts": order, "policy_bundle": dump(state.policy_bundle), **registry_input(state), "evidence_bundle": [dump(item) for item in state.evidence_bundle], "evidence_assessment": dump(state.evidence_assessment), "operational_memory": [dump(hit.memory) for hit in state.memory_retrieval.hits] if state.memory_retrieval else [], "verification_feedback": [dump(issue) for issue in state.verification_feedback], "review_feedback": dump(state.pending_review_result)}


def reviewer_input(state: RuntimeState, now: datetime) -> dict[str, Any]:
    return {"prompt_version": PROMPT_VERSIONS["REVIEW"], "reviewed_at_utc": now.isoformat(), "case_context": dump(state.case_context), "order_snapshot": dump(state.order_snapshot), "policy_bundle": dump(state.policy_bundle), **registry_input(state), "proposed_decision_handoff": dump(state.current_handoff)}
