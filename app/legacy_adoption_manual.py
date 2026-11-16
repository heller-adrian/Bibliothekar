"""Live, read-only SMB instructions for the frozen adoption plan."""
from contextlib import ExitStack
from functools import lru_cache
import json
import os
from pathlib import PurePosixPath
import stat
from unicodedata import normalize

from app.database import database_connection
from app.event_inventory import event_root_relative
from app.filename_collisions import collision_alias_stems
from app.legacy_adoption_inventory import _job
from app.legacy_adoption_paths import AdoptionError, relative_parent
from app.legacy_adoption_plan import _archive_probe, _roots
from app.legacy_adoption_verify import _entry, _matches, _plan, _verify_move, move_rows
from app.manual_file_operations import group_file_operations

MANUAL_PHASES = frozenset({"manual", "verifying", "repair", "registration_pending", "rolling_back"})


def record_missing_directories(connection, library, job, plan):
    # Event directories are attributable to this plan. The shared year folders
    # may serve other events and are excluded from rollback cleanup.
    roots = {event_root_relative(event) for event in json.loads(plan["events_json"])}
    with ExitStack() as stack:
        _, archive = _roots(stack, library, job)
        lookup = _archive_probe(archive)
        connection.executemany(
            "INSERT INTO legacy_adoption_manual_directories VALUES (?, ?)",
            ((plan["id"], path) for (path,) in connection.execute(
                "SELECT relative_path FROM legacy_adoption_directories WHERE plan_id = ?", (plan["id"],),
            ) if not roots.isdisjoint((PurePosixPath(path), *PurePosixPath(path).parents)) and lookup(path) is None),
        )


def _created_paths(connection, plan_id):
    return [row[0] for row in connection.execute(
        """SELECT relative_path FROM legacy_adoption_manual_directories
           WHERE plan_id = ? ORDER BY length(relative_path) DESC, relative_path""",
        (plan_id,),
    )]


def assert_directories_restored(connection, library, job, plan):
    paths = _created_paths(connection, plan["id"])
    if paths:
        with ExitStack() as stack:
            _, archive = _roots(stack, library, job)
            lookup = _archive_probe(archive)
            for path in paths:
                if lookup(path) is not None:
                    raise AdoptionError("Ein für die Übernahme angelegter Archivordner ist noch vorhanden: " + path)


def _existing_directory(root, path):
    if path == ".":
        return "done"
    # Opening a leaf through relative_parent also rejects symlinks and mounts.
    try:
        with relative_parent(root, str(PurePosixPath(path) / ".directory")):
            return "done"
    except FileNotFoundError:
        return "pending"
    except (AdoptionError, OSError):
        return "attention"


def _move_state(source, archive, archive_entry, row, reverse):
    target = row["target_path"]
    original = row["relative_path"]
    try:
        if archive_entry(target) is None:
            identity = tuple(json.loads(row["identity"])[:2])
            if _matches(source, original, row["size_bytes"], row["sha256"], expected_inode=identity):
                return ("done" if reverse else "pending"), None
            return "attention", "source_unverified"
        status = _verify_move(source, archive, row, lambda *_: None)
        if status == "verified":
            return ("pending" if reverse else "done"), None
        return "attention", status
    except (OSError, AdoptionError):
        return "attention", "unsafe"



def _rename_diagnostics(source, archive, reserved):
    @lru_cache(maxsize=32)
    def names(folder):
        try:
            with relative_parent(archive, str(folder / ".directory")) as (parent, _):
                return os.listdir(parent)
        except (OSError, AdoptionError):
            return []

    def observed(row, original, target):
        # An SMB collision name is useful as a hint only. Never approve a
        # different path, copy or unrelated file with a lookalike name.
        try:
            if _entry(source, str(original)) is not None:
                return None
            names_to_match = {normalize("NFC", path.stem).casefold() for path in (original, target)}
            matches = []
            for name in names(target.parent):
                candidate = target.parent / name
                path = str(candidate)
                if path in reserved or candidate.suffix.casefold() != target.suffix.casefold():
                    continue
                aliases = collision_alias_stems(normalize("NFC", candidate.stem), allow_plain_number=True)
                if names_to_match.intersection(aliases) and _matches(
                    archive, path, row["size_bytes"], row["sha256"],
                    expected_inode=tuple(json.loads(row["identity"])[:2]),
                ):
                    matches.append(path)
            return matches[0] if len(matches) == 1 else None
        except (OSError, AdoptionError):
            return None

    return observed

def _summary(items):
    states = {item["state"] for item in items}
    if "unchecked" in states:
        return "unchecked"
    if "attention" in states:
        return "attention"
    return "pending" if states & {"pending", "waiting"} else "done"


def _item(path, state):
    return {"path": path, "state": state}


def _documents(connection, archive, lookup, plan_id, reverse, check):
    items = []
    rows = connection.execute(
        """SELECT prepared.relative_path, length(prepared.content) AS size, prepared.sha256,
                  baseline.size_bytes AS original_size, baseline.sha256 AS original_sha
             FROM legacy_adoption_documents prepared
             LEFT JOIN legacy_adoption_baseline baseline USING (plan_id, relative_path)
            WHERE prepared.plan_id = ? ORDER BY prepared.relative_path""", (plan_id,),
    )
    for row in rows:
        path = row["relative_path"]
        state = "unchecked"
        if check:
            try:
                prepared = _matches(archive, path, row["size"], row["sha256"])
                original = (
                    _matches(archive, path, row["original_size"], row["original_sha"])
                    if row["original_sha"] is not None else lookup(path) is None
                )
                done, pending = (original, prepared) if reverse else (prepared, original)
                state = "done" if done else "pending" if pending else "attention"
            except (OSError, AdoptionError):
                state = "attention"
        items.append(_item(path, state) | {
            "operation": "restore" if row["original_sha"] is not None else "remove",
        })
    return items


def _cleanup_directories(connection, archive, lookup, plan_id, check):
    paths = _created_paths(connection, plan_id)
    expected = set(paths)
    expected.update(row[0] for row in connection.execute(
        """SELECT target_path FROM legacy_adoption_moves WHERE plan_id = ? AND target_path IS NOT NULL
           UNION SELECT relative_path FROM legacy_adoption_documents WHERE plan_id = ?""",
        (plan_id, plan_id),
    ))
    items = []
    for path in paths:
        state = "unchecked"
        if check:
            try:
                entry = lookup(path)
                if entry is None:
                    state = "done"
                elif not stat.S_ISDIR(entry.st_mode) or entry.st_dev != os.fstat(archive).st_dev:
                    state = "attention"
                else:
                    with relative_parent(archive, str(PurePosixPath(path) / ".directory")) as (directory, _):
                        contents = {str(PurePosixPath(path) / entry) for entry in os.listdir(directory)}
                    state = "attention" if contents - expected else "waiting" if contents else "pending"
            except (OSError, AdoptionError):
                state = "attention"
        items.append(_item(path, state))
    return items


def manual_work(library, job_id, *, check=False):
    with database_connection(library.database_path) as connection, ExitStack() as stack:
        connection.execute("BEGIN")
        job = _job(connection, library.library_id, job_id)
        plan = _plan(connection, job_id)
        plan_id = plan["id"]
        execution = connection.execute(
            "SELECT method, phase FROM legacy_adoption_execution WHERE plan_id = ?", (plan_id,),
        ).fetchone()
        if not execution or execution["method"] != "manual" or execution["phase"] not in MANUAL_PHASES:
            raise AdoptionError("Manuelle Arbeit ist in dieser Phase nicht verfügbar.")
        reverse = execution["phase"] == "rolling_back"
        source, archive = _roots(stack, library, job)
        lookup = _archive_probe(archive)
        reserved = {row[0] for row in connection.execute(
            "SELECT target_path FROM legacy_adoption_moves WHERE plan_id = ? AND target_path IS NOT NULL",
            (plan_id,),
        )} if check else set()
        observed_rename = _rename_diagnostics(source, archive, reserved)

        def file_operations():
            for row in move_rows(connection, job_id, plan_id):
                original, target = PurePosixPath(row["relative_path"]), PurePosixPath(row["target_path"])
                state, problem = _move_state(source, archive, lookup, row, reverse) if check else ("unchecked", None)
                start, end = (target, original) if reverse else (original, target)
                item = {"from": start.name, "to": end.name, "state": state, "problem": problem}
                if state == "attention" and (observed := observed_rename(row, original, target)):
                    item["observed_archive_path"] = observed
                    item["expected_archive_path"] = str(target)
                yield start, end, item

        groups = group_file_operations(file_operations())
        documents = _documents(connection, archive, lookup, plan_id, reverse, check)
        if reverse:
            folders = [_item(path, _existing_directory(source, path) if check else "unchecked")
                       for path in sorted({directory for (_, directory), _ in groups}) if path != "."]
        else:
            folders = [_item(path, _existing_directory(archive, path) if check else "unchecked") for (path,) in connection.execute(
                "SELECT relative_path FROM legacy_adoption_directories WHERE plan_id = ? ORDER BY relative_path",
                (plan_id,),
            )]
        steps = [{
            "kind": "restore_source" if reverse else "prepare",
            "state": _summary(folders if reverse else folders + documents),
            "items": folders if reverse else folders + documents,
        }]
        for (start, end), members in groups:
            steps.append({
                "kind": "move", "from": start, "to": end, "state": _summary(members), "items": members,
            })
        if reverse:
            steps.append({"kind": "restore_documents", "state": _summary(documents), "items": documents})
            cleanup = _cleanup_directories(connection, archive, lookup, plan_id, check)
            if cleanup:
                steps.append({"kind": "remove_directories", "state": _summary(cleanup), "items": cleanup})
        return {
            "plan_id": plan_id, "reverse": reverse, "steps": steps,
            "source_root": job["source_root"], "archive_root": job["archive_root"],
            "checked": check,
            "ready": check and all(step["state"] == "done" for step in steps),
        }
