"""Operation availability is independent of structural storage availability.

Unknown effect scope means a workspace write fence, never Storage UNAVAILABLE.
Live leases are recognized by their kernel lock; no record is deleted or waived.
Only trusted startup recovery may bypass this additional admission fence. Existing
F14 identity/generation/journal checks always remain in force.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
import fcntl,hashlib,json,os,stat
from threading import RLock

_RECOVERING=ContextVar('operation_recovery_session',default=False)
_FAILURES={}
_RECOVERY_WORKSPACES={}
_STATUS_LOCK=RLock()
_TECHNICAL_STARTUP_IDS={'technical_setup':True,'protocol':'pre4'}
_READ_ONLY=ContextVar('operation_read_only',default=False)
_RETRIES=ContextVar('operation_qualified_retries',default=())
_RETRY_COMPLETED=ContextVar('operation_retry_completed',default=frozenset())
_RETRY_ISSUES=ContextVar('operation_retry_original_issues',default=None)


class TechnicalStartupError(RuntimeError):pass
class DomainStartupError(RuntimeError):pass


def reset(workspace):
    with _STATUS_LOCK:_FAILURES.pop(str(Path(workspace).absolute()),None)


def failed(workspace,phase,error):
    key=str(Path(workspace).absolute())
    from app.operation_scopes import resources
    status=inspect(workspace)
    effects=frozenset().union(*(resources(r) for r in status['reservations'] if not r['live'])) or {'workspace'}
    item={'phase':phase,'detail':str(error),'scope':sorted(effects),'reason':'effect_scope_requires_qualification'}
    with _STATUS_LOCK:
        bucket=_FAILURES.setdefault(key,[])
        if item not in bucket:bucket.append(item)


@contextmanager
def recovery_session():
    token=_RECOVERING.set(True)
    try:yield
    finally:_RECOVERING.reset(token)


def _live(path):
    lock=path.with_suffix('.lock')
    try:
        fd=os.open(lock,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        try:
            info=os.fstat(fd);named=lock.lstat()
            if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or (info.st_dev,info.st_ino)!=(named.st_dev,named.st_ino):return False
            try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:return True
            finally:
                # Closing our descriptor releases only our lock, never the owner's.
                pass
            return False
        finally:os.close(fd)
    except OSError:return False


def inspect(workspace):
    from app import root_operations as ro
    from app.storage_bootstrap import key_for
    root=Path(workspace).absolute();entries=[]
    try:parent=ro._control_location(root)
    except Exception as error:return {'writes_allowed':False,'issues':[{'detail':str(error),'scope':'workspace'}],'reservations':[],'blocked_scopes':['workspace'],'storage_state_independent':True}
    active={str(r['_path']):{k:v for k,v in r.items() if not k.startswith('_')} for r in ro._ACTIVE.get()}
    for path in sorted(parent.glob('operation-*.json')):
        item={'path':str(path),'scope':'workspace','live':False,'qualified':False}
        try:
            r=ro._read(path)
            nonce=r.get('reservation_id')
            if (r.get('format')!=1 or r.get('workspace')!=str(root) or not isinstance(r.get('ids'),dict)
                or not isinstance(r.get('kind'),str) or not isinstance(r.get('library'),str)
                or not isinstance(r.get('bindings'),dict) or not isinstance(nonce,str)
                or len(nonce)!=32 or any(c not in '0123456789abcdef' for c in nonce)
                or not isinstance(r.get('generation'),list) or len(r['generation'])!=2
                or any(type(g) is not int or g<0 for g in r['generation'])
                or path.name!='operation-'+key_for(r)+'.json'):raise ValueError('operation record/key invalid')
            item.update({k:r.get(k) for k in ('kind','library','database','ids','reservation_id','generation')})
            if 'effect_resources' in r:item['effect_resources']=r['effect_resources']
            item['live']=active.get(str(path))==r or _live(path)
            if r.get('kind')=='metadata' and r.get('ids',{}).get('area')=='general':
                item['affected']={'area':'metadata_general','relative_path':r['ids'].get('relative_path'),'library':r.get('library')}
            item['record_sha256']=hashlib.sha256(json.dumps(r,sort_keys=True).encode()).hexdigest()
            item['qualified']=True  # Record syntax only; NEVER completion authority.
            from app.operation_scopes import resources
            item['scope']=sorted(resources(item))
        except Exception as error:item['detail']=str(error)
        entries.append(item)
    with _STATUS_LOCK:
        issues=list(_FAILURES.get(str(root),[]))
        if _RECOVERY_WORKSPACES.get(str(root)) and not _RECOVERING.get():
            issues.append({'phase':'recovery_in_progress','scope':'workspace','detail':'Recovery holds write admission until qualification and startup finish.'})
    orphan=[r for r in entries if not r['live']]
    blocked=set()
    for record in orphan+issues:
        scope=record.get('scope','workspace')
        blocked.update([scope] if isinstance(scope,str) else scope)
    return {'writes_allowed':not orphan and not issues,'issues':issues,'reservations':entries,
            'workspace_writes_allowed':'workspace' not in blocked,
            'blocked_scopes':sorted(blocked),
            'scope_policy':'verified_resource_overlap_only_unknown_effects_fence_workspace','storage_state_independent':True}


def require_write(workspace,*,candidate=None):
    from app.root_operations import RootOperationError
    if _RECOVERING.get():return
    if _READ_ONLY.get():
        raise RootOperationError('operation_read_only_request: writes are paused')
    status=inspect(workspace)
    # Explicitly qualified retry capabilities are bound to unchanged records.
    retry=dict(_RETRIES.get())
    dead=[r for r in status['reservations'] if not r['live']]
    if retry and dead and not any(i.get('phase')=='recovery_in_progress' for i in status['issues']) and all(r['qualified'] and retry.get(r['path'])==(r.get('reservation_id'),r.get('record_sha256')) for r in dead):return
    # In RC14, multiple families share one historical F14 key. The first
    # successful family releases the key. Continue only THIS previously
    # qualified request after reserve() attests that exact F14 release.
    if retry and not dead and status['reservations'] and _retry_issues_match(status):
        # validate_active_roots() runs INSIDE the resumed F14 lease, before
        # it has returned successfully. Its own live lease must pass, but no
        # unrelated lease may gain this exception.
        from app.root_operations import _ACTIVE
        live={str(r['_path']):r for r in _ACTIVE.get() if r.get('_resumed')}
        if all(r['live'] and retry.get(r['path'])==(r.get('reservation_id'),r.get('record_sha256'))
               and r['path'] in live and live[r['path']]['reservation_id']==r['reservation_id']
               for r in status['reservations']):
            return
    if retry and not dead and _RETRY_COMPLETED.get()==frozenset(retry) and _retry_issues_match(status):
        return
    # Exact original retries still run their original domain qualification.
    dead=[r for r in status['reservations'] if not r['live']]
    if candidate and not status['issues'] and dead and all(
        r['qualified'] and all(r.get(k)==candidate.get(k) for k in ('kind','library','database','ids')) for r in dead):return
    if not status['writes_allowed']:
        from app.operation_scopes import resources, conflicts, current
        requested=resources(candidate or current(str(Path(workspace).absolute())) or {})
        if not conflicts(requested,set(status['blocked_scopes'])):
            return
        raise RootOperationError('operation_recovery_required: workspace writes paused; storage may remain READY; '+
                                 str((dead or status['issues'])[0]))


def startup_session(workspace_provider):
    """Other request/worker contexts cannot mistake a recovering lease for a
    normal live operation and write beside its temporarily active kernel lock.
    """
    from functools import wraps
    def decorate(function):
        @wraps(function)
        def call(*args,**kwargs):
            key=str(Path(workspace_provider()).absolute())
            with _STATUS_LOCK:_RECOVERY_WORKSPACES[key]=_RECOVERY_WORKSPACES.get(key,0)+1
            try:
                with recovery_session():return function(*args,**kwargs)
            finally:
                with _STATUS_LOCK:
                    remaining=_RECOVERY_WORKSPACES[key]-1
                    if remaining:_RECOVERY_WORKSPACES[key]=remaining
                    else:_RECOVERY_WORKSPACES.pop(key)
        return call
    return decorate


def technical_failure(error):
    import sqlite3
    from app.database import DatabaseError
    if isinstance(error,(TechnicalStartupError,DatabaseError)):return True
    # A domain UNIQUE/FK violation or failed statement is not proof that the
    # database file or required storage has been lost/corrupted.
    return isinstance(error,sqlite3.DatabaseError) and (
        getattr(error,'sqlite_errorcode',0) & 0xff
    ) in {sqlite3.SQLITE_CORRUPT,sqlite3.SQLITE_NOTADB,sqlite3.SQLITE_CANTOPEN,sqlite3.SQLITE_IOERR,sqlite3.SQLITE_READONLY}


def recover_known_before_startup(workspace,registry,logs,*,database=None):
    """Unknown intents never permit ordinary migrations/backfill as recovery."""
    from app.observation_recovery import recover
    recover(workspace)
    current=inspect(workspace)
    dead=[r for r in current['reservations'] if not r['live']]
    if not dead:return
    # A pre4 technical-only lease can repeat its exact schema preparation. Old
    # startup ids={} included domain writes and must never gain this authority.
    if len(dead)==1 and dead[0].get('kind')=='startup' and dead[0].get('ids')==_TECHNICAL_STARTUP_IDS:
        from app import root_operations as ro
        from app.storage_config import load_storage_settings
        path=Path(dead[0]['path'])
        with ro._lock(path.with_suffix('.lock'),exclusive=True):
            record=ro._read(path,{})
            if database is None or hashlib.sha256(json.dumps(record,sort_keys=True).encode()).hexdigest()!=dead[0]['record_sha256']:
                raise DomainStartupError('technical_startup_reservation_changed')
            state=ro._read(path.parent/'state.json',{})
            owner=ro._registered(Path(database)) if database is not None else None
            required={str(Path(workspace).absolute()),*(str(Path(workspace)/n) for n in load_storage_settings(workspace_root=Path(workspace)).values())}
            if owner and owner.get('is_registered',True):required.add(owner['work_root'])
            if (record.get('library')!='main' or record.get('database')!=str(Path(database).absolute())
                or record.get('generation')!=[state.get('generation'),state.get('libraries',{}).get('main',0)]
                or set(record.get('bindings',{}))!=required
                or any(v is None or state.get('bindings',{}).get(k)!=v for k,v in record['bindings'].items())):
                raise DomainStartupError('technical_startup_reservation_not_qualified')
            ro._check(record['bindings'])
            return record
    known={'app.metadata_correction.execute_metadata_correction','app.metadata_correction.apply_metadata_correction'}
    if not all(r['qualified'] and r.get('kind')=='metadata' and r.get('ids',{}).get('function') in known for r in dead):
        raise DomainStartupError('unresolved_operation_scope: safe read views remain available; '+str(dead))
    from app.metadata_abort_recovery import recover_general_outcomes
    recover_general_outcomes(workspace,registry,logs=logs,physical=True)
    if not inspect(workspace)['writes_allowed']:raise DomainStartupError('operation_recovery_incomplete')


def read_only():
    return _READ_ONLY.get()


@contextmanager
def read_session():
    token=_READ_ONLY.set(True)
    try:yield
    finally:_READ_ONLY.reset(token)


def read_connection(database):
    import sqlite3
    path=Path(database).absolute()
    if not path.is_file() or path.resolve()!=path:
        raise sqlite3.OperationalError('required catalogue unavailable: '+str(path))
    connection=sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,timeout=5)
    connection.row_factory=sqlite3.Row
    connection.execute('PRAGMA foreign_keys=ON')
    connection.execute('PRAGMA query_only=ON')
    return connection


def _retry_issues_match(status):
    original=_RETRY_ISSUES.get()
    return (original is not None
            and all(issue.get('phase')=='startup-recovery' for issue in status['issues'])
            and tuple(status['issues'])==original)


def note_completed_retry(record):
    """Trusted reserve() calls this only AFTER a resumed F14 lease is retired."""
    if not record.get('_resumed'):
        return
    retry=dict(_RETRIES.get())
    path=str(record.get('_path'))
    original=retry.get(path)
    if original is None:
        return
    public={k:v for k,v in record.items() if not k.startswith('_')}
    digest=hashlib.sha256(json.dumps(public,sort_keys=True).encode()).hexdigest()
    if original != (record.get('reservation_id'),digest):
        raise ValueError('completed_retry_identity_changed')
    _RETRY_COMPLETED.set(_RETRY_COMPLETED.get() | frozenset({path}))


def finish_qualified_retry(workspace):
    """Verify successful domain completion without globally dropping write fences.

    The subsequent startup session first establishes its concurrent-writer fence,
    then resets historical startup diagnostics and performs normal startup.
    """
    from app.root_operations import RootOperationError
    retry=dict(_RETRIES.get())
    status=inspect(workspace)
    if not retry or status['reservations']:
        raise RootOperationError('retry_has_unresolved_reservations')
    if _RETRY_COMPLETED.get()!=frozenset(retry) or not _retry_issues_match(status):
        raise RootOperationError('retry_completion_not_verified')
    key=str(Path(workspace).absolute())
    original=_RETRY_ISSUES.get()
    with _STATUS_LOCK:
        if tuple(_FAILURES.get(key,[]))!=original:
            raise RootOperationError('retry_recovery_diagnostic_changed')


@contextmanager
def qualified_retry(workspace, paths):
    from app.root_operations import RootOperationError
    status=inspect(workspace)
    dead=[r for r in status['reservations'] if not r['live']]
    if any(i.get('phase')=='recovery_in_progress' for i in status['issues']) or not dead or any(not r['qualified'] or r['path'] not in paths for r in dead):
        raise RootOperationError('retry_has_other_unresolved_effects')
    token=_RETRIES.set(tuple((r['path'],(r['reservation_id'],r['record_sha256'])) for r in dead))
    done_token=_RETRY_COMPLETED.set(frozenset())
    issue_token=_RETRY_ISSUES.set(tuple(status['issues']))
    try:yield
    finally:
        _RETRY_ISSUES.reset(issue_token)
        _RETRY_COMPLETED.reset(done_token)
        _RETRIES.reset(token)


def _guard_workspace_connection(connection, workspace, *, library=None, registry=False):
    import sqlite3
    from app.root_operations import RootOperationError
    writes={getattr(sqlite3,name) for name in (
        'SQLITE_INSERT','SQLITE_UPDATE','SQLITE_DELETE','SQLITE_CREATE_INDEX',
        'SQLITE_CREATE_TABLE','SQLITE_CREATE_TEMP_INDEX','SQLITE_CREATE_TEMP_TABLE',
        'SQLITE_CREATE_TEMP_TRIGGER','SQLITE_CREATE_TEMP_VIEW','SQLITE_CREATE_TRIGGER',
        'SQLITE_CREATE_VIEW','SQLITE_DROP_INDEX','SQLITE_DROP_TABLE','SQLITE_DROP_TEMP_INDEX',
        'SQLITE_DROP_TEMP_TABLE','SQLITE_DROP_TEMP_TRIGGER','SQLITE_DROP_TEMP_VIEW',
        'SQLITE_DROP_TRIGGER','SQLITE_DROP_VIEW','SQLITE_ALTER_TABLE','SQLITE_REINDEX',
        'SQLITE_ANALYZE','SQLITE_ATTACH','SQLITE_DETACH')}
    def authorize(action,arg1,arg2,db,origin):
        if action in writes:
            try:
                from app.operation_scopes import current
                candidate=current(str(Path(workspace).absolute()))
                extra=set()
                if str(arg1 or '').startswith(('metadata_', 'batch_metadata_')):
                    extra.add('metadata')
                if 'trash' in str(arg1 or ''):
                    extra.add('trash')
                if candidate is not None and extra:
                    from app.operation_scopes import resources
                    effects=resources(candidate)
                    # Only an already admitted General file lease may update
                    # its task rows without acquiring the entire metadata area.
                    from app.root_operations import _ACTIVE
                    if any(r.get('kind')=='metadata' for r in _ACTIVE.get()) and any(r.startswith('metadata/general/') for r in effects):
                        extra.discard('metadata')
                    candidate={'_resources':effects|extra}
                if candidate is None and library:
                    candidate={'_resources':{'library:'+str(library), 'central_stock', *extra}}
                # Registry writes coordinate all catalogues and stock. A domain
                # lease, when present, supplies the narrower proven footprint.
                if candidate is None and registry:
                    candidate={'_resources':{'central_stock'}}
                require_write(workspace, candidate=candidate)
            except RootOperationError:return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK
    connection.set_authorizer(authorize)
    return connection


def guard_connection(connection, database):
    """Additional DB write barrier; filesystem publication still owns F14 leases."""
    from app import root_operations as ro
    owner=ro._registered(Path(database).absolute())
    if owner is None:return connection
    return _guard_workspace_connection(connection,Path(owner['workspace_root']),library=owner['library_id'])


def guard_registry_connection(connection, registry):
    workspace=os.environ.get('KAMERA_WORKSPACE')
    configured=os.environ.get('KAMERA_REGISTRY_DATABASE')
    if not workspace or not configured or Path(configured).absolute()!=Path(registry).absolute():return connection
    return _guard_workspace_connection(connection,Path(workspace),registry=True)
