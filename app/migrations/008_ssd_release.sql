PRAGMA foreign_keys = ON;

CREATE TABLE event_ssd_releases (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
    event_id TEXT NOT NULL,
    verification_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK (
        status IN (
            'verifying',
            'deleting',
            'finalizing',
            'completed',
            'failed',
            'interrupted'
        )
    ),
    workspace_root TEXT NOT NULL,
    archive_root TEXT NOT NULL,
    file_count INTEGER NOT NULL DEFAULT 0,
    verified_source_count INTEGER NOT NULL DEFAULT 0,
    verified_archive_count INTEGER NOT NULL DEFAULT 0,
    deleted_file_count INTEGER NOT NULL DEFAULT 0,
    total_size_bytes INTEGER NOT NULL DEFAULT 0,
    deleted_size_bytes INTEGER NOT NULL DEFAULT 0,
    removed_directory_count INTEGER NOT NULL DEFAULT 0,
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
        ON DELETE CASCADE,
    FOREIGN KEY(verification_id)
        REFERENCES event_archive_verifications(id)
        ON DELETE RESTRICT
);

CREATE TABLE event_ssd_release_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    release_id TEXT NOT NULL,
    file_id INTEGER NOT NULL,
    source_relative_path TEXT NOT NULL,
    archive_relative_path TEXT NOT NULL,
    expected_size_bytes INTEGER NOT NULL,
    expected_sha256 TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'planned' CHECK (
        status IN (
            'planned',
            'source_verified',
            'archive_verified',
            'deleted',
            'already_released',
            'failed'
        )
    ),
    actual_source_size_bytes INTEGER,
    actual_source_sha256 TEXT,
    actual_archive_size_bytes INTEGER,
    actual_archive_sha256 TEXT,
    error_message TEXT,
    verified_at TEXT,
    deleted_at TEXT,
    FOREIGN KEY(release_id)
        REFERENCES event_ssd_releases(id)
        ON DELETE CASCADE,
    FOREIGN KEY(file_id)
        REFERENCES files(id)
        ON DELETE CASCADE,
    UNIQUE(release_id, file_id)
);

CREATE INDEX idx_event_ssd_releases_event
    ON event_ssd_releases(event_id, created_at);

CREATE INDEX idx_event_ssd_releases_status
    ON event_ssd_releases(status, updated_at);

CREATE INDEX idx_event_ssd_release_files_run
    ON event_ssd_release_files(release_id, id);
