BEGIN;

-- Running upgrade 0003_policy_rag -> 0004_operational_memory

CREATE TABLE operational_memories (
    memory_id VARCHAR(128) NOT NULL,
    submission_ref VARCHAR(256) NOT NULL,
    candidate_payload_hash VARCHAR(64) NOT NULL,
    trigger_conditions JSON NOT NULL,
    recommended_behavior TEXT NOT NULL,
    rationale TEXT NOT NULL,
    source_case_refs JSON NOT NULL,
    source_revision_event_refs JSON NOT NULL,
    policy_version VARCHAR(256) NOT NULL,
    claim_registry_version VARCHAR(128) NOT NULL,
    scope_market VARCHAR(64) NOT NULL,
    scope_reason_codes VARCHAR[] NOT NULL,
    scope_claim_ids VARCHAR[] NOT NULL,
    scope_categories VARCHAR[] NOT NULL,
    confidence FLOAT NOT NULL,
    status VARCHAR(16) NOT NULL,
    submitted_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    approved_at TIMESTAMP WITH TIME ZONE,
    retired_at TIMESTAMP WITH TIME ZONE,
    PRIMARY KEY (memory_id),
    CONSTRAINT ck_operational_memories_status CHECK (status IN ('CANDIDATE', 'APPROVED', 'RETIRED')),
    CONSTRAINT ck_operational_memories_confidence CHECK (confidence >= 0 AND confidence <= 1),
    CONSTRAINT ck_operational_memories_submission_ref_not_blank CHECK (length(trim(submission_ref)) > 0),
    CONSTRAINT ck_operational_memories_behavior_not_blank CHECK (length(trim(recommended_behavior)) > 0),
    CONSTRAINT ck_operational_memories_rationale_not_blank CHECK (length(trim(rationale)) > 0),
    CONSTRAINT ck_operational_memories_policy_version_not_blank CHECK (length(trim(policy_version)) > 0),
    CONSTRAINT ck_operational_memories_registry_version_not_blank CHECK (length(trim(claim_registry_version)) > 0),
    CONSTRAINT ck_operational_memories_scope_market_not_blank CHECK (length(trim(scope_market)) > 0),
    CONSTRAINT ck_operational_memories_lifecycle_timestamps CHECK ((status = 'CANDIDATE' AND approved_at IS NULL AND retired_at IS NULL) OR (status = 'APPROVED' AND approved_at IS NOT NULL AND retired_at IS NULL) OR (status = 'RETIRED' AND approved_at IS NOT NULL AND retired_at IS NOT NULL)),
    CONSTRAINT ck_operational_memories_approval_after_submission CHECK (approved_at IS NULL OR approved_at >= submitted_at),
    CONSTRAINT ck_operational_memories_retirement_after_approval CHECK (retired_at IS NULL OR retired_at >= approved_at),
    UNIQUE (submission_ref)
);

CREATE INDEX ix_operational_memories_approved_lookup ON operational_memories (status, scope_market, policy_version, confidence);

CREATE TABLE operational_memory_events (
    event_id VARCHAR(128) NOT NULL,
    memory_id VARCHAR(128) NOT NULL,
    event_type VARCHAR(16) NOT NULL,
    from_status VARCHAR(16) NOT NULL,
    to_status VARCHAR(16) NOT NULL,
    occurred_at TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY (event_id),
    CONSTRAINT ck_operational_memory_events_type CHECK (event_type IN ('APPROVED', 'RETIRED')),
    CONSTRAINT ck_operational_memory_events_transition CHECK ((event_type = 'APPROVED' AND from_status = 'CANDIDATE' AND to_status = 'APPROVED') OR (event_type = 'RETIRED' AND from_status = 'APPROVED' AND to_status = 'RETIRED')),
    FOREIGN KEY(memory_id) REFERENCES operational_memories (memory_id)
);

CREATE INDEX ix_operational_memory_events_memory_id ON operational_memory_events (memory_id);

UPDATE alembic_version SET version_num='0004_operational_memory' WHERE alembic_version.version_num = '0003_policy_rag';

COMMIT;
