BEGIN;

-- Running upgrade 0002_case_lifecycle -> 0003_policy_rag

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE policy_documents (
    document_id VARCHAR(128) NOT NULL,
    policy_family VARCHAR(128) NOT NULL,
    version VARCHAR(128) NOT NULL,
    source_ref VARCHAR(512) NOT NULL,
    checksum VARCHAR(64) NOT NULL,
    is_active BOOLEAN NOT NULL,
    ingested_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    PRIMARY KEY (document_id),
    CONSTRAINT uq_policy_documents_family_version UNIQUE (policy_family, version),
    CONSTRAINT uq_policy_documents_source_version UNIQUE (source_ref, version)
);

CREATE TABLE policy_clauses (
    clause_id VARCHAR(256) NOT NULL,
    document_id VARCHAR(128) NOT NULL,
    policy_version VARCHAR(256) NOT NULL,
    effective_from TIMESTAMP WITH TIME ZONE NOT NULL,
    effective_to TIMESTAMP WITH TIME ZONE,
    markets VARCHAR[] NOT NULL,
    reason_codes VARCHAR[] NOT NULL,
    categories VARCHAR[] NOT NULL,
    required_claim_ids VARCHAR[] NOT NULL,
    allowed_actions VARCHAR[] NOT NULL,
    return_policy VARCHAR(32) NOT NULL,
    clause_text TEXT NOT NULL,
    embedding_model VARCHAR(128) NOT NULL,
    embedding VECTOR(1536) NOT NULL,
    PRIMARY KEY (clause_id),
    FOREIGN KEY(document_id) REFERENCES policy_documents (document_id)
);

CREATE INDEX ix_policy_clauses_document_id ON policy_clauses (document_id);

CREATE TABLE policy_retrievals (
    retrieval_id VARCHAR(128) NOT NULL,
    request_hash VARCHAR(64) NOT NULL,
    bundle_version VARCHAR(128) NOT NULL,
    retrieval_status VARCHAR(32) NOT NULL,
    bundle_payload JSON NOT NULL,
    retrieved_at TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY (retrieval_id),
    CONSTRAINT uq_policy_retrievals_bundle_version UNIQUE (bundle_version)
);

CREATE INDEX ix_policy_retrievals_request_hash ON policy_retrievals (request_hash);

CREATE INDEX ix_policy_clauses_markets_gin ON policy_clauses USING gin (markets);

CREATE INDEX ix_policy_clauses_reason_codes_gin ON policy_clauses USING gin (reason_codes);

CREATE INDEX ix_policy_clauses_categories_gin ON policy_clauses USING gin (categories);

CREATE INDEX ix_policy_clauses_embedding_hnsw ON policy_clauses USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);

UPDATE alembic_version SET version_num='0003_policy_rag' WHERE alembic_version.version_num = '0002_case_lifecycle';

COMMIT;
