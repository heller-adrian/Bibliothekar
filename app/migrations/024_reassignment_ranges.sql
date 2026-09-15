ALTER TABLE event_reapply_removed_families
ADD COLUMN released_start_datetime TEXT;

ALTER TABLE event_reapply_removed_families
ADD COLUMN released_end_datetime TEXT;
