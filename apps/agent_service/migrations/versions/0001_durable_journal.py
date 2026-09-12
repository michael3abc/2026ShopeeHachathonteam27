"""Command identity, leases and transactional result outbox."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0001_durable_journal"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("agent_threads", sa.Column("thread_id", sa.Text(), primary_key=True), sa.Column("case_ref", sa.Text(), nullable=False, unique=True), sa.Column("start_command_id", sa.Text(), nullable=False, unique=True))
    op.create_table("command_journal", sa.Column("command_id", sa.Text(), primary_key=True), sa.Column("thread_id", sa.Text(), sa.ForeignKey("agent_threads.thread_id"), nullable=False), sa.Column("case_ref", sa.Text(), nullable=False), sa.Column("payload_hash", sa.String(64), nullable=False), sa.Column("request", JSONB(), nullable=False), sa.Column("status", sa.String(20), nullable=False), sa.Column("lease_owner", sa.Text(), nullable=False), sa.Column("leased_until", sa.DateTime(timezone=True), nullable=False), sa.Column("initial_checkpoint_id", sa.Text()), sa.Column("result", JSONB()), sa.Column("distillation_input", JSONB()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.CheckConstraint("status IN ('CLAIMED','TERMINAL')", name="journal_status_valid"))
    op.create_index("ix_command_journal_thread_id", "command_journal", ["thread_id"])
    op.create_table("agent_event_outbox", sa.Column("event_id", sa.Text(), primary_key=True), sa.Column("command_id", sa.Text(), sa.ForeignKey("command_journal.command_id"), nullable=False), sa.Column("event_index", sa.Integer(), nullable=False), sa.Column("payload", JSONB(), nullable=False), sa.Column("published_at", sa.DateTime(timezone=True)), sa.Column("lease_token", sa.Text()), sa.Column("claimed_until", sa.DateTime(timezone=True)), sa.UniqueConstraint("command_id", "event_index", name="agent_event_index_unique"))


def downgrade():
    op.execute("DO $$ BEGIN IF EXISTS (SELECT 1 FROM command_journal) THEN RAISE EXCEPTION 'Journal data exists; archive before downgrade'; END IF; END $$")
    for table in ("agent_event_outbox", "command_journal", "agent_threads"):
        op.drop_table(table)
