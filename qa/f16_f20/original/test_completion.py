from pathlib import Path
import threading,hashlib,json
import pytest
from test_interleavings import seed,thread_call
from test_more import start,release,end
from test_process_crashes import snapshot,invoke
from app import main
from app.database import database_connection

@pytest.mark.parametrize('operation',['full','selective'])
def test_delete_during_restore(tmp_path,monkeypatch,operation):
    case,ev,data,db,ws=seed(tmp_path,'restore','P401-live-restore-'+operation,monkeypatch)
    child,control,log=start(case,'restore','restore.move1',ev)
    try:
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as error:
            if operation=='full':main.api_empty_trash({'confirmation':main.TRASH_CONFIRMATION})
            else:main.api_empty_trash_selection({'relative_paths':['B.JPG']})
        assert error.value.status_code==409
        snapshot(case,ev/'rejected-while-restore-active.json')
    finally:result=release(child,control,log)
    restarts=end(case,ev,{'order':['real restore first move','delete still-reserved B requested','409 rejection','restore resumes'],'restore':result})
    assert result['status']=='ok'
    for digest in data['expected'].values():assert any(hashlib.sha256(p.read_bytes()).hexdigest()==digest for p in ws.rglob('*.JPG'))
    assert all(r['returncode']==0 for r in restarts)


def test_restore_waits_for_selective_delete(tmp_path,monkeypatch):
    case,ev,data,db,ws=seed(tmp_path,'trash','P401-restore-after-active-delete-verified',monkeypatch)
    child,control,log=start(case,'trash','trash.stage1',ev)
    import fcntl
    real=fcntl.flock;entered=threading.Event()
    def flock(fd,op):
        if op==fcntl.LOCK_EX:entered.set()
        return real(fd,op)
    monkeypatch.setattr(fcntl,'flock',flock)
    t,result=thread_call(lambda:main.api_restore_trash({'relative_paths':['A.JPG']}))
    attempted_lock=entered.wait(1)
    deleted=release(child,control,log);t.join(15);assert not t.is_alive()
    restarts=end(case,ev,{'order':['real deletion stages A with process lock','restore directly reconciles catalogue without operation lock','deletion attempts commit and rollback','restore rejects absent A'],'lock_attempt_observed':attempted_lock,'delete':deleted,'restore':result})
    assert deleted['status']=='ok' and not result[0]['ok'],(deleted,result)
    assert not list((ws/'Papierkorb').rglob('*.JPG'))
    assert all(r['returncode']==0 for r in restarts)

@pytest.mark.parametrize('kind,boundary',[('import','import.move1'),('reconcile','reconcile.move1')])
def test_inventory_other_moves(tmp_path,monkeypatch,kind,boundary):
    case,ev,data,db,ws=seed(tmp_path,kind,'P407-inventory-'+kind+'-final',monkeypatch)
    child,control,log=start(case,kind,boundary,ev)
    try:
        scans=[main.reconcile_global_central_stock_state(force=True) for _ in range(2)]
        snapshot(case,ev/'during-worker-after-scans.json')
    finally:result=release(child,control,log)
    restarts=end(case,ev,{'order':['first move','two actual central reconciliation calls','worker resumes'],'scans':scans,'worker':result})
    assert result['status']=='ok',result
    with database_connection(db) as c:assert c.execute('SELECT COUNT(*) FROM files').fetchone()[0]==3
    assert all(r['returncode']==0 for r in restarts)


def test_inventory_during_ssd_release(tmp_path,monkeypatch):
    case,ev,data,db,ws=seed(tmp_path,'ssd','P407-inventory-ssd-final',monkeypatch)
    from app.event_inventory import scan_event_inventory
    child,control,log=start(case,'ssd','ssd.unlink1',ev)
    try:
        scans=[scan_event_inventory(db,ws/'Arbeitsbereich',data['job'],data['event'],root_kind='shared_workspace',persist=True,update_known_file_locations=True) for _ in range(2)]
        snapshot(case,ev/'during-release-after-scans.json')
    finally:result=release(child,control,log)
    restarts=end(case,ev,{'order':['first SSD file unlinked','two event inventory scans persist intermediate state','release continues'],'scans':scans,'release':result})
    assert result['status']=='ok',result
    with database_connection(db) as c:
        rows=c.execute('SELECT * FROM files').fetchall();assert len(rows)==2
        for row in rows:assert hashlib.sha256((case/'archive'/row['current_relative_path']).read_bytes()).hexdigest()==row['sha256_current']
    assert all(r['returncode']==0 for r in restarts)


def test_duplicate_metadata_work_race(tmp_path,monkeypatch):
    case,ev,data,db,ws=seed(tmp_path,'library_metadata','P408-duplicate-metadata-work',monkeypatch)
    from app import metadata_correction as mc
    read_a=threading.Event();read_b=threading.Event();staged=threading.Event();resume_a=threading.Event()
    actual_get=mc.get_metadata_correction;actual_write=mc.write_metadata_datetime;seen=set();roles={}
    def get(*a,**kw):
        value=actual_get(*a,**kw);role=roles.get(threading.get_ident())
        if role and role not in seen:
            seen.add(role)
            if role=='A':read_a.set();assert read_b.wait(10)
            else:assert read_a.wait(10);read_b.set();assert staged.wait(10)
        return value
    def write(*a,**kw):
        if roles.get(threading.get_ident())=='A':staged.set();assert resume_a.wait(20)
        return actual_write(*a,**kw)
    monkeypatch.setattr(mc,'get_metadata_correction',get);monkeypatch.setattr(mc,'write_metadata_datetime',write)
    def apply(role):
        roles[threading.get_ident()]=role
        return mc.apply_metadata_correction(db,data['task'],workspace_root=ws,library_id='main')
    a,x=thread_call(lambda:apply('A'));assert read_a.wait(10)
    b,y=thread_call(lambda:apply('B'));b.join(20);assert not b.is_alive()
    snapshot(case,ev/'second-finished-first-still-staged.json');resume_a.set();a.join(20);assert not a.is_alive()
    monkeypatch.setattr(mc,'get_metadata_correction',actual_get)
    restarts=end(case,ev,{'order':['both read prepared task','A copies task-specific work and pauses','B reuses same work directory and completes','A resumes after B cleanup'],'A':x,'B':y})
    final=actual_get(db,data['task']);(ev/'final-task.json').write_text(json.dumps(final,indent=2))
    assert all(r['returncode']==0 for r in restarts)
    assert any(r['ok'] for r in x+y),x+y
    assert final['status']=='completed',final


def test_writing_metadata_request_rejected(tmp_path,monkeypatch):
    case,ev,data,db,ws=seed(tmp_path,'library_metadata','P408-writing-metadata-rejected',monkeypatch)
    from app import metadata_correction as mc
    real=mc.write_metadata_datetime;reached=threading.Event();resume=threading.Event()
    def write(*a,**kw):reached.set();assert resume.wait(15);return real(*a,**kw)
    monkeypatch.setattr(mc,'write_metadata_datetime',write)
    t,result=thread_call(lambda:mc.apply_metadata_correction(db,data['task'],workspace_root=ws,library_id='main'))
    assert reached.wait(10)
    with pytest.raises(mc.MetadataCorrectionError):mc.apply_metadata_correction(db,data['task'],workspace_root=ws,library_id='main')
    snapshot(case,ev/'second-rejected.json');resume.set();t.join(20);assert not t.is_alive()
    restarts=end(case,ev,{'order':['first task writing','second request observes writing and rejects','first completes'],'first':result})
    assert result[0]['ok'] and mc.get_metadata_correction(db,data['task'])['status']=='completed'
    assert all(r['returncode']==0 for r in restarts)
