"""Read-only qualification of an RC14 pre-journal metadata abort.

This is NOT prospective swap ownership and never allows a missing-journal
rollback. RC14's global reintegration key lacked family_id. Its old writer
verified each source against the stored wall clock BEFORE staging the first
file or creating a swap journal. We settle this key only when every potential
corrected Undated family provably fails that exact original preflight and all
its originals still agree with the completed correction receipts.
"""
from pathlib import Path
from contextlib import closing
import hashlib
import json
import os
import stat

from app import operation_health as health


def _refuse(reason):
    raise health.DomainStartupError("scoped_metadata_legacy_prejournal_"+reason)


def _file_identity(path, expected_sha, expected_size):
    a=path.lstat()
    if (not stat.S_ISREG(a.st_mode) or a.st_nlink!=1
        or path.resolve()!=path or a.st_size!=expected_size):
        _refuse("source_inode_or_size_changed")
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    b=path.lstat()
    if ((a.st_dev,a.st_ino,a.st_size,a.st_mtime_ns,a.st_ctime_ns)
        != (b.st_dev,b.st_ino,b.st_size,b.st_mtime_ns,b.st_ctime_ns)
        or digest!=expected_sha):
        _refuse("source_bytes_changed")
    return (a.st_dev,a.st_ino,digest)


def qualify(record, owner, parent, metadata):
    from app.metadata_abort_recovery import _binding
    from app.import_recovery import _catalogue_identity
    from app.metadata_correction import (
        MetadataCorrectionError, metadata_area_paths, verify_metadata_datetime,
    )
    from app.metadata_swap_recovery import _journal_dir
    from app.storage_config import storage_paths
    from app.managed_directory_names import is_undated_name

    # Only the old, exactly unscoped F14 key, never a modern family-scoped
    # write or a different operation, qualifies for the retrospective check.
    if record.get("ids")!={"function":"app.metadata_correction.reintegrate_library_metadata_family"}:
        _refuse("not_legacy_unscoped_key")
    _binding(record,owner)
    if record.get("library")!=owner.get("library_id"):
        _refuse("owner_changed")
    directory=_journal_dir(metadata)
    if directory.is_symlink() or (os.path.lexists(directory) and not directory.is_dir()):
        _refuse("journal_exists_or_unsafe")
    # RC14 creates this directory only when it has a physical swap plan.
    # A pre-verification refusal normally leaves it absent altogether.
    if directory.is_dir() and any(directory.iterdir()):
        _refuse("journal_exists_or_unsafe")
    # A separate missing prospective proof is not reinterpreted as ownership.
    if any(parent.glob("metadata-scoped-ownership-*.json")):
        _refuse("other_original_swap_proof_exists")
    db=Path(record["database"])
    catalogue=_catalogue_identity(db)
    stock=storage_paths(Path(record["workspace"]))["backup_root"].absolute()
    output=metadata_area_paths(area="library",workspace_root=Path(record["workspace"]),
                               library_id=record["library"],create=False)["output_root"].absolute()
    if stock!=output:
        _refuse("stock_root_changed")
    with closing(health.read_connection(db)) as c:
        if c.execute("PRAGMA integrity_check").fetchone()[0]!="ok" or c.execute("PRAGMA foreign_key_check").fetchall():
            _refuse("database_integrity")
        families=[dict(row) for row in c.execute(
            "SELECT DISTINCT ff.id,ff.job_id,ff.family_key,ff.selected_capture_time "
            "FROM file_families ff JOIN files f ON f.family_id=ff.id "
            "WHERE f.review_status='corrected' AND f.metadata_write_status='written' "
            "ORDER BY ff.id")]
        if not families:
            _refuse("no_completed_corrected_families")
        tasks=[dict(row) for row in c.execute(
            "SELECT status,detected_json,verification_json,proposed_datetime "
            "FROM metadata_corrections WHERE area='library'")]
        members={family["id"]:[dict(x) for x in c.execute(
            "SELECT id,job_id,current_relative_path,size_bytes,sha256_current,sha256_original,"
            "review_status,metadata_write_status,selected_capture_time "
            "FROM files WHERE family_id=? ORDER BY id",(family["id"],))] for family in families}
    proof=[]
    for family in families:
        stored=str(family["selected_capture_time"] or "")
        if not stored or len(stored)!=19:
            _refuse("original_timestamp_not_truncated")
        rows=members[family["id"]]
        if not rows or any(x["review_status"]!="corrected" or x["metadata_write_status"]!="written"
                           or str(x["selected_capture_time"] or "")!=stored for x in rows):
            _refuse("partial_family_or_changed_timestamp")
        matches=[]
        for task in tasks:
            if task["status"]!="completed":
                continue
            try:
                d=json.loads(task["detected_json"] or "{}")
                v=json.loads(task["verification_json"] or "{}")
            except (TypeError,ValueError):
                _refuse("invalid_correction_receipt")
            if (str(d.get("family_id") or "")==str(family["id"])
                and d.get("job_id")==family["job_id"]
                and d.get("family_key")==family["family_key"]
                and bool(v.get("reintegration_pending"))):
                matches.append(v)
        if len(matches)!=1:
            _refuse("completed_receipt_missing_or_ambiguous")
        v=matches[0]
        receipt_members=v.get("members")
        if not isinstance(receipt_members,list) or len(receipt_members)!=len(rows):
            _refuse("receipt_membership_changed")
        by_id={int(x["file_id"]):x for x in receipt_members}
        if len(by_id)!=len(rows) or set(by_id)!={x["id"] for x in rows}:
            _refuse("receipt_file_ids_changed")
        for row in rows:
            relative=Path(str(row["current_relative_path"] or ""))
            if (relative.is_absolute() or len(relative.parts)<2
                or not is_undated_name(relative.parts[0]) or ".." in relative.parts):
                _refuse("original_not_in_undated_stock")
            path=(stock/relative).absolute()
            if not path.is_relative_to(stock):
                _refuse("source_outside_stock")
            rec=by_id[row["id"]]
            sha=str(row["sha256_current"] or row["sha256_original"] or "")
            if (rec.get("output_sha256")!=sha
                or int(rec.get("output_size_bytes") or -1)!=int(row["size_bytes"])
                or rec.get("output_relative_path")!=str(relative)):
                _refuse("completed_receipt_file_changed")
            original=_file_identity(path,sha,int(row["size_bytes"]))
            # In RC14 this verification occurs before copy/staging, journal
            # creation, SQL updates, or any original-file rename. If it
            # succeeds for ANY candidate, the legacy lease may represent a
            # later state, so the unscoped orphan must remain fenced.
            try:
                verify_metadata_datetime(path,stored)
            except MetadataCorrectionError as error:
                if not str(error).startswith(
                    "Die geschriebenen Aufnahmeinformationen konnten nicht bestätigt werden."):
                    _refuse("unexpected_original_preflight_failure")
            else:
                _refuse("original_preflight_could_have_passed")
            proof.append([str(path),*original])
    if catalogue!=_catalogue_identity(db):
        _refuse("catalogue_identity_changed")
    return {"format":1,"reservation":record,"catalogue":catalogue,
            "status":"rc14_original_prejournal_refusal_verified",
            "files":proof}
