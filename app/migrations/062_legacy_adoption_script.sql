CREATE TABLE legacy_adoption_scripts (
    plan_id TEXT PRIMARY KEY REFERENCES legacy_adoption_execution(plan_id) ON DELETE CASCADE,
    manifest_sha256 TEXT NOT NULL,
    package_device INTEGER NOT NULL,
    package_inode INTEGER NOT NULL,
    host_json TEXT NOT NULL
) WITHOUT ROWID;
