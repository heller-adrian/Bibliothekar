ALTER TABLE events
ADD COLUMN event_kind TEXT NOT NULL
DEFAULT 'event'
CHECK (
    event_kind IN (
        'event',
        'no_event'
    )
);

ALTER TABLE events
ADD COLUMN preserve_day_folders INTEGER NOT NULL
DEFAULT 0
CHECK (
    preserve_day_folders IN (0, 1)
);

ALTER TABLE events
ADD COLUMN revision INTEGER NOT NULL
DEFAULT 1
CHECK (
    revision >= 1
);

ALTER TABLE events
ADD COLUMN applied_at TEXT;

ALTER TABLE events
ADD COLUMN archived_at TEXT;


CREATE TABLE archive_change_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    job_id TEXT NOT NULL,
    event_id TEXT,
    file_id INTEGER,

    detected_relative_path TEXT,
    expected_relative_path TEXT NOT NULL,

    sha256_expected TEXT,
    size_bytes_expected INTEGER,

    review_status TEXT NOT NULL
    DEFAULT 'pending'
    CHECK (
        review_status IN (
            'pending',
            'manual_move_required',
            'manually_moved',
            'verified',
            'missing',
            'ambiguous',
            'ignored'
        )
    ),

    reason TEXT,

    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    verified_at TEXT,

    UNIQUE (
        event_id,
        file_id,
        expected_relative_path
    ),

    FOREIGN KEY(job_id)
        REFERENCES jobs(id)
        ON DELETE CASCADE,

    FOREIGN KEY(event_id)
        REFERENCES events(id)
        ON DELETE SET NULL,

    FOREIGN KEY(file_id)
        REFERENCES files(id)
        ON DELETE CASCADE
);


CREATE INDEX idx_events_kind
    ON events(
        job_id,
        event_kind,
        status
    );

CREATE INDEX idx_archive_change_job
    ON archive_change_reviews(
        job_id,
        review_status
    );

CREATE INDEX idx_archive_change_event
    ON archive_change_reviews(
        event_id,
        review_status
    );

CREATE INDEX idx_archive_change_file
    ON archive_change_reviews(file_id);
