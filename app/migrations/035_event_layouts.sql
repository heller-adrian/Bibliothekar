-- 035: Konfigurierbare, pro Ereignis eingefrorene Unterordnerstruktur.
--
-- Globale Einstellungen sind nur Vorlagen für NEUE Ereignisse. Jedes Ereignis
-- erhält eine eigene Momentaufnahme. Bestehende Ereignisse werden exakt auf das
-- bisherige Verhalten Alle/Sortiert/Export, Input=Alle zurückgefüllt.
CREATE TABLE app_settings (
    setting_key TEXT PRIMARY KEY,
    value_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE event_folder_layouts (
    event_id TEXT PRIMARY KEY REFERENCES events(id) ON DELETE CASCADE,
    structure_enabled INTEGER NOT NULL DEFAULT 1
        CHECK (structure_enabled IN (0,1)),
    input_path TEXT NOT NULL DEFAULT 'Alle',
    layout_json TEXT NOT NULL,
    revision INTEGER NOT NULL DEFAULT 1 CHECK (revision >= 1),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE event_inventory_directories (
    event_id TEXT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    root_kind TEXT NOT NULL CHECK (root_kind IN ('shared_workspace','camera_archive')),
    event_relative_path TEXT NOT NULL,
    scanned_at TEXT NOT NULL,
    PRIMARY KEY(event_id, root_kind, event_relative_path)
);

CREATE INDEX idx_event_inventory_directories_lookup
    ON event_inventory_directories(event_id, root_kind);

CREATE TABLE event_structure_changes (
    id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    root_kind TEXT NOT NULL CHECK (root_kind IN ('shared_workspace','camera_archive')),
    status TEXT NOT NULL CHECK (
        status IN ('pending','prepared','verified','completed','cancelled','blocked')
    ),
    detected_json TEXT NOT NULL,
    proposed_layout_json TEXT NOT NULL DEFAULT '',
    proposed_input_path TEXT NOT NULL DEFAULT '',
    error_message TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE UNIQUE INDEX idx_event_structure_changes_one_open
    ON event_structure_changes(event_id, root_kind)
    WHERE status IN ('pending','prepared','verified');

CREATE INDEX idx_event_structure_changes_status
    ON event_structure_changes(status, updated_at);

INSERT OR IGNORE INTO app_settings(setting_key, value_json, updated_at)
VALUES (
    'event_folder_layout_default',
    '{"structure_enabled":true,"input_path":"Alle","layout":{"version":1,"nodes":[{"id":"legacy-alle","name":"Alle","children":[]},{"id":"legacy-sortiert","name":"Sortiert","children":[]},{"id":"legacy-export","name":"Export","children":[]}]}}',
    datetime('now')
);

INSERT OR IGNORE INTO event_folder_layouts(
    event_id, structure_enabled, input_path, layout_json, revision, created_at, updated_at
)
SELECT
    id,
    1,
    'Alle',
    '{"version":1,"nodes":[{"id":"legacy-alle","name":"Alle","children":[]},{"id":"legacy-sortiert","name":"Sortiert","children":[]},{"id":"legacy-export","name":"Export","children":[]}]}',
    1,
    COALESCE(created_at, datetime('now')),
    COALESCE(updated_at, datetime('now'))
FROM events
WHERE parent_event_id IS NULL;
