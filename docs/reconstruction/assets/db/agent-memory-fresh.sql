-- Generated baseline DDL; fresh database only.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE memory_job_results (
	job_id VARCHAR(256) NOT NULL,
	input_hash VARCHAR(64) NOT NULL,
	prompt_version VARCHAR(256) NOT NULL,
	result JSON,
	terminal_event JSON,
	PRIMARY KEY (job_id)
);
