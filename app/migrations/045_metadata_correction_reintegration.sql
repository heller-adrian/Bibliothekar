ALTER TABLE files
ADD COLUMN source_size_bytes INTEGER;

UPDATE files
SET source_size_bytes = size_bytes
WHERE source_size_bytes IS NULL;
