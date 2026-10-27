"""RC11 bootstrap evidence, explicit RC10 adoption, durable completion.

No missing DB/registration flag overrides positive history. Hashes bind an
administrator's reviewed snapshot; they do not authenticate its earlier life.
"""
from contextlib import closing
from pathlib import Path
import base64
import hashlib
import json
import os
import sqlite3
import stat
import uuid

from app.private_storage_security import RootOperationError, qualified

CONFIRMATION = 'ADOPT RC10 BOOTSTRAP'


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def key_for(record):
    # Preserve the exact RC10 key algorithm, including its JSON separators.
    return hashlib.sha256(json.dumps([record['library'], record['kind'], str(record['database']), record['ids']], sort_keys=True).encode()).hexdigest()


def raw_file(path):
    with qualified(path) as (fd, check):
        data = os.read(fd, 4*1024*1024+1)
        if len(data) > 4*1024*1024: raise RootOperationError('control_document_too_large: '+str(path))
        check()
        return base64.b64encode(data).decode()


def migration_receipt(parent, name, root):
    from app.root_operations import _read
    if not isinstance(name, str) or Path(name).name != name or not name.endswith('.json'):
        raise RootOperationError('bootstrap_migration_receipt_invalid: '+str(parent))
    if name.startswith('rc11-adoption-'):
        prefix = 'rc11-adoption-'
    elif name.startswith('rc11-control-migration-'):
        prefix = 'rc11-control-migration-'
    else: raise RootOperationError('bootstrap_migration_receipt_invalid: '+str(parent/name))
    token = name[len(prefix):-5]
    if len(token) != 64 or any(c not in '0123456789abcdef' for c in token):
        raise RootOperationError('bootstrap_migration_receipt_invalid: '+str(parent/name))
    value = _read(parent/name, None)
    if not isinstance(value, dict): raise RootOperationError('bootstrap_migration_receipt_invalid: '+str(parent/name))
    if prefix == 'rc11-adoption-':
        if value.get('kind') != 'rc11_administrative_adoption' or value.get('confirmation') != CONFIRMATION or not value.get('backup_reference') or value.get('scope') not in ('bootstrap','control') or value.get('material', {}).get('workspace') != str(root) or digest(value.get('material')) != token:
            raise RootOperationError('bootstrap_migration_receipt_invalid: '+str(parent/name))
    elif value.get('kind') != 'rc11_control_migration' or digest(value) != token:
        raise RootOperationError('bootstrap_migration_receipt_invalid: '+str(parent/name))
    return value


def tree(root, names, *, legacy=None, allow_legacy=False):
    """One FD-bound observation. Legacy lock is inert, never an authority."""
    from app.import_publication import _parent
    root = Path(root)
    allowed = set(names.values()) | {names['backup_directory_name']+'/.incoming'}
    allowed.update(names['metadata_directory_name']+'/'+n for n in ['General', 'Batch Correction', '.trash-deletions', '.trash-restores'])
    lock = names['metadata_directory_name']+'/.trash-deletions/.lock'
    issues = []; observed_lock = None
    def issue(code, rel, detail): issues.append({'code': code, 'path': str(root/rel), 'detail': detail})
    def walk(fd, prefix=''):
        nonlocal observed_lock
        before = os.fstat(fd)
        for name in sorted(os.listdir(fd)):
            rel = prefix+name
            info = os.stat(name, dir_fd=fd, follow_symlinks=False)
            if stat.S_ISDIR(info.st_mode) and rel in allowed:
                child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                try:
                    opened = os.fstat(child)
                    if (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino):
                        issue('workspace_identity_changed', rel, 'directory replaced during scan'); continue
                    walk(child, rel+'/')
                    if os.stat(name, dir_fd=fd, follow_symlinks=False).st_ino != info.st_ino:
                        issue('workspace_identity_changed', rel, 'directory replaced after scan')
                finally: os.close(child)
            elif name == '.DS_Store' and stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_size <= 1024*1024:
                continue
            elif rel == lock and stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_size == 0 and info.st_uid == os.geteuid():
                observed_lock = {'path': str(root/rel), 'identity': [info.st_dev, info.st_ino], 'uid': info.st_uid,
                                 'gid': info.st_gid, 'mode': stat.S_IMODE(info.st_mode), 'size': 0, 'nlink': 1}
                held = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
                try:
                    opened = os.fstat(held)
                    if (opened.st_dev,opened.st_ino,opened.st_size,opened.st_uid,opened.st_nlink) != (info.st_dev,info.st_ino,0,info.st_uid,1):
                        issue('workspace_scan_changed', rel, 'legacy artifact replaced'); continue
                    try:
                        from app.private_storage_security import attributes
                        attrs = attributes(held)
                        observed_lock['acl_attributes'] = {n:base64.b64encode(v).decode() for n,v in sorted(attrs.items())}
                        observed_lock['acl_observation'] = 'observed_inert_not_authority'
                    except (OSError, ValueError) as error:
                        observed_lock['acl_observation'] = 'unavailable_inert_not_authority'
                        observed_lock['acl_error'] = str(error)
                    after_lock = os.fstat(held)
                    current = os.stat(name,dir_fd=fd,follow_symlinks=False)
                    if (after_lock.st_dev,after_lock.st_ino,after_lock.st_size,after_lock.st_mtime_ns,after_lock.st_ctime_ns) != (info.st_dev,info.st_ino,0,info.st_mtime_ns,info.st_ctime_ns) or (current.st_dev,current.st_ino)!=(info.st_dev,info.st_ino):
                        issue('workspace_scan_changed', rel, 'legacy artifact changed')
                finally: os.close(held)
                if not allow_legacy and observed_lock != legacy:
                    issue('legacy_lock_not_migrated', rel, f'RC10 lock mode={stat.S_IMODE(info.st_mode):04o}; explicit migration required; file retained')
            else:
                issue('workspace_unknown_entry', rel, 'unknown file, link or nontechnical directory; preserved')
        after = os.fstat(fd)
        if (before.st_dev, before.st_ino, before.st_mtime_ns, before.st_ctime_ns) != (after.st_dev, after.st_ino, after.st_mtime_ns, after.st_ctime_ns):
            issue('workspace_scan_changed', prefix, 'directory changed during scan; retry without concurrent editors')
    try:
        with _parent(root/'probe') as (fd, _): walk(fd)
    except OSError as error: issue('workspace_scan_error', '', str(error))
    return {'empty': not issues, 'issues': issues, 'legacy_lock': observed_lock}


def logical_database(path):
    """Snapshot includes committed WAL-visible rows, not a main-file-only hash."""
    path = Path(path)
    if not path.exists(): return None
    with qualified(path) as (_, check), closing(sqlite3.connect(path.absolute().as_uri()+'?mode=ro', uri=True)) as conn:
        conn.execute('BEGIN')
        schema = conn.execute("SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name").fetchall()
        rows = {}
        for kind, name, _, _ in schema:
            if kind != 'table': continue
            quoted = '"'+name.replace('"', '""')+'"'
            values = conn.execute('SELECT * FROM '+quoted).fetchall()
            rows[name] = sorted([repr(tuple(row)) for row in values])
        check()
        return digest({'schema': schema, 'rows': rows})


def _history(root, database, registry, state):
    from app.managed_storage_health import catalog_has_history, empty_bootstrap_registry
    if state.get('libraries'):
        raise RootOperationError('historical_library_generation: '+str(root))
    reset = state.get('setup_reset') or {}
    if reset:
        from app.root_operations import _control_location, _read
        name = reset.get('history', '')
        if Path(name).name != name or not name.startswith('setup-history-') or reset.get('confirmation') != 'SET UP AGAIN':
            raise RootOperationError('setup_reset_receipt_invalid: '+str(root))
        previous = _read(_control_location(root)/name, None)
        if previous is None or hashlib.sha256(json.dumps(previous, sort_keys=True).encode()).hexdigest() != reset.get('previous_state_sha256') or previous.get('libraries') or state.get('generation') != previous.get('generation', 0)+1:
            raise RootOperationError('setup_reset_receipt_invalid: '+str(root))
    elif state.get('generation') != 0:
        raise RootOperationError('historical_workspace_generation: '+str(root))
    databases = set(Path(database).parent.rglob('*.sqlite3')) | {Path(database)}
    for path in databases:
        if path == Path(registry): continue
        if catalog_has_history(path): raise RootOperationError('catalogue_history: '+str(path))
    try:
        empty_bootstrap_registry(registry, root, database)
    except (ValueError, sqlite3.Error) as error:
        raise RootOperationError(str(error)+': '+str(registry)) from error
    retention = Path(database).parent/'.bibliothekar-restore-retention'
    if retention.is_symlink() or retention.exists() and any(retention.iterdir()):
        raise RootOperationError('retention_survives: '+str(retention))
    # Unknown private catalog/sidecar ownership is never missing-history proof.
    for path in Path(database).parent.rglob('*'):
        if path.is_symlink(): raise RootOperationError('private_symlink: '+str(path))
        if path.name.endswith(('-wal', '-shm', '-journal')):
            suffix = next(s for s in ('-wal', '-shm', '-journal') if path.name.endswith(s))
            owner = Path(str(path)[:-len(suffix)])
            if path.stat().st_size and (owner not in databases | {Path(registry)} or not owner.is_file() or not owner.stat().st_size):
                raise RootOperationError('orphan_sqlite_sidecar: '+str(path))
            if suffix == '-journal' and path.stat().st_size:
                raise RootOperationError('sqlite_recovery_pending: '+str(path))
    from app.storage_config import _config_path
    if _config_path().exists():
        with qualified(_config_path()) as (fd, check):
            config = json.loads(os.read(fd, 1024*1024+1)); check()
        if config.get('libraries') or config.get('library') or (config.get('metadata_correction') or {}).get('general_root'):
            raise RootOperationError('configured_library_survives: '+str(_config_path()))


def evidence(root, database, state, *, require_adoption=True):
    """Strict pending-bootstrap qualification; callers hold locks before writes."""
    from app.root_operations import _control_location, _read, _identity
    from app.storage_config import load_storage_settings
    root, database = Path(root).absolute(), Path(database).absolute()
    registry = Path(os.environ.get('KAMERA_REGISTRY_DATABASE', str(database.parent/'bibliothekar-global.sqlite3'))).absolute()
    parent = _control_location(root); names = load_storage_settings(workspace_root=root)
    init = state.get('storage_initialization') or {}
    if state.get('workspace') != _identity(root): raise RootOperationError('workspace_identity_changed: '+str(root))
    if state.get('storage_names') != names or init.get('names') != names or init.get('database') != str(database):
        raise RootOperationError('bootstrap_binding_mismatch: '+str(root))
    if init.get('phase') not in ('initializing', 'prepared', 'completed'):
        raise RootOperationError('bootstrap_phase_unknown: '+str(root))
    if init.get('registry') not in (None, str(registry)):
        raise RootOperationError('bootstrap_registry_binding_mismatch: '+str(registry))
    _history(root, database, registry, state)
    expected_paths = {str(root), *(str(root/n) for n in names.values())}
    if set(state.get('bindings', {})) - expected_paths:
        raise RootOperationError('bootstrap_additional_binding: '+str(root))
    for path, identity in state.get('bindings', {}).items():
        if identity is not None and identity != _identity(path):
            raise RootOperationError('bootstrap_binding_mismatch: '+path)
    if str(root) not in state.get('bindings', {}): raise RootOperationError('bootstrap_binding_missing: '+str(root))
    template = {'library': 'main', 'kind': 'startup', 'database': str(database), 'ids': {'initialize_storage': True}}
    operation_key = key_for(template)
    operation_path = parent/('operation-'+operation_key+'.json')
    operation = _read(operation_path, None)
    if operation is None:
        if state.get('format') != 2 or init.get('operation_key') != operation_key or not init.get('reservation_id'):
            raise RootOperationError('bootstrap_reservation_missing: '+str(operation_path))
    else:
        if any(operation.get(k) != v for k, v in template.items()) or operation.get('format') != 1 or operation.get('workspace') != str(root) or operation.get('generation') != [state['generation'], 0]:
            raise RootOperationError('bootstrap_reservation_mismatch: '+str(operation_path))
        nonce = operation.get('reservation_id', '')
        if not isinstance(nonce, str) or len(nonce) != 32 or any(c not in '0123456789abcdef' for c in nonce):
            raise RootOperationError('bootstrap_reservation_mismatch: '+str(operation_path))
        if set(operation.get('bindings', {})) != expected_paths:
            raise RootOperationError('bootstrap_reservation_mismatch: '+str(operation_path))
        for path, identity in operation['bindings'].items():
            if identity is not None and identity != _identity(path):
                raise RootOperationError('bootstrap_binding_mismatch: '+path)
            if identity is not None and state['bindings'].get(path) != identity:
                raise RootOperationError('bootstrap_reservation_mismatch: '+path)
        if init.get('bootstrap_id') not in (None, nonce):
            raise RootOperationError('bootstrap_reservation_mismatch: '+str(operation_path))
        if init.get('reservation_id') not in (None, nonce):
            raise RootOperationError('bootstrap_reservation_mismatch: '+str(operation_path))
    allowed = {'state.json', operation_path.name}
    if state.get('setup_reset', {}).get('history'):
        allowed.add(state['setup_reset']['history'])
    nonce = operation.get('reservation_id') if operation else init.get('reservation_id')
    if nonce:
        proof_name = 'finished-'+nonce+'.json'
        proof = _read(parent/proof_name, None)
        if proof is not None:
            if not operation or proof.get('receipt') != 'operation_returned_and_roots_verified' or proof.get('reservation') != operation:
                raise RootOperationError('bootstrap_completion_receipt_mismatch: '+str(parent/proof_name))
            allowed.add(proof_name)
    if init.get('bootstrap_id'):
        allowed.update({'bootstrap-completed-'+init['bootstrap_id']+'.json', 'bootstrap-operation-'+init['bootstrap_id']+'.json'})
    migration = state.get('control_migration') or {}
    if migration.get('receipt'): allowed.add(migration['receipt'])
    adoption_files = []
    for path in parent.glob('*.json'):
        if path.name.startswith('rc11-adoption-') and path.name not in allowed:
            adoption_files.append(path)
            continue  # exact token and complete receipt checked below
        if path.name not in allowed:
            raise RootOperationError('bootstrap_additional_operation: '+str(path))
    for path in parent.iterdir():
        if path.name.endswith('.json') or path.name.startswith('.pending-'): continue
        lock_name = path.name
        normal_lock = lock_name in {'workspace.lock','shared.lock','state.lock','trash-recovery.lock'}
        hashed_lock = any(lock_name.startswith(prefix) and lock_name.endswith('.lock') and len(lock_name[len(prefix):-5]) == 64 and all(c in '0123456789abcdef' for c in lock_name[len(prefix):-5]) for prefix in ('operation-','library-'))
        if not (normal_lock or hashed_lock): raise RootOperationError('bootstrap_unknown_control_entry: '+str(path))
        with qualified(path) as (fd, check):
            if os.fstat(fd).st_size != 0 or os.fstat(fd).st_uid != os.geteuid():
                raise RootOperationError('bootstrap_unknown_control_entry: '+str(path))
            check()
    legacy = None
    if migration.get('receipt'):
        receipt = migration_receipt(parent, migration['receipt'], root)
        legacy = receipt.get('legacy_lock')
    scan = tree(root, names, legacy=legacy, allow_legacy=state.get('format') == 1)
    if scan['issues']:
        row = scan['issues'][0]; raise RootOperationError(row['code']+': '+row['path']+': '+row['detail'])
    material = {'workspace': str(root), 'database': str(database), 'registry': str(registry),
                'state': raw_file(parent/'state.json'), 'operation': raw_file(operation_path) if operation else None,
                'legacy_lock': scan['legacy_lock'],
                'catalogues': {str(p): logical_database(p) for p in sorted(set(database.parent.rglob('*.sqlite3')) | {database, registry})}}
    token = digest(material)
    # Only RC11 temporary publications for this exact bootstrap's targets
    # are non-authoritative residue. Keep every byte and report it; never
    # parse a partial publication as committed state or a completion proof.
    targets = set(allowed) | {'rc11-adoption-'+token+'.json'}
    if nonce:
        targets.update({'bootstrap-completed-'+nonce+'.json', 'bootstrap-operation-'+nonce+'.json'})
    target_hashes = {hashlib.sha256(n.encode()).hexdigest()[:16] for n in targets}
    retained_publications = []
    for path in sorted(parent.glob('.pending-*')):
        pieces = path.name.split('-')
        if len(pieces) != 3 or pieces[1] not in target_hashes or len(pieces[2]) != 32 or any(c not in '0123456789abcdef' for c in pieces[2]):
            raise RootOperationError('bootstrap_uncommitted_publication_unknown: '+str(path))
        raw = raw_file(path)
        # Positive historical state in even an uncommitted complete document
        # cannot be discarded simply because its filename is technical.
        try: draft = json.loads(base64.b64decode(raw))
        except (ValueError, UnicodeDecodeError): draft = None
        if isinstance(draft, dict) and (draft.get('libraries') or type(draft.get('generation')) is int and draft['generation'] > state['generation']):
            raise RootOperationError('bootstrap_uncommitted_history: '+str(path))
        retained_publications.append({'path':str(path),'sha256':hashlib.sha256(base64.b64decode(raw)).hexdigest(),'disposition':'retained_uncommitted_not_authority'})
    adoption_name = 'rc11-adoption-'+token+'.json'
    for path in adoption_files:
        if path.name != adoption_name:
            raise RootOperationError('bootstrap_additional_operation: '+str(path))
        migration_receipt(parent, path.name, root)
    adoption = _read(parent/adoption_name, None)
    if state.get('format') == 1 and require_adoption:
        # An explicit old audited empty reset is already a separate admin decision,
        # but an open RC10 bootstrap is never silently adopted after ACL hardening.
        if not adoption or adoption.get('material') != material or adoption.get('confirmation') != CONFIRMATION:
            raise RootOperationError('bootstrap_administrative_review_required: '+str(parent)+': use python -m app.storage_admin inspect; secure private ACLs, preserve a consistent backup, then explicitly adopt this exact evidence')
    return {'token': token, 'material': material, 'operation': operation, 'operation_key': operation_key,
            'legacy_lock': scan['legacy_lock'], 'adoption': adoption, 'retained_publications':retained_publications}


def assert_no_orphan_legacy_lock(root):
    """A missing F14 state cannot authorize switching an existing RC10 lock."""
    from app.storage_config import load_storage_settings
    names = load_storage_settings(workspace_root=root)
    lock = Path(root)/names['metadata_directory_name']/'.trash-deletions/.lock'
    if lock.exists() or lock.is_symlink():
        raise RootOperationError('legacy_lock_without_control_state: '+str(lock)+': restore and review original F14 evidence before changing lock authority; artifact preserved')


def prepare_control(root, database):
    """Version fence before any RC11 domain lock; never silently adopt an intent."""
    from app.root_operations import _control, _read, _write, _lock
    root, parent = _control(root)
    with _lock(parent/'workspace.lock', exclusive=True), _lock(parent/'shared.lock', exclusive=True), _lock(parent/'state.lock', exclusive=True, wait=True):
        state = _read(parent/'state.json', None)
        if not state:
            assert_no_orphan_legacy_lock(root)
            return
        if state.get('format') == 2: return
        if state.get('format') != 1: raise RootOperationError('control_format_unsupported: '+str(parent))
        init = state.get('storage_initialization') or {}
        own = None; scan = None
        if init.get('phase') in ('initializing', 'completed') and any(parent.glob('operation-*.json')):
            own = evidence(root, database, state)
            receipt = own['adoption']
            receipt_name = 'rc11-adoption-'+own['token']+'.json'
        else:
            # Established installs do not become fresh; retain their original
            # state and every operation. Full domain recovery remains required.
            from app.storage_config import load_storage_settings
            scan = tree(root, load_storage_settings(workspace_root=root), allow_legacy=True)
            from app.storage_admin import control_evidence
            reviewed = control_evidence(root, Path(database))
            receipt_name = 'rc11-adoption-'+reviewed['token']+'.json'
            receipt = _read(parent/receipt_name, None)
            if not receipt or receipt.get('scope') != 'control' or receipt.get('material') != reviewed['material'] or receipt.get('confirmation') != CONFIRMATION:
                raise RootOperationError('control_administrative_review_required: '+str(parent)+': use python -m app.storage_admin inspect --scope control; earlier format-1 ACL provenance cannot be inferred from current modes')
            migration_receipt(parent, receipt_name, root)
        state['format'] = 2
        state['control_migration'] = {'receipt': receipt_name, 'previous_format': 1}
        if own:
            record = own['operation']
            state['storage_initialization'] = {**init, 'phase':'initializing', 'bootstrap_id': record['reservation_id'],
                'reservation_id': record['reservation_id'], 'operation_key': own['operation_key'],
                'registry': os.environ.get('KAMERA_REGISTRY_DATABASE', str(Path(database).parent/'bibliothekar-global.sqlite3')),
                'origin': 'migrated_rc10'}
        _write(parent/'state.json', state)


def begin(state, record, operation_key, names):
    previous = state.get('storage_initialization') or {}
    nonce = record['reservation_id']
    if previous.get('reservation_id') not in (None, nonce) or previous.get('bootstrap_id') not in (None, nonce):
        raise RootOperationError('bootstrap_reservation_mismatch: '+record['workspace'])
    state['format'] = 2
    state['storage_initialization'] = {**previous, 'phase': previous.get('phase', 'initializing'),
        'names': names, 'database': record['database'], 'registry':os.environ.get('KAMERA_REGISTRY_DATABASE', str(Path(record['database']).parent/'bibliothekar-global.sqlite3')), 'reservation_id': nonce,
        'operation_key': operation_key, 'bootstrap_id': previous.get('bootstrap_id', nonce),
        'origin': previous.get('origin', 'new_rc11')}


def technical_postconditions(root, database, state):
    from app.database import available_migrations
    from app.library_registry import REGISTRY_SCHEMA_VERSION
    from app.root_operations import _identity
    init = state['storage_initialization']
    registry = Path(init['registry'])
    expected_catalogue = {version for version, _ in available_migrations()}
    result = {}
    for path, table, expected in [(Path(database), 'schema_versions', expected_catalogue),
                                   (registry, 'registry_schema_versions', set(range(1,REGISTRY_SCHEMA_VERSION+1)))]:
        if not path.is_file() or not path.stat().st_size:
            raise RootOperationError('bootstrap_database_not_prepared: '+str(path))
        with qualified(path) as (_, check), closing(sqlite3.connect(path.absolute().as_uri()+'?mode=ro', uri=True)) as connection:
            connection.execute('BEGIN')
            versions = {row[0] for row in connection.execute('SELECT version FROM '+table)}
            if versions != expected or connection.execute('PRAGMA quick_check').fetchone()[0] != 'ok' or connection.execute('PRAGMA foreign_key_check').fetchall():
                raise RootOperationError('bootstrap_database_postcondition_failed: '+str(path))
            result[str(path)] = sorted(versions); check()
    for name in init['names'].values():
        path = str(Path(root)/name)
        if _identity(path) is None or state['bindings'].get(path) != _identity(path):
            raise RootOperationError('bootstrap_root_not_prepared: '+path)
    return result


def complete(root, record):
    """Called only after successful technical startup; workers are still gated."""
    from app.root_operations import _control_location, _read, _write, _lock, validate_active_roots
    parent = _control_location(root)
    validate_active_roots()
    state = _read(parent/'state.json')
    evidence(root, record['database'], state)
    schemas = technical_postconditions(root, record['database'], state)
    with _lock(parent/'state.lock', exclusive=True, wait=True):
        state = _read(parent/'state.json'); init = state['storage_initialization']
        init['phase'] = 'prepared'; _write(parent/'state.json', state)
        public = {k: v for k, v in record.items() if not k.startswith('_')}
        receipt = {'kind': 'rc11_bootstrap_completed', 'bootstrap_id': init['bootstrap_id'],
                   'reservation': public, 'registry':init['registry'], 'storage_names':init['names'], 'schema_versions':schemas, 'postconditions': 'technical_schema_registry_and_roots_verified'}
        name = 'bootstrap-completed-'+init['bootstrap_id']+'.json'
        old = _read(parent/name, None)
        if old is not None and old != receipt: raise RootOperationError('bootstrap_completion_receipt_mismatch: '+str(parent/name))
        if old is None: _write(parent/name, receipt)
        init['completion_receipt'] = name; init['phase'] = 'completed'
        _write(parent/'state.json', state)


def finish(root, parent, record):
    from app.root_operations import _read, _write
    state = _read(parent/'state.json'); init = state.get('storage_initialization') or {}
    receipt = _read(parent/('bootstrap-completed-'+record['reservation_id']+'.json'), None)
    if init.get('phase') != 'completed' or not receipt or receipt.get('reservation') != record:
        raise RootOperationError('bootstrap_completion_receipt_missing: '+str(parent))
    name = parent/('bootstrap-operation-'+record['reservation_id']+'.json')
    old = _read(name, None)
    if old is not None and old != record: raise RootOperationError('bootstrap_archive_mismatch: '+str(name))
    if old is None: _write(name, record)


def completed(root, state):
    from app.root_operations import _read, _control_location
    init = state.get('storage_initialization') or {}
    nonce = init.get('bootstrap_id')
    if not nonce: return state.get('format') == 1
    if not isinstance(nonce, str) or len(nonce) != 32 or any(c not in '0123456789abcdef' for c in nonce): return False
    parent = _control_location(root)
    receipt = _read(parent/('bootstrap-completed-'+nonce+'.json'), None)
    archived = _read(parent/('bootstrap-operation-'+nonce+'.json'), None)
    active = bool(init.get('operation_key') and (parent/('operation-'+init['operation_key']+'.json')).is_file())
    if not receipt or (archived is not None and archived != receipt.get('reservation')) or (archived is None and not active): return False
    return bool(receipt and receipt.get('kind') == 'rc11_bootstrap_completed' and receipt.get('bootstrap_id') == nonce
                and receipt.get('reservation', {}).get('reservation_id') == init.get('reservation_id')
                and receipt.get('reservation', {}).get('workspace') == str(root)
                and receipt.get('reservation', {}).get('database') == init.get('database')
                and receipt.get('registry') == init.get('registry')
                and receipt.get('storage_names') == init.get('names')
                and key_for(receipt['reservation']) == init.get('operation_key'))
