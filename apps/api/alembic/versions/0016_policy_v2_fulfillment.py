"""Versioned policy evaluations, consent and API return fulfillment."""
import json
import sqlalchemy as sa
from alembic import op

revision = "0016_policy_v2_fulfillment"
down_revision = "0015_user_risk_authorization"
branch_labels = None
depends_on = None

OLD_STATES = "'OBSERVING','AWAITING_CLARIFICATION','AWAITING_EVIDENCE','AWAITING_HUMAN_REVIEW','EXECUTING','RESOLVED','ESCALATED'"
NEW_STATES = OLD_STATES + ",'AWAITING_POLICY_CONFIRMATION','AWAITING_RETURN_CONFIRMATION','AWAITING_RETURN','AWAITING_RETURN_INSPECTION'"
TABLES = ("policy_evaluations","policy_selections","policy_confirmations","return_authorizations","return_event_receipts","refund_completion_outbox","demo_sessions")


def _s(name, size=256, nullable=False, primary_key=False):
    return sa.Column(name,sa.String(size),nullable=nullable,primary_key=primary_key)


def _json(name, nullable=False):
    return sa.Column(name,sa.JSON(),nullable=nullable)


def upgrade():
    op.add_column("operational_memories",_s("scope_policy_path_id",64,True))
    op.add_column("policy_documents",_json("path_payload",True))
    op.add_column("policy_clauses",_s("path_id",64,True))
    op.add_column("cases",sa.Column("policy_schema_version",sa.String(8),nullable=False,server_default="v1"))
    op.add_column("cases",_json("v2_context_payload",True))
    with op.batch_alter_table("cases") as batch:
        batch.drop_constraint("ck_cases_status",type_="check")
        batch.create_check_constraint("ck_cases_status",f"status IN ({NEW_STATES})")
    op.create_table("policy_evaluations",_s("evaluation_ref",primary_key=True),_s("case_ref",128),_json("payload"))
    op.create_index("ix_policy_evaluations_case_ref","policy_evaluations",["case_ref"])
    op.create_table("policy_selections",_s("case_ref",128,primary_key=True),
        sa.Column("selection_version",sa.Integer(),primary_key=True),_json("payload"))
    op.create_table("policy_confirmations",_s("request_ref",primary_key=True),_s("case_ref",128),
        _json("request_payload"),_json("response_payload",True),_s("idempotency_key",nullable=True))
    op.create_index("ix_policy_confirmations_case_ref","policy_confirmations",["case_ref"])
    op.create_table("return_authorizations",_s("authorization_ref",primary_key=True),_s("case_ref",128),
        _s("execution_ref",128),_json("payload"),_s("payload_hash",64),_s("state",64),
        _json("confirmation_payload",True),_s("arrived_event_id",nullable=True),_s("inspection_event_id",nullable=True),
        _json("execution_result",True),_s("reason",128,True),_s("lease_owner",nullable=True),
        sa.Column("lease_until",sa.DateTime(timezone=True)),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint("case_ref"),sa.UniqueConstraint("execution_ref"))
    op.create_table("return_event_receipts",_s("receipt_ref",primary_key=True),_s("producer_id",128),_s("event_id"),
        _s("authorization_ref"),_json("event_payload"),_json("receipt_payload"),sa.UniqueConstraint("producer_id","event_id"))
    op.create_index("ix_return_event_receipts_authorization_ref","return_event_receipts",["authorization_ref"])
    op.create_table("refund_completion_outbox",_s("resolution_ref",primary_key=True),_json("payload"),sa.Column("published",sa.Boolean(),nullable=False))
    op.create_table("demo_sessions",_s("token_hash",64,primary_key=True),_s("user_ref",128),_s("role",32),
        sa.Column("expires_at",sa.DateTime(timezone=True),nullable=False))


def downgrade():
    if not op.get_context().as_sql:
        source_rows = op.get_bind().execute(sa.text(
            "SELECT source_event_refs, applicability_limits, "
            "prohibited_inferences FROM operational_memories"
        )).mappings()
        for row in source_rows:
            values = {
                key: json.loads(row[key]) if isinstance(row[key], str) else row[key]
                for key in row.keys()
            }
            if (
                values["applicability_limits"]
                or values["prohibited_inferences"]
                or any(
                    str(ref).startswith("LEARNING-")
                    for ref in values["source_event_refs"] or []
                )
            ):
                raise RuntimeError(
                    "cannot downgrade v2 learning sources to correction-only history"
                )
    condition = " OR ".join(f"EXISTS (SELECT 1 FROM {table})" for table in TABLES) + " OR EXISTS (SELECT 1 FROM cases WHERE policy_schema_version = 'v2')"
    if op.get_context().as_sql:
        op.execute(f"DO $$ BEGIN IF {condition} THEN RAISE EXCEPTION 'archive v2 records before downgrade'; END IF; END $$")
    elif op.get_bind().execute(sa.text(f"SELECT ({condition})")).scalar():
        raise RuntimeError("archive v2 records before downgrade")
    for table in reversed(TABLES):
        op.drop_table(table)
    with op.batch_alter_table("cases") as batch:
        batch.drop_constraint("ck_cases_status",type_="check")
        batch.create_check_constraint("ck_cases_status",f"status IN ({OLD_STATES})")
        batch.drop_column("v2_context_payload")
        batch.drop_column("policy_schema_version")
    op.drop_column("policy_clauses","path_id")
    op.drop_column("policy_documents","path_payload")
    op.drop_column("operational_memories","scope_policy_path_id")
