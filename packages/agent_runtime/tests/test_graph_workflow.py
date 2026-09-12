import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from return_agent_contracts.enums import OutcomeSource
from return_agent_contracts.runtime import AgentRunStatus

from .conftest import user_turn


def test_happy_path_emits_graph_derived_resolution(happy_runtime):
    runtime, _model, providers = happy_runtime

    result = runtime.start(
        thread_id="THREAD-001",
        case_ref="CASE-001",
        initial_turn=user_turn(artifacts=["artifact://evidence/EV-002"]),
    )

    assert result.status is AgentRunStatus.COMPLETED
    assert result.manual_escalation is None
    assert result.resolution_handoff is not None
    assert result.resolution_handoff.outcome_source is OutcomeSource.REVIEWER_APPROVE
    assert result.resolution_handoff.final_decision.amount == 1200
    assert result.resolution_handoff.final_decision.currency == "TWD"
    assert result.resolution_handoff.execution_blocked is False
    assert providers["evidence"].calls == ["artifact://evidence/EV-002"]
    assert len(providers["verification"].calls) == 1
    assert result.resolution_handoff.review_result.verdict == "APPROVE"

    state = runtime.graph.get_state(
        {"configurable": {"thread_id": "THREAD-001"}}
    ).values
    assert state["claimed_line_item_ids"] == ["LI-002"]
    assert state["normalized_intent"].claimed_line_item_ids == ["LI-002"]
    assert state["propose_round"] == 1


@pytest.mark.asyncio
async def test_observed_start_reports_node_enter_and_exit(happy_runtime):
    runtime, _model, _providers = happy_runtime
    observations = []

    result = await runtime.astart(
        thread_id="THREAD-OBSERVED",
        case_ref="CASE-001",
        initial_turn=user_turn(artifacts=["artifact://evidence/EV-002"]),
        observer=observations.append,
    )

    assert result.status is AgentRunStatus.COMPLETED
    assert observations[0].phase == "ENTER"
    assert observations[0].node == "parse_request"
    assert observations[-1].phase == "EXIT"
    assert observations[-1].node == "enqueue_memory_distillation"
    starts = {item.task_ref for item in observations if item.phase == "ENTER"}
    exits = {item.task_ref for item in observations if item.phase == "EXIT"}
    assert starts == exits


@pytest.mark.asyncio
async def test_observer_failure_does_not_change_graph_result(happy_runtime, caplog):
    runtime, _model, _providers = happy_runtime

    def broken_observer(_observation):
        raise RuntimeError("telemetry unavailable")

    result = await runtime.astart(
        thread_id="THREAD-BROKEN-OBSERVER",
        case_ref="CASE-001",
        initial_turn=user_turn(artifacts=["artifact://evidence/EV-002"]),
        observer=broken_observer,
    )

    assert result.status is AgentRunStatus.COMPLETED
    assert "node observer failed" in caplog.text
    state = runtime.graph.get_state({"configurable": {"thread_id": "THREAD-BROKEN-OBSERVER"}}).values
    assert state["learning_trace"].status == "COMPLETE"


@pytest.mark.asyncio
async def test_observed_run_reports_unhandled_task_error(happy_runtime):
    runtime, _model, _providers = happy_runtime

    def fail(_state):
        raise RuntimeError("boom")

    builder = StateGraph(dict)
    builder.add_node("parse_request", fail)
    builder.add_edge(START, "parse_request")
    builder.add_edge("parse_request", END)
    runtime.graph = builder.compile(checkpointer=InMemorySaver())
    observations = []

    with pytest.raises(RuntimeError, match="boom"):
        await runtime._ainvoke_observed(
            {},
            config=runtime._config("THREAD-ERROR"),
            observer=observations.append,
        )

    assert [item.phase.value for item in observations] == ["ENTER", "ERROR"]
    assert observations[-1].error_message == "RuntimeError: boom"
