"""Trusted inputs, immutable policy retrievals and authorization history."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0002_capabilities"
down_revision = "0001_case_lifecycle"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("trusted_orders", sa.Column("order_ref", sa.Text(), primary_key=True), sa.Column("market", sa.Text(), nullable=False), sa.Column("snapshot", JSONB(), nullable=False))
    op.create_table("evidence_metadata", sa.Column("artifact_ref", sa.Text(), primary_key=True), sa.Column("payload", JSONB(), nullable=False))
    op.create_table("policy_clauses", sa.Column("clause_id", sa.Text(), primary_key=True), sa.Column("policy_version", sa.Text(), primary_key=True), sa.Column("payload", JSONB(), nullable=False))
    op.create_table("policy_retrievals", sa.Column("bundle_version", sa.Text(), primary_key=True), sa.Column("case_ref", sa.Text(), sa.ForeignKey("cases.case_ref"), nullable=False), sa.Column("request", JSONB(), nullable=False), sa.Column("bundle", JSONB(), nullable=False))
    op.create_index("ix_policy_retrievals_case_ref", "policy_retrievals", ["case_ref"])
    op.create_table("handoff_verifications", sa.Column("handoff_id", sa.Text(), primary_key=True), sa.Column("case_ref", sa.Text(), sa.ForeignKey("cases.case_ref"), nullable=False), sa.Column("payload_hash", sa.String(64), nullable=False), sa.Column("handoff", JSONB(), nullable=False), sa.Column("result", JSONB(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_handoff_verifications_case_ref", "handoff_verifications", ["case_ref"])
    op.create_table("human_reviews", sa.Column("review_ref", sa.Text(), primary_key=True), sa.Column("handoff_id", sa.Text(), sa.ForeignKey("handoff_verifications.handoff_id"), unique=True, nullable=False), sa.Column("case_ref", sa.Text(), sa.ForeignKey("cases.case_ref"), nullable=False), sa.Column("payload_hash", sa.String(64), nullable=False), sa.Column("request", JSONB(), nullable=False), sa.Column("result", JSONB()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_human_reviews_case_ref", "human_reviews", ["case_ref"])


def downgrade():
    for table in ("human_reviews", "handoff_verifications", "policy_retrievals", "policy_clauses", "evidence_metadata", "trusted_orders"):
        op.drop_table(table)
