"""Save first memory outputs and replayable terminal events in the Agent DB."""

import sqlalchemy as sa
from alembic import op

revision = "0001_memory_replay"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "memory_job_results",
        sa.Column("job_id", sa.String(256), primary_key=True),
        sa.Column("input_hash", sa.String(64), nullable=False),
        sa.Column("prompt_version", sa.String(256), nullable=False),
        sa.Column("result", sa.JSON(none_as_null=True)),
        sa.Column("terminal_event", sa.JSON(none_as_null=True)),
    )


def downgrade() -> None:
    op.drop_table("memory_job_results")
