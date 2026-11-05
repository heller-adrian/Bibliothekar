-- Archive guided edits must remain linked to the exact detected manual task.
-- Existing change requests have NULL provenance and remain unchanged.
ALTER TABLE event_change_requests ADD COLUMN guided_structure_change_id TEXT;
