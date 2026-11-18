CREATE TABLE legacy_adoption_review_batch (
    job_id TEXT NOT NULL REFERENCES legacy_adoption_jobs(id) ON DELETE CASCADE,
    family_key TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'pending' CHECK (state IN ('pending', 'copied', 'failed')),
    error TEXT,
    PRIMARY KEY (job_id, family_key)
) WITHOUT ROWID;

CREATE INDEX legacy_adoption_review_batch_pending
    ON legacy_adoption_review_batch (job_id, state, family_key);
