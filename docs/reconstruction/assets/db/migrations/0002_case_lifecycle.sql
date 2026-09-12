BEGIN;

-- Running upgrade 0001_evidence_capability -> 0002_case_lifecycle

CREATE TABLE cases (
    case_ref VARCHAR(128) NOT NULL,
    thread_id VARCHAR(128) NOT NULL,
    order_ref VARCHAR(128) NOT NULL,
    user_ref VARCHAR(128) NOT NULL,
    status VARCHAR(32) NOT NULL,
    risk_route VARCHAR(16),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    PRIMARY KEY (case_ref),
    CONSTRAINT ck_cases_status CHECK (status IN ('OBSERVING', 'AWAITING_CLARIFICATION', 'AWAITING_EVIDENCE', 'AWAITING_HUMAN_REVIEW', 'EXECUTING', 'RESOLVED', 'ESCALATED')),
    CONSTRAINT ck_cases_risk_route CHECK (risk_route IS NULL OR risk_route IN ('AUTO', 'HUMAN', 'BLOCK')),
    CONSTRAINT ck_cases_order_ref_not_blank CHECK (length(trim(order_ref)) > 0),
    CONSTRAINT ck_cases_user_ref_not_blank CHECK (length(trim(user_ref)) > 0),
    UNIQUE (thread_id)
);

CREATE INDEX ix_cases_order_ref ON cases (order_ref);

CREATE INDEX ix_cases_user_ref ON cases (user_ref);

CREATE TABLE case_events (
    id SERIAL NOT NULL,
    case_ref VARCHAR(128) NOT NULL,
    seq INTEGER NOT NULL,
    kind VARCHAR(16) NOT NULL,
    payload JSON NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT ck_case_events_seq_positive CHECK (seq >= 1),
    CONSTRAINT ck_case_events_kind CHECK (kind IN ('agent_event', 'user_turn')),
    FOREIGN KEY(case_ref) REFERENCES cases (case_ref) ON DELETE CASCADE,
    CONSTRAINT uq_case_events_case_ref_seq UNIQUE (case_ref, seq)
);

CREATE INDEX ix_case_events_case_ref ON case_events (case_ref);

UPDATE alembic_version SET version_num='0002_case_lifecycle' WHERE alembic_version.version_num = '0001_evidence_capability';

COMMIT;
