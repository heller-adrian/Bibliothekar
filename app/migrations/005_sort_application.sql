PRAGMA foreign_keys = ON;

CREATE TABLE sort_runs (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
    event_id TEXT NOT NULL,
    plan_token TEXT NOT NULL,
    status TEXT NOT NULL CHECK (
        status IN (
            'queued',
            'verifying',
            'moving',
            'finalizing',
            'applied',
            'rolling_back',
            'rolled_back',
            'failed',
            'interrupted'
        )
    ),
    phase TEXT NOT NULL,
    source_root TEXT NOT NULL,
    target_root TEXT NOT NULL,
    file_count INTEGER NOT NULL DEFAULT 0,
    verified_file_count INTEGER NOT NULL DEFAULT 0,
    move_count INTEGER NOT NULL DEFAULT 0,
    moved_file_count INTEGER NOT NULL DEFAULT 0,
    directory_count INTEGER NOT NULL DEFAULT 0,
    created_directory_count INTEGER NOT NULL DEFAULT 0,
    total_size_bytes INTEGER NOT NULL DEFAULT 0,
    verified_bytes INTEGER NOT NULL DEFAULT 0,
    moved_bytes INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    details_json TEXT,
    created_at TEXT NOT NULL,
    started_at TEXT,
    updated_at TEXT NOT NULL,
    completed_at TEXT,
    FOREIGN KEY(job_id)
        REFERENCES jobs(id)
        ON DELETE CASCADE,
    FOREIGN KEY(event_id)
        REFERENCES events(id)
        ON DELETE CASCADE
);

CREATE TABLE sort_operations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sort_run_id TEXT NOT NULL,
    sequence_number INTEGER NOT NULL,
    file_id INTEGER NOT NULL,
    source_relative_path TEXT NOT NULL,
    destination_relative_path TEXT NOT NULL,
    expected_size_bytes INTEGER NOT NULL,
    expected_sha256 TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'planned' CHECK (
        status IN (
            'planned',
            'verified',
            'moved',
            'destination_verified',
            'already_at_target',
            'rolled_back',
            'failed'
        )
    ),
    error_message TEXT,
    verified_at TEXT,
    moved_at TEXT,
    destination_verified_at TEXT,
    rolled_back_at TEXT,
    FOREIGN KEY(sort_run_id)
        REFERENCES sort_runs(id)
        ON DELETE CASCADE,
    FOREIGN KEY(file_id)
        REFERENCES files(id)
        ON DELETE CASCADE,
    UNIQUE(sort_run_id, sequence_number),
    UNIQUE(sort_run_id, file_id)
);

CREATE UNIQUE INDEX idx_sort_runs_active_event
    ON sort_runs(event_id)
    WHERE status IN (
        'queued',
        'verifying',
        'moving',
        'finalizing',
        'rolling_back',
        'interrupted'
    );

CREATE INDEX idx_sort_runs_job
    ON sort_runs(job_id, created_at);

CREATE INDEX idx_sort_runs_event
    ON sort_runs(event_id, created_at);

CREATE INDEX idx_sort_operations_run
    ON sort_operations(sort_run_id, sequence_number);
