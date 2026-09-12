"""Reserve order items before refund mutation; stop execution during upgrade.

Revision ID: 0007_refund_item_reservations
Revises: 0006_refund_execution
"""

from hashlib import sha256
import json

from alembic import op
import sqlalchemy as sa

revision = "0007_refund_item_reservations"
down_revision = "0006_refund_execution"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if not op.get_context().as_sql:
        _validate_legacy_rows()
    elif op.get_context().dialect.name == "postgresql":
        # Offline SQL is safe for fresh databases. Populated upgrades need the
        # Python canonical-hash and ledger preflight from online Alembic.
        op.execute(sa.text("""DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM refund_executions)
                OR EXISTS (SELECT 1 FROM refund_execution_items) THEN
                RAISE EXCEPTION 'Populated refund migration requires online Alembic preflight; stop execution and run alembic upgrade head';
            END IF;
        END $$"""))
    else:
        raise RuntimeError("offline reservation migration requires PostgreSQL")
    op.create_table(
        "refund_item_reservations",
        sa.Column("order_ref", sa.String(128), nullable=False),
        sa.Column("line_item_ref", sa.String(128), nullable=False),
        sa.Column("execution_ref", sa.String(128), nullable=False),
        sa.Column("reserved_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("order_ref", "line_item_ref"),
        sa.ForeignKeyConstraint(["execution_ref"], ["refund_executions.execution_ref"]),
    )
    # Do not use ON CONFLICT: overlapping legacy attempts must block rollout.
    # JSON expansion also works in offline PostgreSQL migration output.
    dialect = op.get_context().dialect.name
    if dialect == "postgresql":
        items = """SELECT e.order_ref, item.value AS line_item_ref,
            e.execution_ref, e.created_at AS reserved_at
            FROM refund_executions e CROSS JOIN LATERAL json_array_elements_text(
                e.request_payload->'resolution_handoff'->'final_decision'
                    ->'refund_scope'->'line_item_ids') AS item(value)
            WHERE e.state = 'IN_PROGRESS'"""
    elif dialect == "sqlite":
        items = """SELECT e.order_ref, item.value AS line_item_ref,
            e.execution_ref, e.created_at AS reserved_at
            FROM refund_executions e, json_each(e.request_payload,
                '$.resolution_handoff.final_decision.refund_scope.line_item_ids') item
            WHERE e.state = 'IN_PROGRESS'"""
    else:
        raise RuntimeError("unsupported reservation migration database")
    op.execute(sa.text("""INSERT INTO refund_item_reservations
        (order_ref, line_item_ref, execution_ref, reserved_at)
        SELECT order_ref, line_item_ref, execution_ref, applied_at
        FROM refund_execution_items UNION ALL """ + items))


def downgrade() -> None:
    op.drop_table("refund_item_reservations")


def _validate_legacy_rows() -> None:
    """Reject ambiguous ownership before DDL, including on SQLite."""
    connection = op.get_bind()
    executions = sa.table(
        "refund_executions",
        sa.column("execution_ref", sa.String), sa.column("handoff_id", sa.String),
        sa.column("case_ref", sa.String), sa.column("order_ref", sa.String),
        sa.column("state", sa.String), sa.column("request_payload", sa.JSON),
        sa.column("payload_hash", sa.String),
    )
    ledger = sa.table(
        "refund_execution_items", sa.column("execution_ref", sa.String),
        sa.column("order_ref", sa.String), sa.column("line_item_ref", sa.String),
    )
    rows = connection.execute(sa.select(executions)).mappings().all()
    owners: dict[tuple[str, str], str] = {}
    expected_ledger: set[tuple[str, str, str]] = set()
    for row in rows:
        if row["state"] not in {"IN_PROGRESS", "SUCCEEDED"}:
            continue
        try:
            payload = row["request_payload"]
            canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            if sha256(canonical.encode()).hexdigest() != row["payload_hash"]:
                raise ValueError("request hash mismatch")
            resolution = payload["resolution_handoff"]
            decision = resolution["final_decision"]
            scope = decision["refund_scope"]["line_item_ids"]
            if (
                resolution["handoff_id"] != row["handoff_id"]
                or resolution["case_ref"] != row["case_ref"]
                or resolution["execution_blocked"] is not False
                or decision["action"] != "FULL_REFUND"
                or not isinstance(row["order_ref"], str) or not row["order_ref"].strip()
                or not isinstance(scope, list) or not scope
                or any(not isinstance(item, str) or not item.strip() for item in scope)
                or len(set(scope)) != len(scope)
            ):
                raise ValueError("inconsistent execution request")
            for item in scope:
                key = (row["order_ref"], item)
                if key in owners:
                    raise ValueError(f"overlapping executions {owners[key]} and {row['execution_ref']}")
                owners[key] = row["execution_ref"]
                if row["state"] == "SUCCEEDED":
                    expected_ledger.add((row["execution_ref"], row["order_ref"], item))
        except (KeyError, TypeError, ValueError) as error:
            raise RuntimeError(
                f"Reservation migration blocked for {row['execution_ref']}: {error}. "
                "Stop refund execution and reconcile legacy records with external outcomes."
            ) from error
    actual_ledger = {tuple(row) for row in connection.execute(sa.select(ledger))}
    if actual_ledger != expected_ledger:
        raise RuntimeError(
            "Reservation migration blocked: successful ledger differs from execution requests; "
            "stop refund execution and reconcile legacy records with external outcomes."
        )
