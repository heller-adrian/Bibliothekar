-- 053: optional per-leaf organization and input layout for manually observed
-- parent/child/day directory structures. Historical parent layouts remain valid.
CREATE TABLE IF NOT EXISTS event_leaf_folder_layouts (
  parent_event_id TEXT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
  leaf_key TEXT NOT NULL,
  leaf_prefix TEXT NOT NULL,
  structure_enabled INTEGER NOT NULL CHECK(structure_enabled IN (0,1)),
  input_path TEXT NOT NULL DEFAULT '',
  layout_json TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (parent_event_id,leaf_key)
);
CREATE INDEX IF NOT EXISTS idx_event_leaf_folder_layout_parent
  ON event_leaf_folder_layouts(parent_event_id);
