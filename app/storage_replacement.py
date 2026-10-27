"""Explicit, audited replacement of a lost managed directory.

No catalogue, archive, retained media or historical F14 receipt is deleted.
An external mount or a surviving directory with unknown contents cannot be
adopted. Root generations change only after the newly created directory and
all its registered child roots have been durably established.
"""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import os
import sqlite3
import stat

from app.import_publication import _parent
from app.library_registry import list_libraries
from app.managed_storage_health import inspect_storage
from app.root_operations import (
    RootOperationError, _assert_startable, _control, _identity, _lock,
    _read, _state, _sync, _write, assert_no_pending,
)
from app.storage_config import load_storage_settings


CONFIRMATION = 'I ACCEPT MISSING FILES'


def _unoccupied(path: Path) -> bool:
    """Finder metadata is harmless, but no foreign files or links are adopted."""
    if not path.exists() and not path.is_symlink():
        return True
    with _parent(path / '.bk-probe') as (fd, _):
        for name in os.listdir(fd):
            st = os.stat(name, dir_fd=fd, follow_symlinks=False)
            if not (name == '.DS_Store' and stat.S_ISREG(st.st_mode)
                    and st.st_nlink == 1 and st.st_size <= 1024 * 1024):
                return False
    return True


def _mkdir_exact(path: Path) -> None:
    """Never follow a substituted ancestor and never overwrite an entry."""
    with _parent(path) as (fd, name):
        try:
            os.mkdir(name, 0o775, dir_fd=fd)
            os.fsync(fd)
        except FileExistsError:
            if not _unoccupied(path):
                raise RootOperationError('replacement_destination_not_empty')
        child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
        try:
            if os.fstatvfs(child).f_flag & os.ST_RDONLY:
                raise RootOperationError('replacement_destination_read_only')
        finally:
            os.close(child)


def replacement_candidates(status):
    """Only previously pinned, inaccessible managed roots may be replaced."""
    if status.get('ready') or status.get('can_initialize') or status.get('can_setup_again'):
        return []
    severe={'workspace_unavailable','workspace_identity_changed','configuration_changed',
            'registry_unavailable','catalog_unavailable','evidence_unreadable',
            'initialization_pending','unresolved_reservation','mount_identity_changed',
            'installation_history_missing','appdata_identity_changed','workspace_claim_conflict'}
    if any(issue['code'] in severe for issue in status.get('issues', ())):
        return []
    return [
        row for row in status.get('folders', ())
        if row.get('status') in {'missing','identity_changed'}
        and row.get('expected_identity') is not None
        and (row.get('key') in load_storage_settings(workspace_root=Path(status['workspace']))
             or (str(row.get('key')).startswith('library_work_root:')
                 and Path(row['path']).is_relative_to(
                     Path(status['workspace'])/load_storage_settings(workspace_root=Path(status['workspace']))['workspaces_directory_name'])))
    ]


def replace_managed_directory(workspace, database, registry, key, confirmation):
    if confirmation != CONFIRMATION:
        raise RootOperationError('replacement_confirmation_required')
    root, parent=_control(workspace)
    names=load_storage_settings(workspace_root=root)
    if key not in names and not key.startswith('library_work_root:'):
        raise RootOperationError('replacement_role_unknown')
    # The exact target of a library child root must come from a registered,
    # previously pinned row; the caller cannot supply an arbitrary path.
    target=root/names[key] if key in names else None
    with _lock(parent/'workspace.lock',exclusive=True), _lock(parent/'shared.lock',exclusive=True), _lock(parent/'state.lock',exclusive=True,wait=True):
        state=_state(parent,root)
        _assert_startable(parent)
        if any(parent.glob('operation-*.json')) or list(parent.glob('mutation*.json')):
            raise RootOperationError('replacement_pending_operations')
        status=inspect_storage(root,database=database)
        matching=[r for r in replacement_candidates(status) if r.get('key')==key]
        if len(matching)!=1:
            raise RootOperationError('replacement_not_qualified')
        if target is None:
            target=Path(matching[0]['path'])
        # Multiple lost roots are repaired one by one. Other previously pinned,
        # missing roots remain blocked until separately restored or confirmed.
        missing_rows=[row for row in status['folders'] if row['status']!='available']
        if any(row['status'] not in {'missing','identity_changed'}
               or row.get('expected_identity') is None for row in missing_rows):
            raise RootOperationError('replacement_other_evidence_unavailable')
        allowed_paths={row['path'] for row in missing_rows}
        if any(issue['code'] not in {'missing','identity_changed'}
               or issue['path'] not in allowed_paths for issue in status['issues']):
            raise RootOperationError('replacement_other_evidence_unavailable')
        # A mount disappearance must never turn into mkdir on its parent FS.
        from app.appdata import mount
        for path, expected_mount in state.get('mounts',{}).items():
            if mount(path) != expected_mount:
                raise RootOperationError('replacement_mount_unavailable: '+path)
        previous=matching[0]['expected_identity']
        # Legacy states lack explicit mount provenance. A recorded device
        # boundary must still not collapse into the parent filesystem.
        actual_target = _identity(target)
        parent_identity = _identity(target.parent)
        if previous and parent_identity and previous[0] != parent_identity[0] and (actual_target is None or actual_target[0] != previous[0]):
            raise RootOperationError('replacement_dataset_mount_unproven: '+str(target))
        if previous != state.get('bindings',{}).get(str(target)):
            raise RootOperationError('replacement_binding_changed')
        if not _unoccupied(target):
            raise RootOperationError('replacement_destination_not_empty')
        libraries=list_libraries(Path(registry),active_only=False,registered_only=False)
        if not any(row.get('is_registered',True) and str(row.get('workspace_root'))==str(root) for row in libraries):
            raise RootOperationError('replacement_no_registered_library')
        databases=sorted({str(Path(database).absolute()),*(str(Path(row['database_path']).absolute()) for row in libraries)})
        for db in databases:
            path=Path(db)
            if not path.is_file() or path.is_symlink():
                raise RootOperationError('replacement_catalogue_unavailable')
            with closing(sqlite3.connect(path.absolute().as_uri()+'?mode=ro',uri=True)) as c:
                if c.execute('PRAGMA quick_check').fetchone()[0]!='ok':
                    raise RootOperationError('replacement_catalogue_unavailable')
        assert_no_pending(root,[Path(db) for db in databases],
                          allowed_missing_roots=tuple(allowed_paths))
        # No implicit recovery of arbitrary historical child roots.
        children=[]
        if key=='workspaces_directory_name':
            for row in libraries:
                if not row.get('is_registered',True):
                    continue
                work=Path(row['work_root']).absolute()
                if work.is_relative_to(target) and work!=target:
                    children.append(work)
            children.sort(key=lambda p:(len(p.parts),str(p)))
        for bound, inode in state.get('bindings',{}).items():
            if inode is not None and Path(bound)!=target and Path(bound).is_relative_to(target):
                if Path(bound) not in children:
                    raise RootOperationError('replacement_unknown_pinned_child')
        if any(not _unoccupied(child) for child in children):
            raise RootOperationError('replacement_child_not_empty')
        # Journal is written before the first mkdir and remains permanently.
        # A process killed after mkdir can safely repeat this same confirmation;
        # unrelated directory contents will still refuse replacement.
        intent_id=hashlib.sha256(json.dumps([str(root),key,previous],sort_keys=True).encode()).hexdigest()
        receipt=parent/('replacement-history-'+intent_id+'.json')
        data={'format':1,'workspace':str(root),'key':key,'path':str(target),
              'old_identity':previous,'prior_generation':state['generation'],
              'registered_libraries':[str(row['library_id']) for row in libraries
                                      if row.get('is_registered',True)],
              'confirmation':CONFIRMATION,'loss_assumed':True}
        old=_read(receipt,None)
        if old is not None and old!=data:
            # A previous completed replacement must not be silently repeated.
            raise RootOperationError('replacement_previous_history_conflict')
        if old is None:
            _write(receipt,data)
        if target.is_symlink():
            raise RootOperationError('replacement_symlink')
        _mkdir_exact(target)
        for child in children:
            chain=[]
            cursor=child
            while cursor!=target:
                chain.append(cursor);cursor=cursor.parent
            for directory in reversed(chain):
                _mkdir_exact(directory)
        for path in [target,*children]:
            actual=_identity(path)
            if actual is None or not _unoccupied(path):
                raise RootOperationError('replacement_changed_during_commit')
            state['bindings'][str(path)]=actual
        state['generation']=int(state['generation'])+1
        for library_id in data['registered_libraries']:
            state['libraries'][library_id]=int(state['libraries'].get(library_id,0))+1
        replacement=dict(data,created_at=datetime.now(timezone.utc).isoformat(),
                         new_identity=_identity(target),new_generation=state['generation'],
                         child_paths=[str(p) for p in children])
        state.setdefault('storage_replacements',[]).append(replacement)
        _write(parent/'state.json',state)
        return {'replaced':True,'key':key,'path':str(target),
                'new_generation':state['generation'],'loss_recorded':True}
