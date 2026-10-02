-- 041: Aufnahmezeit des Live-Archivbestands im Change Request einfrieren.
--
-- Ein Archivscan darf spätere Refreshes nicht dazu führen lassen, dass sich
-- bereits geplante Freigabesegmente nachträglich verschieben. Deshalb wird die
-- bei der Planung maßgebliche Aufnahmezeit pro Review-Zeile dauerhaft
-- gespeichert. Bestehende offene Aufträge bleiben kompatibel: leer bedeutet
-- Legacy-Fallback auf den zuletzt inventarisierten/gespeicherten Wert.

ALTER TABLE event_change_file_reviews
ADD COLUMN planned_capture_time TEXT NOT NULL DEFAULT '';

ALTER TABLE event_change_asset_reviews
ADD COLUMN planned_capture_time TEXT NOT NULL DEFAULT '';
