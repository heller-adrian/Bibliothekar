"""Durable no-replace publication of already verified review media in General."""
import json
import os
from pathlib import PurePosixPath

from app import legacy_adoption_host as host
from app.database import database_connection
from app.legacy_adoption_inventory import _legacy_family_key
from app.legacy_adoption_paths import AdoptionError, bound_file, bound_sha256, directory_identity, target_key, validate_target
from app.root_operations import validate_active_roots


def member_proof(directory, name, member, *, require_owner=False, identity=None):
    with bound_file(directory, name) as (descriptor, info):
        actual = directory_identity(info)
        if ((require_owner and info.st_uid != os.geteuid()) or (identity is not None and actual != tuple(identity))
                or info.st_nlink != 1 or info.st_size != member["size_bytes"]
                or bound_sha256(descriptor) != member["sha256"]):
            raise AdoptionError("Die vorhandene Arbeitskopie weicht von der Inventur ab: " + name)
        return actual


def receipt(connection, job_id, key):
    return connection.execute(
        "SELECT * FROM legacy_adoption_flat_review_copies WHERE job_id = ? AND family_key = ?",
        (job_id, key),
    ).fetchone()


def target_files(connection, job_id, key):
    row = receipt(connection, job_id, key)
    if row and row["state"] == "copied":
        return [member["target"] for member in json.loads(row["members_json"])]
    return []


def require_no_partial_publication(connection, job_id):
    if connection.execute(
        "SELECT 1 FROM legacy_adoption_flat_review_copies WHERE job_id = ? AND state = 'publishing' LIMIT 1", (job_id,),
    ).fetchone():
        raise AdoptionError("Setze zuerst den unterbrochenen Kopierauftrag fort.")


def _workspace_identity(root):
    return json.dumps(directory_identity(os.fstat(root)))


def _choose_names(root, family_key, originals, reserved=()):
    names = set(os.listdir(root)) | set(reserved)
    occupied = {target_key(name) for name in names}
    stems = {target_key(_legacy_family_key(PurePosixPath("."), name)) for name in names}
    stem = PurePosixPath(family_key).name
    if not all(name.startswith(stem) and name[len(stem):].startswith(".") for name in originals):
        raise AdoptionError("Dateinamen der Prüffallfamilie stimmen nicht überein.")
    endings = [name[len(stem):] for name in originals]
    for number in range(len(names) + 1):
        suffix = f"_{number}" if number else ""
        capacity = min(255, os.fpathconf(root, "PC_NAME_MAX")) - max(len(end.encode()) for end in endings) - len(suffix)
        base = stem.encode()[:capacity].decode("utf-8", errors="ignore") + suffix
        targets = [base + end for end in endings]
        if target_key(base) in stems or any(target_key(target) in occupied for target in targets):
            continue
        for target in targets:
            validate_target(target)
        return targets
    raise AdoptionError("Für die Dateifamilie konnte kein freier Name in General ermittelt werden.")


def verify_published(root, plan):
    for entry in plan:
        member_proof(root, entry["target"], entry, require_owner=True, identity=entry["identity"])


def reuse_completed(database, root, job, key, fingerprint, members):
    with database_connection(database) as connection:
        candidates = connection.execute(
            """SELECT * FROM legacy_adoption_flat_review_copies
               WHERE fingerprint = ? AND workspace_identity = ? AND state = 'copied'""",
            (fingerprint, _workspace_identity(root)),
        ).fetchall()
        for row in candidates:
            plan = json.loads(row["members_json"])
            try:
                verify_published(root, plan)
            except (AdoptionError, OSError):
                continue
            sources = {name: member["relative_path"] for name, member in members}
            for entry in plan:
                entry["source"] = sources[entry["name"]]
            connection.execute(
                """INSERT INTO legacy_adoption_flat_review_copies VALUES (?, ?, ?, ?, ?, ?, ?, 'copied')""",
                (job["id"], key, job["source_root"], fingerprint, row["workspace_identity"], row["stage_name"],
                 json.dumps(plan)),
            )
            return True
    return False


def reserve(database, root, stage, job, key, fingerprint, stage_name, members):
    with database_connection(database) as connection:
        connection.execute("BEGIN IMMEDIATE")
        identity = _workspace_identity(root)
        reserved = [
            path["target"] for row in connection.execute(
                """SELECT members_json FROM legacy_adoption_flat_review_copies
                   WHERE workspace_identity = ? AND state = 'publishing'""", (identity,),
            ) for path in json.loads(row[0])
        ]
        targets = _choose_names(root, key, [name for name, _ in members], reserved)
        plan = [
            {"name": name, "target": target, "source": member["relative_path"], "sha256": member["sha256"],
             "size_bytes": member["size_bytes"],
             "identity": directory_identity(os.stat(name, dir_fd=stage, follow_symlinks=False))}
            for (name, member), target in zip(members, targets, strict=True)
        ]
        connection.execute(
            """INSERT INTO legacy_adoption_flat_review_copies VALUES (?, ?, ?, ?, ?, ?, ?, 'publishing')""",
            (job["id"], key, job["source_root"], fingerprint, identity, stage_name, json.dumps(plan)),
        )
    return plan


def _moved(stage, root, plan):
    moved = []
    for entry in plan:
        name, target = entry["name"], entry["target"]
        if host.info_at(stage, name) is None:
            member_proof(root, target, entry, require_owner=True, identity=entry["identity"])
            moved.append(entry)
        else:
            member_proof(stage, name, entry, require_owner=True, identity=entry["identity"])
    return moved


def publish(database, stage, root, job_id, key, plan):
    # Moving each verified inode keeps both the no-clobber property and a
    # restart-proof identity. The adoption lease keeps normal consumers closed
    # until the whole family has been verified and the receipt is complete.
    moved = _moved(stage, root, plan)
    remaining = [entry for entry in plan if entry not in moved]
    owned = {entry["target"] for entry in moved}
    names = set(os.listdir(root)) - owned
    assigned = target_key(_legacy_family_key(PurePosixPath("."), plan[0]["target"]))
    if any(target_key(_legacy_family_key(PurePosixPath("."), name)) == assigned for name in names):
        validate_active_roots()
        for entry in moved:
            host.rename_noreplace(root, entry["target"], stage, entry["name"])
        os.fsync(root)
        os.fsync(stage)
        targets = _choose_names(root, key, [entry["name"] for entry in plan])
        for entry, target in zip(plan, targets, strict=True):
            entry["target"] = target
        with database_connection(database) as connection:
            connection.execute(
                "UPDATE legacy_adoption_flat_review_copies SET members_json = ? WHERE job_id = ? AND family_key = ?",
                (json.dumps(plan), job_id, key),
            )
        remaining = plan
    for entry in remaining:
        validate_active_roots()
        host.rename_noreplace(stage, entry["name"], root, entry["target"])
    os.fsync(stage)
    os.fsync(root)
    verify_published(root, plan)


def finish(database, job_id, key):
    with database_connection(database) as connection:
        connection.execute(
            "UPDATE legacy_adoption_flat_review_copies SET state = 'copied' WHERE job_id = ? AND family_key = ?",
            (job_id, key),
        )
