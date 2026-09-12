BEGIN;

-- Running upgrade 0004_operational_memory -> 0005_safety_verification_risk

CREATE TABLE handoff_verifications (
    verification_id VARCHAR(128) NOT NULL,
    handoff_id VARCHAR(256) NOT NULL,
    payload_hash VARCHAR(64) NOT NULL,
    handoff_payload JSON NOT NULL,
    result_payload JSON NOT NULL,
    verification_status VARCHAR(16) NOT NULL,
    verification_version VARCHAR(128) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY (verification_id),
    CONSTRAINT ck_handoff_verifications_status CHECK (verification_status IN ('PASS', 'FAIL', 'UNAVAILABLE')),
    UNIQUE (handoff_id)
);

CREATE INDEX ix_handoff_verifications_payload_hash ON handoff_verifications (payload_hash);

CREATE TABLE risk_evaluations (
    evaluation_id VARCHAR(128) NOT NULL,
    handoff_id VARCHAR(256) NOT NULL,
    payload_hash VARCHAR(64) NOT NULL,
    handoff_payload JSON NOT NULL,
    result_payload JSON NOT NULL,
    risk_route VARCHAR(16) NOT NULL,
    risk_policy_version VARCHAR(128) NOT NULL,
    effective_config JSON NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY (evaluation_id),
    CONSTRAINT ck_risk_evaluations_route CHECK (risk_route IN ('AUTO', 'HUMAN', 'BLOCK')),
    UNIQUE (handoff_id)
);

CREATE INDEX ix_risk_evaluations_payload_hash ON risk_evaluations (payload_hash);

UPDATE alembic_version SET version_num='0005_safety_verification_risk' WHERE alembic_version.version_num = '0004_operational_memory';

COMMIT;
