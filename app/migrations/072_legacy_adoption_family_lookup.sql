-- Keep the membership probe bounded to one family. On a large inventory
-- SQLite can otherwise scan the job's path-ordered primary key per family.
DROP VIEW legacy_adoption_candidate_families;
CREATE VIEW legacy_adoption_candidate_families AS
SELECT family.*
FROM legacy_adoption_families AS family
WHERE EXISTS (
    SELECT 1 FROM legacy_adoption_inventory AS member INDEXED BY legacy_adoption_inventory_family
    WHERE member.job_id = family.job_id AND member.family_key = family.family_key
      AND member.disposition = 'candidate'
    LIMIT 1
);
