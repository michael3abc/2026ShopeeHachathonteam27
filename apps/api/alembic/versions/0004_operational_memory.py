"""Create durable operational-memory lifecycle storage.

Revision ID: 0004_operational_memory
Revises: 0003_policy_rag
Create Date: 2026-09-06
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY

revision: str = "0004_operational_memory"
down_revision: str | None = "0003_policy_rag"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _array_type() -> ARRAY:
    """Use PostgreSQL arrays at runtime and JSON for SQLite migration tests."""

    return ARRAY(sa.String()).with_variant(sa.JSON(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "operational_memories",
        sa.Column("memory_id", sa.String(length=128), nullable=False),
        sa.Column("submission_ref", sa.String(length=256), nullable=False),
        sa.Column("candidate_payload_hash", sa.String(length=64), nullable=False),
        sa.Column("trigger_conditions", sa.JSON(), nullable=False),
        sa.Column("recommended_behavior", sa.Text(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("source_case_refs", sa.JSON(), nullable=False),
        sa.Column("source_revision_event_refs", sa.JSON(), nullable=False),
        sa.Column("policy_version", sa.String(length=256), nullable=False),
        sa.Column("claim_registry_version", sa.String(length=128), nullable=False),
        sa.Column("scope_market", sa.String(length=64), nullable=False),
        sa.Column("scope_reason_codes", _array_type(), nullable=False),
        sa.Column("scope_claim_ids", _array_type(), nullable=False),
        sa.Column("scope_categories", _array_type(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column(
            "submitted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('CANDIDATE', 'APPROVED', 'RETIRED')",
            name="ck_operational_memories_status",
        ),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_operational_memories_confidence",
        ),
        sa.CheckConstraint(
            "length(trim(submission_ref)) > 0",
            name="ck_operational_memories_submission_ref_not_blank",
        ),
        sa.CheckConstraint(
            "length(trim(recommended_behavior)) > 0",
            name="ck_operational_memories_behavior_not_blank",
        ),
        sa.CheckConstraint(
            "length(trim(rationale)) > 0",
            name="ck_operational_memories_rationale_not_blank",
        ),
        sa.CheckConstraint(
            "length(trim(policy_version)) > 0",
            name="ck_operational_memories_policy_version_not_blank",
        ),
        sa.CheckConstraint(
            "length(trim(claim_registry_version)) > 0",
            name="ck_operational_memories_registry_version_not_blank",
        ),
        sa.CheckConstraint(
            "length(trim(scope_market)) > 0",
            name="ck_operational_memories_scope_market_not_blank",
        ),
        sa.CheckConstraint(
            "(status = 'CANDIDATE' AND approved_at IS NULL AND retired_at IS NULL) "
            "OR (status = 'APPROVED' AND approved_at IS NOT NULL AND retired_at IS NULL) "
            "OR (status = 'RETIRED' AND approved_at IS NOT NULL AND retired_at IS NOT NULL)",
            name="ck_operational_memories_lifecycle_timestamps",
        ),
        sa.CheckConstraint(
            "approved_at IS NULL OR approved_at >= submitted_at",
            name="ck_operational_memories_approval_after_submission",
        ),
        sa.CheckConstraint(
            "retired_at IS NULL OR retired_at >= approved_at",
            name="ck_operational_memories_retirement_after_approval",
        ),
        sa.PrimaryKeyConstraint("memory_id"),
        sa.UniqueConstraint("submission_ref"),
    )
    op.create_index(
        "ix_operational_memories_approved_lookup",
        "operational_memories",
        ["status", "scope_market", "policy_version", "confidence"],
        unique=False,
    )

    op.create_table(
        "operational_memory_events",
        sa.Column("event_id", sa.String(length=128), nullable=False),
        sa.Column("memory_id", sa.String(length=128), nullable=False),
        sa.Column("event_type", sa.String(length=16), nullable=False),
        sa.Column("from_status", sa.String(length=16), nullable=False),
        sa.Column("to_status", sa.String(length=16), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "event_type IN ('APPROVED', 'RETIRED')",
            name="ck_operational_memory_events_type",
        ),
        sa.CheckConstraint(
            "(event_type = 'APPROVED' AND from_status = 'CANDIDATE' "
            "AND to_status = 'APPROVED') OR "
            "(event_type = 'RETIRED' AND from_status = 'APPROVED' "
            "AND to_status = 'RETIRED')",
            name="ck_operational_memory_events_transition",
        ),
        sa.ForeignKeyConstraint(["memory_id"], ["operational_memories.memory_id"]),
        sa.PrimaryKeyConstraint("event_id"),
    )
    op.create_index(
        "ix_operational_memory_events_memory_id",
        "operational_memory_events",
        ["memory_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("operational_memory_events")
    op.drop_table("operational_memories")
