"""Create versioned structured Policy RAG storage.

Revision ID: 0003_policy_rag
Revises: 0002_case_lifecycle
Create Date: 2026-09-06
"""

from collections.abc import Sequence

from alembic import op
from pgvector.sqlalchemy import Vector
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY

revision: str = "0003_policy_rag"
down_revision: str | None = "0002_case_lifecycle"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _array_type() -> ARRAY:
    return ARRAY(sa.String()).with_variant(sa.JSON(), "sqlite")


def _embedding_type() -> Vector:
    return Vector(1536).with_variant(sa.JSON(), "sqlite")


def upgrade() -> None:
    bind = op.get_bind()
    is_postgresql = bind.dialect.name == "postgresql"
    if is_postgresql:
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "policy_documents",
        sa.Column("document_id", sa.String(length=128), nullable=False),
        sa.Column("policy_family", sa.String(length=128), nullable=False),
        sa.Column("version", sa.String(length=128), nullable=False),
        sa.Column("source_ref", sa.String(length=512), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("document_id"),
        sa.UniqueConstraint(
            "policy_family",
            "version",
            name="uq_policy_documents_family_version",
        ),
        sa.UniqueConstraint(
            "source_ref",
            "version",
            name="uq_policy_documents_source_version",
        ),
    )
    op.create_table(
        "policy_clauses",
        sa.Column("clause_id", sa.String(length=256), nullable=False),
        sa.Column("document_id", sa.String(length=128), nullable=False),
        sa.Column("policy_version", sa.String(length=256), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("markets", _array_type(), nullable=False),
        sa.Column("reason_codes", _array_type(), nullable=False),
        sa.Column("categories", _array_type(), nullable=False),
        sa.Column("required_claim_ids", _array_type(), nullable=False),
        sa.Column("allowed_actions", _array_type(), nullable=False),
        sa.Column("return_policy", sa.String(length=32), nullable=False),
        sa.Column("clause_text", sa.Text(), nullable=False),
        sa.Column("embedding_model", sa.String(length=128), nullable=False),
        sa.Column("embedding", _embedding_type(), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["policy_documents.document_id"]),
        sa.PrimaryKeyConstraint("clause_id"),
    )
    op.create_index(
        "ix_policy_clauses_document_id",
        "policy_clauses",
        ["document_id"],
        unique=False,
    )
    op.create_table(
        "policy_retrievals",
        sa.Column("retrieval_id", sa.String(length=128), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("bundle_version", sa.String(length=128), nullable=False),
        sa.Column("retrieval_status", sa.String(length=32), nullable=False),
        sa.Column("bundle_payload", sa.JSON(), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("retrieval_id"),
        sa.UniqueConstraint(
            "bundle_version", name="uq_policy_retrievals_bundle_version"
        ),
    )
    op.create_index(
        "ix_policy_retrievals_request_hash",
        "policy_retrievals",
        ["request_hash"],
        unique=False,
    )

    if is_postgresql:
        op.create_index(
            "ix_policy_clauses_markets_gin",
            "policy_clauses",
            ["markets"],
            unique=False,
            postgresql_using="gin",
        )
        op.create_index(
            "ix_policy_clauses_reason_codes_gin",
            "policy_clauses",
            ["reason_codes"],
            unique=False,
            postgresql_using="gin",
        )
        op.create_index(
            "ix_policy_clauses_categories_gin",
            "policy_clauses",
            ["categories"],
            unique=False,
            postgresql_using="gin",
        )
        op.execute(
            "CREATE INDEX ix_policy_clauses_embedding_hnsw "
            "ON policy_clauses USING hnsw (embedding vector_cosine_ops) "
            "WITH (m = 16, ef_construction = 64)"
        )


def downgrade() -> None:
    op.drop_table("policy_retrievals")
    op.drop_table("policy_clauses")
    op.drop_table("policy_documents")
