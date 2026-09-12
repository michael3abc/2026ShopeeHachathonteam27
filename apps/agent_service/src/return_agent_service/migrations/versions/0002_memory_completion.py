"""Durable correction/APPLIED join, independent of the API migration chain."""
from alembic import op
import sqlalchemy as sa

revision = "0002_memory_completion"
down_revision = "0001_memory_replay"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("memory_completion_joins",
        sa.Column("resolution_ref",sa.String(256),primary_key=True),
        sa.Column("case_ref",sa.String(128),nullable=False),
        sa.Column("resolution_hash",sa.String(64),nullable=False),
        sa.Column("correction_job",sa.JSON(none_as_null=True)),
        sa.Column("applied_event",sa.JSON(none_as_null=True)),
        sa.Column("published",sa.Boolean(),nullable=False))


def downgrade():
    if op.get_context().as_sql:
        op.execute("DO $$ BEGIN IF EXISTS (SELECT 1 FROM memory_completion_joins) THEN RAISE EXCEPTION 'archive memory completion joins before downgrade'; END IF; END $$")
    elif op.get_bind().execute(sa.text("SELECT 1 FROM memory_completion_joins LIMIT 1")).first():
        raise RuntimeError("archive memory completion joins before downgrade")
    op.drop_table("memory_completion_joins")
