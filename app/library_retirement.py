"""Explicit, atomic deregistration. External archives and local DBs are retained."""
from pathlib import Path
import json
import uuid
from datetime import datetime, timezone


def remove(registry, library_id, confirmation):
    from app.library_registry import get_library, LibraryRegistryError, read_library_identity, _connect
    from app.database import database_connection
    from app.root_operations import mutate, _identity, generation
    from app.import_publication import _parent, _verified
    from app.main import _mount_read_only
    row=get_library(registry,library_id,active_only=False)
    if row is None:raise LibraryRegistryError('library_remove_not_found')
    if row['is_main']:raise LibraryRegistryError('library_remove_main_forbidden')
    if confirmation!='REMOVE LIBRARY':raise LibraryRegistryError('library_remove_confirmation_required')
    if not row.get('is_registered',True):
        if (row.get('settings') or {}).get('retirement_receipt'):return row
        raise LibraryRegistryError('library_remove_legacy_retirement_requires_review')
    workspace=Path(row['workspace_root']);work=Path(row['work_root']);archive=Path(row['archive_root']);db=Path(row['database_path'])
    if read_library_identity(db)!=library_id:raise LibraryRegistryError('library_remove_database_identity: '+str(db))
    nonce=uuid.uuid4().hex
    def same():
        now=get_library(registry,library_id,active_only=False)
        return now is not None and all(now[k]==row[k] for k in ('work_root','archive_root','database_path','is_registered'))
    expected=generation(workspace,library_id)
    from app.import_recovery import retained_staging_is_qualified
    from app.main import DATABASE_FILE, LOG_PATH
    with mutate(workspace,library_id=library_id,databases=[db],expected_generation=expected,
                staging_precondition=lambda:retained_staging_is_qualified(DATABASE_FILE,registry,workspace,LOG_PATH),
                precondition=same,rollback_check=same,
                details={'operation':'remove_library','library_id':library_id,'retirement_id':nonce,'registry':str(Path(registry).absolute()),
                         'registry_before':{k:row[k] for k in ('work_root','archive_root','database_path','settings','is_registered')}}):
        # Legacy fixtures/layouts can have a validated in-memory generation
        # before the first durable state file. Persist it BEFORE registry commit.
        from app.root_operations import _control_location,_state,_write,_lock
        control=_control_location(workspace)
        with _lock(control/'state.lock',exclusive=True,wait=True):
            if not (control/'state.json').exists():_write(control/'state.json',_state(control,workspace))
        # No recursive deletion, even for an empty managed shell. Existing
        # names/bindings remain reserved; a new library chooses a distinct name.
        with _parent(work/'probe'):
            if any(work.iterdir()):raise LibraryRegistryError('library_remove_workspace_not_empty: '+str(work))
        if not _mount_read_only(archive):raise LibraryRegistryError('library_remove_archive_not_readonly: '+str(archive))
        with database_connection(db) as c:
            if c.execute("SELECT 1 FROM events WHERE status!='archived' LIMIT 1").fetchone():
                raise LibraryRegistryError('library_remove_open_events')
            files=[dict(r) for r in c.execute('SELECT * FROM files')]
        # Central projections are retained global stock. Local holdings must
        # ALL be verified archive copies before their live ownership can retire.
        for f in files:
            if f['current_root_kind']=='shared_workspace':continue
            if f['current_root_kind']!='camera_archive':raise LibraryRegistryError('library_remove_unsecured_inventory')
            from app.import_recovery import relative
            path=archive/relative(f['current_relative_path'])
            with _parent(path) as (fd,name):
                _verified(fd,name,{'size_bytes':f['size_bytes'],'sha256':f['sha256_current'] or f['sha256_original']})
        connection=_connect(Path(registry))
        try:
            connection.execute('BEGIN IMMEDIATE')
            current=dict(connection.execute('SELECT * FROM libraries WHERE library_id=?',(library_id,)).fetchone())
            if any(current[k]!=row[k] for k in ('work_root','archive_root','database_path','is_registered')):
                raise LibraryRegistryError('library_remove_registry_changed')
            claims=[dict(r) for r in connection.execute('SELECT * FROM family_claims WHERE library_id=? ORDER BY canonical_family_id',(library_id,))]
            if any(c['claim_state']=='reserved' for c in claims):raise LibraryRegistryError('library_remove_reserved_claims')
            # A live ownership claim may retire only when its catalogue
            # holdings have all been verified in the retained RO archive.
            if claims and any(f['current_root_kind']!='camera_archive' for f in files):
                raise LibraryRegistryError('library_remove_unsecured_claims')
            if any(work.iterdir()):raise LibraryRegistryError('library_remove_workspace_not_empty: '+str(work))
            settings=json.loads(current['settings_json'] or '{}')
            settings['retirement_receipt']={'format':1,'id':nonce,'library_id':library_id,
                'at':datetime.now(timezone.utc).isoformat(),'claims':claims,
                'work_identity':_identity(work),'archive_identity':_identity(archive),
                'database':str(db),'workspace_retained':str(work),'archive_retained':str(archive)}
            # Snapshot every historical live claim in the SAME transaction.
            # Original source/canonical/member/media rows never change.
            connection.execute('UPDATE libraries SET is_active=0,is_registered=0,settings_json=?,unregistered_at=?,updated_at=? WHERE library_id=?',
                (json.dumps(settings,ensure_ascii=False),settings['retirement_receipt']['at'],settings['retirement_receipt']['at'],library_id))
            connection.execute('DELETE FROM family_claims WHERE library_id=?',(library_id,))
            connection.commit()
        except BaseException:
            connection.rollback();raise
        finally:connection.close()
    return get_library(registry,library_id,active_only=False)


def recover(workspace):
    """Only finish our receipt-bound registry-only mutation after process death."""
    from app.root_operations import _control_location,_read,_write,_identity,_lock,_sync
    from app.library_registry import get_library, LibraryRegistryError
    root=Path(workspace).absolute();parent=_control_location(root);path=parent/'mutation.json'
    if not path.exists():return
    intent=_read(path,{})
    details=intent.get('details',{})
    if details.get('operation')!='remove_library':return
    lid=details.get('library_id');registry=Path(details.get('registry',''))
    with _lock(parent/'workspace.lock',exclusive=True), _lock(parent/'shared.lock',exclusive=True), _lock(parent/'state.lock',exclusive=True,wait=True):
        if _read(path,{})!=intent or intent.get('changed_paths') or intent.get('library')!=lid:
            raise LibraryRegistryError('library_remove_intent_mismatch')
        old=intent['generation'];state=_read(parent/'state.json',{})
        if old.get('workspace')!=_identity(root) or state.get('workspace')!=old['workspace']:
            raise LibraryRegistryError('library_remove_workspace_changed')
        if any(i is not None and _identity(p)!=i for p,i in old['bindings'].items()):
            raise LibraryRegistryError('library_remove_binding_changed')
        row=get_library(registry,lid,active_only=False)
        if row is None:raise LibraryRegistryError('library_remove_registry_missing')
        receipt=(row.get('settings') or {}).get('retirement_receipt',{})
        committed=not row['is_registered'] and receipt.get('id')==details.get('retirement_id') and receipt.get('library_id')==lid
        if not committed and not row['is_registered']:raise LibraryRegistryError('library_remove_receipt_missing')
        if not committed and any(row[k]!=v for k,v in details.get('registry_before',{}).items()):
            raise LibraryRegistryError('library_remove_registry_changed')
        if committed:
            from app.main import _mount_read_only
            if (_identity(row['work_root'])!=receipt['work_identity']
                or _identity(row['archive_root'])!=receipt['archive_identity']
                or any(Path(row['work_root']).iterdir()) or not _mount_read_only(Path(row['archive_root']))):
                raise LibraryRegistryError('library_remove_retained_roots_changed')
        before=old['libraries'].get(lid,0);after=state['libraries'].get(lid,0)
        if (state['generation']!=old['generation'] or after not in {before,before+1}
            or state['bindings']!=old['bindings'] or state.get('storage_names')!=old.get('storage_names')
            or {k:v for k,v in state['libraries'].items() if k!=lid}!={k:v for k,v in old['libraries'].items() if k!=lid}):
            raise LibraryRegistryError('library_remove_generation_mismatch')
        if committed:
            state['libraries'][lid]=before+1
            _write(parent/'state.json',state)
        elif after!=before:raise LibraryRegistryError('library_remove_uncommitted_generation')
        _write(parent/('library-retirement-'+details['retirement_id']+'.json'),
               {'intent':intent,'committed':committed,'receipt':receipt})
        path.unlink();_sync(parent)
