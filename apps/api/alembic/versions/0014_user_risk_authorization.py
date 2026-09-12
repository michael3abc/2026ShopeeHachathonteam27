"""Immutable user risk history and authorization snapshots."""
import sqlalchemy as sa
from alembic import op

revision = "0014_user_risk_authorization"
down_revision = "0013_activity_tracing"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("user_risk_profiles",
        sa.Column("user_ref",sa.String(128),primary_key=True),
        sa.Column("account_created_at",sa.DateTime(timezone=True),nullable=False),
        sa.Column("orders_90d",sa.Integer(),nullable=False),
        sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False),sa.CheckConstraint("orders_90d >= 0"))
    op.create_table("user_risk_events",
        sa.Column("event_ref",sa.String(256),primary_key=True),
        sa.Column("user_ref",sa.String(128),nullable=False),
        sa.Column("case_ref",sa.String(128),nullable=False),
        sa.Column("order_ref",sa.String(128),nullable=False),
        sa.Column("event_type",sa.String(32),nullable=False),
        sa.Column("reason_code",sa.String(64)),
        sa.Column("occurred_at",sa.DateTime(timezone=True),nullable=False),
        sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint("case_ref","event_type"),
        sa.CheckConstraint("event_type IN ('CLAIM_REGISTERED', 'REFUND_SUCCEEDED')"),
        sa.CheckConstraint("event_type != 'CLAIM_REGISTERED' OR reason_code IS NOT NULL"))
    op.create_index("ix_user_risk_events_user_ref","user_risk_events",["user_ref"])
    op.create_index("ix_user_risk_events_occurred_at","user_risk_events",["occurred_at"])
    op.create_table("user_risk_snapshots",
        sa.Column("snapshot_ref",sa.String(256),primary_key=True),
        sa.Column("case_ref",sa.String(128),nullable=False),
        sa.Column("user_ref",sa.String(128),nullable=False),
        sa.Column("reason_code",sa.String(64),nullable=False),
        sa.Column("as_of",sa.DateTime(timezone=True),nullable=False),
        sa.Column("payload",sa.JSON(),nullable=False),
        sa.Column("payload_hash",sa.String(64),nullable=False),
        sa.UniqueConstraint("case_ref","reason_code","as_of"))


def downgrade():
    if op.get_context().as_sql:
        op.execute("DO $$ BEGIN IF EXISTS (SELECT 1 FROM user_risk_events) OR EXISTS (SELECT 1 FROM user_risk_snapshots) OR EXISTS (SELECT 1 FROM user_risk_profiles) THEN RAISE EXCEPTION 'user risk history must be archived before downgrade'; END IF; END $$")
    else:
        for table in ("user_risk_events","user_risk_snapshots","user_risk_profiles"):
            if op.get_bind().execute(sa.text(f"SELECT 1 FROM {table} LIMIT 1")).first():
                raise RuntimeError("user risk history must be archived before downgrade")
    op.drop_table("user_risk_snapshots")
    op.drop_table("user_risk_events")
    op.drop_table("user_risk_profiles")
