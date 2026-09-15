ALTER TABLE events ADD COLUMN notes TEXT NOT NULL DEFAULT '';
ALTER TABLE events ADD COLUMN edited_at TEXT;
CREATE INDEX idx_events_edited_at ON events(edited_at);
