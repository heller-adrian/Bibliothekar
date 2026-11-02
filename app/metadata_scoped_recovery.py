"""Prospective F14-bound rollback for multiple/reintegration metadata swaps.

No historical journal is granted new ownership after a crash. Only an original
private proof written BEFORE the first rename can authorize an inode-pinned
rollback. Ambiguous, committed, foreign or legacy states stay write-fenced.
"""
from pathlib import Path
from contextlib import closing,contextmanager
from contextvars import ContextVar
from threading import get_ident
import hashlib
import os
import stat

from app import root_operations as ro, operation_health as health

_APPROVED=ContextVar('scoped_original_metadata_retry',default=None)


@contextmanager
def _allow_exact_original(record):
    """Capability is synchronous and tied to the existing full F14 record."""
    token=_APPROVED.set(record)
    try:yield
    finally:_APPROVED.reset(token)


def approved(record):
    return record is not None and _APPROVED.get()==record


FUNCTIONS={
    "multiple": "app.metadata_correction.apply_multiple_metadata_correction",
    "reintegrate": "app.metadata_correction.reintegrate_library_metadata_family",
}


def _refuse(reason):
    raise health.DomainStartupError("scoped_metadata_recovery_"+reason)


def _physical_writer(record):
    from app.metadata_correction import _WRITER_HELD
    return any(pid==os.getpid() and tid==get_ident()
               and ro.canonical_workspace(Path(root))==Path(record["workspace"])
               for root,pid,tid in _WRITER_HELD.get())


def _inode(path, digest):
    path=Path(path)
    a=path.lstat()
    if not stat.S_ISREG(a.st_mode) or a.st_nlink!=1 or path.resolve()!=path:
        _refuse("nonexclusive_original_file")
    actual=hashlib.sha256(path.read_bytes()).hexdigest()
    b=path.lstat()
    if (a.st_dev,a.st_ino,a.st_size,a.st_mtime_ns,a.st_ctime_ns)!=(
        b.st_dev,b.st_ino,b.st_size,b.st_mtime_ns,b.st_ctime_ns) or actual!=digest:
        _refuse("original_bytes_or_inode_changed")
    return [a.st_dev,a.st_ino]


def _snapshot(db,kind,family):
    if kind!="reintegrate":
        return None
    with closing(health.read_connection(db)) as c:
        rows=[dict(x) for x in c.execute(
            "SELECT id,job_id,family_id,current_relative_path,sha256_current,sha256_original "
            "FROM files WHERE family_id=? ORDER BY id",(int(family),))]
        owner=c.execute("SELECT library_id FROM library_identity WHERE singleton=1").fetchone()
    if not rows or owner is None:
        _refuse("family_or_internal_database_owner_missing")
    return {"owner":owner["library_id"],"rows":rows}


def bind_prepared_swap(metadata,journal,data):
    """Called within the original physical metadata writer, before any rename."""
    kind=data.get("kind")
    if kind not in FUNCTIONS:
        return
    record=next((r for r in reversed(ro._ACTIVE.get())
                 if r.get("kind")=="metadata"
                 and r.get("ids",{}).get("function")==FUNCTIONS[kind]),None)
    if record is None:
        return  # Unregistered legacy call: NEVER invent an owner for it.
    if record.get("_resumed") or not _physical_writer(record):
        _refuse("no_original_physical_writer")
    from app.metadata_abort_recovery import _binding, _owner, _plain
    from app.import_recovery import _catalogue_identity
    from app.storage_config import storage_paths
    # A multiple-folder operation may have no database in an unregistered
    # fixture. Missing registry ownership must fail closed with a domain error,
    # never an incidental Path(None) TypeError.
    database=record.get("database")
    owner=_owner(database) if database is not None else None
    if not owner or owner["library_id"]!=record["library"]:
        _refuse("registered_owner_missing")
    plain=_plain(record)
    parent,_=_binding(plain,owner)
    ids=record["ids"]
    if kind=="multiple":
        if set(ids)!={"function","reference_relative_path","expected_preview_fingerprint"}:
            _refuse("original_multiple_key_incomplete")
        from app.metadata_correction import metadata_area_paths
        root=metadata_area_paths(area="multiple",workspace_root=Path(record["workspace"]),
                                 library_id=record["library"],create=False)["root"].absolute()
    else:
        if set(ids)!={"function","family_id"} or ids["family_id"]!=str(data["family_id"]):
            _refuse("original_family_key_mismatch")
        root=storage_paths(Path(record["workspace"]))["backup_root"].absolute()
    if (Path(data["root"]).absolute()!=root or data["state"]!="prepared"
        or Path(journal).parent!=Path(metadata)/".swap-journals"
        or not isinstance(data["files"],list) or not data["files"]):
        _refuse("original_journal_scope_mismatch")
    if kind=="reintegrate" and data["database"]!=str(Path(record["database"]).absolute()):
        _refuse("journal_database_mismatch")
    owned={}
    for item in data["files"]:
        for key,digest in (("source","before_sha"),("incoming","after_sha")):
            p=Path(item[key])
            if not p.is_relative_to(root):
                _refuse("original_file_outside_registered_root")
            owned[str(p)]=_inode(p,item[digest])
        for key in ("backup","destination"):
            if key in item and os.path.lexists(item[key]):
                _refuse("prepublication_endpoint_already_occupied")
    db_snapshot=_snapshot(record["database"],kind,data.get("family_id"))
    if db_snapshot:
        by_id={row["id"]:row for row in db_snapshot["rows"]}
        if (db_snapshot["owner"]!=owner["library_id"]
            or set(by_id)!={i["file_id"] for i in data["files"]}
            or any((by_id[i["file_id"]]["sha256_current"]
                    or by_id[i["file_id"]]["sha256_original"])!=i["before_sha"]
                   for i in data["files"])):
            _refuse("original_database_membership_mismatch")
    proof={"format":1,"reservation":plain,"journal":str(journal),"swap":data,
           "owned":owned,"catalogue":_catalogue_identity(record["database"]),
           "snapshot":db_snapshot}
    path=parent/("metadata-scoped-ownership-"+record["reservation_id"]+".json")
    old=ro._read(path,None)
    if old is not None and old!=proof:
        _refuse("prospective_proof_collision")
    if old is None:
        ro._write(path,proof)


def _qualify(record,owner,parent,metadata):
    from app.metadata_abort_recovery import _binding
    from app.metadata_swap_recovery import _load,_database_state,_preflight_rollback
    from app.storage_config import storage_paths
    from app.import_recovery import _catalogue_identity
    _binding(record,owner)
    kind=next((k for k,v in FUNCTIONS.items() if v==record["ids"].get("function")),None)
    if kind is None:
        _refuse("unrecognized_function")
    proof=ro._read(parent/("metadata-scoped-ownership-"+record["reservation_id"]+".json"),None)
    if not isinstance(proof,dict) or proof.get("format")!=1 or proof.get("reservation")!=record:
        _refuse("original_prospective_proof_missing")
    data=proof.get("swap")
    if (not isinstance(data,dict) or data.get("kind")!=kind or data.get("state")!="prepared"
        or proof.get("catalogue")!=_catalogue_identity(record["database"])):
        _refuse("prospective_proof_or_catalogue_changed")
    ids=record["ids"]
    if kind=="multiple":
        if set(ids)!={"function","reference_relative_path","expected_preview_fingerprint"}:
            _refuse("original_selection_changed")
        from app.metadata_correction import metadata_area_paths
        root=metadata_area_paths(area="multiple",workspace_root=Path(record["workspace"]),
                                 library_id=record["library"],create=False)["root"].absolute()
    else:
        if set(ids)!={"function","family_id"} or ids["family_id"]!=str(data.get("family_id")):
            _refuse("original_family_changed")
        root=storage_paths(Path(record["workspace"]))["backup_root"].absolute()
        if data.get("database")!=str(Path(record["database"]).absolute()):
            _refuse("original_database_changed")
    if Path(data.get("root","")).absolute()!=root:
        _refuse("original_source_root_changed")
    if proof.get("snapshot")!=_snapshot(record["database"],kind,data.get("family_id")):
        _refuse("original_sql_membership_changed")
    journal=Path(proof.get("journal",""))
    directory=Path(metadata)/".swap-journals"
    if (directory.is_symlink() or not directory.is_dir()
        or journal.parent!=directory or journal.suffix!=".json"
        or len(data.get("files",[]))<1):
        _refuse("journal_directory_or_identity_changed")
    live=list(directory.iterdir())
    if live and (live!=[journal] or _load(journal,metadata)!=data):
        _refuse("foreign_or_modified_swap_journal")
    owned=proof.get("owned")
    if not isinstance(owned,dict) or len(owned)!=2*len(data["files"]):
        _refuse("original_inode_evidence_incomplete")
    for item in data["files"]:
        old=tuple(owned.get(item["source"],()))
        new=tuple(owned.get(item["incoming"],()))
        if len(old)!=2 or len(new)!=2 or old==new:
            _refuse("original_inode_evidence_ambiguous")
        for key in ("source","backup","incoming","destination"):
            if key not in item or not os.path.lexists(item[key]):
                continue
            p=Path(item[key]);s=p.lstat()
            allowed={old,new} if key=="source" else {old} if key=="backup" else {new}
            if (not p.is_relative_to(root) or not stat.S_ISREG(s.st_mode)
                or s.st_nlink!=1 or p.resolve()!=p or (s.st_dev,s.st_ino) not in allowed):
                _refuse("foreign_inode_at_original_endpoint")
    if _database_state(data)!="prepared":
        _refuse("committed_or_ambiguous_effects")
    if live:
        _preflight_rollback(data)
    else:
        for item in data["files"]:
            p=Path(item["source"])
            if (not p.is_file() or _inode(p,item["before_sha"])!=owned[item["source"]]
                or any(os.path.lexists(item[k]) for k in ("backup","incoming","destination") if k in item)):
                _refuse("missing_journal_without_complete_rollback")
    return journal,data,owned


def recover(workspace, *, allow_legacy_prejournal=False):
    from app.metadata_abort_recovery import _owner,_binding
    from app.metadata_swap_recovery import metadata_write_guard,recover_swap_journal
    from app.storage_config import storage_paths
    from app.storage_anchors import check_active
    status=health.inspect(workspace)
    dead=[x for x in status["reservations"] if not x["live"]]
    if (len(dead)!=1 or any(x["live"] for x in status["reservations"])
        or not dead[0]["qualified"] or dead[0].get("kind")!="metadata"
        or dead[0].get("ids",{}).get("function") not in FUNCTIONS.values()):
        return False
    record=ro._read(Path(dead[0]["path"]))
    owner=_owner(record.get("database"))
    if not owner:
        return False
    parent,_=_binding(record,owner)
    metadata=storage_paths(Path(workspace))["metadata_root"]
    with metadata_write_guard(metadata):
        # The immutable RC14 release used a family-less F14 reintegration
        # reservation and did not write prospective swap ownership. Its
        # original EXIF verification could fail BEFORE any swap journal. Do
        # not manufacture a prospective proof: accept only a separate,
        # retrospectively verified *negative* prejournal result.
        legacy=None
        try:
            journal,data,owned=_qualify(record,owner,parent,metadata)
        except health.DomainStartupError as error:
            if str(error)!="scoped_metadata_recovery_original_prospective_proof_missing":
                raise
            if not allow_legacy_prejournal:
                raise  # Startup MUST preserve the original historical reservation.
            from app.metadata_legacy_rc14_recovery import qualify as qualify_legacy
            legacy=qualify_legacy(record,owner,parent,metadata)
            journal=data=owned=None
        intent=parent/("domain-recovery-intent-"+record["reservation_id"]+".json")
        expected={"format":1,"reservation":record,"phase":"qualified_recovery_not_finished"}
        old=ro._read(intent,None)
        if old is not None and old!=expected:
            _refuse("original_replay_intent_changed")
        if old is None:
            ro._write(intent,expected)
        with health.qualified_retry(workspace,{dead[0]["path"]}):
            with _allow_exact_original(record), ro.reserve(workspace,library_id=record["library"],database=record["database"],
                            kind="metadata",ids=record["ids"],paths=[Path(p) for p in record["bindings"]],
                            expected_generation=record["generation"],_recovery_record=record):
                if legacy is not None:
                    from app.metadata_legacy_rc14_recovery import qualify as qualify_legacy
                    if qualify_legacy(record,owner,parent,metadata)!=legacy:
                        _refuse("legacy_negative_proof_changed_under_lock")
                else:
                    again,saved,identities=_qualify(record,owner,parent,metadata)
                    if again!=journal or saved!=data or identities!=owned:
                        _refuse("original_plan_changed_under_lock")
                    if journal.exists():
                        outcome=recover_swap_journal(metadata,journal,
                                   allowed_databases={Path(record["database"])},
                                   owned_identities=owned)
                        if outcome!="rolled_back":
                            _refuse("unverified_rollback")
                    _qualify(record,owner,parent,metadata)
                ro._check(record["bindings"]);check_active(workspace,parent)
                path=parent/("metadata-scoped-outcome-"+record["reservation_id"]+".json")
                outcome=({"format":1,"reservation":record,
                          "disposition":"verified_legacy_prejournal_no_effect",
                          "negative_evidence":legacy}
                         if legacy is not None else
                         {"format":1,"reservation":record,
                          "journal":str(journal),"disposition":"original_precommit_rollback_verified"})
                old=ro._read(path,None)
                if old is not None and old!=outcome:
                    _refuse("durable_outcome_changed")
                if old is None:
                    ro._write(path,outcome)
            health.finish_qualified_retry(workspace)
    return True
