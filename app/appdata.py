"""RC12 host-managed storage: continuity and access, not hostile-host attestation.

Opt in through KAMERA_APPDATA. Legacy layouts keep RC11's security contract.
The NAS administrator, dataset owners and ACL writers are trusted operators.
"""
from pathlib import Path
import json
import os
import stat
import sys
import uuid


def root():
    value = os.environ.get('KAMERA_APPDATA')
    return Path(os.path.abspath(value)) if value else None


def configure():
    base = root()
    if base is None: return
    defaults = {'KAMERA_CONFIG': base/'config/settings.json', 'KAMERA_DATABASE_DIR': base/'database',
                'KAMERA_REGISTRY_DATABASE': base/'database/bibliothekar-global.sqlite3',
                'KAMERA_LOG_DIR': base/'logs', 'KAMERA_REMOVABLE_ROOT': base/'removable-sources',
                'KAMERA_REMOVABLE_MOUNT_ROOT': base/'removable-sources'}
    for key, value in defaults.items(): os.environ.setdefault(key, str(value))


def managed(path):
    base = root()
    if base is None: return False
    p = Path(os.path.abspath(path))
    return p == base or p.is_relative_to(base) or base.is_relative_to(p)


def mount(path):
    """Stable mount provenance; kernel mount IDs are not restart-stable."""
    if sys.platform != 'linux': return None
    path = Path(os.path.abspath(path)); found = None
    def unescape(s):
        for old, new in [('\\040',' '),('\\011','\t'),('\\012','\n'),('\\134','\\')]: s = s.replace(old,new)
        return s
    for line in Path('/proc/self/mountinfo').read_text().splitlines():
        fields = line.split(); sep = fields.index('-'); target = Path(unescape(fields[4]))
        if path == target or path.is_relative_to(target):
            row = {'target':str(target),'device':fields[2],'root':unescape(fields[3]),
                   'filesystem':fields[sep+1],'source':unescape(fields[sep+2])}
            if found is None or len(target.parts) > len(Path(found['target']).parts): found = row
    if found is None: raise OSError('mount_evidence_unavailable: '+str(path))
    return found


def _identity(path):
    s = Path(path).lstat()
    if not stat.S_ISDIR(s.st_mode): raise OSError('directory_required: '+str(path))
    return [s.st_dev,s.st_ino]


def prepare():
    """Run as the web UID. Never mkdir a missing appdata mount or chmod/chown."""
    base = root()
    if base is None: return
    from app.private_storage_security import qualified
    if not base.is_dir(): raise OSError('appdata_unavailable: '+str(base))
    if str(base) == '/appdata' and (mount(base) or {}).get('target') != str(base):
        raise OSError('appdata_mount_missing: '+str(base))
    for key in ('KAMERA_CONFIG','KAMERA_DATABASE_DIR','KAMERA_REGISTRY_DATABASE','KAMERA_LOG_DIR','KAMERA_REMOVABLE_ROOT','KAMERA_REMOVABLE_MOUNT_ROOT'):
        if not Path(os.environ[key]).absolute().is_relative_to(base):
            raise OSError('appdata_layout_conflict: '+os.environ[key]+': keep legacy mounts without KAMERA_APPDATA, or use a separate RC12 installation')
    ws = Path(os.environ.get('KAMERA_WORKSPACE','/workspace')).absolute()
    if base == ws or base.is_relative_to(ws) or ws.is_relative_to(base):
        raise OSError('appdata_workspace_overlap: '+str(base))
    with qualified(base,directory=True) as (fd,check):
        for name in ('config','database','logs','removable-sources'):
            try: os.mkdir(name,0o700,dir_fd=fd)
            except FileExistsError: pass
            path = base/name
            with qualified(path,directory=True) as (child,recheck):
                runtime_mount = mount(path)
                if name == 'removable-sources' and runtime_mount and runtime_mount['target'] == str(path):
                    info = os.fstat(child)
                    if runtime_mount['filesystem'] != 'tmpfs' or info.st_uid != 0 or info.st_mode & 0o022:
                        raise OSError('removable_runtime_invalid: '+str(path))
                    recheck(); continue  # Web reads source mounts, never helper journals.
                probe = '.access-'+uuid.uuid4().hex
                out = os.open(probe,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600,dir_fd=child)
                try: os.write(out,b'access probe'); os.fsync(out)
                finally: os.close(out)
                os.unlink(probe,dir_fd=child); os.fsync(child); recheck()
        check(); os.fsync(fd)


def _json(path):
    from app.root_operations import _read
    return _read(path,None)


def verify(workspace):
    """Read-only ownership fence across instances and loss of all appdata."""
    base = root()
    if base is None: return
    from app.root_operations import RootOperationError
    ws = Path(workspace).absolute(); marker = ws/'.bibliothekar-instance.json'
    # Workspace is shared. Read its record with no-follow, not private ACL rules.
    claim = None
    try:
        fd = os.open(marker,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        with os.fdopen(fd) as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size > 4096: raise ValueError('invalid claim file')
            if info.st_nlink != 1:
                manifest = _json(base/'instance.json')
                pending = ws/('.bibliothekar-claim-'+str((manifest or {}).get('instance_id')))
                other = pending.lstat()
                if info.st_nlink != 2 or (other.st_dev,other.st_ino) != (info.st_dev,info.st_ino): raise ValueError('foreign claim link')
            claim = json.load(stream)
    except FileNotFoundError: pass
    except (OSError,ValueError) as error:
        raise RootOperationError('workspace_claim_invalid: '+str(marker)+': '+str(error)) from error
    manifest = _json(base/'instance.json')
    if claim is not None and (not manifest or claim != {k:manifest[k] for k in ('format','instance_id','workspace','identity')}):
        raise RootOperationError('workspace_claim_conflict: '+str(marker)+': different instance or lost appdata; restore original appdata and mount, never initialize over this claim')
    if manifest:
        if manifest.get('format') != 1 or manifest.get('workspace') != str(ws) or manifest.get('identity') != _identity(ws):
            raise RootOperationError('workspace_identity_changed: '+str(ws))
        if manifest.get('appdata_identity') != _identity(base) or manifest.get('appdata_mount') != mount(base):
            raise RootOperationError('appdata_identity_changed: '+str(base))
        if claim is None and manifest.get('phase') != 'initializing': raise RootOperationError('workspace_claim_missing: '+str(marker))
        if manifest.get('phase') == 'ready':
            db = Path(os.environ['KAMERA_DATABASE_DIR'])/'kamera.sqlite3'
            registry = Path(os.environ['KAMERA_REGISTRY_DATABASE'])
            from app.root_operations import _control_location
            for path in (db,registry,_control_location(ws)/'state.json'):
                if not path.is_file(): raise RootOperationError('installation_history_missing: '+str(path)+': restore the consistent database/control backup')
    return manifest


def claim(workspace):
    """Only called after complete empty/history qualification, before F14 writes."""
    base = root()
    if base is None: return
    from app.root_operations import _write,RootOperationError
    from app.import_publication import _parent
    ws = Path(workspace).absolute()
    manifest = _json(base/'instance.json')
    # Persist our intent first; an interrupted intent can publish the same claim.
    if not manifest:
        manifest = {'format':1,'instance_id':uuid.uuid4().hex,'workspace':str(ws),'identity':_identity(ws),
                    'appdata_identity':_identity(base),'appdata_mount':mount(base),'phase':'initializing'}
        _write(base/'instance.json',manifest)
    value = {k:manifest[k] for k in ('format','instance_id','workspace','identity')}
    marker = ws/'.bibliothekar-instance.json'
    if not marker.exists():
        with _parent(marker) as (parent,name):
            pending = '.bibliothekar-claim-'+manifest['instance_id']
            # A complete saved temporary may survive a crash; its exact bytes
            # are checked, never taken as external authority.
            try:
                out = os.open(pending,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=parent)
            except FileExistsError:
                out = None
            if out is not None:
                with os.fdopen(out,'w') as stream:
                    json.dump(value,stream,sort_keys=True);stream.flush();os.fsync(stream.fileno())
            held = os.open(pending,os.O_RDONLY|os.O_NOFOLLOW,dir_fd=parent)
            with os.fdopen(held) as stream:
                info = os.fstat(stream.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or json.load(stream) != value:
                    raise RootOperationError('workspace_claim_invalid: '+str(ws/pending))
            try: os.link(pending,name,src_dir_fd=parent,dst_dir_fd=parent,follow_symlinks=False)
            except FileExistsError: pass
            os.unlink(pending,dir_fd=parent);os.fsync(parent)
    verify(ws)
    pending = ws/('.bibliothekar-claim-'+manifest['instance_id'])
    if pending.exists():
        if pending.stat(follow_symlinks=False).st_ino != marker.stat(follow_symlinks=False).st_ino:
            raise RootOperationError('workspace_claim_invalid: '+str(pending))
        pending.unlink()
    verify(ws)


def finish(workspace):
    base = root()
    if base is None: return
    from app.root_operations import _write
    manifest = verify(workspace)
    if manifest:
        manifest['phase'] = 'ready'; _write(base/'instance.json',manifest)


def pending_operations(workspace, *, all_records=False):
    """Malformed evidence always blocks; startup also fences unrecovered intents.

    A valid *live* reservation may coexist with ordinary requests. Before worker
    release, no other process is allowed to leave an unresolved durable intent.
    """
    if root() is None: return []
    from app.root_operations import _read,_control_location
    from app.storage_bootstrap import key_for
    parent = _control_location(workspace); state = _read(parent/'state.json',{})
    issues = []
    for path in parent.glob('operation-*.json'):
        record = _read(path,{})
        try:
            valid = (record.get('format') == 1 and record.get('workspace') == str(workspace)
                     and isinstance(record['ids'],dict) and isinstance(record['kind'],str)
                     and isinstance(record['library'],str)
                     and path.name == 'operation-'+key_for(record)+'.json'
                     and record['generation'] == [state['generation'],state.get('libraries',{}).get(record['library'],0)]
                     and isinstance(record['bindings'],dict)
                     and len(record['reservation_id']) == 32
                     and all(c in '0123456789abcdef' for c in record['reservation_id'])
                     and all(identity is None or state.get('bindings',{}).get(p)==identity for p,identity in record['bindings'].items()))
        except (KeyError,TypeError,ValueError): valid = False
        if not valid or all_records:
            issues.append({'code':'unresolved_reservation','path':str(path),
                           'detail':'Unrecognized or unrecovered operation; preserve evidence and restore its original roots before retrying.'})
    return issues
