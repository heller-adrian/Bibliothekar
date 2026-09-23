-- 026: Momentaufnahme des realen Ereignisbestands + zusätzliche Archiv-/SSD-Dateien.
--
-- event_inventory_files ist ausdrücklich KEIN dauerhaftes Soll-Inventar.
-- Bei jedem Scan eines Ereignisses werden die Zeilen für event_id/root_kind
-- vollständig ersetzt. Manuelle spätere Löschungen im Archiv gelten dadurch
-- beim nächsten Scan schlicht als neuer IST-Bestand.
CREATE TABLE event_inventory_files (
    event_id TEXT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    root_kind TEXT NOT NULL CHECK (root_kind IN ('shared_workspace','camera_archive')),
    relative_path TEXT NOT NULL,
    event_relative_path TEXT NOT NULL,
    filename TEXT NOT NULL,
    extension TEXT NOT NULL DEFAULT '',
    asset_kind TEXT NOT NULL CHECK (
        asset_kind IN ('camera_original','xmp','export','derived_media','other')
    ),
    known_file_id INTEGER REFERENCES files(id) ON DELETE SET NULL,
    family_id INTEGER REFERENCES file_families(id) ON DELETE SET NULL,
    source_file_id INTEGER REFERENCES files(id) ON DELETE SET NULL,
    size_bytes INTEGER NOT NULL,
    sha256 TEXT NOT NULL,
    selected_capture_time TEXT,
    selected_capture_source TEXT,
    capture_time_confidence TEXT NOT NULL DEFAULT 'missing',
    scanned_at TEXT NOT NULL,
    PRIMARY KEY(event_id, root_kind, relative_path)
);

CREATE INDEX idx_event_inventory_lookup
    ON event_inventory_files(event_id, root_kind, asset_kind);
CREATE INDEX idx_event_inventory_known_file
    ON event_inventory_files(event_id, root_kind, known_file_id);
CREATE INDEX idx_event_inventory_family
    ON event_inventory_files(event_id, root_kind, family_id);

-- Zusätzliche Dateien, die erst nach dem Kameraimport entstehen (XMP/Export
-- usw.), bekommen für einen manuellen Archiv-Änderungsauftrag eigene
-- read-only Prüfzeilen. Die bestehende Kameradatei-Tabelle bleibt unverändert.
CREATE TABLE event_change_asset_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    change_request_id TEXT NOT NULL
        REFERENCES event_change_requests(id) ON DELETE CASCADE,
    asset_kind TEXT NOT NULL,
    source_file_id INTEGER REFERENCES files(id) ON DELETE SET NULL,
    family_id INTEGER REFERENCES file_families(id) ON DELETE SET NULL,
    old_path TEXT NOT NULL,
    new_path TEXT NOT NULL,
    action TEXT NOT NULL CHECK (action IN ('move','keep','unresolved')),
    expected_size_bytes INTEGER NOT NULL DEFAULT 0,
    expected_sha256 TEXT NOT NULL DEFAULT '',
    verification_status TEXT NOT NULL DEFAULT 'pending',
    actual_size_bytes INTEGER,
    actual_sha256 TEXT,
    verified_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX idx_change_asset_review
    ON event_change_asset_reviews(change_request_id, verification_status);

-- Zusatzdateien auf der SSD werden beim Freigabelauf ebenso einzeln gejournaled
-- wie importierte Kameradateien, ohne dafür künstliche rows in files anzulegen.
CREATE TABLE event_ssd_release_assets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    release_id TEXT NOT NULL
        REFERENCES event_ssd_releases(id) ON DELETE CASCADE,
    asset_kind TEXT NOT NULL,
    source_relative_path TEXT NOT NULL,
    archive_relative_path TEXT NOT NULL,
    expected_size_bytes INTEGER NOT NULL,
    expected_sha256 TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'planned' CHECK (
        status IN ('planned','archive_verified','deleted','already_released','failed')
    ),
    actual_source_size_bytes INTEGER,
    actual_source_sha256 TEXT,
    actual_archive_size_bytes INTEGER,
    actual_archive_sha256 TEXT,
    error_message TEXT,
    verified_at TEXT,
    deleted_at TEXT,
    UNIQUE(release_id, source_relative_path)
);

CREATE INDEX idx_event_ssd_release_assets_run
    ON event_ssd_release_assets(release_id, id);
