ALTER TABLE events
ADD COLUMN linked_event_id TEXT
REFERENCES events(id)
ON DELETE SET NULL;

ALTER TABLE events
ADD COLUMN linkage_kind TEXT
CHECK (
    linkage_kind IS NULL
    OR linkage_kind IN (
        'planned_extension',
        'applied_followup',
        'archived_manual'
    )
);

CREATE INDEX idx_events_linked_event
    ON events(linked_event_id, linkage_kind);
