"""Join separately stored RAW and JPEG files with corroborated capture identity."""
from collections import defaultdict
from datetime import datetime, timezone
from itertools import groupby
import json
from pathlib import PurePosixPath
import re


def capture_identity(metadata):
    value = str(metadata.get("EXIF:ExifIFD:ImageUniqueID") or "").strip().lower()
    if not re.fullmatch(r"[0-9a-f]{32}", value) or len(set(value)) == 1:
        return None
    serial = str(metadata.get("EXIF:ExifIFD:BodySerialNumber") or "").strip()
    return {"id": value, "serial": serial}


def _capture_key(key, record):
    identity = record.get("capture_identity")
    make = str(record.get("camera_make") or "").strip().casefold()
    model = str(record.get("camera_model") or "").strip().casefold()
    if not identity or not make or not model:
        return None
    stem = PurePosixPath(key).name
    return identity["id"], make, model, stem.casefold(), len(stem)


def _matching_times(jpeg, raw):
    if any(record.get("review_required") or not record.get("selected_capture_time") for record in (jpeg, raw)):
        return False
    first, second = (datetime.fromisoformat(record["selected_capture_time"]).astimezone(timezone.utc)
                     for record in (jpeg, raw))
    if first.replace(microsecond=0) != second.replace(microsecond=0):
        return False
    return not (first.microsecond and second.microsecond) or first == second


def join_split_families(connection, job_id, draft, cancel):
    protected = set().union(*(draft.get(key, ()) for key in (
        "capture_overrides", "exclude_families", "target_stems", "metadata_review_pending",
    )))
    protected.update(row[0] for row in connection.execute(
        "SELECT family_key FROM legacy_adoption_review_copies WHERE job_id = ?", (job_id,),
    ))
    seen = defaultdict(list)
    rows = connection.execute(
        """SELECT * FROM legacy_adoption_inventory WHERE job_id = ? AND family_key IS NOT NULL
           ORDER BY family_key, relative_path""", (job_id,),
    )
    for key, group in groupby(rows, key=lambda row: row["family_key"]):
        cancel()
        members = [(row, json.loads(row["metadata_json"] or "{}")) for row in group]
        primary = [record for _, record in members if record.get("media_type") in {"raw", "jpeg"}]
        usable = len(primary) == 1 and all(
            row["disposition"] == "candidate" and row["sha256"] and not row["error"]
            and not record.get("metadata_error")
            and record.get("media_type") in {"raw", "jpeg", "xmp"}
            for row, record in members
        )
        for record in primary:
            if proof := _capture_key(key, record):
                seen[proof].append((key, record, members if usable else None))

    for pair in seen.values():
        if len(pair) != 2 or any(members is None for _, _, members in pair):
            continue
        pair.sort(key=lambda item: item[1]["media_type"])
        (jpeg_key, jpeg, jpeg_files), (raw_key, raw, raw_files) = pair
        if jpeg["media_type"] != "jpeg" or raw["media_type"] != "raw" or jpeg_key == raw_key:
            continue
        serials = {record["capture_identity"]["serial"] for record in (jpeg, raw)} - {""}
        if len(serials) > 1 or not _matching_times(jpeg, raw):
            continue
        combined = raw_files + jpeg_files
        stem_length = len(PurePosixPath(raw_key).name)
        endings = {PurePosixPath(row["relative_path"]).name[stem_length:].casefold() for row, _ in combined}
        if len(endings) != len(combined):
            continue
        if {jpeg_key, raw_key} & protected and not all(
            record.get("adoption_family") == raw_key for _, record in combined
        ):
            continue
        connection.executemany(
            """UPDATE legacy_adoption_inventory SET family_key = ?, metadata_json = ?
               WHERE job_id = ? AND relative_path = ?""",
            [(raw_key, json.dumps({**record, "adoption_family": raw_key}, ensure_ascii=False),
              job_id, row["relative_path"]) for row, record in combined],
        )
