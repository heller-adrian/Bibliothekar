-- 012: Sortierlauf-Tabelle bekommt einen Typ
--      + sichere Nachsortierung bereits angewendeter Ereignisse.
--
-- sort_runs dient ab jetzt beiden, sicher getrennten Laufetypen:
--   run_kind = 'initial'  : das normale "Aenderungen anwenden" nach dem
--                           Speichern (0.14.0-Verhalten)
--   run_kind = 'reapply'  : die Nachsortierung nach einer strukturellen
--                           Edition eines bereits angewendeten Ereignisses
--
-- Der Default 'initial' sorgt dafuer, dass Bestandslaufe (produktive
-- Datenbank 0.14.0) automatisch als Initial-Laufe eingeordnet werden.

ALTER TABLE sort_runs
ADD COLUMN run_kind TEXT NOT NULL DEFAULT 'initial'
    CHECK (run_kind IN ('initial', 'reapply'));

ALTER TABLE events
ADD COLUMN resort_required INTEGER NOT NULL DEFAULT 0
    CHECK (resort_required IN (0, 1));

CREATE TABLE event_reapply_removed_families (
    event_id TEXT NOT NULL,
    job_id TEXT NOT NULL,
    family_id INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY(event_id, family_id),
    FOREIGN KEY(event_id) REFERENCES events(id) ON DELETE CASCADE,
    FOREIGN KEY(job_id) REFERENCES jobs(id) ON DELETE CASCADE,
    FOREIGN KEY(family_id) REFERENCES file_families(id) ON DELETE CASCADE
);

CREATE INDEX idx_sort_runs_kind
    ON sort_runs(run_kind, status);
CREATE INDEX idx_event_reapply_removed_job
    ON event_reapply_removed_families(job_id, event_id);
