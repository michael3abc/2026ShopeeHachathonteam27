from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from pydantic import TypeAdapter
from return_agent.db.case import (
    AGENT_EVENT,
    USER_TURN,
    CaseEventRecord,
    CaseRecord,
    append_event,
)
from return_agent.db.models import Base
from return_agent_contracts.ui import AgentEvent
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

_AGENT_EVENT = TypeAdapter(AgentEvent)


def _session_factory() -> sessionmaker[Session]:
    engine = create_engine("sqlite://")
    # SQLite ignores foreign keys unless asked; the orphan test needs them.
    with engine.connect() as connection:
        connection.execute(text("PRAGMA foreign_keys=ON"))
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def _case(
    case_ref: str = "CASE-001",
    status: str = "OBSERVING",
    thread_id: str | None = None,
) -> CaseRecord:
    now = datetime.now(UTC)
    return CaseRecord(
        case_ref=case_ref,
        thread_id=thread_id or f"thread-{case_ref}",
        order_ref="ORDER-001",
        user_ref="USER-001",
        status=status,
        created_at=now,
        updated_at=now,
    )


def _event(node: str = "parse_request") -> dict:
    return {
        "type": "node_enter",
        "case_ref": "CASE-001",
        "seq": 1,
        "ts": "2026-09-06T10:00:00Z",
        "node": node,
        "payload": {"detail": None},
    }


def test_events_are_numbered_from_one_within_each_case() -> None:
    session_factory = _session_factory()
    with session_factory.begin() as session:
        session.add(_case("CASE-001"))
        session.add(_case("CASE-002"))

    with session_factory.begin() as session:
        assert append_event(session, "CASE-001", _event()).seq == 1
        assert append_event(session, "CASE-001", _event("load_case_context")).seq == 2

    # A second case restarts at 1 rather than continuing a global counter.
    with session_factory.begin() as session:
        assert append_event(session, "CASE-002", _event()).seq == 1

    with session_factory() as session:
        case = session.get(CaseRecord, "CASE-001")
        assert case is not None
        assert [event.seq for event in case.events] == [1, 2]
        assert case.events[1].payload["node"] == "load_case_context"
        assert case.events[1].payload["seq"] == 2
        # An agent_event payload must still parse as the contract's union.
        assert case.events[0].kind == AGENT_EVENT
        restored = _AGENT_EVENT.validate_python(case.events[0].payload)
        assert restored.node.value == "parse_request"


def test_duplicate_seq_within_a_case_is_rejected() -> None:
    session_factory = _session_factory()
    with session_factory.begin() as session:
        session.add(_case())
        session.add(
            CaseEventRecord(
                case_ref="CASE-001", seq=1, kind=AGENT_EVENT, payload=_event()
            )
        )

    with pytest.raises(IntegrityError):
        with session_factory.begin() as session:
            session.add(
                CaseEventRecord(
                    case_ref="CASE-001", seq=1, kind=AGENT_EVENT, payload=_event()
                )
            )


def test_seq_below_one_is_rejected() -> None:
    session_factory = _session_factory()
    with session_factory.begin() as session:
        session.add(_case())
    with pytest.raises(IntegrityError):
        with session_factory.begin() as session:
            session.add(
                CaseEventRecord(
                    case_ref="CASE-001", seq=0, kind=AGENT_EVENT, payload=_event()
                )
            )


def test_thread_id_cannot_be_reused_by_another_case() -> None:
    session_factory = _session_factory()
    with session_factory.begin() as session:
        session.add(_case("CASE-001", thread_id="thread-shared"))
    with pytest.raises(IntegrityError):
        with session_factory.begin() as session:
            session.add(_case("CASE-002", thread_id="thread-shared"))


def test_status_outside_the_case_status_enum_is_rejected() -> None:
    session_factory = _session_factory()
    with pytest.raises(IntegrityError):
        with session_factory.begin() as session:
            session.add(_case(status="NOT_A_STATUS"))


def test_case_can_wait_for_agent_clarification() -> None:
    session_factory = _session_factory()
    with session_factory.begin() as session:
        session.add(_case(status="AWAITING_CLARIFICATION"))



def test_event_requires_an_existing_case() -> None:
    session_factory = _session_factory()
    with pytest.raises(IntegrityError):
        with session_factory.begin() as session:
            session.add(
                CaseEventRecord(
                    case_ref="CASE-MISSING", seq=1, kind=AGENT_EVENT, payload=_event()
                )
            )


def test_case_migration_upgrades_and_downgrades_a_fresh_database(
    tmp_path: Path,
) -> None:
    api_root = Path(__file__).resolve().parents[1]
    config = Config(str(api_root / "alembic.ini"))
    config.set_main_option("script_location", str(api_root / "alembic"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{tmp_path / 'case.db'}")

    command.upgrade(config, "head")
    engine = create_engine(config.get_main_option("sqlalchemy.url"))
    tables = inspect(engine).get_table_names()
    assert "cases" in tables
    assert "case_events" in tables
    # The chain must build on the evidence revision, not fork a second root.
    assert "evidence_items" in tables
    assert "policy_documents" in tables
    assert "operational_memories" in tables
    assert "agent_command_outbox" in tables
    assert "processed_agent_events" in tables

    command.downgrade(config, "0001_evidence_capability")
    tables = inspect(engine).get_table_names()
    assert "cases" not in tables
    assert "case_events" not in tables
    assert "agent_command_outbox" not in tables
    assert "processed_agent_events" not in tables
    assert "evidence_items" in tables

    command.downgrade(config, "base")
    tables = inspect(engine).get_table_names()
    assert "evidence_items" not in tables


def test_user_turns_and_agent_events_share_one_sequence() -> None:
    session_factory = _session_factory()
    with session_factory.begin() as session:
        session.add(_case())

    with session_factory.begin() as session:
        append_event(session, "CASE-001", _event())
        append_event(
            session,
            "CASE-001",
            {"message": "補上外箱照片", "attached_artifact_refs": ["artifact://EV-2"]},
            kind=USER_TURN,
        )
        append_event(session, "CASE-001", _event("assess_case"))

    with session_factory() as session:
        case = session.get(CaseRecord, "CASE-001")
        assert case is not None
        # One total order across both kinds: no timestamp merging needed.
        assert [(event.seq, event.kind) for event in case.events] == [
            (1, AGENT_EVENT),
            (2, USER_TURN),
            (3, AGENT_EVENT),
        ]
        assert case.events[1].payload["attached_artifact_refs"] == ["artifact://EV-2"]


def test_unknown_kind_is_rejected() -> None:
    session_factory = _session_factory()
    with session_factory.begin() as session:
        session.add(_case())
    with pytest.raises(IntegrityError):
        with session_factory.begin() as session:
            session.add(
                CaseEventRecord(
                    case_ref="CASE-001", seq=1, kind="something_else", payload={}
                )
            )
