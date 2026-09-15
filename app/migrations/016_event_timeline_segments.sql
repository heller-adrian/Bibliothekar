-- 016: Zeitachsenmodell fuer "Ohne Ereignis" und globale offene Aufgaben.
--
-- Normale Ereignisse bleiben kontinuierliche Zeitraeume. "Ohne Ereignis"
-- verwendet ab 0.16.5 dagegen ausschliesslich einzelne Zeitsegmente. Die
-- historischen start_datetime/end_datetime-Spalten der events-Tabelle bleiben
-- aus Rueckwaertskompatibilitaet bestehen, sind fuer no_event aber nicht mehr
-- fachlich fuehrend.

ALTER TABLE events ADD COLUMN timeline_model TEXT NOT NULL DEFAULT 'continuous'
    CHECK (timeline_model IN ('continuous', 'segments'));

UPDATE events SET timeline_model = 'segments' WHERE event_kind = 'no_event';

CREATE TABLE event_time_segments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    day_key TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    start_datetime TEXT NOT NULL,
    end_datetime TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'user'
        CHECK (source IN ('user', 'migration', 'reassignment', 'cascade')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    CHECK (length(day_key) = 10),
    CHECK (length(start_time) = 5),
    CHECK (length(end_time) = 5),
    CHECK (start_datetime <= end_datetime),
    UNIQUE(event_id, start_datetime, end_datetime)
);

CREATE INDEX idx_event_time_segments_job_day
    ON event_time_segments(job_id, day_key, start_datetime, end_datetime);
CREATE INDEX idx_event_time_segments_event
    ON event_time_segments(event_id, start_datetime, end_datetime);

-- Bestehende "Ohne Ereignis"-Sammlungen werden aus den tatsaechlich
-- zugeordneten Aufnahmezeiten rekonstruiert. Pro belegtem Tag entsteht ein
-- Segment vom fruehesten bis zum spaetesten zugeordneten Aufnahmezeitpunkt.
INSERT OR IGNORE INTO event_time_segments (
    event_id, job_id, day_key, start_time, end_time,
    start_datetime, end_datetime, source, created_at, updated_at
)
SELECT
    root.id,
    root.job_id,
    substr(ff.selected_capture_time, 1, 10) AS day_key,
    substr(min(substr(ff.selected_capture_time, 1, 19)), 12, 5) AS start_time,
    substr(max(substr(ff.selected_capture_time, 1, 19)), 12, 5) AS end_time,
    min(substr(ff.selected_capture_time, 1, 19)) AS start_datetime,
    max(substr(ff.selected_capture_time, 1, 19)) AS end_datetime,
    'migration',
    datetime('now'),
    datetime('now')
FROM event_assignments ea
JOIN events assigned ON assigned.id = ea.event_id
JOIN events root ON root.id = COALESCE(assigned.parent_event_id, assigned.id)
JOIN file_families ff ON ff.id = ea.family_id AND ff.job_id = root.job_id
WHERE root.event_kind = 'no_event'
  AND ea.family_id IS NOT NULL
  AND ff.selected_capture_time IS NOT NULL
GROUP BY root.id, root.job_id, substr(ff.selected_capture_time, 1, 10);
