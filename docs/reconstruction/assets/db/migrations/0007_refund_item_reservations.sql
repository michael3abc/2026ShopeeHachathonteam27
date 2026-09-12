BEGIN;

-- Running upgrade 0006_refund_execution -> 0007_refund_item_reservations

DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM refund_executions)
                OR EXISTS (SELECT 1 FROM refund_execution_items) THEN
                RAISE EXCEPTION 'Populated refund migration requires online Alembic preflight; stop execution and run alembic upgrade head';
            END IF;
        END $$;

CREATE TABLE refund_item_reservations (
    order_ref VARCHAR(128) NOT NULL,
    line_item_ref VARCHAR(128) NOT NULL,
    execution_ref VARCHAR(128) NOT NULL,
    reserved_at TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY (order_ref, line_item_ref),
    FOREIGN KEY(execution_ref) REFERENCES refund_executions (execution_ref)
);

INSERT INTO refund_item_reservations
        (order_ref, line_item_ref, execution_ref, reserved_at)
        SELECT order_ref, line_item_ref, execution_ref, applied_at
        FROM refund_execution_items UNION ALL SELECT e.order_ref, item.value AS line_item_ref,
            e.execution_ref, e.created_at AS reserved_at
            FROM refund_executions e CROSS JOIN LATERAL json_array_elements_text(
                e.request_payload->'resolution_handoff'->'final_decision'
                    ->'refund_scope'->'line_item_ids') AS item(value)
            WHERE e.state = 'IN_PROGRESS';

UPDATE alembic_version SET version_num='0007_refund_item_reservations' WHERE alembic_version.version_num = '0006_refund_execution';

COMMIT;
