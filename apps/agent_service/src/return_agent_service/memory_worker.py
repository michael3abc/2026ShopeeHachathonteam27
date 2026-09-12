"""Independent Redis worker for non-blocking operational-memory distillation."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol
from uuid import uuid4

from pydantic import TypeAdapter, ValidationError
from return_agent_contracts.interfaces import OperationalMemoryStore
from return_agent_contracts.models import (
    MemoryCandidateOutput,
    MemoryDistillationInput,
    MemoryDistillationOutput,
)
from return_agent_contracts.service import (
    MEMORY_JOB_STREAM,
    MemoryDistillationCompletedEvent,
    MemoryDistillationFailedEvent,
    MemoryDistillationJob,
    MemoryJobDeadLetter,
    MemoryServiceEvent,
)

from .broker import BrokerMessage, MemoryStreamBroker
from .journal import CommandClaim, CommandJournal
from .memory_activity import MEMORY_ATTEMPT, background, execute_memory_step
from .memory_replay import SqlAlchemyMemoryReplayStore
from .memory_supervision import MemoryRetryPolicy, is_transient_transport_error

LOGGER = logging.getLogger(__name__)
JOB_ADAPTER = TypeAdapter(MemoryDistillationJob)


class OperationalMemoryDistiller(Protocol):
    prompt_version: str

    def distill(self, input_: MemoryDistillationInput) -> MemoryDistillationOutput: ...


class MemoryWorker:
    def __init__(
        self,
        *,
        distiller: OperationalMemoryDistiller,
        store: OperationalMemoryStore,
        broker: MemoryStreamBroker,
        journal: CommandJournal,
        replay_store: SqlAlchemyMemoryReplayStore,
        consumer_name: str,
        clock: Callable[[], datetime] | None = None,
        block_ms: int = 1_000,
        reclaim_idle_ms: int = 60_000,
        retry_policy: MemoryRetryPolicy | None = None,
        activity_sink=None,
    ) -> None:
        if not consumer_name.strip():
            raise ValueError("consumer_name must be non-empty")
        if block_ms < 1 or reclaim_idle_ms < 1:
            raise ValueError("Redis timing values must be positive")
        self._distiller = distiller
        self._store = store
        self._broker = broker
        self._journal = journal
        self._replay_store = replay_store
        self._consumer_name = consumer_name
        self._clock = clock or (lambda: datetime.now(UTC))
        self._block_ms = block_ms
        self._reclaim_idle_ms = reclaim_idle_ms
        self._retry_policy = retry_policy or MemoryRetryPolicy()
        self._activity_sink = activity_sink

    async def run_forever(self, stop: asyncio.Event) -> None:
        await self._retry_policy.run(
            stop=stop,
            initialize=self._broker.ensure_memory_consumer_group,
            run_once=self.run_once,
            worker_name="memory-worker",
        )

    async def run_once(self) -> bool:
        message = await self._broker.read_memory_job(
            consumer_name=self._consumer_name,
            block_ms=self._block_ms,
            reclaim_idle_ms=self._reclaim_idle_ms,
        )
        if message is None:
            return False
        job = await self._parse_or_dead_letter(message)
        if job is None:
            return True
        claim = await self._journal.claim(job.job_id)
        if claim is CommandClaim.TERMINAL:
            await self._broker.acknowledge_memory_job(message.message_id)
            return True
        if claim is CommandClaim.BUSY:
            return False
        attempt_token = MEMORY_ATTEMPT.set(uuid4().hex)
        background(self._activity_sink, job, "STARTED")
        try:
            await self._execute(message, job)
        except Exception:
            background(self._activity_sink, job, "RETRYING", "MEMORY_RETRY_PENDING")
            await self._journal.abandon(job.job_id)
            raise
        finally:
            MEMORY_ATTEMPT.reset(attempt_token)
        return True

    async def _parse_or_dead_letter(
        self, message: BrokerMessage
    ) -> MemoryDistillationJob | None:
        try:
            return JOB_ADAPTER.validate_python(json.loads(message.body))
        except (json.JSONDecodeError, ValidationError, TypeError, ValueError) as error:
            dead_letter = MemoryJobDeadLetter(
                source_stream=MEMORY_JOB_STREAM,
                source_message_id=message.message_id,
                raw_body=message.body,
                error_code="INVALID_MEMORY_JOB",
                error_message=f"{type(error).__name__}: {error}",
                failed_at=self._utc_now(),
            )
            await self._broker.publish_memory_dead_letter(dead_letter)
            await self._broker.acknowledge_memory_job(message.message_id)
            return None

    async def _execute(
        self, message: BrokerMessage, job: MemoryDistillationJob
    ) -> None:
        replay = await self._replay_store.load(job, self._distiller.prompt_version,
            getattr(self._distiller, "model_profile", None))
        if replay.terminal_event is not None:
            await self._publish_terminal(message, job, replay.terminal_event)
            return
        result = replay.result
        if result is None:
            try:
                result = await asyncio.to_thread(
                    self._activity_step, job, "distill_memory", self._distiller.distill, job.payload.input
                )
            except Exception as error:
                LOGGER.exception("memory model failed for job %s", job.job_id)
                await self._record_failure(message, job, error, replay.prompt_version)
                return
            # A storage failure must escape before any external submission.
            replay = await self._replay_store.save_result(job, result)
            result = replay.result

        try:
            submission_ref = None
            if isinstance(result, MemoryCandidateOutput):
                submission_ref = await asyncio.to_thread(
                    self._activity_step, job, "submit_candidate", self._store.submit_candidate, result.candidate
                )
        except Exception as error:
            if is_transient_transport_error(error):
                # The result is already durable, and submit_candidate is
                # idempotent for this exact payload, including unknown outcomes.
                raise
            LOGGER.exception("memory submission failed for job %s", job.job_id)
            await self._record_failure(message, job, error, replay.prompt_version)
            return

        event = MemoryDistillationCompletedEvent(
            event_type="COMPLETED",
            event_id=f"memory-event-v2:{job.job_id}:completed",
            job_id=job.job_id,
            source_command_id=job.source_command_id,
            case_ref=job.case_ref,
            thread_id=job.thread_id,
            occurred_at=self._utc_now(),
            payload={
                "result": result,
                "submission_ref": submission_ref,
                "distiller_prompt_version": replay.prompt_version,
            },
        )
        replay = await self._replay_store.save_event(job, event)
        if replay.terminal_event is None:
            raise RuntimeError("memory terminal event was not persisted")
        await self._publish_terminal(message, job, replay.terminal_event)

    async def _record_failure(
        self,
        message: BrokerMessage,
        job: MemoryDistillationJob,
        error: Exception,
        prompt_version: str,
    ) -> None:
        error_type = type(error).__name__
        LOGGER.error("memory job %s failed (%s)", job.job_id, error_type)
        event = MemoryDistillationFailedEvent(
            event_type="FAILED",
            event_id=f"memory-event-v2:{job.job_id}:failed",
            job_id=job.job_id,
            source_command_id=job.source_command_id,
            case_ref=job.case_ref,
            thread_id=job.thread_id,
            occurred_at=self._utc_now(),
            payload={
                "code": "MEMORY_DISTILLATION_FAILED",
                "message": f"{error_type}: operational memory processing failed; "
                "inspect restricted service telemetry",
                "retryable": False,
                "distiller_prompt_version": prompt_version,
            },
        )
        replay = await self._replay_store.save_event(job, event)
        if replay.terminal_event is None:
            raise RuntimeError("memory terminal event was not persisted")
        await self._publish_terminal(message, job, replay.terminal_event)

    async def _publish_terminal(
        self,
        message: BrokerMessage,
        job: MemoryDistillationJob,
        event: MemoryServiceEvent,
    ) -> None:
        await self._broker.publish_memory_event(event)
        if isinstance(event, MemoryDistillationFailedEvent):
            background(self._activity_sink, job, "FAILED", "MEMORY_FAILED")
        else:
            background(self._activity_sink, job, "COMPLETED" if event.payload.submission_ref else "SKIPPED")
        if isinstance(event, MemoryDistillationFailedEvent):
            await self._journal.fail(job.job_id)
        else:
            await self._journal.complete(job.job_id)
        await self._broker.acknowledge_memory_job(message.message_id)

    def _utc_now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value):
            raise ValueError("memory worker clock must return UTC")
        return value.astimezone(UTC)

    def _activity_step(self, job, node, function, *args):
        return execute_memory_step(self._activity_sink, job, node, function, *args)
