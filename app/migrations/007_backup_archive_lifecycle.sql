PRAGMA foreign_keys = ON;

CREATE TABLE backup_lifecycles (
    job_id TEXT PRIMARY KEY,
    status TEXT NOT NULL CHECK (
        status IN (
            'copying',
            'backup_verified',
            'snapshot_created',
            'workspace_moving',
            'workspace_verified',
            'protocol_archived',
            'completed',
            'failed'
        )
    ),
    source_path TEXT,
    temporary_backup_path TEXT,
    workspace_path TEXT,
    protocol_path TEXT,
    snapshot_backend TEXT,
    snapshot_reference TEXT,
    file_count INTEGER NOT NULL DEFAULT 0,
    total_size_bytes INTEGER NOT NULL DEFAULT 0,
    moved_file_count INTEGER NOT NULL DEFAULT 0,
    temporary_backup_removed INTEGER NOT NULL DEFAULT 0 CHECK (
        temporary_backup_removed IN (0, 1)
    ),
    details_json TEXT,
    error_message TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT,
    FOREIGN KEY(job_id)
        REFERENCES jobs(id)
        ON DELETE CASCADE
);

CREATE INDEX idx_backup_lifecycles_status
    ON backup_lifecycles(status, updated_at);

CREATE TABLE event_archive_verifications (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
    event_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK (
        status IN (
            'running',
            'verified',
            'failed'
        )
    ),
    archive_root TEXT NOT NULL,
    file_count INTEGER NOT NULL DEFAULT 0,
    verified_file_count INTEGER NOT NULL DEFAULT 0,
    total_size_bytes INTEGER NOT NULL DEFAULT 0,
    verified_size_bytes INTEGER NOT NULL DEFAULT 0,
    missing_file_count INTEGER NOT NULL DEFAULT 0,
    mismatched_file_count INTEGER NOT NULL DEFAULT 0,
    details_json TEXT,
    error_message TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT,
    FOREIGN KEY(job_id)
        REFERENCES jobs(id)
        ON DELETE CASCADE,
    FOREIGN KEY(event_id)
        REFERENCES events(id)
        ON DELETE CASCADE
);

CREATE INDEX idx_event_archive_verifications_event
    ON event_archive_verifications(event_id, created_at);

CREATE TABLE event_archive_verification_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    verification_id TEXT NOT NULL,
    file_id INTEGER NOT NULL,
    expected_relative_path TEXT NOT NULL,
    expected_size_bytes INTEGER NOT NULL,
    expected_sha256 TEXT NOT NULL,
    status TEXT NOT NULL CHECK (
        status IN (
            'verified',
            'missing',
            'size_mismatch',
            'sha256_mismatch',
            'unsafe_path'
        )
    ),
    actual_size_bytes INTEGER,
    actual_sha256 TEXT,
    error_message TEXT,
    FOREIGN KEY(verification_id)
        REFERENCES event_archive_verifications(id)
        ON DELETE CASCADE,
    FOREIGN KEY(file_id)
        REFERENCES files(id)
        ON DELETE CASCADE,
    UNIQUE(verification_id, file_id)
);
