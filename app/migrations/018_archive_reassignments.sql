-- 0.16.10: Ziele für herausfallende Familien aus manuellen Archivänderungen.
CREATE TABLE event_change_reassignments (
    change_request_id TEXT NOT NULL REFERENCES event_change_requests(id) ON DELETE CASCADE,
    family_id INTEGER NOT NULL REFERENCES file_families(id) ON DELETE CASCADE,
    target_kind TEXT NOT NULL CHECK (target_kind IN ('new_event','new_no_event','existing_no_event')),
    target_event_id TEXT REFERENCES events(id),
    target_name TEXT NOT NULL,
    target_folder_name TEXT NOT NULL,
    target_start_datetime TEXT NOT NULL,
    target_end_datetime TEXT NOT NULL,
    target_uses_time_range INTEGER NOT NULL DEFAULT 0 CHECK (target_uses_time_range IN (0,1)),
    target_child_name TEXT,
    target_child_folder TEXT,
    target_preserve_day_folders INTEGER NOT NULL DEFAULT 0 CHECK (target_preserve_day_folders IN (0,1)),
    created_at TEXT NOT NULL,
    PRIMARY KEY(change_request_id, family_id)
);
CREATE INDEX idx_event_change_reassign_target ON event_change_reassignments(target_event_id, target_kind);

-- Archivierte „Ohne Ereignis“-Sammlungen speichern ihre echten Segmente
-- im Änderungsauftrag; die Von-bis-Werte sind nur eine Bounding-Ansicht.
ALTER TABLE event_change_requests
    ADD COLUMN no_event_segments TEXT NOT NULL DEFAULT '[]';
