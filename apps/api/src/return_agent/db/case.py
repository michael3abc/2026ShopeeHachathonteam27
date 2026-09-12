"""SQLAlchemy models for the backend-owned case lifecycle.

The case DB is the canonical record of where a return case stands. It is not
a mirror of the Agent graph working state: the graph owns its counters and
snapshots and resumes from its own checkpointer. Nothing here should ever
hold a graph counter such as `evidence_round` — the backend records that a
case is awaiting evidence, not which round it is on.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from pydantic import TypeAdapter
from return_agent_contracts.ui import AgentEvent, CaseStatus
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
    select,
)
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship
from sqlalchemy.types import JSON

from .models import Base

CASE_STATUSES = tuple(member.value for member in CaseStatus)

AGENT_EVENT = "agent_event"
USER_TURN = "user_turn"
EVENT_KINDS = (AGENT_EVENT, USER_TURN)
_AGENT_EVENT_ADAPTER = TypeAdapter(AgentEvent)


def _in_list(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(value) for value in values)})"


class CaseRecord(Base):
    """One return case, keyed by the reference the Demo/UI holds."""

    __tablename__ = "cases"
    __table_args__ = (
        CheckConstraint(_in_list("status", CASE_STATUSES), name="ck_cases_status"),
        CheckConstraint(
            "length(trim(order_ref)) > 0", name="ck_cases_order_ref_not_blank"
        ),
        CheckConstraint(
            "length(trim(user_ref)) > 0", name="ck_cases_user_ref_not_blank"
        ),
    )

    case_ref: Mapped[str] = mapped_column(String(128), primary_key=True)
    policy_schema_version: Mapped[str] = mapped_column(String(8),default="v1",server_default="v1")
    v2_context_payload: Mapped[dict | None] = mapped_column(JSON,nullable=True)
    # Backend-private LangGraph thread. Unique because resuming a case must
    # reuse its thread and a new case must never reuse an old one.
    thread_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    order_ref: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    user_ref: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    events: Mapped[list[CaseEventRecord]] = relationship(
        back_populates="case",
        cascade="all, delete-orphan",
        order_by="CaseEventRecord.seq",
    )


class CaseEventRecord(Base):
    """One entry in a case's transcript.

    This single table serves three jobs: SSE replay after a reconnect, the
    conversation transcript, and the audit trail.

    `kind` says what the payload is:

    - `agent_event` — an `AgentEvent` the backend emitted. Already redacted:
      no secrets, artifact bytes, raw signed URLs, or model chain-of-thought.
    - `user_turn` — `{"message": str, "attached_artifact_refs": [str]}`,
      built from a validated `SendMessageRequest`. Untrusted input, kept
      distinguishable from agent output by this column rather than by
      convention.

    Both kinds share one table because the transcript needs a single total
    order. Two tables would leave cross-table ordering to `created_at` and
    make a Last-Event-ID resume ambiguous about entries of the other kind.
    """

    __tablename__ = "case_events"
    __table_args__ = (
        # Per-case numbering, so a client can resume from Last-Event-ID and
        # the demo shows 1, 2, 3 rather than global ids with gaps.
        UniqueConstraint("case_ref", "seq", name="uq_case_events_case_ref_seq"),
        CheckConstraint("seq >= 1", name="ck_case_events_seq_positive"),
        CheckConstraint(_in_list("kind", EVENT_KINDS), name="ck_case_events_kind"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_ref: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("cases.case_ref", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    case: Mapped[CaseRecord] = relationship(back_populates="events")


def append_event(
    session: Session, case_ref: str, payload: dict, kind: str = AGENT_EVENT
) -> CaseEventRecord:
    """Append a transcript entry, numbering it from 1 within the case.

    Sequence allocation keeps the compact max(seq) + 1 representation, while
    a Case row lock serializes HTTP and Agent-event writers.
    """

    if kind == AGENT_EVENT:
        return append_agent_event(session, case_ref, payload)

    highest = _lock_case_and_highest_sequence(session, case_ref)
    event = CaseEventRecord(
        case_ref=case_ref, seq=(highest or 0) + 1, kind=kind, payload=payload
    )
    session.add(event)
    return event


def append_agent_event(
    session: Session,
    case_ref: str,
    payload: Mapping[str, Any],
) -> CaseEventRecord:
    """Validate and append a Backend-authored AgentEvent with the next sequence."""

    highest = _lock_case_and_highest_sequence(session, case_ref)
    sequence = (highest or 0) + 1
    event = _AGENT_EVENT_ADAPTER.validate_python(
        {**payload, "case_ref": case_ref, "seq": sequence}
    )
    record = CaseEventRecord(
        case_ref=case_ref,
        seq=sequence,
        kind=AGENT_EVENT,
        payload=event.model_dump(mode="json"),
    )
    session.add(record)
    return record


def _lock_case_and_highest_sequence(session: Session, case_ref: str) -> int | None:
    """Serialize all writers before assigning a per-case event sequence."""

    case = session.scalar(
        select(CaseRecord)
        .where(CaseRecord.case_ref == case_ref)
        .with_for_update()
    )
    if case is None:
        raise LookupError(f"unknown case {case_ref}")
    return session.scalar(
        select(func.max(CaseEventRecord.seq)).where(
            CaseEventRecord.case_ref == case_ref
        )
    )
