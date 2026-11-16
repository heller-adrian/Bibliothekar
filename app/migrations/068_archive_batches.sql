CREATE TABLE archive_batches (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL CHECK(kind IN ('verify','release')),
    verification_batch_id TEXT REFERENCES archive_batches(id),
    status TEXT NOT NULL CHECK(status IN ('queued','running','completed','failed','interrupted')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE UNIQUE INDEX archive_batches_active ON archive_batches ((1))
    WHERE status IN ('queued','running');

CREATE TABLE archive_batch_items (
    batch_id TEXT NOT NULL REFERENCES archive_batches(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    job_id TEXT NOT NULL,
    event_id TEXT NOT NULL,
    event_name TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('queued','running','verified','released','failed','skipped','interrupted')),
    verification_id TEXT,
    release_checks_json TEXT NOT NULL DEFAULT '[]',
    message TEXT,
    PRIMARY KEY (batch_id, position)
) WITHOUT ROWID;
