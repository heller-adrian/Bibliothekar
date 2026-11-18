CREATE TABLE legacy_adoption_review_runs (
    job_id TEXT PRIMARY KEY REFERENCES legacy_adoption_jobs(id) ON DELETE CASCADE,
    id TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('active', 'finished', 'cancelling', 'cancelled')),
    error TEXT
) WITHOUT ROWID;

ALTER TABLE legacy_adoption_review_copies ADD COLUMN batch_id TEXT;
ALTER TABLE legacy_adoption_flat_review_copies ADD COLUMN batch_id TEXT;
ALTER TABLE legacy_adoption_flat_review_copies ADD COLUMN owns_files INTEGER NOT NULL DEFAULT 0;

-- Kept independently of the latest queue so a failed family can be resumed.
CREATE TABLE legacy_adoption_review_stages (
    job_id TEXT NOT NULL REFERENCES legacy_adoption_jobs(id) ON DELETE CASCADE,
    family_key TEXT NOT NULL,
    batch_id TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    workspace_identity TEXT NOT NULL,
    parent_name TEXT NOT NULL,
    parent_identity TEXT NOT NULL,
    stage_identity TEXT,
    members_json TEXT NOT NULL DEFAULT '{}',
    PRIMARY KEY (job_id, family_key)
) WITHOUT ROWID;
