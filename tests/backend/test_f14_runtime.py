"""Real file-operation boundaries, full application starts and F14 conflicts."""
from pathlib import Path
import hashlib,json,os,signal,subprocess,sys,time
import pytest
from app import main
from app.database import database_connection
from app.library_registry import update_library_paths
from app.library_context import resolve_library_context
from app.storage_config import load_storage_settings,storage_paths
from tests.backend import test_0562_process_recovery as r
from tests.backend.test_0562_process_recovery import isolated_process_environment


def fixture(tmp_path,monkeypatch,kind,managed=False):
    ev,case,data=r.new_case(tmp_path,kind,'f14-'+tmp_path.name)
    db=Path(data['db']);ws=Path(data['workspace']);reg=db.parent/'registry.sqlite3'
    monkeypatch.setenv('KAMERA_CONFIG',str(db.parent/'settings.json'))
    monkeypatch.setenv('KAMERA_REGISTRY_DATABASE',str(reg))
    if managed:
        legacy=ws/'Arbeitsbereich';managed_root=storage_paths(ws)['workspaces_root']/'main';managed_root.parent.mkdir(exist_ok=True)
        legacy.rename(managed_root);legacy.symlink_to(managed_root,target_is_directory=True)
        update_library_paths(reg,'main',work_root=managed_root)
    context=resolve_library_context(reg,'main')
    for key,value in {'WORKSPACE_PATH':ws,'DATABASE_FILE':db,'REGISTRY_DATABASE_FILE':reg,'CONFIG_PATH':db.parent/'settings.json','MAIN_LIBRARY_CONTEXT':context}.items():monkeypatch.setattr(main,key,value)
    monkeypatch.setattr(main,'current_database_file',lambda:db)
    data['original_media']=[{'path':str(p.relative_to(case)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'inode':p.stat().st_ino,'size':p.stat().st_size} for p in case.rglob('*') if p.is_file() and not p.is_symlink() and p.suffix.upper() in {'.JPG','.JPEG','.PNG','.MOV','.MP4'}]
    assert data['original_media']
    (ev/'original-media.json').write_text(json.dumps(data['original_media'],indent=2))
    r.snapshot(case,ev/'before-operation.json')
    return ev,case,data,db,ws


def begin(case,boundary,ev,label='worker'):
    control=ev/label;control.mkdir();log=(control/'process.log').open('w')
    source=Path(__file__).resolve().parents[2]
    worker=source/'qa/f14/original/worker_concurrent.py'
    process=subprocess.Popen([sys.executable,str(worker),str(case),'operate',boundary,str(control)],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    deadline=time.monotonic()+20
    while process.poll() is None and time.monotonic()<deadline:
        marker=control/'checkpoint.json'
        if marker.exists():
            try:
                if json.loads(marker.read_text())['pid']==process.pid:return process,control,log
            except (ValueError,KeyError):pass
        time.sleep(.01)
    if process.poll() is None:os.killpg(process.pid,signal.SIGKILL);process.wait()
    log.close();raise AssertionError((control/'process.log').read_text())


def finish(process,control,log,kill=False):
    try:
        if kill:os.killpg(process.pid,signal.SIGKILL)
        else:(control/'continue').write_text('continue')
        process.wait(timeout=25)
        assert process.returncode==(-9 if kill else 0),(control/'process.log').read_text()
    finally:
        if process.poll() is None:os.killpg(process.pid,signal.SIGKILL);process.wait()
        log.close()
    result={'pid':process.pid,'returncode':process.returncode,'checkpoint':json.loads((control/'checkpoint.json').read_text())}
    (control/'execution.json').write_text(json.dumps(result,indent=2));return result


def payload(setting='workspaces_directory_name'):
    settings=load_storage_settings();settings[setting]='Changed-'+setting;return settings


def reject(settings):
    with pytest.raises(main.HTTPException) as exc:main.api_set_storage_paths(settings)
    assert exc.value.status_code==410


def originals_survive(case,data):
    identities={(p.stat().st_ino,hashlib.sha256(p.read_bytes()).hexdigest(),p.stat().st_size) for p in case.rglob('*') if p.is_file() and not p.is_symlink()}
    expected=[x for x in data['original_media'] if data['kind']!='ssd' or x['path'].startswith('archive/')]
    assert expected
    assert all((x['inode'],x['sha256'],x['size']) in identities for x in expected)


@pytest.mark.parametrize('kind,boundary',[('import','import.move1'),('sort','sort.move1'),('reconcile','reconcile.move1')])
def test_f14_real_worker_rejects_rename_then_allows_completion(tmp_path,monkeypatch,kind,boundary):
    ev,case,data,db,ws=fixture(tmp_path,monkeypatch,kind)
    process,control,log=begin(case,boundary,ev)
    try:
        reject(payload('backup_directory_name'))
        r.snapshot(case,ev/'blocked-before-worker-resume.json')
    finally:finish(process,control,log)
    state=r.three_restarts(case,ev);originals_survive(case,data)
    reject(payload('backup_directory_name'))
    r.snapshot(case,ev/'completed-then-root-changed.json')
    for n in (1,2,3):
        assert r.invoke(case,'startup','none',ev/f'after-rename-start{n}')['returncode']==0
        r.checks_sql(r.snapshot(case,ev/f'after-rename-start{n}.json'))
    originals_survive(case,data)


@pytest.mark.parametrize('boundary',['ssd.archive_verified','ssd.unlink1'])
@pytest.mark.parametrize('kill',[False,True])
def test_f14_ssd_real_boundary_and_partial_journal(tmp_path,monkeypatch,boundary,kill):
    ev,case,data,db,ws=fixture(tmp_path,monkeypatch,'ssd',managed=True)
    process,control,log=begin(case,boundary,ev)
    try:
        reject(payload());paused=r.snapshot(case,ev/'root-change-rejected.json')
        originals_survive(case,data)
    finally:finish(process,control,log,kill=kill)
    if kill:
        with database_connection(db) as c:assert c.execute("SELECT COUNT(*) FROM event_ssd_releases WHERE status='completed'").fetchone()[0]==0
        state=r.three_restarts(case,ev)
        # Direct releases have no queued retry task. These starts must preserve
        # remaining SSD files; this does not replace F13's background contract.
        first={x['path']:x['sha256'] for x in paused['files'] if x['path'].endswith('.JPG')}
        final={x['path']:x['sha256'] for x in state['files'] if x['path'].endswith('.JPG')}
        assert first==final
        reject(payload())
        retry=r.invoke(case,'retry','none',ev/'explicit-retry');assert retry['returncode']==0,retry
    with database_connection(db) as c:
        assert c.execute("SELECT COUNT(*) FROM event_ssd_releases WHERE status='completed'").fetchone()[0]==1
        rows=c.execute('SELECT current_relative_path,sha256_current FROM files').fetchall();assert len(rows)==2
        for row in rows:assert hashlib.sha256((case/'archive'/row['current_relative_path']).read_bytes()).hexdigest()==row['sha256_current']
    reject(payload())
    r.snapshot(case,ev/'after-safe-completion-and-rename.json');originals_survive(case,data)


@pytest.mark.parametrize('same_bytes',[False,True])
def test_f14_manual_root_replacement_during_sort_preserves_foreign_files(tmp_path,monkeypatch,same_bytes):
    ev,case,data,db,ws=fixture(tmp_path,monkeypatch,'sort')
    root=storage_paths(ws)['backup_root'];process,control,log=begin(case,'sort.move1',ev)
    old=root.with_name(root.name+'-external');root.rename(old);root.mkdir()
    remaining=next(old.rglob('*.JPG'));foreign=root/remaining.relative_to(old);foreign.parent.mkdir(parents=True,exist_ok=True)
    foreign_bytes=remaining.read_bytes() if same_bytes else b'foreign-original';foreign.write_bytes(foreign_bytes);foreign_inode=foreign.stat().st_ino
    try:
        (control/'continue').write_text('continue');process.wait(timeout=25)
        assert process.returncode!=0
    finally:
        if process.poll() is None:os.killpg(process.pid,signal.SIGKILL);process.wait()
        log.close()
    assert foreign.read_bytes()==foreign_bytes and foreign.stat().st_ino==foreign_inode;originals_survive(case,data)
    for n in (1,2,3):
        result=r.invoke(case,'startup','none',ev/f'blocked-start{n}');assert result['returncode']!=0
        assert foreign.read_bytes()==foreign_bytes and foreign.stat().st_ino==foreign_inode;originals_survive(case,data)
        r.snapshot(case,ev/f'blocked-start{n}.json')


@pytest.mark.parametrize('kind',['inventory','archive-verification'])
def test_f14_actual_scan_holds_root_binding(tmp_path,monkeypatch,kind):
    import threading
    from app import event_inventory as inventory,archive_transfer as archive
    ev,case,data,db,ws=fixture(tmp_path,monkeypatch,'ssd')
    context=resolve_library_context(db.parent/'registry.sqlite3','main')
    reached=threading.Event();release=threading.Event();results=[];errors=[]
    module,function=(inventory,'_iter_regular_event_files') if kind=='inventory' else (inventory,'_sha256_file')
    real=getattr(module,function)
    def barrier(*args,**kwargs):
        reached.set();assert release.wait(15)
        return real(*args,**kwargs)
    monkeypatch.setattr(module,function,barrier)
    def run():
        try:
            if kind=='inventory':
                results.append(inventory.scan_event_inventory(db,context.work_root,data['job'],data['event'],root_kind='shared_workspace'))
            else:
                results.append(archive.verify_event_archive(db,context.archive_root,data['job'],data['event'],workspace_path=ws))
        except BaseException as error:errors.append(repr(error))
    thread=threading.Thread(target=run);thread.start()
    try:
        assert reached.wait(15),errors
        reject(payload('backup_directory_name'))
        foreign=case/'new-archive';foreign.mkdir()
        with pytest.raises(main.HTTPException) as exc:
            main.api_update_library('main',{'archive_root':str(foreign)})
        assert exc.value.status_code==409
        originals_survive(case,data)
        r.snapshot(case,ev/'scan-paused-root-change-rejected.json')
    finally:release.set();thread.join(20)
    assert not thread.is_alive() and not errors and len(results)==1
    if kind=='archive-verification':assert results[0]['verified'] is True
    r.three_restarts(case,ev);originals_survive(case,data)
    r.snapshot(case,ev/'scan-complete.json')
