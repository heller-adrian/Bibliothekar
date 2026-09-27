-- 028: durable, event-independent marker for families released by an
-- explicitly confirmed Applied edit/delete.  It is informational only:
-- no reassignment or resort task is created from this table.
CREATE TABLE released_free_families (
    job_id TEXT NOT NULL,
    family_id INTEGER NOT NULL,
    released_start_datetime TEXT,
    released_end_datetime TEXT,
    created_at TEXT NOT NULL,
    PRIMARY KEY(job_id, family_id),
    FOREIGN KEY(job_id) REFERENCES jobs(id) ON DELETE CASCADE,
    FOREIGN KEY(family_id) REFERENCES file_families(id) ON DELETE CASCADE
);

CREATE INDEX idx_released_free_families_job
    ON released_free_families(job_id, family_id);
