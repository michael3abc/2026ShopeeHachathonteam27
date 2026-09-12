BEGIN;

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL,
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> 0001_evidence_capability

CREATE TABLE evidence_items (
    evidence_id VARCHAR(128) NOT NULL,
    type VARCHAR(16) NOT NULL,
    source VARCHAR(32) NOT NULL,
    subject VARCHAR(128) NOT NULL,
    artifact_ref VARCHAR(512) NOT NULL,
    extracted_summary TEXT NOT NULL,
    collected_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    content_hash VARCHAR(64) NOT NULL,
    PRIMARY KEY (evidence_id),
    CONSTRAINT ck_evidence_items_type CHECK (type IN ('IMAGE', 'VIDEO', 'TEXT', 'DOCUMENT')),
    CONSTRAINT ck_evidence_items_source CHECK (source IN ('USER', 'ORDER_TOOL', 'LOGISTICS_TOOL', 'SYSTEM')),
    CONSTRAINT ck_evidence_items_subject_not_blank CHECK (length(trim(subject)) > 0),
    CONSTRAINT ck_evidence_items_artifact_ref_not_blank CHECK (length(trim(artifact_ref)) > 0),
    CONSTRAINT ck_evidence_items_summary_not_blank CHECK (length(trim(extracted_summary)) > 0),
    UNIQUE (artifact_ref),
    UNIQUE (content_hash)
);

INSERT INTO alembic_version (version_num) VALUES ('0001_evidence_capability') RETURNING alembic_version.version_num;

COMMIT;
