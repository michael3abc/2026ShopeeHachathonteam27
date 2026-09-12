from dataclasses import replace
from decimal import Decimal

import pytest
from pydantic import TypeAdapter

from return_agent_contracts.domain import FailedVerificationResult, VerificationIssue
from return_agent_contracts.human import HumanReviewResult
from return_agent_contracts.messages import AgentResumeRequest, AgentUserTurn, ClarificationResume, EvidenceResume, HumanReviewPollResume
from return_agent_runtime.graph import NODES, ReturnRuntime
from return_agent_runtime.ports import stable_id
from return_agent_runtime.state import RuntimeState


def test_a_auto_resolution_and_separated_model_inputs(runtime_scenario):
    s = runtime_scenario
    result = s.runtime.start(s.request)
    assert result.result_type == "RESOLUTION", s.runtime.state(s.request.thread_id)
    assert result.resolution_handoff.final_decision.amount == Decimal("1200")
    assert result.resolution_handoff.review_gate.status == "PASS"
    assert s.providers.submitted is None
    assert len(NODES) == 16
    state = s.runtime.state(s.request.thread_id)
    assert RuntimeState.model_validate_json(state.model_dump_json()) == state
    assert state.memory_distillation_input is None
    for task, payload in s.model.calls:
        if task in ("ASSESS", "PROPOSE_OR_REVISE"):
            assert not {"currency", "refundable_amount_max", "already_refunded_amount"}.intersection(payload["order_facts"])
            assert all("refundable_amount" not in item for item in payload["order_facts"]["line_items"])
        if task == "REVIEW":
            assert not {"operational_memory", "evidence_assessment", "memory_retrieval"}.intersection(payload)
    assert s.runtime.continue_run(s.request.thread_id) == result
    with pytest.raises(ValueError):
        s.runtime.start(s.request)


def test_evidence_interrupt_recreates_runtime_and_resumes(runtime_scenario):
    s = runtime_scenario
    request = s.request.model_copy(update={"initial_turn": s.request.initial_turn.model_copy(update={"attached_artifact_refs": []})})
    result = s.runtime.start(request)
    assert result.result_type == "INTERRUPTED" and result.interrupt_payload.kind == "EVIDENCE_REQUEST"
    resumed = ReturnRuntime(s.deps, s.saver)
    assert resumed.continue_run(request.thread_id) == result
    with pytest.raises(ValueError):
        resumed.resume(AgentResumeRequest(thread_id=request.thread_id, payload=HumanReviewPollResume(kind="HUMAN_REVIEW")))
    result = resumed.resume(AgentResumeRequest(thread_id=request.thread_id, payload=EvidenceResume(kind="EVIDENCE_REQUEST", artifact_refs=[s.evidence.artifact_ref])))
    assert result.result_type == "RESOLUTION", resumed.state(request.thread_id)
    assert s.providers.query_calls == 2


def test_high_value_human_edit_never_returns_to_reviewer(runtime_scenario):
    s = runtime_scenario
    s.providers.order = s.order.model_copy(update={"refundable_amount_max": Decimal("6200"), "line_items": [s.order.line_items[0].model_copy(update={"refundable_amount": Decimal("6200")})]})
    result = s.runtime.start(s.request)
    assert result.result_type == "INTERRUPTED" and result.interrupt_payload.kind == "HUMAN_REVIEW"
    assert result.interrupt_payload.routing_reason == "HIGH_VALUE_ITEM"
    s.providers.human_result = TypeAdapter(HumanReviewResult).validate_python({"decision": "EDIT", "final_resolution_ref": "runtime-human-final", "reviewed_at": s.now, "review_note": "經人工判斷商品已無回收價值，免退回。", "generalizable": True, "correction_reason_code": "RETURN_REQUIREMENT_INCORRECT", "corrected_decision": {"action": "FULL_REFUND", "refund_scope": {"line_item_ids": ["runtime-item"]}, "return_decision": {"source": "HUMAN_REVIEW", "requirement": {"required": False, "reason_code": "ITEM_UNSALVAGEABLE"}}}})
    result = ReturnRuntime(s.deps, s.saver).resume(AgentResumeRequest(thread_id=s.request.thread_id, payload=HumanReviewPollResume(kind="HUMAN_REVIEW")))
    assert result.result_type == "RESOLUTION", s.runtime.state(s.request.thread_id)
    assert result.resolution_handoff.outcome_source == "HUMAN_EDIT"
    assert s.model.counts["REVIEW"] == 1
    assert s.runtime.state(s.request.thread_id).memory_distillation_input.human_review_result == s.providers.human_result


def revise(s, index):
    def output(payload):
        return {"verdict": "REVISE", "reviewed_at": s.now, "reviewer_prompt_version": "reviewer:2.1", "reviewer_claim_findings": s.model.findings(payload), "revision_reasons": [{"code": "RETURN_REQUIREMENT_INCONSISTENT", "subject": "runtime-item", "message": f"需補充第 {index} 項退回判斷依據", "required_change": f"說明第 {index} 項檢測目的", "policy_refs": ["runtime-clause"]}]}
    return output


def test_four_revise_reviews_consume_three_revisions_then_human(runtime_scenario):
    s = runtime_scenario
    s.model.scripted["REVIEW"] = [revise(s, index) for index in range(4)]
    result = s.runtime.start(s.request)
    assert result.result_type == "INTERRUPTED", s.runtime.state(s.request.thread_id)
    assert result.interrupt_payload.routing_reason == "REVISION_BUDGET_EXCEEDED"
    dossier = result.interrupt_payload.dossier
    assert len(dossier.review_history) == 4 and len(dossier.revision_events) == 3
    assert [p.revision_round for p in dossier.proposal_history] == [0, 1, 2, 3]
    assert dossier.review_gate is None


def test_verification_retries_have_distinct_ids_and_no_review_round(runtime_scenario):
    s = runtime_scenario
    attempts = []
    def verify(params):
        attempts.append(params.handoff.handoff_id)
        if len(attempts) < 3:
            return FailedVerificationResult(status="FAIL", verification_version="verification:1.0", issues=[VerificationIssue(code="TEMPORARY_FIX_REQUIRED", field_path="handoff", message="修正提案")])
        from return_agent_contracts.domain import PassedVerificationResult
        return PassedVerificationResult(status="PASS", verification_version="verification:1.0")
    s.providers.verify = verify
    assert s.runtime.start(s.request).result_type == "RESOLUTION"
    state = s.runtime.state(s.request.thread_id)
    assert len(set(attempts)) == 3 and state.verification_round == 2 and state.revision_round == 0
    assert len(state.proposal_history) == 1 and s.model.counts["REVIEW"] == 1
    assert attempts[0] == stable_id("handoff", s.request.case_ref, 1)


@pytest.mark.parametrize("failure", ["summary", "memory", "artifact", "shape"])
def test_optional_memory_boundary_and_fail_closed_contracts(runtime_scenario, failure):
    s = runtime_scenario
    request = s.request
    if failure == "summary":
        s.model.scripted["MEMORY_QUERY_SUMMARY"] = [ValueError("synthetic failure")]
    elif failure == "memory":
        def fail(params):
            raise RuntimeError("synthetic retrieval failure")
        s.providers.query_approved = fail
    elif failure == "artifact":
        request = request.model_copy(update={"initial_turn": request.initial_turn.model_copy(update={"attached_artifact_refs": ["unknown"]})})
    else:
        s.model.scripted["ASSESS"] = [{"evidence_status": "invented"}]
    result = s.runtime.start(request)
    assert result.result_type == ("RESOLUTION" if failure in ("summary", "memory") else "MANUAL_ESCALATION")
    if failure in ("summary", "memory"):
        memory = s.runtime.state(request.thread_id).memory_retrieval
        assert memory.status == "UNAVAILABLE" and memory.hits == []
    else:
        assert result.manual_escalation.escalation_reason == "CONTRACT_VIOLATION"


def test_clarification_budget_and_duplicate_turn(runtime_scenario):
    s = runtime_scenario
    incomplete = {"completeness": "INCOMPLETE", "requested_action": "UNSPECIFIED", "missing_fields": ["reason"], "clarification_question": "請說明退貨原因。"}
    s.model.scripted["INTAKE"] = [incomplete] * 3
    assert s.runtime.start(s.request).interrupt_payload.kind == "CLARIFICATION"
    with pytest.raises(ValueError, match="Duplicate"):
        s.runtime.resume(AgentResumeRequest(thread_id=s.request.thread_id, payload=ClarificationResume(kind="CLARIFICATION", turn=s.request.initial_turn)))
    for index in range(2):
        result = s.runtime.resume(AgentResumeRequest(thread_id=s.request.thread_id, payload=ClarificationResume(kind="CLARIFICATION", turn=AgentUserTurn(turn_id=f"clarify-{index}", role="USER", text="仍未說明原因", received_at=s.now))))
    assert result.result_type == "MANUAL_ESCALATION" and result.manual_escalation.escalation_reason == "CLARIFICATION_BUDGET_EXCEEDED"


def test_observer_enter_precedes_model_call_and_pause_is_distinct(runtime_scenario):
    s = runtime_scenario
    observations = []
    class Observer:
        def observe(self, observation):
            observations.append((observation.node, observation.phase, sum(s.model.counts.values())))
        def paused(self, node, task_ref):
            observations.append((node, "PAUSED", sum(s.model.counts.values())))
    runtime = ReturnRuntime(replace(s.deps, observer=Observer()), s.saver)
    request = s.request.model_copy(update={"initial_turn": s.request.initial_turn.model_copy(update={"attached_artifact_refs": []})})
    assert runtime.start(request).result_type == "INTERRUPTED"
    assert observations[0] == ("parse_request", "ENTER", 0)
    assert any(node == "request_evidence" and phase == "PAUSED" for node, phase, _ in observations)


def test_reviewer_evidence_objection_survives_resume_and_reassessment(runtime_scenario):
    s = runtime_scenario
    def needs_evidence(payload):
        result = revise(s, 1)(payload)
        result["reviewer_claim_findings"][1].update(status="UNSUPPORTED", supporting_evidence_refs=[])
        result["revision_reasons"][0].update(code="EVIDENCE_INSUFFICIENT", required_change="補充能辨識品項的裂痕近照")
        return result
    s.model.scripted["REVIEW"] = [needs_evidence]
    s.model.scripted["PROPOSE_OR_REVISE"] = [lambda payload: s.model.default("PROPOSE_OR_REVISE", payload), {"result_type": "REQUEST_EVIDENCE", "evidence_request": {"request_id": "model-request", "missing_claims": [{"claim_id": "ITEM_PHYSICALLY_DAMAGED", "subject": "runtime-item"}], "accepted_evidence_types": ["IMAGE", "VIDEO"], "policy_refs": ["runtime-clause"], "user_message": "請補充品項可辨識的近照。"}}]
    result = s.runtime.start(s.request)
    assert result.result_type == "INTERRUPTED" and result.interrupt_payload.kind == "EVIDENCE_REQUEST"
    assert s.runtime.state(s.request.thread_id).pending_review_result.verdict == "REVISE"
    result = ReturnRuntime(s.deps, s.saver).resume(AgentResumeRequest(thread_id=s.request.thread_id, payload=EvidenceResume(kind="EVIDENCE_REQUEST", artifact_refs=[s.evidence.artifact_ref])))
    assert result.result_type == "RESOLUTION", s.runtime.state(s.request.thread_id)
    assessments = [payload for task, payload in s.model.calls if task == "ASSESS"]
    assert assessments[-1]["review_feedback"]["revision_reasons"][0]["code"] == "EVIDENCE_INSUFFICIENT"
    assert s.providers.query_calls == 2 and s.model.counts["REVIEW"] == 2


def test_evidence_budget_is_bounded_even_when_model_keeps_requesting(runtime_scenario):
    s = runtime_scenario
    def insufficient(payload):
        payload = {**payload, "evidence_bundle": []}
        return s.model.default("ASSESS", payload)
    s.model.scripted["ASSESS"] = [insufficient] * 3
    result = s.runtime.start(s.request)
    for _ in range(2):
        assert result.result_type == "INTERRUPTED"
        result = s.runtime.resume(AgentResumeRequest(thread_id=s.request.thread_id, payload=EvidenceResume(kind="EVIDENCE_REQUEST", artifact_refs=[s.evidence.artifact_ref])))
    assert result.result_type == "MANUAL_ESCALATION" and result.manual_escalation.escalation_reason == "EVIDENCE_BUDGET_EXCEEDED"


def test_verification_budget_and_explicit_conflict_escalate(runtime_scenario):
    s = runtime_scenario
    s.providers.verify = lambda params: FailedVerificationResult(status="FAIL", verification_version="verification:1.0", issues=[VerificationIssue(code="INVALID", field_path="handoff", message="持續不符合")])
    result = s.runtime.start(s.request)
    assert result.result_type == "MANUAL_ESCALATION" and result.manual_escalation.escalation_reason == "VERIFICATION_BUDGET_EXCEEDED"
    assert s.model.counts["REVIEW"] == 0 and s.model.counts["PROPOSE_OR_REVISE"] == 3
