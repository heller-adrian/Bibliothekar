-- 047: 0.41.2 – Hinweise von echten Aufgaben trennen und
--      persistente Zuordnungskonflikte bündeln.

ALTER TABLE external_change_notices
ADD COLUMN action_required INTEGER NOT NULL DEFAULT 0
CHECK (action_required IN (0,1));

ALTER TABLE external_change_notices
ADD COLUMN acknowledged_at TEXT;

ALTER TABLE external_change_notices
ADD COLUMN group_key TEXT NOT NULL DEFAULT '';

CREATE INDEX idx_external_change_notices_attention
ON external_change_notices(status, action_required, acknowledged_at, group_key);

-- 0.41.1 erzeugte pro bestätigter Einzeldateilöschung einen sichtbaren
-- Hinweis. Einzeldateilöschungen gehören ab 0.41.2 nur noch ins Audit.
UPDATE external_change_notices
SET status='resolved',
    completed_at=COALESCE(completed_at,updated_at)
WHERE status='open'
  AND kind IN ('central_file_deleted','central_file_modified');

-- Bereits erkannte falsche Ablagen bleiben echte Konsistenzaufgaben,
-- werden aber künftig nur noch einmal gebündelt dargestellt.
UPDATE external_change_notices
SET action_required=1,
    group_key='placement_conflict'
WHERE status='open'
  AND kind IN ('central_file_misplaced','central_file_ambiguous','cross_event_move');
