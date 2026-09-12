import socket
import threading
import time
from contextlib import contextmanager
from dataclasses import replace
from decimal import Decimal

import pytest
import uvicorn
from pydantic import SecretStr, TypeAdapter
from sqlalchemy import func, select

from return_agent_contracts.domain import ReviewerGateConfig
from return_agent_contracts.messages import AgentCommand, COMMAND_STREAM, COMMAND_GROUP, EVENT_STREAM
from return_agent_contracts.providers import ContractConflict
from return_agent_contracts.workflow import AgentServiceEvent
from return_agent.main import create_app
from return_agent.settings import Settings
from return_agent.db import CommandOutboxRow, MockRefundReceiptRow, ProcessedAgentEventRow, RefundReservationRow, ResolutionJobRow
from return_agent.projection import EventOutOfOrder, EventProjector
from return_agent.refunds import RefundService, SimulatedRefundApplication
from return_agent.workers import CommandDispatcher, EventConsumer, ResolutionWorker
from return_agent_service.checkpoint import checkpoint_saver
from return_agent_service.db import CommandRow, EventOutboxRow, make_sessions
from return_agent_service.fake_model import TypedFakeModel
from return_agent_service.journal import CommandJournal
from return_agent_service.providers import HttpProviders
from return_agent_service.workers import CommandWorker, EventPublisher
from return_agent_runtime.graph import ReturnRuntime
from return_agent_runtime.ports import RuntimeDependencies


@contextmanager
def http_api(cases):
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(create_app(Settings(internal_service_token=SecretStr("integration-token")), store=cases), log_level="error", access_log=False))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.01)
    assert server.started
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(5)
        sock.close()
        assert not thread.is_alive()


@pytest.fixture
def bridge(trusted, agent_database, test_redis):
    caps = trusted[0]
    engine, url, schema = agent_database
    journal = CommandJournal(make_sessions(engine))
    model = TypedFakeModel()
    with http_api(caps.cases) as base_url:
        providers = HttpProviders(base_url, "integration-token")
        dependencies = RuntimeDependencies(model=model, context=providers, policy=providers, evidence=providers, verification=providers, human=providers, memory=providers, clock=caps.cases.clock, gates=ReviewerGateConfig())
        @contextmanager
        def factory(observer):
            with checkpoint_saver(url, schema=schema) as saver:
                yield ReturnRuntime(replace(dependencies, observer=observer), saver)
        worker = CommandWorker(engine, journal, test_redis, factory, consumer="integration-worker", min_idle_ms=0)
        publisher = EventPublisher(journal, test_redis)
        consumer = EventConsumer(caps.cases, test_redis, consumer="integration-api", min_idle_ms=0)
        dispatcher = CommandDispatcher(caps.cases, test_redis)
        refunds = ResolutionWorker(caps.cases, RefundService(caps, SimulatedRefundApplication(caps)))
        yield dict(caps=caps, journal=journal, model=model, factory=factory, worker=worker, publisher=publisher, consumer=consumer, dispatcher=dispatcher, refunds=refunds, redis=test_redis, engine=engine)
        providers.close()


def pump(bridge):
    bridge["dispatcher"].tick()
    bridge["worker"].tick()
    bridge["publisher"].tick()
    for _ in range(10):
        if not bridge["consumer"].tick():
            break
    bridge["refunds"].tick()


def test_http_redis_durable_human_interrupt_and_resume(bridge, trusted):
    from return_agent.human_review import HumanReviewService
    from return_agent_contracts.human import EditReviewDecision
    b, caps = bridge, bridge["caps"]
    case_ref = trusted[2].case_ref
    pump(b)
    detail = caps.cases.detail(case_ref)
    assert detail.status == "AWAITING_HUMAN_REVIEW", [event.model_dump() for event in caps.cases.events(case_ref)]
    assert detail.human_review.amount == Decimal("7400")
    # Re-create workers and checkpoint connections; resume must preserve the same dossier.
    review_calls = b["model"].counts["REVIEW"]
    edit = EditReviewDecision.model_validate({"decision": "EDIT", "handoff_id": detail.human_review.handoff_id, "review_note": "限縮為有明確檢測需要的線材退款。", "generalizable": True, "correction_reason_code": "SCOPE_INCORRECT", "corrected_decision": {"action": "FULL_REFUND", "refund_scope": {"line_item_ids": ["item-two"]}, "return_decision": {"source": "HUMAN_REVIEW", "requirement": {"required": True, "reason_code": "RETURN_REQUIRED_FOR_INSPECTION"}}}})
    HumanReviewService(caps).complete(case_ref, edit)
    b["worker"] = CommandWorker(b["engine"], b["journal"], b["redis"], b["factory"], consumer="restarted-worker", min_idle_ms=0)
    pump(b)
    detail = caps.cases.detail(case_ref)
    assert detail.status == "RESOLVED", [event.model_dump() for event in caps.cases.events(case_ref)]
    assert detail.final_resolution.final_decision.amount == Decimal("1200")
    assert detail.refund_execution.application_result.status == "APPLIED"
    assert b["model"].counts["REVIEW"] == review_calls
    with b["journal"].sessions() as session:
        commands = list(session.scalars(select(CommandRow).order_by(CommandRow.created_at)))
        assert len(commands) == 2 and all(row.status == "TERMINAL" for row in commands)
        assert commands[-1].distillation_input["human_review_result"]["decision"] == "EDIT"
    assert b["redis"].xpending(COMMAND_STREAM, COMMAND_GROUP)["pending"] == 0


def test_projection_reordering_hash_conflict_and_replay_are_atomic(bridge, trusted, monkeypatch):
    b, caps = bridge, bridge["caps"]
    b["dispatcher"].tick()
    b["worker"].tick()
    with b["journal"].sessions() as session:
        events = [TypeAdapter(AgentServiceEvent).validate_python(row.payload) for row in session.scalars(select(EventOutboxRow).order_by(EventOutboxRow.event_index))]
    projector = EventProjector(caps.cases)
    with pytest.raises(EventOutOfOrder):
        projector.project(events[1])
    with caps.sessions() as session:
        assert session.scalar(select(func.count()).select_from(ProcessedAgentEventRow)) == 0
    original = caps.cases.append_event
    def fail(*args):
        raise RuntimeError("synthetic projection failure")
    monkeypatch.setattr(caps.cases, "append_event", fail)
    with pytest.raises(RuntimeError):
        projector.project(events[0])
    monkeypatch.setattr(caps.cases, "append_event", original)
    assert projector.project(events[0]) and not projector.project(events[0])
    with pytest.raises(ContractConflict):
        projector.project(events[0].model_copy(update={"occurred_at": caps.cases.clock()}))
    assert projector.project(events[1])


def test_terminal_command_redelivery_does_not_rerun_model(bridge):
    b = bridge
    pump(b)
    calls = len(b["model"].calls)
    with b["journal"].sessions() as session:
        row = session.scalar(select(CommandRow))
        body = TypeAdapter(AgentCommand).validate_python(row.request).model_dump_json()
    b["redis"].xadd(COMMAND_STREAM, {"body": body})
    b["worker"].tick()
    assert len(b["model"].calls) == calls


def test_checkpoint_survives_crash_before_journal_terminal_commit(bridge, monkeypatch):
    b = bridge
    b["journal"].lease_seconds = 0
    original = b["journal"].complete
    def crash(*args):
        raise RuntimeError("synthetic crash after checkpoint")
    monkeypatch.setattr(b["journal"], "complete", crash)
    b["dispatcher"].tick()
    with pytest.raises(RuntimeError):
        b["worker"].tick()
    calls = len(b["model"].calls)
    assert b["redis"].xpending(COMMAND_STREAM, COMMAND_GROUP)["pending"] == 1
    monkeypatch.setattr(b["journal"], "complete", original)
    replacement = CommandWorker(b["engine"], b["journal"], b["redis"], b["factory"], consumer="after-crash", min_idle_ms=0)
    assert replacement.tick() == 1
    assert len(b["model"].calls) == calls
    with b["journal"].sessions() as session:
        assert session.scalar(select(CommandRow)).status == "TERMINAL"
    assert b["redis"].xpending(COMMAND_STREAM, COMMAND_GROUP)["pending"] == 0


def test_pending_out_of_order_event_does_not_starve_earlier_unread_event(bridge):
    b = bridge
    b["dispatcher"].tick()
    b["worker"].tick()
    with b["journal"].sessions() as session:
        events = [TypeAdapter(AgentServiceEvent).validate_python(row.payload) for row in session.scalars(select(EventOutboxRow).order_by(EventOutboxRow.event_index).limit(2))]
    b["redis"].xadd(EVENT_STREAM, {"body": events[1].model_dump_json()})
    b["consumer"].tick()
    b["redis"].xadd(EVENT_STREAM, {"body": events[0].model_dump_json()})
    b["consumer"].tick()
    b["consumer"].tick()
    with b["caps"].sessions() as session:
        assert session.scalar(select(func.count()).select_from(ProcessedAgentEventRow)) == 2


def test_dispatcher_unknown_publish_result_resends_same_command(bridge, monkeypatch):
    from datetime import timedelta
    from redis.exceptions import ConnectionError
    b = bridge
    original = b["redis"].xadd
    def interrupted(*args, **kwargs):
        original(*args, **kwargs)
        raise ConnectionError("synthetic disconnect after XADD")
    monkeypatch.setattr(b["redis"], "xadd", interrupted)
    with pytest.raises(ConnectionError):
        b["dispatcher"].tick()
    with b["caps"].sessions.begin() as session:
        row = session.scalar(select(CommandOutboxRow))
        assert row.published_at is None
        row.claimed_until = b["caps"].cases.clock() - timedelta(seconds=1)
    monkeypatch.setattr(b["redis"], "xadd", original)
    b["dispatcher"].tick()
    assert b["redis"].xlen(COMMAND_STREAM) == 2
    b["worker"].tick()
    assert b["model"].counts["REVIEW"] == 1
    with b["journal"].sessions() as session:
        assert session.scalar(select(func.count()).select_from(CommandRow)) == 1
