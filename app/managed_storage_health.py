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
    for path in root.rglob('*'):
        info=path.lstat();rel=path.relative_to(root).as_posix()
        if stat.S_ISDIR(info.st_mode) and rel in allowed:continue
        if rel==lock and stat.S_ISREG(info.st_mode) and info.st_size==0 and info.st_nlink==1 and info.st_uid==os.geteuid() and not info.st_mode&0o022:continue
        return False
    return True


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
        empty_new=not (known or registry_history or old_database or evidence or custom_configuration) and (not occupied or structural_empty)
        safe_resume=resuming and not ((registry_history and not registry_technical) or old_database) and _empty_initial_tree(root,names)
        # Already created technical DB/default rows do not establish prior use.
        # A bootstrap intent can only complete its exact empty structural tree.
        if resuming:issues.append({'code':'initialization_pending','path':str(root)})
        if database is not None and not Path(database).is_file() and (known or registered) and not safe_resume:
            issues.append({'code':'catalog_unavailable','path':str(database)})
        can_initialize=(empty_new or safe_resume) and all(i['code'] in {'missing','initialization_pending'} for i in issues)
        return {'ready':not issues,'can_initialize':can_initialize,'existing_installation':existing and not safe_resume,'workspace':str(root),'folders':folders,'issues':issues,'mount_evidence':'administrator_responsibility','initialization_evidence':'resumable_empty_structure' if safe_resume else 'new_empty_installation' if empty_new else 'existing_or_unclear'}

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
