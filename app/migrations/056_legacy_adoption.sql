CREATE TABLE legacy_adoption_jobs (
    id TEXT PRIMARY KEY,
    library_id TEXT NOT NULL REFERENCES library_identity(library_id),
    source_root TEXT NOT NULL,
    source_device INTEGER NOT NULL,
    source_inode INTEGER NOT NULL,
    archive_root TEXT NOT NULL,
    archive_device INTEGER NOT NULL,
    archive_inode INTEGER NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('ready', 'scanning', 'inventoried', 'discarded')),
    scan_generation INTEGER NOT NULL DEFAULT 0,
    scan_error TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE legacy_adoption_inventory (
    job_id TEXT NOT NULL REFERENCES legacy_adoption_jobs(id) ON DELETE CASCADE,
    relative_path TEXT NOT NULL,
    family_key TEXT,
    size_bytes INTEGER,
    identity TEXT,
    sha256 TEXT,
    metadata_json TEXT,
    error TEXT,
    seen_generation INTEGER NOT NULL,
    PRIMARY KEY (job_id, relative_path)
) WITHOUT ROWID;

CREATE INDEX legacy_adoption_inventory_family
    ON legacy_adoption_inventory(job_id, family_key, relative_path);
