import asyncio
from threading import Event

import pytest
from return_agent_contracts.activity import Lifecycle, NodeSummary
from return_agent_contracts.models import ApprovedHumanReviewResult
from return_agent_contracts.review_gates import ReviewerGateConfig
from return_agent_contracts.runtime import HumanReviewPollResume
from return_agent_runtime.model import ModelTask

from .conftest import (
    TIME,
    approved_review,
    evidence_item,
    make_runtime,
    proposal_output,
    user_turn,
)
from .fakes import QueuedModel
from .test_revision_and_failures import queue_initial_resolution, revised_review


@pytest.mark.asyncio
async def test_model_start_is_observable_while_call_is_blocked():
    release = Event()

    class BlockedModel(QueuedModel):
        def generate(self, **kwargs):
            if kwargs["task"] == ModelTask.INTAKE:
                assert release.wait(5)
            return super().generate(**kwargs)

    model = BlockedModel()
    queue_initial_resolution(model)
    model.queue(ModelTask.REVIEW, approved_review())
    evidence = evidence_item()
    runtime, _ = make_runtime(
        model=model, evidence_items={evidence.artifact_ref: evidence}
    )
    events = []
    started = asyncio.Event()

    def observe(event):
        events.append(event)
        if (
            isinstance(event.payload, Lifecycle)
            and event.payload.type == "model"
            and event.payload.phase == "STARTED"
        ):
            started.set()

    task = asyncio.create_task(
        runtime.astart(
            thread_id="TRACE-BLOCK",
            case_ref="CASE-001",
            initial_turn=user_turn(artifacts=[evidence.artifact_ref]),
            activity_observer=observe,
            run_id="COMMAND-1",
        )
    )
    try:
        await asyncio.wait_for(started.wait(), 3)
        assert not task.done()
        assert not any(isinstance(e.payload, NodeSummary) for e in events)
    finally:
        release.set()
        result = await task
    assert result.status.value == "COMPLETED"
    completed = {
        (e.node, e.operation_id)
        for e in events
        if isinstance(e.payload, Lifecycle)
        and e.payload.type == "node"
        and e.payload.phase == "COMPLETED"
    }
    summaries = {
        (e.node, e.operation_id) for e in events if isinstance(e.payload, NodeSummary)
    }
    assert completed == summaries
    assert all(e.run_id == "COMMAND-1" for e in events)
    intent_summaries = [e for e in events if isinstance(e.payload, NodeSummary) and e.payload.intent_display]
    assert intent_summaries
    assert all(e.node in {"parse_request", "load_case_context"} for e in intent_summaries)
    assert intent_summaries[0].payload.intent_display.requested_action
    assert sum(call.task == ModelTask.INTAKE for call in model.calls) == 1
    assert "artifact://" not in str([e.model_dump_json() for e in events])
    assert any(e.payload.type == "tool" for e in events)


@pytest.mark.asyncio
async def test_revise_gate_pause_resume_and_attempt_identity():
    model = QueuedModel()
    queue_initial_resolution(model)
    model.queue(
        ModelTask.PROPOSE_OR_REVISE,
        proposal_output(rationale="Reviewer feedback applied."),
    )
    model.queue(ModelTask.REVIEW, revised_review(), approved_review())
    evidence = evidence_item()
    runtime, _ = make_runtime(
        model=model,
        evidence_items={evidence.artifact_ref: evidence},
        reviewer_gate_config=ReviewerGateConfig(thresholds={"TWD": "1"}),
        verification_results=[
            {"status": "PASS", "issues": [], "verification_version": "v1"}
        ]
        * 2,
        human_results=[
            None,
            ApprovedHumanReviewResult(
                decision="APPROVE",
                review_note="Authorized.",
                final_resolution_ref="RES-1",
                reviewed_at=TIME,
            ),
        ],
    )
    events = []
    result = await runtime.astart(
        thread_id="TRACE-GATE",
        case_ref="CASE-001",
        initial_turn=user_turn(artifacts=[evidence.artifact_ref]),
        activity_observer=events.append,
    )
    assert result.interrupt_payload.routing_reason == "HIGH_VALUE_ITEM"
    reviewers = [
        e for e in events if e.node == "reviewer" and isinstance(e.payload, NodeSummary)
    ]
    assert [e.payload.facts.verdict for e in reviewers] == ["REVISE", "APPROVE"]
    assert reviewers[0].payload.review_gate is None
    assert reviewers[1].payload.review_gate.status == "HUMAN_REQUIRED"
    assert len({e.attempt_id for e in reviewers}) == 2
    paused = [
        e
        for e in events
        if isinstance(e.payload, Lifecycle) and e.payload.phase == "PAUSED"
    ]
    assert paused and paused[0].node == "await_human_review"
    assert not any(
        e.operation_id == paused[0].operation_id and isinstance(e.payload, NodeSummary)
        for e in events
    )
    resumed = []
    await runtime.aresume(
        thread_id="TRACE-GATE",
        payload=HumanReviewPollResume(kind="HUMAN_REVIEW"),
        activity_observer=resumed.append,
    )
    assert not any(e.node == "reviewer" for e in resumed)
    assert resumed[0].attempt_id != paused[0].attempt_id


@pytest.mark.asyncio
async def test_broken_activity_sink_does_not_change_resolution(happy_runtime):
    runtime, _, _ = happy_runtime

    def fail(_event):
        raise ConnectionError("private diagnostic")

    result = await runtime.astart(
        thread_id="TRACE-SINK-FAIL",
        case_ref="CASE-001",
        initial_turn=user_turn(artifacts=[evidence_item().artifact_ref]),
        activity_observer=fail,
    )
    assert result.status.value == "COMPLETED"
