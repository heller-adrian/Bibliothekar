-- Sichtbarkeit des Prüfverlaufs gehört zum Auftrag, nicht zur Datei-Lebensdauer.
ALTER TABLE jobs ADD COLUMN history_hidden INTEGER NOT NULL DEFAULT 0 CHECK(history_hidden IN (0, 1));
CREATE INDEX IF NOT EXISTS idx_jobs_history_hidden_created ON jobs(history_hidden, created_at DESC, id DESC);
