import pytest
from return_agent_contracts.models import ApprovedHumanReviewResult
from return_agent_contracts.review_gates import ReviewerGateConfig
from return_agent_contracts.runtime import HumanReviewPollResume
from return_agent_runtime.model import ModelTask
from .conftest import TIME, approved_review, evidence_item, make_runtime, user_turn, proposal_output
from .fakes import QueuedModel
from .test_revision_and_failures import queue_initial_resolution, revised_review

@pytest.mark.asyncio
async def test_first_approve_interrupts_without_revision_and_resume_never_reenters_reviewer():
    model = QueuedModel()
    queue_initial_resolution(model)
    model.queue(ModelTask.REVIEW, approved_review())
    evidence = evidence_item()
    runtime, providers = make_runtime(model=model, evidence_items={evidence.artifact_ref: evidence},
        reviewer_gate_config=ReviewerGateConfig(thresholds={"TWD": "1"}), human_results=[None, ApprovedHumanReviewResult(
            decision="APPROVE", review_note="Authorized above the automatic limit.", final_resolution_ref="RES-1", reviewed_at=TIME)])
    observations = []
    result = await runtime.astart(thread_id="GATE-1", case_ref="CASE-001", initial_turn=user_turn(artifacts=[evidence.artifact_ref]), observer=observations.append)
    assert result.interrupt_payload.routing_reason == "HIGH_VALUE_ITEM"
    assert result.interrupt_payload.review_result.verdict.value == "APPROVE"
    dossier = result.interrupt_payload.dossier
    assert dossier.proposal_history[-1].revision_round == 0
    assert dossier.revision_events == []
    assert any(o.review_gate and o.review_gate.status == "HUMAN_REQUIRED" for o in observations)
    completed = await runtime.aresume(thread_id="GATE-1", payload=HumanReviewPollResume(kind="HUMAN_REVIEW"))
    assert completed.resolution_handoff.outcome_source.value == "HUMAN_APPROVE"
    assert completed.resolution_handoff.review_gate == dossier.review_gate
    assert len(providers["human"].submit_calls) == 1

def test_revise_does_not_run_monetary_gate_and_approve_after_revision_does():
    model = QueuedModel()
    queue_initial_resolution(model)
    model.queue(ModelTask.PROPOSE_OR_REVISE, proposal_output(rationale="Reviewer feedback was applied."))
    model.queue(ModelTask.REVIEW, revised_review(), approved_review())
    evidence = evidence_item()
    runtime, _ = make_runtime(model=model, evidence_items={evidence.artifact_ref: evidence},
        reviewer_gate_config=ReviewerGateConfig(thresholds={}),
        verification_results=[{"status":"PASS", "issues":[], "verification_version":"v1"}] * 2)
    result = runtime.start(thread_id="GATE-REVISE", case_ref="CASE-001", initial_turn=user_turn(artifacts=[evidence.artifact_ref]))
    assert result.interrupt_payload.routing_reason == "CURRENCY_THRESHOLD_UNCONFIGURED"
    assert result.interrupt_payload.dossier.proposal_history[-1].revision_round == 1
    assert [r.verdict.value for r in result.interrupt_payload.dossier.review_history] == ["REVISE", "APPROVE"]
