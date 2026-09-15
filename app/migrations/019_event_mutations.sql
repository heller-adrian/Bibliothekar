-- 0.17.0: durable event mutation / suspension state.
-- One active mutation is allowed per backup job. The original event graph is
-- retained until the physical reconciliation or manual archive verification
-- has completed, so a pending change can be cancelled safely.
CREATE TABLE event_mutations (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    anchor_event_id TEXT NOT NULL,
    mutation_kind TEXT NOT NULL DEFAULT 'edit'
        CHECK (mutation_kind IN ('edit','delete','cascade')),
    status TEXT NOT NULL
        CHECK (status IN ('pending_reassignment','pending_apply','manual_archive','completed','cancelled','failed')),
    affected_event_ids_json TEXT NOT NULL DEFAULT '[]',
    original_state_json TEXT NOT NULL,
    target_state_json TEXT NOT NULL DEFAULT '{}',
    error_message TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT,
    cancelled_at TEXT
);

CREATE UNIQUE INDEX idx_event_mutations_one_active_job
    ON event_mutations(job_id)
    WHERE status IN ('pending_reassignment','pending_apply','manual_archive');

CREATE INDEX idx_event_mutations_anchor
    ON event_mutations(job_id, anchor_event_id, status);
