from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from return_agent.cases import CaseStateConflict
from return_agent.db import Base, CaseEventRow, CaseRow, CommandOutboxRow
from return_agent.main import create_app
from return_agent_contracts.public import CreateCaseRequest, SendMessageRequest


def request():
    return CreateCaseRequest(order_ref="order-test", user_ref="demo_customer", initial_message="品項外殼有裂痕", attached_artifact_refs=["artifact-test"])


def awaiting(store, case_ref, status="AWAITING_EVIDENCE"):
    with store.sessions.begin() as session:
        case = store.locked_case(session, case_ref)
        store.transition(session, case, status, "Awaiting customer evidence", "request_evidence")


def test_empty_database_migration_matches_models(database):
    engine, config = database
    with engine.begin() as connection:
        context = MigrationContext.configure(connection)
        assert compare_metadata(context, Base.metadata) == []
        config.attributes["connection"] = connection
        command.upgrade(config, "head")


def test_c15_create_persists_case_turn_and_one_start_atomically(store):
    ref = store.create(request())
    with store.sessions() as session:
        case = session.get(CaseRow, ref)
        assert case.status == "OBSERVING"
        turns = list(session.scalars(select(CaseEventRow).where(CaseEventRow.case_ref == ref)))
        commands = list(session.scalars(select(CommandOutboxRow).where(CommandOutboxRow.case_ref == ref)))
        assert len(turns) == len(commands) == 1
        assert commands[0].payload["command_type"] == "START"
        assert commands[0].payload["thread_id"] == case.thread_id
        assert commands[0].published_at is None


def test_c15_failure_before_outbox_commit_leaves_no_orphans(store, monkeypatch):
    def fail(*args): raise RuntimeError("injected outbox failure")
    monkeypatch.setattr(store, "enqueue", fail)
    with pytest.raises(RuntimeError): store.create(request())
    with store.sessions() as session:
        for table in (CaseRow, CaseEventRow, CommandOutboxRow):
            assert session.scalar(select(func.count()).select_from(table)) == 0


def test_c15_concurrent_messages_produce_one_resume(store):
    ref = store.create(request())
    awaiting(store, ref)
    barrier = Barrier(2)
    def submit():
        barrier.wait(timeout=5)
        try:
            store.message(ref, SendMessageRequest(message="補充照片", attached_artifact_refs=["artifact-second"]))
            return "accepted"
        except CaseStateConflict:
            return "conflict"
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: submit(), range(2)))
    assert sorted(results) == ["accepted", "conflict"]
    with store.sessions() as session:
        commands = list(session.scalars(select(CommandOutboxRow).where(CommandOutboxRow.case_ref == ref)))
        assert len(commands) == 2
        assert store.detail(ref).status == "OBSERVING"
        events = list(session.scalars(select(CaseEventRow).where(CaseEventRow.case_ref == ref).order_by(CaseEventRow.seq)))
        assert [event.seq for event in events] == list(range(1, len(events)+1))


def test_resume_failure_rolls_back_turn_status_and_outbox(store, monkeypatch):
    ref = store.create(request())
    awaiting(store, ref)
    def fail(*args): raise RuntimeError("injected resume enqueue failure")
    monkeypatch.setattr(store, "enqueue", fail)
    with pytest.raises(RuntimeError):
        store.message(ref, SendMessageRequest(message="補充", attached_artifact_refs=["artifact-second"]))
    assert store.detail(ref).status == "AWAITING_EVIDENCE"
    with store.sessions() as session:
        assert session.scalar(select(func.count()).select_from(CommandOutboxRow)) == 1
        assert session.scalar(select(func.count()).select_from(CaseEventRow)) == 2


def test_public_routes_validate_state_and_do_not_expose_thread(store):
    with TestClient(create_app(store=store)) as client:
        response = client.post("/cases", json=request().model_dump(mode="json"))
        assert response.status_code == 201
        ref = response.json()["case_ref"]
        detail = client.get(f"/cases/{ref}")
        assert detail.status_code == 200 and "thread_id" not in detail.json()
        assert client.get("/cases/unknown").status_code == 404
        assert client.post(f"/cases/{ref}/messages", json={"message": "再送一次"}).status_code == 409
        awaiting(store, ref)
        assert client.post(f"/cases/{ref}/messages", json={"message": "缺照片"}).status_code == 422
        assert client.post("/cases", json={**request().model_dump(), "amount": "1"}).status_code == 422


def test_c17_case_event_cursor_can_have_user_turn_holes(store):
    ref = store.create(request())
    awaiting(store, ref)
    store.message(ref, SendMessageRequest(message="補圖", attached_artifact_refs=["artifact-second"]))
    assert [event.seq for event in store.events(ref)] == [2, 4]
    assert [event.seq for event in store.events(ref, after_seq=2)] == [4]


def test_terminal_case_sse_replays_then_closes_and_validates_cursor(store):
    ref = store.create(request())
    with store.sessions.begin() as session:
        case = store.locked_case(session, ref)
        store.transition(session, case, "ESCALATED", "Cannot proceed safely", "terminate_automation")
    with TestClient(create_app(store=store)) as client:
        response = client.get(f"/cases/{ref}/events")
        assert response.status_code == 200
        assert "id: 2\nevent: state_change" in response.text
        assert client.get(f"/cases/{ref}/events", headers={"Last-Event-ID": "2"}).text == ""
        assert client.get(f"/cases/{ref}/events", headers={"Last-Event-ID": "-1"}).status_code == 400


def test_create_has_no_client_idempotency_contract(store):
    assert store.create(request()) != store.create(request())
