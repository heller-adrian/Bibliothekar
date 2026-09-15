-- 0.20.0: exakter zuletzt erfolgreich geprüfter Archivpfad je Datei.
-- Zusätzlich zum stabilen Familienanker kann die App dadurch zuerst den
-- tatsächlich geprüften Ort verwenden. Wurde die Datei danach innerhalb
-- Alle/Sortiert/Export verschoben, fällt die Auflösung kontrolliert auf die
-- Suche innerhalb des stabilen Strukturankers zurück.
CREATE TABLE event_archive_verified_file_locations (
    event_id TEXT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    family_id INTEGER NOT NULL REFERENCES file_families(id) ON DELETE CASCADE,
    file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    relative_path TEXT NOT NULL,
    verified_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY(event_id, file_id)
);

CREATE INDEX idx_event_archive_verified_file_locations_family
    ON event_archive_verified_file_locations(event_id, family_id);
