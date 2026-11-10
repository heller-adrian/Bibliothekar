CREATE TABLE legacy_adoption_families (
    job_id TEXT NOT NULL REFERENCES legacy_adoption_jobs(id) ON DELETE CASCADE,
    family_key TEXT NOT NULL,
    capture_time TEXT,
    review_required INTEGER NOT NULL CHECK (review_required IN (0, 1)),
    PRIMARY KEY (job_id, family_key)
) WITHOUT ROWID;

CREATE INDEX legacy_adoption_families_chronology
    ON legacy_adoption_families(job_id, capture_time, family_key);

CREATE TABLE legacy_adoption_plans (
    job_id TEXT PRIMARY KEY REFERENCES legacy_adoption_jobs(id) ON DELETE CASCADE,
    id TEXT NOT NULL UNIQUE,
    state TEXT NOT NULL CHECK (state IN ('prepared', 'media_verified', 'verified', 'registering', 'completed')),
    draft_json TEXT NOT NULL,
    events_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE legacy_adoption_moves (
    plan_id TEXT NOT NULL REFERENCES legacy_adoption_plans(id) ON DELETE CASCADE,
    relative_path TEXT NOT NULL,
    target_path TEXT,
    target_key TEXT,
    parent_event_id TEXT NOT NULL,
    assigned_event_id TEXT NOT NULL,
    capture_time TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    PRIMARY KEY (plan_id, relative_path),
    UNIQUE (plan_id, target_key)
) WITHOUT ROWID;

CREATE INDEX legacy_adoption_moves_content ON legacy_adoption_moves(plan_id, sha256);

CREATE TABLE legacy_adoption_directories (
    plan_id TEXT NOT NULL REFERENCES legacy_adoption_plans(id) ON DELETE CASCADE,
    relative_path TEXT NOT NULL,
    PRIMARY KEY (plan_id, relative_path)
) WITHOUT ROWID;

CREATE TABLE legacy_adoption_baseline (
    plan_id TEXT NOT NULL REFERENCES legacy_adoption_plans(id) ON DELETE CASCADE,
    relative_path TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    sha256 TEXT NOT NULL,
    PRIMARY KEY (plan_id, relative_path)
) WITHOUT ROWID;

CREATE TABLE legacy_adoption_issues (
    plan_id TEXT NOT NULL REFERENCES legacy_adoption_plans(id) ON DELETE CASCADE,
    relative_path TEXT NOT NULL,
    issue TEXT NOT NULL,
    PRIMARY KEY (plan_id, relative_path, issue)
) WITHOUT ROWID;

CREATE INDEX legacy_adoption_known_original ON files(sha256_original);
CREATE INDEX legacy_adoption_known_current ON files(sha256_current);
