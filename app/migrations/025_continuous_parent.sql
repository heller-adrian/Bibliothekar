-- Preserve historical child-defined occupancy without rewriting any interval.
ALTER TABLE events ADD COLUMN time_model_version INTEGER NOT NULL DEFAULT 1;
UPDATE events SET time_model_version=2 WHERE event_kind='no_event'
 OR NOT EXISTS (SELECT 1 FROM events c WHERE c.parent_event_id=events.id);

ALTER TABLE event_change_requests ADD COLUMN time_model_version INTEGER NOT NULL DEFAULT 1;
