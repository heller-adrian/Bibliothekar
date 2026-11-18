CREATE TABLE legacy_adoption_flat_review_copies (
    job_id TEXT NOT NULL,
    family_key TEXT NOT NULL,
    source_root TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    workspace_identity TEXT NOT NULL,
    stage_name TEXT NOT NULL,
    members_json TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('publishing', 'copied')),
    PRIMARY KEY (job_id, family_key)
) WITHOUT ROWID;

CREATE INDEX legacy_adoption_flat_review_fingerprint
    ON legacy_adoption_flat_review_copies (fingerprint, workspace_identity, state);

ALTER TABLE legacy_adoption_review_batch ADD COLUMN bytes_total INTEGER NOT NULL DEFAULT 0;
ALTER TABLE legacy_adoption_review_batch ADD COLUMN bytes_verified INTEGER NOT NULL DEFAULT 0;

UPDATE legacy_adoption_review_batch AS batch
   SET bytes_total = (
       SELECT coalesce(sum(size_bytes), 0) FROM legacy_adoption_inventory member
        WHERE member.job_id = batch.job_id AND member.family_key = batch.family_key
   );
UPDATE legacy_adoption_review_batch SET bytes_verified = bytes_total WHERE state = 'copied';
