"""Durable execution, item reservations and idempotent simulated payment receipts."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0003_refund_safety"
down_revision = "0002_capabilities"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("refund_executions", sa.Column("execution_ref", sa.Text(), primary_key=True), sa.Column("handoff_id", sa.Text(), nullable=False, unique=True), sa.Column("case_ref", sa.Text(), sa.ForeignKey("cases.case_ref"), nullable=False), sa.Column("order_ref", sa.Text(), sa.ForeignKey("trusted_orders.order_ref"), nullable=False), sa.Column("payload_hash", sa.String(64), nullable=False), sa.Column("request", JSONB(), nullable=False), sa.Column("status", sa.String(20), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.Column("application_started_at", sa.DateTime(timezone=True)), sa.Column("application_result", JSONB()), sa.CheckConstraint("status IN ('IN_PROGRESS','SUCCEEDED','REJECTED')", name="refund_execution_status_valid"))
    op.create_index("ix_refund_executions_case_ref", "refund_executions", ["case_ref"])
    for table in ("refund_item_reservations", "refund_execution_items"):
        op.create_table(table, sa.Column("order_ref", sa.Text(), sa.ForeignKey("trusted_orders.order_ref"), primary_key=True), sa.Column("line_item_ref", sa.Text(), primary_key=True), sa.Column("execution_ref", sa.Text(), sa.ForeignKey("refund_executions.execution_ref"), nullable=False), sa.Column("amount", sa.Text(), nullable=False))
        op.create_index(f"ix_{table}_execution_ref", table, ["execution_ref"])
    op.create_table("mock_refund_receipts", sa.Column("execution_ref", sa.Text(), primary_key=True), sa.Column("payload_hash", sa.String(64), nullable=False), sa.Column("result", JSONB(), nullable=False))


def downgrade():
    # Financial audit history must be explicitly archived before destructive rollback.
    op.execute("DO $$ BEGIN IF EXISTS (SELECT 1 FROM refund_executions) OR EXISTS (SELECT 1 FROM mock_refund_receipts) THEN RAISE EXCEPTION 'Refund data exists; archive and reconcile before downgrade'; END IF; END $$")
    for table in ("mock_refund_receipts", "refund_execution_items", "refund_item_reservations", "refund_executions"):
        op.drop_table(table)
