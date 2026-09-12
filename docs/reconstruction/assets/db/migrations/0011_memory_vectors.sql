BEGIN;

-- Running upgrade 0010_reviewer_handoff -> 0011_memory_vectors

ALTER TABLE operational_memories ADD COLUMN retrieval_summary TEXT;

ALTER TABLE operational_memories ADD COLUMN summary_version VARCHAR(64);

ALTER TABLE operational_memories ADD COLUMN summary_hash VARCHAR(64);

ALTER TABLE operational_memories ADD COLUMN embedding_model VARCHAR(128);

ALTER TABLE operational_memories ADD COLUMN embedding VECTOR(1536);

UPDATE alembic_version SET version_num='0011_memory_vectors' WHERE alembic_version.version_num = '0010_reviewer_handoff';

COMMIT;
