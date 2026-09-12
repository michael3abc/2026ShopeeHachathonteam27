"""Create the backend-owned case lifecycle tables.

Revision ID: 0002_case_lifecycle
Revises: 0001_evidence_capability
Create Date: 2026-09-06
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0002_case_lifecycle"
down_revision: str | None = "0001_evidence_capability"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CASE_STATUSES = (
    "OBSERVING",
    "AWAITING_CLARIFICATION",
    "AWAITING_EVIDENCE",
    "AWAITING_HUMAN_REVIEW",
    "EXECUTING",
    "RESOLVED",
    "ESCALATED",
)
RISK_ROUTES = ("AUTO", "HUMAN", "BLOCK")
EVENT_KINDS = ("agent_event", "user_turn")


def _in_list(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(value) for value in values)})"


def upgrade() -> None:
    op.create_table(
        "cases",
        sa.Column("case_ref", sa.String(length=128), nullable=False),
        sa.Column("thread_id", sa.String(length=128), nullable=False),
        sa.Column("order_ref", sa.String(length=128), nullable=False),
        sa.Column("user_ref", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("risk_route", sa.String(length=16), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(_in_list("status", CASE_STATUSES), name="ck_cases_status"),
        sa.CheckConstraint(
            f"risk_route IS NULL OR {_in_list('risk_route', RISK_ROUTES)}",
            name="ck_cases_risk_route",
        ),
        sa.CheckConstraint(
            "length(trim(order_ref)) > 0", name="ck_cases_order_ref_not_blank"
        ),
        sa.CheckConstraint(
            "length(trim(user_ref)) > 0", name="ck_cases_user_ref_not_blank"
        ),
        sa.PrimaryKeyConstraint("case_ref"),
        sa.UniqueConstraint("thread_id"),
    )
    op.create_index("ix_cases_order_ref", "cases", ["order_ref"])
    op.create_index("ix_cases_user_ref", "cases", ["user_ref"])

    op.create_table(
        "case_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("case_ref", sa.String(length=128), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint("seq >= 1", name="ck_case_events_seq_positive"),
        sa.CheckConstraint(_in_list("kind", EVENT_KINDS), name="ck_case_events_kind"),
        sa.ForeignKeyConstraint(["case_ref"], ["cases.case_ref"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("case_ref", "seq", name="uq_case_events_case_ref_seq"),
    )
    op.create_index("ix_case_events_case_ref", "case_events", ["case_ref"])


def downgrade() -> None:
    op.drop_index("ix_case_events_case_ref", table_name="case_events")
    op.drop_table("case_events")
    op.drop_index("ix_cases_user_ref", table_name="cases")
    op.drop_index("ix_cases_order_ref", table_name="cases")
    op.drop_table("cases")
