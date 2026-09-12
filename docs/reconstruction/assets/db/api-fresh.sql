-- Generated baseline DDL; fresh database only.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE agent_command_outbox (
	command_id VARCHAR(128) NOT NULL,
	payload JSON NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	published_at TIMESTAMP WITH TIME ZONE,
	claimed_by VARCHAR(256),
	claimed_until TIMESTAMP WITH TIME ZONE,
	lease_token VARCHAR(32),
	attempt_count INTEGER DEFAULT '0' NOT NULL,
	last_error TEXT,
	PRIMARY KEY (command_id),
	CONSTRAINT ck_agent_command_outbox_attempt_count CHECK (attempt_count >= 0)
);

CREATE TABLE cases (
	case_ref VARCHAR(128) NOT NULL,
	thread_id VARCHAR(128) NOT NULL,
	order_ref VARCHAR(128) NOT NULL,
	user_ref VARCHAR(128) NOT NULL,
	status VARCHAR(32) NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (case_ref),
	CONSTRAINT ck_cases_status CHECK (status IN ('OBSERVING', 'AWAITING_CLARIFICATION', 'AWAITING_EVIDENCE', 'AWAITING_HUMAN_REVIEW', 'EXECUTING', 'RESOLVED', 'ESCALATED')),
	CONSTRAINT ck_cases_order_ref_not_blank CHECK (length(trim(order_ref)) > 0),
	CONSTRAINT ck_cases_user_ref_not_blank CHECK (length(trim(user_ref)) > 0),
	UNIQUE (thread_id)
);

CREATE INDEX ix_cases_order_ref ON cases (order_ref);

CREATE INDEX ix_cases_user_ref ON cases (user_ref);

CREATE TABLE evidence_items (
	evidence_id VARCHAR(128) NOT NULL,
	type VARCHAR(16) NOT NULL,
	source VARCHAR(32) NOT NULL,
	subject VARCHAR(128) NOT NULL,
	artifact_ref VARCHAR(512) NOT NULL,
	extracted_summary TEXT NOT NULL,
	collected_at TIMESTAMP WITH TIME ZONE NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
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

CREATE TABLE human_reviews (
	review_ref VARCHAR(256) NOT NULL,
	handoff_id VARCHAR(256) NOT NULL,
	case_ref VARCHAR(128) NOT NULL,
	payload_hash VARCHAR(64) NOT NULL,
	handoff_payload JSON NOT NULL,
	review_payload JSON,
	dossier_payload JSON,
	result_payload JSON,
	submitted_at TIMESTAMP WITH TIME ZONE NOT NULL,
	reviewed_at TIMESTAMP WITH TIME ZONE,
	PRIMARY KEY (review_ref),
	CONSTRAINT ck_human_reviews_result_has_timestamp CHECK (result_payload IS NULL OR reviewed_at IS NOT NULL),
	UNIQUE (handoff_id)
);

CREATE INDEX ix_human_reviews_case_ref ON human_reviews (case_ref);

CREATE TABLE operational_memories (
	memory_id VARCHAR(128) NOT NULL,
	submission_ref VARCHAR(256) NOT NULL,
	candidate_payload_hash VARCHAR(64) NOT NULL,
	retrieval_summary TEXT,
	summary_version VARCHAR(64),
	summary_hash VARCHAR(64),
	embedding_model VARCHAR(128),
	embedding VECTOR(1536),
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
	submitted_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
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

CREATE TABLE policy_documents (
	document_id VARCHAR(128) NOT NULL,
	policy_family VARCHAR(128) NOT NULL,
	version VARCHAR(128) NOT NULL,
	source_ref VARCHAR(512) NOT NULL,
	checksum VARCHAR(64) NOT NULL,
	is_active BOOLEAN NOT NULL,
	ingested_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (document_id),
	CONSTRAINT uq_policy_documents_family_version UNIQUE (policy_family, version),
	CONSTRAINT uq_policy_documents_source_version UNIQUE (source_ref, version)
);

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

CREATE TABLE refund_executions (
	execution_ref VARCHAR(128) NOT NULL,
	handoff_id VARCHAR(256) NOT NULL,
	case_ref VARCHAR(128) NOT NULL,
	payload_hash VARCHAR(64) NOT NULL,
	request_payload JSON NOT NULL,
	order_ref VARCHAR(128),
	application_result_payload JSON,
	state VARCHAR(16) NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	application_started_at TIMESTAMP WITH TIME ZONE,
	completed_at TIMESTAMP WITH TIME ZONE,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (execution_ref),
	CONSTRAINT ck_refund_executions_state CHECK (state IN ('IN_PROGRESS', 'SUCCEEDED', 'REJECTED')),
	CONSTRAINT ck_refund_executions_terminal_result CHECK ((state = 'IN_PROGRESS' AND application_result_payload IS NULL AND completed_at IS NULL) OR (state IN ('SUCCEEDED', 'REJECTED') AND application_result_payload IS NOT NULL AND completed_at IS NOT NULL)),
	UNIQUE (handoff_id)
);

CREATE TABLE rejected_agent_events (
	source_message_id VARCHAR(128) NOT NULL,
	event_id VARCHAR(256),
	case_ref VARCHAR(128),
	raw_body TEXT NOT NULL,
	error_code VARCHAR(64) NOT NULL,
	error_message TEXT NOT NULL,
	rejected_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (source_message_id)
);

CREATE INDEX ix_rejected_agent_events_case_ref ON rejected_agent_events (case_ref);

CREATE INDEX ix_rejected_agent_events_event_id ON rejected_agent_events (event_id);

CREATE TABLE agent_event_projection_cursors (
	command_id VARCHAR(128) NOT NULL,
	case_ref VARCHAR(128) NOT NULL,
	last_event_index INTEGER NOT NULL,
	terminated_at TIMESTAMP WITH TIME ZONE,
	termination_event_id VARCHAR(256),
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (command_id),
	CONSTRAINT ck_agent_event_projection_cursor_index CHECK (last_event_index >= 0),
	FOREIGN KEY(case_ref) REFERENCES cases (case_ref) ON DELETE CASCADE
);

CREATE INDEX ix_agent_event_projection_cursors_case_ref ON agent_event_projection_cursors (case_ref);

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

CREATE TABLE case_events (
	id SERIAL NOT NULL,
	case_ref VARCHAR(128) NOT NULL,
	seq INTEGER NOT NULL,
	kind VARCHAR(16) NOT NULL,
	payload JSON NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_case_events_case_ref_seq UNIQUE (case_ref, seq),
	CONSTRAINT ck_case_events_seq_positive CHECK (seq >= 1),
	CONSTRAINT ck_case_events_kind CHECK (kind IN ('agent_event', 'user_turn')),
	FOREIGN KEY(case_ref) REFERENCES cases (case_ref) ON DELETE CASCADE
);

CREATE INDEX ix_case_events_case_ref ON case_events (case_ref);

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

CREATE TABLE processed_agent_events (
	event_id VARCHAR(256) NOT NULL,
	case_ref VARCHAR(128) NOT NULL,
	command_id VARCHAR(128) NOT NULL,
	event_index INTEGER NOT NULL,
	payload_hash VARCHAR(64) NOT NULL,
	processed_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (event_id),
	FOREIGN KEY(case_ref) REFERENCES cases (case_ref) ON DELETE CASCADE
);

CREATE INDEX ix_processed_agent_events_case_ref ON processed_agent_events (case_ref);

CREATE TABLE refund_execution_items (
	execution_ref VARCHAR(128) NOT NULL,
	line_item_ref VARCHAR(128) NOT NULL,
	order_ref VARCHAR(128) NOT NULL,
	applied_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (execution_ref, line_item_ref),
	CONSTRAINT uq_refund_execution_items_order_line_item UNIQUE (order_ref, line_item_ref),
	FOREIGN KEY(execution_ref) REFERENCES refund_executions (execution_ref)
);

CREATE TABLE refund_item_reservations (
	order_ref VARCHAR(128) NOT NULL,
	line_item_ref VARCHAR(128) NOT NULL,
	execution_ref VARCHAR(128) NOT NULL,
	reserved_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (order_ref, line_item_ref),
	FOREIGN KEY(execution_ref) REFERENCES refund_executions (execution_ref)
);

CREATE TABLE activity_narration_outbox (
	source_event_id VARCHAR(200) NOT NULL,
	payload JSON NOT NULL,
	dispatched BOOLEAN NOT NULL,
	result_event_id VARCHAR(200),
	PRIMARY KEY (source_event_id),
	FOREIGN KEY(source_event_id) REFERENCES case_activities (event_id)
);

CREATE INDEX ix_activity_narration_outbox_dispatched ON activity_narration_outbox (dispatched);
