-- 013: Change-Request-Workflow fuer archivierte Ereignisse
--
-- Archivierte Ereignisse koennen ab jetzt nicht nur in Namen/Notizen geaendert,
-- sondern auch strukturell bearbeitet werden — aber nur ueber einen
-- ueberwachten Change-Request-Prozess, der den Benutzer Schritt fuer Schritt
-- durch die erforderlichen manuellen Aenderungen fuehrt.
--
--    1. aenderbar_vorschlagen : Die App berechnet den neuen Zustand und
--       erzeugt einen Änderungsauftrag ohne Datenbank-Änderungen.
--    2. aenderbar_bestaetigt : Der Benutzer hat die Dateiänderungen
--       (verschieben, löschen, zusammenfuegen) manuell durchgefuehrt.
--    3. aenderbar_archiviert : Der Änderungsauftrag ist abgeschlossen,
--       die Dateiänderungen sind verifiziert und das Ereignis wird
--       abschließend neu archiviert mit der neuen Struktur.
--
-- event_change_requests (Aenderungsauftraege pro archiviertem Ereignis)
-- event_change_file_reviews  (pro Datei: alter Pfad, neuer Pfad, Bestaetigung)

-- ── Aenderungsauftraege ──────────────────────────────────────────

CREATE TABLE event_change_requests (
    id TEXT NOT NULL PRIMARY KEY,
    event_id TEXT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    job_id TEXT NOT NULL,
    event_name TEXT NOT NULL,
    notes TEXT NOT NULL,
    parent_folder TEXT NOT NULL,
    child_folder TEXT,
    uses_time_range INTEGER NOT NULL DEFAULT 0
        CHECK (uses_time_range IN (0, 1)),
    preserve_day_folders INTEGER NOT NULL DEFAULT 1
        CHECK (preserve_day_folders IN (0, 1)),
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    start_time TEXT,
    end_time TEXT,
    selected_day_keys TEXT NOT NULL DEFAULT '',
    selected_family_ids TEXT NOT NULL,
    selected_file_count INTEGER NOT NULL DEFAULT 0,
    selected_family_count INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'aenderbar_vorschlagen'
        CHECK (status IN (
            'aenderbar_vorschlagen',
            'aenderbar_bestaetigt',
            'aenderbar_abgebrochen',
            'aenderbar_archiviert'
        )),
    version INTEGER NOT NULL DEFAULT 1,
    proposed_at TEXT NOT NULL,
    confirmed_at TEXT,
    finished_at TEXT,
    cancelled_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Nur ein aktiver (nicht abgebrochener) Auftrag pro Ereignis erlauben.
CREATE UNIQUE INDEX idx_change_req_active
    ON event_change_requests(event_id, version)
    WHERE status IN ('aenderbar_vorschlagen', 'aenderbar_bestaetigt');

-- Schnelle Suche nach offenem Aenderungsauftrag.
CREATE INDEX idx_change_req_event_status
    ON event_change_requests(event_id, status);

-- ── Datei-Bestaetigungen ─────────────────────────────────────────

CREATE TABLE event_change_file_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    change_request_id TEXT NOT NULL
        REFERENCES event_change_requests(id) ON DELETE CASCADE,
    family_id INTEGER NOT NULL,
    old_path TEXT NOT NULL,
    new_path TEXT NOT NULL,
    action TEXT NOT NULL
        CHECK (action IN ('move', 'delete', 'keep', 'merge')),
    confirmed INTEGER NOT NULL DEFAULT 0
        CHECK (confirmed IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX idx_change_file_review
    ON event_change_file_reviews(change_request_id, confirmed);
