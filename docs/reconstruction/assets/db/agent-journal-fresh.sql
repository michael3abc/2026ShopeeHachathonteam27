CREATE TABLE IF NOT EXISTS agent_command_journal (
    command_id TEXT PRIMARY KEY,
    state TEXT NOT NULL CHECK (
        state IN ('RUNNING', 'COMPLETED', 'FAILED')
    ),
    claimed_by TEXT,
    claimed_until TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL
);
