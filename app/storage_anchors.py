"""Structural roots only: media/day folders and operation outcomes are not anchors.

Existing F14 bindings remain authoritative. Additional fixed administration
children use additive first-observation receipts; none is recreated on loss.
"""
from contextlib import closing
from pathlib import Path
from threading import Lock
import os
import sqlite3
import stat

_INTEGRITY = {}
_INTEGRITY_LOCK = Lock()


def definitions(workspace, state):
    from app.storage_config import load_storage_settings, storage_paths
    from app.managed_directory_names import directory_name
    from app.appdata import root as appdata_root, mount
    root = Path(workspace).absolute()
    paths = storage_paths(root)
    result = {str(root): {'role': 'workspace', 'writable': True}}
    for key, name in load_storage_settings(workspace_root=root).items():
        result[str(root/name)] = {'role': key, 'writable': True}
    saved = state.get('structural_anchors', {})
    for kind in ('metadata_general', 'metadata_multiple'):
        prior = [p for p, row in saved.items() if row.get('role') == kind]
        if len(prior) > 1:
            raise ValueError('duplicate_structural_role: ' + kind)
        path = Path(prior[0]) if prior else paths['metadata_root']/directory_name(paths['metadata_root'], kind)
        if path.parent != paths['metadata_root'] or path.name not in __import__('app.managed_directory_names', fromlist=['NAME_PAIRS']).NAME_PAIRS[kind]:
            raise ValueError('structural_role_path_invalid: ' + str(path))
        result[str(path)] = {'role': kind, 'writable': True}
    registry = os.environ.get('KAMERA_REGISTRY_DATABASE')
    if registry and Path(registry).is_file():
        with closing(sqlite3.connect(Path(registry).absolute().as_uri()+'?mode=ro', uri=True)) as connection:
            if connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='libraries'").fetchone():
                for library, work, archive in connection.execute('SELECT library_id,work_root,archive_root FROM libraries WHERE COALESCE(is_registered,1)=1 AND workspace_root=?', (str(root),)):
                    result[work] = {'role': 'library_work_root:'+library, 'writable': True}
                    result[archive] = {'role': 'library_archive_root:'+library, 'writable': False}
    base = appdata_root()
    if base:
        result[str(base)] = {'role': 'appdata', 'writable': True}
        for name in ('config', 'database', 'logs', 'removable-sources'):
            path = base/name
            row = {'role': 'appdata_'+name, 'writable': True}
            mounted = mount(path)
            if name == 'removable-sources' and mounted and mounted['target'] == str(path) and mounted['filesystem'] == 'tmpfs':
                row['policy'] = 'runtime_tmpfs'
            result[str(path)] = row
    return result


def expected_identity(state, path):
    # An explicit loss-confirmed F14 root replacement updates bindings. Never
    # let an older display receipt override that audited transition.
    return state.get('bindings', {}).get(str(path), state.get('structural_anchors', {}).get(str(path), {}).get('identity'))


def issues(workspace, state, *, initializing=False):
    from app.appdata import mount
    from app.root_operations import _read, _control_location
    result = []
    saved = state.get('structural_anchors', {})
    anchors = definitions(workspace, state)
    for name, row in anchors.items():
        path = Path(name)
        old = saved.get(name)
        expected = expected_identity(state, name)
        code = None
        try:
            info = path.lstat()
            if not stat.S_ISDIR(info.st_mode) or path.resolve() != path:
                code = 'invalid_directory'
            runtime = row.get('policy') == 'runtime_tmpfs'
            if old and old.get('policy') != row.get('policy'):
                code = 'structural_anchor_policy_changed'
            if runtime:
                if info.st_uid != 0 or info.st_mode & 0o022:
                    code = 'removable_runtime_invalid'
            elif expected is not None and expected != [info.st_dev, info.st_ino]:
                code = 'identity_changed'
            access = os.R_OK | os.X_OK | (os.W_OK if row['writable'] and not runtime else 0)
            if not os.access(path, access):
                code = 'inaccessible'
            expected_mount = state.get('mounts', {}).get(name, (old or {}).get('mount'))
            if old and expected_mount != mount(path) and not runtime:
                code = 'mount_identity_changed'
            if str(workspace) == '/workspace' and row['role'].startswith('library_archive_root:') and not os.statvfs(path).f_flag & os.ST_RDONLY:
                code = 'archive_mount_not_read_only'
        except FileNotFoundError:
            if not initializing:
                code = 'missing'
        except OSError:
            code = 'inaccessible'
        if code:
            result.append({'code': code, 'path': name, 'key': row['role'], 'expected_identity': expected})
    # A malformed domain record fences writes in operation_health. A proven
    # contradiction concerning a required root remains a structural failure.
    for path in _control_location(workspace).glob('operation-*.json'):
        try:
            record = _read(path)
            bindings = record.get('bindings', {})
            if not isinstance(bindings, dict):
                continue
        except Exception:
            continue
        for name, identity in bindings.items():
            expected = expected_identity(state, name)
            if name in anchors and identity is not None and expected not in (None, identity):
                result.append({'code': 'control_identity_invalid', 'path': str(path), 'detail': 'contradictory protected root binding: '+name})
    return result


def pin(workspace):
    from app import root_operations as ro
    from app.appdata import mount
    root, parent = ro._control(workspace)
    with ro._lock(parent/'workspace.lock'), ro._lock(parent/'state.lock', exclusive=True, wait=True):
        state = ro._state(parent, root)
        problems = issues(root, state)
        if problems:
            raise ro.RootOperationError('structural_anchor_qualification_failed: '+str(problems))
        current = state.setdefault('structural_anchors', {})
        for name, row in definitions(root, state).items():
            if name in current:
                continue
            info = Path(name).stat()
            current[name] = dict(row, identity=[info.st_dev, info.st_ino], mount=mount(name))
        ro._write(parent/'state.json', state)


def _stamp(path):
    def one(p):
        try:
            info = p.stat()
            return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
        except FileNotFoundError:
            return None
    return (one(path), one(Path(str(path)+'-wal')))


def database_issues(workspace, database, state, *, initializing=False):
    """Bounded SQLite integrity checks cached only for unchanged DB+WAL bytes."""
    if initializing:
        return []  # Exact bootstrap evidence already qualifies this empty state.
    from app.storage_config import _config_path
    result = []
    config = _config_path()
    if state and (not config.is_file() or config.resolve() != config.absolute()):
        result.append({'code': 'configuration_unavailable', 'path': str(config)})
    registry = os.environ.get('KAMERA_REGISTRY_DATABASE')
    paths = {Path(database).absolute()} if database is not None else set()
    if registry:
        paths.add(Path(registry).absolute())
        if Path(registry).is_file():
            try:
                with closing(sqlite3.connect(Path(registry).absolute().as_uri()+'?mode=ro', uri=True)) as connection:
                    if connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='libraries'").fetchone():
                        registered = connection.execute('SELECT database_path FROM libraries WHERE workspace_root=? AND COALESCE(is_registered,1)=1', (str(workspace),)).fetchall()
                        paths.update(Path(p).absolute() for p, in registered)
                        if registered and not state:
                            result.append({'code': 'installation_history_missing', 'path': str(workspace)})
            except sqlite3.Error as error:
                result.append({'code': 'registry_unavailable', 'path': str(registry), 'detail': str(error)})
    for path in paths:
        try:
            if not path.is_file() or path.resolve() != path:
                raise ValueError('required database missing or symlink')
            before = _stamp(path)
            with _INTEGRITY_LOCK:
                cached = _INTEGRITY.get(str(path))
            if cached == before:
                continue
            with closing(sqlite3.connect(path.as_uri()+'?mode=ro', uri=True, timeout=5)) as connection:
                connection.execute('BEGIN')
                check = connection.execute('PRAGMA quick_check').fetchall()
                if check != [('ok',)] or connection.execute('PRAGMA foreign_key_check').fetchone():
                    raise ValueError('SQLite integrity / foreign keys invalid: '+str(check[:3]))
            if before == _stamp(path):
                with _INTEGRITY_LOCK:
                    _INTEGRITY[str(path)] = before
        except (sqlite3.Error, OSError, ValueError) as error:
            result.append({'code': 'catalog_unavailable', 'path': str(path), 'detail': str(error)})
    return result
