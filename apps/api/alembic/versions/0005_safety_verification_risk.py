"""Create durable verification and risk-gate records.

Revision ID: 0005_safety_verification_risk
Revises: 0004_operational_memory
Create Date: 2026-09-07
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0005_safety_verification_risk"
down_revision: str | None = "0004_operational_memory"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "handoff_verifications",
        sa.Column("verification_id", sa.String(length=128), nullable=False),
        sa.Column("handoff_id", sa.String(length=256), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("handoff_payload", sa.JSON(), nullable=False),
        sa.Column("result_payload", sa.JSON(), nullable=False),
        sa.Column("verification_status", sa.String(length=16), nullable=False),
        sa.Column("verification_version", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "verification_status IN ('PASS', 'FAIL', 'UNAVAILABLE')",
            name="ck_handoff_verifications_status",
        ),
        sa.PrimaryKeyConstraint("verification_id"),
        sa.UniqueConstraint("handoff_id"),
    )
    op.create_index(
        "ix_handoff_verifications_payload_hash",
        "handoff_verifications",
        ["payload_hash"],
        unique=False,
    )
    op.create_table(
        "risk_evaluations",
        sa.Column("evaluation_id", sa.String(length=128), nullable=False),
        sa.Column("handoff_id", sa.String(length=256), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("handoff_payload", sa.JSON(), nullable=False),
        sa.Column("result_payload", sa.JSON(), nullable=False),
        sa.Column("risk_route", sa.String(length=16), nullable=False),
        sa.Column("risk_policy_version", sa.String(length=128), nullable=False),
        sa.Column("effective_config", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "risk_route IN ('AUTO', 'HUMAN', 'BLOCK')",
            name="ck_risk_evaluations_route",
        ),
        sa.PrimaryKeyConstraint("evaluation_id"),
        sa.UniqueConstraint("handoff_id"),
    )
    op.create_index(
        "ix_risk_evaluations_payload_hash",
        "risk_evaluations",
        ["payload_hash"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("risk_evaluations")
    op.drop_table("handoff_verifications")
