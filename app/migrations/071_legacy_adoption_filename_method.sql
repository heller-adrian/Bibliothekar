ALTER TABLE legacy_adoption_plans ADD COLUMN filename_method TEXT
    CHECK (filename_method IN ('manual', 'script'));
