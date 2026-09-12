BEGIN;

-- Running upgrade 0012_human_review_dossier -> 0013_activity_tracing

CREATE TABLE case_activities (
    event_id VARCHAR(200) NOT NULL,
    case_ref VARCHAR(128) NOT NULL,
    seq INTEGER NOT NULL,
    payload JSON NOT NULL,
    PRIMARY KEY (event_id),
    UNIQUE (case_ref, seq),
    FOREIGN KEY(case_ref) REFERENCES cases (case_ref)
);

CREATE INDEX ix_case_activities_case_ref ON case_activities (case_ref);

CREATE TABLE activity_narration_outbox (
    source_event_id VARCHAR(200) NOT NULL,
    payload JSON NOT NULL,
    dispatched BOOLEAN NOT NULL,
    result_event_id VARCHAR(200),
    PRIMARY KEY (source_event_id),
    FOREIGN KEY(source_event_id) REFERENCES case_activities (event_id)
);

CREATE INDEX ix_activity_narration_outbox_dispatched ON activity_narration_outbox (dispatched);

UPDATE alembic_version SET version_num='0013_activity_tracing' WHERE alembic_version.version_num = '0012_human_review_dossier';

COMMIT;
