BEGIN;

-- Running upgrade 0009_human_reviews -> 0010_reviewer_handoff

ALTER TABLE human_reviews ALTER COLUMN risk_payload DROP NOT NULL;

ALTER TABLE human_reviews RENAME risk_payload TO legacy_risk_payload;

ALTER TABLE human_reviews ADD COLUMN review_payload JSON;

UPDATE alembic_version SET version_num='0010_reviewer_handoff' WHERE alembic_version.version_num = '0009_human_reviews';

COMMIT;
