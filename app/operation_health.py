"""Operation availability is independent of structural storage availability.

Unknown effect scope means a workspace write fence, never Storage UNAVAILABLE.
Live leases are recognized by their kernel lock; no record is deleted or waived.
Only trusted startup recovery may bypass this additional admission fence. Existing
F14 identity/generation/journal checks always remain in force.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
import fcntl,os,stat

_RECOVERING=ContextVar('operation_recovery_session',default=False)
_FAILURES={}
_READ_ONLY=ContextVar('operation_read_only',default=False)
_RETRIES=ContextVar('operation_qualified_retries',default=())


class TechnicalStartupError(RuntimeError):pass
class DomainStartupError(RuntimeError):pass


def reset(workspace):_FAILURES.pop(str(Path(workspace).absolute()),None)


def failed(workspace,phase,error):
    key=str(Path(workspace).absolute())
    item={'phase':phase,'detail':str(error),'scope':'workspace','reason':'effect_scope_requires_qualification'}
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
            item['live']=active.get(str(path))==r or _live(path)
            if r.get('kind')=='metadata' and r.get('ids',{}).get('area')=='general':
                item['affected']={'area':'metadata_general','relative_path':r['ids'].get('relative_path'),'library':r.get('library')}
            item['qualified']=True  # Record syntax only; NEVER completion authority.
        except Exception as error:item['detail']=str(error)
        entries.append(item)
    issues=list(_FAILURES.get(str(root),[]))
    orphan=[r for r in entries if not r['live']]
    return {'writes_allowed':not orphan and not issues,'issues':issues,'reservations':entries,
            'blocked_scopes':['workspace'] if orphan or issues else [],
            'scope_policy':'unknown_or_shared_effects_fence_writes_only','storage_state_independent':True}


def require_write(workspace,*,candidate=None):
    from app.root_operations import RootOperationError
    if _RECOVERING.get():return
    if _READ_ONLY.get():
        raise RootOperationError('operation_read_only_request: writes are paused')
    status=inspect(workspace)
    # Explicitly qualified retry capabilities are bound to unchanged records.
    retry=dict(_RETRIES.get())
    dead=[r for r in status['reservations'] if not r['live']]
    if retry and dead and all(r['qualified'] and retry.get(r['path'])==r.get('reservation_id') for r in dead):return
    # Exact original retries still run their original domain qualification.
    dead=[r for r in status['reservations'] if not r['live']]
    if candidate and not status['issues'] and dead and all(
        r['qualified'] and all(r.get(k)==candidate.get(k) for k in ('kind','library','database','ids')) for r in dead):return
    if not status['writes_allowed']:
        raise RootOperationError('operation_recovery_required: workspace writes paused; storage may remain READY; '+
                                 str((dead or status['issues'])[0]))


def startup_session(function):
    from functools import wraps
    @wraps(function)
    def call(*args,**kwargs):
        with recovery_session():return function(*args,**kwargs)
    return call


def technical_failure(error):
    import sqlite3
    from app.database import DatabaseError
    return isinstance(error,(TechnicalStartupError,sqlite3.DatabaseError,DatabaseError))


def recover_known_before_startup(workspace,registry,logs):
    """Unknown intents never permit ordinary migrations/backfill as recovery."""
    current=inspect(workspace)
    dead=[r for r in current['reservations'] if not r['live']]
    if not dead:return
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


@contextmanager
def qualified_retry(workspace, paths):
    from app.root_operations import RootOperationError
    status=inspect(workspace)
    dead=[r for r in status['reservations'] if not r['live']]
    if not dead or any(not r['qualified'] or r['path'] not in paths for r in dead):
        raise RootOperationError('retry_has_other_unresolved_effects')
    token=_RETRIES.set(tuple((r['path'],r['reservation_id']) for r in dead))
    try:yield
    finally:_RETRIES.reset(token)


def _guard_workspace_connection(connection, workspace):
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
            try:require_write(workspace)
            except RootOperationError:return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK
    connection.set_authorizer(authorize)
    return connection


def guard_connection(connection, database):
    """Additional DB write barrier; filesystem publication still owns F14 leases."""
    from app import root_operations as ro
    owner=ro._registered(Path(database).absolute())
    if owner is None:return connection
    return _guard_workspace_connection(connection,Path(owner['workspace_root']))


def guard_registry_connection(connection, registry):
    workspace=os.environ.get('KAMERA_WORKSPACE')
    configured=os.environ.get('KAMERA_REGISTRY_DATABASE')
    if not workspace or not configured or Path(configured).absolute()!=Path(registry).absolute():return connection
    return _guard_workspace_connection(connection,Path(workspace))
