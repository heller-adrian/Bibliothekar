"""Read-only storage preflight. Missing established roots are never initialized.

This is continuity evidence from the existing F14 state, not a mount/ACL or
content-authenticity certificate. Unknown causes remain explicitly unknown.
"""
from pathlib import Path
from contextlib import closing
import os,sqlite3,stat
from app.storage_config import load_storage_settings,ENGLISH_STORAGE_DEFAULTS,LEGACY_STORAGE_DEFAULTS



def _empty_sqlite_header(connection):
    """A read/open may leave one empty page; custom or retired schemas fail."""
    return (not connection.execute('SELECT 1 FROM sqlite_master LIMIT 1').fetchone()
            and all(connection.execute('PRAGMA '+key).fetchone()[0]==value
                    for key,value in [('page_count',1),('freelist_count',0),('application_id',0),('user_version',0)]))


def catalog_has_history(database):
    """Technical schema/default rows alone are not a used media catalogue."""
    if database is None or not Path(database).exists():return False
    path=Path(database)
    if path.is_symlink() or not path.is_file():raise ValueError('invalid catalogue')
    from app.private_storage_security import qualify_existing
    qualify_existing(path)
    if path.stat().st_size==0:return False
    with closing(sqlite3.connect(path.absolute().as_uri()+'?mode=ro',uri=True)) as c:
        tables=[row[0] for row in c.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        if not tables and _empty_sqlite_header(c):return False
        if not {'schema_versions','jobs','files'}<=set(tables):raise ValueError('unrecognised catalogue')
        for table in tables:
            quoted='"'+table.replace('"','""')+'"'
            if table=='schema_versions':continue
            if table=='sqlite_sequence':
                if c.execute('SELECT 1 FROM sqlite_sequence WHERE seq>0 LIMIT 1').fetchone():return True
                continue
            if table=='app_settings':
                # Both shipped default layouts are technical first-run settings.
                import json
                rows=c.execute('SELECT setting_key,value_json FROM app_settings').fetchall()
                for key,value in rows:
                    if key!='event_folder_layout_default':return True
                    setting=json.loads(value);nodes=setting.get('layout',{}).get('nodes',[])
                    if len(nodes)!=3 or {n.get('name') for n in nodes} not in ({'Alle','Sortiert','Export'},{'All','Sorted','Export'}):return True
                continue
            if table=='library_identity':continue
            if c.execute('SELECT 1 FROM '+quoted+' LIMIT 1').fetchone():return True
    return False


def empty_bootstrap_registry(registry, root, database):
    """Snapshot a strictly unused placeholder; never discard retired libraries.

    Its flags alone prove nothing: all other registry tables must be empty,
    paths and bootstrap markers must match, and no retirement evidence may exist.
    The caller also checks catalogue, workspace, archive and private retention.
    """
    import json
    registry=Path(registry)
    if not registry.exists() and not registry.is_symlink():return []
    if registry.is_symlink() or not registry.is_file():raise ValueError('registry_invalid')
    from app.private_storage_security import qualify_existing
    qualify_existing(registry)
    if registry.stat().st_size==0:return []
    with closing(sqlite3.connect(registry.absolute().as_uri()+'?mode=ro',uri=True)) as c:
        c.row_factory=sqlite3.Row
        tables={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not tables and _empty_sqlite_header(c):return []
        if not {'libraries','registry_schema_versions'}<=tables:raise ValueError('unknown_registry_schema')
        for table in tables-{'registry_schema_versions','libraries'}:
            quoted='"'+table.replace('"','""')+'"'
            if c.execute('SELECT 1 FROM '+quoted+' LIMIT 1').fetchone():raise ValueError('library_or_stock_registry_history')
        rows=[dict(r) for r in c.execute('SELECT * FROM libraries')]
    if not rows:return []
    row=rows[0];archive=os.environ.get('KAMERA_ARCHIVE_ROOT')
    if (len(rows)!=1 or row['library_id']!='main' or row['is_main']!=1 or row['is_registered']!=0
            or row.get('deactivated_at') or row.get('unregistered_at')
            or row['database_path']!=str(Path(database).absolute()) or row['workspace_root']!=str(root)
            or row['work_root']!=str(root/'.bibliothekar-ohne-bibliothek') or not archive or row['archive_root']!=archive
            or json.loads(row['settings_json'])!={'bootstrap':True,'onboarding_required':True}):
        raise ValueError('library_or_stock_registry_history')
    return rows


def _initial_tree(root, names):
    from app.root_operations import _control_location, _read
    from app.storage_bootstrap import tree
    parent = _control_location(root)
    state = _read(parent/'state.json', {})
    migration = state.get('control_migration') or {}
    legacy = None
    if migration.get('receipt'):
        from app.storage_bootstrap import migration_receipt
        receipt = migration_receipt(parent, migration['receipt'], root)
        legacy = receipt.get('legacy_lock')
    return tree(root, names, legacy=legacy)


def _empty_initial_tree(root, names):
    return _initial_tree(root, names)['empty']


def _inspect_storage(workspace, *, database=None):
    from app.root_operations import _control_location,_read
    root=Path(os.path.abspath(workspace));issues=[];folders=[]
    try:
        from app.private_storage_security import qualify_existing
        from app.storage_config import _config_path
        qualify_existing(_config_path().parent)
        if database is not None: qualify_existing(Path(database).absolute().parent)
        configured_registry = os.environ.get('KAMERA_REGISTRY_DATABASE')
        if configured_registry: qualify_existing(Path(configured_registry).absolute().parent)
        state=_read(_control_location(root)/'state.json',{})
        names=load_storage_settings(workspace_root=root)
        pinned=state.get('storage_names') or {}
        if pinned and names!=pinned:
            issues.append({'code':'configuration_changed','path':str(root)})
        expected=pinned or names
        tree_observation = _initial_tree(root, names)
        structural_empty = tree_observation['empty']
        def identity(path):
            current=Path(path.anchor)
            for part in path.parts[1:]:
                current/=part
                info=current.lstat()
                if stat.S_ISLNK(info.st_mode):raise ValueError('symlink')
                if not stat.S_ISDIR(info.st_mode):raise ValueError('not_directory')
            info=path.lstat()
            return [info.st_dev,info.st_ino]
        try:
            root_id=identity(root)
            if state.get('workspace') is not None and state['workspace']!=root_id:
                issues.append({'code':'workspace_identity_changed','path':str(root)})
            if not os.access(root,os.R_OK|os.W_OK|os.X_OK):raise PermissionError(str(root))
            if str(root)=='/workspace' and not os.path.ismount(root):
                # Linux bind mounts on the same device are absent from ismount.
                mounts=Path('/proc/self/mountinfo')
                if not mounts.is_file() or not any(line.split()[4]=='/workspace' for line in mounts.read_text().splitlines()):
                    raise ValueError('configured_workspace_mount_missing')
            if os.statvfs(root).f_flag&os.ST_RDONLY:raise PermissionError('workspace_read_only')
        except (OSError,ValueError) as error:
            issues.append({'code':'workspace_unavailable','path':str(root),'detail':str(error)})
        bindings=state.get('bindings',{})
        known=False
        for key,name in expected.items():
            path=root/name;expected_id=bindings.get(str(path));code='available'
            # Prior F14 versions did not pin role names. Retain evidence that a
            # known German root disappeared rather than selecting an empty EN path.
            old_candidates=[root/n for n in {name,ENGLISH_STORAGE_DEFAULTS[key],LEGACY_STORAGE_DEFAULTS[key]} if bindings.get(str(root/n)) is not None]
            if not pinned and len(old_candidates)==1 and old_candidates[0]!=path:
                path=old_candidates[0];expected_id=bindings[str(path)]
                code='configuration_changed'
            known=known or expected_id is not None
            try:
                actual=identity(path)
                if expected_id is not None and actual!=expected_id:code='identity_changed'
                if not os.access(path,os.R_OK|os.W_OK|os.X_OK):code='inaccessible'
            except FileNotFoundError:actual=None;code='missing'
            except PermissionError:actual=None;code='inaccessible'
            except (OSError,ValueError):actual=None;code='invalid_directory'
            row={'key':key,'name':path.name,'path':str(path),'status':code,'identity':actual,'expected_identity':expected_id,'identity_evidence':'previously_observed' if expected_id is not None else 'no_previous_identity'}
            folders.append(row)
            if code!='available':issues.append({'code':code,'path':str(path),'key':key})
        # Inspect existing registration only; never create/open a guessed DB RW.
        registered=False;registry_history=False;registry_technical=False
        registry=os.environ.get('KAMERA_REGISTRY_DATABASE')
        if registry and Path(registry).is_file():
            with closing(sqlite3.connect(Path(registry).absolute().as_uri()+'?mode=ro',uri=True)) as c:
                tables={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                if 'libraries' in tables:
                    registered_paths=[r[0] for r in c.execute('SELECT database_path FROM libraries WHERE workspace_root=? AND COALESCE(is_registered,1)=1',(str(root),))]
                    registered=bool(registered_paths)
                    all_rows=c.execute('SELECT library_id,database_path,workspace_root,is_registered FROM libraries').fetchall()
                    registry_history=bool(all_rows)
                    # Registered work roots are protected identities too. A
                    # missing child with an available Library Workspaces parent
                    # must reach recovery rather than cause an opaque 500.
                    workspaces=root/expected['workspaces_directory_name']
                    workspaces_row=next((f for f in folders if f['key']=='workspaces_directory_name'),None)
                    if workspaces_row and workspaces_row['status']=='available':
                        registered_works=c.execute(
                            'SELECT library_id,work_root FROM libraries WHERE workspace_root=? AND COALESCE(is_registered,1)=1',
                            (str(root),)).fetchall()
                        for library_id,work_root in registered_works:
                            path=Path(work_root)
                            if path==workspaces or not path.is_relative_to(workspaces):
                                continue
                            key='library_work_root:'+str(library_id)
                            prior=bindings.get(str(path))
                            try:
                                actual=identity(path)
                                code='identity_changed' if prior is not None and actual!=prior else 'available'
                                if not os.access(path,os.R_OK|os.W_OK|os.X_OK):code='inaccessible'
                            except FileNotFoundError:actual=None;code='missing'
                            except PermissionError:actual=None;code='inaccessible'
                            except (OSError,ValueError):actual=None;code='invalid_directory'
                            folders.append({'key':key,'name':path.name,'path':str(path),
                                            'status':code,'identity':actual,'expected_identity':prior,
                                            'identity_evidence':'previously_observed' if prior else 'no_previous_identity'})
                            if code!='available':issues.append({'code':code,'path':str(path),'key':key})
                    init_database=(state.get('storage_initialization') or {}).get('database')
                    bootstrap_database=database or init_database or (state.get('setup_reset') or {}).get('database')
                    try:registry_technical=bool(empty_bootstrap_registry(registry,root,bootstrap_database)) if bootstrap_database is not None else False
                    except ValueError:registry_technical=False
                    if database is not None and str(Path(database).absolute()) in registered_paths and not Path(database).is_file():
                        issues.append({'code':'catalog_unavailable','path':str(database)})
        configured=False
        from app.storage_config import _config_path
        import json
        if _config_path().is_file():
            raw=json.loads(_config_path().read_text()).get('storage')
            configured=isinstance(raw,dict) and any(key in raw for key in ENGLISH_STORAGE_DEFAULTS)
        if registry and Path(registry).absolute().parent == _control_location(root).parent.parent and not Path(registry).is_file() and known and state.get('storage_names') and (state.get('storage_initialization') or {}).get('phase')!='initializing':
            issues.append({'code':'registry_unavailable','path':str(registry)})
        occupied=any(root.iterdir()) if root.is_dir() else True
        old_database=catalog_has_history(database)
        init=state.get('storage_initialization') or {}
        from app.storage_bootstrap import key_for
        candidate_key = init.get('operation_key')
        if candidate_key is None and init.get('database'):
            candidate_key = key_for({'library':'main','kind':'startup','database':init['database'],'ids':{'initialize_storage':True}})
        pending_operation = bool(candidate_key and (_control_location(root)/('operation-'+candidate_key+'.json')).exists())
        resuming=(init.get('phase') in ('initializing', 'prepared') or (init.get('phase')=='completed' and pending_operation))
        resuming=(resuming and init.get('names')==names
                  and (database is None or init.get('database')==str(Path(database).absolute())))
        evidence=bool(state) or any(_control_location(root).glob('*.json'))
        existing=bool(known or registry_history or old_database or evidence or (occupied and not structural_empty))
        custom_configuration=configured and names!=ENGLISH_STORAGE_DEFAULTS
        # Finder metadata is not evidence that a library has been used. An
        # otherwise empty tree remains fresh even when managed roots are absent.
        reset=state.get('setup_reset') or {}
        approved_reset=False
        if reset and not known and (not registry_history or registry_technical) and not old_database and not custom_configuration:
            import hashlib,json
            history=reset.get('history','')
            if history.startswith('setup-history-') and Path(history).name==history:
                previous=_read(_control_location(root)/history,{})
                approved_reset=(hashlib.sha256(json.dumps(previous,sort_keys=True).encode()).hexdigest()==reset.get('previous_state_sha256')
                                and state.get('workspace')==root_id and structural_empty)
        empty_new=(not (known or registry_history or old_database or evidence or custom_configuration) or approved_reset) and structural_empty
        # Resuming a bootstrap must never silently rebind a previously pinned F14 inode.
        # A changed root needs the explicit, audited setup-reset transition.
        changed_roots=any(f['expected_identity'] is not None and f['status']!='available' for f in folders)
        safe_resume=False
        retained_publications=[]
        if resuming and not changed_roots:
            from app.storage_bootstrap import evidence as bootstrap_evidence
            try:
                bootstrap_database = database or init.get('database')
                if bootstrap_database is None: raise ValueError('bootstrap_database_missing: '+str(root))
                checked_bootstrap=bootstrap_evidence(root, bootstrap_database, state)
                retained_publications=checked_bootstrap.get('retained_publications',[])
                safe_resume = True
            except Exception as error:
                detail = str(error); pieces = detail.split(': ', 2)
                code = pieces[0] if pieces[0].replace('_','').isalnum() else 'bootstrap_evidence_unreadable'
                path = pieces[1] if len(pieces)>1 and pieces[1].startswith('/') else str(root)
                issues.append({'code':code,'path':path,'detail':pieces[2] if len(pieces)>2 else detail})
        if state.get('format') in (2, 3) and init.get('bootstrap_id') and init.get('phase') == 'completed':
            from app.storage_bootstrap import completed
            if not completed(root, state):
                issues.append({'code':'bootstrap_completion_receipt_missing','path':str(_control_location(root))})
        # Already created technical DB/default rows do not establish prior use.
        # A bootstrap intent can only complete its exact empty structural tree.
        if resuming:issues.append({'code':'bootstrap_incomplete','path':str(root),'detail':init.get('phase')})
        if reset and not state.get('storage_initialization') and not approved_reset:
            issues.append({'code':'reset_requires_empty','path':str(root)})
        missing_catalog=database is not None and (not Path(database).is_file() or Path(database).stat().st_size==0)
        if missing_catalog and not safe_resume:
            # A configured archive is an unselected source mount, not a library
            # registration. Its bytes must not obstruct first-library setup.
            if registered or (occupied and not structural_empty):
                issues.append({'code':'catalog_unavailable','path':str(database)})
        if database is not None and not Path(database).is_file() and (known or registered) and not safe_resume:
            issues.append({'code':'catalog_unavailable','path':str(database)})
        if not structural_empty and not resuming and not (known or registered) and (empty_new or any(i['code'] in {'missing','catalog_unavailable'} for i in issues)):
            issues.extend(tree_observation['issues'])
        can_initialize=(empty_new or safe_resume) and all(i['code'] in {'missing','bootstrap_incomplete'} for i in issues)
        # Several independent missing-catalog checks may report the same path.
        issues=list({(i['code'],i['path']):i for i in issues}.values())
        reset=setup_again_evidence(root,database=database) if database is not None and (issues or empty_new) else {'allowed':False}
        # No control file is not proof that private data vanished. Apply the
        # same complete emptiness audit before automatic first initialization.
        if empty_new and database is not None and not reset['allowed']:
            can_initialize=False
            issues.append({'code':'initialization_blocked','path':str(root),'detail':reset.get('reason')})
        blocker = next((i['code'] for i in issues if i['code'] not in {'missing','bootstrap_incomplete'}), None) if resuming else reset.get('reason')
        return {'retained_publications':retained_publications,'can_setup_again':reset['allowed'],'setup_token':reset.get('token'),'setup_blocker':blocker,'setup_evidence':reset.get('basis'),'ready':not issues,'can_initialize':can_initialize,'existing_installation':existing and not safe_resume,'workspace':str(root),'folders':folders,'issues':issues,'mount_evidence':'administrator_responsibility','initialization_evidence':'resumable_empty_structure' if safe_resume else 'new_empty_installation' if empty_new else 'existing_or_unclear'}

    except Exception as error:
        from app.private_storage_security import PrivateStorageError
        from app.storage_config import StorageSettingsError, _config_path
        if isinstance(error, StorageSettingsError):
            return {'ready':False,'can_initialize':False,'can_setup_again':False,'existing_installation':True,'workspace':str(root),'folders':folders,'issues':[{'code':'configuration_invalid','path':str(_config_path()),'detail':str(error)}],'setup_blocker':'configuration_invalid'}
        if isinstance(error, PrivateStorageError):
            return {'ready':False,'can_initialize':False,'can_setup_again':False,'existing_installation':True,'workspace':str(root),'folders':folders,'issues':[error.issue()],'setup_blocker':error.code}
        return {'ready':False,'can_initialize':False,'existing_installation':True,'workspace':str(root),'folders':folders,'issues':[{'code':'evidence_unreadable','path':str(root),'detail':str(error)}]}


def inspect_storage(workspace, *, database=None):
    from app.appdata import root as appdata_root, verify, mount
    from app.storage_status import describe
    from app.root_operations import _read, _control_location
    try:
        if appdata_root(): verify(workspace)
        result = _inspect_storage(workspace,database=database)
        if appdata_root():
            state = _read(_control_location(workspace)/'state.json',{})
            if state and state.get('format') != 3:
                raise ValueError('legacy_layout_requires_explicit_migration: '+str(_control_location(workspace)))
            for path, expected in state.get('mounts',{}).items():
                actual = mount(path)
                if actual != expected:
                    result['issues'].append({'code':'mount_identity_changed','path':path,
                                             'detail':f'expected={expected}; actual={actual}'})
                    result.update(ready=False,can_initialize=False)
            if not result.get('can_initialize') and any(r.get('expected_identity') is not None and r['status'] != 'available' for r in result.get('folders',[])):
                for operation in _control_location(workspace).glob('operation-*.json'):
                    result['issues'].append({'code':'unresolved_reservation','path':str(operation),
                        'detail':'Restore original roots and reconcile this operation before accepting a replacement.'})
            result['can_setup_again'] = False
            result['security_model'] = 'host_managed'
            result['warnings'] = [{'code':'host_acl_is_administrative_trust','path':str(appdata_root()),
                'detail':'Dataset owners and ACL writers are trusted host operators; F14 is continuity evidence, not tamper-proof authentication.'}]
        else: result['security_model'] = 'rc11_private_authority'
        return describe(result)
    except Exception as error:
        text=str(error); pieces=text.split(': ',2)
        code=pieces[0] if pieces[0].replace('_','').isalnum() else 'evidence_unreadable'
        path=pieces[1] if len(pieces)>1 and pieces[1].startswith('/') else str(workspace)
        return describe({'ready':False,'can_initialize':False,'can_setup_again':False,
            'existing_installation':True,'workspace':str(workspace),'folders':[],
            'issues':[{'code':code,'path':path,'detail':text}]})


def require_storage(workspace, *, database=None, allow_new=False):
    from app.root_operations import RootOperationError
    result=inspect_storage(workspace,database=database)
    if not result['ready'] and not (allow_new and result['can_initialize']):
        raise RootOperationError('Verwaltungsordner fehlen oder sind nicht eindeutig verfügbar. Betroffene Vorgänge bleiben zum Schutz der Dateien gesperrt: '+', '.join(i['code']+': '+i['path'] for i in result['issues']))
    return result


def require_pinned_storage(workspace, *, initializing=False):
    from app.root_operations import _control_location,_read
    state=_read(_control_location(workspace)/'state.json',{})
    from app.root_operations import _ACTIVE
    bootstrap=initializing or any(r.get('kind')=='startup' and r.get('ids',{}).get('initialize_storage') for r in _ACTIVE.get())
    if state.get('storage_names'):require_storage(workspace,allow_new=bootstrap)


def setup_again_evidence(workspace, *, database):
    """Narrow reset qualification, not an inference from an absent catalogue.

    The workspace itself must still be the observed directory. No registered
    library, live intent, media, retention or catalogue history may be abandoned.
    The returned digest is only an optimistic request token; execution repeats
    every check while holding the complete F14 workspace exclusion lock.
    """
    import hashlib,json
    from app.root_operations import _control_location,_read,_identity
    from app.storage_config import _config_path
    root=Path(os.path.abspath(workspace));parent=_control_location(root)
    try:
        state=_read(parent/'state.json',{})
        names=load_storage_settings(workspace_root=root)
        from app import trash_retention
        _,users=trash_retention.authority(database,root)
        if Path(database).absolute().parent!=parent.parent.parent:raise ValueError('database_binding_changed')
        boundary=parent if parent.exists() else parent.parent if parent.parent.exists() else Path(database).absolute().parent
        with trash_retention.qualified(boundary,users,directory=True) as (_,check):check()
        if (state and (state.get('format') not in (1,2,3) or state.get('workspace')!=_identity(root))) or names!=ENGLISH_STORAGE_DEFAULTS:
            raise ValueError('workspace_or_legacy_binding')
        if state.get('libraries'):
            raise ValueError('library_or_stock_registry_history')
        # Old F14 reservations could pin every root without an initialization
        # intent. That absence is neither fresh-install evidence nor permission
        # to ignore history. Only the explicit reset may use the complete old
        # root bindings, qualified private namespace and all checks below.
        init=state.get('storage_initialization',{})
        if init is None:init={}
        if not isinstance(init,dict) or state.get('storage_names') not in (None,names):
            raise ValueError('unknown_initialization')
        if init.get('names') not in (None,names) or init.get('phase') not in (None,'initializing','prepared','completed'):
            raise ValueError('unknown_initialization')
        basis='initialization_intent'
        receipt=state.get('setup_reset') or {}
        confirmed=False
        history=receipt.get('history','')
        if history and Path(history).name==history and history.startswith('setup-history-'):
            previous=_read(parent/history,None)
            confirmed=(previous is not None and receipt.get('confirmation')=='SET UP AGAIN' and hashlib.sha256(json.dumps(previous,sort_keys=True).encode()).hexdigest()==receipt.get('previous_state_sha256'))
        # A generation-zero workspace-only record may be created before any
        # roots exist. Partial positive root bindings remain ambiguous/rejected.
        technical=(set(state)<={'format','workspace','generation','libraries','bindings','storage_names'} and state.get('generation')==0 and not state.get('libraries') and state.get('bindings')=={str(root):_identity(root)} and not receipt and not init)
        if not state:basis='empty_without_control_evidence'
        elif confirmed:basis='confirmed_empty_reset'
        elif technical:basis='technical_control_only'
        elif not init.get('database') or init.get('names')!=names or init.get('phase') not in ('initializing','prepared','completed') or state.get('storage_names') is None:
            def recorded(value):
                return isinstance(value,list) and len(value)==2 and all(type(v) is int and v>=0 for v in value) and value[1]>0
            if not all(recorded(state.get('bindings',{}).get(str(root/n))) for n in names.values()):
                raise ValueError('incomplete_historical_roots')
            if any(state.get('bindings',{}).get(str(root/n)) is not None for n in LEGACY_STORAGE_DEFAULTS.values()):
                raise ValueError('ambiguous_historical_roots')
            if Path(database).absolute().parent!=parent.parent.parent:
                raise ValueError('database_binding_changed')
            basis='complete_legacy_root_bindings'
        if not _empty_initial_tree(root,names):raise ValueError('workspace_not_empty')
        for pattern in ['operation-*.json','mutation.json','finished-*.json']:
            if list(parent.glob(pattern)):raise ValueError('unresolved_reservation')
        technical_receipts = {'state.json'}
        migration = state.get('control_migration') or {}
        if migration.get('receipt'):
            from app.storage_bootstrap import migration_receipt
            control_receipt = migration_receipt(parent, migration['receipt'], root)
            if control_receipt.get('kind') not in ('rc11_control_migration','rc11_administrative_adoption'):
                raise ValueError('unknown_control_evidence')
            technical_receipts.add(migration['receipt'])
        if init.get('bootstrap_id'):
            from app.storage_bootstrap import completed
            if init.get('phase') == 'completed' and completed(root, state):
                technical_receipts.update({'bootstrap-completed-'+init['bootstrap_id']+'.json', 'bootstrap-operation-'+init['bootstrap_id']+'.json'})
        if any(p.is_symlink() or (p.suffix=='.json' and p.name not in technical_receipts and not p.name.startswith('setup-history-')) for p in (parent.iterdir() if parent.exists() else [])):
            raise ValueError('unknown_control_evidence')
        # Every private media retention and every surviving catalogue is evidence
        # of a used installation, regardless of its current registration flag.
        database=Path(database).absolute()
        if init.get('database') is not None and init['database']!=str(database):raise ValueError('database_binding_changed')
        configured_registry=Path(os.environ.get('KAMERA_REGISTRY_DATABASE',str(database.parent/'bibliothekar-global.sqlite3'))).absolute()
        candidates=set(database.parent.rglob('*.sqlite3'))|{database}
        def unsafe_private_entry(path):
            if path.is_symlink():return True
            if not path.is_file():return False
            if path.suffix=='.sqlite3' and path.stat().st_nlink!=1:return True
            if path.name.endswith(('-wal','-journal')):return bool(path.stat().st_size)
            if path.name.endswith('-shm') and path.stat().st_size:
                # SQLite's own read-only inspection may create SHM. It is not
                # recovery bytes: allow it only beside a present catalogue that
                # is independently checked below. Never ignore WAL/journals or
                # orphan SHM belonging to a missing/empty database.
                owner=Path(str(path)[:-4])
                return owner not in candidates|{configured_registry} or not owner.is_file() or owner.stat().st_size==0
            return False
        if any(unsafe_private_entry(p) for p in database.parent.rglob('*')):
            raise ValueError('private_symlink_or_sqlite_sidecar')
        for candidate in candidates:
            if candidate.absolute()==configured_registry:continue
            if catalog_has_history(candidate):raise ValueError('catalogue_history')
        registry=Path(os.environ.get('KAMERA_REGISTRY_DATABASE',str(database.parent/'bibliothekar-global.sqlite3')))
        bootstrap=empty_bootstrap_registry(registry,root,database)
        if confirmed and receipt.get('bootstrap_registry',[])!=bootstrap:raise ValueError('library_or_stock_registry_history')
        retention=database.parent/'.bibliothekar-restore-retention'
        if retention.is_symlink() or (retention.exists() and any(retention.iterdir())):raise ValueError('retention_survives')
        config={}
        if _config_path().exists() or _config_path().is_symlink():
            with trash_retention.qualified(_config_path(),users) as (fd,check):
                raw=os.read(fd,1024*1024+1)
                if len(raw)>1024*1024:raise ValueError('configuration_too_large')
                config=json.loads(raw);check()
        if config.get('libraries') or config.get('library'):raise ValueError('configured_library_survives')
        configured_archive=os.environ.get('KAMERA_ARCHIVE_ROOT')
        external={}
        if configured_archive:
            from app.import_publication import _parent
            archive=Path(configured_archive)
            if not archive.is_absolute():raise ValueError('archive_unavailable')
            try:
                with _parent(archive/'probe') as (fd,_):
                    info=os.fstat(fd);external[str(archive)]=[info.st_dev,info.st_ino]
                    # Observe its inode without reading or adopting any photos.
                    if _identity(archive)!=external[str(archive)]:raise ValueError('historical_external_binding')
            except OSError as error:raise ValueError('archive_unavailable') from error
        if (config.get('metadata_correction') or {}).get('general_root'):raise ValueError('external_metadata_configuration_survives')
        # Old bindings outside the empty managed tree can denote an archive or a
        # different mount. They must remain identical and empty, never guessed.
        allowed={str(root),*(str(root/n) for n in names.values())}
        for value,identity in state.get('bindings',{}).items():
            path=Path(value)
            if value in allowed:continue
            if path.is_relative_to(root):
                if path.exists() or path.is_symlink():raise ValueError('historical_workspace_content')
            elif _identity(path)!=identity:raise ValueError('historical_external_binding')
            # Preserved, correctly pinned external roots may already hold files.
            # Catalogues, registry history, and private media retention are
            # checked independently and still block an unsafe reset.
        # Reopen every component without following links, including configured
        # private files' parent namespace; existence/access alone is not proof.
        from app.import_publication import _parent
        observed=dict(external)
        for path in [root,*(root/n for n in names.values())]:
            try:
                with _parent(path/'probe') as (fd,_):
                    st=os.fstat(fd);observed[str(path)]=[st.st_dev,st.st_ino]
                    if os.fstatvfs(fd).f_flag&os.ST_RDONLY or not os.access(path,os.R_OK|os.W_OK|os.X_OK):raise ValueError('not_writable')
            except FileNotFoundError:
                if path==root:raise
                observed[str(path)]=None
        if state and observed[str(root)]!=state['workspace']:raise ValueError('workspace_changed_during_check')
        material={'state':state,'observed':observed,'database':str(database),'registry':str(registry),'config':config,'bootstrap_registry':bootstrap}
        return {'allowed':True,'basis':basis,'bootstrap_registry':bootstrap,'token':hashlib.sha256(json.dumps(material,sort_keys=True).encode()).hexdigest(),'observed':observed}
    except Exception as error:
        return {'allowed':False,'reason':str(error)}
