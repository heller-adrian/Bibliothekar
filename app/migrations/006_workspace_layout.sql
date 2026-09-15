PRAGMA foreign_keys = ON;

ALTER TABLE files
ADD COLUMN current_root_kind TEXT NOT NULL
DEFAULT 'job_root'
CHECK (
    current_root_kind IN (
        'job_root',
        'shared_workspace',
        'camera_archive'
    )
);

CREATE INDEX idx_files_current_root_kind
    ON files(job_id, current_root_kind, current_relative_path);

CREATE TABLE workspace_layout_runs (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL CHECK (
        status IN (
            'running',
            'completed',
            'rolled_back',
            'failed'
        )
    ),
    source_root TEXT,
    target_root TEXT NOT NULL,
    file_count INTEGER NOT NULL DEFAULT 0,
    moved_file_count INTEGER NOT NULL DEFAULT 0,
    total_size_bytes INTEGER NOT NULL DEFAULT 0,
    moved_size_bytes INTEGER NOT NULL DEFAULT 0,
    details_json TEXT,
    error_message TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT
);
