"""Preserve structured nonconvergence history for human adjudication."""

import sqlalchemy as sa
from alembic import op

revision = "0012_human_review_dossier"
down_revision = "0011_memory_vectors"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("human_reviews") as batch:
        batch.add_column(sa.Column("dossier_payload", sa.JSON(), nullable=True))


def downgrade() -> None:
    if op.get_context().as_sql:
        if op.get_context().dialect.name != "postgresql":
            raise RuntimeError("Offline dossier downgrade requires PostgreSQL")
        op.execute("""DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM human_reviews WHERE dossier_payload IS NOT NULL
                       AND CAST(dossier_payload AS TEXT) <> 'null') THEN
                RAISE EXCEPTION 'Cannot discard human adjudication audit history';
            END IF;
        END $$;""")
        op.drop_column("human_reviews", "dossier_payload")
        return
    connection = op.get_bind()
    if connection.execute(
        sa.text(
            "SELECT count(*) FROM human_reviews WHERE dossier_payload IS NOT NULL AND CAST(dossier_payload AS TEXT) <> 'null'"
        )
    ).scalar_one():
        raise RuntimeError("Cannot discard human adjudication audit history")
    with op.batch_alter_table("human_reviews") as batch:
        batch.drop_column("dossier_payload")
