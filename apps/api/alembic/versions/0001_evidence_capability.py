"""Create Louis-owned neutral evidence metadata storage.

Revision ID: 0001_evidence_capability
Revises:
Create Date: 2026-09-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_evidence_capability"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "evidence_items",
        sa.Column("evidence_id", sa.String(length=128), nullable=False),
        sa.Column("type", sa.String(length=16), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("subject", sa.String(length=128), nullable=False),
        sa.Column("artifact_ref", sa.String(length=512), nullable=False),
        sa.Column("extracted_summary", sa.Text(), nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.CheckConstraint(
            "type IN ('IMAGE', 'VIDEO', 'TEXT', 'DOCUMENT')",
            name="ck_evidence_items_type",
        ),
        sa.CheckConstraint(
            "source IN ('USER', 'ORDER_TOOL', 'LOGISTICS_TOOL', 'SYSTEM')",
            name="ck_evidence_items_source",
        ),
        sa.CheckConstraint(
            "length(trim(subject)) > 0",
            name="ck_evidence_items_subject_not_blank",
        ),
        sa.CheckConstraint(
            "length(trim(artifact_ref)) > 0",
            name="ck_evidence_items_artifact_ref_not_blank",
        ),
        sa.CheckConstraint(
            "length(trim(extracted_summary)) > 0",
            name="ck_evidence_items_summary_not_blank",
        ),
        sa.PrimaryKeyConstraint("evidence_id"),
        sa.UniqueConstraint("artifact_ref"),
        sa.UniqueConstraint("content_hash"),
    )


def downgrade() -> None:
    op.drop_table("evidence_items")
