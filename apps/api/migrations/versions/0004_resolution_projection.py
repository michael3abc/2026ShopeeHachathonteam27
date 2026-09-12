"""Canonical final decision and durable resolution jobs."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0004_resolution_projection"
down_revision = "0003_refund_safety"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("cases", sa.Column("final_resolution", JSONB()))
    op.add_column("cases", sa.Column("refund_execution", JSONB()))
    op.create_table("resolution_jobs", sa.Column("handoff_id", sa.Text(), primary_key=True), sa.Column("case_ref", sa.Text(), sa.ForeignKey("cases.case_ref"), nullable=False), sa.Column("request", JSONB(), nullable=False), sa.Column("status", sa.String(20), nullable=False), sa.Column("attempts", sa.Integer(), nullable=False), sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False), sa.Column("claimed_until", sa.DateTime(timezone=True)), sa.Column("lease_token", sa.Text()), sa.Column("error_code", sa.Text()), sa.CheckConstraint("status IN ('PENDING','COMPLETED','FAILED')", name="resolution_job_status_valid"))
    op.create_index("ix_resolution_jobs_case_ref", "resolution_jobs", ["case_ref"])


def downgrade():
    op.execute("DO $$ BEGIN IF EXISTS (SELECT 1 FROM resolution_jobs) THEN RAISE EXCEPTION 'Resolution data exists; archive before downgrade'; END IF; END $$")
    op.drop_table("resolution_jobs")
    op.drop_column("cases", "refund_execution")
    op.drop_column("cases", "final_resolution")
