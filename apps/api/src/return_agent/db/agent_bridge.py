"""Persistence for reliable Agent command and event delivery."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from .models import Base


class AgentCommandOutboxRecord(Base):
    """An immutable Agent command waiting to be published to Redis."""

    __tablename__ = "agent_command_outbox"
    __table_args__ = (
        CheckConstraint(
            "attempt_count >= 0", name="ck_agent_command_outbox_attempt_count"
        ),
    )

    command_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    claimed_by: Mapped[str | None] = mapped_column(String(256))
    claimed_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_token: Mapped[str | None] = mapped_column(String(32))
    attempt_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    last_error: Mapped[str | None] = mapped_column(Text)


class ProcessedAgentEventRecord(Base):
    """Database idempotency key for an at-least-once Agent event."""

    __tablename__ = "processed_agent_events"

    event_id: Mapped[str] = mapped_column(String(256), primary_key=True)
    case_ref: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("cases.case_ref", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    command_id: Mapped[str] = mapped_column(String(128), nullable=False)
    event_index: Mapped[int] = mapped_column(Integer, nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class AgentEventProjectionCursorRecord(Base):
    """Last contiguous service event projected for one Agent command."""

    __tablename__ = "agent_event_projection_cursors"
    __table_args__ = (
        CheckConstraint(
            "last_event_index >= 0",
            name="ck_agent_event_projection_cursor_index",
        ),
    )

    command_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    case_ref: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("cases.case_ref", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    last_event_index: Mapped[int] = mapped_column(Integer, nullable=False)
    terminated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    termination_event_id: Mapped[str | None] = mapped_column(String(256))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class RejectedAgentEventRecord(Base):
    """Restricted diagnostic record written before a poison event is ACKed."""

    __tablename__ = "rejected_agent_events"

    source_message_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    event_id: Mapped[str | None] = mapped_column(String(256), index=True)
    case_ref: Mapped[str | None] = mapped_column(String(128), index=True)
    raw_body: Mapped[str] = mapped_column(Text, nullable=False)
    error_code: Mapped[str] = mapped_column(String(64), nullable=False)
    error_message: Mapped[str] = mapped_column(Text, nullable=False)
    rejected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
