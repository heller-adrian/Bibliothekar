-- 051: durable SSD-release queue and explicit archive recovery incidents.
CREATE TABLE IF NOT EXISTS ssd_release_tasks (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
    event_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('queued','running','completed','failed')),
    error_message TEXT,
    result_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    FOREIGN KEY(job_id) REFERENCES jobs(id) ON DELETE CASCADE,
    FOREIGN KEY(event_id) REFERENCES events(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_ssd_release_tasks_status ON ssd_release_tasks(status,created_at);
CREATE UNIQUE INDEX IF NOT EXISTS idx_ssd_release_tasks_active
    ON ssd_release_tasks(event_id) WHERE status IN ('queued','running');

CREATE TABLE IF NOT EXISTS archive_recovery_incidents (
    id TEXT PRIMARY KEY,
    change_request_id TEXT NOT NULL UNIQUE
        REFERENCES event_change_requests(id) ON DELETE CASCADE,
    event_id TEXT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    job_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('manual_review','resolved')),
    reason TEXT NOT NULL,
    snapshot_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    resolved_at TEXT,
    FOREIGN KEY(job_id) REFERENCES jobs(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_archive_recovery_incidents_event
    ON archive_recovery_incidents(event_id,status);
