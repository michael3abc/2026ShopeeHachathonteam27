from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Event

import fakeredis.aioredis
import pytest
from return_agent.agent_bridge import (
    API_EVENT_CONSUMER_GROUP,
    PUBLIC_AGENT_FAILURE_MESSAGE,
    PUBLIC_NODE_FAILURE_MESSAGE,
    AgentBridge,
    AgentBridgeSettings,
    AgentEventGapError,
    AgentEventProjector,
    RefundExecutionUnavailableError,
)
from return_agent.agent_commands import SqlAlchemyAgentCommandOutbox
from return_agent.db.agent_bridge import (
    AgentCommandOutboxRecord,
    AgentEventProjectionCursorRecord,
    ProcessedAgentEventRecord,
    RejectedAgentEventRecord,
)
from return_agent.db.case import CaseEventRecord, CaseRecord
from return_agent.db.models import Base
from return_agent_contracts.models import UserTurn
from return_agent_contracts.service import (
    AGENT_COMMAND_STREAM,
    AGENT_EVENT_STREAM,
    REDIS_BODY_FIELD,
    AgentInterruptedEvent,
    AgentNodeObservedEvent,
    AgentResolvedEvent,
    AgentRunFailedEvent,
    AgentStartCommand,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

TIME = datetime(2026, 9, 8, 10, 0, tzinfo=UTC)


def _session_factory() -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def _case(
    case_ref: str = "CASE-001",
    thread_id: str = "THREAD-001",
) -> CaseRecord:
    return CaseRecord(
        case_ref=case_ref,
        thread_id=thread_id,
        order_ref="ORDER-001",
        user_ref="USER-001",
        status="OBSERVING",
        created_at=TIME,
        updated_at=TIME,
    )


def _command() -> AgentStartCommand:
    return AgentStartCommand(
        command_type="START",
        command_id="COMMAND-001",
        case_ref="CASE-001",
        thread_id="THREAD-001",
        issued_at=TIME,
        payload={
            "order_ref": "ORDER-001",
            "initial_turn": UserTurn(
                turn_id="TURN-001",
                role="USER",
                text="商品損壞",
                received_at=TIME,
            )
        },
    )


def _node_event(
    event_id: str = "EVENT-001",
    *,
    event_index: int = 1,
    phase: str = "ENTER",
    error_message: str | None = None,
) -> AgentNodeObservedEvent:
    return AgentNodeObservedEvent(
        event_type="NODE_OBSERVED",
        event_id=event_id,
        command_id="COMMAND-001",
        case_ref="CASE-001",
        thread_id="THREAD-001",
        event_index=event_index,
        occurred_at=TIME,
        payload={
            "observation": {
                "phase": phase,
                "node": "parse_request",
                "task_ref": "TASK-001",
                "error_message": error_message,
            }
        },
    )


def _evidence_interrupt(event_index: int = 1) -> AgentInterruptedEvent:
    return AgentInterruptedEvent(
        event_type="INTERRUPTED",
        event_id="EVENT-INTERRUPT",
        command_id="COMMAND-001",
        case_ref="CASE-001",
        thread_id="THREAD-001",
        event_index=event_index,
        occurred_at=TIME,
        payload={
            "result": {
                "result_type": "INTERRUPTED",
                "status": "INTERRUPTED",
                "interrupt_payload": {
                    "kind": "EVIDENCE_REQUEST",
                    "case_ref": "CASE-001",
                    "request": {
                        "request_id": "EREQ-001",
                        "missing_claims": [
                            {
                                "claim_id": "DAMAGE_PRESENT_ON_ARRIVAL",
                                "subject": "LI-002",
                            }
                        ],
                        "accepted_evidence_types": ["IMAGE"],
                        "user_message": "請提供外箱與損壞商品照片",
                        "policy_refs": ["POLICY-12:v3#4.2"],
                    },
                },
            }
        },
    )


def _resolution(
    *,
    full_refund: bool,
    execution_blocked: bool = False,
    event_index: int = 1,
) -> AgentResolvedEvent:
    decision = (
        {
            "action": "FULL_REFUND",
            "refund_scope": {"line_item_ids": ["LI-002"]},
            "amount": "1200",
            "currency": "TWD",
            "return_decision": {
                "source": "MODEL_JUDGMENT",
                "requirement": {
                    "required": False,
                    "reason_code": "ITEM_UNSALVAGEABLE",
                },
            },
            "reason_code": "ITEM_DAMAGED",
        }
        if full_refund
        else {
            "action": "DECLINE",
            "refund_scope": {"line_item_ids": []},
            "amount": "0",
            "currency": "TWD",
            "reason_code": "ITEM_DAMAGED",
        }
    )
    return AgentResolvedEvent(
        event_type="RESOLVED",
        event_id="EVENT-RESOLVED",
        command_id="COMMAND-001",
        case_ref="CASE-001",
        thread_id="THREAD-001",
        event_index=event_index,
        occurred_at=TIME,
        payload={
            "result": {
                "result_type": "RESOLUTION",
                "status": "COMPLETED",
                "resolution_handoff": {
                    "case_ref": "CASE-001",
                    "handoff_id": "HANDOFF-001",
                    "outcome_source": ("REVIEWER_APPROVE"),
                    "final_decision": decision,
                    "review_result": {
                        "verdict": "APPROVE",
                        "reviewer_claim_findings": [
                            {
                                "claim_id": "ITEM_PHYSICALLY_DAMAGED",
                                "subject": "LI-002",
                                "status": "SUPPORTED",
                                "explanation": "Visible damage.",
                                "supporting_evidence_refs": [],
                            }
                        ],
                        "revision_reasons": [],
                        "reviewer_prompt_version": "reviewer:2.0",
                        "reviewed_at": TIME,
                    },
                    "execution_blocked": execution_blocked,
                    "emitted_at": TIME,
                },
            }
        },
    )


def _run_failed(message: str) -> AgentRunFailedEvent:
    return AgentRunFailedEvent(
        event_type="RUN_FAILED",
        event_id="EVENT-FAILED",
        command_id="COMMAND-001",
        case_ref="CASE-001",
        thread_id="THREAD-001",
        event_index=1,
        occurred_at=TIME,
        payload={
            "code": "PROVIDER_FAILURE",
            "message": message,
            "retryable": False,
            "failed_node": "parse_request",
        },
    )


def _bridge(
    session_factory: sessionmaker[Session],
    redis,
    *,
    event_reclaim_every: int = 4,
    outbox_dispatcher_name: str | None = None,
) -> AgentBridge:
    return AgentBridge(
        session_factory=session_factory,
        redis=redis,
        settings=AgentBridgeSettings(
            redis_url="redis://unused",
            event_consumer_name="api-test",
            outbox_dispatcher_name=outbox_dispatcher_name,
            event_block_ms=1,
            event_reclaim_idle_ms=1,
            event_reclaim_every=event_reclaim_every,
            idle_poll_seconds=0.01,
        ),
    )


def test_case_and_command_outbox_share_one_transaction() -> None:
    session_factory = _session_factory()
    outbox = SqlAlchemyAgentCommandOutbox()

    with session_factory() as session:
        session.add(_case())
        outbox.enqueue(session, _command())
        session.rollback()

    with session_factory() as session:
        assert session.query(CaseRecord).count() == 0
        assert session.query(AgentCommandOutboxRecord).count() == 0

    with session_factory.begin() as session:
        session.add(_case())
        outbox.enqueue(session, _command())

    with session_factory() as session:
        record = session.get(AgentCommandOutboxRecord, "COMMAND-001")
        assert record is not None
        assert record.payload["case_ref"] == "CASE-001"
        assert record.payload["command_type"] == "START"


@pytest.mark.asyncio
async def test_dispatcher_publishes_then_marks_the_outbox_record() -> None:
    session_factory = _session_factory()
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    with session_factory.begin() as session:
        session.add(_case())
        SqlAlchemyAgentCommandOutbox().enqueue(session, _command())

    assert await _bridge(session_factory, redis).dispatch_outbox_once() is True

    entries = await redis.xrange(AGENT_COMMAND_STREAM)
    assert len(entries) == 1
    assert '"command_id":"COMMAND-001"' in entries[0][1][REDIS_BODY_FIELD]
    with session_factory() as session:
        record = session.get(AgentCommandOutboxRecord, "COMMAND-001")
        assert record is not None
        assert record.published_at is not None
        assert record.attempt_count == 1
        assert record.last_error is None


@pytest.mark.asyncio
async def test_failed_publish_leaves_command_pending_for_retry() -> None:
    class FailingRedis:
        async def xadd(self, *_args, **_kwargs):
            raise ConnectionError("Redis unavailable")

    session_factory = _session_factory()
    with session_factory.begin() as session:
        session.add(_case())
        SqlAlchemyAgentCommandOutbox().enqueue(session, _command())

    with pytest.raises(ConnectionError, match="Redis unavailable"):
        await _bridge(session_factory, FailingRedis()).dispatch_outbox_once()

    with session_factory() as session:
        record = session.get(AgentCommandOutboxRecord, "COMMAND-001")
        assert record is not None
        assert record.published_at is None
        assert record.attempt_count == 1
        assert record.last_error == "ConnectionError: Redis unavailable"
        assert record.claimed_by is None
        assert record.claimed_until is None


@pytest.mark.asyncio
async def test_dispatcher_claim_prevents_routine_duplicate_publication() -> None:
    class BlockingRedis:
        def __init__(self) -> None:
            self.entered = asyncio.Event()
            self.release = asyncio.Event()
            self.published = 0

        async def xadd(self, *_args, **_kwargs):
            self.entered.set()
            await self.release.wait()
            self.published += 1

    session_factory = _session_factory()
    redis = BlockingRedis()
    with session_factory.begin() as session:
        session.add(_case())
        SqlAlchemyAgentCommandOutbox().enqueue(session, _command())
    first = _bridge(session_factory, redis)
    second = _bridge(session_factory, redis)

    publishing = asyncio.create_task(first.dispatch_outbox_once())
    await redis.entered.wait()
    assert await second.dispatch_outbox_once() is False
    redis.release.set()
    assert await publishing is True
    assert redis.published == 1


def test_stale_outbox_lease_cannot_complete_a_new_claim() -> None:
    session_factory = _session_factory()
    with session_factory.begin() as session:
        session.add(_case())
        SqlAlchemyAgentCommandOutbox().enqueue(session, _command())
    first = _bridge(
        session_factory,
        object(),
        outbox_dispatcher_name="shared-dispatcher",
    )
    second = _bridge(
        session_factory,
        object(),
        outbox_dispatcher_name="shared-dispatcher",
    )

    first_claim = first._claim_next_outbox_command()
    assert first_claim is not None
    with session_factory.begin() as session:
        record = session.get(AgentCommandOutboxRecord, "COMMAND-001")
        assert record is not None
        record.claimed_until = datetime.now(UTC) - timedelta(seconds=1)
    second_claim = second._claim_next_outbox_command()
    assert second_claim is not None
    assert first_claim[2] != second_claim[2]

    first._record_publish_success(first_claim[0], first_claim[2])
    with session_factory() as session:
        record = session.get(AgentCommandOutboxRecord, "COMMAND-001")
        assert record is not None
        assert record.published_at is None
        assert record.lease_token == second_claim[2]

    second._record_publish_success(second_claim[0], second_claim[2])
    with session_factory() as session:
        record = session.get(AgentCommandOutboxRecord, "COMMAND-001")
        assert record is not None
        assert record.published_at is not None
        assert record.lease_token is None


def test_projector_is_idempotent_for_duplicate_events() -> None:
    session_factory = _session_factory()
    with session_factory.begin() as session:
        session.add(_case())
    projector = AgentEventProjector(session_factory)

    assert projector.project(_node_event()) is True
    assert projector.project(_node_event()) is False

    with session_factory() as session:
        assert session.query(CaseEventRecord).count() == 1
        assert session.query(ProcessedAgentEventRecord).count() == 1


def test_projector_defers_concurrent_out_of_order_terminal_event() -> None:
    session_factory = _session_factory()
    with session_factory.begin() as session:
        session.add(_case())
    projector = AgentEventProjector(session_factory)
    terminal_was_deferred = Event()

    def project_terminal() -> None:
        with pytest.raises(AgentEventGapError):
            projector.project(_resolution(full_refund=False, event_index=3))
        terminal_was_deferred.set()

    def project_earlier_events() -> None:
        assert terminal_was_deferred.wait(timeout=1)
        projector.project(_node_event(event_index=1))
        projector.project(_node_event("EVENT-002", event_index=2))

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(project_terminal),
            executor.submit(project_earlier_events),
        ]
        for future in futures:
            future.result()
    projector.project(_resolution(full_refund=False, event_index=3))

    with session_factory() as session:
        case = session.get(CaseRecord, "CASE-001")
        assert case is not None
        assert [event.payload["type"] for event in case.events] == [
            "node_enter",
            "node_enter",
            "state_change",
            "state_change",
            "done",
        ]
        cursor = session.get(AgentEventProjectionCursorRecord, "COMMAND-001")
        assert cursor is not None
        assert cursor.last_event_index == 3


@pytest.mark.asyncio
async def test_event_consumer_reclaims_projects_and_acks_after_commit() -> None:
    session_factory = _session_factory()
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    bridge = _bridge(session_factory, redis)
    with session_factory.begin() as session:
        session.add(_case())
    await redis.xgroup_create(
        AGENT_EVENT_STREAM, API_EVENT_CONSUMER_GROUP, id="0-0", mkstream=True
    )
    message_id = await redis.xadd(
        AGENT_EVENT_STREAM,
        {REDIS_BODY_FIELD: _evidence_interrupt().model_dump_json()},
    )
    await redis.xreadgroup(
        API_EVENT_CONSUMER_GROUP,
        "dead-api",
        streams={AGENT_EVENT_STREAM: ">"},
        count=1,
    )
    await asyncio.sleep(0.01)

    assert await bridge.consume_event_once() is True

    pending = await redis.xpending(AGENT_EVENT_STREAM, API_EVENT_CONSUMER_GROUP)
    assert pending["pending"] == 0
    with session_factory() as session:
        case = session.get(CaseRecord, "CASE-001")
        assert case is not None
        assert case.status == "AWAITING_EVIDENCE"
        assert [event.payload["type"] for event in case.events] == [
            "interrupt",
            "state_change",
        ]
        assert session.get(ProcessedAgentEventRecord, "EVENT-INTERRUPT") is not None
    assert message_id is not None


@pytest.mark.asyncio
async def test_pending_event_is_retried_while_new_traffic_continues() -> None:
    session_factory = _session_factory()
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    bridge = _bridge(session_factory, redis, event_reclaim_every=3)
    with session_factory.begin() as session:
        session.add(_case())
    await redis.xgroup_create(
        AGENT_EVENT_STREAM, API_EVENT_CONSUMER_GROUP, id="0-0", mkstream=True
    )
    await redis.xadd(
        AGENT_EVENT_STREAM,
        {
            REDIS_BODY_FIELD: _resolution(
                full_refund=False,
                event_index=2,
            ).model_dump_json()
        },
    )
    await redis.xreadgroup(
        API_EVENT_CONSUMER_GROUP,
        "dead-api",
        streams={AGENT_EVENT_STREAM: ">"},
        count=1,
    )
    await asyncio.sleep(0.01)
    await redis.xadd(
        AGENT_EVENT_STREAM,
        {REDIS_BODY_FIELD: _node_event(event_index=1).model_dump_json()},
    )
    for index in range(4):
        await redis.xadd(
            AGENT_EVENT_STREAM,
            {REDIS_BODY_FIELD: f"invalid-new-event-{index}"},
        )

    for _ in range(3):
        await bridge.consume_event_once()

    with session_factory() as session:
        assert session.get(ProcessedAgentEventRecord, "EVENT-RESOLVED") is not None
        case = session.get(CaseRecord, "CASE-001")
        assert case is not None
        assert case.status == "RESOLVED"


def test_decline_resolution_reaches_terminal_state() -> None:
    session_factory = _session_factory()
    with session_factory.begin() as session:
        session.add(_case())

    AgentEventProjector(session_factory).project(_resolution(full_refund=False))

    with session_factory() as session:
        case = session.get(CaseRecord, "CASE-001")
        assert case is not None
        assert case.status == "RESOLVED"
        assert [event.payload["type"] for event in case.events] == [
            "state_change",
            "state_change",
            "done",
        ]


@pytest.mark.parametrize("outcome", ["SUCCEEDED", "REJECTED", "UNAVAILABLE"])
def test_refund_activity_records_actual_execution_without_affecting_result(outcome):
    from pydantic import TypeAdapter
    from return_agent.activities import ActivityRepository
    from return_agent_contracts.activity import Lifecycle, NodeSummary
    from return_agent_contracts.models import RefundExecutionRecord

    sessions = _session_factory()
    with sessions.begin() as session:
        session.add(_case())
    repository = ActivityRepository(sessions)
    class Executor:
        def execute(self, request):
            live = repository.page("CASE-001", 0, 100).events
            assert [e.payload.phase for e in live] == ["STARTED", "STARTED"]
            if outcome == "UNAVAILABLE":
                raise ConnectionError("private@example.com")
            handoff = request.resolution_handoff
            application = {"status": "APPLIED", "application_ref": "APP-1", "applied_at": TIME} if outcome == "SUCCEEDED" else {"status": "REJECTED", "reason_codes": ["REFUND_REJECTED"], "rejected_at": TIME}
            return TypeAdapter(RefundExecutionRecord).validate_python({"execution_ref": "EXEC-1",
                "handoff_id": handoff.handoff_id, "case_ref": handoff.case_ref, "status": outcome,
                "application_result": application, "created_at": TIME, "updated_at": TIME})
    projector = AgentEventProjector(sessions, refund_execution_provider=Executor())
    if outcome == "UNAVAILABLE":
        with pytest.raises(RefundExecutionUnavailableError):
            projector.project(_resolution(full_refund=True))
    else:
        projector.project(_resolution(full_refund=True))
    events = repository.page("CASE-001", 0, 100).events
    assert all(e.scope == "REFUND" for e in events)
    assert len({e.attempt_id for e in events}) == 1
    assert "private@example.com" not in str([e.model_dump_json() for e in events])
    if outcome == "UNAVAILABLE":
        assert events[-1].payload.phase == "FAILED"
        assert not any(isinstance(e.payload, NodeSummary) for e in events)
    else:
        assert events[-1].payload.facts.outcome == outcome
        assert isinstance(events[-1].payload, NodeSummary)
    assert isinstance(events[0].payload, Lifecycle)
    with sessions() as session:
        assert session.get(CaseRecord, "CASE-001").status == {
            "SUCCEEDED": "RESOLVED", "REJECTED": "ESCALATED", "UNAVAILABLE": "EXECUTING"}[outcome]


def test_refund_resolution_stays_unprocessed_until_executor_exists() -> None:
    session_factory = _session_factory()
    with session_factory.begin() as session:
        session.add(_case())

    with pytest.raises(RefundExecutionUnavailableError):
        AgentEventProjector(session_factory).project(_resolution(full_refund=True))
    with pytest.raises(RefundExecutionUnavailableError):
        AgentEventProjector(session_factory).project(_resolution(full_refund=True))

    with session_factory() as session:
        case = session.get(CaseRecord, "CASE-001")
        assert case is not None
        assert case.status == "EXECUTING"
        assert [event.payload["type"] for event in case.events] == ["state_change"]
        assert session.query(ProcessedAgentEventRecord).count() == 0


@pytest.mark.asyncio
async def test_refund_event_is_not_acked_before_executor_exists() -> None:
    session_factory = _session_factory()
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    bridge = _bridge(session_factory, redis)
    with session_factory.begin() as session:
        session.add(_case())
    await redis.xgroup_create(
        AGENT_EVENT_STREAM, API_EVENT_CONSUMER_GROUP, id="0-0", mkstream=True
    )
    await redis.xadd(
        AGENT_EVENT_STREAM,
        {REDIS_BODY_FIELD: _resolution(full_refund=True).model_dump_json()},
    )

    assert await bridge.consume_event_once() is False

    pending = await redis.xpending(AGENT_EVENT_STREAM, API_EVENT_CONSUMER_GROUP)
    assert pending["pending"] == 1
    with session_factory() as session:
        assert session.query(ProcessedAgentEventRecord).count() == 0


@pytest.mark.asyncio
async def test_invalid_event_is_persisted_before_ack() -> None:
    session_factory = _session_factory()
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    bridge = _bridge(session_factory, redis)
    await redis.xgroup_create(
        AGENT_EVENT_STREAM, API_EVENT_CONSUMER_GROUP, id="0-0", mkstream=True
    )
    await redis.xadd(AGENT_EVENT_STREAM, {REDIS_BODY_FIELD: "not-json"})

    assert await bridge.consume_event_once() is True
    pending = await redis.xpending(AGENT_EVENT_STREAM, API_EVENT_CONSUMER_GROUP)
    assert pending["pending"] == 0
    with session_factory() as session:
        rejection = session.query(RejectedAgentEventRecord).one()
        assert rejection.raw_body == "not-json"
        assert rejection.error_code == "INVALID_AGENT_EVENT"


@pytest.mark.asyncio
async def test_inapplicable_event_is_recorded_and_fails_case_closed() -> None:
    session_factory = _session_factory()
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    bridge = _bridge(session_factory, redis)
    with session_factory.begin() as session:
        session.add(_case())
    await redis.xgroup_create(
        AGENT_EVENT_STREAM, API_EVENT_CONSUMER_GROUP, id="0-0", mkstream=True
    )
    event = _node_event().model_copy(update={"thread_id": "WRONG-THREAD"})
    await redis.xadd(
        AGENT_EVENT_STREAM,
        {REDIS_BODY_FIELD: event.model_dump_json()},
    )

    assert await bridge.consume_event_once() is True
    with session_factory() as session:
        case = session.get(CaseRecord, "CASE-001")
        assert case is not None
        assert case.status == "ESCALATED"
        assert [item.payload["type"] for item in case.events] == [
            "error",
            "state_change",
            "done",
        ]
        assert session.query(RejectedAgentEventRecord).count() == 1


@pytest.mark.asyncio
async def test_rejected_command_stream_rejects_later_events() -> None:
    session_factory = _session_factory()
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    bridge = _bridge(session_factory, redis)
    with session_factory.begin() as session:
        session.add(_case())
    await redis.xgroup_create(
        AGENT_EVENT_STREAM, API_EVENT_CONSUMER_GROUP, id="0-0", mkstream=True
    )
    rejected = _node_event().model_copy(update={"thread_id": "WRONG-THREAD"})
    await redis.xadd(
        AGENT_EVENT_STREAM,
        {REDIS_BODY_FIELD: rejected.model_dump_json()},
    )
    assert await bridge.consume_event_once() is True

    await redis.xadd(
        AGENT_EVENT_STREAM,
        {
            REDIS_BODY_FIELD: _node_event(
                "EVENT-002",
                event_index=2,
            ).model_dump_json()
        },
    )
    assert await bridge.consume_event_once() is True

    pending = await redis.xpending(AGENT_EVENT_STREAM, API_EVENT_CONSUMER_GROUP)
    assert pending["pending"] == 0
    with session_factory() as session:
        cursor = session.get(AgentEventProjectionCursorRecord, "COMMAND-001")
        assert cursor is not None
        assert cursor.terminated_at is not None
        assert session.query(RejectedAgentEventRecord).count() == 2


@pytest.mark.asyncio
async def test_pending_refund_does_not_block_later_reclaimable_event() -> None:
    session_factory = _session_factory()
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    bridge = _bridge(session_factory, redis)
    with session_factory.begin() as session:
        session.add(_case())
    await redis.xgroup_create(
        AGENT_EVENT_STREAM, API_EVENT_CONSUMER_GROUP, id="0-0", mkstream=True
    )
    await redis.xadd(
        AGENT_EVENT_STREAM,
        {REDIS_BODY_FIELD: _resolution(full_refund=True).model_dump_json()},
    )
    await redis.xadd(
        AGENT_EVENT_STREAM,
        {REDIS_BODY_FIELD: "later-poison-event"},
    )
    await redis.xreadgroup(
        API_EVENT_CONSUMER_GROUP,
        "dead-api",
        streams={AGENT_EVENT_STREAM: ">"},
        count=2,
    )
    await asyncio.sleep(0.01)

    assert await bridge.consume_event_once() is False
    assert await bridge.consume_event_once() is True

    pending = await redis.xpending(AGENT_EVENT_STREAM, API_EVENT_CONSUMER_GROUP)
    assert pending["pending"] == 1
    with session_factory() as session:
        rejection = session.query(RejectedAgentEventRecord).one()
        assert rejection.raw_body == "later-poison-event"


@pytest.mark.asyncio
async def test_event_id_collision_is_rejected_and_fails_target_case_closed() -> None:
    session_factory = _session_factory()
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    bridge = _bridge(session_factory, redis)
    with session_factory.begin() as session:
        session.add(_case())
        session.add(_case("CASE-002", "THREAD-002"))
    await redis.xgroup_create(
        AGENT_EVENT_STREAM, API_EVENT_CONSUMER_GROUP, id="0-0", mkstream=True
    )
    await redis.xadd(
        AGENT_EVENT_STREAM,
        {REDIS_BODY_FIELD: _node_event().model_dump_json()},
    )
    assert await bridge.consume_event_once() is True

    collision = _node_event().model_copy(
        update={
            "case_ref": "CASE-002",
            "thread_id": "THREAD-002",
            "command_id": "COMMAND-002",
        }
    )
    await redis.xadd(
        AGENT_EVENT_STREAM,
        {REDIS_BODY_FIELD: collision.model_dump_json()},
    )
    assert await bridge.consume_event_once() is True

    with session_factory() as session:
        original = session.get(CaseRecord, "CASE-001")
        target = session.get(CaseRecord, "CASE-002")
        processed = session.get(ProcessedAgentEventRecord, "EVENT-001")
        assert original is not None and original.status == "OBSERVING"
        assert target is not None and target.status == "ESCALATED"
        assert processed is not None
        assert processed.case_ref == "CASE-001"
        assert processed.command_id == "COMMAND-001"
        assert processed.event_index == 1
        assert len(processed.payload_hash) == 64
        assert session.query(RejectedAgentEventRecord).count() == 1


@pytest.mark.asyncio
async def test_event_id_payload_collision_is_not_treated_as_a_retry() -> None:
    session_factory = _session_factory()
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    bridge = _bridge(session_factory, redis)
    with session_factory.begin() as session:
        session.add(_case())
    await redis.xgroup_create(
        AGENT_EVENT_STREAM, API_EVENT_CONSUMER_GROUP, id="0-0", mkstream=True
    )
    await redis.xadd(
        AGENT_EVENT_STREAM,
        {REDIS_BODY_FIELD: _node_event().model_dump_json()},
    )
    assert await bridge.consume_event_once() is True
    await redis.xadd(
        AGENT_EVENT_STREAM,
        {REDIS_BODY_FIELD: _node_event(phase="EXIT").model_dump_json()},
    )

    assert await bridge.consume_event_once() is True

    with session_factory() as session:
        case = session.get(CaseRecord, "CASE-001")
        assert case is not None
        assert case.status == "ESCALATED"
        assert session.query(ProcessedAgentEventRecord).count() == 1
        assert session.query(RejectedAgentEventRecord).count() == 1


@pytest.mark.parametrize(
    ("event", "public_message"),
    [
        (
            _run_failed("token=secret https://private.example"),
            PUBLIC_AGENT_FAILURE_MESSAGE,
        ),
        (
            _node_event(
                phase="ERROR",
                error_message="password=secret database.internal",
            ),
            PUBLIC_NODE_FAILURE_MESSAGE,
        ),
    ],
)
def test_projector_redacts_internal_error_details(event, public_message: str) -> None:
    session_factory = _session_factory()
    with session_factory.begin() as session:
        session.add(_case())

    AgentEventProjector(session_factory).project(event)

    with session_factory() as session:
        case = session.get(CaseRecord, "CASE-001")
        assert case is not None
        payloads = [item.payload for item in case.events]
        assert payloads[0]["payload"]["message"] == public_message
        assert "secret" not in str(payloads)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "result",
    [
        {"status": "OK", "query_summary": "Current evidence summary", "hits": []},
        {"status": "UNAVAILABLE", "error_code": "SUMMARY_UNAVAILABLE", "hits": []},
    ],
)
async def test_memory_result_redis_projection_and_replay(result):
    sessions = _session_factory()
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    bridge = _bridge(sessions, redis)
    with sessions.begin() as session:
        session.add(_case())
    raw = _node_event(phase="EXIT").model_dump(mode="json")
    raw["payload"]["observation"].update(
        node="retrieve_memory", memory_retrieval=result
    )
    event = AgentNodeObservedEvent.model_validate(raw)
    await redis.xgroup_create(
        AGENT_EVENT_STREAM, API_EVENT_CONSUMER_GROUP, id="0-0", mkstream=True
    )
    for _ in range(2):
        await redis.xadd(
            AGENT_EVENT_STREAM, {REDIS_BODY_FIELD: event.model_dump_json()}
        )
        assert await bridge.consume_event_once()
    with sessions() as session:
        case = session.get(CaseRecord, "CASE-001")
        events = case.events
        assert [e.payload["type"] for e in events] == ["node_exit", "memory_retrieval"]
        assert events[-1].payload[
            "payload"
        ] == event.payload.observation.memory_retrieval.model_dump(mode="json")
    assert (await redis.xpending(AGENT_EVENT_STREAM, API_EVENT_CONSUMER_GROUP))[
        "pending"
    ] == 0
    await redis.aclose()


@pytest.mark.asyncio
async def test_reviewer_gate_survives_redis_replay_without_duplicate_event():
    from decimal import Decimal

    from return_agent_contracts.enums import ResolutionAction
    from return_agent_contracts.review_gates import (
        ReviewerGateConfig,
        evaluate_review_gate,
    )

    sessions = _session_factory()
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    bridge = _bridge(sessions, redis)
    with sessions.begin() as session:
        session.add(_case())
    gate = evaluate_review_gate(ResolutionAction.FULL_REFUND, Decimal(5001), "TWD", ReviewerGateConfig())
    raw = _node_event(phase="EXIT").model_dump(mode="json")
    raw["payload"]["observation"].update(node="reviewer", review_gate=gate.model_dump(mode="json"))
    event = AgentNodeObservedEvent.model_validate(raw)
    await redis.xgroup_create(AGENT_EVENT_STREAM, API_EVENT_CONSUMER_GROUP, id="0-0", mkstream=True)
    for _ in range(2):
        await redis.xadd(AGENT_EVENT_STREAM, {REDIS_BODY_FIELD: event.model_dump_json()})
        assert await bridge.consume_event_once()
    with sessions() as session:
        events = session.get(CaseRecord, "CASE-001").events
        assert len(events) == 1
        assert events[0].payload["payload"]["review_gate"] == gate.model_dump(mode="json")
    assert (await redis.xpending(AGENT_EVENT_STREAM, API_EVENT_CONSUMER_GROUP))["pending"] == 0
    await redis.aclose()
