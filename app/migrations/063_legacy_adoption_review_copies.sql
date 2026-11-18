CREATE TABLE legacy_adoption_review_copies (
    job_id TEXT NOT NULL REFERENCES legacy_adoption_jobs(id) ON DELETE CASCADE,
    family_key TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('copying', 'copied')),
    target_relative TEXT NOT NULL,
    file_count INTEGER NOT NULL,
    size_bytes INTEGER NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (job_id, family_key)
) WITHOUT ROWID;
