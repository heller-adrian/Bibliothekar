-- 029: planned edits/deletes are complete when saved.
-- Legacy open reassignment rows from older planned workflows become
-- informational released-free markers and must never block further editing.
INSERT OR REPLACE INTO released_free_families(
    job_id,
    family_id,
    released_start_datetime,
    released_end_datetime,
    created_at
)
SELECT
    r.job_id,
    r.family_id,
    r.released_start_datetime,
    r.released_end_datetime,
    r.created_at
FROM event_reapply_removed_families r
JOIN events e ON e.id = r.event_id
WHERE e.status IN ('draft','planned')
  AND e.applied_at IS NULL
  AND r.target_event_id IS NULL
  AND COALESCE(r.target_kind,'') <> 'released_free';

DELETE FROM event_reapply_removed_families
WHERE rowid IN (
    SELECT r.rowid
    FROM event_reapply_removed_families r
    JOIN events e ON e.id = r.event_id
    WHERE e.status IN ('draft','planned')
      AND e.applied_at IS NULL
      AND r.target_event_id IS NULL
      AND COALESCE(r.target_kind,'') <> 'released_free'
);
