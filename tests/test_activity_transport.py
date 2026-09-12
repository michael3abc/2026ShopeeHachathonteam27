"""Real HTTP/SSE with an optionally real isolated Redis transport."""

import asyncio
import json
import os
import socket
from datetime import UTC, datetime
from threading import Event
from uuid import uuid4

import fakeredis.aioredis
import httpx
import pytest
import uvicorn
from fastapi import FastAPI
from redis.asyncio import Redis
from return_agent.activities import ActivityRepository, router
from return_agent.activity_bridge import ActivityBridge
from return_agent.db.case import CaseRecord
from return_agent.db.models import Base
from return_agent_contracts.activity import (
    ACTIVITY_STREAM,
    NARRATION_GROUP,
    NARRATION_STREAM,
    ActivityEmission,
    ActivityFacts,
    Narration,
)
from return_agent_contracts.activity_observer import (
    CURRENT_ACTIVITY,
    ActivityContext,
    ObservedProvider,
    span,
)
from return_agent_runtime.model import ModelTask
from return_agent_service.activity_workers import (
    ActivityPublisher,
    NarrationText,
    NarrationWorker,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "offline", [False, True], ids=["model_enabled", "offline_demo"]
)
async def test_provider_start_over_http_before_return_and_late_narration(
    tmp_path, offline
):
    redis_url = os.getenv("ACTIVITY_TEST_REDIS_URL")
    redis = (
        Redis.from_url(redis_url, decode_responses=True)
        if redis_url
        else fakeredis.aioredis.FakeRedis(decode_responses=True)
    )
    assert await redis.xlen(ACTIVITY_STREAM) == 0, (
        "test requires an isolated empty Redis"
    )
    engine = create_engine(f"sqlite:///{tmp_path / 'activity.db'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    now = datetime.now(UTC)
    with sessions.begin() as session:
        session.add(
            CaseRecord(
                case_ref="CASE-TRANSPORT",
                thread_id="THREAD-1",
                order_ref="ORDER-1",
                user_ref="USER-1",
                status="RESOLVED",
                created_at=now,
                updated_at=now,
            )
        )
    repository = ActivityRepository(sessions)
    app = FastAPI()
    app.state.session_factory = sessions
    app.include_router(router)
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(32)
    server = uvicorn.Server(uvicorn.Config(app, log_level="error", lifespan="off"))
    serve = asyncio.create_task(server.serve(sockets=[listener]))
    publisher = ActivityPublisher(redis)
    bridge = ActivityBridge(sessions, redis)
    stop = asyncio.Event()
    publish = asyncio.create_task(publisher.run_forever(stop))
    project = asyncio.create_task(bridge.run_forever())
    release = Event()

    class Provider:
        def verify(self, _request):
            assert release.wait(5)
            return {"status": "PASS"}

    class CaseModel:
        def generate(self, **kwargs):
            return {"verdict": "APPROVE"}

    def execute():
        token = CURRENT_ACTIVITY.set(
            ActivityContext(
                case_ref="CASE-TRANSPORT",
                run_id="RUN-1",
                scope="CASE",
                node="external_verification",
                attempt_id=uuid4().hex,
                sink=publisher.submit,
            )
        )
        try:
            with span("node", "external_verification") as outcome:
                ObservedProvider(CaseModel(), "model", kind="model").generate(
                    task=ModelTask.REVIEW
                )
                ObservedProvider(Provider(), "verification_provider").verify(
                    {"raw_url": "https://secret/", "token": "secret-token"}
                )
                outcome["facts"] = ActivityFacts(outcome="PASS", next_node="reviewer")
        finally:
            CURRENT_ACTIVITY.reset(token)

    operation = None

    class Narrator:
        def generate(self, **kwargs):
            assert set(kwargs["payload"]) == {"node", "facts"}
            return NarrationText(text="驗證已通過，下一步進行複核。")

    narrator = NarrationWorker(redis, None if offline else Narrator())
    try:
        async with asyncio.timeout(10):
            while not server.started:
                await asyncio.sleep(0.01)
            async with httpx.AsyncClient(
                base_url=f"http://127.0.0.1:{listener.getsockname()[1]}", timeout=5
            ) as client:
                async with client.stream(
                    "GET", "/cases/CASE-TRANSPORT/activities/stream"
                ) as response:
                    lines = response.aiter_lines()
                    operation = asyncio.create_task(asyncio.to_thread(execute))
                    received = []
                    async for line in lines:
                        if not line.startswith("data: "):
                            continue
                        event = json.loads(line[6:])
                        received.append(event)
                        if (
                            event["payload"]["type"] == "tool"
                            and event["payload"]["phase"] == "STARTED"
                        ):
                            assert not operation.done()
                            release.set()
                        if event["payload"]["type"] == "node_summary":
                            break
                    await operation
                    cursor = received[-1]["seq"]
                # Reconnection header takes precedence over the query parameter.
                await narrator.setup()
                await bridge.dispatch_once()
                assert await narrator.run_once()
                async with client.stream(
                    "GET",
                    "/cases/CASE-TRANSPORT/activities/stream?after_seq=999",
                    headers={"Last-Event-ID": str(cursor)},
                ) as response:
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            event = json.loads(line[6:])
                            assert event["seq"] > cursor
                            if event["payload"]["type"] == "narration":
                                assert (
                                    event["payload"]["source_event_id"]
                                    == received[-1]["event_id"]
                                )
                                assert event["attempt_id"] == received[-1]["attempt_id"]
                                assert (
                                    event["operation_id"]
                                    == received[-1]["operation_id"]
                                )
                                if offline:
                                    assert event["payload"]["status"] == "UNAVAILABLE"
                                    assert (
                                        event["payload"]["error_code"]
                                        == "NARRATION_DISABLED_OFFLINE_DEMO"
                                    )
                                    assert event["payload"]["text"] is None
                                else:
                                    assert event["payload"]["status"] == "COMPLETED"
                                break
                history = (await client.get("/cases/CASE-TRANSPORT/activities")).json()
                assert "secret" not in json.dumps(history)
                assert any(
                    isinstance(e.payload, Narration)
                    for e in repository.page("CASE-TRANSPORT", 0, 100).events
                )
                assert [e["seq"] for e in history["events"]] == list(
                    range(1, len(history["events"]) + 1)
                )
                model_events = [
                    e for e in history["events"] if e["payload"]["type"] == "model"
                ]
                case_calls = [
                    e
                    for e in model_events
                    if e["payload"]["name"] == ModelTask.REVIEW.value
                ]
                narration_calls = [
                    e
                    for e in model_events
                    if e["payload"]["name"] == "ACTIVITY_NARRATION"
                ]
                assert [e["payload"]["phase"] for e in case_calls] == [
                    "STARTED",
                    "COMPLETED",
                ]
                if offline:
                    assert not narration_calls
                else:
                    assert [e["payload"]["phase"] for e in narration_calls] == [
                        "STARTED",
                        "COMPLETED",
                    ]
                    assert (
                        narration_calls[0]["operation_id"]
                        != case_calls[0]["operation_id"]
                    )
                    assert (
                        narration_calls[0]["attempt_id"] == case_calls[0]["attempt_id"]
                    )
                assert (await redis.xpending(NARRATION_STREAM, NARRATION_GROUP))[
                    "pending"
                ] == 0
                # Outbox redelivery reuses the cached result; API projection deduplicates it.
                original_job = (await redis.xrange(NARRATION_STREAM))[0][1]
                await redis.xadd(NARRATION_STREAM, original_job)
                assert await narrator.run_once()
                replay_fields = (await redis.xrange(ACTIVITY_STREAM))[-1][1]
                replay = json.loads(replay_fields["body"])
                replay_event = repository.append(
                    ActivityEmission.model_validate(replay)
                )
                assert replay_event.seq == history["events"][-1]["seq"]
                assert (
                    await client.get("/cases/CASE-TRANSPORT/activities")
                ).json() == history
                assert (await redis.xpending(NARRATION_STREAM, NARRATION_GROUP))[
                    "pending"
                ] == 0
    finally:
        release.set()
        if operation:
            await operation
        stop.set()
        for task in (publish, project):
            task.cancel()
        await asyncio.gather(publish, project, return_exceptions=True)
        server.should_exit = True
        await serve
        listener.close()
        await redis.aclose()
        engine.dispose()
