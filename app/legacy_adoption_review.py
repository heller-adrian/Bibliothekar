"""Review cases and verified working copies in the existing General intake."""
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import stat

from app import legacy_adoption_host as host
from app.database import database_connection
from app.legacy_adoption_inventory import _inventory_groups, _job
from app.legacy_adoption_paths import (
    AdoptionError, bound_child_directory, bound_directory, bound_file, bound_sha256,
    directory_identity, relative_parent, target_key, validate_target,
)
from app.legacy_adoption_plan import _roots
from app.metadata_correction import metadata_area_paths
from app.root_operations import validate_active_roots
from app.source_filter import LEGACY_REVIEW_STAGING


def _status(family, members, files, draft, copied, unassigned):
    key = family["family_key"]
    reasons = []
    if not family.get("selected_capture_time"):
        reasons.append("missing_capture_time")
    confidences = {file.get("capture_time_confidence") for file in files}
    if family.get("capture_time_confidence") == "conflict" or "conflict" in confidences:
        reasons.append("conflicting_capture_time")
    if any(file.get("metadata_error") for file in files):
        reasons.append("damaged_metadata")
    if any(row["error"] or not row["sha256"] for row in members):
        reasons.append("unreadable_member")
    if unassigned:
        reasons.append("unassigned_event")
    if not reasons:
        reasons.append("uncertain_capture_time")
    state = "open"
    if key in draft.get("exclude_families", []):
        state = "excluded"
    elif key in draft.get("capture_overrides", {}) and not unassigned:
        state = "confirmed"
    if copied:
        state = copied["state"]
    return {
        "family_key": key, "reasons": reasons, "state": state,
        "can_copy": all(row["sha256"] for row in members) and state != "copied",
        "size_bytes": sum(row["size_bytes"] or 0 for row in members),
        "files": [{"relative_path": row["relative_path"], "error": row["error"],
                   "metadata": json.loads(row["metadata_json"]) if row["metadata_json"] else None}
                  for row in members],
        "target_relative": copied["target_relative"] if copied else None,
    }


_REVIEW_WHERE = """
       family.job_id = :job AND (
          family.review_required OR copy.family_key IS NOT NULL OR (
             :plan IS NOT NULL AND NOT EXISTS (
                SELECT 1 FROM legacy_adoption_moves move
                  JOIN legacy_adoption_inventory member
                    ON member.job_id = family.job_id AND member.relative_path = move.relative_path
                 WHERE move.plan_id = :plan AND member.family_key = family.family_key
             )
          )
       )
"""
_REVIEW_FROM = """
    FROM legacy_adoption_families family
    LEFT JOIN legacy_adoption_review_copies copy USING (job_id, family_key)
"""


def _plan_for(connection, job_id):
    return connection.execute(
        """SELECT plan.id, plan.draft_json, execution.method
             FROM legacy_adoption_plans plan LEFT JOIN legacy_adoption_execution execution ON execution.plan_id = plan.id
            WHERE job_id = ?""", (job_id,),
    ).fetchone()


def review_count(connection, job_id, plan_id):
    return connection.execute(
        "SELECT count(*) " + _REVIEW_FROM + " WHERE " + _REVIEW_WHERE,
        {"job": job_id, "plan": plan_id},
    ).fetchone()[0]


def review_cases(library, job_id, *, after=""):
    with database_connection(library.database_path) as connection:
        connection.execute("BEGIN")
        job = _job(connection, library.library_id, job_id)
        plan = _plan_for(connection, job_id)
        draft = json.loads(plan["draft_json"] if plan else job["draft_json"])
        rows = connection.execute(
            """WITH cases AS (
                SELECT family.family_key """ + _REVIEW_FROM + " WHERE " + _REVIEW_WHERE + """
                  AND family.family_key > :after ORDER BY family.family_key LIMIT 60
            )
            SELECT inventory.* FROM cases JOIN legacy_adoption_inventory inventory USING (family_key)
             WHERE inventory.job_id = :job ORDER BY family_key, relative_path""",
            {"job": job_id, "after": after, "plan": plan["id"] if plan else None},
        )
        result = []
        for family, members, files in _inventory_groups(rows, Path(job["source_root"])):
            key = family["family_key"]
            copied = connection.execute(
                "SELECT * FROM legacy_adoption_review_copies WHERE job_id = ? AND family_key = ?", (job_id, key),
            ).fetchone()
            assigned = bool(plan and _assigned(connection, job_id, plan["id"], key))
            case = _status(family, members, files, draft, copied,
                           bool(plan and not assigned and family.get("selected_capture_time")
                                and key not in draft.get("exclude_families", []) and not copied))
            case["can_copy"] = case["can_copy"] and not assigned and not (plan and plan["method"])
            result.append(case)
        return result


def _assigned(connection, job_id, plan_id, key):
    return connection.execute(
        """SELECT 1 FROM legacy_adoption_moves move
             JOIN legacy_adoption_inventory member ON member.job_id = ? AND member.relative_path = move.relative_path
            WHERE move.plan_id = ? AND member.family_key = ? LIMIT 1""",
        (job_id, plan_id, key),
    ).fetchone()


def _new_directory(parent, name):
    try:
        os.mkdir(name, 0o700, dir_fd=parent)
    except FileExistsError:
        pass
    else:
        os.fsync(parent)
    info = os.stat(name, dir_fd=parent, follow_symlinks=False)
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077:
        raise AdoptionError("Der interne Ordner für Prüffallkopien ist nicht privat: " + name)
    return bound_child_directory(parent, name, directory_identity(info))


def _member_proof(directory, name, member):
    with bound_file(directory, name) as (descriptor, info):
        if info.st_size != member["size_bytes"] or bound_sha256(descriptor) != member["sha256"]:
            raise AdoptionError("Die vorhandene Arbeitskopie weicht von der Inventur ab: " + name)


def _discard_partial(stage, temporary):
    pending = host.info_at(stage, temporary)
    if pending is not None:
        if not stat.S_ISREG(pending.st_mode) or pending.st_nlink != 1 or pending.st_uid != os.geteuid():
            raise AdoptionError("Unbekanntes Objekt im internen Kopierordner: " + temporary)
        os.unlink(temporary, dir_fd=stage)


def _copy_member(source, stage, name, temporary, member):
    validate_active_roots()
    with relative_parent(source, member["relative_path"]) as (original, original_name):
        with bound_file(original, original_name, tuple(json.loads(member["identity"]))) as (reader, _):
            fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o666, dir_fd=stage)
            with os.fdopen(fd, "wb") as output:
                while data := os.read(reader, 1024 * 1024):
                    output.write(data)
                output.flush()
                os.fsync(output.fileno())
    _member_proof(stage, temporary, member)
    host.rename_noreplace(stage, temporary, stage, name)
    os.fsync(stage)


def _check_capacity(stage, remaining):
    space = os.fstatvfs(stage)
    required = sum(member["size_bytes"] + space.f_frsize for _, _, member in remaining)
    if space.f_bavail * space.f_frsize < required:
        raise AdoptionError("Im Workspace ist nicht genug Speicherplatz für die vollständige Dateifamilie.")


def _publish_copy(library, job, members, destination):
    general = metadata_area_paths(area="general", workspace_root=library.workspace_root,
                                  library_id=library.library_id, create=False)["root"]
    with ExitStack() as stack:
        source, _ = _roots(stack, library, job)
        root = stack.enter_context(bound_directory(general))
        existing = host.info_at(root, destination)
        if existing is not None:
            with bound_child_directory(root, destination, directory_identity(existing)) as ready:
                if set(os.listdir(ready)) != {name for name, _ in members}:
                    raise AdoptionError("Der Zielordner enthält andere Dateien: " + destination)
                for name, member in members:
                    _member_proof(ready, name, member)
            return
        staging = stack.enter_context(_new_directory(root, LEGACY_REVIEW_STAGING))
        with _new_directory(staging, destination) as stage:
            remaining = []
            for index, (name, member) in enumerate(members):
                temporary = ".copy-" + str(index)
                if host.info_at(stage, name) is None:
                    _discard_partial(stage, temporary)
                    remaining.append((name, temporary, member))
                else:
                    _member_proof(stage, name, member)
            _check_capacity(stage, remaining)
            for name, temporary, member in remaining:
                _copy_member(source, stage, name, temporary, member)
            if set(os.listdir(stage)) != {name for name, _ in members}:
                raise AdoptionError("Die vorbereitete Arbeitskopie enthält unerwartete Dateien.")
        validate_active_roots()
        host.rename_noreplace(staging, destination, root, destination)
        os.fsync(staging)
        os.fsync(root)


def copy_review(library, job_id, key):
    with database_connection(library.database_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        job = dict(_job(connection, library.library_id, job_id))
        plan = _plan_for(connection, job_id)
        if job["state"] != "inventoried" or (plan and plan["method"]):
            raise AdoptionError("Arbeitskopien sind nur während der Planung möglich.")
        row = connection.execute(
            "SELECT review_required FROM legacy_adoption_families WHERE job_id = ? AND family_key = ?",
            (job_id, key),
        ).fetchone()
        assigned = plan and _assigned(connection, job_id, plan["id"], key)
        if row is None or assigned or (not row["review_required"] and not plan):
            raise AdoptionError("Diese Familie ist kein ausstehender Prüffall.")
        previous = connection.execute(
            "SELECT * FROM legacy_adoption_review_copies WHERE job_id = ? AND family_key = ?", (job_id, key),
        ).fetchone()
        if previous and previous["state"] == "copied":
            return dict(previous)
        members = [(Path(item["relative_path"]).name, dict(item)) for item in connection.execute(
            """SELECT relative_path, size_bytes, identity, sha256 FROM legacy_adoption_inventory
                WHERE job_id = ? AND family_key = ? ORDER BY relative_path""",
            (job_id, key),
        )]
        if not members or any(not item["sha256"] or not item["identity"] for _, item in members):
            raise AdoptionError("Die Dateifamilie ist unvollständig und kann nicht als Arbeitskopie übernommen werden.")
        if len({target_key(name) for name, _ in members}) != len(members):
            raise AdoptionError("Mehrere Dateien der Familie beanspruchen denselben Namen.")
        for name, _ in members:
            validate_target(name)
            if name.startswith(".copy-"):
                raise AdoptionError("Der Dateiname ist für Prüffallkopien reserviert.")
        fingerprint = hashlib.sha256(host.json_bytes(sorted(
            (name, item["sha256"]) for name, item in members
        ))).hexdigest()
        destination = "legacy-" + fingerprint
        connection.execute(
            """INSERT OR IGNORE INTO legacy_adoption_review_copies
                (job_id, family_key, state, target_relative, file_count, size_bytes)
                VALUES (?, ?, 'copying', ?, ?, ?)""",
            (job_id, key, destination, len(members), sum(item["size_bytes"] for _, item in members)),
        )
    _publish_copy(library, job, members, destination)
    with database_connection(library.database_path) as connection:
        connection.execute(
            """UPDATE legacy_adoption_review_copies SET state = 'copied', updated_at = CURRENT_TIMESTAMP
                WHERE job_id = ? AND family_key = ?""",
            (job_id, key),
        )
        return dict(connection.execute(
            "SELECT * FROM legacy_adoption_review_copies WHERE job_id = ? AND family_key = ?", (job_id, key),
        ).fetchone())
