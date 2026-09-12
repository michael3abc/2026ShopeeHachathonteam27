BEGIN;

-- Running upgrade 0008_agent_bridge -> 0009_human_reviews

CREATE TABLE human_reviews (
    review_ref VARCHAR(256) NOT NULL,
    handoff_id VARCHAR(256) NOT NULL,
    case_ref VARCHAR(128) NOT NULL,
    payload_hash VARCHAR(64) NOT NULL,
    handoff_payload JSON NOT NULL,
    risk_payload JSON NOT NULL,
    result_payload JSON,
    submitted_at TIMESTAMP WITH TIME ZONE NOT NULL,
    reviewed_at TIMESTAMP WITH TIME ZONE,
    PRIMARY KEY (review_ref),
    CONSTRAINT ck_human_reviews_result_has_timestamp CHECK (result_payload IS NULL OR reviewed_at IS NOT NULL),
    CONSTRAINT uq_human_reviews_handoff_id UNIQUE (handoff_id)
);

CREATE INDEX ix_human_reviews_case_ref ON human_reviews (case_ref);

UPDATE alembic_version SET version_num='0009_human_reviews' WHERE alembic_version.version_num = '0008_agent_bridge';

COMMIT;
