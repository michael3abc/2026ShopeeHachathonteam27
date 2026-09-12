"""Fan resolved cases out to the independent memory-distillation stream."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol

from pydantic import TypeAdapter, ValidationError
from return_agent_contracts.models import MemoryDistillationInput
from return_agent_contracts.completion import RefundAppliedEvent
from return_agent_contracts.service import (
    AgentResolvedEvent,
    AgentServiceEvent,
    MemoryDistillationJob,
)

from .broker import BrokerMessage, MemoryEnqueueStreamBroker
from .memory_activity import MemoryActivityIdentity, background
from .memory_supervision import MemoryRetryPolicy

LOGGER = logging.getLogger(__name__)
EVENT_ADAPTER = TypeAdapter(AgentServiceEvent)


class MemoryDistillationInputProvider(Protocol):
    async def aget_memory_distillation_input(
        self, *, thread_id: str
    ) -> MemoryDistillationInput | None: ...


class MemoryEnqueueWorker:
    """Consume durable terminal events without delaying customer resolution."""

    def __init__(
        self,
        *,
        input_provider: MemoryDistillationInputProvider,
        broker: MemoryEnqueueStreamBroker,
        consumer_name: str,
        clock: Callable[[], datetime] | None = None,
        block_ms: int = 1_000,
        reclaim_idle_ms: int = 60_000,
        retry_policy: MemoryRetryPolicy | None = None,
        activity_sink=None,
        completion_store=None,
    ) -> None:
        if not consumer_name.strip():
            raise ValueError("consumer_name must be non-empty")
        if block_ms < 1 or reclaim_idle_ms < 1:
            raise ValueError("Redis timing values must be positive")
        self._input_provider = input_provider
        self._broker = broker
        self._consumer_name = consumer_name
        self._clock = clock or (lambda: datetime.now(UTC))
        self._block_ms = block_ms
        self._reclaim_idle_ms = reclaim_idle_ms
        self._retry_policy = retry_policy or MemoryRetryPolicy()
        self._activity_sink = activity_sink
        self._completion_store = completion_store

    async def _initialize(self):
        await self._broker.ensure_memory_enqueue_consumer_group()
        if self._completion_store is not None:
            await self._broker.ensure_completion_group()

    async def run_forever(self, stop: asyncio.Event) -> None:
        await self._retry_policy.run(
            stop=stop,
            initialize=self._initialize,
            run_once=self.run_once,
            worker_name="memory-enqueue-worker",
        )

    async def run_once(self) -> bool:
        if self._completion_store is not None:
            completion = await self._broker.read_completion(consumer_name=self._consumer_name,reclaim_idle_ms=self._reclaim_idle_ms)
            if completion is not None:
                event = RefundAppliedEvent.model_validate_json(completion.body)
                await asyncio.to_thread(self._completion_store.applied,event)
                await self._broker.acknowledge_completion(completion.message_id)
            job = await asyncio.to_thread(self._completion_store.next_job)
            if job is not None:
                await self._broker.publish_memory_job(job)
                await asyncio.to_thread(self._completion_store.published,job)
                return True
        message = await self._broker.read_agent_event_for_memory(
            consumer_name=self._consumer_name,
            block_ms=self._block_ms,
            reclaim_idle_ms=self._reclaim_idle_ms,
        )
        if message is None:
            return False
        event = self._parse_event(message)
        if event is None or not isinstance(event, AgentResolvedEvent):
            await self._broker.acknowledge_agent_event_for_memory(message.message_id)
            return True

        identity = MemoryActivityIdentity(event.case_ref, event.command_id,
            f"memory:{event.payload.result.resolution_handoff.handoff_id}")
        try:
            input_ = await self._input_provider.aget_memory_distillation_input(
                thread_id=event.thread_id
            )
        except Exception:
            background(self._activity_sink, identity, "RETRYING", "MEMORY_ENQUEUE_UNAVAILABLE")
            raise
        if input_ is not None:
            handoff_id = event.payload.result.resolution_handoff.handoff_id
            if input_.case_context.policy_schema_version == "v2" and input_.final_resolution.final_decision.action == "FULL_REFUND":
                if self._completion_store is None:
                    raise RuntimeError("v2 memory requires durable payment completion join")
                if input_.final_resolution != event.payload.result.resolution_handoff:
                    raise ValueError("correction trace resolution mismatch")
                job = MemoryDistillationJob(job_id=f"memory:{handoff_id}",source_command_id=event.command_id,
                    case_ref=event.case_ref,thread_id=event.thread_id,issued_at=self._utc_now(),payload={"input":input_})
                await asyncio.to_thread(self._completion_store.correction,job)
                await self._broker.acknowledge_agent_event_for_memory(message.message_id)
                return True
            await self._broker.publish_memory_job(
                MemoryDistillationJob(
                    job_id=f"memory:{handoff_id}",
                    source_command_id=event.command_id,
                    case_ref=event.case_ref,
                    thread_id=event.thread_id,
                    issued_at=self._utc_now(),
                    payload={"input": input_},
                )
            )
        background(self._activity_sink, identity,
            "SCHEDULED" if input_ is not None else "SKIPPED")
        await self._broker.acknowledge_agent_event_for_memory(message.message_id)
        return True

    @staticmethod
    def _parse_event(message: BrokerMessage) -> AgentServiceEvent | None:
        try:
            return EVENT_ADAPTER.validate_python(json.loads(message.body))
        except (json.JSONDecodeError, ValidationError, TypeError, ValueError):
            LOGGER.exception(
                "invalid Agent event %s cannot produce a memory job",
                message.message_id,
            )
            return None

    def _utc_now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value):
            raise ValueError("memory enqueue worker clock must return UTC")
        return value.astimezone(UTC)
