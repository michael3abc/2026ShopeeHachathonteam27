"""Canonical cases, ordered events and transactional command outbox."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_case_lifecycle"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("cases",
        sa.Column("case_ref", sa.Text(), primary_key=True), sa.Column("thread_id", sa.Text(), nullable=False, unique=True),
        sa.Column("order_ref", sa.Text(), nullable=False), sa.Column("user_ref", sa.Text(), nullable=False),
        sa.Column("status", sa.String(40), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        *(sa.Column(name, postgresql.JSONB(), nullable=True) for name in ("clarification_request", "evidence_request", "human_review", "human_review_result")),
        sa.CheckConstraint("status IN ('OBSERVING','AWAITING_CLARIFICATION','AWAITING_EVIDENCE','AWAITING_HUMAN_REVIEW','EXECUTING','RESOLVED','ESCALATED')", name="case_status_valid"))
    for name in ("order_ref", "user_ref"): op.create_index(f"ix_cases_{name}", "cases", [name])
    op.create_table("case_events",
        sa.Column("event_id", sa.Text(), primary_key=True), sa.Column("case_ref", sa.Text(), sa.ForeignKey("cases.case_ref", ondelete="CASCADE"), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False), sa.Column("kind", sa.String(20), nullable=False), sa.Column("payload", postgresql.JSONB(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("case_ref", "seq", name="case_event_sequence_unique"), sa.CheckConstraint("seq > 0", name="case_event_sequence_positive"), sa.CheckConstraint("kind IN ('user_turn','agent_event')", name="case_event_kind_valid"))
    op.create_index("ix_case_events_case_ref", "case_events", ["case_ref"])
    op.create_table("agent_command_outbox",
        sa.Column("command_id", sa.Text(), primary_key=True), sa.Column("case_ref", sa.Text(), sa.ForeignKey("cases.case_ref", ondelete="CASCADE"), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False), sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("attempts", sa.Integer(), nullable=False), sa.Column("claimed_by", sa.Text()), sa.Column("claimed_until", sa.DateTime(timezone=True)), sa.Column("lease_token", sa.Text()),
        sa.CheckConstraint("attempts >= 0", name="outbox_attempts_nonnegative"))
    op.create_index("ix_agent_command_outbox_case_ref", "agent_command_outbox", ["case_ref"])
    op.create_index("outbox_pending", "agent_command_outbox", ["published_at", "claimed_until"])
    op.create_table("processed_agent_events",
        sa.Column("event_id", sa.Text(), primary_key=True), sa.Column("case_ref", sa.Text(), sa.ForeignKey("cases.case_ref"), nullable=False),
        sa.Column("command_id", sa.Text(), nullable=False), sa.Column("event_index", sa.Integer(), nullable=False), sa.Column("payload_hash", sa.String(64), nullable=False), sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_processed_agent_events_command_id", "processed_agent_events", ["command_id"])
    op.create_table("agent_event_projection_cursors",
        sa.Column("command_id", sa.Text(), primary_key=True), sa.Column("case_ref", sa.Text(), sa.ForeignKey("cases.case_ref"), nullable=False), sa.Column("event_index", sa.Integer(), nullable=False), sa.Column("terminal_event_id", sa.Text()), sa.CheckConstraint("event_index >= 0", name="projection_index_nonnegative"))
    op.create_table("rejected_agent_events",
        sa.Column("source_message_id", sa.Text(), primary_key=True), sa.Column("error_code", sa.Text(), nullable=False), sa.Column("payload_hash", sa.String(64), nullable=False), sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=False))


def downgrade():
    for name in ("rejected_agent_events", "agent_event_projection_cursors", "processed_agent_events", "agent_command_outbox", "case_events", "cases"):
        op.drop_table(name)
