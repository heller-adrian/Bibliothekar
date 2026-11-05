"""Serialize metadata preparation against General source cleanup, privately.

This transition lock complements, and never replaces, the physical swap writer
or F14 leases. Busy/uncertain cleanup retains both original and staged bytes.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
import inspect
import os
from pathlib import Path
from app import root_operations as ro

_HELD=ContextVar('general_handoff_roots',default=())


@contextmanager
def transition(workspace):
    root=Path(workspace).absolute();key=str(root)
    if key in _HELD.get():
        ro.validate_active_roots();yield;return
    _,parent=ro._control(root)
    with ro._lock(parent/'general-handoff.lock',exclusive=True):
        token=_HELD.set((*_HELD.get(),key))
        try:yield
        finally:_HELD.reset(token)


def correction(function):
    signature=inspect.signature(function)
    @wraps(function)
    def call(*args,**kwargs):
        from app.metadata_correction import MetadataCorrectionError
        bound=signature.bind(*args,**kwargs)
        try:
            with transition(bound.arguments['workspace_root']):return function(*args,**kwargs)
        except ro.RootOperationError as error:raise MetadataCorrectionError(str(error)) from error
    return call


def cleanup(workspace,stage,entries,job_id):
    from app.metadata_abort_recovery import _paths,_source_proof,_plain
    from app.import_publication import _parent
    removed=0;errors=[]
    try:
        with transition(workspace):
            ro.validate_active_roots()
            metadata,general=_paths(workspace)
            if Path(stage).parent!=metadata/'.general-import' or Path(stage).name!=job_id:
                raise ro.RootOperationError('metadata_cleanup_stage_mismatch: '+str(stage))
            active={str(r['_path']):_plain(r) for r in ro._ACTIVE.get()
                    if r['kind']=='import' and r['ids'].get('job_id')==job_id}
            if not active:
                raise ro.RootOperationError('metadata_cleanup_without_import_reservation: '+str(stage))
            for path in ro._control_location(workspace).glob('operation-*.json'):
                if str(path) not in active or ro._read(path)!=active[str(path)]:
                    raise ro.RootOperationError('metadata_cleanup_unresolved_predecessor: '+str(path))
            for entry in entries:
                from app.import_recovery import relative
                rel=relative(entry['relative_path'])
                for path in (Path(stage)/rel,general/rel):
                    if not os.path.lexists(path):continue
                    proof=_source_proof(path,entry['size_bytes'],entry['sha256'])
                    with _parent(path) as (fd,name):
                        current=os.stat(name,dir_fd=fd,follow_symlinks=False)
                        if [current.st_dev,current.st_ino]!=proof['identity'] or current.st_mtime_ns!=proof['mtime_ns'] or current.st_ctime_ns!=proof['ctime_ns']:
                            raise ro.RootOperationError('metadata_cleanup_source_changed: '+str(path))
                        ro.validate_active_roots();os.unlink(name,dir_fd=fd);os.fsync(fd);removed+=1
    except Exception as error:errors.append(str(error))
    return {'removed_file_count':removed,'errors':errors}
