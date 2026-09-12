BEGIN;

-- Running upgrade 0005_safety_verification_risk -> 0006_refund_execution

CREATE TABLE refund_executions (
    execution_ref VARCHAR(128) NOT NULL,
    handoff_id VARCHAR(256) NOT NULL,
    case_ref VARCHAR(128) NOT NULL,
    payload_hash VARCHAR(64) NOT NULL,
    request_payload JSON NOT NULL,
    order_ref VARCHAR(128),
    application_result_payload JSON,
    state VARCHAR(16) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    application_started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY (execution_ref),
    CONSTRAINT ck_refund_executions_state CHECK (state IN ('IN_PROGRESS', 'SUCCEEDED', 'REJECTED')),
    CONSTRAINT ck_refund_executions_terminal_result CHECK ((state = 'IN_PROGRESS' AND application_result_payload IS NULL AND completed_at IS NULL) OR (state IN ('SUCCEEDED', 'REJECTED') AND application_result_payload IS NOT NULL AND completed_at IS NOT NULL)),
    UNIQUE (handoff_id)
);

CREATE INDEX ix_refund_executions_payload_hash ON refund_executions (payload_hash);

CREATE TABLE refund_execution_items (
    execution_ref VARCHAR(128) NOT NULL,
    line_item_ref VARCHAR(128) NOT NULL,
    order_ref VARCHAR(128) NOT NULL,
    applied_at TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY (execution_ref, line_item_ref),
    FOREIGN KEY(execution_ref) REFERENCES refund_executions (execution_ref),
    CONSTRAINT uq_refund_execution_items_order_line_item UNIQUE (order_ref, line_item_ref)
);

UPDATE alembic_version SET version_num='0006_refund_execution' WHERE alembic_version.version_num = '0005_safety_verification_risk';

COMMIT;
