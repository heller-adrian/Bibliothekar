-- 014: Dateigenaue, read-only pruefbare Archiv-Aenderungsauftraege
ALTER TABLE event_change_file_reviews ADD COLUMN file_id INTEGER REFERENCES files(id);
ALTER TABLE event_change_file_reviews ADD COLUMN expected_size_bytes INTEGER NOT NULL DEFAULT 0;
ALTER TABLE event_change_file_reviews ADD COLUMN expected_sha256 TEXT NOT NULL DEFAULT '';
ALTER TABLE event_change_file_reviews ADD COLUMN verification_status TEXT NOT NULL DEFAULT 'pending';
ALTER TABLE event_change_file_reviews ADD COLUMN actual_size_bytes INTEGER;
ALTER TABLE event_change_file_reviews ADD COLUMN actual_sha256 TEXT;
ALTER TABLE event_change_file_reviews ADD COLUMN verified_at TEXT;

ALTER TABLE event_change_requests ADD COLUMN event_kind TEXT NOT NULL DEFAULT 'event';
ALTER TABLE event_change_requests ADD COLUMN child_event_name TEXT;
