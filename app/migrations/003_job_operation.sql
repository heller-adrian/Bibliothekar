ALTER TABLE jobs
ADD COLUMN operation TEXT NOT NULL
DEFAULT 'legacy_simulation';

CREATE INDEX idx_jobs_operation
    ON jobs(operation, state, created_at);
