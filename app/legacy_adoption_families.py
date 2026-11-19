"""Bind shared capture matching to the adoption inventory and its draft."""
from itertools import groupby
import json

from app.media_family_identity import split_family_groups
from app.metadata import family_member_ending


def join_split_families(connection, job_id, draft, cancel):
    protected = set().union(*(draft.get(key, ()) for key in (
        "capture_overrides", "exclude_families", "target_stems", "metadata_review_pending", "metadata_review_applied",
    )))
    protected.update(row[0] for row in connection.execute(
        "SELECT family_key FROM legacy_adoption_review_copies WHERE job_id = ?", (job_id,),
    ))
    if protected:
        # Unchanged members of a saved RC1 family keep their key even when
        # stronger evidence now finds another matching file for that capture.
        connection.execute(
            """UPDATE legacy_adoption_inventory SET family_key = json_extract(metadata_json, '$.adoption_family')
                WHERE job_id = ? AND json_extract(metadata_json, '$.adoption_family') IN
                      (SELECT value FROM json_each(?))""",
            (job_id, json.dumps(sorted(protected))),
        )
    rows = connection.execute(
        """SELECT relative_path, family_key, disposition, sha256, error, metadata_json
           FROM legacy_adoption_inventory WHERE job_id = ? AND family_key IS NOT NULL
           ORDER BY family_key, relative_path""", (job_id,),
    )

    evidence_fields = (
        "media_type", "extension", "relative_path", "capture_identity", "camera_make", "camera_model",
        "selected_capture_time", "selected_capture_source", "review_required", "metadata_error",
        "capture_settings",
    )

    def groups():
        for key, group in groupby(rows, key=lambda row: row["family_key"]):
            entries = list(group)
            decoded = (json.loads(row["metadata_json"] or "{}") for row in entries)
            members = [{name: item[name] for name in evidence_fields if name in item} for item in decoded]
            usable = key not in protected and all(row["disposition"] == "candidate" and row["sha256"] and not row["error"]
                         and not item.get("metadata_error") for row, item in zip(entries, members, strict=True))
            yield key, members, usable

    for anchor, _, members in split_family_groups(groups(), ending=family_member_ending, cancel=cancel):
        connection.executemany(
            """UPDATE legacy_adoption_inventory
                  SET family_key = ?1, metadata_json = json_set(metadata_json, '$.family_key', ?1, '$.adoption_family', ?1)
                WHERE job_id = ?2 AND relative_path = ?3""",
            [(anchor, job_id, item["relative_path"]) for item in members],
        )
