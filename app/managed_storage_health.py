"""Read-only storage preflight. Missing established roots are never initialized.

This is continuity evidence from the existing F14 state, not a mount/ACL or
content-authenticity certificate. Unknown causes remain explicitly unknown.
"""
from pathlib import Path
from contextlib import closing
import os,sqlite3,stat
from app.storage_config import load_storage_settings,ENGLISH_STORAGE_DEFAULTS,LEGACY_STORAGE_DEFAULTS



def catalog_has_history(database):
    """Technical schema/default rows alone are not a used media catalogue."""
    if database is None or not Path(database).exists():return False
    path=Path(database)
    if path.is_symlink() or not path.is_file():raise ValueError('invalid catalogue')
    if path.stat().st_size==0:return False
    with closing(sqlite3.connect(path.absolute().as_uri()+'?mode=ro',uri=True)) as c:
        tables=[row[0] for row in c.execute("SELECT name FROM sqlite_master WHERE type='table'")]
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


def _empty_initial_tree(root,names):
    allowed={name for name in names.values()}
    allowed.update(names['metadata_directory_name']+'/'+child for child in ['General','Batch Correction','.trash-deletions','.trash-restores'])
    lock=names['metadata_directory_name']+'/.trash-deletions/.lock'
    # Traverse only permitted components through held no-follow descriptors.
    from app.import_publication import _parent
    def walk(fd,prefix=''):
        before=os.fstat(fd)
        for name in os.listdir(fd):
            rel=prefix+name;info=os.stat(name,dir_fd=fd,follow_symlinks=False)
            if stat.S_ISDIR(info.st_mode) and rel in allowed:
                child=os.open(name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd)
                try:
                    if (info.st_dev,info.st_ino)!=(os.fstat(child).st_dev,os.fstat(child).st_ino) or not walk(child,rel+'/'):return False
                    if os.stat(name,dir_fd=fd,follow_symlinks=False).st_ino!=info.st_ino:return False
                finally:os.close(child)
            elif not (rel==lock and stat.S_ISREG(info.st_mode) and info.st_size==0 and info.st_nlink==1 and info.st_uid==os.geteuid() and not info.st_mode&0o022):return False
        after=os.fstat(fd)
        return (before.st_dev,before.st_ino,before.st_mtime_ns,before.st_ctime_ns)==(after.st_dev,after.st_ino,after.st_mtime_ns,after.st_ctime_ns)
    try:
        with _parent(root/'probe') as (fd,_):return walk(fd)
    except OSError:return False



def inspect_storage(workspace, *, database=None):
    from app.root_operations import _control_location,_read
    root=Path(os.path.abspath(workspace));issues=[];folders=[]
    try:
        state=_read(_control_location(root)/'state.json',{})
        names=load_storage_settings(workspace_root=root)
        pinned=state.get('storage_names') or {}
        if pinned and names!=pinned:
            issues.append({'code':'configuration_changed','path':str(root)})
        expected=pinned or names
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
                    registered_paths=[r[0] for r in c.execute('SELECT database_path FROM libraries WHERE workspace_root=?',(str(root),))]
                    registered=bool(registered_paths)
                    all_rows=c.execute('SELECT library_id,database_path,workspace_root,is_registered FROM libraries').fetchall()
                    registry_history=bool(all_rows)
                    init_database=(state.get('storage_initialization') or {}).get('database')
                    registry_technical=bool(all_rows) and all(lid=='main' and not active and ws==str(root) and db==init_database for lid,db,ws,active in all_rows)
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
        resuming=(init.get('phase')=='initializing' and init.get('names')==names
                  and (database is None or init.get('database')==str(Path(database).absolute())))
        evidence=bool(state) or any(_control_location(root).glob('*.json'))
        existing=bool(known or registry_history or old_database or occupied or evidence)
        custom_configuration=configured and names!=ENGLISH_STORAGE_DEFAULTS
        structural_empty=occupied and all(f['status']=='available' for f in folders) and _empty_initial_tree(root,names)
        reset=state.get('setup_reset') or {}
        approved_reset=False
        if reset and not known and not registry_history and not old_database and not custom_configuration:
            import hashlib,json
            history=reset.get('history','')
            if history.startswith('setup-history-') and Path(history).name==history:
                previous=_read(_control_location(root)/history,{})
                approved_reset=(hashlib.sha256(json.dumps(previous,sort_keys=True).encode()).hexdigest()==reset.get('previous_state_sha256')
                                and state.get('workspace')==root_id and _empty_initial_tree(root,names))
        empty_new=(not (known or registry_history or old_database or evidence or custom_configuration) or approved_reset) and (not occupied or structural_empty)
        safe_resume=resuming and not ((registry_history and not registry_technical) or old_database) and _empty_initial_tree(root,names)
        # Already created technical DB/default rows do not establish prior use.
        # A bootstrap intent can only complete its exact empty structural tree.
        if resuming:issues.append({'code':'initialization_pending','path':str(root)})
        if reset and not state.get('storage_initialization') and not approved_reset:
            issues.append({'code':'reset_requires_empty','path':str(root)})
        missing_catalog=database is not None and (not Path(database).is_file() or Path(database).stat().st_size==0)
        if missing_catalog and not safe_resume:
            archive=os.environ.get('KAMERA_ARCHIVE_ROOT')
            archive_occupied=bool(archive and Path(archive).is_dir() and any(Path(archive).iterdir()))
            if registered or (occupied and not _empty_initial_tree(root,names)) or archive_occupied:
                issues.append({'code':'catalog_unavailable','path':str(database)})
        if database is not None and not Path(database).is_file() and (known or registered) and not safe_resume:
            issues.append({'code':'catalog_unavailable','path':str(database)})
        can_initialize=(empty_new or safe_resume) and all(i['code'] in {'missing','initialization_pending'} for i in issues)
        reset=setup_again_evidence(root,database=database) if issues and database is not None else {'allowed':False}
        return {'can_setup_again':reset['allowed'],'setup_token':reset.get('token'),'setup_blocker':reset.get('reason'),'ready':not issues,'can_initialize':can_initialize,'existing_installation':existing and not safe_resume,'workspace':str(root),'folders':folders,'issues':issues,'mount_evidence':'administrator_responsibility','initialization_evidence':'resumable_empty_structure' if safe_resume else 'new_empty_installation' if empty_new else 'existing_or_unclear'}

    except Exception as error:
        return {'ready':False,'can_initialize':False,'existing_installation':True,'workspace':str(root),'folders':folders,'issues':[{'code':'evidence_unreadable','path':str(root),'detail':str(error)}]}


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
        with trash_retention.qualified(parent,users,directory=True) as (_,check):check()
        if not state or state.get('workspace')!=_identity(root) or names!=ENGLISH_STORAGE_DEFAULTS:
            raise ValueError('workspace_or_legacy_binding')
        if state.get('storage_names')!=names or not state.get('storage_initialization'):
            raise ValueError('unknown_initialization')
        if not _empty_initial_tree(root,names):raise ValueError('workspace_not_empty')
        for pattern in ['operation-*.json','mutation.json','finished-*.json']:
            if list(parent.glob(pattern)):raise ValueError('unresolved_reservation')
        if any(p.is_symlink() or (p.suffix=='.json' and p.name!='state.json' and not p.name.startswith('setup-history-')) for p in parent.iterdir()):
            raise ValueError('unknown_control_evidence')
        # Every private media retention and every surviving catalogue is evidence
        # of a used installation, regardless of its current registration flag.
        database=Path(database).absolute()
        if state['storage_initialization'].get('database')!=str(database):raise ValueError('database_binding_changed')
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
        if registry.exists():
            if registry.is_symlink() or not registry.is_file():raise ValueError('registry_invalid')
            if registry.stat().st_size:
                with closing(sqlite3.connect(registry.as_uri()+'?mode=ro',uri=True)) as c:
                    tables={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                    if not {'libraries','registry_schema_versions'}<=tables:raise ValueError('unknown_registry_schema')
                    for table in tables-{'registry_schema_versions'}:
                        quoted='"'+table.replace('"','""')+'"'
                        if c.execute('SELECT 1 FROM '+quoted+' LIMIT 1').fetchone():raise ValueError('library_or_stock_registry_history')
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
        if configured_archive and Path(configured_archive).is_dir() and any(Path(configured_archive).iterdir()):raise ValueError('archive_content_survives')
        if (config.get('metadata_correction') or {}).get('general_root'):raise ValueError('external_metadata_configuration_survives')
        # Old bindings outside the empty managed tree can denote an archive or a
        # different mount. They must remain identical and empty, never guessed.
        allowed={str(root),*(str(root/n) for n in names.values())}
        for value,identity in state.get('bindings',{}).items():
            path=Path(value)
            if value in allowed:continue
            if path.is_relative_to(root):
                if path.exists() or path.is_symlink():raise ValueError('historical_workspace_content')
            elif _identity(path)!=identity or any(path.iterdir()):raise ValueError('historical_external_binding')
        # Reopen every component without following links, including configured
        # private files' parent namespace; existence/access alone is not proof.
        from app.import_publication import _parent
        observed={}
        for path in [root,*(root/n for n in names.values())]:
            try:
                with _parent(path/'probe') as (fd,_):
                    st=os.fstat(fd);observed[str(path)]=[st.st_dev,st.st_ino]
                    if os.fstatvfs(fd).f_flag&os.ST_RDONLY or not os.access(path,os.R_OK|os.W_OK|os.X_OK):raise ValueError('not_writable')
            except FileNotFoundError:
                if path==root:raise
                observed[str(path)]=None
        if observed[str(root)]!=state['workspace']:raise ValueError('workspace_changed_during_check')
        material={'state':state,'observed':observed,'database':str(database),'registry':str(registry),'config':config}
        return {'allowed':True,'token':hashlib.sha256(json.dumps(material,sort_keys=True).encode()).hexdigest(),'observed':observed}
    except Exception as error:
        return {'allowed':False,'reason':str(error)}
