-- 032: distinguish general free-workspace markers from durable archive-release provenance.
--
-- Only families that were physically recovered from the read-only camera archive
-- retain their marker while temporarily assigned to another event.  General
-- planned/applied free markers keep their historical cleanup semantics.

ALTER TABLE released_free_families
ADD COLUMN archive_origin INTEGER NOT NULL DEFAULT 0
    CHECK (archive_origin IN (0,1));

UPDATE released_free_families
SET archive_origin=1
WHERE EXISTS (
    SELECT 1 FROM files f
    WHERE f.family_id=released_free_families.family_id
      AND f.job_id=released_free_families.job_id
      AND f.current_root_kind='shared_workspace'
      AND f.current_relative_path LIKE 'Freigewordene Archivdateien/%'
)
OR EXISTS (
    SELECT 1 FROM released_archive_assets a
    WHERE a.family_id=released_free_families.family_id
      AND a.job_id=released_free_families.job_id
);
