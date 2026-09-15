ALTER TABLE event_change_requests
ADD COLUMN child_segments_json TEXT NOT NULL DEFAULT '[]';
