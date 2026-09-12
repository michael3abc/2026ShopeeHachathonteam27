"""Create durable authorized-refund execution records.

Revision ID: 0006_refund_execution
Revises: 0005_safety_verification_risk
Create Date: 2026-09-08
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0006_refund_execution"
down_revision: str | None = "0005_safety_verification_risk"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "refund_executions",
        sa.Column("execution_ref", sa.String(length=128), nullable=False),
        sa.Column("handoff_id", sa.String(length=256), nullable=False),
        sa.Column("case_ref", sa.String(length=128), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("request_payload", sa.JSON(), nullable=False),
        sa.Column("order_ref", sa.String(length=128), nullable=True),
        sa.Column(
            "application_result_payload",
            sa.JSON(none_as_null=True),
            nullable=True,
        ),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("application_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "state IN ('IN_PROGRESS', 'SUCCEEDED', 'REJECTED')",
            name="ck_refund_executions_state",
        ),
        sa.CheckConstraint(
            "(state = 'IN_PROGRESS' AND application_result_payload IS NULL "
            "AND completed_at IS NULL) OR "
            "(state IN ('SUCCEEDED', 'REJECTED') "
            "AND application_result_payload IS NOT NULL "
            "AND completed_at IS NOT NULL)",
            name="ck_refund_executions_terminal_result",
        ),
        sa.PrimaryKeyConstraint("execution_ref"),
        sa.UniqueConstraint("handoff_id"),
    )
    op.create_index(
        "ix_refund_executions_payload_hash",
        "refund_executions",
        ["payload_hash"],
        unique=False,
    )
    op.create_table(
        "refund_execution_items",
        sa.Column("execution_ref", sa.String(length=128), nullable=False),
        sa.Column("line_item_ref", sa.String(length=128), nullable=False),
        sa.Column("order_ref", sa.String(length=128), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["execution_ref"], ["refund_executions.execution_ref"]),
        sa.PrimaryKeyConstraint("execution_ref", "line_item_ref"),
        sa.UniqueConstraint(
            "order_ref",
            "line_item_ref",
            name="uq_refund_execution_items_order_line_item",
        ),
    )


def downgrade() -> None:
    op.drop_table("refund_execution_items")
    op.drop_table("refund_executions")
