from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import fakeredis.aioredis
import pytest
from return_agent_contracts.service import (
    AGENT_COMMAND_STREAM,
    AGENT_EVENT_STREAM,
    MEMORY_ENQUEUE_CONSUMER_GROUP,
    MEMORY_EVENT_STREAM,
    MEMORY_JOB_STREAM,
    MEMORY_WORKER_CONSUMER_GROUP,
    REDIS_BODY_FIELD,
    AgentRunFailedEvent,
    MemoryDistillationFailedEvent,
)
from return_agent_service.broker import RedisStreamBroker


@pytest.mark.asyncio
async def test_redis_stream_broker_reads_publishes_and_acknowledges() -> None:
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    broker = RedisStreamBroker(client)
    await broker.ensure_consumer_group()
    source_id = await client.xadd(AGENT_COMMAND_STREAM, {REDIS_BODY_FIELD: "{}"})

    message = await broker.read_command(
        consumer_name="worker-1", block_ms=1, reclaim_idle_ms=60_000
    )
    assert message is not None
    assert message.message_id == source_id
    assert message.body == "{}"

    event = AgentRunFailedEvent(
        event_type="RUN_FAILED",
        event_id="EVENT-001",
        command_id="COMMAND-001",
        case_ref="CASE-001",
        thread_id="THREAD-001",
        event_index=1,
        occurred_at=datetime(2026, 9, 6, 12, 0, tzinfo=UTC),
        payload={"code": "FAILED", "message": "failed", "retryable": False},
    )
    await broker.publish_event(event)
    entries = await client.xrange(AGENT_EVENT_STREAM)
    assert '"event_type":"RUN_FAILED"' in entries[0][1][REDIS_BODY_FIELD]

    await broker.acknowledge(message.message_id)
    pending = await client.xpending(AGENT_COMMAND_STREAM, "return-agent-workers-v1")
    assert pending["pending"] == 0


@pytest.mark.asyncio
async def test_stale_pending_command_is_reclaimed_by_another_consumer() -> None:
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    broker = RedisStreamBroker(client)
    await broker.ensure_consumer_group()
    source_id = await client.xadd(AGENT_COMMAND_STREAM, {REDIS_BODY_FIELD: "{}"})
    first = await broker.read_command(
        consumer_name="worker-1", block_ms=1, reclaim_idle_ms=60_000
    )
    assert first is not None

    await asyncio.sleep(0.01)
    reclaimed = await broker.read_command(
        consumer_name="worker-2", block_ms=1, reclaim_idle_ms=1
    )
    assert reclaimed is not None
    assert reclaimed.message_id == source_id


@pytest.mark.asyncio
async def test_memory_enqueue_group_consumes_agent_events_independently() -> None:
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    broker = RedisStreamBroker(client)
    await broker.ensure_memory_enqueue_consumer_group()
    source_id = await client.xadd(AGENT_EVENT_STREAM, {REDIS_BODY_FIELD: "{}"})

    message = await broker.read_agent_event_for_memory(
        consumer_name="memory-enqueuer-1", block_ms=1, reclaim_idle_ms=60_000
    )

    assert message is not None
    assert message.message_id == source_id
    await broker.acknowledge_agent_event_for_memory(message.message_id)
    pending = await client.xpending(AGENT_EVENT_STREAM, MEMORY_ENQUEUE_CONSUMER_GROUP)
    assert pending["pending"] == 0


@pytest.mark.asyncio
async def test_memory_job_and_event_stream_round_trip() -> None:
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    broker = RedisStreamBroker(client)
    await broker.ensure_memory_consumer_group()
    source_id = await client.xadd(MEMORY_JOB_STREAM, {REDIS_BODY_FIELD: "{}"})

    message = await broker.read_memory_job(
        consumer_name="memory-worker-1", block_ms=1, reclaim_idle_ms=60_000
    )
    assert message is not None
    assert message.message_id == source_id

    event = MemoryDistillationFailedEvent(
        event_type="FAILED",
        event_id="MEMORY-EVENT-001",
        job_id="MEMORY-JOB-001",
        source_command_id="COMMAND-001",
        case_ref="CASE-001",
        thread_id="THREAD-001",
        occurred_at=datetime(2026, 9, 6, 12, 0, tzinfo=UTC),
        payload={
            "code": "MEMORY_DISTILLATION_FAILED",
            "message": "invalid candidate",
            "retryable": False,
            "distiller_prompt_version": "memory-distiller:1.0",
        },
    )
    await broker.publish_memory_event(event)
    entries = await client.xrange(MEMORY_EVENT_STREAM)
    assert '"event_type":"FAILED"' in entries[0][1][REDIS_BODY_FIELD]

    await broker.acknowledge_memory_job(message.message_id)
    pending = await client.xpending(MEMORY_JOB_STREAM, MEMORY_WORKER_CONSUMER_GROUP)
    assert pending["pending"] == 0
