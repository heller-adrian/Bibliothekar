"""Cooperative root changes: process locks, generations and durable reservations.

Lock order is workspace -> shared stock -> library -> operation -> state. These locks coordinate
Bibliothekar processes, not external editors. A lost process leaves its exact
binding as evidence; a root change never guesses new paths for that operation.
"""
from __future__ import annotations

from contextlib import contextmanager, closing, nullcontext
from contextvars import ContextVar
from functools import wraps
from dataclasses import dataclass
from threading import RLock
from pathlib import Path
import fcntl
import hashlib
import inspect
import json
import os
import sqlite3
import stat
import tempfile
import time
import uuid

from app.appdata import managed as host_managed, root as appdata_root
from app.private_storage_security import RootOperationError, PrivateStorageError, qualified as private_qualified, check_acl as private_check_acl


class RootOperationBusy(RootOperationError):
    """A live kernel lock conflict, distinct from stale journal evidence."""
    def __init__(self, path):
        self.lock_path = str(path)
        super().__init__('Ein anderer Vorgang verwendet diesen Bereich. Bitte kurz warten und erneut versuchen.')


_ACTIVE = ContextVar('root_operations', default=())
_MUTATION = ContextVar('root_mutation', default=None)


@dataclass(frozen=True)
class _ViewBinding:
    library_id: str
    database_path: Path
    workspace_root: Path
    work_root: Path
    archive_root: Path
    root_generation: tuple
    identities: tuple
    aliases: tuple


_VIEWS = {}
_VIEW_LOCK = RLock()


def _plain_chain(path):
    """Inspect every absolute component without following a symbolic link."""
    path = Path(os.path.abspath(path))
    return tuple((str(parent), tuple(_identity(parent)))
                 for parent in [*reversed(path.parents), path])


def _check_view(binding):
    for path, identity in binding.identities:
        if tuple(_identity(path) or ()) != identity:
            raise RootOperationError('Kompatibilitätsansicht oder Erzeugerkontext wurde ausgetauscht.')
    for path, identity, target in binding.aliases:
        entry = Path(path).lstat()
        if (entry.st_dev, entry.st_ino) != identity or not stat.S_ISLNK(entry.st_mode):
            raise RootOperationError('Kompatibilitätsverknüpfung wurde ersetzt.')
        raw = os.readlink(path)
        actual = os.path.abspath(Path(path).parent / raw)
        if actual != target:
            raise RootOperationError('Kompatibilitätsverknüpfung besitzt ein fremdes Ziel.')
    if generation(binding.workspace_root, binding.library_id) != binding.root_generation:
        raise RootOperationError('Kompatibilitätsansicht besitzt eine veraltete Generation.')


def bind_compatibility_view(view, context, aliases):
    """Remember an explicit creator binding, never infer trust by resolving a link.

    This process-local receipt is intentionally unavailable after restart. A
    registered library always takes precedence over this legacy compatibility.
    """
    owner=_registered(context.database_path)
    if owner is not None and any(os.path.abspath(getattr(context,key))!=os.path.abspath(owner[key])
                                 for key in ('workspace_root','work_root','archive_root')):
        raise RootOperationError('Kompatibilitätsansicht besitzt eine veraltete registrierte Erzeugerbindung.')
    view = Path(os.path.abspath(view))
    identities = dict(_plain_chain(view))
    entries = []
    for name, target in aliases.items():
        target = Path(os.path.abspath(target))
        identities.update(_plain_chain(target))
        link = view / name
        info = link.lstat()
        if stat.S_ISLNK(info.st_mode):
            entries.append((str(link), (info.st_dev, info.st_ino), str(target)))
        elif link == target and stat.S_ISDIR(info.st_mode):
            # An exact directory entry needs identity binding, not a fictitious
            # symlink receipt. No different destination is inferred or resolved.
            identities.update(_plain_chain(link))
        else:
            raise RootOperationError('Kompatibilitätsansicht besitzt keinen eindeutigen Erzeugereintrag.')
    identities.update(_plain_chain(context.workspace_root))
    identities.update(_plain_chain(context.work_root))
    binding = _ViewBinding(str(context.library_id), Path(context.database_path).absolute(),
                           Path(context.workspace_root).absolute(), Path(context.work_root).absolute(),
                           Path(context.archive_root).absolute(),
                           tuple(context.root_generation or generation(context.workspace_root, context.library_id)),
                           tuple(identities.items()), tuple(entries))
    _check_view(binding)
    with _VIEW_LOCK:
        previous = _VIEWS.get((str(view), str(binding.database_path)))
        if previous is not None:
            _check_view(previous)
        _VIEWS[(str(view), str(binding.database_path))] = binding


def attest_legacy_plan_view(database, view, work, backup):
    """Legacy direct planner context: all roots must belong to the DB's parent.

    Production registered contexts never use this inference. The planner records
    only its exact two aliases, not arbitrary links supplied to a worker.
    """
    from types import SimpleNamespace
    if _registered(database) is not None:
        return
    creator = _view_context(view,database)
    if creator is not None:
        from app.storage_config import load_storage_settings
        if (Path(work).absolute() != creator.work_root or
            Path(backup).absolute() != creator.workspace_root/load_storage_settings(workspace_root=creator.workspace_root)['backup_directory_name']):
            raise RootOperationError('Planerwurzeln stimmen nicht mit dem nachgewiesenen Erzeugerkontext überein.')
        return
    database = Path(database).absolute()
    view, work, backup = map(lambda p: Path(os.path.abspath(p)), (view, work, backup))
    if not (view / 'Arbeitsbereich').is_symlink():
        return
    boundary = database.parent
    if any(not p.is_relative_to(boundary) for p in (view, work, backup)):
        raise RootOperationError('Legacy-Plan besitzt keine begrenzte Erzeugerbindung.')
    from app.storage_config import load_storage_settings
    name = load_storage_settings(workspace_root=backup.parent)['backup_directory_name']
    if backup.name != name:
        raise RootOperationError('Legacy-Plan besitzt keine eindeutige Sicherungswurzel.')
    context = SimpleNamespace(library_id='shared', database_path=database,
                              workspace_root=backup.parent, work_root=work,
                              archive_root=backup.parent, root_generation=None)
    bind_compatibility_view(view, context, {'Arbeitsbereich': work, name: backup})


def _view_context(view, database):
    if view is None or database is None:
        return None
    with _VIEW_LOCK:
        binding = _VIEWS.get((os.path.abspath(view), os.path.abspath(database)))
    if binding is not None:
        _check_view(binding)
    return binding


def canonical_workspace(view):
    """Resolve only a process-attested view; never guess from a tmp pathname."""
    path=os.path.abspath(view)
    with _VIEW_LOCK:
        matches=[binding for (root,_),binding in _VIEWS.items() if root==path]
    if not matches:return Path(path)
    if len({str(binding.workspace_root) for binding in matches})!=1:
        raise RootOperationError('Kompatibilitätsansicht besitzt mehrdeutige Workspace-Bindungen.')
    for binding in matches:_check_view(binding)
    return matches[0].workspace_root


def _identity(path):
    try:
        s = Path(path).stat(follow_symlinks=False)
    except FileNotFoundError:
        return None
    if not stat.S_ISDIR(s.st_mode):
        raise RootOperationError('Stammordner ist kein eindeutiges Verzeichnis: ' + str(path))
    return [s.st_dev, s.st_ino]


def _sync(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _write(path, value):
    path = Path(path)
    with private_qualified(path.parent, directory=True) as (parent_fd, check):
        name = '.pending-' + hashlib.sha256(path.name.encode()).hexdigest()[:16] + '-' + uuid.uuid4().hex
        fd = os.open(name, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600, dir_fd=parent_fd)
        try:
            private_check_acl(fd, {0, os.geteuid()}, path=path.parent/name)
            with os.fdopen(fd, 'w') as stream:
                fd = None
                json.dump(value, stream, sort_keys=True)
                stream.flush(); os.fsync(stream.fileno())
                private_check_acl(stream.fileno(), {0, os.geteuid()}, path=path.parent/name)
                expected = os.fstat(stream.fileno())
                current = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
                if (expected.st_dev, expected.st_ino) != (current.st_dev, current.st_ino):
                    raise RootOperationError('Private publication replaced: ' + str(path))
                check()
                os.replace(name, path.name, src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
                os.fsync(parent_fd)
        finally:
            if fd is not None: os.close(fd)
            try: os.unlink(name, dir_fd=parent_fd)
            except FileNotFoundError: pass


def _read(path, default=None):
    path = Path(path)
    if not path.parent.exists():
        # Qualify the nearest existing private ancestor before accepting absence.
        from app.private_storage_security import qualify_existing
        qualify_existing(path.parent)
        return default
    with private_qualified(path.parent, directory=True) as (parent_fd, check):
        for attempt in range(3):
            try:
                fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent_fd)
            except FileNotFoundError as error:
                check()
                if attempt:
                    raise RootOperationError('Operationsnachweis nach Austausch verschwunden: ' + str(path)) from error
                return default
            except OSError as error:
                raise RootOperationError('Operationsnachweis ist nicht lesbar: ' + str(path)) from error
            try:
                info = os.fstat(fd)
                if info.st_nlink == 0 and path.name == 'state.json' and attempt < 2:
                    current = os.stat(path.name, dir_fd=parent_fd, follow_symlinks=False)
                    if (current.st_dev, current.st_ino) != (info.st_dev, info.st_ino): continue
                private_check_acl(fd, {0, os.geteuid()}, path=path)
                if info.st_uid != os.geteuid() and not host_managed(path):
                    raise RootOperationError('Operationsnachweis besitzt keine sichere Eigentumsbindung: ' + str(path))
                with os.fdopen(os.dup(fd)) as stream:
                    value = json.load(stream)
                    private_check_acl(fd, {0, os.geteuid()}, path=path)
                check()
                return value
            except PrivateStorageError as error:
                # A concurrent atomic state publication unlinks the old inode.
                # Retry only that exact, observed exchange; all checks run again
                # on a freshly opened descriptor. Other files/errors stay fatal.
                held = fd
                if path.name == 'state.json' and attempt < 2 and error.code in {'control_file_invalid','private_file_invalid'}:
                    old = os.fstat(held)
                    current = os.stat(path.name, dir_fd=parent_fd, follow_symlinks=False)
                    if old.st_nlink == 0 and (old.st_dev,old.st_ino) != (current.st_dev,current.st_ino):
                        check()
                        continue
                raise
            except (OSError, ValueError) as error:
                raise RootOperationError('Operationsnachweis ist nicht lesbar: ' + str(path)) from error
            finally:
                if fd is not None: os.close(fd)
        raise RootOperationError('Operationsnachweis wurde wiederholt ausgetauscht: '+str(path))


def _control_location(root):
    root=Path(os.path.abspath(Path(root).expanduser()))
    candidates=[root.parent/'registry.sqlite3',root.parent/'bibliothekar-global.sqlite3']
    configured=os.environ.get('KAMERA_REGISTRY_DATABASE')
    if configured: candidates.insert(0, Path(configured))
    matches = {}
    for candidate in dict.fromkeys(candidates):
        if not candidate.is_file(): continue
        from app.private_storage_security import qualify_existing
        qualify_existing(candidate)
        try:
            with closing(sqlite3.connect(candidate.absolute().as_uri()+'?mode=ro', uri=True)) as c:
                if c.execute('SELECT 1 FROM libraries WHERE workspace_root=? LIMIT 1', (str(root),)).fetchone():
                    info = candidate.stat()
                    matches[(info.st_dev, info.st_ino)] = candidate
        except sqlite3.OperationalError as error:
            if 'no such table' not in str(error):
                raise RootOperationError('Gemeinsame Registry ist nicht sicher lesbar: '+str(candidate)) from error
    if len(matches) > 1:
        raise RootOperationError('Mehrere unabhängige Registries beanspruchen denselben Workspace; Operation gesperrt.')
    registry = next(iter(matches.values()), None)
    if registry is None:
        # Unregistered legacy contexts have no registry authority yet. Their
        # fixed sibling namespace is retained; registered contexts never infer
        # coordination from the mere existence of an unrelated SQLite file.
        registry=next((p for p in candidates if p.is_file() and p.parent==root.parent), None)
        if registry is None:
            registry=Path(configured) if configured else Path(os.environ.get('KAMERA_DATABASE_DIR',str(root.parent)))/'bibliothekar-global.sqlite3'
    return registry.parent/'.bibliothekar-root-control'/hashlib.sha256(str(root).encode()).hexdigest()


def _control(root, *, allow_missing=False):
    root = Path(os.path.abspath(Path(root).expanduser()))
    if _identity(root) is None and not allow_missing:
        raise RootOperationError('Workspace ist nicht verfügbar: ' + str(root))
    parent = _control_location(root)
    for directory in [parent.parent,parent]:
        with private_qualified(directory.parent, directory=True) as (fd, check):
            try:
                os.mkdir(directory.name, mode=0o700, dir_fd=fd)
                os.fsync(fd)
            except FileExistsError:
                pass
            check()
        with private_qualified(directory, directory=True) as (_, check): check()
        s = directory.stat(follow_symlinks=False)
        if not stat.S_ISDIR(s.st_mode) or (not host_managed(directory) and (s.st_uid != os.geteuid() or s.st_mode & 0o077)):
            raise RootOperationError('Interne Operationsnachweise sind nicht zugriffsgeschützt.')
    return root, parent


@contextmanager
def _lock(path, exclusive=False, wait=False, wait_seconds=0):
    path = Path(path)
    with private_qualified(path.parent, directory=True) as (parent_fd, check):
        fd = os.open(path.name, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600, dir_fd=parent_fd)
        try:
            def validate():
                check()
                value = private_check_acl(fd, {0, os.geteuid()}, path=path)
                current = os.stat(path.name, dir_fd=parent_fd, follow_symlinks=False)
                if value['identity'] != [current.st_dev, current.st_ino] or (os.fstat(fd).st_uid != os.geteuid() and not host_managed(path)):
                    raise RootOperationError('Ungültige interne Operationssperre: '+str(path))
            validate()
            deadline = time.monotonic() + wait_seconds
            while True:
                try:
                    fcntl.flock(fd, (fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH) | (0 if wait else fcntl.LOCK_NB))
                    break
                except BlockingIOError as error:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0: raise RootOperationBusy(path) from error
                    time.sleep(min(.02, remaining))
            validate()
            yield fd
            validate()
        finally: os.close(fd)


def _state(parent, root):
    value = _read(parent / 'state.json', None)
    if value is None:
        from app.storage_bootstrap import assert_no_orphan_legacy_lock
        assert_no_orphan_legacy_lock(root)
        value = {'format': 3 if appdata_root() else 2, 'workspace': _identity(root), 'generation': 0, 'libraries': {}, 'bindings': {}}
    if appdata_root() and value.get('format') != 3:
        raise RootOperationError('legacy_layout_requires_explicit_migration: '+str(parent))
    if value.get('format') not in (1, 2, 3) or value.get('workspace') != _identity(root):
        raise RootOperationError('Workspace-Identität hat sich außerhalb von Bibliothekar geändert.')
    return value


def generation(workspace, library_id):
    parent = _control_location(workspace)
    value = _read(parent / 'state.json', {})
    return (int(value.get('generation', 0)), int(value.get('libraries', {}).get(str(library_id), 0)))


def _assert_startable(parent, library=None):
    if (parent / 'mutation.json').exists() or (parent / 'mutation.json').is_symlink():
        record=_read(parent/'mutation.json')
        if library is not None and record and record.get('library') not in (None,library):return
        raise RootOperationError('Unvollständiger Stammordnerwechsel: Pfade und Nachweise müssen vor weiteren Dateioperationen geprüft werden. Es wird nichts automatisch umgeschrieben.')


def assert_workspace_startable(workspace, *, check_identity=True):
    parent = _control_location(workspace)
    if parent.exists():
        _assert_startable(parent)
        if check_identity:_state(parent, Path(workspace))


def _check(bindings):
    for path, identity in bindings.items():
        if identity is not None and _identity(path) != identity:
            raise RootOperationError('Stammordner wurde außerhalb von Bibliothekar verändert; Vorgang gestoppt: ' + path)


def validate_active_roots():
    from app.operation_health import require_write
    roots={r['workspace'] for r in _ACTIVE.get()}
    for root in roots:require_write(root)
    for record in _ACTIVE.get():
        from app.storage_anchors import check_active
        check_active(record['workspace'],record['_parent'])
        _check(record['bindings'])
        additions={path:_identity(path) for path,identity in record['bindings'].items() if identity is None}
        additions={path:identity for path,identity in additions.items() if identity is not None}
        if additions:
            parent=record['_parent']
            with _lock(parent/'state.lock',exclusive=True,wait=True):
                state=_state(parent,Path(record['workspace']))
                for path,identity in additions.items():
                    if state['bindings'].get(path) not in (None,identity):
                        raise RootOperationError('Neu angelegter Stammordner besitzt eine widersprüchliche Identität: '+path)
                    state['bindings'][path]=identity;record['bindings'][path]=identity
                if not record.get('_ephemeral'):
                    _write(parent/'state.json',state)
                    _write(record['_path'],{k:v for k,v in record.items() if not k.startswith('_')})


def _registered(database, library_id=None, workspace=None):
    """Read existing registries only; never create a guessed registry."""
    if database is None and (library_id is None or workspace is None):
        return None
    database = Path(database).absolute() if database else None
    directory=database.parent if database else Path(workspace).absolute().parent
    candidates = [directory/'registry.sqlite3', directory/'bibliothekar-global.sqlite3']
    configured = os.environ.get('KAMERA_REGISTRY_DATABASE')
    if configured:
        candidates.insert(0, Path(configured))
    for path in dict.fromkeys(candidates):
        if not path.is_file():
            continue
        try:
            with closing(sqlite3.connect(path.as_uri()+'?mode=ro', uri=True)) as c:
                c.row_factory = sqlite3.Row
                row = c.execute('SELECT * FROM libraries WHERE database_path=?' if database else 'SELECT * FROM libraries WHERE library_id=?', (str(database) if database else str(library_id),)).fetchone()
                if row:
                    return dict(row)
        except sqlite3.OperationalError as error:
            if 'no such table' not in str(error):
                raise RootOperationError('Registry kann nicht sicher geprüft werden: ' + str(path)) from error
    return None


def _receipt_completed(record):
    nonce = record.get('reservation_id')
    if not nonce:
        return False
    if not isinstance(nonce, str) or len(nonce) != 32 or any(c not in '0123456789abcdef' for c in nonce):
        raise RootOperationError('Reservationsidentität ist ungültig.')
    receipt = _read(_control_location(record['workspace']) / ('finished-'+nonce+'.json'))
    if receipt is None:
        return False
    if receipt.get('reservation') != record:
        raise RootOperationError('Abschlussnachweis gehört nicht zur unterbrochenen Reservation.')
    if receipt.get('receipt') == 'operation_returned_and_roots_verified':
        return True
    if receipt.get('receipt') != 'backup_domain_finished' or receipt.get('disposition') not in {'rolled_back','completed'}:
        raise RootOperationError('Unbekannter fachlicher Abschlussnachweis.')
    journal = Path(receipt['journal'])
    if _identity(journal.parent) != receipt['journal_parent_identity']:
        raise RootOperationError('Journalverzeichnis wurde nach dem Abschluss ausgetauscht.')
    # The domain proof is durable BEFORE journal cleanup. A crash during that
    # cleanup must still block root changes until normal recovery finishes it.
    return not os.path.lexists(journal)


def active_backup_reservation(database, central_root, job_id):
    for record in reversed(_ACTIVE.get()):
        if (record['kind'] == 'backup' and record['database'] == str(Path(database).absolute())
            and record['ids'].get('job_id') == str(job_id)
            and record['ids'].get('function') == 'app.backup_management.delete_backup'
            and str(Path(central_root).absolute()) in record['bindings']):
            return {k:v for k,v in record.items() if not k.startswith('_')}
    return None


def finish_backup_reservation(record, *, database, central_root, job_id, journal, disposition):
    """Called only after backup code verified its exact terminal domain state.

    No missing journal or generic exception is considered completion evidence.
    Existing journals without a root receipt remain recoverable as before.
    """
    if record is None:
        return
    if (record.get('kind') != 'backup' or record.get('database') != str(Path(database).absolute())
        or record.get('ids',{}).get('job_id') != str(job_id)
        or record.get('ids',{}).get('function') != 'app.backup_management.delete_backup'
        or str(Path(central_root).absolute()) not in record.get('bindings',{})):
        raise RootOperationError('Sicherungsabschluss gehört nicht zur ursprünglichen Reservation.')
    root,parent = _control(record['workspace'])
    key = hashlib.sha256(json.dumps([record['library'],record['kind'],str(record['database']),record['ids']],sort_keys=True).encode()).hexdigest()
    owned = any(r.get('reservation_id') == record.get('reservation_id') for r in _ACTIVE.get())
    with (nullcontext() if owned else _lock(parent/('operation-'+key+'.lock'),exclusive=True)):
        if _read(parent/('operation-'+key+'.json')) != record:
            raise RootOperationError('Ursprünglicher Reservationsnachweis fehlt oder hat sich geändert.')
        _check(record['bindings'])
        if tuple(record['generation']) != generation(root, record['library']):
            raise RootOperationError('Sicherungsabschluss besitzt eine veraltete Generation.')
        _write(parent/('finished-'+record['reservation_id']+'.json'),
               {'receipt':'backup_domain_finished','reservation':record,'disposition':disposition,
                'journal':str(journal),'journal_parent_identity':_identity(journal.parent)})


def _completed(record):
    if _receipt_completed(record):
        return True
    database = record.get('database')
    ids = record.get('ids', {})
    if not database or not Path(database).is_file():
        return False
    checks = {
        'import': ('SELECT state FROM jobs WHERE id=?', [ids.get('job_id')], {'completed','discarded'}),
        'sort': ('SELECT status FROM sort_runs WHERE id=?', [ids.get('run_id')], {'applied','rolled_back'}),
        'ssd': ("SELECT status FROM event_ssd_releases WHERE job_id=? AND event_id=? ORDER BY created_at DESC LIMIT 1", [ids.get('job_id'),ids.get('event_id')], {'completed'}),
    }
    if record.get('kind') not in checks:
        return False
    sql, values, terminal = checks[record['kind']]
    if any(x is None for x in values):
        return False
    with closing(sqlite3.connect(Path(database).as_uri()+'?mode=ro', uri=True)) as c:
        row = c.execute(sql, values).fetchone()
        return bool(row and row[0] in terminal)


@contextmanager
def admission(context, *, allow_missing_legacy=False):
    from app.operation_scopes import admission as scoped_admission
    with scoped_admission(context.workspace_root, context.library_id):
        with _admission(context, allow_missing_legacy=allow_missing_legacy):
            yield


@contextmanager
def _admission(context, *, allow_missing_legacy=False):
    """Short, nonpersistent gate before request/claim SQLite transactions.

    All domain mutations still own their existing durable journal/reservation.
    Idle claims therefore write neither state JSON nor completion receipts.
    Lock order is identical to a shared file operation.
    """
    from app.operation_health import require_write
    require_write(context.workspace_root)
    from app.managed_storage_health import require_pinned_storage
    require_pinned_storage(context.workspace_root)
    root,parent = _control(context.workspace_root,allow_missing=allow_missing_legacy)
    library = str(context.library_id)
    owner = _MUTATION.get()
    owned = owner is not None and owner['workspace'] == str(root) and owner['library'] is None
    if owner is not None and not owned:
        raise RootOperationError('Lokale Stammänderung darf keine neue Auftragsannahme beginnen.')
    with (nullcontext() if owned else _lock(parent/'workspace.lock')), (nullcontext() if owned else _lock(parent/'shared.lock')), (nullcontext() if owned else _lock(parent/('library-'+hashlib.sha256(library.encode()).hexdigest()+'.lock'))):
        if not owned:_assert_startable(parent,library)
        state = _state(parent,root)
        expected = getattr(context,'root_generation',None)
        current = (state['generation'],state['libraries'].get(library,0))
        if expected is not None and tuple(expected) != current:
            raise RootOperationError('Auftrag verwendet eine veraltete Stammordnergeneration. Bitte erneut anfordern.')
        row = _registered(context.database_path)
        if row is None:
            candidate = _registered(None,library_id=library,workspace=root)
            if candidate and os.path.abspath(candidate['workspace_root']) == str(root):row = candidate
        if row is not None and not Path(context.database_path).is_file():
            raise RootOperationError('Registrierte Bibliotheksdatenbank fehlt; sie wird nicht leer neu angelegt.')
        if row is not None and _identity(root) is None:
            raise RootOperationError('Registrierter Workspace ist nicht verfügbar; Auftrag wird nicht übernommen.')
        if row and any(os.path.abspath(getattr(context,key)) != os.path.abspath(row[key])
                       for key in ['workspace_root','work_root','archive_root','database_path']):
            raise RootOperationError('Bibliotheksbindung hat sich vor der Auftragsannahme geändert.')
        from app.storage_config import load_storage_settings
        paths = [root,context.work_root,context.archive_root,*(root/name for name in load_storage_settings(workspace_root=root).values())]
        observed = {str(Path(path).absolute()):_identity(path) for path in paths}
        for path,identity in observed.items():
            if state['bindings'].get(path) is not None and state['bindings'][path] != identity:
                raise RootOperationError('Stammordner wurde vor der Auftragsannahme ausgetauscht: '+path)
        yield
        _check({path:identity for path,identity in observed.items() if identity is not None})


@contextmanager
def reserve(workspace, *, library_id='shared', paths=(), database=None, kind='operation', ids=None, expected_generation=None, shared=None, operation_wait=0, _recovery_record=None, durable=True):
    if not durable:
        from app.observation_recovery import FUNCTIONS
        if FUNCTIONS.get((ids or {}).get('function')) != kind:
            raise RootOperationError('Only audited media-read-only functions may use a transient reservation.')
    from app.operation_health import require_write
    candidate={'kind':kind,'library':str(library_id),'database':str(Path(database).absolute()) if database is not None else None,'ids':ids or {}}
    require_write(workspace,candidate=candidate)
    from app.managed_storage_health import require_pinned_storage
    require_pinned_storage(workspace,initializing=(kind=='startup' and bool((ids or {}).get('initialize_storage'))))
    root, parent = _control(workspace)
    library_id = str(library_id)
    database=Path(database).absolute() if database is not None else None
    shared = bool(library_id == 'shared' or kind in {'startup', 'trash', 'backup'}) if shared is None else shared
    if _recovery_record is not None:
        if not durable:raise RootOperationError('Recovery requires its original durable reservation.')
        from app.operation_health import _TECHNICAL_STARTUP_IDS
        metadata_retry=kind=='metadata' and (ids or {}).get('function') in {
            'app.metadata_correction.execute_metadata_correction','app.metadata_correction.apply_metadata_correction'}
        technical_retry=kind=='startup' and ids==_TECHNICAL_STARTUP_IDS
        from app.domain_recovery import approved
        domain_retry=approved(_recovery_record)
        if not (metadata_retry or technical_retry or domain_retry):
            raise RootOperationError('Fachliche Wiederaufnahme ist nicht für diesen Auftrag freigegeben.')
    nested = next((r for r in _ACTIVE.get() if r['workspace']==str(root) and r['library']==library_id), None)
    if nested:
        if nested.get('_ephemeral') and durable:
            raise RootOperationError('An observational scan cannot authorize a durable media mutation.')
        if _recovery_record is not None:
            raise RootOperationError('Fachliche Wiederaufnahme benötigt ihre eigene ursprüngliche Reservation.')
        if shared and not nested.get('shared', False):
            raise RootOperationError('Gemeinsamer Bestand benötigt eine vorab erworbene Reservation; verschachtelte Erweiterung ist gesperrt.')
        if nested['database'] != (str(database) if database else None):
            raise RootOperationError('Verschachtelter Auftrag verwendet eine andere Datenbankbindung.')
        if expected_generation is not None and tuple(expected_generation) != tuple(nested['generation']):
            raise RootOperationError('Verschachtelter Auftrag verwendet eine veraltete Generation.')
        validate_active_roots()
        # Reentrant calls must attest additional roots as durably as the caller.
        with _lock(parent/'state.lock', exclusive=True, wait=True):
            state = _state(parent, root)
            from app.operation_scopes import resources
            outer=resources(nested)
            additional=resources(candidate)-outer
            if additional:
                # Nested work cannot disappear from the outer durable intent
                # merely because its original function named fewer resources.
                nested['effect_resources']=sorted(outer | additional)
            for path in (paths() if callable(paths) else paths):
                if path is None: continue
                path = os.path.abspath(path); identity = _identity(path)
                known = nested['bindings'].get(path, state['bindings'].get(path))
                if known is not None and known != identity:
                    raise RootOperationError('Verschachtelte Stammordnerbindung hat sich geändert: '+path)
                nested['bindings'][path] = identity
                if identity is not None: state['bindings'][path] = identity
            if not nested.get('_ephemeral'):
                _write(parent/'state.json', state)
                _write(nested['_path'], {k:v for k,v in nested.items() if not k.startswith('_')})
        yield nested
        validate_active_roots()
        return
    key = hashlib.sha256(json.dumps([library_id,kind,str(database),ids or {}],sort_keys=True).encode()).hexdigest()
    owner = _MUTATION.get()
    owned_mutation = owner is not None and owner['workspace'] == str(root) and owner['library'] is None
    if owner is not None and not owned_mutation:
        raise RootOperationError('Dateioperation darf keine lokale Stammordnermutation erweitern.')
    # A global root mutation already owns the complete lock scope. Its child
    # initialization still gets a separate durable operation record; it never
    # overwrites the parent's mutation intent or starts an unreserved worker.
    with (nullcontext() if owned_mutation else _lock(parent/'workspace.lock')), (nullcontext() if owned_mutation or not shared else _lock(parent/'shared.lock')), (nullcontext() if owned_mutation else _lock(parent/('library-'+hashlib.sha256(library_id.encode()).hexdigest()+'.lock'))), _lock(parent/('operation-'+key+'.lock'), exclusive=True, wait_seconds=operation_wait):
        if not owned_mutation:_assert_startable(parent, library_id)
        with _lock(parent/'state.lock', exclusive=True, wait=True):
            previous_state=_read(parent/'state.json',None)
            owner_row=(_registered(database) if database is not None else
                       _registered(None,library_id=library_id if library_id!='shared' else 'main',workspace=root))
            if previous_state is None and owner_row and owner_row.get('is_registered',True):
                raise RootOperationError('Registered installation lost its control state: '+str(parent))
            state = _state(parent, root)
            current = (state['generation'],state['libraries'].get(library_id,0))
            if expected_generation is not None and tuple(expected_generation)!=current:
                raise RootOperationError('Auftrag verwendet eine veraltete Stammordner-/Bibliotheksgeneration. Bitte erneut anfordern.')
            bindings = {str(root): _identity(root)}
            known_before=dict(state['bindings'])
            for path in (paths() if callable(paths) else paths):
                if path is None:
                    continue
                path = str(Path(path).expanduser().absolute())
                identity = _identity(path)
                if path in state['bindings'] and state['bindings'][path] is not None and state['bindings'][path]!=identity:
                    raise RootOperationError('Stammordneridentität stimmt nicht mehr mit der Reservation überein: '+path)
                if identity is not None:
                    state['bindings'][path]=identity
                bindings[path]=identity
            old = _read(parent/('operation-'+key+'.json'))
            if old and not durable:
                raise RootOperationError('Historical inventory requires verified recovery before a new scan.')
            if _recovery_record is not None and old != _recovery_record:
                raise RootOperationError('Ursprüngliche Wiederaufnahme-Reservation wurde verändert.')
            if old:
                previous=old.get('bindings',{})
                # Nested recovery may have durably extended the outer startup
                # binding before SIGKILL. Retain every extra identity; never
                # infer a new root or discard an old one on the next startup.
                changed=old.get('generation')!=list(current) or not bindings.keys() <= previous.keys()
                for path in previous.keys() - bindings.keys():
                    bindings[path] = _identity(path)
                changed=changed or any(identity is not None and bindings.get(path)!=identity for path,identity in previous.items())
                changed=changed or any(identity is None and bindings[path] is not None and known_before.get(path)!=bindings[path] and not (kind=='startup' and (ids or {}).get('initialize_storage') and path in {str(root/n) for n in state.get('storage_names',{}).values()}) for path,identity in previous.items())
                if changed:raise RootOperationError('Unterbrochener Auftrag besitzt eine andere Stammordnerbindung. Nachweise bleiben erhalten.')
            nonce = old.get('reservation_id') if old else None
            init = state.get('storage_initialization') or {}
            if not nonce and kind == 'startup' and (ids or {}).get('initialize_storage') and init.get('operation_key') == key:
                nonce = init.get('reservation_id')
            if _recovery_record is None and nonce and (parent/('finished-'+nonce+'.json')).exists() and _completed(old) and not (kind == 'startup' and (ids or {}).get('initialize_storage')):
                nonce = None  # a repeated successful operation is a new execution
            record = {'format':1,'reservation_id':nonce or uuid.uuid4().hex,'shared':shared,'workspace':str(root),'library':library_id,'generation':list(current),'bindings':bindings,'database':str(Path(database).absolute()) if database else None,'kind':kind,'ids':ids or {}}
            if old and 'effect_resources' in old:
                record['effect_resources']=old['effect_resources']
            if kind == 'startup':
                from app.storage_config import load_storage_settings
                names=load_storage_settings(workspace_root=root)
                if state.get('storage_names') not in (None,names):
                    raise RootOperationError('Verwaltungsordnernamen widersprechen den gespeicherten Bindungen.')
                state['storage_names']=names
                if (ids or {}).get('initialize_storage'):
                    from app.storage_bootstrap import begin
                    begin(state, record, key, names)
            if state.get('format') == 3:
                from app.appdata import mount
                pinned = state.setdefault('mounts',{})
                for path in bindings:
                    current_mount = mount(path)
                    if path in pinned and pinned[path] != current_mount:
                        raise RootOperationError('mount_identity_changed: '+path)
                    pinned[path] = current_mount
            if durable or previous_state is None:
                _write(parent/'state.json',state)
            if durable:
                _write(parent/('operation-'+key+'.json'),record)
        record['_parent']=parent;record['_path']=parent/('operation-'+key+'.json');record['_resumed']=bool(old)
        record['_ephemeral']=not durable
        token = _ACTIVE.set((*_ACTIVE.get(), record))
        completed = False
        try:
            yield record
            completed = True
        except Exception as error:
            if not durable:
                try:
                    validate_active_roots()
                    from app.observation_recovery import record_failure
                    record_failure(record,error)
                except Exception as audit_error:
                    # A locked/unwritable database cannot turn a failed audit
                    # into a false successful observation or mask the cause.
                    error.add_note('Observation failure audit unavailable: '+str(audit_error))
                    print('Observation failure audit unavailable: '+str(audit_error),flush=True)
            raise
        finally:
            # Only our own fully bound reservation is released. SIGKILL never
            # executes this block; identity uncertainty keeps durable evidence.
            try:
                validate_active_roots()
                if not durable:
                    # Audited observers/preparations never change media. SQL
                    # plans are committed atomically before a durable executor
                    # may begin; they remain queued after a process restart.
                    # Their SQLite transactions
                    # commit or roll back; process death cannot leave a file
                    # mutation requiring a durable F14 recovery intent.
                    pass
                elif completed or (_recovery_record is None and _receipt_completed({k:v for k,v in record.items() if not k.startswith('_')})):
                    if kind == 'startup' and (ids or {}).get('initialize_storage'):
                        from app.storage_bootstrap import finish
                        finish(root, parent, {k:v for k,v in record.items() if not k.startswith('_')})
                    from app.operation_health import _TECHNICAL_STARTUP_IDS
                    if kind=='startup' and ids==_TECHNICAL_STARTUP_IDS:
                        permanent=parent/('technical-startup-'+record['reservation_id']+'.json')
                        outcome={'format':1,'receipt':'technical_setup_returned_and_roots_verified',
                                 'reservation':{k:v for k,v in record.items() if not k.startswith('_')}}
                        previous=_read(permanent,None)
                        if previous is not None and previous!=outcome:
                            raise RootOperationError('Technischer Abschlussnachweis widerspricht der ursprünglichen Reservation.')
                        if previous is None:_write(permanent,outcome)
                    proof = parent / ('finished-'+record['reservation_id']+'.json')
                    _write(proof, {'receipt': 'operation_returned_and_roots_verified',
                                   'reservation': {k:v for k,v in record.items() if not k.startswith('_')}})
                    (parent/('operation-'+key+'.json')).unlink()
                    _sync(parent)
                    proof.unlink(); _sync(parent)
                    # The original RC14 lease must finish durably BEFORE its
                    # next family may run in the same pre-qualified API batch.
                    from app.operation_health import note_completed_retry
                    note_completed_retry(record)
                # An exception is not proof of rollback. Keep the exact binding
                # until an explicit retry or a verified domain recovery finishes.
            finally:_ACTIVE.reset(token)


def protect(*, workspace_arg=None, database_arg='database_path', kind='operation', error_type=RootOperationError, context_provider=None, db_only_if_no_roots=False, operation_wait=0, durable=True):
    def decorate(fn):
        from app.operation_scopes import register
        register(fn, kind)
        signature=inspect.signature(fn)
        @wraps(fn)
        def call(*args, **kwargs):
            bound=signature.bind(*args,**kwargs);bound.apply_defaults();a=bound.arguments
            database=a.get(database_arg)
            context=context_provider(a) if context_provider else a.get('library_context')
            if context is not None:
                database=context.database_path
            row=_registered(database,library_id=a.get('library_id'),workspace=a.get(workspace_arg))
            if row and not row.get('is_registered', True) and any(r.get('kind') == 'startup' and r.get('ids', {}).get('initialize_storage') for r in _ACTIVE.get()):
                from app.managed_storage_health import empty_bootstrap_registry, catalog_has_history
                try:
                    if not catalog_has_history(database) and empty_bootstrap_registry(os.environ['KAMERA_REGISTRY_DATABASE'], Path(row['workspace_root']), database):
                        row = None  # Exact unused technical placeholder, not a domain context.
                except (ValueError, KeyError): pass
            if row and database is None:database=Path(row['database_path'])
            view_context = _view_context(a.get(workspace_arg), database) if row is None and context is None else None
            if view_context is not None: context = view_context
            if row and context and any(Path(getattr(context,k)).absolute()!=Path(row[k]).absolute() for k in ['workspace_root','work_root','archive_root']):
                raise error_type('Auftrag verwendet veraltete Bibliothekspfade. Bitte erneut anfordern.')
            inherited_scope=next((r for r in _ACTIVE.get() if database is not None and r.get('database')==str(Path(database).absolute())),None)
            workspace=Path(row['workspace_root']) if row else (context.workspace_root if context else (Path(inherited_scope['workspace']) if inherited_scope else a.get(workspace_arg)))
            legacy_paths=[]
            if workspace is None and kind=='recovery' and database is not None:
                with closing(sqlite3.connect(Path(database).absolute().as_uri()+'?mode=ro',uri=True)) as c:
                    roots=c.execute("SELECT source_root,target_root FROM sort_runs WHERE status='interrupted'").fetchall()
                if not roots:
                    # This entry point only reads when no interrupted run exists.
                    return fn(*args,**kwargs)
                workspace=Path(database).absolute().parent
                legacy_paths=[Path(p).absolute() for pair in roots for p in pair if p]
                if any(not p.is_relative_to(workspace) for p in legacy_paths):
                    raise error_type('Legacy-Recovery besitzt keine registrierte Workspace-Bindung.')
            if workspace is None and a.get('archive_root') is not None:
                workspace=Path(a['archive_root']).absolute()
                while not workspace.exists() and workspace!=workspace.parent:workspace=workspace.parent
            if workspace is None and db_only_if_no_roots and row is None and a.get('archive_root') is None:
                return fn(*args,**kwargs)
            if workspace is None:
                # No mutation or path resolution may happen without a scope.
                raise error_type('Dateioperation besitzt keine überprüfbare Workspace-Bindung.')
            if row is None and kind in ['inventory','verification']:
                workspace=Path(workspace).absolute()
                while not workspace.exists() and workspace!=workspace.parent:workspace=workspace.parent
            def paths():
                from app.storage_config import load_storage_settings
                result=[Path(workspace),*(Path(workspace)/name for name in load_storage_settings(workspace_root=Path(workspace)).values())]
                result.extend(legacy_paths)
                result.extend(Path(a[key]).absolute() for key in ['archive_root','storage_root','work_root','central_root'] if a.get(key) is not None)
                if row:result.extend([Path(row['work_root']),Path(row['archive_root'])])
                elif context:result.extend([context.work_root,context.archive_root])
                return result
            ids={k:str(a[k]) for k in ['job_id','event_id','run_id','batch_id','cr_id','correction_id','operation_id','root_kind','area','relative_path','reference_relative_path','expected_preview_fingerprint'] if a.get(k) is not None}
            ids['function']=fn.__module__+'.'+fn.__qualname__
            if a.get('relative_paths') is not None:ids['relative_paths']=json.dumps(sorted(map(str,a['relative_paths'])))
            if isinstance(a.get('job'),dict):ids['job_id']=str(a['job']['id'])
            library=str(row['library_id']) if row else (context.library_id if context else (inherited_scope['library'] if inherited_scope else str(a.get('library_id') or 'shared')))
            if not row and context is None:
                inherited=next((r for r in _ACTIVE.get() if r['workspace']==os.path.abspath(Path(workspace))),None)
                if inherited:
                    library=inherited['library'];database=inherited['database']
            global_import = kind == 'import' and (
                a.get('central_stock') is True or
                (isinstance(a.get('job'), dict) and a['job'].get('operation') in {
                    'folder_import', 'metadata_multiple_import', 'metadata_general_import', 'trash_import', 'sd_recheck'
                })
            )
            expected=getattr(context,'root_generation',None) if context else None
            if expected is None:expected=generation(workspace,library)
            try:
                from app.operation_health import read_only
                if not durable and read_only():
                    # Pure snapshots keep the same pinned-root authority but
                    # never acquire/persist a write reservation during a GET.
                    from app.managed_storage_health import require_pinned_storage
                    require_pinned_storage(workspace)
                    if kind!='inventory':raise RootOperationError('Unsupported read-only observer.')
                    if view_context is not None:_check_view(view_context)
                    if row and a.get('storage_root') is not None:
                        role={'shared_workspace':'work_root','camera_archive':'archive_root'}.get(a.get('root_kind'))
                        if role is None or os.path.abspath(a['storage_root'])!=os.path.abspath(row[role]):
                            raise RootOperationError('Inventur verwendet keine aktuelle registrierte Dateiwurzel.')
                    if tuple(expected)!=generation(workspace,library):
                        raise RootOperationError('Read view uses a stale root generation.')
                    observed={str(path):_identity(path) for path in paths()}
                    if fn.__module__== 'app.event_inventory':
                        result=fn(*args,**kwargs)
                    else:
                        from app.observation_recovery import read_snapshot
                        result=read_snapshot(fn.__module__+'.'+fn.__qualname__,database,workspace)
                    _check(observed)
                    if tuple(expected)!=generation(workspace,library):
                        raise RootOperationError('Read view root generation changed during scan.')
                    return result
                with reserve(workspace,library_id=library,paths=paths,database=database,kind=kind,ids=ids,expected_generation=expected,operation_wait=operation_wait, durable=durable, shared=True if global_import or kind in {'trash','backup','import_cleanup'} or (database_arg == 'None' and kind == 'recovery') else None) as reservation:
                    if view_context is not None: _check_view(view_context)
                    if context:reservation['_context_work_root']=str(context.work_root)
                    current=_registered(database) if row else None
                    if row and (current is None or any(current[k]!=row[k] for k in ['workspace_root','work_root','archive_root','database_path'])):
                        raise RootOperationError('Bibliotheksbindung hat sich vor Beginn der Dateioperation geändert.')
                    if row and a.get('archive_root') is not None and Path(a['archive_root']).resolve(strict=False)!=Path(row['archive_root']).resolve(strict=False):
                        raise RootOperationError('Auftrag verwendet eine veraltete Archivwurzel.')
                    if row and a.get('storage_root') is not None:
                        role = {'shared_workspace': 'work_root', 'camera_archive': 'archive_root'}.get(a.get('root_kind'))
                        if role is None or os.path.abspath(a['storage_root']) != os.path.abspath(row[role]):
                            raise RootOperationError('Inventur verwendet keine aktuelle registrierte Dateiwurzel.')
                    if row and a.get('central_root') is not None:
                        from app.storage_config import load_storage_settings
                        current_backup = Path(row['workspace_root']) / load_storage_settings(workspace_root=Path(row['workspace_root']))['backup_directory_name']
                        if os.path.abspath(a['central_root']) != str(current_backup):
                            raise RootOperationError('Auftrag verwendet eine veraltete zentrale Sicherungswurzel.')
                    provided=a.get(workspace_arg)
                    if row and provided is not None and kind in ['sort','ssd','plan']:
                        from app.workspace_layout import shared_work_root
                        if shared_work_root(Path(provided)).resolve(strict=False)!=Path(row['work_root']).resolve(strict=False):
                            raise RootOperationError('Auftrag besitzt keine aktuelle Bindung an die registrierte Arbeitswurzel.')
                    if row and provided is not None and workspace_arg in ['workspace','workspace_path','workspace_root'] and Path(provided).resolve(strict=False)!=Path(row['workspace_root']).resolve(strict=False):
                        alias=Path(provided)/'Arbeitsbereich'
                        if alias.is_symlink() and alias.resolve(strict=False)!=Path(row['work_root']).resolve(strict=False):
                            raise RootOperationError('Kompatibilitätsansicht verwendet eine veraltete Arbeitswurzel.')
                    return fn(*args,**kwargs)
            except RootOperationError as error:
                raise error_type(str(error)) from error
        return call
    return decorate


def _require_coordinated_topology(root, databases):
    """Different workspace namespaces cannot share a root mutation safely yet.

    File operations remain available. Only configuration mutations are refused;
    no registry is rewritten and no inactive library is silently ignored.
    """
    candidates = [root.parent/'registry.sqlite3',root.parent/'bibliothekar-global.sqlite3']
    if os.environ.get('KAMERA_REGISTRY_DATABASE'):candidates.insert(0,Path(os.environ['KAMERA_REGISTRY_DATABASE']))
    for database in databases:
        candidates.extend([Path(database).parent/'registry.sqlite3',Path(database).parent/'bibliothekar-global.sqlite3'])
    for path in dict.fromkeys(candidates):
        if not path.is_file():continue
        try:
            with closing(sqlite3.connect(path.absolute().as_uri()+'?mode=ro',uri=True)) as c:
                roots={os.path.abspath(row[0]) for row in c.execute('SELECT workspace_root FROM libraries')}
        except sqlite3.OperationalError as error:
            if 'no such table' in str(error):continue
            raise RootOperationError('Registry-Topologie kann nicht geprüft werden.') from error
        if str(root) in roots and len(roots)>1:
            raise RootOperationError('Stammänderung bei mehreren Workspace-Namensräumen ist derzeit nicht sicher koordiniert und bleibt gesperrt.')


@contextmanager
def mutate(workspace, *, library_id=None, databases=(), changed_paths=None, rollback_check=None, expected_generation=None, precondition=None, details=None, wait_seconds=0, staging_precondition=None):
    from app.operation_health import require_write
    require_write(workspace)
    from app.managed_storage_health import require_pinned_storage
    require_pinned_storage(workspace)
    root,parent=_control(workspace)
    library=str(library_id) if library_id is not None else None
    owner = _MUTATION.get()
    if owner is not None:
        if owner['workspace'] != str(root) or (owner['library'] is not None and owner['library'] != library):
            raise RootOperationError('Eine Bibliotheksmutation darf ihre Reservation nicht auf globale oder fremde Stammordner erweitern.')
        if precondition is not None and not precondition():
            raise RootOperationError('Verschachtelte Bibliotheksbindung ist nicht mehr aktuell.')
        yield
        return
    databases = tuple(databases)
    _require_coordinated_topology(root,databases)
    with _lock(parent/'workspace.lock',exclusive=library is None,wait_seconds=wait_seconds), _lock(parent/'shared.lock',exclusive=True,wait_seconds=wait_seconds):
        @contextmanager
        def library_lock():
            if library is None:
                yield
            else:
                with _lock(parent/('library-'+hashlib.sha256(library.encode()).hexdigest()+'.lock'),exclusive=True):yield
        with library_lock():
            _require_coordinated_topology(root,databases)
            _assert_startable(parent)
            state=_state(parent,root)
            current=(state['generation'],state['libraries'].get(library or 'shared',0))
            if expected_generation is not None and tuple(expected_generation)!=current:
                raise RootOperationError('Stammordnergeneration hat sich geändert. Bitte die aktuellen Einstellungen erneut laden.')
            if precondition is not None and not precondition():
                raise RootOperationError('Bibliothekspfade haben sich vor der Reservationsentscheidung geändert.')
            assert_no_pending(root,databases,library_id=library,staging_precondition=staging_precondition)
            for p in sorted(parent.glob('operation-*.json')):
                record=_read(p)
                if library is not None and record.get('library')!=library and not record.get('shared', True):continue
                _check(record['bindings'])
                if not _completed(record):
                    raise RootOperationError('Stammordnerwechsel wegen eines unterbrochenen oder ungeklärten Vorgangs gesperrt: '+record['kind'])
                expected=hashlib.sha256(json.dumps([record['library'],record['kind'],str(record['database']),record['ids']],sort_keys=True).encode()).hexdigest()
                if record.get('format')!=1 or record.get('workspace')!=str(root) or p.name!='operation-'+expected+'.json':
                    raise RootOperationError('Unbekannter Reservationsnachweis bleibt erhalten: '+p.name)
                with _lock(p.with_suffix('.lock'),exclusive=True):
                    receipt=parent/('completed-'+expected+'-'+hashlib.sha256(json.dumps(record['generation']).encode()).hexdigest()+'.json')
                    _write(receipt,{'reservation':record,'receipt':'domain_completed'})
                    p.unlink();_sync(parent)
            before=_state(parent,root)
            # A registry-only relink may intentionally repair an old symlink.
            # It never dereferences or mutates that old directory entry.
            bindings={}
            for p in (changed_paths or {}):
                try:s=Path(p).lstat();bindings[str(p)]=[s.st_dev,s.st_ino,s.st_mode]
                except FileNotFoundError:bindings[str(p)]=None
            _write(parent/'mutation.json',{'format':1,'library':library,'generation':before,'changed_paths':{str(k):str(v) for k,v in (changed_paths or {}).items()},'bindings':bindings,'details':details or {}})
            token=_MUTATION.set({'workspace': str(root), 'library': library})
            try:
                yield
                with _lock(parent/'state.lock',exclusive=True,wait=True):
                    state=_state(parent,root)
                    if library is None:state['generation']+=1
                    else:state['libraries'][library]=state['libraries'].get(library,0)+1
                    for old,new in (changed_paths or {}).items():
                        for p in list(state['bindings']):
                            try:relative=Path(p).relative_to(old)
                            except ValueError:continue
                            replacement=Path(new)/relative
                            state['bindings'].pop(p)
                            identity=_identity(replacement)
                            if identity is not None:state['bindings'][str(replacement)]=identity
                    _write(parent/'state.json',state)
                (parent/'mutation.json').unlink();_sync(parent)
            except Exception:
                if rollback_check is not None and rollback_check():
                    (parent/'mutation.json').unlink();_sync(parent)
                raise
            finally:
                # Failure is deliberately not reclassified as a completed root
                # change. Startup and workers retain and reject this intent.
                _MUTATION.reset(token)


def assert_no_pending(workspace, databases, *, library_id=None, allowed_missing_roots=(), staging_precondition=None):
    from app.storage_config import load_storage_settings
    names=load_storage_settings(workspace_root=Path(workspace))
    paths={'metadata_root':Path(workspace)/names['metadata_directory_name'],'backup_root':Path(workspace)/names['backup_directory_name']}
    state=_state(_control_location(workspace),Path(workspace))
    for path in paths.values():
        current=_identity(path)
        known=state['bindings'].get(str(path))
        if known is not None and known!=current and str(path) not in allowed_missing_roots:
            raise RootOperationError('Recoverywurzel ist nicht mehr eindeutig gebunden; Nachweise bleiben erhalten: '+str(path))
    for base in [paths['metadata_root']]:
        for name in ['.trash-deletions','.trash-restores','.swap-journals']:
            for journal in (base/name).glob('*.json'):
                record=_read(journal)
                referenced=set()
                if record and record.get('database'):referenced.add(str(record['database']))
                multi=record.get('databases') if isinstance(record,dict) else None
                if isinstance(multi,dict):referenced.update(multi)
                if isinstance(multi,list):referenced.update(str(x.get('path')) for x in multi if isinstance(x,dict) and x.get('path'))
                owners=[_registered(Path(path)) for path in referenced]
                if library_id is not None and referenced and all(owner is not None and str(owner['library_id'])!=str(library_id) for owner in owners):continue
                raise RootOperationError('Stammordnerwechsel wegen eines ungeklärten Recoveryjournals nicht möglich: '+name)
    if any((paths['backup_root']/'.deleting-journals').glob('*.json')):
        raise RootOperationError('Ungeklärtes Sicherungs-Löschjournal verhindert den Stammordnerwechsel.')
    if any(p.is_file() or p.is_symlink() for p in (paths['backup_root']/'.incoming').rglob('*')) and (staging_precondition is None or not staging_precondition()):
        raise RootOperationError('Ungeklärtes Import-Staging verhindert den Stammordnerwechsel.')
    checks=[('jobs','state',{'queued','copying','verifying','analyzing','organizing','moving','running','interrupted'}),('sort_runs','status',{'queued','planned','verifying','moving','finalizing','rolling_back','interrupted','rollback_failed'}),('event_ssd_releases','status',None),('ssd_release_tasks','status',{'queued','running'}),('background_mutation_cancellations','status',{'queued','running','failed'}),('operation_batches','status',{'queued','running','interrupted'})]
    checks.extend([('metadata_corrections','status',{'queued','writing','interrupted','blocked'}),('event_mutations','status',{'pending_reassignment','pending_apply','manual_archive'}),('archive_recovery_incidents','status',{'manual_review'})])
    for database in databases:
        database=Path(database)
        if not database.is_file():raise RootOperationError('Bibliotheksdatenbank ist nicht verfügbar; Stammordnerwechsel bleibt gesperrt: '+str(database))
        with closing(sqlite3.connect(database.as_uri()+'?mode=ro',uri=True)) as c:
            tables={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            for table,column,active in checks:
                if table not in tables:continue
                values=[r[0] for r in c.execute('SELECT '+column+' FROM '+table)]
                if any(v!='completed' if active is None else v in active for v in values):
                    raise RootOperationError('Stammordnerwechsel wegen eines laufenden oder ungeklärten Vorgangs nicht möglich: '+table)
            if 'event_change_requests' in tables and c.execute("SELECT 1 FROM event_change_requests WHERE status NOT IN ('aenderbar_archiviert','aenderbar_abgebrochen') LIMIT 1").fetchone():
                raise RootOperationError('Ein offener Archivänderungsauftrag verhindert den Stammordnerwechsel.')


@contextmanager
def _registry_write_gate(row, arguments=None):
    """Even unchanged paths must not be republished from an old SQL snapshot."""
    from types import SimpleNamespace
    if row is not None:
        from app.library_context import _context_from_row
        context = _context_from_row(row)
    else:
        a = arguments
        context = SimpleNamespace(library_id=str(a['library_id']), database_path=Path(a['database_path']).absolute(),
                                  workspace_root=Path(a['workspace_root']).absolute(),work_root=Path(a['work_root']).absolute(),
                                  archive_root=Path(a['archive_root']).absolute(),root_generation=generation(a['workspace_root'],a['library_id']))
    owner = _MUTATION.get()
    if owner is not None and owner['workspace'] == str(context.workspace_root) and owner['library'] in {None,context.library_id}:
        yield
    else:
        with admission(context):
            if row is None:
                # First explicit registration must bind its administrative
                # roots BEFORE publishing the first registry row. Otherwise a
                # subsequent observer cannot distinguish initial control setup
                # from loss of an existing installation's authority.
                root,parent=_control(context.workspace_root)
                with _lock(parent/'state.lock',exclusive=True,wait=True):
                    if _read(parent/'state.json',None) is None:
                        registry=Path(arguments['registry_path'])
                        if registry.is_file():
                            with closing(sqlite3.connect(registry.absolute().as_uri()+'?mode=ro',uri=True)) as c:
                                exists=c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='libraries'").fetchone()
                                if exists and c.execute('SELECT 1 FROM libraries WHERE workspace_root=? LIMIT 1',(str(root),)).fetchone():
                                    raise RootOperationError('Registered installation lost its control state: '+str(parent))
                        state=_state(parent,root)
                        from app.storage_config import load_storage_settings
                        roots=[root,context.work_root,context.archive_root,
                               *(root/name for name in load_storage_settings(workspace_root=root).values())]
                        state['bindings']={str(Path(path).absolute()):identity for path in roots
                                           if (identity:=_identity(path)) is not None}
                        _write(parent/'state.json',state)
            yield


def guard_database_relink(fn):
    """DB rebinding uses the workspace lock, including central projections."""
    signature = inspect.signature(fn)
    @wraps(fn)
    def call(*args, **kwargs):
        a = signature.bind(*args, **kwargs); a.apply_defaults(); a = a.arguments
        from app.library_registry import get_library, read_library_identity, LibraryRegistryError
        old = get_library(a['registry_path'], a['library_id'], active_only=False)
        new = Path(a['database_path']).expanduser().resolve(strict=False)
        if old is None:return fn(*args, **kwargs)
        if str(new) == old['database_path']:
            with _registry_write_gate(old):return fn(*args, **kwargs)
        if not new.is_file() or read_library_identity(new) != a['library_id']:
            raise LibraryRegistryError('Ersatz-Datenbank besitzt keine nachgewiesene Bibliotheksidentität.')
        fields = ['workspace_root', 'work_root', 'archive_root', 'database_path']
        def unchanged():
            current = get_library(a['registry_path'], a['library_id'], active_only=False)
            return current is not None and all(current[k] == old[k] for k in fields)
        try:
            expected = generation(old['workspace_root'], 'shared')
            with closing(sqlite3.connect(Path(a['registry_path']).absolute().as_uri()+'?mode=ro', uri=True)) as c:
                databases = [new if row[0] == old['database_path'] else Path(row[0])
                             for row in c.execute('SELECT database_path FROM libraries')]
            with mutate(old['workspace_root'], databases=databases, expected_generation=expected,
                        precondition=unchanged, rollback_check=unchanged,
                        details={'registry_before': {k: old[k] for k in fields},
                                 'registry_after': {**{k: old[k] for k in fields}, 'database_path': str(new)}}):
                return fn(*args, **kwargs)
        except RootOperationError as error:
            raise LibraryRegistryError(str(error)) from error
    return call


def guard_registry_paths(fn):
    signature=inspect.signature(fn)
    @wraps(fn)
    def call(*args,**kwargs):
        a=signature.bind(*args,**kwargs);a.apply_defaults();a=a.arguments
        from app.library_registry import get_library, LibraryRegistryError
        snapshot = a.get('_expected_roots')
        def check_snapshot(current):
            if snapshot is not None and (current is None or any(str(current.get(k)) != str(v) for k,v in snapshot.items())):
                raise LibraryRegistryError('Bibliotheksbindung hat sich seit dem Lesen geändert. Die veraltete Änderung wurde nicht übernommen; bitte neu laden.')
        if not Path(a['registry_path']).is_file():
            check_snapshot(None)
            with _registry_write_gate(None,a):return fn(*args,**kwargs)
        try:old=get_library(a['registry_path'],a['library_id'],active_only=False)
        except sqlite3.OperationalError as error:
            if 'no such table' not in str(error):raise
            return fn(*args,**kwargs)
        check_snapshot(old)
        fields=['workspace_root','work_root','archive_root','database_path']
        changed=old and any(str(Path(a[k]).expanduser().resolve(strict=False))!=str(old[k]) for k in fields)
        if not changed:
            try:
                with _registry_write_gate(old,a):
                    check_snapshot(get_library(a['registry_path'],a['library_id'],active_only=False))
                    return fn(*args,**kwargs)
            except RootOperationError as error:
                raise LibraryRegistryError(str(error)) from error
        if str(Path(a['workspace_root']).resolve(strict=False))!=str(old['workspace_root']):
            raise LibraryRegistryError('Der Workspace-Mount kann nicht während einer Bibliothekspfadänderung gewechselt werden.')
        def rolled_back():
            current=get_library(a['registry_path'],a['library_id'],active_only=False)
            return current is not None and all(current[k]==old[k] for k in fields)
        try:
            db_changed = str(Path(a['database_path']).expanduser().resolve(strict=False)) != str(old['database_path'])
            scope = None if db_changed else a['library_id']
            expected=generation(Path(old['workspace_root']),scope or 'shared')
            db_only=all(str(Path(a[k]).expanduser().resolve(strict=False))==str(old[k]) for k in ['workspace_root','work_root','archive_root'])
            check_database=Path(a['database_path']) if db_only and not Path(old['database_path']).is_file() else Path(old['database_path'])
            databases = [check_database]
            if db_changed:
                # Central projections can reference any registered or retired DB.
                with closing(sqlite3.connect(Path(a['registry_path']).absolute().as_uri()+'?mode=ro', uri=True)) as c:
                    databases = [check_database if row[0] == str(old['database_path']) else Path(row[0])
                                 for row in c.execute('SELECT database_path FROM libraries')]
            with mutate(Path(old['workspace_root']),library_id=scope,databases=databases,changed_paths={Path(old[k]):Path(a[k]).expanduser().resolve(strict=False) for k in ['work_root','archive_root'] if str(old[k])!=str(a[k])},rollback_check=rolled_back,expected_generation=expected,precondition=rolled_back,details={'registry_before':{k:str(old[k]) for k in fields},'registry_after':{k:str(a[k]) for k in fields}}):
                check_snapshot(get_library(a['registry_path'],a['library_id'],active_only=False))
                return fn(*args,**kwargs)
        except RootOperationError as error:
            raise LibraryRegistryError(str(error)) from error
    return call


def reset_empty_storage(workspace, database, token):
    """Explicit empty setup transition; archive old F14 state before commit.

    This never deletes folders, journals, retention, registry or catalogue rows.
    SIGKILL before the state publication leaves the original state intact; after
    publication the ordinary empty-initialization startup can safely resume.
    """
    from app.managed_storage_health import setup_again_evidence
    root,parent=_control(workspace)
    with _lock(parent/'workspace.lock',exclusive=True), _lock(parent/'shared.lock',exclusive=True), _lock(parent/'state.lock',exclusive=True,wait=True):
        proof=setup_again_evidence(root,database=database)
        if not proof['allowed'] or proof['token']!=token:
            raise RootOperationError('Neue Einrichtung ist nicht sicher freigegeben: '+proof.get('reason','Zustand wurde verändert. Bitte erneut prüfen.'))
        old=_read(parent/'state.json',{})
        if old:_state(parent,root)
        archive=parent/('setup-history-'+hashlib.sha256(json.dumps(old,sort_keys=True).encode()).hexdigest()+'.json')
        if archive.exists():
            if _read(archive)!=old:raise RootOperationError('Vorhandener Einrichtungsbeleg widerspricht dem Altzustand.')
        else:_write(archive,old)
        # Keep the complete old state as immutable history. Advancing generation
        # invalidates stale request contexts; no old library is rebound.
        new={'format':2,'workspace':proof['observed'][str(root)],'generation':old.get('generation',0)+1,'libraries':{},'bindings':{str(root):proof['observed'][str(root)]},
             'setup_reset':{'history':archive.name,'confirmation':'SET UP AGAIN','bootstrap_registry':proof.get('bootstrap_registry',[]),'qualification':proof.get('basis','initialization_intent'),'database':str(Path(database).absolute()),'previous_state_sha256':hashlib.sha256(json.dumps(old,sort_keys=True).encode()).hexdigest()}}
        if old.get('control_migration'):
            new['control_migration']=old['control_migration']
        current=setup_again_evidence(root,database=database)
        if not current['allowed'] or current['token']!=token:raise RootOperationError('Leerheitsnachweis wurde während der Einrichtung verändert.')
        _check({p:i for p,i in proof['observed'].items() if i is not None})
        _write(parent/'state.json',new)
