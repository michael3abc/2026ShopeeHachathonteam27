BEGIN;

-- Running upgrade 0011_memory_vectors -> 0012_human_review_dossier

ALTER TABLE human_reviews ADD COLUMN dossier_payload JSON;

UPDATE alembic_version SET version_num='0012_human_review_dossier' WHERE alembic_version.version_num = '0011_memory_vectors';

COMMIT;
