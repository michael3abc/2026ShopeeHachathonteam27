"""Add durable Human Review handoff storage.

Revision ID: 0009_human_reviews
Revises: 0008_agent_bridge
Create Date: 2026-09-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_human_reviews"
down_revision: str | None = "0008_agent_bridge"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "human_reviews",
        sa.Column("review_ref", sa.String(length=256), nullable=False),
        sa.Column("handoff_id", sa.String(length=256), nullable=False),
        sa.Column("case_ref", sa.String(length=128), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("handoff_payload", sa.JSON(), nullable=False),
        sa.Column("risk_payload", sa.JSON(), nullable=False),
        sa.Column("result_payload", sa.JSON(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "result_payload IS NULL OR reviewed_at IS NOT NULL",
            name="ck_human_reviews_result_has_timestamp",
        ),
        sa.PrimaryKeyConstraint("review_ref"),
        sa.UniqueConstraint("handoff_id", name="uq_human_reviews_handoff_id"),
    )
    op.create_index("ix_human_reviews_case_ref", "human_reviews", ["case_ref"])


def downgrade() -> None:
    op.drop_index("ix_human_reviews_case_ref", table_name="human_reviews")
    op.drop_table("human_reviews")
