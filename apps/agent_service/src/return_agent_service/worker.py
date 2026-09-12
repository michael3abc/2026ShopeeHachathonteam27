"""At-least-once Redis command worker for the Agent runtime."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Protocol

from pydantic import TypeAdapter, ValidationError
from return_agent_contracts.models import UserTurn
from return_agent_contracts.runtime import (
    AgentRunResult,
    InterruptedAgentRunResult,
    ManualEscalationAgentRunResult,
    NodeExecutionObservation,
    ResolutionAgentRunResult,
    ResumePayload,
)
from return_agent_contracts.service import (
    AGENT_COMMAND_STREAM,
    AgentCommand,
    AgentCommandDeadLetter,
    AgentEscalatedEvent,
    AgentInterruptedEvent,
    AgentNodeObservedEvent,
    AgentResolvedEvent,
    AgentResumeCommand,
    AgentRunFailedEvent,
    AgentServiceEvent,
    AgentStartCommand,
)

from .broker import AgentStreamBroker, BrokerMessage
from .journal import CommandClaim, CommandJournal

LOGGER = logging.getLogger(__name__)
COMMAND_ADAPTER = TypeAdapter(AgentCommand)

Clock = Callable[[], datetime]


class ObservableAgentRuntime(Protocol):
    async def astart(
        self,
        *,
        thread_id: str,
        case_ref: str,
        order_ref: str,
        initial_turn: UserTurn,
        observer: Callable[[NodeExecutionObservation], Awaitable[None] | None],
    ) -> AgentRunResult: ...

    async def aresume(
        self,
        *,
        thread_id: str,
        payload: ResumePayload,
        observer: Callable[[NodeExecutionObservation], Awaitable[None] | None],
    ) -> AgentRunResult: ...


class AgentWorker:
    def __init__(
        self,
        *,
        runtime: ObservableAgentRuntime,
        broker: AgentStreamBroker,
        journal: CommandJournal,
        consumer_name: str,
        clock: Clock | None = None,
        block_ms: int = 1_000,
        reclaim_idle_ms: int = 60_000,
        activity_sink=None,
    ) -> None:
        if not consumer_name.strip():
            raise ValueError("consumer_name must be non-empty")
        if block_ms < 1 or reclaim_idle_ms < 1:
            raise ValueError("Redis timing values must be positive")
        self._runtime = runtime
        self._broker = broker
        self._journal = journal
        self._consumer_name = consumer_name
        self._clock = clock or (lambda: datetime.now(UTC))
        self._block_ms = block_ms
        self._reclaim_idle_ms = reclaim_idle_ms
        self._activity_sink = activity_sink

    async def run_forever(self, stop: asyncio.Event) -> None:
        await self._broker.ensure_consumer_group()
        while not stop.is_set():
            await self.run_once()

    async def run_once(self) -> bool:
        message = await self._broker.read_command(
            consumer_name=self._consumer_name,
            block_ms=self._block_ms,
            reclaim_idle_ms=self._reclaim_idle_ms,
        )
        if message is None:
            return False
        command = await self._parse_or_dead_letter(message)
        if command is None:
            return True

        claim = await self._journal.claim(command.command_id)
        if claim is CommandClaim.TERMINAL:
            await self._broker.acknowledge(message.message_id)
            return True
        if claim is CommandClaim.BUSY:
            return False

        try:
            await self._execute(message, command)
        except Exception:
            await self._journal.abandon(command.command_id)
            raise
        return True

    async def _parse_or_dead_letter(
        self, message: BrokerMessage
    ) -> AgentCommand | None:
        try:
            raw = json.loads(message.body)
            return COMMAND_ADAPTER.validate_python(raw)
        except (json.JSONDecodeError, ValidationError, TypeError, ValueError) as error:
            dead_letter = AgentCommandDeadLetter(
                source_stream=AGENT_COMMAND_STREAM,
                source_message_id=message.message_id,
                raw_body=message.body,
                error_code="INVALID_AGENT_COMMAND",
                error_message=f"{type(error).__name__}: {error}",
                failed_at=self._utc_now(),
            )
            await self._broker.publish_dead_letter(dead_letter)
            await self._broker.acknowledge(message.message_id)
            return None

    async def _execute(
        self,
        message: BrokerMessage,
        command: AgentStartCommand | AgentResumeCommand,
    ) -> None:
        event_index = 0
        last_node: str | None = None
        observation_error: Exception | None = None

        async def observe(observation: NodeExecutionObservation) -> None:
            nonlocal event_index, last_node, observation_error
            event_index += 1
            last_node = observation.node.value
            event = AgentNodeObservedEvent(
                event_type="NODE_OBSERVED",
                event_id=self._event_id(command.command_id, event_index),
                command_id=command.command_id,
                case_ref=command.case_ref,
                thread_id=command.thread_id,
                event_index=event_index,
                occurred_at=self._utc_now(),
                payload={"observation": observation},
            )
            try:
                await self._broker.publish_event(event)
            except Exception as error:  # noqa: BLE001 - transport failure is recorded
                observation_error = observation_error or error

        try:
            if isinstance(command, AgentStartCommand):
                result = await self._runtime.astart(
                    thread_id=command.thread_id,
                    case_ref=command.case_ref,
                    order_ref=command.payload.order_ref,
                    initial_turn=command.payload.initial_turn,
                    observer=observe,
                    **({"activity_observer": self._activity_sink, "run_id": command.command_id} if self._activity_sink else {}),
                )
            else:
                result = await self._runtime.aresume(
                    thread_id=command.thread_id,
                    payload=command.payload.resume,
                    observer=observe,
                    **({"activity_observer": self._activity_sink, "run_id": command.command_id} if self._activity_sink else {}),
                )
        except Exception as error:
            if observation_error is not None:
                raise observation_error
            LOGGER.exception("Agent command %s failed", command.command_id)
            event_index += 1
            failure = AgentRunFailedEvent(
                event_type="RUN_FAILED",
                event_id=self._event_id(command.command_id, event_index),
                command_id=command.command_id,
                case_ref=command.case_ref,
                thread_id=command.thread_id,
                event_index=event_index,
                occurred_at=self._utc_now(),
                payload={
                    "code": "AGENT_RUN_FAILED",
                    "message": f"{type(error).__name__}: {error}",
                    "retryable": False,
                    "failed_node": last_node,
                },
            )
            await self._broker.publish_event(failure)
            await self._journal.fail(command.command_id)
            await self._broker.acknowledge(message.message_id)
            return

        if observation_error is not None:
            raise observation_error

        event_index += 1
        terminal = self._terminal_event(command, result, event_index)
        await self._broker.publish_event(terminal)
        await self._journal.complete(command.command_id)
        await self._broker.acknowledge(message.message_id)

    def _terminal_event(
        self,
        command: AgentStartCommand | AgentResumeCommand,
        result: AgentRunResult,
        event_index: int,
    ) -> AgentServiceEvent:
        common = {
            "event_id": self._event_id(command.command_id, event_index),
            "command_id": command.command_id,
            "case_ref": command.case_ref,
            "thread_id": command.thread_id,
            "event_index": event_index,
            "occurred_at": self._utc_now(),
        }
        if isinstance(result, InterruptedAgentRunResult):
            return AgentInterruptedEvent(
                event_type="INTERRUPTED",
                payload={"result": result},
                **common,
            )
        if isinstance(result, ResolutionAgentRunResult):
            return AgentResolvedEvent(
                event_type="RESOLVED",
                payload={"result": result},
                **common,
            )
        if isinstance(result, ManualEscalationAgentRunResult):
            return AgentEscalatedEvent(
                event_type="ESCALATED",
                payload={"result": result},
                **common,
            )
        raise TypeError(f"unsupported AgentRunResult: {type(result).__name__}")

    def _event_id(self, command_id: str, event_index: int) -> str:
        return f"event:{command_id}:{event_index}"

    def _utc_now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value):
            raise ValueError("Agent service clock must return UTC")
        return value.astimezone(UTC)
