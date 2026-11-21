-- RC2 keeps a source SHA-256 and a separate approved destination SHA-256
-- when (and only when) the Camera Raw XMP RawFileName has to be rewritten.
-- Defaults are NULL: all previously prepared RC1 moves retain their contract.
ALTER TABLE legacy_adoption_moves ADD COLUMN current_sha256 TEXT;
ALTER TABLE legacy_adoption_moves ADD COLUMN current_size_bytes INTEGER;
ALTER TABLE legacy_adoption_moves ADD COLUMN xmp_old_raw_name TEXT;
ALTER TABLE legacy_adoption_moves ADD COLUMN xmp_new_raw_name TEXT;
