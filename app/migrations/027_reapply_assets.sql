-- 027: Zusätzliche XMP-/Begleitdateien werden bei einer bestätigten
-- Nachsortierung genauso sicher gejournaled wie importierte Kameradateien.
--
-- Sie erhalten bewusst keine künstlichen rows in files.  Der aktuelle
-- Ereignis-Inventarscan ordnet sie der Kamerafamilie zu; dieses Journal hält
-- nur die konkrete physische Reapply-Operation mit Prüfsumme fest.
CREATE TABLE sort_asset_operations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sort_run_id TEXT NOT NULL
        REFERENCES sort_runs(id) ON DELETE CASCADE,
    sequence_number INTEGER NOT NULL,
    asset_kind TEXT NOT NULL,
    family_id INTEGER
        REFERENCES file_families(id) ON DELETE SET NULL,
    source_file_id INTEGER
        REFERENCES files(id) ON DELETE SET NULL,
    source_relative_path TEXT NOT NULL,
    destination_relative_path TEXT NOT NULL,
    expected_size_bytes INTEGER NOT NULL,
    expected_sha256 TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'planned' CHECK (
        status IN (
            'planned',
            'verified',
            'moved',
            'destination_verified',
            'already_at_target',
            'rolled_back',
            'failed'
        )
    ),
    error_message TEXT,
    verified_at TEXT,
    moved_at TEXT,
    destination_verified_at TEXT,
    rolled_back_at TEXT,
    UNIQUE(sort_run_id, sequence_number),
    UNIQUE(sort_run_id, source_relative_path)
);

CREATE INDEX idx_sort_asset_operations_run
    ON sort_asset_operations(sort_run_id, sequence_number);
