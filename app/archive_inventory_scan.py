"""A library's explicit, read-only inventory job and its findings."""
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path, PurePosixPath
import time
from uuid import uuid4

from app.database import database_connection
from app.event_inventory import IGNORED_EVENT_FILES
from app.external_changes import record_notice, resolve_notice_key
from app.legacy_adoption_paths import (
    AdoptionError, bound_directory, bound_file, bound_sha256, file_identity, walk_bound_files,
)
from app.root_operations import RootOperationBusy, protect, validate_active_roots

_KEY = "archive_inventory_scan"
_ACTIVE = {"queued", "running", "interrupted"}
_KINDS = ("added", "missing", "moved", "changed", "unassigned")
_NOTICE_KIND = "archive_inventory_scan"


def _now():
    return datetime.now(timezone.utc).isoformat()


def _get(connection):
    row = connection.execute("SELECT value_json FROM app_settings WHERE setting_key=?", (_KEY,)).fetchone()
    return json.loads(row[0]) if row else {"status": "idle", "last_success_at": None}


def _save(connection, state):
    connection.execute(
        """INSERT INTO app_settings(setting_key,value_json,updated_at) VALUES (?,?,?)
           ON CONFLICT(setting_key) DO UPDATE SET value_json=excluded.value_json,updated_at=excluded.updated_at""",
        (_KEY, json.dumps(state, sort_keys=True), _now()),
    )


def status(database_path):
    with database_connection(database_path) as connection:
        return _get(connection)


def enqueue(database_path):
    with database_connection(database_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        previous = _get(connection)
        if previous["status"] in _ACTIVE:
            return previous
        state = {
            "id": uuid4().hex, "status": "queued", "phase": "discovery", "attempt": 0,
            "checked": 0, "total": None, "percent": None, "eta_seconds": None,
            "last_success_at": previous["last_success_at"], "result": previous.get("result"),
        }
        _save(connection, state)
        return state


def _catalogue(connection, archive_root):
    from app.event_access import event_file_rows
    from app.event_inventory import event_root_relative

    events = {}
    expected = defaultdict(set)
    for row in connection.execute("""
        SELECT e.*, latest.id AS proof_id
        FROM events e
        LEFT JOIN event_archive_verifications latest ON latest.id=(
            SELECT id FROM event_archive_verifications
            WHERE event_id=e.id AND job_id=e.job_id AND status='verified' AND archive_root=?
            ORDER BY created_at DESC,id DESC LIMIT 1
        )
        WHERE e.parent_event_id IS NULL AND COALESCE(TRIM(e.linkage_kind),'')=''
          AND (e.status='archived' OR (e.status='applied' AND latest.id IS NOT NULL))
        """, (str(archive_root),)).fetchall():
        event = dict(row)
        event_id = event["id"]
        events[event_id] = (event["job_id"], event["name"], str(event_root_relative(event)), event["revision"], event["proof_id"])
        proof = event["proof_id"]
        registered = {}
        locations = dict(connection.execute(
            "SELECT file_id,relative_path FROM event_archive_verified_file_locations WHERE event_id=?",
            (event_id,),
        ).fetchall())
        if proof:
            for file in connection.execute("""
                SELECT file_id,expected_relative_path,expected_size_bytes,expected_sha256
                FROM event_archive_verification_files WHERE verification_id=? AND status='verified'
                """, (proof,)):
                registered[file[0]] = tuple(file)[1:]
            for asset in connection.execute("""
                SELECT expected_relative_path,expected_size_bytes,expected_sha256
                FROM event_archive_verification_assets WHERE verification_id=? AND status='verified'
                """, (proof,)):
                expected[asset[0]].add((event_id, asset[1], asset[2]))
        for file in event_file_rows(connection, event_id):
            if file.get("current_root_kind") != "camera_archive" and file["file_id"] not in locations:
                continue
            path = file["current_relative_path"] if file.get("current_root_kind") == "camera_archive" else locations[file["file_id"]]
            digest = file["sha256_current"] or file["sha256_original"]
            if path and digest:
                registered[file["file_id"]] = (path, file["size_bytes"], digest)
        for path, size, digest in registered.values():
            expected[path].add((event_id, size, digest))
    return events, dict(expected)


def _findings(events, expected, actual):
    owners = defaultdict(set)
    for event_id, event in events.items():
        owners[event[2]].add(event_id)

    def owner(path):
        for folder in PurePosixPath(path).parents:
            matches = owners.get(str(folder))
            if matches:
                return next(iter(matches)) if len(matches) == 1 else None
        return None

    groups = defaultdict(lambda: {"counts": Counter(), "examples": []})

    def add(event_id, kind, path, **details):
        group = groups[event_id]
        group["counts"][kind] += 1
        if len(group["examples"]) < 30:
            group["examples"].append({"kind": kind, "path": path, **details})

    expected_content = Counter((size, digest) for variants in expected.values() for _, size, digest in variants)
    actual_content = Counter(actual.values())
    missing = {}
    for path, variants in sorted(expected.items()):
        if len(variants) != 1:
            add(None, "unassigned", path)
            continue
        event_id, size, digest = next(iter(variants))
        if path not in actual:
            missing[path] = (event_id, (size, digest))
        elif actual[path] != (size, digest):
            add(event_id, "changed", path)

    extras = defaultdict(list)
    for path in sorted(actual.keys() - expected.keys()):
        extras[actual[path]].append(path)
    for path, (event_id, content) in missing.items():
        if expected_content[content] == actual_content[content] == 1 and content in extras:
            target, = extras.pop(content)
            add(event_id, "moved", path, observed_path=target)
        else:
            add(event_id, "missing", path)
    for content, paths in extras.items():
        for path in paths:
            event_id = owner(path)
            if event_id is None or expected_content[content]:
                add(event_id, "unassigned", path)
            else:
                add(event_id, "added", path)
    return groups


def _publish(connection, state, events, groups, archive_root):
    now = _now()
    totals = dict.fromkeys(_KINDS, 0)
    remaining = {row[0] for row in connection.execute(
        "SELECT notice_key FROM external_change_notices WHERE kind=? AND status='open'", (_NOTICE_KIND,),
    )}
    for event_id, result in groups.items():
        key = f"{_NOTICE_KIND}:{event_id or 'unassigned'}"
        remaining.discard(key)
        job_id, event_name, prefix, _, _ = events.get(event_id, (None, "", "", None, None))
        for kind, count in result["counts"].items():
            totals[kind] += count
        record_notice(
            connection, notice_key=key, kind=_NOTICE_KIND, root_kind="camera_archive",
            title="Abweichungen im Archivbestand",
            detail="Die Archivprüfung hat Abweichungen festgestellt. Prüfe die gefundenen Pfade in den Aufgabendetails.",
            job_id=job_id, event_id=event_id, relative_path=prefix, action_required=True,
            details={**result, "event_name": event_name, "event_id": event_id, "job_id": job_id},
            now=now,
        )
        if event_id is None:
            continue
        # Preserve the proof as history. Supersede it using the same mechanism
        # as an applied-event edit, so batch release requires a current proof.
        proof = connection.execute("""
            SELECT * FROM event_archive_verifications WHERE event_id=? AND job_id=?
            ORDER BY created_at DESC,id DESC LIMIT 1
            """, (event_id, job_id)).fetchone()
        if proof and proof["status"] == "verified" and proof["archive_root"] == str(archive_root):
            connection.execute("""
                INSERT INTO event_archive_verifications(
                    id,job_id,event_id,status,archive_root,file_count,total_size_bytes,
                    details_json,error_message,created_at,updated_at,completed_at
                ) VALUES (?,?,?,'failed',?,?,?,?,'verification_invalidated_by_archive_scan',?,?,?)
                """, (
                uuid4().hex, job_id, event_id, str(archive_root), proof["file_count"], proof["total_size_bytes"],
                json.dumps({"supersedes_verification_id": proof["id"], "scan_id": state["id"]}), now, now, now,
            ))
    for key in remaining:
        resolve_notice_key(connection, key, now=now)
    state.update(status="completed", phase="complete", percent=100, eta_seconds=None,
                 last_success_at=now, result=totals)
    _save(connection, state)


@protect(workspace_arg="workspace_path", kind="inventory", error_type=AdoptionError, durable=False)
def run(database_path, workspace_path, archive_root, stopping):
    with database_connection(database_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        state = _get(connection)
        if state["status"] not in _ACTIVE or stopping():
            return False
        state.update(status="running", phase="discovery", checked=0, total=None,
                     percent=None, eta_seconds=None, attempt=state["attempt"] + 1)
        state.pop("error", None)
        _save(connection, state)

    def check_stop():
        if stopping():
            raise InterruptedError("Archivscan beim Herunterfahren unterbrochen.")

    try:
        archive_root = Path(archive_root).resolve(strict=True)
        with database_connection(database_path) as connection:
            connection.execute("BEGIN")
            events, expected = _catalogue(connection, archive_root)

        def files(root_fd):
            for path, parent, filename, info in walk_bound_files(root_fd, PurePosixPath(), validate_names=False):
                check_stop()
                if path in expected or (filename not in IGNORED_EVENT_FILES and not filename.startswith("._")):
                    yield path, parent, filename, info

        with bound_directory(archive_root) as directory:
            planned = {path: file_identity(info) for path, _, _, info in files(directory)}
            total = len(planned)
            total_bytes = sum(identity[2] for identity in planned.values())
            start = last_update = time.monotonic()
            read_bytes = 0
            actual = {}
            state.update(phase="hashing", total=total, percent=0)
            with database_connection(database_path) as connection:
                _save(connection, state)

            def report(byte_count):
                nonlocal read_bytes, last_update
                read_bytes += byte_count
                now = time.monotonic()
                if now - last_update < 1:
                    return
                elapsed = now - start
                rate = read_bytes / elapsed
                state.update(
                    checked=len(actual),
                    percent=min(99, int(100 * (read_bytes / total_bytes if total_bytes else len(actual) / max(total, 1)))),
                    eta_seconds=round((total_bytes - read_bytes) / rate) if elapsed >= 5 and rate > 0 else None,
                )
                with database_connection(database_path) as connection:
                    _save(connection, state)
                last_update = now

            for path, parent, filename, _ in files(directory):
                if path not in planned:
                    raise AdoptionError("Der Archivbestand hat sich während der Erfassung geändert.")
                with bound_file(parent, filename, planned[path]) as (descriptor, info):
                    digest = bound_sha256(descriptor, check_stop, progress_callback=report)
                    actual[path] = (info.st_size, digest)
                report(0)
            if actual.keys() != planned.keys():
                raise AdoptionError("Der Archivbestand hat sich während der Erfassung geändert.")

        check_stop()
        groups = _findings(events, expected, actual)
        with database_connection(database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            validate_active_roots()
            if _catalogue(connection, archive_root) != (events, expected):
                raise AdoptionError("Der Bibliothekskatalog hat sich während der Erfassung geändert. Bitte erneut scannen.")
            state["checked"] = total
            _publish(connection, state, events, groups, archive_root)
    except (InterruptedError, AdoptionError, OSError, ValueError, RuntimeError) as error:
        state.update(status="interrupted" if isinstance(error, InterruptedError) else "failed",
                     eta_seconds=None, error=str(error))
        with database_connection(database_path) as connection:
            _save(connection, state)
            if state["status"] == "failed":
                connection.execute("""
                    INSERT INTO audit_log(action,entity_type,entity_id,details_json,created_at)
                    VALUES ('archive_inventory_scan_failed','archive_inventory_scan',?,?,?)
                    """, (state["id"], json.dumps({"error": str(error)}), _now()))
    return True


def process_next(context, stopping):
    if status(context.database_path)["status"] not in _ACTIVE or stopping():
        return False
    try:
        return run(context.database_path, context.workspace_root, context.archive_root, stopping)
    except AdoptionError as error:
        if isinstance(error.__cause__, RootOperationBusy):
            return False
        # The root reservation failed before the job could safely start.
        with database_connection(context.database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            state = _get(connection)
            if state["status"] in _ACTIVE:
                state.update(status="failed", error=str(error), eta_seconds=None)
                _save(connection, state)
        return False
