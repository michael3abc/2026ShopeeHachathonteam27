"""Bounded checkpoint learning history, independent of Activity and narration."""

import re
from dataclasses import dataclass
from functools import wraps
from uuid import NAMESPACE_URL, uuid5

from return_agent_contracts.enums import ResolutionAction
from return_agent_contracts.models import (
    LearningDecision,
    LearningDialogueTurn,
    LearningEvent,
    LearningEvidence,
    LearningHumanDecision,
    LearningMemory,
    LearningTrace,
)
from return_agent_contracts.validation import (
    redact_learning_dialogue,
    validate_memory_summary,
)


@dataclass(frozen=True)
class LearningTraceLimits:
    max_events: int = 96
    max_bytes: int = 131072

    def __post_init__(self):
        if not 1 <= self.max_events <= 256 or self.max_bytes < 1024:
            raise ValueError("invalid learning trace limits")


def validate_safe_learning_text(value: object) -> None:
    """Reject unsafe projections rather than silently dropping source facts."""
    if isinstance(value, str):
        if re.fullmatch(r"[A-Z][A-Z0-9_-]*-[a-fA-F0-9]{32}", value):
            return  # Graph-owned UUID references are not payment-card numbers.
        validate_memory_summary(value)
    elif isinstance(value, dict):
        for item in value.values():
            validate_safe_learning_text(item)
    elif isinstance(value, list):
        for item in value:
            validate_safe_learning_text(item)


def _decision(handoff, *, final=False) -> LearningDecision:
    decision = handoff.proposed_decision if not final else handoff.final_decision
    return LearningDecision(
        handoff_id=handoff.handoff_id, action=decision.action,
        line_item_ids=decision.refund_scope.line_item_ids,
        return_decision=(decision.return_decision
                         if decision.action is ResolutionAction.FULL_REFUND else None),
        explanation=handoff.rationale_summary if not final else "Final adjudication; downstream execution not verified.",
    )


def _project(name: str, before: dict, update: dict, sequence: int) -> LearningEvent:
    state = before | update
    fields = {
        "event_id": "LEARNING-" + uuid5(NAMESPACE_URL, f"{state['thread_id']}:{sequence}:{name}").hex,
        "sequence": sequence, "node": name, "next_node": update.get("_route"),
    }
    dialogue = []
    if name == "parse_request" and sequence == 1:
        turn = state["conversation_turns"][0]
        dialogue.append(_dialogue(turn.turn_id, "USER", turn.text))
    if name == "request_clarification":
        request = before["pending_clarification_request"]
        for turn in update.get("conversation_turns", [])[len(before.get("conversation_turns", [])):]:
            dialogue.append(_dialogue(turn.turn_id, "USER", turn.text, request.request_id))
    if name == "request_evidence":
        turn = before.get("_learning_reply")
        if turn is None:
            fields["dialogue_missing"] = True
        else:
            dialogue.append(_dialogue(turn.turn_id, "USER", turn.text, before["pending_evidence_request"].request_id))
    for key, message_key in (("pending_clarification_request", "clarification_question"),
                             ("pending_evidence_request", "user_message")):
        request = update.get(key)
        if request is not None:
            dialogue.append(_dialogue(request.request_id, "AGENT", getattr(request, message_key), request.request_id))
            fields[key.removeprefix("pending_")] = request
    seen = {turn.turn_ref: turn for event in before["learning_trace"].events for turn in event.dialogue}
    unique_dialogue = []
    for turn in dialogue:
        if turn.turn_ref in seen and seen[turn.turn_ref] != turn:
            raise ValueError("conflicting dialogue identity")
        if turn.turn_ref not in seen:
            unique_dialogue.append(turn)
            seen[turn.turn_ref] = turn
    fields["dialogue"] = unique_dialogue
    if name == "parse_request":
        fields["intent"] = update.get("normalized_intent")
        fields["claimed_line_item_ids"] = state.get("claimed_line_item_ids", [])
        fields["clarification_request"] = update.get("pending_clarification_request")
    if name == "request_clarification":
        fields["clarification_request"] = before.get("pending_clarification_request")
        fields["response_turn_refs"] = [t.turn_id for t in update.get("conversation_turns", [])[len(before.get("conversation_turns", [])):]]
    if name == "load_case_context" and update.get("case_context"):
        fields["context_snapshot_version"] = update["case_context"].snapshot_version
        fields["order_snapshot_version"] = update["order_snapshot"].snapshot_version
        fields["claimed_line_item_ids"] = state["claimed_line_item_ids"]
    if name == "retrieve_policy" and update.get("policy_bundle"):
        bundle = update["policy_bundle"]
        fields["policy_bundle_version"] = bundle.policy_bundle_version
        fields["policy_versions"] = sorted({c.policy_version for c in bundle.clauses})
    if name in {"prepare_memory_query", "request_evidence"}:
        old_ids = {e.evidence_id for e in before.get("evidence_bundle", [])}
        fields["evidence"] = [
            LearningEvidence.model_validate(e.model_dump(exclude={"artifact_ref", "collected_at"}))
            for e in update.get("evidence_bundle", []) if e.evidence_id not in old_ids
        ]
        if name == "request_evidence":
            fields["evidence_request"] = before.get("pending_evidence_request")
    if name in {"prepare_memory_query", "retrieve_memory"}:
        fields["memory_query_summary"] = update.get("memory_query_summary", state.get("memory_query_summary"))
        observation = update.get("memory_retrieval")
        if observation:
            fields["memory_status"] = observation.status
            fields["error_code"] = observation.error_code
            fields["memories"] = [LearningMemory(
                memory_id=h.memory.memory_id, policy_version=h.memory.policy_version,
                claim_registry_version=h.memory.claim_registry_version,
                recommended_behavior=h.memory.recommended_behavior,
            ) for h in observation.hits]
    if name == "assess_case":
        fields["assessment"] = update.get("evidence_assessment")
        if fields["assessment"]:
            fields["claim_registry_version"] = fields["assessment"].claim_registry_version
    if name in {"assess_case", "propose_decision"}:
        fields["evidence_request"] = update.get("pending_evidence_request")
    if name == "propose_decision" and update.get("current_handoff"):
        fields["decision"] = _decision(update["current_handoff"])
    if name == "external_verification":
        fields["verification"] = update.get("verification_result")
    if name == "reviewer" and update.get("review_history"):
        fields["review"] = update["review_history"][-1]
    if name == "record_revision_event" and update.get("revision_events"):
        fields["revision_event_ref"] = update["revision_events"][-1].event_id
    if name == "await_human_review":
        fields["human_review_ref"] = update.get("human_review_ref")
        human = update.get("human_review_result")
        if human:
            fields["human_decision"] = LearningHumanDecision(
                decision=human.decision, final_resolution_ref=human.final_resolution_ref,
                correction_reason_code=getattr(human, "correction_reason_code", None),
                review_note=human.review_note,
            )
    if name == "emit_resolution_handoff" and update.get("resolution_handoff"):
        final = update["resolution_handoff"]
        fields["decision"] = _decision(final, final=True)
        fields["outcome_source"] = final.outcome_source
    if update.get("escalation_reason"):
        fields["error_code"] = update["escalation_reason"].value
    return LearningEvent.model_validate(fields)


def _dialogue(turn_ref: str, role: str, text: str, request_ref: str | None = None) -> LearningDialogueTurn:
    safe_text, redacted = redact_learning_dialogue(text)
    return LearningDialogueTurn(turn_ref=turn_ref, role=role, text=safe_text,
        request_ref=request_ref, redacted=redacted, trust=("USER_STATEMENT_UNVERIFIED"
        if role == "USER" else "AGENT_REQUEST_NOT_EXECUTION"))


def record_learning_node(name: str, function, limits: LearningTraceLimits):
    """Return checkpoint updates only after a node finishes, never on interrupt."""
    @wraps(function)
    def execute(state):
        update = function(state)
        reply = update.pop("_learning_reply", None)
        if name == "enqueue_memory_distillation":
            return update
        trace = state.get("learning_trace")
        if trace is None:
            trace = LearningTrace(case_ref=state["case_ref"], thread_id=state["thread_id"],
                                  status="INCOMPLETE", failure_code="MISSING_INITIAL_TRACE")
        if trace.status != "RECORDING":
            return update | {"learning_trace": trace}
        try:
            event = _project(name, state | {"_learning_reply": reply}, update, len(trace.events) + 1)
            validate_safe_learning_text(event.model_dump(mode="json"))
            events = [*trace.events, event]
            if len(events) > limits.max_events:
                raise OverflowError
            status = "COMPLETE" if event.outcome_source else "RECORDING"
            next_trace = trace.model_copy(update={"events": events, "status": status})
            if len(next_trace.model_dump_json().encode()) > limits.max_bytes:
                raise OverflowError
        except OverflowError:
            next_trace = trace.model_copy(update={"status": "LIMIT_EXCEEDED", "failure_code": "TRACE_BUDGET_EXCEEDED"})
        except ValueError:
            next_trace = trace.model_copy(update={"status": "UNSAFE_CONTENT", "failure_code": "UNSAFE_LEARNING_PROJECTION"})
        except Exception:  # noqa: BLE001 - observational learning must not block adjudication
            next_trace = trace.model_copy(update={"status": "INCOMPLETE", "failure_code": "LEARNING_PROJECTION_FAILED"})
        return update | {"learning_trace": next_trace}
    return execute
