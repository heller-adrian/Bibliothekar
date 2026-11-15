"""Review cases and verified working copies in the existing General intake."""
from contextlib import ExitStack, contextmanager
from functools import partial
import errno
import hashlib
import json
import logging
import os
from pathlib import Path
import stat
from uuid import uuid4

from app import legacy_adoption_host as host
from app import legacy_adoption_flat_copy as flat
from app import legacy_adoption_review_cancel as cancel
from app import legacy_adoption_review_progress as progress
from app.legacy_adoption_dataset import DatasetError
from app.database import database_connection
from app.legacy_adoption_inventory import _inventory_groups, _job
from app.legacy_adoption_paths import (
    AdoptionError, bound_child_directory, bound_directory, bound_file, bound_sha256,
    directory_identity, relative_parent, target_key, validate_target,
)
from app.legacy_adoption_plan import _roots
from app.legacy_adoption_review_metadata import capture_choices
from app.metadata_correction import MetadataCorrectionError, metadata_area_paths
from app.root_operations import RootOperationError, validate_active_roots
from app.private_storage_security import NFS4, PrivateStorageError, attributes, filesystem, secure_working_directory
from app.source_filter import LEGACY_REVIEW_PRIVATE_STAGING, LEGACY_REVIEW_STAGING, LEGACY_REVIEW_VERIFIED_STAGING

logger = logging.getLogger(__name__)


class ReviewStagingError(AdoptionError):
    def __init__(self, operation, error):
        super().__init__(STAGING_ERROR)
        self.operation = operation
        self.code = getattr(error, "errno", None) or getattr(error, "code", type(error).__name__)
        if self.code == "private_acl_replace_failed":
            self.operation = "fsetxattr system.nfs4_acl_xdr"
            self.code = error.__cause__.errno


STAGING_ERROR = ("Bibliothekar kann keinen privaten Arbeitsordner erstellen. "
                 "Prüfe die Berechtigungen und ACLs des Workspace und versuche es erneut.")


def _status(family, members, files, draft, copied, unassigned):
    key = family["family_key"]
    reasons = []
    confidences = {file.get("capture_time_confidence") for file in files}
    if family.get("capture_time_confidence") == "conflict" or "conflict" in confidences:
        reasons.append("conflicting_capture_time")
    elif not any(file.get("selected_capture_time") for file in files):
        reasons.append("missing_capture_time")
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
        "can_copy": all(row["sha256"] and row["identity"] and not row["error"] for row in members) and state != "copied",
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
       AND family.family_key NOT IN (SELECT key FROM json_each(:accepted))
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
    plan = _plan_for(connection, job_id)
    draft = json.loads(plan["draft_json"] if plan else connection.execute(
        "SELECT draft_json FROM legacy_adoption_jobs WHERE id = ?", (job_id,),
    ).fetchone()[0])
    return connection.execute(
        "SELECT count(*) " + _REVIEW_FROM + " WHERE " + _REVIEW_WHERE,
        {"job": job_id, "plan": plan_id, "accepted": json.dumps(draft.get("metadata_review_applied", {}))},
    ).fetchone()[0]


def _copy_allowed(job, plan):
    return job["state"] == "inventoried" and not (plan and plan["method"])


def _confirmed(draft, key):
    return key in draft.get("capture_overrides", {}) and key not in draft.get("exclude_families", [])


def _copyable_cases(connection, job_id, job, plan):
    if not _copy_allowed(job, plan):
        raise AdoptionError("Arbeitskopien sind nur während der Planung möglich.")
    draft = json.loads(plan["draft_json"] if plan else job["draft_json"])
    rows = connection.execute(
        """SELECT family.family_key """ + _REVIEW_FROM + " WHERE " + _REVIEW_WHERE + """
            AND (copy.state IS NULL OR copy.state = 'copying')
            AND NOT EXISTS (
                SELECT 1 FROM legacy_adoption_inventory member INDEXED BY legacy_adoption_inventory_family
                 WHERE member.job_id = family.job_id AND member.family_key = family.family_key
                   AND (member.sha256 IS NULL OR member.identity IS NULL OR member.error IS NOT NULL)
            )
            AND NOT EXISTS (
                SELECT 1 FROM legacy_adoption_inventory member
                 JOIN legacy_adoption_moves move ON move.plan_id = :plan AND move.relative_path = member.relative_path
                 WHERE member.job_id = family.job_id AND member.family_key = family.family_key
            )
            ORDER BY family.family_key""",
        {"job": job_id, "plan": plan["id"] if plan else None,
         "accepted": json.dumps(draft.get("metadata_review_applied", {}))},
    )
    confirmed = draft.get("capture_overrides", {}).keys() - set(draft.get("exclude_families", []))
    pending = draft.get("metadata_review_pending", {})
    return [row[0] for row in rows if row[0] not in pending and (plan or row[0] not in confirmed)]


def review_selection(library, job_id, *, include_metadata=False):
    with database_connection(library.database_path) as connection:
        connection.execute("BEGIN")
        job = _job(connection, library.library_id, job_id)
        plan = _plan_for(connection, job_id)
        selected = _copyable_cases(connection, job_id, job, plan)
        if include_metadata and not plan:
            from app.legacy_adoption_review_metadata import _decision_rows

            draft = json.loads(job["draft_json"])
            reviewed = draft.get("capture_overrides", {})
            keys = [row[0] for row in connection.execute(
                "SELECT family_key FROM legacy_adoption_families WHERE job_id = ? AND review_required", (job_id,),
            ) if row[0] not in reviewed]
            selected = sorted(set(selected) | {key for key, members in _decision_rows(connection, job, keys)
                                               if capture_choices(members)})
        return selected


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
            SELECT inventory.* FROM cases
             CROSS JOIN legacy_adoption_inventory inventory INDEXED BY legacy_adoption_inventory_family
                ON inventory.job_id = :job AND inventory.family_key = cases.family_key
             ORDER BY inventory.family_key, inventory.relative_path""",
            {"job": job_id, "after": after, "plan": plan["id"] if plan else None,
             "accepted": json.dumps(draft.get("metadata_review_applied", {}))},
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
            pending = draft.get("metadata_review_pending", {}).get(key)
            case["pending_metadata"] = pending
            case["metadata_choices"] = (
                [{"source": source, "time": choice["time"]} for source, choice in capture_choices(members).items()]
                if not (plan or copied or _confirmed(draft, key)) and _copy_allowed(job, plan) else []
            )
            case["can_copy"] = (case["can_copy"] and not pending and not assigned and _copy_allowed(job, plan)
                                and (plan is not None or not _confirmed(draft, key)))
            failure = connection.execute(
                "SELECT state, error FROM legacy_adoption_review_batch WHERE job_id = ? AND family_key = ?",
                (job_id, key),
            ).fetchone()
            case["copy_error"] = None
            case["target_files"] = flat.target_files(connection, job_id, key) if copied else []
            if case["target_files"]:
                case["target_relative"] = None
            if failure and case["state"] != "copied":
                case["copy_error"] = failure["error"]
                if failure["state"] == "failed":
                    case["state"] = "failed"
                elif failure["state"] == "pending" and case["state"] != "copying":
                    case["state"] = "queued"
            result.append(case)
        return result


def _assigned(connection, job_id, plan_id, key):
    return connection.execute(
        """SELECT 1 FROM legacy_adoption_moves move
             JOIN legacy_adoption_inventory member ON member.job_id = ? AND member.relative_path = move.relative_path
            WHERE move.plan_id = ? AND member.family_key = ? LIMIT 1""",
        (job_id, plan_id, key),
    ).fetchone()


@contextmanager
def _staging_operation(operation):
    try:
        yield
    except (AdoptionError, OSError, PrivateStorageError) as error:
        if isinstance(error, ReviewStagingError) or getattr(error, "errno", None) == errno.ENOSPC:
            raise
        raise ReviewStagingError(operation, error) from error


@contextmanager
def _new_directory(parent, name):
    with _staging_operation("inspect private staging"):
        info = host.info_at(parent, name)
    if info is None:
        temporary = ".prepare-" + uuid4().hex
        with _staging_operation("mkdir private staging"):
            os.mkdir(temporary, 0o700, dir_fd=parent)
            info = os.stat(temporary, dir_fd=parent, follow_symlinks=False)
        identity = directory_identity(info)
        try:
            with _staging_operation("qualify private staging ACL"):
                with bound_child_directory(parent, temporary, identity) as descriptor:
                    secure_working_directory(descriptor, name, created=True)
            with _staging_operation("rename private staging"):
                host.rename_noreplace(parent, temporary, parent, name)
            with _staging_operation("fsync private staging parent"):
                os.fsync(parent)
        finally:
            pending = host.info_at(parent, temporary)
            if pending is not None and directory_identity(pending) == identity:
                os.rmdir(temporary, dir_fd=parent)
    with bound_child_directory(parent, name, directory_identity(info)) as descriptor:
        with _staging_operation("validate private staging ACL"):
            secure_working_directory(descriptor, name)
        yield descriptor


def _staging(stack, root):
    # Reuse a private RC10 directory so interrupted families can resume. Existing
    # directories with wider permissions are not modified or used for new media.
    if host.info_at(root, LEGACY_REVIEW_PRIVATE_STAGING) is None:
        try:
            return stack.enter_context(_new_directory(root, LEGACY_REVIEW_STAGING)), LEGACY_REVIEW_STAGING
        except ReviewStagingError as error:
            if getattr(error.__cause__, "code", "") != "private_acl_untrusted_write":
                raise
    return stack.enter_context(_new_directory(root, LEGACY_REVIEW_PRIVATE_STAGING)), LEGACY_REVIEW_PRIVATE_STAGING


def _general(library):
    return metadata_area_paths(area="general", workspace_root=library.workspace_root,
                               library_id=library.library_id, create=False)["root"]


def _native_staging(root):
    with _staging_operation("read Workspace ACL backend"):
        return filesystem(root) == "zfs" and NFS4[0] in attributes(root, allow_zfs_posix=True)


def _use_unnamed_staging(root):
    if not _native_staging(root):
        return False
    try:
        os.close(_open_unnamed(root))
    except ReviewStagingError as error:
        if error.code in {errno.EOPNOTSUPP, errno.EINVAL, errno.ENOSYS}:
            return False  # Older kernels can still use ACL-qualified staging.
        raise
    return True


@contextmanager
def _verified_directory(parent, name):
    # This namespace may inherit Workspace access. Only verified inodes can
    # be linked here. A retry never adopts, removes or replaces unknown files.
    with _staging_operation("mkdir verified staging"):
        validate_active_roots()
        try:
            os.mkdir(name, 0o770, dir_fd=parent)
        except FileExistsError:
            pass
        info = os.stat(name, dir_fd=parent, follow_symlinks=False)
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid():
            raise PrivateStorageError("private_owner_untrusted", name, "application-owned directory required")
        os.fsync(parent)
    with bound_child_directory(parent, name, directory_identity(info)) as descriptor:
        yield descriptor


def _open_unnamed(directory):
    with _staging_operation("openat O_TMPFILE"):
        fd = os.open(".", os.O_TMPFILE | os.O_RDWR, 0o666, dir_fd=directory)
        try:
            if os.fstat(fd).st_nlink != 0:
                raise AdoptionError("Der Workspace stellt keine unbenannte Arbeitsdatei bereit.")
        except BaseException:
            os.close(fd)
            raise
        return fd


def check_review_staging(library):
    with _staging_operation("open and validate Workspace staging"):
        with ExitStack() as stack:
            root = stack.enter_context(bound_directory(_general(library)))
            if _use_unnamed_staging(root):
                stack.enter_context(_verified_directory(root, LEGACY_REVIEW_VERIFIED_STAGING))
            else:
                _staging(stack, root)


def _discard_partial(stage, temporary):
    pending = host.info_at(stage, temporary)
    if pending is not None:
        if not stat.S_ISREG(pending.st_mode) or pending.st_nlink != 1 or pending.st_uid != os.geteuid():
            raise AdoptionError("Unbekanntes Objekt im internen Kopierordner: " + temporary)
        os.unlink(temporary, dir_fd=stage)


def _write_member(source, output, member):
    validate_active_roots()
    with relative_parent(source, member["relative_path"]) as (original, original_name):
        with bound_file(original, original_name, tuple(json.loads(member["identity"]))) as (reader, _):
            while True:
                progress.check()
                block = os.read(reader, 1024 * 1024)
                if not block:
                    break
                output.write(block)
                progress.wrote(len(block))
            output.flush()
            os.fsync(output.fileno())


def _copy_member(source, stage, name, temporary, member, record):
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o666, dir_fd=stage)
    with os.fdopen(fd, "wb") as output:
        if record:
            record(name, temporary, fd)
        _write_member(source, output, member)
    flat.member_proof(stage, temporary, member, check=progress.check)
    host.rename_noreplace(stage, temporary, stage, name)
    os.fsync(stage)
    progress.checkpoint(member["size_bytes"])


def _copy_unnamed_member(source, stage, name, member, record=None):
    # ZFS creates an unlinked inode. Inherited Workspace ACLs cannot expose
    # it through a path, and closing the descriptor discards an interrupted copy.
    with os.fdopen(_open_unnamed(stage), "w+b") as output:
        _write_member(source, output, member)
        fd = output.fileno()
        info = os.fstat(fd)
        if info.st_nlink != 0 or info.st_size != member["size_bytes"] or bound_sha256(fd, progress.check) != member["sha256"]:
            raise AdoptionError("Die vorhandene Arbeitskopie weicht von der Inventur ab: " + name)
        validate_active_roots()
        # linkat follows this descriptor symlink without CAP_DAC_READ_SEARCH.
        # The destination name is created exclusively; no existing file is replaced.
        try:
            if record:
                record(name, None, fd)
            os.link(f"/proc/self/fd/{fd}", name, dst_dir_fd=stage)
        except PermissionError as error:
            raise ReviewStagingError("linkat verified inode", error) from error
        os.fsync(fd)
        os.fsync(stage)
        progress.checkpoint(member["size_bytes"])


def _verify_family(directory, members, *, require_owner=False, allow_missing=False):
    names = set(os.listdir(directory))
    expected = {name for name, _ in members}
    if names - expected or (not allow_missing and names != expected):
        raise AdoptionError("Die vorbereitete Arbeitskopie enthält unerwartete Dateien.")
    for name, member in members:
        if name in names:
            flat.member_proof(directory, name, member, require_owner=require_owner, check=progress.check)
    return [(name, member) for name, member in members if name not in names]


def _prepare_native_copy(source, stage, members, record):
    remaining = _verify_family(stage, members, require_owner=True, allow_missing=True)
    progress.checkpoint(sum(member["size_bytes"] for _, member in members)
                        - sum(member["size_bytes"] for _, member in remaining), recovered=True)
    _check_capacity(stage, (member for _, member in remaining))
    for name, member in remaining:
        _copy_unnamed_member(source, stage, name, member, record)


def _prepare_private_copy(source, stage, members, record):
    remaining = []
    for index, (name, member) in enumerate(members):
        temporary = ".copy-" + str(index)
        if host.info_at(stage, name) is None:
            _discard_partial(stage, temporary)
            remaining.append((name, temporary, member))
        else:
            flat.member_proof(stage, name, member, check=progress.check)
    _check_capacity(stage, (member for _, _, member in remaining))
    progress.checkpoint(sum(member["size_bytes"] for _, member in members)
                        - sum(member["size_bytes"] for _, _, member in remaining), recovered=True)
    for name, temporary, member in remaining:
        _copy_member(source, stage, name, temporary, member, record)
    secure_working_directory(stage, "review staging")


def _check_capacity(stage, remaining):
    space = os.fstatvfs(stage)
    required = sum(member["size_bytes"] + space.f_frsize for member in remaining)
    if space.f_bavail * space.f_frsize < required:
        raise AdoptionError("Im Workspace ist nicht genug Speicherplatz für die vollständige Dateifamilie.")


def _publish_copy(library, job, members, destination):
    database = library.database_path
    key = members[0][1]["family_key"]
    transfer = progress.transfer()
    batch = transfer.batch if transfer else None
    with ExitStack() as stack:
        source, _ = _roots(stack, library, job)
        root = stack.enter_context(bound_directory(_general(library)))
        with database_connection(database) as connection:
            receipt = flat.receipt(connection, job["id"], key)
            journal = cancel.journal(connection, job["id"], key)
        if receipt:
            _resume_publication(database, root, job, key, destination, receipt, journal)
            return
        existing = host.info_at(root, destination)
        if existing is not None:
            with bound_child_directory(root, destination, directory_identity(existing)) as ready:
                _verify_family(ready, members)
            os.fsync(root)
            for name in (LEGACY_REVIEW_STAGING, LEGACY_REVIEW_PRIVATE_STAGING, LEGACY_REVIEW_VERIFIED_STAGING):
                previous_stage = host.info_at(root, name)
                if previous_stage is not None:
                    with bound_child_directory(root, name, directory_identity(previous_stage)) as stage:
                        os.fsync(stage)
            return
        if not journal and flat.reuse_completed(database, root, job, key, destination, members, batch=batch, check=progress.check):
            return
        if journal:
            if journal["fingerprint"] != destination or journal["parent_name"] not in cancel.STAGE_PARENTS:
                raise AdoptionError(cancel.UNPROVEN)
            if directory_identity(os.fstat(root)) != tuple(json.loads(journal["workspace_identity"])):
                raise AdoptionError(cancel.UNPROVEN)
            stage_name = journal["parent_name"]
            staging = stack.enter_context(bound_child_directory(root, stage_name, tuple(json.loads(journal["parent_identity"]))))
            if stage_name != LEGACY_REVIEW_VERIFIED_STAGING:
                secure_working_directory(staging, stage_name)
        elif _use_unnamed_staging(root):
            stage_name = LEGACY_REVIEW_VERIFIED_STAGING
            staging = stack.enter_context(_verified_directory(root, stage_name))
        else:
            staging, stage_name = _staging(stack, root)
        if stage_name == LEGACY_REVIEW_VERIFIED_STAGING:
            open_stage, prepare = _verified_directory, _prepare_native_copy
        else:
            open_stage, prepare = _new_directory, _prepare_private_copy
        if batch and not journal:
            journal = cancel.write_journal(database, job["id"], key, batch, destination, root, stage_name, staging)
        folder = cancel.folder_name(journal) if journal else destination
        with open_stage(staging, folder) as stage:
            identity = directory_identity(os.fstat(stage))
            if journal:
                cancel.record_directory(database, journal, stage)
                cancel.verify_stage(stage, journal)
            record = partial(cancel.record_inode, database, job["id"], key) if journal else None
            prepare(source, stage, members, record)
            if set(os.listdir(stage)) != {name for name, _ in members}:
                raise AdoptionError("Die vorbereitete Arbeitskopie enthält unerwartete Dateien.")
            manifest = flat.reserve(database, root, stage, job, key, destination, stage_name, members,
                                    batch=journal["batch_id"] if journal else None)
            flat.publish(database, stage, root, job["id"], key, manifest, check=progress.check)
        _complete_publication(database, staging, job["id"], key, folder, identity)


def _complete_publication(database, staging, job_id, key, destination, identity):
    if directory_identity(os.stat(destination, dir_fd=staging, follow_symlinks=False)) != identity:
        raise AdoptionError("Der interne Arbeitsordner wurde ausgetauscht.")
    os.rmdir(destination, dir_fd=staging)
    os.fsync(staging)
    flat.finish(database, job_id, key)


def _resume_publication(database, root, job, key, destination, receipt, journal):
    if (receipt["fingerprint"] != destination
            or tuple(json.loads(receipt["workspace_identity"])) != directory_identity(os.fstat(root))):
        raise AdoptionError("Inventur oder Workspace der unterbrochenen Arbeitskopie haben sich geändert.")
    if receipt["owns_files"] and (not journal or receipt["batch_id"] != journal["batch_id"]):
        raise AdoptionError(cancel.UNPROVEN)
    manifest = json.loads(receipt["members_json"])
    if receipt["state"] == "copied":
        flat.verify_published(root, manifest, progress.check)
        return
    stage_name = receipt["stage_name"]
    if stage_name not in {LEGACY_REVIEW_STAGING, LEGACY_REVIEW_PRIVATE_STAGING, LEGACY_REVIEW_VERIFIED_STAGING}:
        raise AdoptionError("Der interne Arbeitsordner ist ungültig.")
    folder = cancel.folder_name(journal) if journal else destination
    info = host.info_at(root, stage_name)
    if info is not None:
        parent_identity = tuple(json.loads(journal["parent_identity"])) if journal else directory_identity(info)
        with bound_child_directory(root, stage_name, parent_identity) as staging:
            info = host.info_at(staging, folder)
            if info is not None:
                identity = tuple(json.loads(journal["stage_identity"])) if journal else directory_identity(info)
                with bound_child_directory(staging, folder, identity) as stage:
                    if stage_name != LEGACY_REVIEW_VERIFIED_STAGING:
                        secure_working_directory(staging, stage_name)
                        secure_working_directory(stage, folder)
                    flat.publish(database, stage, root, job["id"], key, manifest, check=progress.check)
                _complete_publication(database, staging, job["id"], key, folder, identity)
                return
            os.fsync(staging)
    flat.verify_published(root, manifest, progress.check)
    os.fsync(root)
    flat.finish(database, job["id"], key)


def _copy_response(connection, row):
    result = dict(row)
    result["target_files"] = flat.target_files(connection, row["job_id"], row["family_key"])
    if result["target_files"]:
        result["target_relative"] = None
    return result


def copy_review(library, job_id, key):
    transfer = progress.transfer()
    batch = transfer.batch if transfer else None
    progress.check(force=True)
    with database_connection(library.database_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        job = dict(_job(connection, library.library_id, job_id))
        plan = _plan_for(connection, job_id)
        if not _copy_allowed(job, plan):
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
            return _copy_response(connection, previous)
        draft = json.loads(job["draft_json"])
        if key in draft.get("metadata_review_pending", {}):
            raise AdoptionError("Entferne zuerst die vorgemerkte Metadatenquelle.")
        if not plan and not previous and _confirmed(draft, key):
            raise AdoptionError("Diese Familie ist kein ausstehender Prüffall.")
        members = [(Path(item["relative_path"]).name, dict(item)) for item in connection.execute(
            """SELECT relative_path, family_key, size_bytes, identity, sha256, error FROM legacy_adoption_inventory
                WHERE job_id = ? AND family_key = ? ORDER BY relative_path""",
            (job_id, key),
        )]
        if not members or any(not item["sha256"] or not item["identity"] or item["error"] for _, item in members):
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
                (job_id, family_key, state, target_relative, file_count, size_bytes, batch_id)
                VALUES (?, ?, 'copying', ?, ?, ?, ?)""",
            (job_id, key, destination, len(members), sum(item["size_bytes"] for _, item in members), batch),
        )
    _publish_copy(library, job, members, destination)
    with database_connection(library.database_path) as connection:
        connection.execute(
            """UPDATE legacy_adoption_review_copies SET state = 'copied', target_relative = ?,
                       file_count = ?, size_bytes = ?, updated_at = CURRENT_TIMESTAMP
                WHERE job_id = ? AND family_key = ?""",
            (destination, len(members), sum(item["size_bytes"] for _, item in members), job_id, key),
        )
        return _copy_response(connection, connection.execute(
            "SELECT * FROM legacy_adoption_review_copies WHERE job_id = ? AND family_key = ?", (job_id, key),
        ).fetchone())


def review_batch_status(connection, job_id):
    result = dict(connection.execute(
        """SELECT count(*) AS total, count(*) FILTER (WHERE state = 'pending') AS pending,
                  count(*) FILTER (WHERE state = 'copied') AS copied,
                  count(*) FILTER (WHERE state = 'failed') AS failed
             FROM legacy_adoption_review_batch WHERE job_id = ?""",
        (job_id,),
    ).fetchone())
    current = cancel.run(connection, job_id)
    if current:
        result.update(batch_id=current["id"], state=current["state"], cancel_error=current["error"])
    return result


def begin_review_batch(library, job_id, keys):
    with database_connection(library.database_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        job = _job(connection, library.library_id, job_id)
        status = review_batch_status(connection, job_id)
        if status["pending"] or status.get("state") in {"active", "cancelling"}:
            raise AdoptionError("Setze zuerst den unterbrochenen Kopierauftrag fort.")
        eligible = _copyable_cases(connection, job_id, job, _plan_for(connection, job_id))
        if keys is not None:
            selected = set(keys)
            eligible = [key for key in eligible if key in selected]
        if not eligible:
            raise AdoptionError("Keine geeigneten Prüffälle ausgewählt.")
        connection.execute("DELETE FROM legacy_adoption_review_batch WHERE job_id = ?", (job_id,))
        connection.executemany(
            """INSERT INTO legacy_adoption_review_batch (job_id, family_key, bytes_total)
               SELECT ?, ?, coalesce(sum(size_bytes), 0) FROM legacy_adoption_inventory
               WHERE job_id = ? AND family_key = ?""",
            ((job_id, key, job_id, key) for key in eligible),
        )
        return cancel.start(connection, job_id)


def run_review_batch(library, job_id, *, copy_family):
    while True:
        with database_connection(library.database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            current = cancel.run(connection, job_id)
            if current and current["state"] != "active":
                return
            batch = current["id"] if current else None
            row = connection.execute(
                """SELECT family_key FROM legacy_adoption_review_batch
                    WHERE job_id = ? AND state = 'pending' ORDER BY family_key LIMIT 1""",
                (job_id,),
            ).fetchone()
            if row is None:
                if batch:
                    connection.execute(
                        "UPDATE legacy_adoption_review_runs SET state = 'finished' WHERE job_id = ? AND id = ?",
                        (job_id, batch),
                    )
                return
        key = row["family_key"]
        try:
            with progress.track(library.database_path, job_id, key, batch):
                copy_family(key)
        except cancel.CancelRequested:
            return
        except ReviewStagingError as error:
            logger.warning("Legacy review staging %s: %s (%s)", job_id, error.operation, error.code)
            fail_pending_review_batch(library, job_id, str(error))
            continue
        except OSError as error:
            message = str(error)
            if error.errno == errno.ENOSPC:
                message = "Im Workspace ist nicht genug Speicherplatz für die vollständige Dateifamilie."
        except (AdoptionError, DatasetError, MetadataCorrectionError, RootOperationError) as error:
            message = str(error)
        else:
            message = None
        with database_connection(library.database_path) as connection:
            connection.execute(
                """UPDATE legacy_adoption_review_batch SET state = ?, error = ?,
                       bytes_verified = CASE WHEN ? THEN bytes_verified ELSE bytes_total END
                    WHERE job_id = ? AND family_key = ?""",
                ("failed" if message else "copied", message[:2000] if message else None, bool(message), job_id, key),
            )


def fail_pending_review_batch(library, job_id, message):
    with database_connection(library.database_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        current = cancel.run(connection, job_id)
        if current and current["state"] != "active":
            return
        connection.execute(
            """UPDATE legacy_adoption_review_batch SET state = 'failed', error = ?
                WHERE job_id = ? AND state = 'pending'""",
            (message[:2000], job_id),
        )
        if current:
            connection.execute("UPDATE legacy_adoption_review_runs SET state = 'finished' WHERE job_id = ?", (job_id,))


def _cancel_stage(database, root, entry, receipt):
    name = entry["parent_name"]
    if (name not in cancel.STAGE_PARENTS
            or directory_identity(os.fstat(root)) != tuple(json.loads(entry["workspace_identity"]))):
        raise AdoptionError(cancel.UNPROVEN)
    folder = cancel.folder_name(entry)
    members = json.loads(entry["members_json"])
    if receipt and (receipt["batch_id"] != entry["batch_id"] or not receipt["owns_files"]):
        raise AdoptionError(cancel.UNPROVEN)
    published = {member["name"]: member for member in json.loads(receipt["members_json"])} if receipt else {}
    with ExitStack() as stack:
        parent = stack.enter_context(bound_child_directory(root, name, tuple(json.loads(entry["parent_identity"]))))
        private = name != LEGACY_REVIEW_VERIFIED_STAGING
        if private:
            secure_working_directory(parent, name)
        stage = None
        if host.info_at(parent, folder) is not None:
            if entry["stage_identity"] is None:
                raise AdoptionError(cancel.UNPROVEN)
            stage = stack.enter_context(bound_child_directory(parent, folder, tuple(json.loads(entry["stage_identity"]))))
            if private:
                secure_working_directory(stage, folder)
            cancel.verify_stage(stage, entry)
        for member, record in members.items():
            if record.get("removed"):
                continue
            proof = published.get(member)
            qname = ".cancel-" + hashlib.sha256(host.json_bytes([entry["job_id"], entry["family_key"], folder, member])).hexdigest()
            positions = [member, record["temporary"]] if record["temporary"] else [member]
            for index, position in enumerate(positions):
                quarantine = qname + str(index)
                if host.info_at(parent, quarantine) is not None or (stage is not None and host.info_at(stage, position) is not None):
                    if stage is None:
                        raise AdoptionError(cancel.UNPROVEN)
                    cancel.remove_owned(stage, position, parent, quarantine, record["identity"])
                    break
            else:
                if proof:
                    if tuple(proof["identity"]) != tuple(record["identity"]):
                        raise AdoptionError(cancel.UNPROVEN)
                    cancel.remove_owned(root, proof["target"], parent, qname,
                                        record["identity"], lambda fd, path: flat.member_proof(fd, path, proof,
                                            require_owner=True, identity=record["identity"]))
            record["removed"] = True
            with database_connection(database) as connection:
                connection.execute(
                    "UPDATE legacy_adoption_review_stages SET members_json = ? WHERE job_id = ? AND family_key = ?",
                    (json.dumps(members), entry["job_id"], entry["family_key"]),
                )
        if stage is not None:
            if os.listdir(stage):
                raise AdoptionError(cancel.UNPROVEN)
            os.fsync(stage)
    with bound_child_directory(root, name, tuple(json.loads(entry["parent_identity"]))) as parent:
        if stage is not None:
            if directory_identity(os.stat(folder, dir_fd=parent, follow_symlinks=False)) != tuple(json.loads(entry["stage_identity"])):
                raise AdoptionError(cancel.UNPROVEN)
            validate_active_roots()
            os.rmdir(folder, dir_fd=parent)
            os.fsync(parent)


def finish_review_cancellation(library, job_id):
    database = library.database_path
    with database_connection(database) as connection:
        current = cancel.run(connection, job_id)
        if not current or current["state"] != "cancelling":
            return
        batch = current["id"]
        entries = connection.execute(
            "SELECT * FROM legacy_adoption_review_stages WHERE job_id = ? AND batch_id = ? ORDER BY family_key",
            (job_id, batch),
        ).fetchall()
    try:
        if entries:
            with bound_directory(_general(library)) as root:
                for entry in entries:
                    with database_connection(database) as connection:
                        receipt = flat.receipt(connection, job_id, entry["family_key"])
                    _cancel_stage(database, root, entry, receipt)
        with database_connection(database) as connection:
            connection.execute("BEGIN IMMEDIATE")
            parameters = (job_id, batch)
            for table in ("legacy_adoption_flat_review_copies", "legacy_adoption_review_copies", "legacy_adoption_review_stages"):
                connection.execute(f"DELETE FROM {table} WHERE job_id = ? AND batch_id = ?", parameters)
            connection.execute("DELETE FROM legacy_adoption_review_batch WHERE job_id = ?", (job_id,))
            connection.execute(
                "UPDATE legacy_adoption_review_runs SET state = 'cancelled', error = NULL WHERE job_id = ? AND id = ?",
                parameters,
            )
    except (AdoptionError, OSError, host.ExecutionError, RootOperationError, PrivateStorageError) as error:
        logger.warning("Legacy review cancellation %s: %s", job_id, error)
        with database_connection(database) as connection:
            connection.execute(
                "UPDATE legacy_adoption_review_runs SET error = ? WHERE job_id = ? AND id = ?",
                (cancel.UNPROVEN, job_id, batch),
            )
