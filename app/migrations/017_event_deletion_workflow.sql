-- 0.16.8: sichere Lösch-Workflows für applied/archived Ereignisse.
ALTER TABLE events ADD COLUMN pending_delete INTEGER NOT NULL DEFAULT 0 CHECK (pending_delete IN (0,1));
ALTER TABLE event_change_requests ADD COLUMN delete_event INTEGER NOT NULL DEFAULT 0 CHECK (delete_event IN (0,1));
