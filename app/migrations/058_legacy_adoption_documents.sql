ALTER TABLE legacy_adoption_plans ADD COLUMN documents_at TEXT;
ALTER TABLE legacy_adoption_baseline ADD COLUMN document BLOB;

CREATE TABLE legacy_adoption_documents (
    plan_id TEXT NOT NULL REFERENCES legacy_adoption_plans(id) ON DELETE CASCADE,
    relative_path TEXT NOT NULL,
    content BLOB NOT NULL,
    sha256 TEXT NOT NULL,
    PRIMARY KEY (plan_id, relative_path)
) WITHOUT ROWID;
