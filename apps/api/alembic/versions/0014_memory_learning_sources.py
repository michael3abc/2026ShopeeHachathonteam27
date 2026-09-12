"""General learning sources and explicit experience boundaries."""

import json
from hashlib import sha256

import sqlalchemy as sa
from alembic import op

revision = "0014_memory_learning_sources"
down_revision = "0013_activity_tracing"
branch_labels = None
depends_on = None


def _rehash(connection, *, upgrade):
    # Keep the payload hash consistent with the new DTO, without altering
    # governance, source values, summaries, vectors or approval/retirement events.
    table = sa.Table("operational_memories", sa.MetaData(), autoload_with=connection)
    for row in connection.execute(sa.select(table)).mappings():
        if row["retrieval_summary"] is None:
            continue  # Pre-vector historical record has no current candidate DTO.
        payload = {key: row[key] for key in (
            "memory_id", "retrieval_summary", "trigger_conditions",
            "recommended_behavior", "rationale", "source_case_refs",
            "policy_version", "claim_registry_version", "confidence",
        )}
        source_field = "source_event_refs" if upgrade else "source_revision_event_refs"
        payload[source_field] = row[source_field]
        if upgrade:
            payload["applicability_limits"] = row["applicability_limits"]
            payload["prohibited_inferences"] = row["prohibited_inferences"]
        payload["status"] = "CANDIDATE"
        payload["scope"] = {"market": row["scope_market"],
            "reason_codes": row["scope_reason_codes"],
            "claim_ids": row["scope_claim_ids"], "categories": row["scope_categories"]}
        digest = sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                   separators=(",", ":")).encode()).hexdigest()
        connection.execute(table.update().where(table.c.memory_id == row["memory_id"])
                           .values(candidate_payload_hash=digest))


def upgrade():
    with op.batch_alter_table("operational_memories") as batch:
        batch.alter_column("source_revision_event_refs", new_column_name="source_event_refs", existing_type=sa.JSON())
        batch.add_column(sa.Column("applicability_limits", sa.JSON(), nullable=False, server_default="[]"))
        batch.add_column(sa.Column("prohibited_inferences", sa.JSON(), nullable=False, server_default="[]"))
    _rehash(op.get_bind(), upgrade=True)


def downgrade():
    connection = op.get_bind()
    table = sa.Table("operational_memories", sa.MetaData(), autoload_with=connection)
    for row in connection.execute(sa.select(table)).mappings():
        if (row["applicability_limits"] or row["prohibited_inferences"]
                or any(ref.startswith("LEARNING-") for ref in row["source_event_refs"])):
            raise RuntimeError("cannot downgrade v2 learning records into correction-only sources")
    with op.batch_alter_table("operational_memories") as batch:
        batch.alter_column("source_event_refs", new_column_name="source_revision_event_refs", existing_type=sa.JSON())
        batch.drop_column("applicability_limits")
        batch.drop_column("prohibited_inferences")
    _rehash(connection, upgrade=False)
