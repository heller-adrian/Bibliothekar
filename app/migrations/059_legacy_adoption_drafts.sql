ALTER TABLE legacy_adoption_jobs ADD COLUMN draft_json TEXT NOT NULL DEFAULT '{}';

CREATE TABLE legacy_adoption_folder_moves (
    plan_id TEXT NOT NULL REFERENCES legacy_adoption_plans(id) ON DELETE CASCADE,
    source_path TEXT NOT NULL,
    target_path TEXT NOT NULL,
    file_count INTEGER NOT NULL,
    PRIMARY KEY (plan_id, source_path)
) WITHOUT ROWID;
