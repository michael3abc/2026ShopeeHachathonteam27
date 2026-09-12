from __future__ import annotations

import json
from collections import deque
from datetime import UTC, datetime

import pytest
from return_agent_contracts.enums import ReasonCode
from return_agent_contracts.models import UserTurn
from return_agent_contracts.runtime import ManualEscalationAgentRunResult
from return_agent_contracts.service import (
    AgentCommandDeadLetter,
    AgentResumeCommand,
    AgentServiceEvent,
    AgentStartCommand,
)
from return_agent_service.broker import BrokerMessage
from return_agent_service.demo import create_demo_runtime
from return_agent_service.journal import CommandClaim, InMemoryCommandJournal
from return_agent_service.worker import AgentWorker

TIME = datetime(2026, 9, 6, 12, 0, tzinfo=UTC)


def _command(command_id: str = "COMMAND-001") -> AgentStartCommand:
    return AgentStartCommand(
        command_type="START",
        command_id=command_id,
        case_ref="CASE-DEMO",
        thread_id=f"THREAD-{command_id}",
        issued_at=TIME,
        payload={
            "order_ref": "ORDER-DEMO",
            "initial_turn": UserTurn(
                turn_id="TURN-DEMO",
                role="USER",
                text="ORDER-DEMO 的喇叭到貨時損壞",
                attached_artifact_refs=["artifact://demo/damage"],
                received_at=TIME,
            )
        },
    )


class FakeBroker:
    def __init__(self, *bodies: str) -> None:
        self.messages = deque(
            BrokerMessage(message_id=f"1-{index}", body=body)
            for index, body in enumerate(bodies, start=1)
        )
        self.events: list[AgentServiceEvent] = []
        self.dead_letters: list[AgentCommandDeadLetter] = []
        self.acks: list[str] = []
        self.fail_event_publication = False

    async def ensure_consumer_group(self) -> None:
        return None

    async def read_command(self, **_kwargs) -> BrokerMessage | None:
        return self.messages.popleft() if self.messages else None

    async def publish_event(self, event: AgentServiceEvent) -> str:
        if self.fail_event_publication:
            raise ConnectionError("Redis unavailable")
        self.events.append(event)
        return f"event-{len(self.events)}"

    async def publish_dead_letter(self, dead_letter: AgentCommandDeadLetter) -> str:
        self.dead_letters.append(dead_letter)
        return "dlq-1"

    async def acknowledge(self, message_id: str) -> None:
        self.acks.append(message_id)

    async def ping(self) -> bool:
        return True

    async def close(self) -> None:
        return None


class FailingRuntime:
    async def astart(self, **_kwargs):
        raise RuntimeError("provider failed")

    async def aresume(self, **_kwargs):
        raise RuntimeError("provider failed")


class ResumeRuntime:
    def __init__(self) -> None:
        self.payload = None

    async def astart(self, **_kwargs):
        raise AssertionError("start must not be called")

    async def aresume(self, *, payload, **_kwargs):
        self.payload = payload
        return ManualEscalationAgentRunResult(
            result_type="MANUAL_ESCALATION",
            status="COMPLETED",
            manual_escalation={
                "case_ref": "CASE-DEMO",
                "thread_id": "THREAD-RESUME",
                "escalation_reason": "CONTRACT_VIOLATION",
                "accumulated_context": {
                    "clarification_round": 0,
                    "evidence_round": 0,
                    "verification_round": 0,
                    "revision_round": 0,
                    "review_history_refs": [],
                    "verification_issues": [],
                },
                "created_at": TIME,
            },
        )


@pytest.mark.asyncio
async def test_worker_runs_real_demo_graph_and_emits_terminal_event() -> None:
    command = _command()
    broker = FakeBroker(command.model_dump_json())
    worker = AgentWorker(
        runtime=create_demo_runtime(),
        broker=broker,
        journal=InMemoryCommandJournal(),
        consumer_name="test-worker",
        clock=lambda: TIME,
    )

    assert await worker.run_once() is True
    assert broker.acks == ["1-1"]
    assert [event.event_index for event in broker.events] == list(
        range(1, len(broker.events) + 1)
    )
    memory_events = [event.payload.observation.memory_retrieval for event in broker.events
                     if event.event_type == "NODE_OBSERVED" and event.payload.observation.memory_retrieval is not None]
    assert len(memory_events) == 1
    assert memory_events[0].status == "OK"
    assert memory_events[0].query_summary and memory_events[0].hits == []
    assert broker.events[-1].event_type == "RESOLVED"
    assert (
        broker.events[-1].payload.result.resolution_handoff.final_decision.amount
        == 1200
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "reason_code", [ReasonCode.CHANGED_MIND, ReasonCode.ITEM_DAMAGED]
)
async def test_demo_scenarios_support_repeated_independent_cases(
    reason_code: ReasonCode,
) -> None:
    commands = [_command(f"COMMAND-REPEAT-{index}") for index in range(2)]
    if reason_code is ReasonCode.CHANGED_MIND:
        for command in commands:
            command.payload.initial_turn.attached_artifact_refs = []
            command.payload.initial_turn.text = "ORDER-DEMO 的喇叭不想要了"
    broker = FakeBroker(*(command.model_dump_json() for command in commands))
    worker = AgentWorker(
        runtime=create_demo_runtime(reason_code=reason_code),
        broker=broker,
        journal=InMemoryCommandJournal(),
        consumer_name="test-worker",
        clock=lambda: TIME,
    )
    for _ in commands:
        assert await worker.run_once() is True
        terminal = broker.events[-1]
        assert terminal.event_type == "RESOLVED"
        assert (
            terminal.payload.result.resolution_handoff.final_decision.action
            == "FULL_REFUND"
        )
    assert broker.acks == ["1-1", "1-2"]


@pytest.mark.asyncio
async def test_invalid_command_is_dead_lettered_before_ack() -> None:
    broker = FakeBroker(json.dumps({"command_type": "START"}))
    worker = AgentWorker(
        runtime=create_demo_runtime(),
        broker=broker,
        journal=InMemoryCommandJournal(),
        consumer_name="test-worker",
        clock=lambda: TIME,
    )

    assert await worker.run_once() is True
    assert broker.dead_letters[0].error_code == "INVALID_AGENT_COMMAND"
    assert broker.acks == ["1-1"]


@pytest.mark.asyncio
async def test_duplicate_terminal_command_is_acked_without_rerun() -> None:
    command = _command()
    broker = FakeBroker(command.model_dump_json(), command.model_dump_json())
    journal = InMemoryCommandJournal()
    worker = AgentWorker(
        runtime=create_demo_runtime(),
        broker=broker,
        journal=journal,
        consumer_name="test-worker",
        clock=lambda: TIME,
    )

    await worker.run_once()
    event_count = len(broker.events)
    await worker.run_once()
    assert len(broker.events) == event_count
    assert broker.acks == ["1-1", "1-2"]


@pytest.mark.asyncio
async def test_busy_command_is_not_acked() -> None:
    command = _command()
    broker = FakeBroker(command.model_dump_json())
    journal = InMemoryCommandJournal()
    assert await journal.claim(command.command_id) is CommandClaim.CLAIMED
    worker = AgentWorker(
        runtime=create_demo_runtime(),
        broker=broker,
        journal=journal,
        consumer_name="test-worker",
        clock=lambda: TIME,
    )

    assert await worker.run_once() is False
    assert broker.acks == []


@pytest.mark.asyncio
async def test_event_publish_failure_does_not_ack_and_releases_claim() -> None:
    command = _command()
    broker = FakeBroker(command.model_dump_json())
    broker.fail_event_publication = True
    journal = InMemoryCommandJournal()
    worker = AgentWorker(
        runtime=create_demo_runtime(),
        broker=broker,
        journal=journal,
        consumer_name="test-worker",
        clock=lambda: TIME,
    )

    with pytest.raises(ConnectionError):
        await worker.run_once()
    assert broker.acks == []
    assert await journal.claim(command.command_id) is CommandClaim.CLAIMED


@pytest.mark.asyncio
async def test_runtime_failure_emits_typed_failure_before_ack() -> None:
    command = _command()
    broker = FakeBroker(command.model_dump_json())
    worker = AgentWorker(
        runtime=FailingRuntime(),
        broker=broker,
        journal=InMemoryCommandJournal(),
        consumer_name="test-worker",
        clock=lambda: TIME,
    )

    assert await worker.run_once() is True
    assert broker.events[-1].event_type == "RUN_FAILED"
    assert broker.events[-1].payload.retryable is False
    assert broker.acks == ["1-1"]


@pytest.mark.asyncio
async def test_worker_routes_resume_command_to_runtime_aresume() -> None:
    runtime = ResumeRuntime()
    command = AgentResumeCommand(
        command_type="RESUME",
        command_id="COMMAND-RESUME",
        case_ref="CASE-DEMO",
        thread_id="THREAD-RESUME",
        issued_at=TIME,
        payload={"resume": {"kind": "HUMAN_REVIEW"}},
    )
    broker = FakeBroker(command.model_dump_json())
    worker = AgentWorker(
        runtime=runtime,
        broker=broker,
        journal=InMemoryCommandJournal(),
        consumer_name="test-worker",
        clock=lambda: TIME,
    )

    assert await worker.run_once() is True
    assert runtime.payload.kind == "HUMAN_REVIEW"
    assert broker.events[-1].event_type == "ESCALATED"
    assert broker.acks == ["1-1"]
