ALTER TABLE events
ADD COLUMN folder_naming_json TEXT NOT NULL DEFAULT '{}';

CREATE TABLE metadata_corrections (
    id TEXT PRIMARY KEY,
    area TEXT NOT NULL CHECK (area IN ('library','general')),
    status TEXT NOT NULL
        CHECK (status IN ('pending_review','prepared','writing','completed','blocked','cancelled')),
    source_path TEXT NOT NULL,
    source_relative_path TEXT NOT NULL,
    source_filename TEXT NOT NULL,
    source_size_bytes INTEGER NOT NULL,
    source_sha256 TEXT NOT NULL,
    media_type TEXT NOT NULL,
    detected_json TEXT NOT NULL DEFAULT '{}',
    proposed_datetime TEXT,
    proposal_source TEXT,
    output_path TEXT,
    output_size_bytes INTEGER,
    output_sha256 TEXT,
    verification_json TEXT NOT NULL DEFAULT '{}',
    error_message TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE INDEX idx_metadata_corrections_status
ON metadata_corrections(status, created_at);

CREATE INDEX idx_metadata_corrections_area
ON metadata_corrections(area, created_at);
