PRAGMA foreign_keys = ON;

ALTER TABLE sort_runs
ADD COLUMN central_root TEXT;

ALTER TABLE sort_operations
ADD COLUMN destination_root_kind TEXT NOT NULL DEFAULT 'target_root'
CHECK (destination_root_kind IN ('target_root','central_stock'));

ALTER TABLE sort_asset_operations
ADD COLUMN destination_root_kind TEXT NOT NULL DEFAULT 'target_root'
CHECK (destination_root_kind IN ('target_root','central_stock'));
