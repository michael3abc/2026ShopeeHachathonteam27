"""Bounded telemetry delivery and asynchronous summary-only LLM narration."""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import UTC, datetime
from time import monotonic
from uuid import uuid4

from pydantic import Field, TypeAdapter
from redis.asyncio import Redis
from redis.exceptions import RedisError, ResponseError
from return_agent_contracts.activity import (
    ACTIVITY_STREAM,
    NARRATION_GROUP,
    NARRATION_STREAM,
    ActivityEmission,
    Lifecycle,
    Narration,
    NarrationJob,
)
from return_agent_contracts.activity_observer import safe_reference
from return_agent_contracts.base import ContractModel
from return_agent_runtime.model import ModelTask, OutputSchema, StructuredOutputModel

LOGGER = logging.getLogger(__name__)


class ActivityPublisher:
    def __init__(self, redis: Redis, capacity: int = 1024) -> None:
        if capacity < 1:
            raise ValueError("activity capacity must be positive")
        self.redis = redis
        self.queue: asyncio.Queue[ActivityEmission] = asyncio.Queue(maxsize=capacity)
        self.loop: asyncio.AbstractEventLoop | None = None
        self.failed = 0

    def submit(self, event: ActivityEmission) -> None:
        def enqueue():
            try:
                self.queue.put_nowait(event)
            except asyncio.QueueFull:
                self.failed += 1
                LOGGER.error("activity queue full; trace incomplete")

        if self.loop is None:
            try:
                self.loop = asyncio.get_running_loop()
            except RuntimeError:
                self.failed += 1
                LOGGER.error("activity publisher not started; trace incomplete")
                return
        self.loop.call_soon_threadsafe(enqueue)

    async def run_forever(self, stop: asyncio.Event) -> None:
        self.loop = asyncio.get_running_loop()
        while not stop.is_set():
            event = await self.queue.get()
            delay = 0.1
            while not stop.is_set():
                try:
                    await asyncio.wait_for(
                        self.redis.xadd(
                            ACTIVITY_STREAM, {"body": event.model_dump_json()}
                        ),
                        5,
                    )
                    break
                except asyncio.CancelledError:
                    raise
                except (RedisError, TimeoutError, OSError):
                    self.failed += 1
                    LOGGER.error("activity publish failed; retrying same event ID")
                    await asyncio.sleep(delay)
                    delay = min(5, delay * 2)
            self.queue.task_done()


class NarrationText(ContractModel):
    text: str = Field(min_length=1, max_length=600)


NARRATION_PROMPT = """你是內部案件操作紀錄的解說員。只依提供的 node 與已完成結果 facts，
用一至兩句繁體中文描述已完成的操作。不得推測原因、退款資格、未發生的下一步結果，
next_node 只表示選定的後續路由，只能說「下一步預計…」，不能說已進入、已轉交、
已送交、已啟動或完成下一節點。Reviewer APPROVE 不等於退款已執行。
不得加入資料中沒有的事實，不得輸出個資、URL、憑證或隱藏推理。只回傳 {text: ...}。"""


class NarrationWorker:
    def __init__(
        self,
        redis: Redis,
        model: StructuredOutputModel | None,
        *,
        timeout: float = 20.0,
        concurrency: int = 2,
    ) -> None:
        if timeout <= 0 or concurrency < 1 or concurrency > 16:
            raise ValueError("invalid narration worker bounds")
        self.redis, self.model = redis, model
        self.timeout, self.concurrency = timeout, concurrency
        self.consumer = "narrator-" + uuid4().hex

    async def setup(self) -> None:
        try:
            await self.redis.xgroup_create(
                NARRATION_STREAM, NARRATION_GROUP, id="0-0", mkstream=True
            )
        except ResponseError as error:
            if "BUSYGROUP" not in str(error):
                raise

    async def run_forever(self, stop: asyncio.Event) -> None:
        async def loop(slot):
            while not stop.is_set():
                try:
                    await self.setup()
                    await self.run_once(f"{self.consumer}:{slot}")
                except asyncio.CancelledError:
                    raise
                except Exception:  # noqa: BLE001 - worker boundary retains pending jobs
                    LOGGER.error("narration transport unavailable; retry pending job")
                    await asyncio.sleep(1)

        async with asyncio.TaskGroup() as group:
            for slot in range(self.concurrency):
                group.create_task(loop(slot))

    async def run_once(self, consumer: str = "narrator-test") -> bool:
        claimed = await self.redis.xautoclaim(
            NARRATION_STREAM,
            NARRATION_GROUP,
            consumer,
            min_idle_time=max(120000, int(self.timeout * 4000)),
            start_id="0-0",
            count=1,
        )
        entries = claimed[1]
        if not entries:
            batches = await self.redis.xreadgroup(
                NARRATION_GROUP, consumer, {NARRATION_STREAM: ">"}, count=1, block=100
            )
            entries = batches[0][1] if batches else []
        if not entries:
            return False
        message_id, fields = entries[0]
        try:
            job = NarrationJob.model_validate_json(fields["body"])
        except (ValueError, KeyError):
            await self.redis.xadd(
                NARRATION_STREAM + ".rejected",
                {"message_id": message_id, "code": "INVALID_NARRATION_JOB"},
            )
            await self.redis.xack(NARRATION_STREAM, NARRATION_GROUP, message_id)
            return True
        key = "activity-narration-result:" + job.job_id
        cached = await self.redis.get(key)
        if cached:
            await self.redis.xadd(ACTIVITY_STREAM, {"body": cached})
            await self.redis.xack(NARRATION_STREAM, NARRATION_GROUP, message_id)
            return True
        lock = key + ":lock"
        owner = uuid4().hex
        if not await self.redis.set(
            lock, owner, nx=True, px=max(120000, int(self.timeout * 4000))
        ):
            return False
        if self.model is None:
            await self._publish_result(
                job,
                Narration(
                    source_event_id=job.source.event_id,
                    status="UNAVAILABLE",
                    error_code="NARRATION_DISABLED_OFFLINE_DEMO",
                ),
                key,
                message_id,
            )
            return True
        operation_id = uuid4().hex
        started = monotonic()

        async def model_event(phase, error_code=None):
            event = job.source.model_copy(
                update={
                    "event_id": uuid4().hex,
                    "operation_id": operation_id,
                    "parent_operation_id": job.source.operation_id,
                    "occurred_at": datetime.now(UTC),
                    "payload": Lifecycle(
                        type="model",
                        phase=phase,
                        name=ModelTask.ACTIVITY_NARRATION.value,
                        model=safe_reference(
                            getattr(self.model, "model_name", type(self.model).__name__)
                        ),
                        duration_ms=None
                        if phase == "STARTED"
                        else int((monotonic() - started) * 1000),
                        error_code=error_code,
                    ),
                }
            )
            await self.redis.xadd(ACTIVITY_STREAM, {"body": event.model_dump_json()})

        await model_event("STARTED")
        task = asyncio.create_task(
            asyncio.to_thread(
                self.model.generate,
                task=ModelTask.ACTIVITY_NARRATION,
                system_prompt=NARRATION_PROMPT,
                payload={
                    "node": job.source.node,
                    "facts": job.source.payload.facts.model_dump(mode="json"),
                },
                output_schema=OutputSchema("NarrationText", TypeAdapter(NarrationText)),
            )
        )
        try:
            generated = await asyncio.wait_for(asyncio.shield(task), self.timeout)
            if re.search("已(?:進入|轉交|送交|啟動)", generated.text):
                raise ValueError("narration overstates downstream execution")
            payload = Narration(
                source_event_id=job.source.event_id,
                status="COMPLETED",
                text=generated.text,
            )
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - model and validation failures are observational
            payload = Narration(
                source_event_id=job.source.event_id,
                status="UNAVAILABLE",
                error_code="NARRATION_UNAVAILABLE",
            )
        try:
            await model_event(
                "COMPLETED" if payload.status == "COMPLETED" else "FAILED",
                payload.error_code,
            )
            await self._publish_result(job, payload, key, message_id)
        finally:
            # Retain the slot even if result publication fails after a timeout.
            try:
                await task
            except Exception:  # noqa: BLE001 - model failure already recorded safely
                LOGGER.debug("narration model call ended unsuccessfully")
        return True

    async def _publish_result(
        self, job: NarrationJob, payload: Narration, key: str, message_id: str
    ) -> None:
        event = ActivityEmission(
            **{
                **job.source.model_dump(),
                "event_id": job.job_id,
                "occurred_at": datetime.now(UTC),
                "payload": payload,
            }
        )
        # Save output and publish atomically before ACK; retry reuses exact output.
        async with self.redis.pipeline(transaction=True) as pipe:
            pipe.set(key, event.model_dump_json())
            pipe.xadd(ACTIVITY_STREAM, {"body": event.model_dump_json()})
            pipe.xack(NARRATION_STREAM, NARRATION_GROUP, message_id)
            await pipe.execute()
