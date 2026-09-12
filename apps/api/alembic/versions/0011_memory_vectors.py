"""Add derived memory summaries and vectors without changing governed records."""

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision = "0011_memory_vectors"
down_revision = "0010_reviewer_handoff"
branch_labels = None
depends_on = None


def upgrade() -> None:
    vector_type = Vector(1536).with_variant(sa.JSON(), "sqlite")
    with op.batch_alter_table("operational_memories") as batch:
        batch.add_column(sa.Column("retrieval_summary", sa.Text(), nullable=True))
        batch.add_column(sa.Column("summary_version", sa.String(64), nullable=True))
        batch.add_column(sa.Column("summary_hash", sa.String(64), nullable=True))
        batch.add_column(sa.Column("embedding_model", sa.String(128), nullable=True))
        batch.add_column(sa.Column("embedding", vector_type, nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("operational_memories") as batch:
        for name in (
            "embedding",
            "embedding_model",
            "summary_hash",
            "summary_version",
            "retrieval_summary",
        ):
            batch.drop_column(name)
