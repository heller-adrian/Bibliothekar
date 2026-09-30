-- 034: Ein logisches Ereignis kann Dateien/Familien aus mehreren Sicherungen besitzen.
--
-- events.job_id bleibt der technische Anchor des Workflows. event_source_jobs
-- dokumentiert dagegen ausschließlich die tatsächliche Herkunft des Inhalts.
CREATE TABLE event_source_jobs (
    event_id TEXT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    PRIMARY KEY(event_id, job_id)
);

CREATE INDEX idx_event_source_jobs_job
    ON event_source_jobs(job_id, event_id);

-- Bestehende Ereignisse stammen mindestens aus ihrer bisherigen Anchor-Sicherung.
-- Linked Legacy-Nachträge bleiben zunächst eigenständige Ereignisse; eine physische
-- Zusammenführung erfolgt ausdrücklich nicht in dieser Foundation-Migration.
INSERT OR IGNORE INTO event_source_jobs(event_id, job_id, created_at)
SELECT id, job_id, COALESCE(created_at, datetime('now'))
FROM events
WHERE parent_event_id IS NULL;
