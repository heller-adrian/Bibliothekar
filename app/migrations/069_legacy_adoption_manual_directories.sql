CREATE TABLE legacy_adoption_manual_directories (
    plan_id TEXT NOT NULL REFERENCES legacy_adoption_plans(id) ON DELETE CASCADE,
    relative_path TEXT NOT NULL,
    PRIMARY KEY (plan_id, relative_path)
);
