"""Structural anchors only. Dynamic media, day folders and jobs are not anchors."""
from contextlib import closing
from pathlib import Path
import os,sqlite3,stat


def definitions(workspace,state):
    from app.storage_config import load_storage_settings,storage_paths,_config_path
    from app.managed_directory_names import directory_name
    from app.appdata import root as appdata_root,mount
    root=Path(workspace).absolute();paths=storage_paths(root)
    result={str(root):{'role':'workspace','writable':True}}
    for key,value in load_storage_settings(workspace_root=root).items():result[str(root/value)]={'role':key,'writable':True}
    saved=state.get('structural_anchors',{})
    for kind in ('metadata_general','metadata_multiple'):
        prior=next((p for p,v in saved.items() if v['role']==kind),None)
        path=Path(prior) if prior else paths['metadata_root']/directory_name(paths['metadata_root'],kind)
        result[str(path)]={'role':kind,'writable':True}
    registry=os.environ.get('KAMERA_REGISTRY_DATABASE')
    if registry and Path(registry).is_file():
        with closing(sqlite3.connect(Path(registry).absolute().as_uri()+'?mode=ro',uri=True)) as c:
            registered = c.execute('SELECT library_id,work_root,archive_root FROM libraries WHERE COALESCE(is_registered,1)=1 AND workspace_root=?',(str(root),)).fetchall() if c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='libraries'").fetchone() else []
            for lid,work,archive in registered:
                result[work]={'role':'library_work_root:'+lid,'writable':True}
                result[archive]={'role':'library_archive_root:'+lid,'writable':False}
    base=appdata_root()
    if base:
        result[str(base)]={'role':'appdata','writable':True}
        for name in ('config','database','logs','removable-sources'):
            path=base/name;row={'role':'appdata_'+name,'writable':True}
            m=mount(path)
            if name=='removable-sources' and m and m['target']==str(path) and m['filesystem']=='tmpfs':row['policy']='runtime_tmpfs'
            result[str(path)]=row
    return result


def issues(workspace,state,*,initializing=False):
    from app.appdata import mount
    from app.root_operations import _read,_control_location
    result=[];saved=state.get('structural_anchors',{})
    for name,row in definitions(workspace,state).items():
        path=Path(name);old=saved.get(name);expected=(old or {}).get('identity',state.get('bindings',{}).get(name))
        try:
            info=path.lstat()
            if not stat.S_ISDIR(info.st_mode) or path.resolve()!=path:raise ValueError('symlink or non-directory')
            runtime=row.get('policy')=='runtime_tmpfs'
            if old and old.get('policy')!=row.get('policy'):raise ValueError('anchor policy changed')
            if runtime:
                if info.st_uid!=0 or info.st_mode&0o022:raise ValueError('unsafe removable runtime')
            elif expected is not None and expected!=[info.st_dev,info.st_ino]:raise ValueError('anchor identity changed')
            mode=os.R_OK|os.X_OK|(os.W_OK if row['writable'] and not runtime else 0)
            if not os.access(path,mode):raise PermissionError('required access missing')
            if old and old.get('mount')!=mount(path) and not runtime:raise ValueError('anchor mount changed')
            if str(workspace)=='/workspace' and row['role'].startswith('library_archive_root:') and not os.statvfs(path).f_flag&os.ST_RDONLY:raise ValueError('archive mount is not read-only')
        except FileNotFoundError:
            if not initializing:result.append({'code':'missing','path':name,'key':row['role']})
        except (OSError,ValueError) as error:result.append({'code':'structural_anchor_invalid','path':name,'detail':str(error),'key':row['role']})
    # Only anchor contradictions are global. Stale dynamic bindings are a domain issue.
    protected=set(definitions(workspace,state))
    for path in _control_location(workspace).glob('operation-*.json'):
        try:
            record=_read(path)
            if not isinstance(record,dict) or not isinstance(record.get('bindings'),dict):raise ValueError('invalid control record')
            for p,identity in record['bindings'].items():
                if p in protected and identity is not None and state.get('bindings',{}).get(p) not in (None,identity):raise ValueError('contradictory protected root binding: '+p)
        except Exception as error:result.append({'code':'control_identity_invalid','path':str(path),'detail':str(error)})
    return result


def pin(workspace):
    from app import root_operations as ro
    from app.appdata import mount
    root,parent=ro._control(workspace)
    with ro._lock(parent/'workspace.lock'), ro._lock(parent/'state.lock',exclusive=True,wait=True):
        state=ro._state(parent,root)
        problems=issues(root,state)
        if problems:raise ro.RootOperationError('structural_anchor_qualification_failed: '+str(problems))
        current=state.setdefault('structural_anchors',{})
        for name,row in definitions(root,state).items():
            if name in current:continue
            info=Path(name).stat();entry=dict(row,identity=[info.st_dev,info.st_ino],mount=mount(name))
            current[name]=entry
        ro._write(parent/'state.json',state)
