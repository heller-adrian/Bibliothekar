"""Finish only a fully qualified general-metadata outcome, preserving its history.

A blocked task or missing journal alone is NEVER an authorization. Domain plans
and outcome receipts retain the complete original reservation and task snapshots.
F14 itself closes the exact lease only after this domain code returns normally.
"""
from contextlib import closing
from contextvars import ContextVar
from dataclasses import dataclass
from functools import wraps
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import stat

from app import root_operations as ro

EXECUTE='app.metadata_correction.execute_metadata_correction'
APPLY='app.metadata_correction.apply_metadata_correction'
_DEPTH=ContextVar('general_metadata_error_delivery_depth',default=0)


@dataclass
class _VerifiedFailure:
    error: Exception


def deliver_verified_error(function):
    """Raise the user error AFTER the owning F14 lease has acknowledged rollback.

    execute -> apply is nested; an internal verified outcome is carried back to
    execute, never serialized to the API or treated as successful correction.
    """
    @wraps(function)
    def call(*args,**kwargs):
        depth=_DEPTH.get();token=_DEPTH.set(depth+1)
        try:
            result=function(*args,**kwargs)
            if isinstance(result,_VerifiedFailure) and depth==0:raise result.error
            return result
        finally:_DEPTH.reset(token)
    return call


def _plain(record):return {k:v for k,v in record.items() if not k.startswith('_')}


def _fail(reason,path):raise ro.RootOperationError('metadata_outcome_'+reason+': '+str(path))


def _owner(database):
    owner=ro._registered(Path(database).absolute())
    if owner and not owner.get('is_registered',True):_fail('library_not_registered',database)
    return owner


def _active(database,workspace):
    return next((r for r in reversed(ro._ACTIVE.get()) if r['kind']=='metadata'
        and r['database']==str(Path(database).absolute()) and r['workspace']==str(Path(workspace).absolute())
        and r['ids'].get('function') in {EXECUTE,APPLY}),None)


def assert_fresh_attempt(database,workspace):
    record=_active(database,workspace)
    if record and record.get('_resumed'):
        _fail('previous_attempt_requires_recovery',record['_path'])


def _task_rows(database,where,values):
    database=Path(database).absolute()
    if not database.is_file() or database.is_symlink():_fail('database_missing',database)
    with closing(sqlite3.connect(database.as_uri()+'?mode=ro',uri=True)) as c:
        c.row_factory=sqlite3.Row;c.execute('BEGIN')
        return [dict(r) for r in c.execute('SELECT * FROM metadata_corrections WHERE '+where,values)]


def _save_once(path,data):
    if os.path.lexists(path):
        if ro._read(path)!=data:_fail('receipt_conflict',path)
    else:ro._write(path,data)


def _paths(workspace):
    from app.storage_config import storage_paths
    from app.managed_directory_names import directory_name
    metadata=Path(storage_paths(workspace)['metadata_root']).absolute()
    general=metadata/directory_name(metadata,'metadata_general')
    if not general.is_dir() or general.resolve()!=general:_fail('general_root_unavailable',general)
    return metadata,general


def _binding(record,owner):
    from app.storage_config import load_storage_settings
    from app.storage_bootstrap import key_for
    from app.appdata import mount
    workspace=Path(owner['workspace_root']).absolute();parent=ro._control_location(workspace)
    path=parent/('operation-'+key_for(record)+'.json')
    if record.get('format')!=1 or record.get('kind')!='metadata' or record.get('shared') is not False:
        _fail('reservation_format',path)
    if record.get('database')!=str(Path(owner['database_path']).absolute()) or record.get('library')!=owner['library_id'] or record.get('workspace')!=str(workspace):
        _fail('reservation_owner',path)
    nonce=record.get('reservation_id','')
    if not isinstance(nonce,str) or not re.fullmatch('[0-9a-f]{32}',nonce):_fail('reservation_id',path)
    state=ro._read(parent/'state.json',{})
    if state.get('format') not in (1,2,3) or state.get('workspace')!=ro._identity(workspace):_fail('workspace_identity',workspace)
    if record.get('generation')!=[state.get('generation'),state.get('libraries',{}).get(owner['library_id'],0)]:_fail('generation',path)
    bindings=record.get('bindings',{})
    required={str(workspace),str(owner['work_root']),str(owner['archive_root']),
              *(str(workspace/n) for n in load_storage_settings(workspace_root=workspace).values())}
    if not required<=set(bindings) or any(i is None or state.get('bindings',{}).get(p)!=i for p,i in bindings.items()):_fail('role_bindings',path)
    ro._check(bindings)
    if state.get('format')==3 and any(state.get('mounts',{}).get(p)!=mount(p) for p in bindings):_fail('mount_identity',path)
    if ro._read(path)!=record:_fail('reservation_changed',path)
    return parent,path


def _task(record,owner,parent):
    plan=ro._read(parent/('metadata-intent-'+record['reservation_id']+'.json'))
    ids=record['ids'];function=ids.get('function')
    if function==EXECUTE:
        if set(ids)!={'function','area','relative_path'} or ids['area']!='general':_fail('operation_key',parent)
    elif function==APPLY:
        if set(ids)!={'function','correction_id'}:_fail('operation_key',parent)
    else:_fail('operation_function',parent)
    if plan:
        if plan.get('format')!=1 or plan.get('reservation')!=record:_fail('intent_binding',parent)
        rows=_task_rows(owner['database_path'],'id=?',(plan.get('task',{}).get('id'),))
    elif function==APPLY:rows=_task_rows(owner['database_path'],'id=?',(ids['correction_id'],))
    else:rows=_task_rows(owner['database_path'],"area='general' AND source_relative_path=?",(ids['relative_path'],))
    if len(rows)!=1:_fail('task_missing_or_ambiguous',parent)
    task=rows[0]
    try:detected=json.loads(task['detected_json'])
    except (ValueError,TypeError):_fail('task_metadata',task['id'])
    if task['area']!='general' or not isinstance(detected,dict) or detected.get('library_id')!=owner['library_id']:_fail('task_owner',task['id'])
    if function==EXECUTE and task['source_relative_path']!=ids['relative_path']:_fail('task_path',task['id'])
    if function==APPLY and task['id']!=ids['correction_id']:_fail('task_id',task['id'])
    if plan:
        for key in ('id','area','source_path','source_relative_path','source_filename','source_size_bytes','source_sha256','media_type','detected_json','proposed_datetime','proposal_source','created_at'):
            if plan['task'].get(key)!=task[key]:_fail('task_intent_changed',task['id'])
    return task,plan


def _source_proof(source,size,sha):
    from app.import_publication import _parent
    if not re.fullmatch('[0-9a-f]{64}',str(sha)) or type(size) is not int or size<0:_fail('source_fingerprint',source)
    with _parent(source) as (parent,name):
        fd=os.open(name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=parent)
        try:
            before=os.fstat(fd)
            if not stat.S_ISREG(before.st_mode) or before.st_nlink!=1 or before.st_size!=size:_fail('source_type_or_size',source)
            digest=hashlib.sha256()
            while block:=os.read(fd,1048576):digest.update(block)
            after=os.fstat(fd);named=os.stat(name,dir_fd=parent,follow_symlinks=False)
            fields=lambda s:(s.st_dev,s.st_ino,s.st_mode,s.st_nlink,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
            if fields(before)!=fields(after) or fields(named)!=fields(after) or digest.hexdigest()!=sha:_fail('source_hash_or_identity',source)
            return {'path':str(source),'sha256':sha,'size_bytes':size,'identity':[after.st_dev,after.st_ino],
                    'mode':stat.S_IMODE(after.st_mode),'mtime_ns':after.st_mtime_ns,'ctime_ns':after.st_ctime_ns}
        finally:os.close(fd)


def _scan(metadata,general):
    from app.metadata_swap_recovery import assert_no_pending_swaps
    assert_no_pending_swaps(metadata)
    def scan_error(error):raise error
    for directory,dirs,files in os.walk(general,followlinks=False,onerror=scan_error):
        for name in dirs+files:
            if '.metadata-' in name or '.metadata-before-' in name or name.endswith(('_exiftool_tmp','_original')):
                _fail('unknown_working_copy',Path(directory)/name)


def _qualify(record,owner,parent):
    from app.metadata_correction import _safe_relative
    metadata,general=_paths(Path(record['workspace']));task,plan=_task(record,owner,parent)
    relative=_safe_relative(task['source_relative_path'])
    if relative.as_posix()!=task['source_relative_path']:_fail('noncanonical_source_path',task['id'])
    source=general/relative
    if str(source)!=task['source_path'] or source.resolve()!=source or source.name!=task['source_filename']:_fail('source_path',source)
    _scan(metadata,general)
    if task['status']=='completed':
        if not task['completed_at'] or task['output_path']!=str(source):_fail('completed_task',task['id'])
        try:verification=json.loads(task['verification_json'])
        except (ValueError,TypeError):_fail('completed_verification',task['id'])
        if not isinstance(verification,dict) or not verification:_fail('completed_verification',task['id'])
        disposition='completed';size=task['output_size_bytes'];sha=task['output_sha256']
    else:
        if task['status'] not in {'prepared','writing','blocked'} or task['completed_at'] is not None or any(task[k] not in (None,'') for k in ('output_path','output_sha256','output_size_bytes')):_fail('uncommitted_task',task['id'])
        try:verification=json.loads(task['verification_json'] or '{}')
        except (ValueError,TypeError):_fail('uncommitted_verification',task['id'])
        if verification!={}:_fail('uncommitted_verification',task['id'])
        disposition='rolled_back';size=task['source_size_bytes'];sha=task['source_sha256']
    proof=_source_proof(source,size,sha)
    _binding(record,owner);_scan(metadata,general)
    return task,plan,disposition,proof


def bind_task(database,workspace,task):
    record=_active(database,workspace);owner=_owner(database)
    # Historical standalone callers without a registry keep their existing
    # conservative exception behavior. They cannot authorize this completion.
    if record is None or owner is None:return
    assert_fresh_attempt(database,workspace)
    plain=_plain(record);parent,_=_binding(plain,owner)
    # Plan persists BEFORE any original or staging byte is written.
    plan={'format':1,'reservation':plain,'task':_task_rows(database,'id=?',(task['id'],))[0]}
    _save_once(parent/('metadata-intent-'+plain['reservation_id']+'.json'),plan)


def _finish(record,owner,*,error=None):
    plain=_plain(record);parent,_=_binding(plain,owner)
    task,plan,disposition,proof=_qualify(plain,owner,parent)
    plan=plan or {'format':1,'reservation':plain,'task':task}
    _save_once(parent/('metadata-intent-'+plain['reservation_id']+'.json'),plan)
    if disposition=='rolled_back' and task['status']!='blocked':
        from app.metadata_correction import _mark_task_blocked
        _mark_task_blocked(Path(owner['database_path']),task['id'],error or RuntimeError('Unterbrochene allgemeine Metadatenkorrektur anhand unveränderter Originalbytes zurückgesetzt.'))
    final,_,decision,again=_qualify(plain,owner,parent)
    if decision!=disposition or again!=proof:_fail('state_changed_during_qualification',task['id'])
    receipt={'format':1,'disposition':disposition,'reservation':plain,'task_before':plan['task'],
             'task_after':final,'source':proof,'not_inferred_from_blocked_status':True}
    _save_once(parent/('metadata-outcome-'+plain['reservation_id']+'.json'),receipt)
    # A late external change must keep the pending operation, even after its
    # outcome receipt was persisted. Never use that receipt as a generic bypass.
    _binding(plain,owner)
    metadata,general=_paths(Path(plain['workspace']));_scan(metadata,general)
    if _source_proof(Path(proof['path']),proof['size_bytes'],proof['sha256'])!=proof:
        _fail('source_changed_before_completion',proof['path'])
    return final,disposition


def verified_error(database,workspace,error):
    record=_active(database,workspace);owner=_owner(database)
    if record is None or owner is None:return None
    final,decision=_finish(record,owner,error=error)
    if decision=='completed':
        from app.metadata_correction import get_metadata_correction
        return get_metadata_correction(Path(database),final['id'])
    return _VerifiedFailure(error)


def _recover_general_outcomes(workspace,registry):
    """Called after startup's lease exits, before any workers are released."""
    from app.library_registry import list_libraries
    from app.metadata_swap_recovery import metadata_write_guard
    workspace=Path(workspace).absolute();_,parent=ro._control(workspace)
    owners={r['library_id']:r for r in list_libraries(registry,active_only=False,registered_only=True)}
    outcomes=[]
    for path in sorted(parent.glob('operation-*.json')):
        record=ro._read(path,{})
        if record.get('kind')!='metadata':continue
        ids=record.get('ids',{});function=ids.get('function')
        if function==EXECUTE and ids.get('area')!='general':continue
        if function not in {EXECUTE,APPLY}:continue
        owner=owners.get(record.get('library'))
        if owner is None:_fail('library_authority_missing',path)
        if function==APPLY:
            rows=_task_rows(owner['database_path'],'id=?',(ids.get('correction_id'),))
            if len(rows)==1 and rows[0]['area']!='general':continue
        _binding(record,owner)
        from app.storage_bootstrap import key_for
        if path.name!='operation-'+key_for(record)+'.json':_fail('operation_filename',path)
        with ro.reserve(workspace,library_id=record['library'],database=Path(record['database']),
                        paths=list(record['bindings']),kind='metadata',ids=ids,
                        expected_generation=tuple(record['generation']),shared=False,_recovery_record=record) as active:
            if _plain(active)!=record:_fail('reservation_changed',path)
            metadata,_=_paths(workspace)
            with metadata_write_guard(metadata):
                final,disposition=_finish(active,owner)
                outcomes.append({'task_id':final['id'],'disposition':disposition,'reservation_id':record['reservation_id']})
    return outcomes


def recover_general_outcomes(workspace,registry):
    try:
        return _recover_general_outcomes(workspace,registry)
    except ro.RootOperationError:
        raise
    except Exception as error:
        # Recovery uncertainty keeps the authenticated shell available, with a
        # precise startup block; it never becomes a successful domain outcome.
        raise ro.RootOperationError('metadata_outcome_unverified: '+str(error)) from error
