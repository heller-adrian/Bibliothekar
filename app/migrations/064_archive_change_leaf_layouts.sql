-- Freeze individually configured subevent and day folders in new archive requests.
ALTER TABLE event_change_requests ADD COLUMN target_leaf_layouts_json TEXT;
