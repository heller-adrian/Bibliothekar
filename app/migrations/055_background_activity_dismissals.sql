-- Nur die Sichtbarkeit beendeter Hintergrundauftraege wird markiert.
-- Die urspruenglichen Jobs, Protokolle und Fotodateien bleiben unveraendert.
CREATE TABLE IF NOT EXISTS background_activity_dismissals (
  kind TEXT NOT NULL,
  operation_id TEXT NOT NULL,
  revision TEXT NOT NULL,
  dismissed_at TEXT NOT NULL DEFAULT (datetime('now')),
  PRIMARY KEY (kind, operation_id, revision)
);
