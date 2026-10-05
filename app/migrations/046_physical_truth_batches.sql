-- 046: 0.41.1 – physische Zentralbestandswahrheit, externe Änderungen
--      und persistente serverseitige Mehrfach-Sortierläufe.

CREATE TABLE central_missing_file_observations (
    file_id INTEGER PRIMARY KEY REFERENCES files(id) ON DELETE CASCADE,
    job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    consecutive_misses INTEGER NOT NULL DEFAULT 1,
    first_missing_at TEXT NOT NULL,
    last_missing_at TEXT NOT NULL
);

CREATE INDEX idx_central_missing_file_observations
ON central_missing_file_observations(job_id, consecutive_misses);

CREATE TABLE external_change_notices (
    id TEXT PRIMARY KEY,
    notice_key TEXT NOT NULL UNIQUE,
    kind TEXT NOT NULL,
    root_kind TEXT NOT NULL,
    job_id TEXT,
    event_id TEXT,
    file_id INTEGER,
    relative_path TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL,
    detail TEXT NOT NULL,
    repairable INTEGER NOT NULL DEFAULT 0 CHECK (repairable IN (0,1)),
    details_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'open'
        CHECK (status IN ('open','repaired','dismissed','resolved')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE INDEX idx_external_change_notices_open
ON external_change_notices(status, created_at);

CREATE TABLE operation_batches (
    id TEXT PRIMARY KEY,
    batch_kind TEXT NOT NULL CHECK (batch_kind IN ('apply_events')),
    status TEXT NOT NULL
        CHECK (status IN ('queued','running','applied','failed','interrupted')),
    item_count INTEGER NOT NULL DEFAULT 0,
    completed_item_count INTEGER NOT NULL DEFAULT 0,
    current_index INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    details_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    started_at TEXT,
    updated_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE TABLE operation_batch_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id TEXT NOT NULL REFERENCES operation_batches(id) ON DELETE CASCADE,
    sequence_number INTEGER NOT NULL,
    job_id TEXT NOT NULL,
    event_id TEXT NOT NULL,
    plan_token TEXT NOT NULL,
    sort_run_id TEXT,
    sort_run_job_id TEXT,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending','running','applied','failed')),
    error_message TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT,
    UNIQUE(batch_id, sequence_number),
    UNIQUE(batch_id, event_id)
);

CREATE INDEX idx_operation_batches_active
ON operation_batches(status, created_at);

CREATE INDEX idx_operation_batch_items_run
ON operation_batch_items(sort_run_id);
