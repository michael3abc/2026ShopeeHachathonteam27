"""Opt-in real Redis tests use unique keys and never flush shared Redis."""

import asyncio
import os
from uuid import uuid4

import pytest
from redis.asyncio import Redis

import return_agent_service.broker as broker_module
from return_agent_service.broker import RedisStreamBroker
from return_agent_service.journal import CommandClaim, PostgresCommandJournal
from return_agent_service.memory_replay import SqlAlchemyMemoryReplayStore
from return_agent_service.memory_worker import MemoryWorker
from sqlalchemy import text

from test_memory_worker import CandidateStore, SkipDistiller, _job, replay_engine  # noqa: F401


@pytest.fixture
def redis_namespace(monkeypatch):
    url = os.environ.get("PV2_TEST_REDIS_URL")
    if not url:
        pytest.skip("PV2_TEST_REDIS_URL enables namespaced Redis recovery tests")
    prefix = "test:pv2:" + uuid4().hex + ":"
    keys = []
    for name in ("REFUND_COMPLETION_STREAM", "MEMORY_JOB_STREAM", "MEMORY_EVENT_STREAM", "MEMORY_JOB_DLQ_STREAM"):
        key = prefix + name.lower()
        monkeypatch.setattr(broker_module, name, key)
        keys.append(key)
    return url, keys


@pytest.mark.asyncio
async def test_completion_pending_is_reclaimed_and_ack_replay_is_idempotent(redis_namespace):
    url, keys = redis_namespace
    client = Redis.from_url(url, decode_responses=True)
    broker = RedisStreamBroker(client)
    try:
        await broker.ensure_completion_group()
        stream = broker_module.REFUND_COMPLETION_STREAM
        group = broker_module.REFUND_COMPLETION_GROUP
        source_id = await client.xadd(stream, {"body": "synthetic-completion"})
        first = await broker.read_completion(consumer_name="old-worker", reclaim_idle_ms=60_000)
        assert first.message_id == source_id
        await client.xclaim(stream, group, "old-worker", min_idle_time=0, message_ids=[source_id], idle=1000)
        reopened = RedisStreamBroker(client)
        second = await reopened.read_completion(consumer_name="new-worker", reclaim_idle_ms=1)
        assert second == first
        await reopened.acknowledge_completion(source_id)
        await reopened.acknowledge_completion(source_id)
        assert (await client.xpending(stream, group))["pending"] == 0
        assert await reopened.read_completion(consumer_name="third-worker", reclaim_idle_ms=1) is None
    finally:
        await client.delete(*keys)
        await client.aclose()


@pytest.mark.asyncio
async def test_durable_journal_concurrent_initial_claim(replay_engine):
    if replay_engine.dialect.name != "postgresql":
        pytest.skip("AGENT_TEST_POSTGRES_URL enables durable journal contention")
    conninfo = replay_engine.url.set(drivername="postgresql").render_as_string(hide_password=False)
    journals = [PostgresCommandJournal(conninfo, owner=f"worker-{i}") for i in range(4)]
    try:
        for journal in journals:
            await journal.setup()
        results = await asyncio.gather(*(journal.claim("same-logical-job") for journal in journals))
        assert results.count(CommandClaim.CLAIMED) == 1
        assert results.count(CommandClaim.BUSY) == 3
    finally:
        for journal in journals:
            await journal.close()


@pytest.mark.asyncio
async def test_real_redis_job_replay_after_ack_loss_and_worker_restart(redis_namespace, replay_engine):
    if replay_engine.dialect.name != "postgresql":
        pytest.skip("AGENT_TEST_POSTGRES_URL enables durable worker restart")
    url, keys = redis_namespace
    client = Redis.from_url(url, decode_responses=True)
    conninfo = replay_engine.url.set(drivername="postgresql").render_as_string(hide_password=False)
    journal = PostgresCommandJournal(conninfo, owner="old-worker")
    reopened = PostgresCommandJournal(conninfo, owner="new-worker")
    replay = SqlAlchemyMemoryReplayStore(replay_engine)
    replay.migrate()
    job = _job()

    class Distiller(SkipDistiller):
        calls = 0

        def distill(self, input_):
            self.calls += 1
            return super().distill(input_)

    class LostAckBroker(RedisStreamBroker):
        async def acknowledge_memory_job(self, message_id):
            raise ConnectionError("synthetic lost acknowledgement")

    distiller = Distiller()
    broker = RedisStreamBroker(client)
    try:
        await journal.setup()
        await reopened.setup()
        await broker.ensure_memory_consumer_group()
        message_id = await broker.publish_memory_job(job)
        worker = MemoryWorker(distiller=distiller, store=CandidateStore(), broker=LostAckBroker(client),
            journal=journal, replay_store=replay, consumer_name="old-worker", block_ms=1, reclaim_idle_ms=1)
        with pytest.raises(ConnectionError, match="lost acknowledgement"):
            await worker.run_once()
        assert distiller.calls == 1
        await journal.close()
        stream, group = broker_module.MEMORY_JOB_STREAM, broker_module.MEMORY_WORKER_CONSUMER_GROUP
        await client.xclaim(stream, group, "old-worker", min_idle_time=0, message_ids=[message_id], idle=1000)
        replacement = MemoryWorker(distiller=distiller, store=CandidateStore(), broker=broker,
            journal=reopened, replay_store=SqlAlchemyMemoryReplayStore(replay_engine),
            consumer_name="new-worker", block_ms=1, reclaim_idle_ms=1)
        assert await replacement.run_once()
        assert distiller.calls == 1
        assert (await client.xpending(stream, group))["pending"] == 0
        assert len(await client.xrange(broker_module.MEMORY_EVENT_STREAM)) == 1
        with replay_engine.connect() as connection:
            assert connection.scalar(text("SELECT count(*) FROM memory_job_results")) == 1
    finally:
        await journal.close()
        await reopened.close()
        await client.delete(*keys)
        await client.aclose()
