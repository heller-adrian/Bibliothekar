-- 037: Ordnerlayout im archivierten Change-Request
--
-- Ein Archiv-Edit darf die kanonische DB erst nach der read-only Prüfung
-- verändern. Deshalb wird auch die gewünschte Unterordnerkonfiguration im
-- Änderungsauftrag selbst eingefroren.
ALTER TABLE event_change_requests
    ADD COLUMN folder_structure_enabled INTEGER
        CHECK (folder_structure_enabled IN (0,1));

ALTER TABLE event_change_requests
    ADD COLUMN folder_input_path TEXT;

ALTER TABLE event_change_requests
    ADD COLUMN folder_layout_json TEXT;
