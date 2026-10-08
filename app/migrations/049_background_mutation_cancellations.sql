-- Persistente Hintergrundaufträge für Applied-Mutationsverwerfen (0.44.3).
CREATE TABLE IF NOT EXISTS background_mutation_cancellations (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
    mutation_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued' CHECK(status IN ('queued','running','completed','failed')),
    error_message TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    started_at TEXT,
    completed_at TEXT,
    UNIQUE(job_id, mutation_id)
);
CREATE INDEX IF NOT EXISTS idx_background_mutation_cancel_queue
    ON background_mutation_cancellations(status, created_at);
