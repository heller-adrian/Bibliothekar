-- 0.19.0: zuletzt verifizierter stabiler Archiv-Strukturanker je Familie.
-- Der Anker endet vor den veränderlichen Sortierordnern Alle/Sortiert/Export.
CREATE TABLE event_archive_family_anchors (
    event_id TEXT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    family_id INTEGER NOT NULL REFERENCES file_families(id) ON DELETE CASCADE,
    anchor_relative_path TEXT NOT NULL,
    verified_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY(event_id, family_id)
);

CREATE INDEX idx_event_archive_family_anchors_family
    ON event_archive_family_anchors(family_id, event_id);
