-- 036: physischer IST-Zustand 0.28.2
--
-- Platzierungs-Snapshots speichern ausschließlich die letzte bekannte
-- organisationsrelative Lage einer Kameradatei. Sie sind kein zweites
-- Ereignis-SOLL, sondern dienen nur der expliziten Wiederherstellung, wenn
-- Bibliothekar eine Ordnerstruktur AUS und später wieder EIN schaltet.
CREATE TABLE event_file_placement_snapshots (
    event_id TEXT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    organization_path TEXT NOT NULL DEFAULT '',
    restore_pending INTEGER NOT NULL DEFAULT 0 CHECK (restore_pending IN (0,1)),
    captured_at TEXT NOT NULL,
    PRIMARY KEY(event_id,file_id)
);

CREATE INDEX idx_event_file_placement_restore
    ON event_file_placement_snapshots(event_id,restore_pending,file_id);

-- Ein fehlendes Kameraoriginal wird niemals nach einem einzelnen Scan als
-- gelöscht gewertet. Erst zwei aufeinanderfolgende vollständige Scans desselben
-- Ereignisses bestätigen die Löschung. Wird die Datei wieder gefunden,
-- verschwindet diese Beobachtung wieder.
CREATE TABLE event_missing_file_observations (
    event_id TEXT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    root_kind TEXT NOT NULL CHECK (root_kind IN ('shared_workspace','camera_archive')),
    file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    consecutive_misses INTEGER NOT NULL DEFAULT 1,
    first_missing_at TEXT NOT NULL,
    last_missing_at TEXT NOT NULL,
    PRIMARY KEY(event_id,root_kind,file_id)
);

CREATE INDEX idx_event_missing_file_observations
    ON event_missing_file_observations(event_id,root_kind,consecutive_misses);
