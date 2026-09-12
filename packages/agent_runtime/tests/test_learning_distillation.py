"""Whole-case learning without changing the decision graph's authority."""

from dataclasses import replace

import pytest
from return_agent_contracts.models import MemoryCandidateOutput, MemorySkipOutput
from return_agent_contracts.runtime import EvidenceResume
from return_agent_runtime import MemoryDistiller, ReturnAgentRuntime
from return_agent_runtime.learning import LearningTraceLimits, record_learning_node
from return_agent_runtime.model import ModelTask

from .conftest import approved_review, evidence_item, make_runtime, proposal_output, supported_assessment, user_turn
from .fakes import QueuedModel
from .test_interrupt_resume import complete_intake, insufficient_assessment


def reflection(trace, *, category="OPERATIONAL_METHOD"):
    refs = [e.event_id for e in trace.events]
    return dict(
        case_review=dict(key_issue="Arrival damage needs contextual evidence.",
            actions_taken=["Collected and assessed evidence."], observations=["Observed damaged item."],
            judgment_changes=[], final_action=trace.events[-1].decision.action,
            limitations=["Refund execution and causal benefit are unverified."], source_event_refs=refs),
        learning=dict(category=category, explanation="A context-preserving evidence collection method.", source_event_refs=refs),
    )


def candidate_output(trace):
    return MemoryCandidateOutput(
        result_type="CREATE_CANDIDATE", **reflection(trace),
        candidate=dict(memory_id="MODEL-ID", retrieval_summary="Keep package and damage in the same observation.",
            trigger_conditions=["Arrival damage with incomplete context."],
            recommended_behavior="Request an image connecting package and damaged item.",
            rationale="The case provides an operational observation, not proof of causation.",
            source_case_refs=[trace.case_ref], source_event_refs=[e.event_id for e in trace.events],
            applicability_limits=["Only arrival damage evidence gaps."],
            prohibited_inferences=["Damage alone does not prove arrival timing or refund eligibility."],
            policy_version="POLICY-12:v3", claim_registry_version="claim-registry:1.0",
            scope=dict(market="TW", reason_codes=["ITEM_DAMAGED"], claim_ids=["DAMAGE_PRESENT_ON_ARRIVAL"],
                       categories=["CAT-AUDIO-SPEAKERS"]), confidence=0.6, status="CANDIDATE"),
    )


def closed_case(*, needs_evidence=False, limits=None):
    model = QueuedModel()
    model.queue(ModelTask.INTAKE, complete_intake())
    model.queue(ModelTask.ASSESS, *([insufficient_assessment()] if needs_evidence else []), supported_assessment())
    model.queue(ModelTask.PROPOSE_OR_REVISE, proposal_output())
    model.queue(ModelTask.REVIEW, approved_review())
    evidence = evidence_item()
    runtime, _ = make_runtime(model=model, evidence_items={evidence.artifact_ref: evidence})
    if limits:
        runtime = ReturnAgentRuntime(replace(runtime.dependencies, learning_trace_limits=limits), runtime.checkpointer)
    result = runtime.start(thread_id="THREAD-LEARNING", case_ref="CASE-001",
        initial_turn=user_turn(artifacts=[] if needs_evidence else [evidence.artifact_ref]))
    if needs_evidence:
        paused = runtime.graph.get_state({"configurable": {"thread_id": "THREAD-LEARNING"}}).values
        assert paused["memory_distillation_input"] is None
        assert paused["learning_trace"].events[-1].evidence_request is not None
        result = runtime.resume(thread_id="THREAD-LEARNING", payload=EvidenceResume(
            kind="EVIDENCE_REQUEST", artifact_refs=[evidence.artifact_ref]))
    state = runtime.graph.get_state({"configurable": {"thread_id": "THREAD-LEARNING"}}).values
    return runtime, model, state, result


def test_uncorrected_case_can_learn_and_skipped_case_still_has_review():
    _, model, state, result = closed_case()
    input_ = state["memory_distillation_input"]
    assert input_ is not None and not input_.revision_events
    trace = input_.learning_trace
    assert trace.status == "COMPLETE"
    assert trace.events[-1].decision.action == result.resolution_handoff.final_decision.action
    model.queue(ModelTask.MEMORY_DISTILL, candidate_output(trace))
    output = MemoryDistiller(model).distill(input_)
    assert isinstance(output, MemoryCandidateOutput)
    assert output.candidate.memory_id.startswith("MEMORY-V2-")
    payload = model.calls[-1].payload
    assert "distillation_input" not in payload
    assert "artifact://" not in str(payload)
    model.queue(ModelTask.MEMORY_DISTILL, MemorySkipOutput(result_type="SKIP",
        reason_code="CASE_SPECIFIC_ONLY", **reflection(trace, category="CASE_DISCRETION")))
    skipped = MemoryDistiller(model).distill(input_)
    assert skipped.case_review and skipped.learning.category == "CASE_DISCRETION"


def test_interrupt_retains_both_assessments_request_and_observation():
    _, _, state, _ = closed_case(needs_evidence=True)
    trace = state["learning_trace"]
    assert trace.status == "COMPLETE"
    assessments = [e.assessment for e in trace.events if e.assessment]
    assert [a.evidence_status.value for a in assessments] == ["INSUFFICIENT", "SUFFICIENT_FOR_APPROVAL"]
    response = next(e for e in trace.events if e.node == "request_evidence")
    assert response.evidence_request and response.evidence[0].evidence_id == "EV-002"
    assert len({e.event_id for e in trace.events}) == len(trace.events)
    assert "artifact://" not in trace.model_dump_json()


@pytest.mark.parametrize("mutation", ["missing", "incomplete", "limit", "unsafe", "wrong_case"])
def test_invalid_history_skips_without_model(mutation):
    _, model, state, _ = closed_case()
    input_ = state["memory_distillation_input"]
    trace = input_.learning_trace
    changes = {"incomplete": {"status": "INCOMPLETE"}, "limit": {"status": "LIMIT_EXCEEDED"},
               "unsafe": {"status": "UNSAFE_CONTENT"}, "wrong_case": {"case_ref": "OTHER"}}
    bad_trace = None if mutation == "missing" else trace.model_copy(update=changes[mutation])
    before = len(model.calls)
    output = MemoryDistiller(model).distill(input_.model_copy(update={"learning_trace": bad_trace}))
    assert output.result_type == "SKIP" and output.case_review is None
    assert len(model.calls) == before


@pytest.mark.parametrize("field", ["source", "category", "pii", "limits", "final"])
def test_untrusted_distillation_cannot_create_candidate(field):
    _, model, state, _ = closed_case()
    input_ = state["memory_distillation_input"]
    output = candidate_output(input_.learning_trace)
    if field == "source":
        output.candidate.source_event_refs = ["OTHER-CASE-EVENT"]
    elif field == "category":
        output.learning.category = "SYSTEM_DEFECT"
    elif field == "pii":
        output.case_review.key_issue = "Email private@example.com"
    elif field == "limits":
        output.candidate.applicability_limits = []
    else:
        output.case_review.final_action = "DECLINE"
    model.queue(ModelTask.MEMORY_DISTILL, output)
    with pytest.raises(ValueError):
        MemoryDistiller(model).distill(input_)


def test_recording_is_retry_stable_and_privacy_failure_does_not_change_route():
    _, _, state, _ = closed_case()
    trace = state["learning_trace"].model_copy(update={"events": [], "status": "RECORDING"})
    source = state | {"learning_trace": trace}
    update = {"normalized_intent": state["normalized_intent"], "_route": "load_case_context"}
    node = record_learning_node("parse_request", lambda _: update, LearningTraceLimits())
    assert node(source)["learning_trace"] == node(source)["learning_trace"]
    update["normalized_intent"] = update["normalized_intent"].model_copy(update={"reason_summary": "Email private@example.com"})
    result = node(source)
    assert result["_route"] == "load_case_context"
    assert result["learning_trace"].status == "UNSAFE_CONTENT"
    assert not result["learning_trace"].events


@pytest.mark.parametrize("field", ["reason_codes", "claim_ids", "categories"])
def test_new_experience_cannot_use_wildcard_to_broaden_source_scope(field):
    _, model, state, _ = closed_case()
    input_ = state["memory_distillation_input"]
    output = candidate_output(input_.learning_trace)
    setattr(output.candidate.scope, field, [])
    model.queue(ModelTask.MEMORY_DISTILL, output)
    with pytest.raises(ValueError, match="wildcard scope exceeds"):
        MemoryDistiller(model).distill(input_)


def test_trace_budget_never_blocks_resolution():
    _, model, state, result = closed_case(limits=LearningTraceLimits(max_events=2))
    assert result.status == "COMPLETED"
    assert state["learning_trace"].status == "LIMIT_EXCEEDED"
    assert len(state["learning_trace"].events) == 2
    assert MemoryDistiller(model).distill(state["memory_distillation_input"]).reason_code == "TRACE_LIMIT_EXCEEDED"
