"""Operation availability is independent of structural storage availability.

Unknown effect scope means a workspace write fence, never Storage UNAVAILABLE.
Live leases are recognized by their kernel lock; no record is deleted or waived.
Only trusted startup recovery may bypass this additional admission fence. Existing
F14 identity/generation/journal checks always remain in force.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
import fcntl,json,os,stat

_RECOVERING=ContextVar('operation_recovery_session',default=False)
_FAILURES={}


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
    active={r.get('reservation_id') for r in ro._ACTIVE.get()}
    for path in sorted(parent.glob('operation-*.json')):
        item={'path':str(path),'scope':'workspace','live':False,'qualified':False}
        try:
            r=ro._read(path)
            if (r.get('format')!=1 or r.get('workspace')!=str(root) or not isinstance(r.get('ids'),dict)
                or path.name!='operation-'+key_for(r)+'.json'):raise ValueError('operation record/key invalid')
            item.update({k:r.get(k) for k in ('kind','library','database','ids','reservation_id','generation')})
            item['live']=r.get('reservation_id') in active or _live(path)
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
    status=inspect(workspace)
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
