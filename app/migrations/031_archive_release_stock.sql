-- 031: Herausfallende Archivdateien sicher in den SSD-Arbeitsbereich zurückholen.
--
-- Ein Archiv-Änderungsauftrag weist freigewordene Familien nicht mehr sofort
-- einem neuen Ereignis zu. Die Dateien werden zunächst manuell in
-- Arbeitsbereich/Freigewordene Archivdateien kopiert, per SHA-256 geprüft und
-- erst danach manuell aus der Kamerabibliothek entfernt.

ALTER TABLE event_change_file_reviews
ADD COLUMN workspace_release_path TEXT NOT NULL DEFAULT '';

ALTER TABLE event_change_asset_reviews
ADD COLUMN workspace_release_path TEXT NOT NULL DEFAULT '';

CREATE TABLE released_archive_assets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    family_id INTEGER REFERENCES file_families(id) ON DELETE CASCADE,
    source_file_id INTEGER REFERENCES files(id) ON DELETE SET NULL,
    asset_kind TEXT NOT NULL,
    current_relative_path TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    sha256 TEXT NOT NULL,
    origin_change_request_id TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(job_id, current_relative_path)
);

CREATE INDEX idx_released_archive_assets_family
    ON released_archive_assets(job_id, family_id);

-- Sortierjournale müssen bei gemischten Quellen pro Operation wissen, ob der
-- Quellpfad unter der ursprünglichen Sicherung oder im gemeinsamen SSD-
-- Arbeitsbereich liegt. Das ist für sicheren Rollback nach Neustart nötig.
ALTER TABLE sort_operations
ADD COLUMN source_root_kind TEXT NOT NULL DEFAULT 'job_root'
    CHECK (source_root_kind IN ('job_root','shared_workspace'));

ALTER TABLE sort_asset_operations
ADD COLUMN source_root_kind TEXT NOT NULL DEFAULT 'shared_workspace'
    CHECK (source_root_kind IN ('job_root','shared_workspace'));

UPDATE sort_operations
SET source_root_kind='shared_workspace'
WHERE sort_run_id IN (
    SELECT id FROM sort_runs
    WHERE COALESCE(run_kind,'initial')='reapply'
);
