BEGIN;

-- Running downgrade 0012_human_review_dossier -> 0011_memory_vectors

DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM human_reviews WHERE dossier_payload IS NOT NULL
                       AND CAST(dossier_payload AS TEXT) <> 'null') THEN
                RAISE EXCEPTION 'Cannot discard human adjudication audit history';
            END IF;
        END $$;;

ALTER TABLE human_reviews DROP COLUMN dossier_payload;

UPDATE alembic_version SET version_num='0011_memory_vectors' WHERE alembic_version.version_num = '0012_human_review_dossier';

COMMIT;
