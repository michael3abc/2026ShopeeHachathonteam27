import asyncio
from datetime import UTC, datetime
from threading import Event
from types import SimpleNamespace

import fakeredis.aioredis
import pytest
from return_agent_contracts.activity import (
    ACTIVITY_STREAM,
    NARRATION_GROUP,
    NARRATION_STREAM,
    ActivityEmission,
    ActivityFacts,
    NarrationJob,
    NodeSummary,
)
from return_agent_service import composition
from return_agent_service.activity_workers import (
    ActivityPublisher,
    NarrationText,
    NarrationWorker,
)
from return_agent_service.demo import create_demo_runtime
from return_agent_service.settings import AgentServiceSettings


def job():
    source = ActivityEmission(
        event_id="SOURCE-1",
        case_ref="CASE-1",
        run_id="RUN-1",
        scope="CASE",
        node="reviewer",
        operation_id="OP-1",
        attempt_id="ATTEMPT-1",
        occurred_at=datetime.now(UTC),
        payload=NodeSummary(facts=ActivityFacts(verdict="APPROVE")),
    )
    return NarrationJob(job_id="narration:SOURCE-1", source=source)


class Model:
    def __init__(self, text="複核已核准提案。"):
        self.text, self.calls = text, []

    def generate(self, **kwargs):
        self.calls.append(kwargs)
        return NarrationText(text=self.text)


@pytest.mark.asyncio
async def test_narration_summary_only_and_replay_cached():
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    model = Model()
    worker = NarrationWorker(redis, model)
    await worker.setup()
    for _ in range(2):
        await redis.xadd(NARRATION_STREAM, {"body": job().model_dump_json()})
        assert await worker.run_once()
    assert len(model.calls) == 1
    assert set(model.calls[0]["payload"]) == {"node", "facts"}
    model_events = [
        ActivityEmission.model_validate_json(fields["body"])
        for _, fields in await redis.xrange(ACTIVITY_STREAM)
        if ActivityEmission.model_validate_json(fields["body"]).payload.type == "model"
    ]
    assert [event.payload.phase for event in model_events] == ["STARTED", "COMPLETED"]
    assert len({event.operation_id for event in model_events}) == 1
    for event in model_events:
        assert event.operation_id != job().source.operation_id
        assert event.parent_operation_id == job().source.operation_id
        assert event.attempt_id == job().source.attempt_id
        assert event.payload.name == "ACTIVITY_NARRATION"
    entries = [
        (key, fields)
        for key, fields in await redis.xrange(ACTIVITY_STREAM)
        if ActivityEmission.model_validate_json(fields["body"]).payload.type
        == "narration"
    ]
    assert entries[0][1] == entries[1][1]
    assert (await redis.xpending(NARRATION_STREAM, NARRATION_GROUP))["pending"] == 0
    await redis.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize("profile", ["demo", "demo-qwen"])
async def test_composition_selects_narration_model_explicitly(monkeypatch, profile):
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(
        composition.RedisStreamBroker,
        "from_url",
        lambda _url: SimpleNamespace(transport_client=redis),
    )
    captured = {}
    monkeypatch.setattr(
        composition, "create_health_app", lambda **kwargs: captured.update(kwargs)
    )
    runtime = create_demo_runtime(
        model_override=Model() if profile == "demo-qwen" else None
    )
    settings = AgentServiceSettings(
        redis_url="redis://unused", consumer_name="test", profile=profile
    )
    composition.compose_service(settings=settings, runtime=runtime)
    narrator = captured["narration_worker"]
    assert narrator.model is (None if profile == "demo" else runtime.dependencies.model)
    assert captured["worker"]._runtime is runtime
    await redis.aclose()


@pytest.mark.asyncio
async def test_offline_narration_consumes_and_replays_without_model_events():
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    worker = NarrationWorker(redis, None)
    await worker.setup()
    for _ in range(2):
        await redis.xadd(NARRATION_STREAM, {"body": job().model_dump_json()})
        assert await worker.run_once()
        assert (await redis.xpending(NARRATION_STREAM, NARRATION_GROUP))["pending"] == 0
    entries = await redis.xrange(ACTIVITY_STREAM)
    assert len(entries) == 2
    assert entries[0][1] == entries[1][1]
    result = ActivityEmission.model_validate_json(entries[0][1]["body"])
    assert result.payload.type == "narration"
    assert result.payload.status == "UNAVAILABLE"
    assert result.payload.error_code == "NARRATION_DISABLED_OFFLINE_DEMO"
    assert result.payload.text is None
    assert result.payload.source_event_id == job().source.event_id
    assert result.operation_id == job().source.operation_id
    assert result.attempt_id == job().source.attempt_id
    assert (
        await redis.get("activity-narration-result:" + job().job_id)
        == entries[0][1]["body"]
    )
    assert not await worker.run_once()
    await redis.aclose()


@pytest.mark.asyncio
async def test_real_model_failure_is_not_reported_as_offline_disabled():
    class FailingModel:
        def generate(self, **kwargs):
            raise RuntimeError("private-model-error")

    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    worker = NarrationWorker(redis, FailingModel())
    await worker.setup()
    await redis.xadd(NARRATION_STREAM, {"body": job().model_dump_json()})
    assert await worker.run_once()
    entries = await redis.xrange(ACTIVITY_STREAM)
    events = [
        ActivityEmission.model_validate_json(fields["body"]) for _, fields in entries
    ]
    assert [event.payload.phase for event in events[:-1]] == ["STARTED", "FAILED"]
    assert events[-1].payload.error_code == "NARRATION_UNAVAILABLE"
    assert events[-1].payload.text is None
    assert "private-model-error" not in str(entries)
    assert (await redis.xpending(NARRATION_STREAM, NARRATION_GROUP))["pending"] == 0
    await redis.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "unsafe", ["請寄信 user@example.com。", "請讀 https://private/a。", "sk-secretkey"]
)
async def test_invalid_narration_is_unavailable_without_leaking(unsafe):
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    worker = NarrationWorker(redis, Model(unsafe))
    await worker.setup()
    await redis.xadd(NARRATION_STREAM, {"body": job().model_dump_json()})
    await worker.run_once()
    raw = (await redis.xrange(ACTIVITY_STREAM))[-1][1]["body"]
    assert "UNAVAILABLE" in raw and unsafe not in raw
    await redis.aclose()


@pytest.mark.asyncio
async def test_timeout_emits_unavailable_before_thread_releases_slot():
    release = Event()

    class SlowModel:
        def generate(self, **kwargs):
            release.wait(5)
            return NarrationText(text="複核已完成。")

    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    worker = NarrationWorker(redis, SlowModel(), timeout=0.02)
    await worker.setup()
    await redis.xadd(NARRATION_STREAM, {"body": job().model_dump_json()})
    task = asyncio.create_task(worker.run_once())
    try:
        async with asyncio.timeout(2):
            while await redis.xlen(ACTIVITY_STREAM) < 3:
                await asyncio.sleep(0.005)
        assert not task.done()
        assert "UNAVAILABLE" in (await redis.xrange(ACTIVITY_STREAM))[-1][1]["body"]
    finally:
        release.set()
        await task
        await redis.aclose()


@pytest.mark.asyncio
async def test_publisher_bounds_and_same_event_delivery():
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    publisher = ActivityPublisher(redis, capacity=1)
    publisher.submit(job().source)
    publisher.submit(job().source)
    await asyncio.sleep(0)
    assert publisher.failed == 1
    stop = asyncio.Event()
    task = asyncio.create_task(publisher.run_forever(stop))
    await asyncio.wait_for(publisher.queue.join(), 2)
    assert await redis.xlen(ACTIVITY_STREAM) == 1
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    await redis.aclose()
