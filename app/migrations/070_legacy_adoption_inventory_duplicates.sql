ALTER TABLE legacy_adoption_inventory ADD COLUMN disposition TEXT NOT NULL DEFAULT 'candidate'
    CHECK (disposition IN ('candidate', 'duplicate', 'detached'));

CREATE VIEW legacy_adoption_candidate_families AS
SELECT family.*
FROM legacy_adoption_families AS family
WHERE EXISTS (
    SELECT 1 FROM legacy_adoption_inventory AS member
     WHERE member.job_id = family.job_id AND member.family_key = family.family_key
       AND member.disposition = 'candidate'
);
