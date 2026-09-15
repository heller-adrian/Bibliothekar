PRAGMA foreign_keys = ON;

ALTER TABLE jobs ADD COLUMN source_signature TEXT;
ALTER TABLE jobs ADD COLUMN source_fingerprint TEXT;
ALTER TABLE jobs ADD COLUMN duplicate_of_job_id TEXT;

CREATE INDEX idx_jobs_source_signature
    ON jobs(operation, source_signature, state, created_at);

CREATE INDEX idx_jobs_source_fingerprint
    ON jobs(operation, source_fingerprint, state, created_at);
