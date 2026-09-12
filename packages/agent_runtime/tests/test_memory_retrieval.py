from __future__ import annotations

import pytest
from return_agent_contracts.models import ApprovedMemory, MemorySearchHit
from return_agent_contracts.review_gates import ReviewerGateConfig
from return_agent_contracts.runtime import EvidenceResume
from return_agent_runtime.model import ModelTask

from .conftest import (
    TIME,
    approved_review,
    evidence_item,
    make_runtime,
    proposal_output,
    supported_assessment,
    user_turn,
)
from .fakes import QueuedModel
from .test_interrupt_resume import complete_intake, insufficient_assessment


def _hits():
    return [
        MemorySearchHit(
            memory=ApprovedMemory(
                memory_id=name,
                retrieval_summary="Packaging inspection; compare visible damage.",
                status="APPROVED",
                recommended_behavior="Compare visible packaging and damage.",
                trigger_conditions=["Current evidence shows the packaging."],
                policy_version="POLICY-12:v3",
                claim_registry_version="claim-registry:1.0",
                scope={"market": "TW"},
                confidence=confidence,
                approved_at=TIME,
            ),
            similarity=score,
        )
        for name, confidence, score in [
            ("MEM-RELEVANT", 0.1, 0.91),
            ("MEM-CONFIDENT", 0.99, 0.72),
            ("MEM-THIRD", 0.8, 0.41),
        ]
    ]


@pytest.mark.asyncio
async def test_async_human_review_interrupt_projects_retrieved_memory_ids():
    model = QueuedModel()
    model.queue(ModelTask.INTAKE, complete_intake())
    model.queue(ModelTask.ASSESS, supported_assessment())
    model.queue(ModelTask.PROPOSE_OR_REVISE, proposal_output())
    model.queue(ModelTask.REVIEW, approved_review())
    evidence = evidence_item()
    runtime, _ = make_runtime(
        model=model,
        memory_results=_hits(),
        evidence_items={evidence.artifact_ref: evidence},
        reviewer_gate_config=ReviewerGateConfig(thresholds={"TWD": "1"}),
    )

    result = await runtime.astart(
        thread_id="THREAD-MEMORY-HUMAN-REVIEW",
        case_ref="CASE-001",
        initial_turn=user_turn(artifacts=[evidence.artifact_ref]),
    )

    assert result.interrupt_payload.routing_reason == "HIGH_VALUE_ITEM"
    assert result.interrupt_payload.memory_ids == [
        hit.memory.memory_id for hit in _hits()
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("resumed_result", ["empty", "unavailable", "summary_failure"])
async def test_summary_and_scored_hits_replace_on_resume(resumed_result):
    model = QueuedModel()
    model.queue(ModelTask.INTAKE, complete_intake())
    model.queue(
        ModelTask.MEMORY_QUERY_SUMMARY,
        {"query_summary": "Buyer reports damaged speaker."},
        {}
        if resumed_result == "summary_failure"
        else {"query_summary": "Photo shows speaker and carton damage."},
    )
    model.queue(ModelTask.ASSESS, insufficient_assessment(), supported_assessment())
    model.queue(ModelTask.PROPOSE_OR_REVISE, proposal_output())
    model.queue(ModelTask.REVIEW, approved_review())
    evidence = evidence_item()
    runtime, providers = make_runtime(
        model=model,
        memory_results=_hits(),
        evidence_items={evidence.artifact_ref: evidence},
    )
    observations = []
    await runtime.astart(
        thread_id="THREAD-MEMORY",
        case_ref="CASE-001",
        initial_turn=user_turn(),
        observer=observations.append,
    )
    first = [item.memory_retrieval for item in observations if item.memory_retrieval][
        -1
    ]
    assert first.hits == _hits()
    assess = next(call for call in model.calls if call.task is ModelTask.ASSESS)
    assert [m["memory_id"] for m in assess.payload["operational_memory"]] == [
        hit.memory.memory_id for hit in _hits()
    ]
    providers["memory"].results = (
        ConnectionError("VDB down") if resumed_result == "unavailable" else []
    )
    await runtime.aresume(
        thread_id="THREAD-MEMORY",
        payload=EvidenceResume(
            kind="EVIDENCE_REQUEST", artifact_refs=[evidence.artifact_ref]
        ),
        observer=observations.append,
    )
    result = [item.memory_retrieval for item in observations if item.memory_retrieval][
        -1
    ]
    assert result.hits == []
    assert result.status == ("OK" if resumed_result == "empty" else "UNAVAILABLE")
    summary_calls = [c for c in model.calls if c.task is ModelTask.MEMORY_QUERY_SUMMARY]
    assert len(summary_calls) == 2
    assert not summary_calls[0].payload["evidence"]
    assert (
        summary_calls[1].payload["evidence"][0]["summary"] == evidence.extracted_summary
    )
    assert providers["evidence"].calls == [evidence.artifact_ref]
    for call in summary_calls:
        assert "operational_memory" not in call.payload
        assert "artifact_ref" not in str(call.payload)
        assert "policy_bundle" not in call.payload
    reviewer = next(c for c in model.calls if c.task is ModelTask.REVIEW)
    assert "operational_memory" not in reviewer.payload
    last_assess = [c for c in model.calls if c.task is ModelTask.ASSESS][-1]
    assert last_assess.payload["operational_memory"] == []


def test_initial_attachment_is_resolved_before_summary_and_failure_stays_closed():
    for resolved in [evidence_item(), RuntimeError("unreadable attachment")]:
        model = QueuedModel()
        model.queue(ModelTask.INTAKE, complete_intake())
        model.queue(ModelTask.ASSESS, supported_assessment())
        model.queue(ModelTask.PROPOSE_OR_REVISE, proposal_output())
        model.queue(ModelTask.REVIEW, approved_review())
        evidence = evidence_item()
        runtime, providers = make_runtime(
            model=model, evidence_items={evidence.artifact_ref: resolved}
        )
        result = runtime.start(
            thread_id="THREAD-INITIAL",
            case_ref="CASE-001",
            initial_turn=user_turn(artifacts=[evidence.artifact_ref]),
        )
        summaries = [c for c in model.calls if c.task is ModelTask.MEMORY_QUERY_SUMMARY]
        assert providers["evidence"].calls == [evidence.artifact_ref]
        if isinstance(resolved, Exception):
            assert not summaries and result.manual_escalation is not None
        else:
            assert len(summaries) == 1
            assert (
                summaries[0].payload["evidence"][0]["summary"]
                == evidence.extracted_summary
            )


@pytest.mark.parametrize(
    "summary",
    ["See https://example.com/private", "Email buyer@example.com", "x" * 2001],
)
def test_invalid_query_summary_clears_memory_without_querying(summary):
    model = QueuedModel()
    model.queue(ModelTask.INTAKE, complete_intake())
    model.queue(ModelTask.MEMORY_QUERY_SUMMARY, {"query_summary": summary})
    model.queue(ModelTask.ASSESS, insufficient_assessment())
    runtime, providers = make_runtime(model=model, memory_results=_hits())
    runtime.start(
        thread_id="THREAD-INVALID", case_ref="CASE-001", initial_turn=user_turn()
    )
    assert not providers["memory"].query_calls
    state = runtime.graph.get_state(
        {"configurable": {"thread_id": "THREAD-INVALID"}}
    ).values
    assert state["memory_retrieval"].error_code == "SUMMARY_UNAVAILABLE"
    assert state["operational_memory"] == []
