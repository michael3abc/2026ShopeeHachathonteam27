from copy import deepcopy

import pytest

from return_agent_contracts.activity import ActivityEmission, ActivityFacts, Narration, NarrationJob, NodeSummary
from return_agent_contracts.distillation import MemoryDistillationInput
from return_agent_contracts.domain import ApprovalEvidenceAssessment
from return_agent_contracts.human import ReviewerApprovedResolutionHandoff
from return_agent_contracts.memory import MemoryRetrievalObservation
from return_agent_contracts.workflow import AgentInterruptedEvent, NodeExecutionObservation


def emission(scenario, payload):
    return ActivityEmission(event_id="activity-test", case_ref="case-test", scope="CASE", run_id="run-test", node="assess_case", operation_id="operation-test", attempt_id="attempt-test", occurred_at=scenario["now"], payload=payload)


@pytest.mark.parametrize("injection", ["https://example.invalid", "person@example.invalid", "Bearer token", "0912-345-678", {"raw": "payload"}])
def test_c35_activity_identifier_rejects_sensitive_or_raw_values(injection):
    with pytest.raises(ValueError): ActivityFacts(references=[injection])


def test_c35_no_prompt_or_full_state_fields(scenario):
    with pytest.raises(ValueError): ActivityFacts(raw_prompt="private prompt")
    with pytest.raises(ValueError):
        ActivityEmission.model_validate({**emission(scenario, NodeSummary(facts=ActivityFacts())).model_dump(), "state": {"any": "data"}})


def test_memory_prose_is_omitted_from_activity_summary():
    summary = NodeSummary(facts=ActivityFacts(count=1), memory_retrieval={"query_summary": "private text", "hits": [{"anything": "private"}]})
    assert summary.memory_retrieval is None
    assert "private" not in summary.model_dump_json()


def test_narration_source_is_summary_with_facts_only(scenario):
    source = emission(scenario, NodeSummary(facts=ActivityFacts(count=2)))
    NarrationJob(job_id="narration-test", source=source)
    source.payload = {"type": "tool", "name": "resolve", "phase": "STARTED"}
    with pytest.raises(ValueError): NarrationJob(job_id="narration-test", source=source)


@pytest.mark.parametrize("payload", [
    {"status": "COMPLETED", "text": None},
    {"status": "COMPLETED", "text": "已完成。", "error_code": "FAILED"},
    {"status": "UNAVAILABLE"},
    {"status": "UNAVAILABLE", "error_code": "TIMEOUT", "text": "改用模板。"},
    {"status": "COMPLETED", "text": "第一句。第二句。第三句。"},
    {"status": "COMPLETED", "text": "已啟動下一節點。"},
])
def test_c32_c33_narration_result_is_coherent(payload):
    with pytest.raises(ValueError): Narration(source_event_id="activity-test", **payload)


def test_offline_narration_is_explicitly_disabled():
    disabled = Narration(source_event_id="activity-test", status="UNAVAILABLE", error_code="NARRATION_DISABLED_OFFLINE_DEMO")
    assert disabled.text is None


def test_memory_unavailable_clears_hits_and_exposes_error():
    with pytest.raises(ValueError): MemoryRetrievalObservation(status="UNAVAILABLE")
    with pytest.raises(ValueError): MemoryRetrievalObservation(status="OK", error_code="SUMMARY_UNAVAILABLE", query_summary="測試摘要")
    valid = MemoryRetrievalObservation(status="UNAVAILABLE", error_code="RETRIEVAL_UNAVAILABLE", query_summary="測試摘要")
    assert valid.hits == []


def test_node_observation_phase_matches_payload():
    with pytest.raises(ValueError): NodeExecutionObservation(node="assess_case", phase="ERROR", task_ref="task-test")
    with pytest.raises(ValueError): NodeExecutionObservation(node="assess_case", phase="ENTER", task_ref="task-test", error_message="error")
    with pytest.raises(ValueError): NodeExecutionObservation(node="assess_case", phase="EXIT", task_ref="task-test", memory_retrieval={"status": "OK", "query_summary": "測試摘要"})


def test_service_event_cannot_project_another_cases_interrupt(scenario):
    event = dict(schema_version="v1", event_id="event-test", command_id="command-test", case_ref="case-test", thread_id="thread-test", event_index=1, occurred_at=scenario["now"], event_type="INTERRUPTED", payload={"result": {"result_type": "INTERRUPTED", "status": "INTERRUPTED", "interrupt_payload": {"kind": "CLARIFICATION", "case_ref": "other-case", "request": {"request_id": "request-test", "clarification_round": 1, "missing_fields": ["item"], "clarification_question": "哪個品項？"}}}})
    with pytest.raises(ValueError): AgentInterruptedEvent.model_validate(event)


def test_distillation_requires_a_confirmed_correction_trace(scenario):
    s = scenario
    proposal = s["handoff"].proposed_decision
    final = ReviewerApprovedResolutionHandoff(handoff_id=s["handoff"].handoff_id, case_ref=s["context"].case_ref, emitted_at=s["now"], execution_blocked=False, outcome_source="REVIEWER_APPROVE", review_result=s["review"], final_decision={key: value for key, value in proposal.model_dump().items() if key not in ("evidence_refs", "policy_refs")})
    data = dict(case_context=s["context"], evidence_assessment=ApprovalEvidenceAssessment(evidence_status="SUFFICIENT_FOR_APPROVAL", claim_registry_version=s["handoff"].claim_registry_version, claim_findings=s["findings"]), final_resolution=final, policy_bundle=s["policy"], proposal_history=[s["handoff"]], claimed_categories=["audio"])
    with pytest.raises(ValueError, match="confirmed correction"):
        MemoryDistillationInput(**data)
