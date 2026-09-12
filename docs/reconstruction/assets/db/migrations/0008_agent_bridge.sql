BEGIN;

-- Running upgrade 0007_refund_item_reservations -> 0008_agent_bridge

CREATE TABLE agent_command_outbox (
    command_id VARCHAR(128) NOT NULL,
    payload JSON NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    published_at TIMESTAMP WITH TIME ZONE,
    claimed_by VARCHAR(256),
    claimed_until TIMESTAMP WITH TIME ZONE,
    lease_token VARCHAR(32),
    attempt_count INTEGER DEFAULT '0' NOT NULL,
    last_error TEXT,
    PRIMARY KEY (command_id),
    CONSTRAINT ck_agent_command_outbox_attempt_count CHECK (attempt_count >= 0)
);

CREATE TABLE processed_agent_events (
    event_id VARCHAR(256) NOT NULL,
    case_ref VARCHAR(128) NOT NULL,
    command_id VARCHAR(128) NOT NULL,
    event_index INTEGER NOT NULL,
    payload_hash VARCHAR(64) NOT NULL,
    processed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    PRIMARY KEY (event_id),
    FOREIGN KEY(case_ref) REFERENCES cases (case_ref) ON DELETE CASCADE
);

CREATE INDEX ix_processed_agent_events_case_ref ON processed_agent_events (case_ref);

CREATE TABLE agent_event_projection_cursors (
    command_id VARCHAR(128) NOT NULL,
    case_ref VARCHAR(128) NOT NULL,
    last_event_index INTEGER NOT NULL,
    terminated_at TIMESTAMP WITH TIME ZONE,
    termination_event_id VARCHAR(256),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    PRIMARY KEY (command_id),
    CONSTRAINT ck_agent_event_projection_cursor_index CHECK (last_event_index >= 0),
    FOREIGN KEY(case_ref) REFERENCES cases (case_ref) ON DELETE CASCADE
);

CREATE INDEX ix_agent_event_projection_cursors_case_ref ON agent_event_projection_cursors (case_ref);

CREATE TABLE rejected_agent_events (
    source_message_id VARCHAR(128) NOT NULL,
    event_id VARCHAR(256),
    case_ref VARCHAR(128),
    raw_body TEXT NOT NULL,
    error_code VARCHAR(64) NOT NULL,
    error_message TEXT NOT NULL,
    rejected_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    PRIMARY KEY (source_message_id)
);

CREATE INDEX ix_rejected_agent_events_event_id ON rejected_agent_events (event_id);

CREATE INDEX ix_rejected_agent_events_case_ref ON rejected_agent_events (case_ref);

UPDATE alembic_version SET version_num='0008_agent_bridge' WHERE alembic_version.version_num = '0007_refund_item_reservations';

COMMIT;
