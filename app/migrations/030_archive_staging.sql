-- 030: Archivänderungen mit vorbereiteter SSD-Struktur und sicheren Zuführungen.
--
-- Die Kamerabibliothek bleibt read-only. Neue freie Arbeitsdateien können in
-- Arbeitsbereich/Später zuordnen als geprüfte Hardlinks vorbereitet werden und
-- werden erst nach erfolgreicher Archivprüfung aus dem SSD-Arbeitsbestand
-- freigegeben.

ALTER TABLE event_change_requests
ADD COLUMN prepared_structure_path TEXT NOT NULL DEFAULT '';

ALTER TABLE event_change_file_reviews
ADD COLUMN source_root_kind TEXT NOT NULL DEFAULT 'camera_archive'
    CHECK (source_root_kind IN ('camera_archive','shared_workspace'));

ALTER TABLE event_change_file_reviews
ADD COLUMN workspace_original_path TEXT NOT NULL DEFAULT '';

ALTER TABLE event_change_file_reviews
ADD COLUMN workspace_staging_path TEXT NOT NULL DEFAULT '';
