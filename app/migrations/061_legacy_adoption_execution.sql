ALTER TABLE legacy_adoption_jobs ADD COLUMN draft_revision INTEGER NOT NULL DEFAULT 0;

CREATE TABLE legacy_adoption_execution (
    plan_id TEXT PRIMARY KEY REFERENCES legacy_adoption_plans(id) ON DELETE CASCADE,
    method TEXT NOT NULL CHECK (method IN ('manual', 'script')),
    phase TEXT NOT NULL CHECK (phase IN (
        'manual', 'script_prepared', 'script_running', 'script_interrupted', 'operations_done',
        'verifying', 'repair', 'registration_pending', 'registering', 'completed',
        'rolling_back', 'rolled_back'
    )),
    confirmed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
) WITHOUT ROWID;
