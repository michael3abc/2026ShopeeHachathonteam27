"""Independent activity sequence and transactional narration outbox."""

import sqlalchemy as sa
from alembic import op

revision = "0013_activity_tracing"
down_revision = "0012_human_review_dossier"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "case_activities",
        sa.Column("event_id", sa.String(200), primary_key=True),
        sa.Column(
            "case_ref", sa.String(128), sa.ForeignKey("cases.case_ref"), nullable=False
        ),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.UniqueConstraint("case_ref", "seq"),
    )
    op.create_index("ix_case_activities_case_ref", "case_activities", ["case_ref"])
    op.create_table(
        "activity_narration_outbox",
        sa.Column(
            "source_event_id",
            sa.String(200),
            sa.ForeignKey("case_activities.event_id"),
            primary_key=True,
        ),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("dispatched", sa.Boolean(), nullable=False),
        sa.Column("result_event_id", sa.String(200)),
    )
    op.create_index(
        "ix_activity_narration_outbox_dispatched",
        "activity_narration_outbox",
        ["dispatched"],
    )


def downgrade():
    if op.get_context().as_sql:
        raise RuntimeError("Activity downgrade requires online empty-data preflight")
    if (
        op.get_bind()
        .execute(sa.text("SELECT count(*) FROM case_activities"))
        .scalar_one()
    ):
        raise RuntimeError("Cannot discard activity audit history")
    op.drop_table("activity_narration_outbox")
    op.drop_table("case_activities")
