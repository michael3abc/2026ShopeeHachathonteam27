"""SQLAlchemy models for backend-owned persistence."""

from __future__ import annotations

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    Integer,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base metadata for tables maintained by this backend."""


class UserRiskProfileRecord(Base):
    __tablename__ = "user_risk_profiles"
    user_ref: Mapped[str] = mapped_column(String(128), primary_key=True)
    account_created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    orders_90d: Mapped[int] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (CheckConstraint("orders_90d >= 0"),)


class UserRiskEventRecord(Base):
    __tablename__ = "user_risk_events"
    event_ref: Mapped[str] = mapped_column(String(256), primary_key=True)
    user_ref: Mapped[str] = mapped_column(String(128), index=True)
    case_ref: Mapped[str] = mapped_column(String(128))
    order_ref: Mapped[str] = mapped_column(String(128))
    event_type: Mapped[str] = mapped_column(String(32))
    reason_code: Mapped[str | None] = mapped_column(String(64))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (UniqueConstraint("case_ref", "event_type"),
        CheckConstraint("event_type IN ('CLAIM_REGISTERED', 'REFUND_SUCCEEDED')"),
        CheckConstraint("event_type != 'CLAIM_REGISTERED' OR reason_code IS NOT NULL"))


class UserRiskSnapshotRecord(Base):
    __tablename__ = "user_risk_snapshots"
    snapshot_ref: Mapped[str] = mapped_column(String(256), primary_key=True)
    case_ref: Mapped[str] = mapped_column(String(128))
    user_ref: Mapped[str] = mapped_column(String(128))
    reason_code: Mapped[str] = mapped_column(String(64))
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    payload: Mapped[dict] = mapped_column(JSON)
    payload_hash: Mapped[str] = mapped_column(String(64))
    __table_args__ = (UniqueConstraint("case_ref", "reason_code", "as_of"),)


class PolicyEvaluationRecord(Base):
    __tablename__ = "policy_evaluations"
    evaluation_ref: Mapped[str] = mapped_column(String(256),primary_key=True)
    case_ref: Mapped[str] = mapped_column(String(128),index=True)
    payload: Mapped[dict] = mapped_column(JSON)


class PolicySelectionRecord(Base):
    __tablename__ = "policy_selections"
    case_ref: Mapped[str] = mapped_column(String(128), primary_key=True)
    selection_version: Mapped[int] = mapped_column(Integer, primary_key=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)


class PolicyConfirmationRecord(Base):
    __tablename__ = "policy_confirmations"
    request_ref: Mapped[str] = mapped_column(String(256),primary_key=True)
    case_ref: Mapped[str] = mapped_column(String(128),index=True)
    request_payload: Mapped[dict] = mapped_column(JSON)
    response_payload: Mapped[dict | None] = mapped_column(JSON,nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(256),nullable=True)


class ReturnAuthorizationRecord(Base):
    __tablename__ = "return_authorizations"
    authorization_ref: Mapped[str] = mapped_column(String(256),primary_key=True)
    case_ref: Mapped[str] = mapped_column(String(128),unique=True)
    execution_ref: Mapped[str] = mapped_column(String(128),unique=True)
    payload: Mapped[dict] = mapped_column(JSON)
    payload_hash: Mapped[str] = mapped_column(String(64))
    state: Mapped[str] = mapped_column(String(64))
    confirmation_payload: Mapped[dict | None] = mapped_column(JSON,nullable=True)
    arrived_event_id: Mapped[str | None] = mapped_column(String(256),nullable=True)
    inspection_event_id: Mapped[str | None] = mapped_column(String(256),nullable=True)
    execution_result: Mapped[dict | None] = mapped_column(JSON,nullable=True)
    reason: Mapped[str | None] = mapped_column(String(128),nullable=True)
    lease_owner: Mapped[str | None] = mapped_column(String(256),nullable=True)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True),nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ReturnReceiptRecord(Base):
    __tablename__ = "return_event_receipts"
    receipt_ref: Mapped[str] = mapped_column(String(256),primary_key=True)
    producer_id: Mapped[str] = mapped_column(String(128))
    event_id: Mapped[str] = mapped_column(String(256))
    authorization_ref: Mapped[str] = mapped_column(String(256),index=True)
    event_payload: Mapped[dict] = mapped_column(JSON)
    receipt_payload: Mapped[dict] = mapped_column(JSON)
    __table_args__ = (UniqueConstraint("producer_id","event_id"),)


class RefundCompletionOutboxRecord(Base):
    __tablename__ = "refund_completion_outbox"
    resolution_ref: Mapped[str] = mapped_column(String(256),primary_key=True)
    payload: Mapped[dict] = mapped_column(JSON)
    published: Mapped[bool] = mapped_column(Boolean,default=False)


class DemoSessionRecord(Base):
    __tablename__ = "demo_sessions"
    token_hash: Mapped[str] = mapped_column(String(64),primary_key=True)
    user_ref: Mapped[str] = mapped_column(String(128))
    role: Mapped[str] = mapped_column(String(32))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class EvidenceRecord(Base):
    """Neutral metadata for an evidence artifact; never stores artifact bytes."""

    __tablename__ = "evidence_items"
    __table_args__ = (
        CheckConstraint(
            "type IN ('IMAGE', 'VIDEO', 'TEXT', 'DOCUMENT')",
            name="ck_evidence_items_type",
        ),
        CheckConstraint(
            "source IN ('USER', 'ORDER_TOOL', 'LOGISTICS_TOOL', 'SYSTEM')",
            name="ck_evidence_items_source",
        ),
        CheckConstraint(
            "length(trim(subject)) > 0", name="ck_evidence_items_subject_not_blank"
        ),
        CheckConstraint(
            "length(trim(artifact_ref)) > 0",
            name="ck_evidence_items_artifact_ref_not_blank",
        ),
        CheckConstraint(
            "length(trim(extracted_summary)) > 0",
            name="ck_evidence_items_summary_not_blank",
        ),
    )

    evidence_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    subject: Mapped[str] = mapped_column(String(128), nullable=False)
    artifact_ref: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)
    extracted_summary: Mapped[str] = mapped_column(Text, nullable=False)
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)


def _postgres_array() -> ARRAY:
    """Use PostgreSQL arrays at runtime and JSON for SQLite contract tests."""

    return ARRAY(String()).with_variant(JSON(), "sqlite")


def _embedding_vector() -> Vector:
    """Use pgvector in PostgreSQL and a JSON vector in SQLite tests."""

    return Vector(1536).with_variant(JSON(), "sqlite")


class PolicyDocumentRecord(Base):
    """A versioned policy source document owned by the Policy RAG capability."""

    __tablename__ = "policy_documents"
    __table_args__ = (
        UniqueConstraint(
            "policy_family",
            "version",
            name="uq_policy_documents_family_version",
        ),
        UniqueConstraint(
            "source_ref",
            "version",
            name="uq_policy_documents_source_version",
        ),
    )

    document_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    path_payload: Mapped[list | None] = mapped_column(JSON, nullable=True)
    policy_family: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[str] = mapped_column(String(128), nullable=False)
    source_ref: Mapped[str] = mapped_column(String(512), nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class PolicyClauseRecord(Base):
    path_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    """Structured, embedded clause data used for retrieval, never decisioning."""

    __tablename__ = "policy_clauses"

    clause_id: Mapped[str] = mapped_column(String(256), primary_key=True)
    document_id: Mapped[str] = mapped_column(
        ForeignKey("policy_documents.document_id"), nullable=False, index=True
    )
    policy_version: Mapped[str] = mapped_column(String(256), nullable=False)
    effective_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    markets: Mapped[list[str]] = mapped_column(_postgres_array(), nullable=False)
    reason_codes: Mapped[list[str]] = mapped_column(_postgres_array(), nullable=False)
    categories: Mapped[list[str]] = mapped_column(_postgres_array(), nullable=False)
    required_claim_ids: Mapped[list[str]] = mapped_column(
        _postgres_array(), nullable=False
    )
    allowed_actions: Mapped[list[str]] = mapped_column(
        _postgres_array(), nullable=False
    )
    return_policy: Mapped[str] = mapped_column(String(32), nullable=False)
    clause_text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(128), nullable=False)
    embedding: Mapped[list[float]] = mapped_column(_embedding_vector(), nullable=False)


class PolicyRetrievalRecord(Base):
    """Durable exact PolicyBundle returned for a retrieval request."""

    __tablename__ = "policy_retrievals"
    __table_args__ = (
        UniqueConstraint("bundle_version", name="uq_policy_retrievals_bundle_version"),
    )

    retrieval_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    bundle_version: Mapped[str] = mapped_column(String(128), nullable=False)
    retrieval_status: Mapped[str] = mapped_column(String(32), nullable=False)
    bundle_payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class OperationalMemoryRecord(Base):
    """Durable candidate lifecycle and audit-source data for operational memory."""

    __tablename__ = "operational_memories"
    __table_args__ = (
        CheckConstraint(
            "status IN ('CANDIDATE', 'APPROVED', 'RETIRED')",
            name="ck_operational_memories_status",
        ),
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_operational_memories_confidence",
        ),
        CheckConstraint(
            "length(trim(submission_ref)) > 0",
            name="ck_operational_memories_submission_ref_not_blank",
        ),
        CheckConstraint(
            "length(trim(recommended_behavior)) > 0",
            name="ck_operational_memories_behavior_not_blank",
        ),
        CheckConstraint(
            "length(trim(rationale)) > 0",
            name="ck_operational_memories_rationale_not_blank",
        ),
        CheckConstraint(
            "length(trim(policy_version)) > 0",
            name="ck_operational_memories_policy_version_not_blank",
        ),
        CheckConstraint(
            "length(trim(claim_registry_version)) > 0",
            name="ck_operational_memories_registry_version_not_blank",
        ),
        CheckConstraint(
            "length(trim(scope_market)) > 0",
            name="ck_operational_memories_scope_market_not_blank",
        ),
        CheckConstraint(
            "(status = 'CANDIDATE' AND approved_at IS NULL AND retired_at IS NULL) "
            "OR (status = 'APPROVED' AND approved_at IS NOT NULL AND retired_at IS NULL) "
            "OR (status = 'RETIRED' AND approved_at IS NOT NULL AND retired_at IS NOT NULL)",
            name="ck_operational_memories_lifecycle_timestamps",
        ),
        CheckConstraint(
            "approved_at IS NULL OR approved_at >= submitted_at",
            name="ck_operational_memories_approval_after_submission",
        ),
        CheckConstraint(
            "retired_at IS NULL OR retired_at >= approved_at",
            name="ck_operational_memories_retirement_after_approval",
        ),
    )

    memory_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    submission_ref: Mapped[str] = mapped_column(
        String(256), nullable=False, unique=True
    )
    candidate_payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    retrieval_summary: Mapped[str | None] = mapped_column(Text)
    summary_version: Mapped[str | None] = mapped_column(String(64))
    summary_hash: Mapped[str | None] = mapped_column(String(64))
    embedding_model: Mapped[str | None] = mapped_column(String(128))
    embedding: Mapped[list[float] | None] = mapped_column(_embedding_vector())
    trigger_conditions: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    recommended_behavior: Mapped[str] = mapped_column(Text, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    source_case_refs: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    source_revision_event_refs: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    policy_version: Mapped[str] = mapped_column(String(256), nullable=False)
    claim_registry_version: Mapped[str] = mapped_column(String(128), nullable=False)
    scope_market: Mapped[str] = mapped_column(String(64), nullable=False)
    scope_policy_path_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    scope_reason_codes: Mapped[list[str]] = mapped_column(
        _postgres_array(), nullable=False
    )
    scope_claim_ids: Mapped[list[str]] = mapped_column(
        _postgres_array(), nullable=False
    )
    scope_categories: Mapped[list[str]] = mapped_column(
        _postgres_array(), nullable=False
    )
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OperationalMemoryEventRecord(Base):
    """Append-only approval and retirement events for an operational memory."""

    __tablename__ = "operational_memory_events"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('APPROVED', 'RETIRED')",
            name="ck_operational_memory_events_type",
        ),
        CheckConstraint(
            "(event_type = 'APPROVED' AND from_status = 'CANDIDATE' "
            "AND to_status = 'APPROVED') OR "
            "(event_type = 'RETIRED' AND from_status = 'APPROVED' "
            "AND to_status = 'RETIRED')",
            name="ck_operational_memory_events_transition",
        ),
    )

    event_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    memory_id: Mapped[str] = mapped_column(
        ForeignKey("operational_memories.memory_id"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(16), nullable=False)
    from_status: Mapped[str] = mapped_column(String(16), nullable=False)
    to_status: Mapped[str] = mapped_column(String(16), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class HandoffVerificationRecord(Base):
    """Canonical deterministic verification result for one proposed handoff."""

    __tablename__ = "handoff_verifications"
    __table_args__ = (
        CheckConstraint(
            "verification_status IN ('PASS', 'FAIL', 'UNAVAILABLE')",
            name="ck_handoff_verifications_status",
        ),
    )

    verification_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    handoff_id: Mapped[str] = mapped_column(String(256), nullable=False, unique=True)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    handoff_payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    result_payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    verification_status: Mapped[str] = mapped_column(String(16), nullable=False)
    verification_version: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )


class HumanReviewRecord(Base):
    """Durable handoff submission and eventual human-review result."""

    __tablename__ = "human_reviews"
    __table_args__ = (
        CheckConstraint(
            "result_payload IS NULL OR reviewed_at IS NOT NULL",
            name="ck_human_reviews_result_has_timestamp",
        ),
    )

    review_ref: Mapped[str] = mapped_column(String(256), primary_key=True)
    handoff_id: Mapped[str] = mapped_column(String(256), nullable=False, unique=True)
    case_ref: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    handoff_payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    review_payload: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    dossier_payload: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    result_payload: Mapped[dict[str, object] | None] = mapped_column(
        JSON(none_as_null=True)
    )
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RefundExecutionRecord(Base):
    """Durable local lifecycle for one authorized refund handoff."""

    __tablename__ = "refund_executions"
    __table_args__ = (
        CheckConstraint(
            "state IN ('IN_PROGRESS', 'SUCCEEDED', 'REJECTED')",
            name="ck_refund_executions_state",
        ),
        CheckConstraint(
            "(state = 'IN_PROGRESS' AND application_result_payload IS NULL "
            "AND completed_at IS NULL) OR "
            "(state IN ('SUCCEEDED', 'REJECTED') "
            "AND application_result_payload IS NOT NULL "
            "AND completed_at IS NOT NULL)",
            name="ck_refund_executions_terminal_result",
        ),
    )

    execution_ref: Mapped[str] = mapped_column(String(128), primary_key=True)
    handoff_id: Mapped[str] = mapped_column(String(256), nullable=False, unique=True)
    case_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    request_payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    order_ref: Mapped[str | None] = mapped_column(String(128))
    application_result_payload: Mapped[dict[str, object] | None] = mapped_column(
        JSON(none_as_null=True)
    )
    state: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    application_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )


class RefundItemReservation(Base):
    """Durable item ownership established before an external refund attempt."""

    __tablename__ = "refund_item_reservations"

    order_ref: Mapped[str] = mapped_column(String(128), primary_key=True)
    line_item_ref: Mapped[str] = mapped_column(String(128), primary_key=True)
    execution_ref: Mapped[str] = mapped_column(
        ForeignKey("refund_executions.execution_ref"), nullable=False
    )
    reserved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class RefundExecutionItemRecord(Base):
    """A successfully applied order-item refund without an Allen table FK."""

    __tablename__ = "refund_execution_items"
    __table_args__ = (
        UniqueConstraint(
            "order_ref",
            "line_item_ref",
            name="uq_refund_execution_items_order_line_item",
        ),
    )

    execution_ref: Mapped[str] = mapped_column(
        ForeignKey("refund_executions.execution_ref"),
        primary_key=True,
    )
    line_item_ref: Mapped[str] = mapped_column(String(128), primary_key=True)
    order_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    applied_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
