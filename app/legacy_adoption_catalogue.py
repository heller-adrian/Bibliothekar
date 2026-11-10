"""Use the regular catalogue schema to project verified legacy media."""
from datetime import datetime, timezone
import hashlib
from itertools import groupby
import json
from pathlib import Path

from app import __version__
from app.archive_locations import record_family_anchor, record_verified_file_location
from app.database import database_connection
from app.event_access import event_file_rows, register_source_jobs
from app.event_document import EVENT_DOCUMENT_FILENAME, build_event_document_from_db
from app.event_inventory import IGNORED_EVENT_FILES, event_root_relative
from app.event_leaf_layouts import save_leaf_layouts
from app.event_timeline import replace_event_segments
from app.legacy_adoption_inventory import _job
from app.legacy_adoption_paths import AdoptionError
from app.legacy_adoption_verify import _catalogue_unchanged, _plan
from app.metadata import summarize_file_metadata


def catalogue_job_id(plan):
    return "LEGACY_" + plan["id"].upper()


def adoption_source_signature(plan):
    return "legacy-adoption:" + plan["id"]


def _inventory_rows(connection, plan, job):
    return connection.execute(
        """SELECT move.*, inventory.family_key, inventory.size_bytes, inventory.metadata_json
             FROM legacy_adoption_moves move
             JOIN legacy_adoption_inventory inventory ON inventory.job_id = ?
                  AND inventory.relative_path = move.relative_path
            WHERE move.plan_id = ? AND move.target_path IS NOT NULL
            ORDER BY inventory.family_key, move.relative_path""",
        (job["id"], plan["id"]),
    )


def _store_job(connection, library, job, plan, now):
    count, size = connection.execute(
        """SELECT count(*), coalesce(sum(inventory.size_bytes), 0)
             FROM legacy_adoption_moves move JOIN legacy_adoption_inventory inventory
             ON inventory.job_id = ? AND inventory.relative_path = move.relative_path
            WHERE move.plan_id = ? AND move.target_path IS NOT NULL""",
        (job["id"], plan["id"]),
    ).fetchone()
    job_id = catalogue_job_id(plan)
    connection.execute(
        """INSERT INTO jobs (
               id, kind, operation, trigger_type, state, stage, source_path, source_signature,
               archive_target_path, source_volume_label, file_count, total_size_bytes,
               created_at, started_at, updated_at, finished_at, result_json
           ) VALUES (?, 'archive_verification', 'legacy_adoption', 'manual', 'completed', 'completed',
                     ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (job_id, job["source_root"], adoption_source_signature(plan), str(library.archive_root),
         Path(job["source_root"]).name, count, size, now, now, now, now,
         json.dumps({"legacy_adoption_id": job["id"], "plan_id": plan["id"]})),
    )
    return job_id


def _store_event(connection, job_id, event, now):
    event_id = event["id"]
    if event["existing"]:
        connection.execute(
            "UPDATE events SET revision = revision + 1, updated_at = ?, edited_at = ? WHERE id = ?",
            (now, now, event_id),
        )
    else:
        connection.execute(
            """INSERT INTO events (
                   id, job_id, event_level, name, start_datetime, end_datetime, folder_name,
                   status, created_at, updated_at, event_kind, preserve_day_folders,
                   applied_at, archived_at, timeline_model, time_model_version, folder_naming_json
               ) VALUES (?, ?, 'parent', ?, ?, ?, ?, 'archived', ?, ?, ?, ?, ?, ?, ?, 2, ?)""",
            (event_id, job_id, event["name"], event["start_datetime"], event["end_datetime"],
             event["folder_name"], now, now, event["event_kind"], int(event["preserve_day_folders"]),
             now, now, "segments" if event["event_kind"] == "no_event" else "continuous",
             json.dumps(event["naming"])),
        )
        layout = event["folder_layout"]
        connection.execute(
            """INSERT INTO event_folder_layouts (
                   event_id, structure_enabled, input_path, layout_json, revision, created_at, updated_at
               ) VALUES (?, ?, ?, ?, 1, ?, ?)""",
            (event_id, int(layout["structure_enabled"]), layout["input_path"],
             json.dumps(layout["layout"]), now, now),
        )
        if event["children"]:
            # store_subevents allocates child IDs for normal authoring. The
            # manual plan must keep its previously published identities.
            connection.executemany(
                """INSERT INTO events (
                       id, job_id, parent_event_id, event_level, name, start_datetime, end_datetime,
                       uses_time_range, folder_name, status, created_at, updated_at,
                       preserve_day_folders, applied_at, archived_at, time_model_version
                   ) VALUES (?, ?, ?, 'child', ?, ?, ?, 1, ?, 'archived', ?, ?, ?, ?, ?, 2)""",
                ((child["id"], job_id, event_id, child["name"], child["start_datetime"],
                  child["end_datetime"], child["folder_name"], now, now,
                  int(event["preserve_day_folders"]), now, now) for child in event["children"]),
            )
        save_leaf_layouts(connection, event_id, list(event["leaf_layouts"].values()), now=now)
        if event["segments"]:
            replace_event_segments(connection, event_id=event_id, job_id=job_id, segments=event["segments"], now=now)
    register_source_jobs(connection, event_id, [job_id], created_at=now)


def _store_file(connection, job_id, family_id, row, record, capture, manually_reviewed, now):
    confidence = "high" if manually_reviewed else record["capture_time_confidence"]
    source = "manual_legacy_adoption" if manually_reviewed else record["selected_capture_source"]
    selected_time = capture if manually_reviewed else record["selected_capture_time"]
    result = connection.execute(
        """INSERT INTO files (
               job_id, family_id, original_relative_path, current_relative_path, current_root_kind,
               original_filename, extension, media_type, size_bytes, source_size_bytes,
               sha256_original, sha256_current, selected_capture_time, selected_capture_source,
               capture_time_confidence, review_status, created_at, updated_at
           ) VALUES (?, ?, ?, ?, 'camera_archive', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (job_id, family_id, row["relative_path"], row["target_path"], record["filename"], record["extension"],
         record["media_type"], row["size_bytes"], row["size_bytes"], row["sha256"], row["sha256"],
         selected_time, source, confidence, "confirmed" if manually_reviewed else "not_required", now, now),
    )
    file_id = result.lastrowid
    connection.executemany(
        """INSERT INTO metadata_candidates (
               file_id, metadata_group, tag_name, raw_value, normalized_datetime, priority,
               confidence, is_selected, conflicts_with_selected
           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        ((file_id, item["metadata_group"], item["tag_name"], item["raw_value"], item["normalized_datetime"],
          item["priority"], item["confidence"], int(item["is_selected"] and not manually_reviewed),
          int(item["conflicts_with_selected"])) for item in record["metadata_candidates"]),
    )
    return file_id


def _existing_inventory(connection, plan_id, event, now):
    if not event["existing"]:
        return
    prefix = str(event_root_relative(event)) + "/"
    baseline = {
        row["relative_path"]: dict(row) for row in connection.execute(
            """SELECT relative_path, size_bytes, sha256 FROM legacy_adoption_baseline
                WHERE plan_id = ? AND substr(relative_path, 1, ?) = ?""",
            (plan_id, len(prefix), prefix),
        )
        if Path(row["relative_path"]).name not in IGNORED_EVENT_FILES
    }
    previous = {row["relative_path"]: dict(row) for row in connection.execute(
        """SELECT * FROM event_inventory_files WHERE event_id = ? AND root_kind = 'camera_archive'""",
        (event["id"],),
    )}
    for row in event_file_rows(connection, event["id"]):
        path = row["current_relative_path"]
        if not path or path not in baseline or baseline[path]["sha256"] != (row["sha256_current"] or row["sha256_original"]):
            raise AdoptionError("Ein bekanntes Archivoriginal weicht vom Katalog ab. "
                                "Prüfe zuerst das bestehende Ereignis: " + str(path))
        previous[path] = {**previous.get(path, {}), **{
            "known_file_id": row["id"], "family_id": row["family_id"], "asset_kind": "camera_original",
            "selected_capture_time": row["selected_capture_time"],
            "selected_capture_source": row["selected_capture_source"],
            "capture_time_confidence": row["capture_time_confidence"],
        }}
    connection.execute(
        "DELETE FROM event_inventory_files WHERE event_id = ? AND root_kind = 'camera_archive'", (event["id"],),
    )
    for path, proof in baseline.items():
        entry = previous.get(path, {})
        _inventory_file(connection, event["id"], event["job_id"], path, path[len(prefix):], proof, entry, now)


def _inventory_file(connection, event_id, anchor, path, relative, proof, attributes, now):
    filename = Path(path).name
    connection.execute(
        """INSERT INTO event_inventory_files (
               event_id, job_id, root_kind, relative_path, event_relative_path, filename,
               extension, asset_kind, known_file_id, family_id, source_file_id, size_bytes, sha256,
               selected_capture_time, selected_capture_source, capture_time_confidence, scanned_at
           ) VALUES (?, ?, 'camera_archive', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (event_id, anchor, path, relative, filename, Path(filename).suffix.lower(),
         attributes.get("asset_kind", "other"), attributes.get("known_file_id"),
         attributes.get("family_id"), attributes.get("source_file_id"), proof["size_bytes"], proof["sha256"],
         attributes.get("selected_capture_time"), attributes.get("selected_capture_source"),
         attributes.get("capture_time_confidence", "missing"), now),
    )


def _store_verified_event(connection, plan, library, event, anchor, now):
    event_id = event["id"]
    verification = plan["id"] + "-" + event_id
    count, size = connection.execute(
        """SELECT count(*), coalesce(sum(size_bytes), 0) FROM event_inventory_files
           WHERE event_id = ? AND root_kind = 'camera_archive'
             AND (known_file_id IS NOT NULL OR asset_kind IN ('xmp','export','derived_media'))""", (event_id,),
    ).fetchone()
    connection.execute(
        """INSERT INTO event_archive_verifications (
               id, job_id, event_id, status, archive_root, file_count, verified_file_count,
               total_size_bytes, verified_size_bytes, created_at, updated_at, completed_at
           ) VALUES (?, ?, ?, 'verified', ?, ?, ?, ?, ?, ?, ?, ?)""",
        (verification, anchor, event_id, str(library.archive_root), count, count, size, size, now, now, now),
    )
    connection.execute(
        """INSERT INTO event_archive_verification_files (
               verification_id, file_id, expected_relative_path, expected_size_bytes, expected_sha256,
               status, actual_size_bytes, actual_sha256
           )
           SELECT ?, known_file_id, relative_path, size_bytes, sha256, 'verified', size_bytes, sha256
             FROM event_inventory_files WHERE event_id = ? AND root_kind = 'camera_archive'
               AND known_file_id IS NOT NULL""",
        (verification, event_id),
    )
    connection.execute(
        """INSERT INTO event_archive_verification_assets (
               verification_id, source_event_relative_path, expected_relative_path, asset_kind,
               expected_size_bytes, expected_sha256, status, actual_size_bytes, actual_sha256
           )
           SELECT ?, event_relative_path, relative_path, asset_kind, size_bytes, sha256,
                  'verified', size_bytes, sha256
             FROM event_inventory_files WHERE event_id = ? AND root_kind = 'camera_archive'
               AND known_file_id IS NULL AND asset_kind IN ('xmp','export','derived_media')""",
        (verification, event_id),
    )


def write_catalogue(connection, library, job, plan, events, now):
    """Write one coherent catalogue transaction (or an uncommitted projection)."""
    job_id = _store_job(connection, library, job, plan, now)
    by_id = {event["id"]: event for event in events}
    prefixes = {event["id"]: event_root_relative(event) for event in events}
    overrides = json.loads(plan["draft_json"]).get("capture_overrides", {})
    for event in events:
        _existing_inventory(connection, plan["id"], event, now)
        _store_event(connection, job_id, event, now)

    source = Path(job["source_root"])
    for key, group in groupby(_inventory_rows(connection, plan, job), key=lambda row: row["family_key"]):
        rows = list(group)
        first = rows[0]
        capture = first["capture_time"]
        manually_reviewed = key in overrides
        records = [json.loads(row["metadata_json"]) for row in rows]
        family = summarize_file_metadata(source, records)["families"][0]
        family_id = connection.execute(
            """INSERT INTO file_families (
                   job_id, family_key, original_stem, status, selected_capture_time, capture_time_confidence
               ) VALUES (?, ?, ?, 'complete', ?, ?)""",
            (job_id, key, Path(key).name, capture,
             "high" if manually_reviewed else family["capture_time_confidence"]),
        ).lastrowid
        assigned = first["assigned_event_id"]
        parent = first["parent_event_id"]
        connection.execute(
            """INSERT INTO event_assignments (event_id, family_id, assignment_source, created_at)
               VALUES (?, ?, ?, ?)""", (assigned, family_id, "manual" if manually_reviewed else "date_range", now),
        )
        anchor_job = by_id[parent].get("job_id", job_id)
        for row, record in zip(rows, records):
            file_id = _store_file(connection, job_id, family_id, row, record, capture, manually_reviewed, now)
            path = row["target_path"]
            relative = Path(path).relative_to(prefixes[parent]).as_posix()
            _inventory_file(connection, parent, anchor_job, path, relative, row, {
                "asset_kind": "camera_original", "known_file_id": file_id, "family_id": family_id,
                "selected_capture_time": capture if manually_reviewed else record["selected_capture_time"],
                "selected_capture_source": "manual_legacy_adoption" if manually_reviewed else record["selected_capture_source"],
                "capture_time_confidence": "high" if manually_reviewed else record["capture_time_confidence"],
            }, now)
            record_verified_file_location(connection, parent, family_id, file_id, path, now)
        record_family_anchor(connection, parent, family_id, (row["target_path"] for row in rows), now)
    for event in events:
        _store_verified_event(connection, plan, library, event, event.get("job_id", job_id), now)


def catalogue_documents(connection, library, plan, events, now):
    for event in events:
        payload = build_event_document_from_db(
            library.database_path, library.workspace_root, event.get("job_id", catalogue_job_id(plan)),
            event["id"], include_archived=True, transaction_connection=connection,
        )
        if payload is None:
            raise AdoptionError("Das Ereignisdokument konnte nicht erzeugt werden.")
        payload["generated_at"] = now
        payload["source_app_version"] = __version__
        content = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
        yield str(event_root_relative(event) / EVENT_DOCUMENT_FILENAME), content, hashlib.sha256(content).hexdigest()


def prepare_documents(library, job_id: str) -> list[dict]:
    now = datetime.now(timezone.utc).isoformat()
    with database_connection(library.database_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        job = _job(connection, library.library_id, job_id)
        plan = _plan(connection, job_id)
        if plan["state"] not in {"prepared", "media_verified", "verified"} or connection.execute(
            "SELECT 1 FROM legacy_adoption_execution WHERE plan_id = ?", (plan["id"],),
        ).fetchone():
            raise AdoptionError("Die Ereignisdokumente können in diesem Zustand nicht vorbereitet werden.")
        events = json.loads(plan["events_json"])
        _catalogue_unchanged(connection, job_id, events)
        connection.execute("SAVEPOINT legacy_event_documents")
        try:
            write_catalogue(connection, library, job, plan, events, now)
            documents = list(catalogue_documents(connection, library, plan, events, now))
        finally:
            connection.execute("ROLLBACK TO legacy_event_documents")
            connection.execute("RELEASE legacy_event_documents")
        connection.execute("DELETE FROM legacy_adoption_documents WHERE plan_id = ?", (plan["id"],))
        connection.executemany(
            "INSERT INTO legacy_adoption_documents VALUES (?, ?, ?, ?)",
            ((plan["id"], path, content, digest) for path, content, digest in documents),
        )
        connection.execute(
            """UPDATE legacy_adoption_plans SET documents_at = ?,
               state = CASE WHEN state = 'verified' THEN 'media_verified' ELSE state END WHERE id = ?""",
            (now, plan["id"]),
        )
    return [{"relative_path": path, "size_bytes": len(content), "sha256": digest}
            for path, content, digest in documents]
