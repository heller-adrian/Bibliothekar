CREATE TABLE IF NOT EXISTS library_identity (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    library_id TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL
);
