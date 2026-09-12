"""Preserve the exact distillation profile separately from the prompt version."""

import sqlalchemy as sa
from alembic import op

revision = "0002_memory_model_profile"
down_revision = "0001_memory_replay"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("memory_job_results", sa.Column("model_profile", sa.JSON(none_as_null=True)))


def downgrade() -> None:
    if op.get_context().as_sql:
        op.execute(
            "DO $$ BEGIN IF EXISTS (SELECT 1 FROM memory_job_results "
            "WHERE model_profile IS NOT NULL) THEN RAISE EXCEPTION "
            "'cannot discard recorded memory model provenance'; "
            "END IF; END $$"
        )
        with op.batch_alter_table("memory_job_results") as batch:
            batch.drop_column("model_profile")
        return
    connection = op.get_bind()
    recorded = connection.scalar(sa.text(
        "SELECT 1 FROM memory_job_results WHERE model_profile IS NOT NULL LIMIT 1"
    ))
    if recorded is not None:
        raise RuntimeError("cannot discard recorded memory model provenance")
    with op.batch_alter_table("memory_job_results") as batch:
        batch.drop_column("model_profile")
