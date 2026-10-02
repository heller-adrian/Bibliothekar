-- 042: Herkunft eingehender Archiv-Assets dauerhaft im Änderungsauftrag speichern.
--
-- 0.32.7 rekonstruierte bei XMP/Export später anhand released_archive_assets,
-- ob eine Datei aus dem globalen SSD-Rückkehrbestand oder bereits aus dem
-- Kameraarchiv stammt. Sobald sich das Journal änderte, verlor der Finder-
-- Assistent diese Information und behandelte Assets fälschlich als
-- Archiv-intern. 0.32.8 friert deshalb dieselbe Provenienz wie bei
-- Kameraoriginalen direkt in der Review-Zeile ein.

ALTER TABLE event_change_asset_reviews
ADD COLUMN source_root_kind TEXT NOT NULL DEFAULT 'camera_archive'
    CHECK (source_root_kind IN ('camera_archive','shared_workspace'));

ALTER TABLE event_change_asset_reviews
ADD COLUMN workspace_original_path TEXT NOT NULL DEFAULT '';

ALTER TABLE event_change_asset_reviews
ADD COLUMN workspace_staging_path TEXT NOT NULL DEFAULT '';

ALTER TABLE event_change_asset_reviews
ADD COLUMN released_archive_asset_id INTEGER;
