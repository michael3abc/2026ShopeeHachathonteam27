from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from return_agent.app import app, get_session
from return_agent.db.case import (
    AGENT_EVENT,
    USER_TURN,
    CaseEventRecord,
    CaseRecord,
    append_agent_event,
)
from return_agent.db.models import Base
from return_agent.store import CaseStore, IllegalTransitionError
from return_agent_contracts.service import AgentResumeCommand, AgentStartCommand
from return_agent_contracts.ui import CaseStatus
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


class RecordingOutbox:
    def __init__(self) -> None:
        self.commands: list[AgentStartCommand | AgentResumeCommand] = []

    def enqueue(self, _session: Session, command) -> None:
        self.commands.append(command)


class FailingOutbox:
    def enqueue(self, _session: Session, _command) -> None:
        raise RuntimeError("outbox unavailable")


@pytest.fixture
def session_factory() -> sessionmaker[Session]:
    # TestClient runs requests on another thread, so the in-memory database
    # must be one shared connection rather than one per thread.
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with engine.connect() as connection:
        connection.execute(text("PRAGMA foreign_keys=ON"))
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture
def client(session_factory: sessionmaker[Session]) -> Iterator[TestClient]:
    def _session() -> Iterator[Session]:
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = _session
    app.state.session_factory = session_factory
    app.state.agent_command_outbox = RecordingOutbox()
    yield TestClient(app)
    app.dependency_overrides.clear()
    app.state.agent_command_outbox = None


def _create(client: TestClient) -> str:
    response = client.post(
        "/cases",
        json={
            "order_ref": "ORDER-001",
            "user_ref": "USER-001",
            "initial_message": "喇叭到貨就破了，我要退款",
        },
    )
    assert response.status_code == 201
    return response.json()["case_ref"]


def _interrupt_event(case_ref: str, seq: int) -> dict:
    return {
        "type": "interrupt",
        "case_ref": case_ref,
        "seq": seq,
        "ts": "2026-09-06T10:00:00Z",
        "node": "request_evidence",
        "payload": {
            "interrupt_kind": "EVIDENCE_REQUEST",
            "request": {
                "case_ref": case_ref,
                "request_id": "REQ-1",
                "user_message": "請拍一張同時包含外箱與破損處的照片",
                "missing_claims": [
                    {"claim_id": "DAMAGE_PRESENT_ON_ARRIVAL", "subject": "LI-002"}
                ],
                "accepted_evidence_types": ["IMAGE"],
                "policy_refs": ["POLICY-12:v3#4.2"],
            },
        },
    }


def test_health_is_served_by_the_same_app(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}


def test_create_then_read(client: TestClient) -> None:
    case_ref = _create(client)

    case = client.get(f"/cases/{case_ref}").json()
    assert case["case_ref"] == case_ref
    assert case["order_ref"] == "ORDER-001"
    assert case["status"] == CaseStatus.OBSERVING.value
    assert case["human_review"] is None
    assert case["evidence_request"] is None
    # thread_id is backend-private and must not reach the UI.
    assert "thread_id" not in case


def test_creating_a_case_records_the_opening_turn(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    case_ref = _create(client)

    with session_factory() as session:
        events = session.query(CaseEventRecord).filter_by(case_ref=case_ref).all()
        assert [(event.seq, event.kind) for event in events] == [(1, USER_TURN)]
        assert events[0].payload["message"] == "喇叭到貨就破了，我要退款"
        command = client.app.state.agent_command_outbox.commands[-1]
        assert events[0].payload["turn_ref"] == command.payload.initial_turn.turn_id


def test_creating_a_case_forwards_attached_artifacts(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    response = client.post(
        "/cases",
        json={
            "order_ref": "ORDER-001",
            "user_ref": "USER-001",
            "initial_message": "喇叭到貨就破了，我要退款",
            "attached_artifact_refs": ["artifact://demo/damage"],
        },
    )
    assert response.status_code == 201
    case_ref = response.json()["case_ref"]

    with session_factory() as session:
        events = session.query(CaseEventRecord).filter_by(case_ref=case_ref).all()
        assert events[0].payload["attached_artifact_refs"] == ["artifact://demo/damage"]

    command = client.app.state.agent_command_outbox.commands[-1]
    assert command.payload.initial_turn.attached_artifact_refs == [
        "artifact://demo/damage"
    ]


def test_each_case_gets_its_own_thread(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    first = _create(client)
    second = _create(client)

    with session_factory() as session:
        store = CaseStore(session)
        assert store.get(first).thread_id != store.get(second).thread_id


def test_unknown_case_is_404(client: TestClient) -> None:
    assert client.get("/cases/CASE-NOPE").status_code == 404
    assert (
        client.post("/cases/CASE-NOPE/messages", json={"message": "hi"}).status_code
        == 404
    )


def test_invalid_create_payload_is_422(client: TestClient) -> None:
    response = client.post(
        "/cases",
        json={"order_ref": "ORDER-001", "user_ref": "USER-001", "initial_message": ""},
    )
    assert response.status_code == 422


def test_message_is_appended_after_the_opening_turn(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    case_ref = _create(client)
    with session_factory.begin() as session:
        CaseStore(session).transition(case_ref, CaseStatus.AWAITING_CLARIFICATION)

    response = client.post(
        f"/cases/{case_ref}/messages",
        json={"message": "補上照片", "attached_artifact_refs": ["artifact://EV-1"]},
    )
    assert response.status_code == 200
    assert response.json()["case_ref"] == case_ref
    assert response.json()["status"] == CaseStatus.OBSERVING.value

    with session_factory() as session:
        events = (
            session.query(CaseEventRecord)
            .filter_by(case_ref=case_ref)
            .order_by(CaseEventRecord.seq)
            .all()
        )
        assert [event.seq for event in events] == [1, 2, 3]
        assert events[1].payload["attached_artifact_refs"] == ["artifact://EV-1"]
        assert events[2].payload["type"] == "state_change"
        assert events[2].payload["payload"] == {
            "from_status": "AWAITING_CLARIFICATION",
            "to_status": "OBSERVING",
            "reason": "User supplied the requested Agent input.",
        }


def test_awaiting_evidence_surfaces_the_pending_request(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    case_ref = _create(client)
    with session_factory.begin() as session:
        session.add(
            CaseEventRecord(
                case_ref=case_ref,
                seq=2,
                kind=AGENT_EVENT,
                payload=_interrupt_event(case_ref, 2),
            )
        )
        CaseStore(session).transition(case_ref, CaseStatus.AWAITING_EVIDENCE)

    case = client.get(f"/cases/{case_ref}").json()
    assert case["status"] == CaseStatus.AWAITING_EVIDENCE.value
    assert case["evidence_request"]["request_id"] == "REQ-1"
    # The other interrupt slot stays empty: a case advertises only what it awaits.
    assert case["human_review"] is None


def test_unconfigured_outbox_rejects_create_without_storing_case(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    app.state.agent_command_outbox = None

    response = client.post(
        "/cases",
        json={
            "order_ref": "ORDER-001",
            "user_ref": "USER-001",
            "initial_message": "需要退款",
        },
    )

    assert response.status_code == 503
    with session_factory() as session:
        assert session.query(CaseRecord).count() == 0
        assert session.query(CaseEventRecord).count() == 0


def test_outbox_failure_rolls_back_case_and_opening_turn(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    app.state.agent_command_outbox = FailingOutbox()

    with pytest.raises(RuntimeError, match="outbox unavailable"):
        client.post(
            "/cases",
            json={
                "order_ref": "ORDER-001",
                "user_ref": "USER-001",
                "initial_message": "需要退款",
            },
        )

    with session_factory() as session:
        assert session.query(CaseRecord).count() == 0
        assert session.query(CaseEventRecord).count() == 0


def test_interrupt_is_not_surfaced_once_the_case_moves_on(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    case_ref = _create(client)
    with session_factory.begin() as session:
        session.add(
            CaseEventRecord(
                case_ref=case_ref,
                seq=2,
                kind=AGENT_EVENT,
                payload=_interrupt_event(case_ref, 2),
            )
        )
        store = CaseStore(session)
        store.transition(case_ref, CaseStatus.AWAITING_EVIDENCE)
        store.transition(case_ref, CaseStatus.OBSERVING)

    case = client.get(f"/cases/{case_ref}").json()
    assert case["evidence_request"] is None



def test_illegal_transition_is_rejected(
    session_factory: sessionmaker[Session], client: TestClient
) -> None:
    case_ref = _create(client)
    with pytest.raises(IllegalTransitionError), session_factory.begin() as session:
        # OBSERVING cannot jump straight to RESOLVED.
        CaseStore(session).transition(case_ref, CaseStatus.RESOLVED)


def test_terminal_case_rejects_new_messages(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    case_ref = _create(client)
    with session_factory.begin() as session:
        store = CaseStore(session)
        store.transition(case_ref, CaseStatus.EXECUTING)
        store.transition(case_ref, CaseStatus.RESOLVED)

    response = client.post(f"/cases/{case_ref}/messages", json={"message": "還在嗎"})
    assert response.status_code == 409


@pytest.mark.parametrize(
    "case_status",
    [
        CaseStatus.OBSERVING,
        CaseStatus.EXECUTING,
        CaseStatus.AWAITING_HUMAN_REVIEW,
        CaseStatus.ESCALATED,
    ],
)
def test_non_resumable_case_status_rejects_messages(
    case_status: CaseStatus,
    client: TestClient,
    session_factory: sessionmaker[Session],
) -> None:
    case_ref = _create(client)
    if case_status is not CaseStatus.OBSERVING:
        with session_factory.begin() as session:
            CaseStore(session).transition(case_ref, case_status)

    response = client.post(f"/cases/{case_ref}/messages", json={"message": "繼續"})

    assert response.status_code == 409


def test_evidence_resume_requires_and_forwards_artifact_refs(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    case_ref = _create(client)
    with session_factory.begin() as session:
        CaseStore(session).transition(case_ref, CaseStatus.AWAITING_EVIDENCE)

    missing = client.post(
        f"/cases/{case_ref}/messages",
        json={"message": "我補資料了"},
    )
    assert missing.status_code == 422

    response = client.post(
        f"/cases/{case_ref}/messages",
        json={
            "message": "補上開箱照片",
            "attached_artifact_refs": ["artifact://EV-2"],
        },
    )

    assert response.status_code == 200
    command = app.state.agent_command_outbox.commands[-1]
    assert isinstance(command, AgentResumeCommand)
    assert command.case_ref == case_ref
    assert command.payload.resume.kind == "EVIDENCE_REQUEST"
    assert command.payload.resume.artifact_refs == ["artifact://EV-2"]


def test_sse_streams_only_agent_events_in_sequence(client, session_factory) -> None:
    case_ref = _create(client)
    with session_factory.begin() as session:
        append_agent_event(
            session,
            case_ref,
            {
                "type": "node_enter",
                "ts": datetime.now(UTC),
                "node": "parse_request",
                "payload": {"detail": None},
            },
        )
        append_agent_event(
            session,
            case_ref,
            {
                "type": "done",
                "ts": datetime.now(UTC),
                "node": "terminate_automation",
                "payload": {
                    "terminal_ref": "ESCALATION-1",
                    "status": "ESCALATED",
                },
            },
        )
        CaseStore(session).transition(case_ref, CaseStatus.ESCALATED)

    response = client.get(f"/cases/{case_ref}/events")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-cache"
    assert "id: 1\n" not in response.text  # opening user_turn is not an AgentEvent
    assert "id: 2\nevent: node_enter\n" in response.text
    assert "id: 3\nevent: done\n" in response.text


def test_sse_last_event_id_skips_already_seen_events(client, session_factory) -> None:
    case_ref = _create(client)
    with session_factory.begin() as session:
        append_agent_event(
            session,
            case_ref,
            {
                "type": "node_enter",
                "ts": datetime.now(UTC),
                "node": "parse_request",
                "payload": {"detail": None},
            },
        )
        append_agent_event(
            session,
            case_ref,
            {
                "type": "done",
                "ts": datetime.now(UTC),
                "node": "terminate_automation",
                "payload": {
                    "terminal_ref": "ESCALATION-1",
                    "status": "ESCALATED",
                },
            },
        )
        CaseStore(session).transition(case_ref, CaseStatus.ESCALATED)

    response = client.get(f"/cases/{case_ref}/events", headers={"Last-Event-ID": "2"})

    assert "event: node_enter" not in response.text
    assert "id: 3\nevent: done\n" in response.text


def test_sse_rejects_invalid_cursor_and_unknown_case(client) -> None:
    case_ref = _create(client)

    assert (
        client.get(
            f"/cases/{case_ref}/events", headers={"Last-Event-ID": "nope"}
        ).status_code
        == 400
    )
    assert client.get("/cases/CASE-NOPE/events").status_code == 404


def test_create_stages_start_command_in_the_request_transaction(client) -> None:
    case_ref = _create(client)
    command = app.state.agent_command_outbox.commands[-1]

    assert isinstance(command, AgentStartCommand)
    assert command.case_ref == case_ref
    assert command.payload.order_ref == "ORDER-001"
    assert command.payload.initial_turn.text == "喇叭到貨就破了，我要退款"


@pytest.mark.parametrize("status", [CaseStatus.AWAITING_CLARIFICATION, CaseStatus.AWAITING_EVIDENCE])
def test_reply_transport_preserves_transcript_identity(client, session_factory, status):
    case_ref = _create(client)
    with session_factory.begin() as session:
        CaseStore(session).transition(case_ref, status)
    response = client.post(f"/cases/{case_ref}/messages",
        json={"message": "這是補拍的照片", "attached_artifact_refs": ["artifact://EV-1"]})
    assert response.status_code == 200
    command = client.app.state.agent_command_outbox.commands[-1]
    turn = command.payload.resume.turn
    assert turn.text == "這是補拍的照片"
    assert turn.attached_artifact_refs == ["artifact://EV-1"]
    with session_factory() as session:
        events = session.query(CaseEventRecord).filter_by(case_ref=case_ref, kind=USER_TURN).order_by(CaseEventRecord.seq).all()
        assert events[-1].payload["turn_ref"] == turn.turn_id
        assert events[0].payload["turn_ref"] != turn.turn_id
