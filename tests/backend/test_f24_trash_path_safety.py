"""Synthetic namespace races, permanent-byte assertions and real SIGKILL."""
import errno,hashlib,json,os,subprocess,sys,threading
from contextlib import contextmanager
from pathlib import Path
import pytest
from app import trash_selective as ts
from app.trash import TrashError
from app.trash_path_safety import DirectoryTree
from app.database import database_connection
from tests.backend import test_0562_process_recovery as r
from tests.backend.test_0562_process_recovery import isolated_process_environment


@pytest.fixture(autouse=True)
def preserve_configuration(monkeypatch,tmp_path):
    monkeypatch.setenv("KAMERA_CONFIG",os.environ.get("KAMERA_CONFIG",str(tmp_path/"settings.json")))


def seed(tmp_path):
    case=tmp_path/'case';case.mkdir();ev=tmp_path/'f24-evidence';ev.mkdir()
    for action,boundary in [('seed','trash'),('startup','none')]:assert r.invoke(case,action,boundary,ev/action)['returncode']==0
    data=json.loads((case/'case.json').read_text());data['dbs']=[Path(p) for p in data['databases']]
    os.environ['KAMERA_CONFIG']=str(case/'settings.json');r.snapshot(case,ev/'before.json')
    return case,ev,data,Path(data['workspace'])


def starts(case,ev,blocked=False):
    states=[];label='blocked' if blocked else 'restart'
    for n in (1,2,3):
        record=r.invoke(case,'recover_trash_only' if blocked else 'startup','none',ev/f'{label}{n}')
        assert (record['returncode']!=0)==blocked,record
        state=r.snapshot(case,ev/f'after-{label}{n}.json');r.checks_sql(state);states.append(state)
    assert r.business_rows(states[0])==r.business_rows(states[1])==r.business_rows(states[2])
    return states[-1]


def delete(data,ws,paths=None):return ts.delete_selected_trash_files(data['dbs'],ws,paths or ['A.JPG'])


def originals(data,ws):
    for name,digest in data['expected'].items():assert hashlib.sha256((ws/'Papierkorb'/name).read_bytes()).hexdigest()==digest


@pytest.mark.parametrize('component',['trash','source_parent','metadata','staging','workspace'])
@pytest.mark.parametrize('same',[False,True])
def test_f24_directory_swap(tmp_path,monkeypatch,component,same):
    case,ev,data,ws=seed(tmp_path);outside=case/'outside';outside.mkdir();victim=outside/'A.JPG'
    expected=b'synthetic-trash-A.JPG' if same else b'synthetic-foreign-canary';victim.write_bytes(expected);path='A.JPG'
    if component=='source_parent':
        (ws/'Papierkorb/Folder').mkdir();(ws/'Papierkorb/A.JPG').rename(ws/'Papierkorb/Folder/A.JPG');path='Folder/A.JPG'
        for db in data['dbs']:
            with database_connection(db) as c:c.execute("UPDATE files SET current_relative_path=? WHERE current_relative_path='A.JPG'",(path,))
    real=ts._move_checked;swapped=[]
    def swap(source,target,*a,**kw):
        entry={'trash':ws/'Papierkorb','source_parent':ws/'Papierkorb/Folder','metadata':ws/'Metadatenkorrektur','staging':target.parent,'workspace':ws}[component]
        saved=entry.with_name(entry.name+'-saved-by-test');entry.rename(saved);entry.symlink_to(outside,target_is_directory=True);swapped.extend([entry,saved])
        return real(source,target,*a,**kw)
    monkeypatch.setattr(ts,'_move_checked',swap)
    with pytest.raises((TrashError,OSError)):delete(data,ws,[path])
    assert victim.read_bytes()==expected;r.snapshot(case,ev/'after-conflict.json');starts(case,ev,True);assert victim.read_bytes()==expected
    entry,saved=swapped;entry.unlink();saved.rename(entry)  # explicit synthetic operator repair
    monkeypatch.setattr(ts,'_move_checked',real);starts(case,ev)
    assert victim.read_bytes()==expected and hashlib.sha256((ws/'Papierkorb'/path).read_bytes()).hexdigest()==data['expected']['A.JPG']


@pytest.mark.parametrize('replacement',['same','different','symlink','hardlink','directory'])
def test_f24_last_component(tmp_path,monkeypatch,replacement):
    case,ev,data,ws=seed(tmp_path);outside=case/'outside';outside.mkdir();victim=outside/'A.JPG';before=b'synthetic-trash-A.JPG';victim.write_bytes(before)
    source=ws/'Papierkorb/A.JPG';saved=ws/'Papierkorb/original-A.JPG';real=ts.rename_exclusive;once=[True]
    def swap(*args):
        if once[0] and args[1]=='A.JPG':
            once[0]=False
            program="""from pathlib import Path
import os,sys,json
source,saved,victim=map(Path,sys.argv[1:4]);kind=sys.argv[4];source.rename(saved)
if kind=='symlink':source.symlink_to(victim)
elif kind=='hardlink':os.link(victim,source)
elif kind=='directory':source.mkdir();(source/'canary').write_bytes(b'foreign-member')
else:source.write_bytes(victim.read_bytes() if kind=='same' else b'foreign-different')
print(json.dumps({'pid':os.getpid(),'uid':os.geteuid(),'boundary':'after verified private snapshot, before atomic capture'}))
"""
            child=subprocess.run([sys.executable,'-c',program,str(source),str(saved),str(victim),replacement],capture_output=True,text=True,timeout=10,check=True)
            (ev/'external-writer.json').write_text(child.stdout)
        return real(*args)
    monkeypatch.setattr(ts,'rename_exclusive',swap)
    with pytest.raises((TrashError,OSError)):delete(data,ws)
    assert victim.read_bytes()==before and saved.read_bytes()==before
    if replacement=='directory':assert (source/'canary').read_bytes()==b'foreign-member'
    elif replacement=='symlink':assert source.is_symlink()
    else:assert source.read_bytes()==(before if replacement in {'same','hardlink'} else b'foreign-different')
    r.snapshot(case,ev/'after-leaf-conflict.json');starts(case,ev,True);assert victim.read_bytes()==before
    source.rename(case/'preserved-foreign-entry');saved.rename(source);monkeypatch.setattr(ts,'rename_exclusive',real)
    starts(case,ev);assert source.read_bytes()==before and victim.read_bytes()==before


@pytest.mark.parametrize('boundary',['before_capture','after_capture','before_private_unlink'])
def test_f24_stage_swap(tmp_path,monkeypatch,boundary):
    case,ev,data,ws=seed(tmp_path);outside=case/'outside';outside.mkdir();victim=outside/'A.JPG';before=b'synthetic-trash-A.JPG';victim.write_bytes(before);swapped=[]
    def swap_stage(tree):
        stage=tree.private_root/tree.record['id'];saved=stage.with_name(stage.name+'-saved-by-test');stage.rename(saved);stage.symlink_to(outside,target_is_directory=True);swapped.extend([stage,saved])
    if boundary=='before_private_unlink':
        real=DirectoryTree.unlink_private
        def wrapped(self,path,*a,**kw):
            if not swapped and '.captured' in path.parts:swap_stage(self)
            return real(self,path,*a,**kw)
        monkeypatch.setattr(DirectoryTree,'unlink_private',wrapped)
    else:
        real=ts.rename_exclusive
        def wrapped(*a):
            if not swapped and a[1]=='A.JPG':
                tree=ts.ACTIVE.get()
                if boundary=='before_capture':swap_stage(tree)
                result=real(*a)
                if boundary=='after_capture':swap_stage(tree)
                return result
            return real(*a)
        monkeypatch.setattr(ts,'rename_exclusive',wrapped)
    with pytest.raises((TrashError,OSError)):delete(data,ws)
    assert victim.read_bytes()==before;r.snapshot(case,ev/'after-stage-conflict.json');starts(case,ev,True)
    entry,saved=swapped;entry.unlink();saved.rename(entry);starts(case,ev)
    assert victim.read_bytes()==before;originals(data,ws)


def test_f24_no_public_unlink(tmp_path,monkeypatch):
    case,ev,data,ws=seed(tmp_path);public=(ws/'Papierkorb').stat();real=os.unlink;seen=[]
    if sys.platform.startswith('linux'):
        native=DirectoryTree.native
        def confined(self,operation,**kw):
            if operation=='unlink':
                info=os.fstat(kw['dst']);assert (info.st_dev,info.st_ino)!=(public.st_dev,public.st_ino);seen.append(kw['target'])
            return native(self,operation,**kw)
        monkeypatch.setattr(DirectoryTree,'native',confined)
    else:
        def checked(path,*a,**kw):
            fd=kw.get('dir_fd');assert fd is not None
            info=os.fstat(fd);assert (info.st_dev,info.st_ino)!=(public.st_dev,public.st_ino)
            seen.append(str(path));return real(path,*a,**kw)
        monkeypatch.setattr(os,'unlink',checked)
    assert delete(data,ws)['deleted_file_count']==1;assert seen
    monkeypatch.setattr(os,'unlink',real);starts(case,ev)


def test_f24_snapshot_independent_of_source_hardlink(tmp_path,monkeypatch):
    case,ev,data,ws=seed(tmp_path);outside=case/'outside-hardlink.JPG';os.link(ws/'Papierkorb/A.JPG',outside);inode=outside.stat().st_ino;real=ts._purge_selected
    def observe(*a):
        staged=next(case.rglob('DELETE_*/A.JPG'));assert staged.stat().st_ino!=inode
        outside.write_bytes(b'external-in-place-edit');assert hashlib.sha256(staged.read_bytes()).hexdigest()==data['expected']['A.JPG']
        return real(*a)
    monkeypatch.setattr(ts,'_purge_selected',observe)
    with pytest.raises(TrashError):delete(data,ws)
    assert outside.read_bytes()==b'external-in-place-edit'
    staged=next(case.rglob('DELETE_*/A.JPG'));assert hashlib.sha256(staged.read_bytes()).hexdigest()==data['expected']['A.JPG']
    r.snapshot(case,ev/'independent-snapshot-after-external-edit.json')
    # Explicit synthetic operator repair restores the changed original version.
    outside.write_bytes(b'synthetic-trash-A.JPG');starts(case,ev);originals(data,ws)


@pytest.mark.parametrize('guard',['private_permissions','unknown_acl','unsupported_filesystem','cross_mount_capture'])
def test_f24_unclear_boundary(tmp_path,monkeypatch,guard):
    case,ev,data,ws=seed(tmp_path);source=ws/'Papierkorb/A.JPG';before=source.read_bytes()
    if guard=='private_permissions':
        real=ts._move_checked
        def insecure(s,t,*a,**kw):t.parent.chmod(0o777);return real(s,t,*a,**kw)
        monkeypatch.setattr(ts,'_move_checked',insecure)
    elif guard=='unknown_acl':monkeypatch.setattr(os,'listxattr',lambda *a,**kw:['system.nfs4_acl_xdr'],raising=False)
    elif guard=='unsupported_filesystem':monkeypatch.setattr(DirectoryTree,'qualify_filesystem',staticmethod(lambda fd:(_ for _ in ()).throw(TrashError('unqualified synthetic filesystem'))))
    else:monkeypatch.setattr(ts,'rename_exclusive',lambda *a:(_ for _ in ()).throw(OSError(errno.EXDEV,'synthetic mount boundary')))
    with pytest.raises((TrashError,OSError)):delete(data,ws)
    assert source.read_bytes()==before;r.snapshot(case,ev/'after-denial.json')


@pytest.mark.parametrize('boundary',['f24.link','f24.staged','f24.capture','f24.capture_unlink','trash.db1','trash.committed','trash.cleanup1'])
def test_f24_sigkill(tmp_path,boundary):
    case,ev,data,ws=seed(tmp_path);before=r.snapshot(case,ev/'before-kill.json')
    r.invoke(case,'operate',boundary,ev/'kill',kill=True);r.snapshot(case,ev/'after-kill.json');state=starts(case,ev)
    committed=boundary in {'trash.committed','trash.cleanup1','f24.capture_unlink'}
    for db in ('kamera.sqlite3','second1.sqlite3'):
        for table in ('files','file_families'):assert r.db_rows(state,table,db)==([] if committed else r.db_rows(before,table,db))
    if committed:assert not (ws/'Papierkorb/A.JPG').exists() and not (ws/'Papierkorb/B.JPG').exists()
    else:originals(data,ws)
    assert not list(case.rglob('DELETE_*.json'))


@pytest.mark.parametrize('boundary',['f24.recover_publish','f24.recover_cleanup'])
def test_f24_recovery_sigkill_twice(tmp_path,boundary):
    case,ev,data,ws=seed(tmp_path);r.invoke(case,'operate','trash.db1',ev/'kill',kill=True)
    for n in (1,2):r.invoke(case,'startup',boundary,ev/f'recovery-kill{n}',kill=True);r.snapshot(case,ev/f'after-recovery-kill{n}.json')
    starts(case,ev);originals(data,ws);assert not list(case.rglob('DELETE_*.json'))


def test_f24_legacy_v2(tmp_path):
    case,ev,data,ws=seed(tmp_path);r.invoke(case,'operate','trash.db1',ev/'kill',kill=True)
    path=next(case.rglob('DELETE_*.json'));record=json.loads(path.read_text());record['format']=2
    for item in record['files']:
        for key in ('source_identity','staged_identity','link_path'):item.pop(key,None)
    for item in record['files']:
        staged=path.with_suffix('')/item['path'];capture=path.with_suffix('')/'.captured'/item['path']
        if capture.exists():
            staged.rename(case/('preserved-prototype-snapshot-'+Path(item['path']).name));capture.rename(staged)
    path.write_text(json.dumps(record));r.snapshot(case,ev/'legacy-v2.json');starts(case,ev);originals(data,ws)


def test_f24_parallel_stage_and_selected_delete(tmp_path,monkeypatch):
    case,ev,data,ws=seed(tmp_path);reached=threading.Event();release=threading.Event();attempt=threading.Event();results=[]
    actual_move=ts._move_checked;actual_lock=ts._operation_lock
    def pause(*args,**kw):
        value=actual_move(*args,**kw)
        if threading.current_thread().name=='stage-A':reached.set();assert release.wait(15)
        return value
    @contextmanager
    def observed_lock(*args,**kw):
        if threading.current_thread().name=='delete-B':attempt.set()
        with actual_lock(*args,**kw):yield
    monkeypatch.setattr(ts,'_move_checked',pause);monkeypatch.setattr(ts,'_operation_lock',observed_lock)
    def run(path):
        try:results.append(delete(data,ws,[path]))
        except Exception as error:results.append(error)
    first=threading.Thread(target=run,args=('A.JPG',),name='stage-A');first.start();assert reached.wait(15)
    second=threading.Thread(target=run,args=('B.JPG',),name='delete-B');second.start();assert attempt.wait(15)
    assert results==[] and (ws/'Papierkorb/B.JPG').is_file();r.snapshot(case,ev/'second-waits-for-staging.json')
    release.set();first.join(15);second.join(15);assert not first.is_alive() and not second.is_alive()
    assert results==[{'deleted_file_count':1},{'deleted_file_count':1}],results
    starts(case,ev);assert not list(case.rglob('DELETE_*.json'))


def test_f24_rollback_preserves_original_inode_and_attributes(tmp_path):
    case,ev,data,ws=seed(tmp_path);source=ws/'Papierkorb/A.JPG';source.chmod(0o640);os.utime(source,ns=(1600000000000000000,1600000001000000000));before=source.stat()
    r.invoke(case,'operate','trash.db1',ev/'kill',kill=True);r.snapshot(case,ev/'after-kill.json');starts(case,ev)
    after=source.stat()
    assert (after.st_dev,after.st_ino,after.st_uid,after.st_gid,after.st_mode&0o777,after.st_mtime_ns)==(before.st_dev,before.st_ino,before.st_uid,before.st_gid,before.st_mode&0o777,before.st_mtime_ns)
    originals(data,ws)


def test_f24_missing_original_preserves_snapshot_and_journal(tmp_path):
    case,ev,data,ws=seed(tmp_path);r.invoke(case,'operate','f24.staged',ev/'kill',kill=True)
    source=ws/'Papierkorb/A.JPG';source.rename(case/'external-moved-original.JPG')
    starts(case,ev,True);assert list(case.rglob('DELETE_*.json'))
    staged=next(case.rglob('DELETE_*/A.JPG'));assert hashlib.sha256(staged.read_bytes()).hexdigest()==data['expected']['A.JPG']
    (case/'external-moved-original.JPG').rename(source);starts(case,ev);originals(data,ws)


@pytest.mark.parametrize('hardlink',[True,False])
def test_f24_legacy_dual_copy_ownership(tmp_path,hardlink):
    case,ev,data,ws=seed(tmp_path);r.invoke(case,'operate','f24.link',ev/'kill',kill=True)
    path=next(case.rglob('DELETE_*.json'));record=json.loads(path.read_text());stage=path.with_suffix('');record['format']=2
    first=record['files'][0];link=stage/first['link_path'];target=stage/first['path']
    if hardlink:link.rename(target)
    else:target.write_bytes(link.read_bytes());link.rename(case/'preserved-link-evidence.JPG')
    for item in record['files']:
        for key in ('source_identity','staged_identity','link_path'):item.pop(key,None)
    path.write_text(json.dumps(record));starts(case,ev,blocked=not hardlink);originals(data,ws)
    if not hardlink:assert path.exists() and hashlib.sha256(target.read_bytes()).hexdigest()==data['expected']['A.JPG']
