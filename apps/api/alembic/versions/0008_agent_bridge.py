"""Add the Agent command outbox and event idempotency ledger.

Revision ID: 0008_agent_bridge
Revises: 0007_refund_item_reservations
Create Date: 2026-09-08
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0008_agent_bridge"
down_revision: str | None = "0007_refund_item_reservations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_command_outbox",
        sa.Column("command_id", sa.String(length=128), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("claimed_by", sa.String(length=256), nullable=True),
        sa.Column("claimed_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_token", sa.String(length=32), nullable=True),
        sa.Column(
            "attempt_count", sa.Integer(), server_default="0", nullable=False
        ),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "attempt_count >= 0", name="ck_agent_command_outbox_attempt_count"
        ),
        sa.PrimaryKeyConstraint("command_id"),
    )

    op.create_table(
        "processed_agent_events",
        sa.Column("event_id", sa.String(length=256), nullable=False),
        sa.Column("case_ref", sa.String(length=128), nullable=False),
        sa.Column("command_id", sa.String(length=128), nullable=False),
        sa.Column("event_index", sa.Integer(), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "processed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["case_ref"], ["cases.case_ref"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("event_id"),
    )
    op.create_index(
        "ix_processed_agent_events_case_ref",
        "processed_agent_events",
        ["case_ref"],
    )

    op.create_table(
        "agent_event_projection_cursors",
        sa.Column("command_id", sa.String(length=128), nullable=False),
        sa.Column("case_ref", sa.String(length=128), nullable=False),
        sa.Column("last_event_index", sa.Integer(), nullable=False),
        sa.Column("terminated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("termination_event_id", sa.String(length=256), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "last_event_index >= 0",
            name="ck_agent_event_projection_cursor_index",
        ),
        sa.ForeignKeyConstraint(
            ["case_ref"], ["cases.case_ref"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("command_id"),
    )
    op.create_index(
        "ix_agent_event_projection_cursors_case_ref",
        "agent_event_projection_cursors",
        ["case_ref"],
    )

    op.create_table(
        "rejected_agent_events",
        sa.Column("source_message_id", sa.String(length=128), nullable=False),
        sa.Column("event_id", sa.String(length=256), nullable=True),
        sa.Column("case_ref", sa.String(length=128), nullable=True),
        sa.Column("raw_body", sa.Text(), nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=False),
        sa.Column(
            "rejected_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("source_message_id"),
    )
    op.create_index(
        "ix_rejected_agent_events_event_id", "rejected_agent_events", ["event_id"]
    )
    op.create_index(
        "ix_rejected_agent_events_case_ref", "rejected_agent_events", ["case_ref"]
    )


def downgrade() -> None:
    op.drop_index(
        "ix_rejected_agent_events_case_ref", table_name="rejected_agent_events"
    )
    op.drop_index(
        "ix_rejected_agent_events_event_id", table_name="rejected_agent_events"
    )
    op.drop_table("rejected_agent_events")
    op.drop_index(
        "ix_agent_event_projection_cursors_case_ref",
        table_name="agent_event_projection_cursors",
    )
    op.drop_table("agent_event_projection_cursors")
    op.drop_index(
        "ix_processed_agent_events_case_ref", table_name="processed_agent_events"
    )
    op.drop_table("processed_agent_events")
    op.drop_table("agent_command_outbox")
