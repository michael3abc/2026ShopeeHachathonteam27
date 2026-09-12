"""Replace risk-based human submission with Reviewer objections.

Historical risk records remain audit-only; old graph checkpoints cannot resume.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010_reviewer_handoff"
down_revision: str | None = "0009_human_reviews"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("human_reviews") as batch:
        batch.alter_column("risk_payload", new_column_name="legacy_risk_payload",
                           existing_type=sa.JSON(), nullable=True)
        batch.add_column(sa.Column("review_payload", sa.JSON(), nullable=True))
    # Keep the old nullable case risk_route and risk_evaluations as historical
    # data. The application no longer maps, reads, or writes either one.


def downgrade() -> None:
    connection = op.get_bind()
    if not op.get_context().as_sql:
        count = connection.execute(sa.text(
            "SELECT COUNT(*) FROM human_reviews WHERE review_payload IS NOT NULL"
        )).scalar_one()
        if count:
            raise RuntimeError("Reviewer submissions exist; restore a backup to downgrade")
    with op.batch_alter_table("human_reviews") as batch:
        batch.drop_column("review_payload")
        batch.alter_column("legacy_risk_payload", new_column_name="risk_payload",
                           existing_type=sa.JSON(), nullable=False)
