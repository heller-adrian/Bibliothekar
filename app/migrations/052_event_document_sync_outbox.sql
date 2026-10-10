-- 052: BA-01 durable document synchronization, committed together with event edits.
-- The document is a recoverable projection; an unresolved task is never silently lost.
CREATE TABLE IF NOT EXISTS event_document_sync_tasks (
    event_id TEXT PRIMARY KEY REFERENCES events(id) ON DELETE CASCADE,
    job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    revision INTEGER NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('pending', 'blocked', 'completed')),
    error_message TEXT NOT NULL DEFAULT '',
    attempts INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_event_document_sync_status
    ON event_document_sync_tasks(status, updated_at);
