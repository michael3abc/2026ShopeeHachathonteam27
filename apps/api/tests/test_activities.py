from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import fakeredis.aioredis
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from return_agent.activities import ActivityRepository, router, stream_activities
from return_agent.activity_bridge import ActivityBridge
from return_agent.db.activity import NarrationOutboxRecord
from return_agent.db.case import CaseRecord
from return_agent.db.models import Base
from return_agent_contracts.activity import (
    ACTIVITY_GROUP,
    ACTIVITY_STREAM,
    NARRATION_STREAM,
    ActivityEmission,
    ActivityFacts,
    Narration,
    NodeSummary,
)
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

TIME = datetime(2026, 9, 11, tzinfo=UTC)


def emission(**updates):
    raw = {
        "event_id": uuid4().hex,
        "case_ref": "CASE-1",
        "run_id": "RUN-1",
        "scope": "CASE",
        "node": "reviewer",
        "operation_id": "OP-1",
        "attempt_id": "ATTEMPT-1",
        "occurred_at": TIME,
        "payload": NodeSummary(facts=ActivityFacts(verdict="APPROVE")),
    }
    return ActivityEmission(**(raw | updates))


@pytest.fixture
def repository(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'activity.db'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    with sessions.begin() as session:
        for i in (1, 2):
            session.add(
                CaseRecord(
                    case_ref=f"CASE-{i}",
                    thread_id=f"THREAD-{i}",
                    order_ref=f"ORDER-{i}",
                    user_ref="USER-1",
                    status="RESOLVED",
                    created_at=TIME,
                    updated_at=TIME,
                )
            )
    yield ActivityRepository(sessions)
    engine.dispose()


def test_dedupe_case_isolation_and_transactional_outbox(repository):
    source = emission()
    first = repository.append(source)
    assert repository.append(source) == first
    assert repository.append(emission(case_ref="CASE-2")).seq == 1
    assert repository.append(emission()).seq == 2
    with pytest.raises(ValueError, match="collision"):
        repository.append(source.model_copy(update={"run_id": "OTHER"}))
    with repository.sessions() as session:
        assert (
            session.scalar(select(func.count()).select_from(NarrationOutboxRecord)) == 3
        )
    page = repository.page("CASE-1", 0, 1)
    assert page.next_cursor == 1 and page.has_more
    assert repository.page("CASE-1", 2, 100).events == []


def test_narration_source_binding_and_one_result(repository):
    source = emission()
    repository.append(source)
    result = source.model_copy(
        update={
            "event_id": "NARRATION-1",
            "payload": Narration(
                source_event_id=source.event_id,
                status="COMPLETED",
                text="複核已核准提案。",
            ),
        }
    )
    with pytest.raises(ValueError, match="correlation"):
        repository.append(result.model_copy(update={"case_ref": "CASE-2"}))
    first = repository.append(result)
    assert (
        repository.append(result.model_copy(update={"event_id": "NARRATION-2"}))
        == first
    )
    assert len(repository.page("CASE-1", 0, 100).events) == 2


@pytest.mark.asyncio
async def test_http_pages_validation_and_cursor(repository):
    app = FastAPI()
    app.state.session_factory = repository.sessions
    app.include_router(router)
    repository.append(emission())
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        result = await client.get("/cases/CASE-1/activities?limit=1")
        assert result.status_code == 200 and result.json()["next_cursor"] == 1
        assert (await client.get("/cases/missing/activities")).status_code == 404
        assert (
            await client.get("/cases/CASE-1/activities?after_seq=-1")
        ).status_code == 422
        assert (
            await client.get("/cases/CASE-1/activities?limit=501")
        ).status_code == 422
        assert (
            await client.get(
                "/cases/CASE-1/activities/stream", headers={"Last-Event-ID": "bad"}
            )
        ).status_code == 400


@pytest.mark.asyncio
async def test_sse_stays_open_after_terminal_for_late_events(repository):
    async def connected():
        return False

    request = SimpleNamespace(is_disconnected=connected)
    first = repository.append(emission())
    stream = stream_activities(
        repository, request, "CASE-1", first.seq, poll=0.001, heartbeat=0.001
    )
    assert await anext(stream) == ": keep-alive\n\n"
    late = repository.append(emission(scope="MEMORY", job_id="JOB-1"))
    assert f"id: {late.seq}\n" in await anext(stream)
    await stream.aclose()


@pytest.mark.asyncio
async def test_bridge_replay_and_outbox_retry(repository):
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    bridge = ActivityBridge(repository.sessions, redis)
    await bridge.setup()
    source = emission()
    for _ in range(2):
        await redis.xadd(ACTIVITY_STREAM, {"body": source.model_dump_json()})
    await bridge.consume_once()
    assert len(repository.page("CASE-1", 0, 100).events) == 1
    assert (await redis.xpending(ACTIVITY_STREAM, ACTIVITY_GROUP))["pending"] == 0
    original = bridge._mark_sent

    def unavailable(_source):
        raise ConnectionError("test")

    bridge._mark_sent = unavailable
    with pytest.raises(ConnectionError):
        await bridge.dispatch_once()
    bridge._mark_sent = original
    await bridge.dispatch_once()
    jobs = await redis.xrange(NARRATION_STREAM)
    assert len(jobs) == 2 and jobs[0][1] == jobs[1][1]
    await redis.xadd(ACTIVITY_STREAM, {"body": '{"credential":"secret"}'})
    await bridge.consume_once()
    rejected = str(await redis.xrange(ACTIVITY_STREAM + ".rejected"))
    assert "secret" not in rejected and "INVALID_ACTIVITY" in rejected
    await redis.aclose()
