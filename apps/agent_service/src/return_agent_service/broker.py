"""Redis Streams transport owned by the Agent service."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from pydantic import TypeAdapter
from redis.asyncio import Redis
from redis.exceptions import ResponseError
from return_agent_contracts.completion import REFUND_COMPLETION_STREAM, REFUND_COMPLETION_GROUP
from return_agent_contracts.service import (
    AGENT_COMMAND_DLQ_STREAM,
    AGENT_COMMAND_STREAM,
    AGENT_EVENT_STREAM,
    AGENT_WORKER_CONSUMER_GROUP,
    MEMORY_ENQUEUE_CONSUMER_GROUP,
    MEMORY_EVENT_STREAM,
    MEMORY_JOB_DLQ_STREAM,
    MEMORY_JOB_STREAM,
    MEMORY_WORKER_CONSUMER_GROUP,
    REDIS_BODY_FIELD,
    AgentCommandDeadLetter,
    AgentServiceEvent,
    MemoryDistillationJob,
    MemoryJobDeadLetter,
    MemoryServiceEvent,
)

EVENT_ADAPTER = TypeAdapter(AgentServiceEvent)
MEMORY_EVENT_ADAPTER = TypeAdapter(MemoryServiceEvent)


@dataclass(frozen=True, slots=True)
class BrokerMessage:
    message_id: str
    body: str


class AgentStreamBroker(Protocol):
    async def ensure_consumer_group(self) -> None: ...

    async def read_command(
        self,
        *,
        consumer_name: str,
        block_ms: int,
        reclaim_idle_ms: int,
    ) -> BrokerMessage | None: ...

    async def publish_event(self, event: AgentServiceEvent) -> str: ...

    async def publish_dead_letter(self, dead_letter: AgentCommandDeadLetter) -> str: ...

    async def acknowledge(self, message_id: str) -> None: ...

    async def ping(self) -> bool: ...

    async def close(self) -> None: ...


class MemoryJobPublisher(Protocol):
    async def publish_memory_job(self, job: MemoryDistillationJob) -> str: ...


class MemoryEnqueueStreamBroker(MemoryJobPublisher, Protocol):
    async def ensure_completion_group(self) -> None: ...
    async def read_completion(self, *, consumer_name: str, reclaim_idle_ms: int) -> BrokerMessage | None: ...
    async def acknowledge_completion(self, message_id: str) -> None: ...
    async def ensure_memory_enqueue_consumer_group(self) -> None: ...

    async def read_agent_event_for_memory(
        self,
        *,
        consumer_name: str,
        block_ms: int,
        reclaim_idle_ms: int,
    ) -> BrokerMessage | None: ...

    async def acknowledge_agent_event_for_memory(self, message_id: str) -> None: ...


class MemoryStreamBroker(MemoryJobPublisher, Protocol):
    async def ensure_memory_consumer_group(self) -> None: ...

    async def read_memory_job(
        self,
        *,
        consumer_name: str,
        block_ms: int,
        reclaim_idle_ms: int,
    ) -> BrokerMessage | None: ...

    async def publish_memory_event(self, event: MemoryServiceEvent) -> str: ...

    async def publish_memory_dead_letter(
        self, dead_letter: MemoryJobDeadLetter
    ) -> str: ...

    async def acknowledge_memory_job(self, message_id: str) -> None: ...


class RedisStreamBroker:
    """Encode each contract as one JSON value in the Redis `body` field."""

    def __init__(self, client: Redis) -> None:
        self._client = client

    async def ensure_completion_group(self):
        try:
            await self._client.xgroup_create(REFUND_COMPLETION_STREAM,REFUND_COMPLETION_GROUP,id="0-0",mkstream=True)
        except ResponseError as error:
            if "BUSYGROUP" not in str(error):
                raise

    async def read_completion(self, *, consumer_name, reclaim_idle_ms):
        claimed = await self._client.xautoclaim(REFUND_COMPLETION_STREAM,REFUND_COMPLETION_GROUP,
            consumer_name,min_idle_time=reclaim_idle_ms,start_id="0-0",count=1)
        if len(claimed) > 1 and claimed[1]:
            return self._decode(claimed[1][0])
        response = await self._client.xreadgroup(REFUND_COMPLETION_GROUP,consumer_name,
            streams={REFUND_COMPLETION_STREAM:">"},count=1)
        return self._decode(response[0][1][0]) if response else None

    async def acknowledge_completion(self, message_id):
        await self._client.xack(REFUND_COMPLETION_STREAM,REFUND_COMPLETION_GROUP,message_id)

    @property
    def transport_client(self) -> Redis:
        """Shared service-owned Redis connection for independent worker streams."""
        return self._client

    @classmethod
    def from_url(cls, url: str) -> RedisStreamBroker:
        return cls(Redis.from_url(url, decode_responses=True))

    async def ensure_consumer_group(self) -> None:
        try:
            await self._client.xgroup_create(
                AGENT_COMMAND_STREAM,
                AGENT_WORKER_CONSUMER_GROUP,
                id="0-0",
                mkstream=True,
            )
        except ResponseError as error:
            if "BUSYGROUP" not in str(error):
                raise

    async def ensure_memory_consumer_group(self) -> None:
        try:
            await self._client.xgroup_create(
                MEMORY_JOB_STREAM,
                MEMORY_WORKER_CONSUMER_GROUP,
                id="0-0",
                mkstream=True,
            )
        except ResponseError as error:
            if "BUSYGROUP" not in str(error):
                raise

    async def ensure_memory_enqueue_consumer_group(self) -> None:
        try:
            await self._client.xgroup_create(
                AGENT_EVENT_STREAM,
                MEMORY_ENQUEUE_CONSUMER_GROUP,
                id="0-0",
                mkstream=True,
            )
        except ResponseError as error:
            if "BUSYGROUP" not in str(error):
                raise

    async def read_command(
        self,
        *,
        consumer_name: str,
        block_ms: int,
        reclaim_idle_ms: int,
    ) -> BrokerMessage | None:
        claimed = await self._client.xautoclaim(
            AGENT_COMMAND_STREAM,
            AGENT_WORKER_CONSUMER_GROUP,
            consumer_name,
            min_idle_time=reclaim_idle_ms,
            start_id="0-0",
            count=1,
        )
        claimed_messages = claimed[1] if len(claimed) > 1 else []
        if claimed_messages:
            return self._decode(claimed_messages[0])

        response = await self._client.xreadgroup(
            AGENT_WORKER_CONSUMER_GROUP,
            consumer_name,
            streams={AGENT_COMMAND_STREAM: ">"},
            count=1,
            block=block_ms,
        )
        if not response:
            return None
        return self._decode(response[0][1][0])

    async def publish_event(self, event: AgentServiceEvent) -> str:
        return str(
            await self._client.xadd(
                AGENT_EVENT_STREAM,
                {REDIS_BODY_FIELD: EVENT_ADAPTER.dump_json(event).decode("utf-8")},
            )
        )

    async def publish_memory_job(self, job: MemoryDistillationJob) -> str:
        return str(
            await self._client.xadd(
                MEMORY_JOB_STREAM,
                {REDIS_BODY_FIELD: job.model_dump_json()},
            )
        )

    async def read_agent_event_for_memory(
        self,
        *,
        consumer_name: str,
        block_ms: int,
        reclaim_idle_ms: int,
    ) -> BrokerMessage | None:
        claimed = await self._client.xautoclaim(
            AGENT_EVENT_STREAM,
            MEMORY_ENQUEUE_CONSUMER_GROUP,
            consumer_name,
            min_idle_time=reclaim_idle_ms,
            start_id="0-0",
            count=1,
        )
        claimed_messages = claimed[1] if len(claimed) > 1 else []
        if claimed_messages:
            return self._decode(claimed_messages[0])
        response = await self._client.xreadgroup(
            MEMORY_ENQUEUE_CONSUMER_GROUP,
            consumer_name,
            streams={AGENT_EVENT_STREAM: ">"},
            count=1,
            block=block_ms,
        )
        if not response:
            return None
        return self._decode(response[0][1][0])

    async def read_memory_job(
        self,
        *,
        consumer_name: str,
        block_ms: int,
        reclaim_idle_ms: int,
    ) -> BrokerMessage | None:
        claimed = await self._client.xautoclaim(
            MEMORY_JOB_STREAM,
            MEMORY_WORKER_CONSUMER_GROUP,
            consumer_name,
            min_idle_time=reclaim_idle_ms,
            start_id="0-0",
            count=1,
        )
        claimed_messages = claimed[1] if len(claimed) > 1 else []
        if claimed_messages:
            return self._decode(claimed_messages[0])
        response = await self._client.xreadgroup(
            MEMORY_WORKER_CONSUMER_GROUP,
            consumer_name,
            streams={MEMORY_JOB_STREAM: ">"},
            count=1,
            block=block_ms,
        )
        if not response:
            return None
        return self._decode(response[0][1][0])

    async def publish_memory_event(self, event: MemoryServiceEvent) -> str:
        return str(
            await self._client.xadd(
                MEMORY_EVENT_STREAM,
                {
                    REDIS_BODY_FIELD: MEMORY_EVENT_ADAPTER.dump_json(event).decode(
                        "utf-8"
                    )
                },
            )
        )

    async def publish_memory_dead_letter(self, dead_letter: MemoryJobDeadLetter) -> str:
        return str(
            await self._client.xadd(
                MEMORY_JOB_DLQ_STREAM,
                {REDIS_BODY_FIELD: dead_letter.model_dump_json()},
            )
        )

    async def publish_dead_letter(self, dead_letter: AgentCommandDeadLetter) -> str:
        return str(
            await self._client.xadd(
                AGENT_COMMAND_DLQ_STREAM,
                {REDIS_BODY_FIELD: dead_letter.model_dump_json()},
            )
        )

    async def acknowledge(self, message_id: str) -> None:
        await self._client.xack(
            AGENT_COMMAND_STREAM,
            AGENT_WORKER_CONSUMER_GROUP,
            message_id,
        )

    async def acknowledge_memory_job(self, message_id: str) -> None:
        await self._client.xack(
            MEMORY_JOB_STREAM,
            MEMORY_WORKER_CONSUMER_GROUP,
            message_id,
        )

    async def acknowledge_agent_event_for_memory(self, message_id: str) -> None:
        await self._client.xack(
            AGENT_EVENT_STREAM,
            MEMORY_ENQUEUE_CONSUMER_GROUP,
            message_id,
        )

    async def ping(self) -> bool:
        return bool(await self._client.ping())

    async def close(self) -> None:
        await self._client.aclose()

    @staticmethod
    def _decode(message: tuple[object, dict[object, object]]) -> BrokerMessage:
        message_id, fields = message
        body = fields.get(REDIS_BODY_FIELD)
        if body is None:
            body = fields.get(REDIS_BODY_FIELD.encode())
        return BrokerMessage(
            message_id=_text(message_id),
            body="" if body is None else _text(body),
        )


def _text(value: object) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return str(value)
