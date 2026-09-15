PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_versions (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE jobs (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL CHECK (
        kind IN (
            'simulation',
            'sd_import',
            'archive_verification',
            'hardlink_sync'
        )
    ),
    trigger_type TEXT NOT NULL CHECK (
        trigger_type IN (
            'manual',
            'approved_sd',
            'usb_key',
            'system'
        )
    ),
    state TEXT NOT NULL CHECK (
        state IN (
            'queued',
            'copying',
            'verifying',
            'backup_verified',
            'analyzing_metadata',
            'waiting_for_review',
            'organizing',
            'waiting_for_archive',
            'archive_verified',
            'deletion_approved',
            'completed',
            'failed',
            'interrupted'
        )
    ),
    stage TEXT NOT NULL,
    source_path TEXT,
    working_path TEXT,
    archive_target_path TEXT,
    source_device_id TEXT,
    source_filesystem_uuid TEXT,
    source_volume_label TEXT,
    file_count INTEGER,
    total_size_bytes INTEGER,
    error_message TEXT,
    created_at TEXT NOT NULL,
    started_at TEXT,
    updated_at TEXT NOT NULL,
    finished_at TEXT
);

CREATE TABLE file_families (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL,
    family_key TEXT NOT NULL,
    original_stem TEXT,
    status TEXT NOT NULL DEFAULT 'detected' CHECK (
        status IN (
            'detected',
            'complete',
            'incomplete',
            'ambiguous',
            'review_required'
        )
    ),
    selected_capture_time TEXT,
    capture_time_confidence TEXT CHECK (
        capture_time_confidence IN (
            'high',
            'medium',
            'low',
            'conflict',
            'missing'
        )
    ),
    UNIQUE(job_id, family_key),
    FOREIGN KEY(job_id)
        REFERENCES jobs(id)
        ON DELETE CASCADE
);

CREATE TABLE files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL,
    family_id INTEGER,
    original_relative_path TEXT NOT NULL,
    current_relative_path TEXT,
    original_filename TEXT NOT NULL,
    extension TEXT NOT NULL,
    media_type TEXT NOT NULL CHECK (
        media_type IN (
            'raw',
            'jpeg',
            'image',
            'xmp',
            'video',
            'audio',
            'other'
        )
    ),
    size_bytes INTEGER NOT NULL,
    sha256_original TEXT NOT NULL,
    sha256_current TEXT,
    selected_capture_time TEXT,
    selected_capture_source TEXT,
    capture_time_confidence TEXT NOT NULL DEFAULT 'missing' CHECK (
        capture_time_confidence IN (
            'high',
            'medium',
            'low',
            'conflict',
            'missing'
        )
    ),
    review_status TEXT NOT NULL DEFAULT 'unreviewed' CHECK (
        review_status IN (
            'unreviewed',
            'not_required',
            'required',
            'confirmed',
            'corrected',
            'rejected'
        )
    ),
    metadata_write_status TEXT NOT NULL DEFAULT 'not_requested' CHECK (
        metadata_write_status IN (
            'not_requested',
            'planned',
            'confirmed',
            'written',
            'failed'
        )
    ),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(job_id, original_relative_path),
    FOREIGN KEY(job_id)
        REFERENCES jobs(id)
        ON DELETE CASCADE,
    FOREIGN KEY(family_id)
        REFERENCES file_families(id)
        ON DELETE SET NULL
);

CREATE TABLE metadata_candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id INTEGER NOT NULL,
    metadata_group TEXT NOT NULL,
    tag_name TEXT NOT NULL,
    raw_value TEXT,
    normalized_datetime TEXT,
    timezone_source TEXT,
    priority INTEGER NOT NULL,
    confidence TEXT NOT NULL CHECK (
        confidence IN (
            'high',
            'medium',
            'low',
            'unusable'
        )
    ),
    is_selected INTEGER NOT NULL DEFAULT 0 CHECK (
        is_selected IN (0, 1)
    ),
    conflicts_with_selected INTEGER NOT NULL DEFAULT 0 CHECK (
        conflicts_with_selected IN (0, 1)
    ),
    FOREIGN KEY(file_id)
        REFERENCES files(id)
        ON DELETE CASCADE
);

CREATE TABLE events (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
    parent_event_id TEXT,
    event_level TEXT NOT NULL CHECK (
        event_level IN (
            'parent',
            'child'
        )
    ),
    name TEXT NOT NULL,
    start_datetime TEXT NOT NULL,
    end_datetime TEXT NOT NULL,
    uses_time_range INTEGER NOT NULL DEFAULT 0 CHECK (
        uses_time_range IN (0, 1)
    ),
    folder_name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (
        status IN (
            'draft',
            'planned',
            'applied',
            'archived'
        )
    ),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,

    CHECK (
        (
            event_level = 'parent'
            AND parent_event_id IS NULL
            AND uses_time_range = 0
        )
        OR
        (
            event_level = 'child'
            AND parent_event_id IS NOT NULL
            AND uses_time_range = 1
        )
    ),

    FOREIGN KEY(job_id)
        REFERENCES jobs(id)
        ON DELETE CASCADE,
    FOREIGN KEY(parent_event_id)
        REFERENCES events(id)
        ON DELETE CASCADE
);

CREATE TABLE event_assignments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL,
    family_id INTEGER,
    file_id INTEGER,
    assignment_source TEXT NOT NULL CHECK (
        assignment_source IN (
            'date_range',
            'date_time_range',
            'manual',
            'calendar'
        )
    ),
    created_at TEXT NOT NULL,

    CHECK (
        (family_id IS NOT NULL AND file_id IS NULL)
        OR
        (family_id IS NULL AND file_id IS NOT NULL)
    ),

    UNIQUE(event_id, family_id),
    UNIQUE(event_id, file_id),

    FOREIGN KEY(event_id)
        REFERENCES events(id)
        ON DELETE CASCADE,
    FOREIGN KEY(family_id)
        REFERENCES file_families(id)
        ON DELETE CASCADE,
    FOREIGN KEY(file_id)
        REFERENCES files(id)
        ON DELETE CASCADE
);

CREATE TABLE archive_verifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL,
    archive_root TEXT NOT NULL,
    expected_file_count INTEGER NOT NULL,
    matched_file_count INTEGER NOT NULL,
    missing_file_count INTEGER NOT NULL,
    mismatched_file_count INTEGER NOT NULL,
    extra_file_count INTEGER NOT NULL,
    verified INTEGER NOT NULL CHECK (
        verified IN (0, 1)
    ),
    verified_at TEXT NOT NULL,
    FOREIGN KEY(job_id)
        REFERENCES jobs(id)
        ON DELETE CASCADE
);

CREATE TABLE audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT,
    action TEXT NOT NULL,
    entity_type TEXT,
    entity_id TEXT,
    details_json TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(job_id)
        REFERENCES jobs(id)
        ON DELETE SET NULL
);

CREATE INDEX idx_files_job
    ON files(job_id);

CREATE INDEX idx_files_family
    ON files(family_id);

CREATE INDEX idx_files_review
    ON files(job_id, review_status);

CREATE INDEX idx_metadata_file
    ON metadata_candidates(file_id, priority);

CREATE INDEX idx_events_job
    ON events(job_id, event_level);

CREATE INDEX idx_events_parent
    ON events(parent_event_id);

CREATE INDEX idx_events_time
    ON events(job_id, start_datetime, end_datetime);

CREATE INDEX idx_jobs_state
    ON jobs(state, updated_at);
