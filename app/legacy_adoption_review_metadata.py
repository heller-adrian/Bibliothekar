"""Stage an explicit metadata choice, then apply it to the adoption draft."""
from collections import defaultdict
from contextlib import ExitStack
from datetime import datetime
from itertools import groupby
import json

from app.database import database_connection
from app.legacy_adoption_inventory import _job, inventory_fingerprint
from app.legacy_adoption_paths import AdoptionError, bound_file, relative_parent
from app.legacy_adoption_plan import _roots, preview_draft


DETECTED = "@detected"


def _captured_time(value):
    try:
        capture = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    if capture.year > 1904 and capture.tzinfo is not None and "T" in value:
        return capture.isoformat()
    return None


def capture_choices(members):
    """Use exact inventoried tags and refuse conflicting values within a family."""
    if any(not row["identity"] or not row["sha256"] or row["error"] for row in members):
        return {}
    by_source = defaultdict(list)
    for row in members:
        metadata = json.loads(row["metadata_json"] or "{}")
        if metadata.get("metadata_error"):
            return {}
        # Sidecars can provide XMP candidates, but their file-system dates do
        # not describe the media file and must not be used for a family.
        sidecar = metadata.get("media_type") == "xmp"
        detected = metadata.get("selected_capture_source")
        for candidate in metadata.get("metadata_candidates", []):
            tag = candidate["tag_name"]
            if sidecar and tag.startswith("File:"):
                continue
            value = _captured_time(candidate["normalized_datetime"])
            evidence = {"path": row["relative_path"], "tag": tag, "raw": candidate["raw_value"], "time": value}
            by_source[tag].append(evidence)
            if tag == detected and value and value == metadata.get("selected_capture_time"):
                by_source[DETECTED].append(evidence)
    options = {}
    for source, evidence in sorted(by_source.items()):
        times = {item["time"] for item in evidence}
        if len(times) == 1 and None not in times:
            options[source] = {"source": source, "time": next(iter(times)), "evidence": evidence}
    return options


def _decision_rows(connection, job, keys):
    rows = connection.execute(
        """SELECT item.* FROM json_each(?) AS wanted
               CROSS JOIN legacy_adoption_families family
                    ON family.job_id = ? AND family.family_key = wanted.value
               CROSS JOIN legacy_adoption_inventory item INDEXED BY legacy_adoption_inventory_family
                    ON item.job_id = family.job_id AND item.family_key = family.family_key
               WHERE family.review_required AND NOT EXISTS (
                   SELECT 1 FROM legacy_adoption_review_copies copy
                   WHERE copy.job_id = family.job_id AND copy.family_key = family.family_key
               ) ORDER BY item.family_key, item.relative_path""",
        (json.dumps(sorted(set(keys)), ensure_ascii=True), job["id"]),
    )
    for key, members in groupby(rows, key=lambda row: row["family_key"]):
        yield key, list(members)


def _editable(connection, library, job_id, revision):
    job = _job(connection, library.library_id, job_id)
    if job["state"] != "inventoried" or connection.execute(
        "SELECT 1 FROM legacy_adoption_plans WHERE job_id = ?", (job_id,),
    ).fetchone():
        raise AdoptionError("Der Entwurf ist in diesem Zustand nicht bearbeitbar.")
    if job["draft_revision"] != revision:
        raise AdoptionError("Der Entwurf wurde in einer anderen Sitzung geändert. Lade ihn erneut.")
    return job, json.loads(job["draft_json"])


def _save(connection, job, draft):
    revision = job["draft_revision"] + 1
    connection.execute("UPDATE legacy_adoption_jobs SET draft_json = ?, draft_revision = ? WHERE id = ?",
                       (json.dumps(draft), revision, job["id"]))
    return revision


def metadata_sources(library, job_id, *, revision, keys):
    with database_connection(library.database_path) as connection:
        connection.execute("BEGIN")
        job, draft = _editable(connection, library, job_id, revision)
        pending = draft.get("metadata_review_pending", {})
        overrides = draft.get("capture_overrides", {})
        counts = defaultdict(int)
        for key, members in _decision_rows(connection, job, keys):
            if key not in pending and key not in overrides:
                for source in capture_choices(members):
                    counts[source] += 1
        return {"selected": len(set(keys)), "sources": dict(counts)}


def stage_metadata(library, job_id, *, revision, keys, source, individual):
    with database_connection(library.database_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        job, draft = _editable(connection, library, job_id, revision)
        pending = draft.setdefault("metadata_review_pending", {})
        overrides = draft.get("capture_overrides", {})
        if source is None:
            pending.pop(keys[0], None)
            return {"revision": _save(connection, job, draft), "staged": 0, "rejected": {}}
        rejected = dict.fromkeys(keys, "unavailable")
        staged = 0
        for key, members in _decision_rows(connection, job, keys):
            if key in overrides or (key in pending and not individual):
                rejected[key] = "already_selected"
                continue
            choice = capture_choices(members).get(source)
            if choice is None:
                rejected[key] = "source_unavailable"
                continue
            pending[key] = {**choice, "fingerprint": inventory_fingerprint(members)}
            del rejected[key]
            staged += 1
        return {"revision": _save(connection, job, draft) if staged else revision,
                "staged": staged, "rejected": rejected}


def apply_metadata(library, job_id, *, revision, allow_existing):
    with database_connection(library.database_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        job, draft = _editable(connection, library, job_id, revision)
        pending = draft.get("metadata_review_pending", {})
        if not pending:
            return {"revision": revision, "applied": 0, "rejected": {}}
        overrides = draft.setdefault("capture_overrides", {})
        applied = draft.setdefault("metadata_review_applied", {})
        rejected = dict.fromkeys(pending, "unavailable")
        verified = {}
        with ExitStack() as stack:
            source, _ = _roots(stack, library, job)
            for key, members in _decision_rows(connection, job, pending):
                decision = pending[key]
                current = capture_choices(members).get(decision["source"])
                if current is None or decision != {**current, "fingerprint": inventory_fingerprint(members)}:
                    rejected[key] = "source_changed"
                    continue
                try:
                    for member in members:
                        with relative_parent(source, member["relative_path"]) as (parent, name):
                            with bound_file(parent, name, tuple(json.loads(member["identity"]))):
                                pass
                except (AdoptionError, OSError):
                    rejected[key] = "source_changed"
                    continue
                verified[key] = decision
                del rejected[key]
        if verified:
            for key, decision in verified.items():
                overrides[key] = decision["time"]
                applied[key] = pending.pop(key)
            draft["exclude_families"] = [key for key in draft.get("exclude_families", []) if key not in verified]
            if not preview_draft(library, job_id, draft, allow_existing=allow_existing)["valid"]:
                raise AdoptionError("Zeitkonflikt: Korrigiere die markierte Planung. Gespeicherte Entwürfe bleiben erhalten.")
        return {"revision": _save(connection, job, draft) if verified else revision,
                "applied": len(verified), "rejected": rejected}
