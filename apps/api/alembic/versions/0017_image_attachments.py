"""API-owned image attachments."""

import sqlalchemy as sa
from alembic import op

revision = "0017_image_attachments"
down_revision = "0016_policy_v2_fulfillment"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "image_attachments",
        sa.Column("attachment_id", sa.String(128), primary_key=True),
        sa.Column("artifact_ref", sa.String(512), nullable=False, unique=True),
        sa.Column(
            "evidence_id",
            sa.String(128),
            sa.ForeignKey("evidence_items.evidence_id"),
            nullable=False,
        ),
        sa.Column("user_ref", sa.String(128), nullable=False),
        sa.Column("order_ref", sa.String(128), nullable=False),
        sa.Column("case_ref", sa.String(128), sa.ForeignKey("cases.case_ref")),
        sa.Column("subject", sa.String(128), nullable=False),
        sa.Column("media_type", sa.String(32), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("content_sha256", sa.String(64), nullable=False),
    )
    op.create_index("ix_image_attachments_case_ref", "image_attachments", ["case_ref"])


def downgrade():
    if op.get_context().as_sql:
        op.execute(
            "DO $$ BEGIN IF EXISTS (SELECT 1 FROM image_attachments) "
            "THEN RAISE EXCEPTION 'Cannot discard image attachment history'; "
            "END IF; END $$"
        )
    elif (
        op.get_bind()
        .execute(sa.text("SELECT count(*) FROM image_attachments"))
        .scalar_one()
    ):
        raise RuntimeError("Cannot discard image attachment history")
    op.drop_table("image_attachments")
