"""Copy batch transitions and ownership of files created during review staging."""

import json
import os
import stat
from hashlib import sha256
from time import monotonic
from uuid import uuid4

from app import legacy_adoption_host as host
from app.database import database_connection
from app.legacy_adoption_paths import AdoptionError, bound_file, directory_identity
from app.root_operations import validate_active_roots
from app.source_filter import LEGACY_REVIEW_PRIVATE_STAGING, LEGACY_REVIEW_STAGING, LEGACY_REVIEW_VERIFIED_STAGING

STALE = "Dieser Kopierauftrag ist bereits beendet oder wurde ersetzt."
UNPROVEN = "Eine Arbeitskopie oder ihr Ordner wurde verändert. Die Bereinigung wartet auf eine sichere Wiederherstellung."
STAGE_PARENTS = frozenset({
    LEGACY_REVIEW_STAGING, LEGACY_REVIEW_PRIVATE_STAGING, LEGACY_REVIEW_VERIFIED_STAGING,
})


class CancelRequested(Exception):
    pass


def run(connection, job_id):
    return connection.execute(
        "SELECT id, state, error FROM legacy_adoption_review_runs WHERE job_id = ?", (job_id,),
    ).fetchone()


def start(connection, job_id):
    batch = uuid4().hex
    connection.execute(
        """INSERT INTO legacy_adoption_review_runs VALUES (?, ?, 'active', NULL)
           ON CONFLICT(job_id) DO UPDATE SET id = excluded.id, state = 'active', error = NULL""",
        (job_id, batch),
    )
    return batch


def request(connection, job_id, batch):
    current = run(connection, job_id)
    if current is None or current["id"] != batch or current["state"] == "finished":
        raise AdoptionError(STALE)
    if current["state"] != "cancelled":
        connection.execute(
            "UPDATE legacy_adoption_review_runs SET state = 'cancelling', error = NULL WHERE job_id = ? AND id = ?",
            (job_id, batch),
        )
    return current["state"] != "cancelled"


def cancellation_check(database, job_id, batch):
    last_check = 0.0

    def check(*, force=False):
        nonlocal last_check
        if not batch or (not force and monotonic() - last_check < 0.2):
            return
        with database_connection(database) as connection:
            row = run(connection, job_id)
        last_check = monotonic()
        if row is None or row["id"] != batch or row["state"] != "active":
            raise CancelRequested

    return check


def journal(connection, job, family):
    return connection.execute(
        "SELECT * FROM legacy_adoption_review_stages WHERE job_id = ? AND family_key = ?", (job, family),
    ).fetchone()


def write_journal(database, job, family, batch, fingerprint, root, parent_name, parent):
    with database_connection(database) as connection:
        connection.execute(
            """INSERT INTO legacy_adoption_review_stages
               (job_id, family_key, batch_id, fingerprint, workspace_identity, parent_name, parent_identity)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (job, family, batch, fingerprint, json.dumps(directory_identity(os.fstat(root))),
             parent_name, json.dumps(directory_identity(os.fstat(parent)))),
        )
        return journal(connection, job, family)


def folder_name(entry):
    family = sha256(entry["family_key"].encode()).hexdigest()[:16]
    return f"{entry['fingerprint']}-{entry['batch_id']}-{family}"


def record_directory(database, entry, stage):
    identity = json.dumps(directory_identity(os.fstat(stage)))
    if entry["stage_identity"] not in (None, identity):
        raise AdoptionError(UNPROVEN)
    if entry["stage_identity"] is None:
        if os.listdir(stage):
            raise AdoptionError(UNPROVEN)
        with database_connection(database) as connection:
            connection.execute(
                "UPDATE legacy_adoption_review_stages SET stage_identity = ? WHERE job_id = ? AND family_key = ?",
                (identity, entry["job_id"], entry["family_key"]),
            )


def record_inode(database, job, family, name, temporary, descriptor):
    info = os.fstat(descriptor)
    with database_connection(database) as connection:
        entry = journal(connection, job, family)
        if entry:
            members = json.loads(entry["members_json"])
            members[name] = {"identity": directory_identity(info), "temporary": temporary}
            connection.execute(
                "UPDATE legacy_adoption_review_stages SET members_json = ? WHERE job_id = ? AND family_key = ?",
                (json.dumps(members), job, family),
            )


def verify_stage(stage, entry):
    if not entry:
        return
    recorded = {}
    for name, item in json.loads(entry["members_json"]).items():
        recorded[name] = item["identity"]
        if item["temporary"]:
            recorded[item["temporary"]] = item["identity"]
    for name in os.listdir(stage):
        if name not in recorded or not _matches(os.stat(name, dir_fd=stage, follow_symlinks=False), recorded[name]):
            raise AdoptionError(UNPROVEN)


def _matches(info, identity):
    return (stat.S_ISREG(info.st_mode) and info.st_uid == os.geteuid()
            and info.st_nlink == 1 and directory_identity(info) == tuple(identity))


def remove_owned(directory, name, holding, quarantine, identity, verify=None):
    """Move into the bound operation directory before deleting a verified inode.

    If the original name changes in the rename window, return that object by a
    no-replace rename. An occupied original name leaves both files recoverable.
    The quarantine name is deterministic so a restart finds a detached inode.
    """
    held = host.info_at(holding, quarantine)
    original = host.info_at(directory, name)
    if held is None:
        if original is None:
            return
        if not _matches(original, identity):
            raise AdoptionError(UNPROVEN)
        if verify:
            verify(directory, name)
        validate_active_roots()
        host.rename_noreplace(directory, name, holding, quarantine)
        os.fsync(directory)
        os.fsync(holding)
        held = os.stat(quarantine, dir_fd=holding, follow_symlinks=False)
    try:
        if not _matches(held, identity):
            raise AdoptionError(UNPROVEN)
        if verify:
            verify(holding, quarantine)
        with bound_file(holding, quarantine) as (_, opened):
            if not _matches(opened, identity):
                raise AdoptionError(UNPROVEN)
    except AdoptionError:
        if host.info_at(directory, name) is None:
            host.rename_noreplace(holding, quarantine, directory, name)
            os.fsync(holding)
            os.fsync(directory)
        raise
    validate_active_roots()
    os.unlink(quarantine, dir_fd=holding)
    os.fsync(holding)
