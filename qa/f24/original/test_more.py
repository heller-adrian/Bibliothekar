from pathlib import Path
import os,json,threading,subprocess,sys,time,hashlib
import pytest
from test_interleavings import seed,thread_call
from test_process_crashes import invoke,snapshot,checks_sql
from app import main
from app.database import database_connection


def start(case,kind,boundary,ev):
    control=ev/'concurrent-worker';control.mkdir()
    log=(control/'process.log').open('w')
    child=subprocess.Popen([sys.executable,str(Path(__file__).with_name('worker_concurrent.py')),str(case),'operate',boundary,str(control)],stdout=log,stderr=subprocess.STDOUT)
    until=time.monotonic()+15
    while time.monotonic()<until:
        if (control/'checkpoint.json').exists():
            try:
                marker=json.loads((control/'checkpoint.json').read_text())
                if marker['pid']==child.pid:return child,control,log
            except ValueError:pass
        if child.poll() is not None:break
        time.sleep(.01)
    child.kill();child.wait();log.close();raise AssertionError((control/'process.log').read_text()[-2000:])

def release(child,control,log):
    (control/'continue').write_text('resume')
    try:child.wait(timeout=20)
    finally:
        if child.poll() is None:child.kill();child.wait()
        log.close()
    return json.loads((control/'result.json').read_text())

def end(case,ev,trace):
    (ev/'interleaving.json').write_text(json.dumps(trace,indent=2,default=str));snapshot(case,ev/'after-interleaving.json')
    results=[]
    for n in (1,2,3):
        r=invoke(case,'startup','none',ev/f'restart{n}');results.append(r)
        checks_sql(snapshot(case,ev/f'after-restart{n}.json'))
    return results

@pytest.mark.parametrize('kind,boundary',[('import','import.move1'),('sort','sort.move1')])
def test_rename_with_live_worker(tmp_path,monkeypatch,kind,boundary):
    case,ev,data,db,ws=seed(tmp_path,kind,'P403-rename-'+kind,monkeypatch)
    from app.storage_config import load_storage_settings
    old=ws/load_storage_settings()['backup_directory_name']
    child,control,log=start(case,kind,boundary,ev)
    try:
        settings=load_storage_settings();settings['backup_directory_name']='RenamedCentral'
        try:renamed=main.api_set_storage_paths(settings);answer={'accepted':True}
        except Exception as e:answer={'accepted':False,'error':repr(e)}
        snapshot(case,ev/'after-rename-before-worker-resume.json')
    finally:result=release(child,control,log)
    restarts=end(case,ev,{'order':['real worker performs first move','rename central root','worker continues'],'rename':answer,'worker':result})
    assert all(r['returncode']==0 for r in restarts),restarts
    if answer['accepted']:assert not old.exists(),'Live worker recreated old root after successful rename'


def test_inventory_waits_for_restore(tmp_path,monkeypatch):
    case,ev,data,db,ws=seed(tmp_path,'restore','P407-inventory-restore',monkeypatch)
    child,control,log=start(case,'restore','restore.move1',ev)
    import fcntl
    real=fcntl.flock;entered=threading.Event()
    def observed(fd,op):
        if op==fcntl.LOCK_EX:entered.set()
        return real(fd,op)
    monkeypatch.setattr(fcntl,'flock',observed)
    t,results=thread_call(main.api_trash_inventory)
    assert entered.wait(10)
    outcome=release(child,control,log);t.join(10);assert not t.is_alive()
    assert outcome['status']=='ok' and results[0]['ok'],(outcome,results)
    restarts=end(case,ev,{'order':['restore first move with process flock held','inventory attempts actual lock','restore finishes','inventory returns'],'inventory':results,'worker':outcome})
    assert all(r['returncode']==0 for r in restarts)
    for raw in data['databases']:
        with database_connection(Path(raw)) as c:
            rows=c.execute('SELECT * FROM files').fetchall();assert len(rows)==2
            for row in rows:
                assert row['current_root_kind']=='shared_workspace'
                assert hashlib.sha256((ws/'SD-Kartensicherungen'/row['current_relative_path']).read_bytes()).hexdigest()==row['sha256_current']


def test_two_http_restore_requests(tmp_path,monkeypatch):
    case,ev,data,db,ws=seed(tmp_path,'trash','P408-http-duplicate-restore-verified',monkeypatch)
    from fastapi.testclient import TestClient
    barrier=threading.Barrier(3)
    def request():
        client=TestClient(main.app);barrier.wait(timeout=10)
        try:
            response=client.post('/api/trash/restore',json={'relative_paths':['A.JPG']})
            return {'status':response.status_code,'body':response.json()}
        finally:client.close()
    a,x=thread_call(request);b,y=thread_call(request);barrier.wait(timeout=10);a.join(15);b.join(15)
    assert not a.is_alive() and not b.is_alive()
    results=x+y;assert all(r['ok'] for r in results),results
    snapshot(case,ev/'after-HTTP-before-startup.json')
    restarts=end(case,ev,{'order':['two TestClients at barrier','concurrent identical HTTP POST','route reservation locking'],'responses':results})
    assert sorted(r['value']['status'] for r in results)==[200,409],results
    assert all(r['returncode']==0 for r in restarts)
    with database_connection(db) as c:assert c.execute("SELECT COUNT(*) FROM jobs WHERE operation='trash_import'").fetchone()[0]==1
    assert any(p.read_bytes()==b'synthetic-trash-A.JPG' for p in (ws/'SD-Kartensicherungen').rglob('A.JPG'))


def test_hardlink_in_place_characterization(tmp_path,monkeypatch):
    case,ev,data,db,ws=seed(tmp_path,'trash','P405-hardlink-inplace',monkeypatch)
    from app.archive_staging import _stage_verified_source
    source=case/'synthetic-original.JPG';source.write_bytes(b'synthetic-hardlink-original')
    staged=case/'staging/IMG.JPG';digest=hashlib.sha256(source.read_bytes()).hexdigest()
    mode=_stage_verified_source(source,staged,expected_size=source.stat().st_size,expected_sha=digest)
    snapshot(case,ev/'before-inplace-write.json')
    barrier=threading.Barrier(2)
    def editor():barrier.wait(timeout=10);staged.write_bytes(b'synthetic-editor-changed')
    thread=threading.Thread(target=editor);thread.start();barrier.wait(timeout=10);thread.join(10)
    assert not thread.is_alive()
    restarts=end(case,ev,{'order':['actual verified hardlink staging','editor barrier','in-place write on staging'],'mode':mode,'classification':'observed property; application-level reachability not proved'})
    assert mode=='hardlink' and source.stat().st_ino==staged.stat().st_ino
    assert source.read_bytes()==b'synthetic-editor-changed'
    assert all(r['returncode']==0 for r in restarts)


def test_claims_two_libraries(tmp_path,monkeypatch):
    case,ev,data,db,ws=seed(tmp_path,'multi','P406-claim-threads',monkeypatch)
    assert invoke(case,'operate','none',ev/'complete-synthetic-import')['returncode']==0
    snapshot(case,ev/'before-claims.json')
    from app.library_registry import claim_source_family,LibraryRegistryError
    import sqlite3
    from contextlib import closing
    registry=db.parent/'registry.sqlite3'
    with closing(sqlite3.connect(registry)) as c:key=c.execute('SELECT source_family_key FROM source_families ORDER BY source_family_key LIMIT 1').fetchone()[0]
    barrier=threading.Barrier(3)
    def claim(library):
        barrier.wait(timeout=10)
        try:return {'accepted':True,'value':claim_source_family(registry,source_family_key=key,library_id=library,event_id=None)}
        except LibraryRegistryError as e:return {'accepted':False,'error':str(e)}
    a,x=thread_call(lambda:claim('main'));b,y=thread_call(lambda:claim('second1'));barrier.wait(timeout=10);a.join(10);b.join(10)
    assert not a.is_alive() and not b.is_alive()
    results=x+y;assert all(r['ok'] for r in results),results
    assert sum(r['value']['accepted'] for r in results)==1,results
    with closing(sqlite3.connect(registry)) as c:assert c.execute('SELECT COUNT(*) FROM family_claims').fetchone()[0]==1
    restarts=end(case,ev,{'order':['two active libraries claim same canonical family at barrier','BEGIN IMMEDIATE serializes'], 'event_id':None,'results':results,'scope':'claim core; no planned event assignment'})
    assert all(r['returncode']==0 for r in restarts)


@pytest.mark.parametrize('kind',['import','sort'])
def test_rename_same_web_process(tmp_path,monkeypatch,kind):
    case,ev,data,db,ws=seed(tmp_path,kind,'P403-thread-rename-'+kind,monkeypatch)
    monkeypatch.setattr(main,'CONFIG_PATH',db.parent/'settings.json')
    from app.storage_config import load_storage_settings
    reached=threading.Event();proceed=threading.Event();old=ws/load_storage_settings()['backup_directory_name'];count=0
    if kind=='import':
        from app import folder_import as module
        real=module.os.replace
        def paused(src,dst):
            nonlocal count
            result=real(src,dst)
            if '/Original/' in str(src) and '.incoming' not in str(dst):
                count+=1
                if count==1:reached.set();assert proceed.wait(15)
            return result
        monkeypatch.setattr(module.os,'replace',paused)
        from app.database import claim_next_job
        job=claim_next_job(db)
        action=lambda:main.process_claimed_job(job,library_context=main.MAIN_LIBRARY_CONTEXT)
    else:
        import app.sort_apply as module
        real=module._move_without_overwrite
        def paused(*a,**k):
            nonlocal count
            result=real(*a,**k);count+=1
            if count==1:reached.set();assert proceed.wait(15)
            return result
        monkeypatch.setattr(module,'_move_without_overwrite',paused)
        action=lambda:module.execute_sort_run(db,data['run'],ws)
    t,results=thread_call(action)
    assert reached.wait(15)
    try:
        settings=load_storage_settings();settings['backup_directory_name']='RenamedCentral'
        try:main.api_set_storage_paths(settings);answer={'accepted':True}
        except Exception as e:answer={'accepted':False,'error':repr(e)}
        snapshot(case,ev/'after-rename-before-worker-resume.json')
    finally:proceed.set();t.join(20)
    assert not t.is_alive()
    restarts=end(case,ev,{'order':['background thread first real move','same-process root rename','thread continues'],'rename':answer,'worker':results})
    assert all(r['returncode']==0 for r in restarts),restarts
    if answer['accepted']:assert not old.exists(),'Old root recreated by same-process background thread'
