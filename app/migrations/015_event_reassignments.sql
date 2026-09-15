-- 015: Neu-Zuordnung herausfallender Familien (0.16.3)
--
-- Die bestehende Tabelle event_reapply_removed_families wird als sichere,
-- transiente Warteschlange erweitert. Sie speichert jetzt nicht nur, welche
-- Familie aus einem bearbeiteten Ereignis herausfällt, sondern auch wohin sie
-- anschließend gehört. Für planned-Ereignisse wird der Eintrag nach der reinen
-- DB-Zuordnung wieder entfernt. Für applied-Ereignisse bleibt er bis zum
-- vollständig geprüften Reapply-Lauf bestehen, damit der Dateiplan das neue
-- Ziel kennt.

ALTER TABLE event_reapply_removed_families ADD COLUMN target_event_id TEXT;
ALTER TABLE event_reapply_removed_families ADD COLUMN target_status TEXT;
ALTER TABLE event_reapply_removed_families ADD COLUMN target_kind TEXT;
ALTER TABLE event_reapply_removed_families ADD COLUMN target_name TEXT;
ALTER TABLE event_reapply_removed_families ADD COLUMN target_folder_name TEXT;
ALTER TABLE event_reapply_removed_families ADD COLUMN target_preserve_day_folders INTEGER;
ALTER TABLE event_reapply_removed_families ADD COLUMN target_linkage_kind TEXT;
ALTER TABLE event_reapply_removed_families ADD COLUMN reassigned_at TEXT;

CREATE INDEX idx_event_reapply_removed_target
    ON event_reapply_removed_families(target_event_id, target_status);
