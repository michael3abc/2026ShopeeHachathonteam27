"""LangGraph custom-stream bridge for transport-neutral activity spans."""

import logging
from uuid import uuid4

from langchain_core.runnables import RunnableConfig
from langgraph.config import get_stream_writer
from return_agent_contracts.activity import ActivityFacts, IntentDisplay, safe_reference
from return_agent_contracts.activity_observer import (
    CURRENT_ACTIVITY,
    ActivityContext,
    facts_from,
    span,
)


def traced_node(name, function):
    def execute(state: dict, config: RunnableConfig):
        context = ActivityContext(
            case_ref=state["case_ref"],
            run_id=config["configurable"].get("activity_run_id", state["thread_id"]),
            scope="CASE",
            node=name,
            attempt_id=uuid4().hex,
            sink=get_stream_writer(),
        )
        token = CURRENT_ACTIVITY.set(context)
        try:
            with span("node", name) as outcome:
                result = function(state)
                value = result
                for key in (
                    "current_handoff",
                    "evidence_assessment",
                    "normalized_intent",
                    "policy_bundle",
                    "order_snapshot",
                    "verification_result",
                    "review_gate",
                    "resolution_handoff",
                    "manual_escalation",
                    "memory_retrieval",
                    "human_review_result",
                ):
                    if result.get(key) is not None:
                        value = result[key]
                        break
                if result.get("review_history"):
                    value = result["review_history"][-1]
                try:
                    facts = facts_from(value)
                    if (
                        name == "external_verification"
                        and "verification_provider" in context.observations
                    ):
                        facts = context.observations[
                            "verification_provider"
                        ].model_copy(deep=True)
                except (ValueError, TypeError, AttributeError):
                    logging.getLogger(__name__).error(
                        "node activity projection unavailable"
                    )
                    facts = ActivityFacts(outcome="SUMMARY_UNAVAILABLE")
                facts.next_node = result.get("_route")
                gate = result.get("review_gate")
                if gate is not None and gate.reason:
                    facts.reason_codes = [*facts.reason_codes, gate.reason][:30]
                if result.get("escalation_reason") is not None:
                    facts.reason_codes = [str(result["escalation_reason"])]
                if name == "terminate_automation":
                    facts.next_node = "__end__"
                outcome["facts"] = facts
                intent = result.get("normalized_intent")
                if (
                    name in {"parse_request", "load_case_context"}
                    and intent is not None
                ):
                    categories = {
                        "order_ref": "ORDER",
                        "reason_code": "REASON",
                        "reason_summary": "REASON",
                        "requested_action": "ACTION",
                        "claimed_line_item_ids": "ITEMS",
                    }
                    outcome["intent_display"] = IntentDisplay(
                        reason_code=intent.reason_code,
                        requested_action=intent.requested_action,
                        claimed_line_item_ids=[
                            safe_reference(ref) for ref in intent.claimed_line_item_ids
                        ],
                        completeness=intent.completeness,
                        missing_fields=list(
                            dict.fromkeys(
                                categories.get(field, "OTHER")
                                for field in intent.missing_fields
                            )
                        ),
                    )
                outcome["memory_retrieval"] = result.get("memory_retrieval")
                outcome["review_gate"] = result.get("review_gate")
                return result
        finally:
            CURRENT_ACTIVITY.reset(token)

    return execute
