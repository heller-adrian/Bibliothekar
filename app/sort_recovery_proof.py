"""Qualify one original pre-commit sort journal, never infer a new media plan.

Only camera-file runs within registered central/work anchors are admitted here.
Unsupported assets, committed runs, foreign bytes, duplicate endpoints and
unbound roots retain their original F14 fence for separate qualification.
"""
from contextlib import closing
from pathlib import Path
import hashlib,json,os,stat

FUNCTIONS={'app.sort_apply.execute_sort_run','app.workspace_reconcile.execute_workspace_reconcile_run'}


def qualify(database,workspace,owner,run_id,*,finished=False):
    from app.operation_health import read_connection,DomainStartupError
    from app.sort_apply import _safe_relative,_verify_recovery_copy
    from app.storage_config import storage_paths
    def refuse(detail):raise DomainStartupError('sort_recovery_'+detail)
    if not isinstance(run_id,str) or not run_id or '/' in run_id or '\\' in run_id:
        refuse('invalid_run_identity')
    with closing(read_connection(Path(database))) as connection:
        identity=connection.execute('SELECT library_id FROM library_identity WHERE singleton=1').fetchone()
        if identity is None or identity['library_id']!=owner['library_id']:refuse('catalogue_library_identity_mismatch')
        row=connection.execute('SELECT * FROM sort_runs WHERE id=?',(run_id,)).fetchone()
        if row is None:refuse('missing_run')
        run=dict(row)
        if run['status'] not in {'queued','verifying','moving','finalizing','rolling_back','interrupted','rolled_back'}:
            refuse('requires_separate_committed_outcome_proof')
        if finished and run['status']!='rolled_back':refuse('rollback_not_finished')
        if not connection.execute('SELECT 1 FROM jobs WHERE id=?',(run['job_id'],)).fetchone():
            refuse('missing_original_job')
        if not connection.execute('SELECT 1 FROM events WHERE id=? AND job_id=?',(run['event_id'],run['job_id'])).fetchone():
            refuse('missing_original_event')
        if connection.execute('SELECT 1 FROM sort_asset_operations WHERE sort_run_id=?',(run_id,)).fetchone():
            refuse('asset_scope_requires_separate_qualification')
        operations=[dict(r) for r in connection.execute(
            'SELECT * FROM sort_operations WHERE sort_run_id=? ORDER BY sequence_number,id',(run_id,))]
        if not operations or len(operations)!=int(run['file_count']):refuse('incomplete_operation_set')
        files={r['file_id']:dict(connection.execute('SELECT * FROM files WHERE id=?',(r['file_id'],)).fetchone() or {}) for r in operations}
    central=storage_paths(Path(workspace))['backup_root'].absolute()
    work=Path(owner['work_root']).absolute()
    if Path(run['target_root']).absolute()!=work or Path(run['central_root']).absolute()!=central:
        refuse('run_roots_not_registered')
    source_root=Path(run['source_root']).absolute()
    if source_root not in {central,work}:refuse('source_root_not_registered')
    paths=[];file_ids=set()
    for operation in operations:
        fid=operation['file_id'];file=files[fid]
        if fid in file_ids or not file or file['job_id']!=run['job_id']:refuse('catalogue_owner_mismatch')
        file_ids.add(fid)
        if (file['current_relative_path']!=operation['source_relative_path']
            or file['current_root_kind']!=operation['source_root_kind']
            or int(file['size_bytes'])!=int(operation['expected_size_bytes'])
            or (file.get('sha256_current') or file.get('sha256_original'))!=operation['expected_sha256']):
            refuse('catalogue_journal_mismatch')
        digest=operation['expected_sha256']
        if not isinstance(digest,str) or len(digest)!=64 or any(c not in '0123456789abcdef' for c in digest):
            refuse('invalid_hash')
        kind=operation['source_root_kind']
        if kind not in {'job_root','shared_workspace','central_stock'}:refuse('unknown_source_role')
        stored=operation.get('source_root_path')
        original=Path(stored).absolute() if stored else (work if run['run_kind']=='reapply' and kind=='shared_workspace' else source_root)
        if original not in {central,work}:refuse('operation_root_not_registered')
        target_kind=operation['destination_root_kind']
        if target_kind not in {'target_root','central_stock'}:refuse('unknown_destination_role')
        source=original/_safe_relative(operation['source_relative_path'])
        destination=(central if target_kind=='central_stock' else work)/_safe_relative(operation['destination_relative_path'])
        for path in {source,destination}:
            # Reject symlinked parents and non-directory replacements. Missing
            # dynamic destination parents are allowed; recovery never trusts
            # them as replacement administrative anchors.
            for ancestor in [*reversed(path.parent.parents),path.parent]:
                if not os.path.lexists(ancestor):continue
                if not stat.S_ISDIR(ancestor.lstat().st_mode):refuse('non_directory_parent: '+str(ancestor))
        present=[p for p in {source,destination} if os.path.lexists(p)]
        if len(present)!=1:refuse('ambiguous_file_endpoints: '+str(source))
        if finished and present!=[source]:refuse('source_not_restored: '+str(source))
        info=present[0].lstat()
        if info.st_nlink!=1:refuse('hardlinked_file: '+str(present[0]))
        _verify_recovery_copy(present[0],operation['expected_size_bytes'],digest)
        paths.append({'source':str(source),'destination':str(destination),'sha256':digest,
                      'bytes':operation['expected_size_bytes'],'file_id':fid})
    stable={key:run[key] for key in ('id','job_id','event_id','source_root','target_root','central_root','plan_token','run_kind')}
    proof={'run':stable,'files':paths}
    return proof,hashlib.sha256(json.dumps(proof,sort_keys=True).encode()).hexdigest()
