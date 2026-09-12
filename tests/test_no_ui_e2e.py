from __future__ import annotations

from collections.abc import AsyncIterator

import fakeredis.aioredis
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from pydantic import TypeAdapter
from return_agent.agent_bridge import (
    API_EVENT_CONSUMER_GROUP,
    AgentBridge,
    AgentBridgeSettings,
)
from return_agent.agent_commands import SqlAlchemyAgentCommandOutbox
from return_agent.app import app
from return_agent.db.agent_bridge import (
    AgentCommandOutboxRecord,
    ProcessedAgentEventRecord,
)
from return_agent.db.case import CaseRecord
from return_agent.db.models import Base
from return_agent_contracts.enums import ReasonCode
from return_agent_contracts.service import (
    AGENT_COMMAND_STREAM,
    AGENT_EVENT_STREAM,
    REDIS_BODY_FIELD,
    AgentInterruptedEvent,
    AgentResolvedEvent,
    AgentServiceEvent,
)
from return_agent_service.broker import RedisStreamBroker
from return_agent_service.demo import create_demo_runtime
from return_agent_service.journal import InMemoryCommandJournal
from return_agent_service.worker import AgentWorker
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

RESOLVED_EVENT_ADAPTER = TypeAdapter(AgentResolvedEvent)
SERVICE_EVENT_ADAPTER = TypeAdapter(AgentServiceEvent)


@pytest.mark.asyncio
async def test_uploaded_pixels_cross_api_graph_and_model_only(
    e2e_components, tmp_path, monkeypatch
):
    """Real sanitized bytes and graph; only the model's answer is synthetic."""
    import base64
    import io
    import json
    from contextlib import closing
    from dataclasses import replace
    from types import SimpleNamespace

    from fastapi.testclient import TestClient
    from PIL import Image
    from return_agent.attachments import sanitize
    from return_agent.capabilities.evidence import SqlAlchemyEvidenceProvider
    from return_agent_contracts.image_adapter import HttpEvidenceImageProvider
    from return_agent_runtime import ReturnAgentRuntime
    from return_agent_runtime.model import ModelTask, OpenAIStructuredOutputModel

    sessions, redis, bridge, worker = e2e_components
    original = worker._runtime
    snapshot = original.dependencies.case_context_provider.load_case_context(
        "CASE-DEMO"
    ).order_snapshot
    monkeypatch.setattr(
        app.state,
        "provider_bundle",
        SimpleNamespace(
            case_context_provider=SimpleNamespace(
                load_order_snapshot=lambda ref: snapshot
            )
        ),
    )
    monkeypatch.setattr(app.state, "internal_service_token", "image-e2e")
    monkeypatch.setenv("RETURN_AGENT_IMAGE_DIR", str(tmp_path / "images"))
    output = io.BytesIO()
    Image.new("RGB", (32, 24), "blue").save(output, format="PNG")
    source = output.getvalue()
    expected_bytes = sanitize(source, "image/png")[0]
    captured_tasks = []
    activities = []
    worker._activity_sink = activities.append
    with closing(TestClient(app)) as client:
        uploaded = client.post(
            "/attachments",
            data={
                "order_ref": "ORDER-DEMO",
                "subject": "LI-DEMO",
            },
            files={"file": ("synthetic.png", source, "image/png")},
        )
        assert uploaded.status_code == 201, uploaded.text
        attachment = uploaded.json()
        model = OpenAIStructuredOutputModel(
            model_name="gpt-5.6",
            api_key="test",
            temperature=None,
            image_provider=HttpEvidenceImageProvider(
                "http://testserver", "image-e2e", client
            ),
        )

        class WireModel:
            def generate(self, *, task, system_prompt, payload, output_schema):
                expected = original.dependencies.model.generate(
                    task=task,
                    system_prompt=system_prompt,
                    payload=payload,
                    output_schema=output_schema,
                )
                # Demo fixture citations must bind to this upload's real evidence ID.
                answer = json.loads(
                    json.dumps(
                        output_schema.adapter.dump_python(expected, mode="json")
                    ).replace("EV-DEMO", attachment["evidence_id"])
                )

                def invoke(messages):
                    blocks = messages[1].content
                    if task in {
                        ModelTask.ASSESS,
                        ModelTask.PROPOSE_OR_REVISE,
                        ModelTask.REVIEW,
                    }:
                        assert isinstance(blocks, list)
                        assert attachment["evidence_id"] in blocks[1]["text"]
                        assert (
                            base64.b64decode(
                                blocks[2]["image_url"]["url"].split(",", 1)[1]
                            )
                            == expected_bytes
                        )
                        captured_tasks.append(task)
                    else:
                        assert isinstance(blocks, str)
                    wrapped = (
                        output_schema.adapter.json_schema().get("type") != "object"
                    )
                    return {"output": answer} if wrapped else answer

                model._model = SimpleNamespace(
                    with_structured_output=lambda *a, **kw: SimpleNamespace(
                        invoke=invoke
                    )
                )
                return model.generate(
                    task=task,
                    system_prompt=system_prompt,
                    payload=payload,
                    output_schema=output_schema,
                )

        worker._runtime = ReturnAgentRuntime(
            replace(
                original.dependencies,
                model=WireModel(),
                evidence_provider=SqlAlchemyEvidenceProvider(sessions),
            ),
            original.checkpointer,
        )
        created = client.post(
            "/cases",
            json={
                "order_ref": "ORDER-DEMO",
                "user_ref": "demo_customer",
                "initial_message": "商品與外箱到貨時有損壞",
                "attached_artifact_refs": [attachment["artifact_ref"]],
            },
        )
        assert created.status_code == 201, created.text
        assert await bridge.dispatch_outbox_once()
        assert await worker.run_once()
        assert captured_tasks == [
            ModelTask.ASSESS,
            ModelTask.PROPOSE_OR_REVISE,
            ModelTask.REVIEW,
        ]
        events = await redis.xrange(AGENT_EVENT_STREAM)
        terminal = SERVICE_EVENT_ADAPTER.validate_json(events[-1][1][REDIS_BODY_FIELD])
        assert isinstance(terminal, AgentResolvedEvent), terminal
        streams = repr(events) + repr(await redis.xrange(AGENT_COMMAND_STREAM))
        checkpoints = repr(list(original.checkpointer.list(None)))
        assert activities
        for persisted in (streams, checkpoints, repr(activities)):
            assert "data:image" not in persisted
            assert base64.b64encode(expected_bytes).decode() not in persisted
            assert repr(expected_bytes) not in persisted
        assert attachment["artifact_ref"] in checkpoints


def _session_factory() -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with engine.connect() as connection:
        connection.execute(text("PRAGMA foreign_keys=ON"))
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def e2e_components() -> AsyncIterator[
    tuple[
        sessionmaker[Session],
        fakeredis.aioredis.FakeRedis,
        AgentBridge,
        AgentWorker,
    ]
]:
    session_factory = _session_factory()
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    bridge = AgentBridge(
        session_factory=session_factory,
        redis=redis,
        settings=AgentBridgeSettings(
            redis_url="redis://unused",
            event_consumer_name="api-e2e",
            outbox_dispatcher_name="api-e2e",
            event_block_ms=1,
            event_reclaim_idle_ms=1,
            event_reclaim_every=100,
            idle_poll_seconds=0.01,
        ),
    )
    broker = RedisStreamBroker(redis)
    worker = AgentWorker(
        runtime=create_demo_runtime(reason_code=ReasonCode.ITEM_DAMAGED),
        broker=broker,
        journal=InMemoryCommandJournal(),
        consumer_name="agent-e2e",
        block_ms=1,
        reclaim_idle_ms=1,
    )

    previous_session_factory = app.state.session_factory
    previous_outbox = app.state.agent_command_outbox
    app.state.session_factory = session_factory
    app.state.agent_command_outbox = SqlAlchemyAgentCommandOutbox()
    await redis.xgroup_create(
        AGENT_EVENT_STREAM,
        API_EVENT_CONSUMER_GROUP,
        id="0-0",
        mkstream=True,
    )
    await broker.ensure_consumer_group()
    try:
        yield session_factory, redis, bridge, worker
    finally:
        app.state.session_factory = previous_session_factory
        app.state.agent_command_outbox = previous_outbox
        await redis.aclose()


@pytest.mark.asyncio
async def test_case_api_reaches_agent_refund_execution_boundary_without_ui(
    e2e_components: tuple[
        sessionmaker[Session],
        fakeredis.aioredis.FakeRedis,
        AgentBridge,
        AgentWorker,
    ],
) -> None:
    session_factory, redis, bridge, worker = e2e_components
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://api.test") as client:
        created = await client.post(
            "/cases",
            json={
                "order_ref": "ORDER-DEMO",
                "user_ref": "USER-DEMO",
                "initial_message": (
                    "ORDER-DEMO 的喇叭到貨時外箱與商品都已損壞，我要退款"
                ),
            },
        )
        assert created.status_code == 201
        case_ref = created.json()["case_ref"]

        assert await bridge.dispatch_outbox_once() is True
        assert await worker.run_once() is True

        first_run_event_count = await redis.xlen(AGENT_EVENT_STREAM)
        assert first_run_event_count > 1
        terminal_entries = await redis.xrevrange(AGENT_EVENT_STREAM, count=1)
        service_terminal = SERVICE_EVENT_ADAPTER.validate_json(
            terminal_entries[0][1][REDIS_BODY_FIELD]
        )
        assert isinstance(service_terminal, AgentInterruptedEvent), (
            service_terminal.model_dump_json(indent=2)
        )
        assert service_terminal.payload.result.interrupt_payload.kind == (
            "EVIDENCE_REQUEST"
        )
        first_consume_results = [
            await bridge.consume_event_once() for _ in range(first_run_event_count)
        ]
        assert all(first_consume_results)

        awaiting_evidence = await client.get(f"/cases/{case_ref}")
        assert awaiting_evidence.status_code == 200
        assert awaiting_evidence.json()["status"] == "AWAITING_EVIDENCE"
        assert len(awaiting_evidence.json()["evidence_request"]["missing_claims"]) == 2

        resumed = await client.post(
            f"/cases/{case_ref}/messages",
            json={
                "message": "補上同時拍到外箱及商品裂痕的照片",
                "attached_artifact_refs": ["artifact://demo/damage"],
            },
        )
        assert resumed.status_code == 200
        assert resumed.json()["status"] == "OBSERVING"

        assert await bridge.dispatch_outbox_once() is True
        assert await worker.run_once() is True

        published_event_count = await redis.xlen(AGENT_EVENT_STREAM)
        second_run_event_count = published_event_count - first_run_event_count
        assert second_run_event_count > 1
        terminal_entries = await redis.xrevrange(AGENT_EVENT_STREAM, count=1)
        service_terminal = SERVICE_EVENT_ADAPTER.validate_json(
            terminal_entries[0][1][REDIS_BODY_FIELD]
        )
        assert isinstance(service_terminal, AgentResolvedEvent), (
            service_terminal.model_dump_json(indent=2)
        )
        consume_results = [
            await bridge.consume_event_once() for _ in range(second_run_event_count)
        ]

        case = await client.get(f"/cases/{case_ref}")
        assert case.status_code == 200
        assert case.json()["status"] == "EXECUTING"
        assert "risk_route" not in case.json()

    terminal_event = RESOLVED_EVENT_ADAPTER.validate_json(
        terminal_entries[0][1][REDIS_BODY_FIELD]
    )
    handoff = terminal_event.payload.result.resolution_handoff
    assert handoff.case_ref == case_ref
    assert handoff.final_decision.action == "FULL_REFUND"
    assert handoff.final_decision.amount == 1200
    assert handoff.final_decision.currency == "TWD"
    assert consume_results[-1] is False

    command_pending = await redis.xpending(
        AGENT_COMMAND_STREAM,
        "return-agent-workers-v1",
    )
    event_pending = await redis.xpending(
        AGENT_EVENT_STREAM,
        API_EVENT_CONSUMER_GROUP,
    )
    assert command_pending["pending"] == 0
    assert event_pending["pending"] == 1

    with session_factory() as session:
        persisted_case = session.get(CaseRecord, case_ref)
        assert persisted_case is not None
        assert persisted_case.status == "EXECUTING"
        outbox_records = session.query(AgentCommandOutboxRecord).all()
        assert len(outbox_records) == 2
        assert all(record.published_at is not None for record in outbox_records)
        assert session.query(ProcessedAgentEventRecord).count() == (
            published_event_count - 1
        )


@pytest.mark.asyncio
async def test_activity_service_path_survives_evidence_resume(e2e_components):
    from return_agent.activities import ActivityRepository
    from return_agent.activity_bridge import ActivityBridge
    from return_agent_contracts.activity import ACTIVITY_STREAM, Lifecycle, NodeSummary

    sessions, redis, _, worker = e2e_components
    observed = []
    worker._activity_sink = observed.append
    await test_case_api_reaches_agent_refund_execution_boundary_without_ui(e2e_components)
    assert len({e.run_id for e in observed}) == 2
    paused = [e for e in observed if isinstance(e.payload, Lifecycle) and e.payload.phase == "PAUSED"]
    assert paused and paused[0].node == "request_evidence"
    assert not any(isinstance(e.payload, NodeSummary) and e.operation_id == paused[0].operation_id for e in observed)
    projection = ActivityBridge(sessions, redis)
    await projection.setup()
    for event in observed:
        await redis.xadd(ACTIVITY_STREAM, {"body": event.model_dump_json()})
    while await projection.consume_once():
        pass
    page = ActivityRepository(sessions).page(observed[0].case_ref, 0, 500)
    assert len(page.events) == len(observed)
    assert [e.event_id for e in page.events] == [e.event_id for e in observed]
