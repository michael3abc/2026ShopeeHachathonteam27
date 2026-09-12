from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


class Base(DeclarativeBase):
    pass


class ThreadRow(Base):
    __tablename__ = "agent_threads"
    thread_id: Mapped[str] = mapped_column(Text, primary_key=True)
    case_ref: Mapped[str] = mapped_column(Text, unique=True)
    start_command_id: Mapped[str] = mapped_column(Text, unique=True)


class CommandRow(Base):
    __tablename__ = "command_journal"
    __table_args__ = (CheckConstraint("status IN ('CLAIMED','TERMINAL')", name="journal_status_valid"),)
    command_id: Mapped[str] = mapped_column(Text, primary_key=True)
    thread_id: Mapped[str] = mapped_column(ForeignKey("agent_threads.thread_id"), index=True)
    case_ref: Mapped[str] = mapped_column(Text)
    payload_hash: Mapped[str] = mapped_column(String(64))
    request: Mapped[dict[str, Any]] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(20))
    lease_owner: Mapped[str] = mapped_column(Text)
    leased_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    initial_checkpoint_id: Mapped[str | None] = mapped_column(Text)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    distillation_input: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class EventOutboxRow(Base):
    __tablename__ = "agent_event_outbox"
    __table_args__ = (UniqueConstraint("command_id", "event_index", name="agent_event_index_unique"),)
    event_id: Mapped[str] = mapped_column(Text, primary_key=True)
    command_id: Mapped[str] = mapped_column(ForeignKey("command_journal.command_id"))
    event_index: Mapped[int] = mapped_column(Integer)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_token: Mapped[str | None] = mapped_column(Text)
    claimed_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


def make_engine(url: str, *, schema: str | None = None):
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    args = {"connect_timeout": 5}
    if schema:
        if not schema.replace("_", "").isalnum():
            raise ValueError("Invalid schema name")
        args["options"] = f"-csearch_path={schema}"
    return create_engine(url, connect_args=args, pool_size=6, max_overflow=0, pool_timeout=5, pool_pre_ping=True)


def make_sessions(engine):
    return sessionmaker(engine, expire_on_commit=False)
