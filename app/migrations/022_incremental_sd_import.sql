PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS imported_source_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_device_id TEXT NOT NULL,
    relative_path TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    modified_at_ns INTEGER,
    sha256 TEXT NOT NULL,
    imported_job_id TEXT NOT NULL,
    first_imported_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    UNIQUE(source_device_id, relative_path, sha256)
);

CREATE INDEX IF NOT EXISTS idx_imported_source_files_fast
    ON imported_source_files(source_device_id, relative_path, size_bytes, modified_at_ns);

CREATE INDEX IF NOT EXISTS idx_imported_source_files_hash
    ON imported_source_files(source_device_id, sha256, size_bytes);
