from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from .settings import Settings


class Base(DeclarativeBase):
    pass


class CaseRow(Base):
    __tablename__ = "cases"
    __table_args__ = (CheckConstraint("status IN ('OBSERVING','AWAITING_CLARIFICATION','AWAITING_EVIDENCE','AWAITING_HUMAN_REVIEW','EXECUTING','RESOLVED','ESCALATED')", name="case_status_valid"),)
    case_ref: Mapped[str] = mapped_column(Text, primary_key=True)
    thread_id: Mapped[str] = mapped_column(Text, unique=True)
    order_ref: Mapped[str] = mapped_column(Text, index=True)
    user_ref: Mapped[str] = mapped_column(Text, index=True)
    status: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    clarification_request: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    evidence_request: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    human_review: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    human_review_result: Mapped[dict[str, Any] | None] = mapped_column(JSONB)


class CaseEventRow(Base):
    __tablename__ = "case_events"
    __table_args__ = (
        UniqueConstraint("case_ref", "seq", name="case_event_sequence_unique"),
        CheckConstraint("seq > 0", name="case_event_sequence_positive"),
        CheckConstraint("kind IN ('user_turn','agent_event')", name="case_event_kind_valid"),
    )
    event_id: Mapped[str] = mapped_column(Text, primary_key=True)
    case_ref: Mapped[str] = mapped_column(ForeignKey("cases.case_ref", ondelete="CASCADE"), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(20))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CommandOutboxRow(Base):
    __tablename__ = "agent_command_outbox"
    __table_args__ = (CheckConstraint("attempts >= 0", name="outbox_attempts_nonnegative"), Index("outbox_pending", "published_at", "claimed_until"))
    command_id: Mapped[str] = mapped_column(Text, primary_key=True)
    case_ref: Mapped[str] = mapped_column(ForeignKey("cases.case_ref", ondelete="CASCADE"), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    payload_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    claimed_by: Mapped[str | None] = mapped_column(Text)
    claimed_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_token: Mapped[str | None] = mapped_column(Text)


class ProcessedAgentEventRow(Base):
    __tablename__ = "processed_agent_events"
    event_id: Mapped[str] = mapped_column(Text, primary_key=True)
    case_ref: Mapped[str] = mapped_column(ForeignKey("cases.case_ref"))
    command_id: Mapped[str] = mapped_column(Text, index=True)
    event_index: Mapped[int] = mapped_column(Integer)
    payload_hash: Mapped[str] = mapped_column(String(64))
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ProjectionCursorRow(Base):
    __tablename__ = "agent_event_projection_cursors"
    __table_args__ = (CheckConstraint("event_index >= 0", name="projection_index_nonnegative"),)
    command_id: Mapped[str] = mapped_column(Text, primary_key=True)
    case_ref: Mapped[str] = mapped_column(ForeignKey("cases.case_ref"))
    event_index: Mapped[int] = mapped_column(Integer, default=0)
    terminal_event_id: Mapped[str | None] = mapped_column(Text)


class RejectedAgentEventRow(Base):
    __tablename__ = "rejected_agent_events"
    source_message_id: Mapped[str] = mapped_column(Text, primary_key=True)
    error_code: Mapped[str] = mapped_column(Text)
    payload_hash: Mapped[str] = mapped_column(String(64))
    rejected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class TrustedOrderRow(Base):
    __tablename__ = "trusted_orders"
    order_ref: Mapped[str] = mapped_column(Text, primary_key=True)
    market: Mapped[str] = mapped_column(Text)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB)


class EvidenceRow(Base):
    __tablename__ = "evidence_metadata"
    artifact_ref: Mapped[str] = mapped_column(Text, primary_key=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)


class PolicyClauseRow(Base):
    __tablename__ = "policy_clauses"
    clause_id: Mapped[str] = mapped_column(Text, primary_key=True)
    policy_version: Mapped[str] = mapped_column(Text, primary_key=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)


class PolicyRetrievalRow(Base):
    __tablename__ = "policy_retrievals"
    bundle_version: Mapped[str] = mapped_column(Text, primary_key=True)
    case_ref: Mapped[str] = mapped_column(ForeignKey("cases.case_ref"), index=True)
    request: Mapped[dict[str, Any]] = mapped_column(JSONB)
    bundle: Mapped[dict[str, Any]] = mapped_column(JSONB)


class VerificationRow(Base):
    __tablename__ = "handoff_verifications"
    handoff_id: Mapped[str] = mapped_column(Text, primary_key=True)
    case_ref: Mapped[str] = mapped_column(ForeignKey("cases.case_ref"), index=True)
    payload_hash: Mapped[str] = mapped_column(String(64))
    handoff: Mapped[dict[str, Any]] = mapped_column(JSONB)
    result: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class HumanReviewRow(Base):
    __tablename__ = "human_reviews"
    review_ref: Mapped[str] = mapped_column(Text, primary_key=True)
    handoff_id: Mapped[str] = mapped_column(ForeignKey("handoff_verifications.handoff_id"), unique=True)
    case_ref: Mapped[str] = mapped_column(ForeignKey("cases.case_ref"), index=True)
    payload_hash: Mapped[str] = mapped_column(String(64))
    request: Mapped[dict[str, Any]] = mapped_column(JSONB)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


def make_engine(settings: Settings, *, schema: str | None = None) -> Engine:
    if not settings.database_url:
        raise ValueError("API_DATABASE_URL is required")
    connect_args: dict[str, Any] = {"connect_timeout": settings.database_timeout_seconds}
    if schema is not None:
        if not schema.replace("_", "").isalnum():
            raise ValueError("Invalid schema identifier")
        connect_args["options"] = f"-csearch_path={schema},public"
    return create_engine(settings.database_url, connect_args=connect_args, pool_size=5, max_overflow=0, pool_timeout=5, pool_pre_ping=True)


def make_sessions(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(engine, expire_on_commit=False)
