ALTER TABLE jobs
ADD COLUMN progress_current INTEGER NOT NULL DEFAULT 0;

ALTER TABLE jobs
ADD COLUMN progress_total INTEGER NOT NULL DEFAULT 0;

ALTER TABLE jobs
ADD COLUMN progress_message TEXT;

ALTER TABLE jobs
ADD COLUMN result_json TEXT;

CREATE INDEX idx_jobs_queue
    ON jobs(state, created_at, id);
