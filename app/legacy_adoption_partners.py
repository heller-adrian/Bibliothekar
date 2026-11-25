"""Bind explicitly approved sidecar partnerships to the inventoried files."""
from collections import defaultdict
from datetime import datetime, timezone
import json
from pathlib import PurePosixPath

from app.filename_collisions import has_capture_fraction
from app.legacy_adoption_paths import AdoptionError
from app.legacy_adoption_xmp_plan import RAW_EXTENSIONS
from app.media_family_identity import IDENTITY_VERSION


def compatible(first, second):
    left, right = (json.loads(row["metadata_json"] or "{}") for row in (first, second))
    a, b = ((metadata.get("capture_identity") or {}) for metadata in (left, right))
    if any(identity.get("conflict") for identity in (a, b)) or any(
        a.get(tag) and b.get(tag) and a[tag] != b[tag] for tag in ("id", "serial")
    ):
        return False

    def shutter_time(metadata):
        value = metadata.get("selected_capture_time")
        if (value and not metadata.get("review_required")
                and (metadata.get("selected_capture_source") or "").endswith(":DateTimeOriginal")):
            return value

    times = tuple(shutter_time(item) for item in (left, right))
    if not all(times):
        return True
    t1, t2 = (datetime.fromisoformat(value).astimezone(timezone.utc) for value in times)
    if all(has_capture_fraction(value) for value in times):
        return t1 == t2
    return t1.replace(microsecond=0) == t2.replace(microsecond=0)


def proof(sidecar, master, family):
    """Return a valid option and the full membership evidence behind it."""
    metadata = json.loads(sidecar["metadata_json"] or "{}")
    raw = PurePosixPath(master["relative_path"])
    hint = (metadata.get("capture_identity") or {}).get("sidecar_raw")
    if (raw.suffix.casefold() not in RAW_EXTENSIONS or metadata.get("metadata_error")
            or sidecar["review_copy"] or sidecar["disposition"] != "candidate"
            or (hint and raw.name.casefold() != hint)
            or any(row["disposition"] != "candidate" or row["review_copy"]
                   or not row["sha256"] or not compatible(sidecar, row) for row in family)):
        return None

    def binding(row):
        return [row["relative_path"], row["sha256"], json.loads(row["identity"])]

    if not sidecar["sha256"]:
        return None
    return {"xmp": sidecar["relative_path"], "raw": master["relative_path"],
            "files": [row["relative_path"] for row in family],
            "evidence": [binding(sidecar), *(binding(row) for row in family)],
            "version": IDENTITY_VERSION}


def inventory_members(connection, job_id):
    return connection.execute(
        """SELECT inventory.*, families.capture_time, families.review_required, copy.state AS review_copy
             FROM legacy_adoption_inventory inventory
             JOIN legacy_adoption_families families USING (job_id, family_key)
             LEFT JOIN legacy_adoption_review_copies copy USING (job_id, family_key)
            WHERE inventory.job_id = ? ORDER BY family_key, relative_path""",
        (job_id,),
    )


def resolve(rows, draft):
    """Project accepted stand-alone sidecars into their selected family."""
    decisions = draft.get("file_partners") or {}
    if not decisions:
        return rows, {}
    originals, families = {}, defaultdict(list)
    for row in rows:
        originals[row["relative_path"]] = row
        families[row["family_key"]].append(row)
    merged = defaultdict(list)
    masters = {}
    excluded = draft.get("file_exclusions") or {}
    unavailable = set(draft.get("exclude_families") or ())
    for xmp, decision in decisions.items():
        sidecar, master = originals.get(xmp), originals.get(decision["raw"])
        if sidecar is not None and master is not None:
            old, new = sidecar["family_key"], master["family_key"]
            if (old != new and len(families[old]) == 1
                    and old not in unavailable and new not in unavailable
                    and old not in (draft.get("capture_overrides") or {})
                    and old not in (draft.get("target_stems") or {})
                    and not any(row["relative_path"] in excluded for row in (sidecar, *families[new]))
                    and proof(sidecar, master, families[new]) == decision
                    and all(compatible(sidecar, record) for record in merged[new])):
                merged[new].append(sidecar)
                masters[xmp] = master
                continue
        raise AdoptionError("Eine bestätigte Dateipartnerschaft hat sich geändert. Prüfe oder widerrufe sie: " + xmp)
    result = []
    for key, members in families.items():
        result.extend(row for row in members if row["relative_path"] not in masters)
        result.extend({**sidecar, "family_key": key, "confirmed_partner": masters[sidecar["relative_path"]]["relative_path"]}
                      for sidecar in merged.get(key, ()))
    return result, masters


def reconcile_after_scan(connection, job_id, draft):
    """Keep only re-inventoried bindings, including unambiguous renames."""
    decisions = draft.get("file_partners") or {}
    if not decisions:
        return 0, 0

    def identifier(digest, stamp):
        return digest, *stamp[:3]  # kernel device, inode and file size

    rows = list(inventory_members(connection, job_id))
    by_path = {row["relative_path"]: row for row in rows if row["sha256"] and row["identity"]}
    by_identity, families = defaultdict(list), defaultdict(list)
    for row in rows:
        families[row["family_key"]].append(row)
    for row in by_path.values():
        by_identity[identifier(row["sha256"], json.loads(row["identity"]))].append(row)

    def observed(binding):
        old_path, digest, stamp = binding
        candidates = by_identity.get(identifier(digest, stamp), ())
        # If multiple aliases exist, only a pre-existing concrete path may
        # keep its binding. A disappeared path needs a unique replacement.
        return next((row for row in candidates if row["relative_path"] == old_path),
                    candidates[0] if len(candidates) == 1 else None)

    valid, linked = {}, defaultdict(list)
    relocated = 0
    excluded = draft.get("file_exclusions") or {}
    unavailable = set(draft.get("exclude_families") or ())
    for decision in decisions.values():
        if decision["version"] != IDENTITY_VERSION:
            continue
        matched = {item[0]: observed(item) for item in decision["evidence"]}
        if any(row is None for row in matched.values()):
            continue
        sidecar, master = matched[decision["xmp"]], matched[decision["raw"]]
        old, new = sidecar["family_key"], master["family_key"]
        xmp = sidecar["relative_path"]
        if (old == new or len(families[old]) != 1 or old in unavailable or new in unavailable
                or old in (draft.get("capture_overrides") or {}) or old in (draft.get("target_stems") or {})
                or xmp in valid or any(row["relative_path"] in excluded for row in matched.values())
                or {row["relative_path"] for row in families[new]}
                != {matched[path]["relative_path"] for path in decision["files"]}
                or not all(compatible(sidecar, prior) for prior in linked[new])):
            continue
        replacement = proof(sidecar, master, families[new])
        if replacement is None:
            continue
        valid[xmp] = replacement
        linked[new].append(sidecar)
        relocated += any(old_path != row["relative_path"] for old_path, row in matched.items())
    draft["file_partners"] = valid
    return len(decisions) - len(valid), relocated
