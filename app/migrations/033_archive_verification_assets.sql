-- 033: Dynamische Ereignisdateien (XMP/Export) in der Archivprüfung journalen.
--
-- event_archive_verification_files bleibt auf importierte Kameraoriginale
-- beschränkt. Zusatzdateien erhalten ein eigenes, SHA-256-basiertes Journal.
CREATE TABLE event_archive_verification_assets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    verification_id TEXT NOT NULL
        REFERENCES event_archive_verifications(id) ON DELETE CASCADE,
    asset_kind TEXT NOT NULL CHECK (
        asset_kind IN ('xmp','export','derived_media')
    ),
    source_event_relative_path TEXT NOT NULL,
    expected_relative_path TEXT NOT NULL,
    expected_size_bytes INTEGER NOT NULL,
    expected_sha256 TEXT NOT NULL,
    status TEXT NOT NULL CHECK (
        status IN ('verified','missing','size_mismatch','sha256_mismatch','unsafe_path')
    ),
    actual_size_bytes INTEGER,
    actual_sha256 TEXT,
    error_message TEXT,
    UNIQUE(verification_id, source_event_relative_path)
);

CREATE INDEX idx_archive_verification_assets_run
    ON event_archive_verification_assets(verification_id, status);
