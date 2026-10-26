"""Two distinct sources: real publication, persistent handoff, no empty history."""
import hashlib,json,shutil,uuid
import pytest
from app import main,sd_recheck as sr
from app.database import database_connection,claim_next_job,get_job
from tests.backend.test_f14_root_operations import fixture
from tests.backend.test_rc1_sd_reimport import setup_live_import,direct_import_lifecycle


def test_two_distinct_sources_overlap_without_empty_import(fixture,monkeypatch):
    case,ws,reg,dbs,photo,context=setup_live_import(fixture,monkeypatch)
    other=photo.parent.with_name('OTHER');other.mkdir();shutil.copy2(photo,other/photo.name)
    monkeypatch.setattr(main,'IMPORT_ROOT',photo.parent.parent)
    requests=[]
    for name in ('CARD','OTHER'):
        requests.append(json.loads(main.api_run_folder_import({'source_root_key':'saved','source_relative_path':name,'source_mode':'folder','request_id':str(uuid.uuid4())}).body))
    # Both parents have been admitted before either publication. Claim both so
    # this also models two worker processes whose verification overlaps.
    first=claim_next_job(dbs[0],operation='sd_recheck');second=claim_next_job(dbs[0],operation='sd_recheck')
    assert first and second and first['id']!=second['id']
    for job in (first,second):main.process_claimed_job(job,library_context=context)
    for _ in range(8):
        job=claim_next_job(dbs[0],operation='folder_import') or claim_next_job(dbs[0],operation='sd_recheck')
        if not job:break
        main.process_claimed_job(job,library_context=context)
    parents=[get_job(dbs[0],r['task_id']) for r in requests]
    assert all(j['state']=='completed' for j in parents),parents
    with database_connection(dbs[0]) as c:
        imports=c.execute("SELECT id,state,file_count,result_json FROM jobs WHERE operation='folder_import'").fetchall()
        assert len(imports)==1,[(r['id'],r['state'],r['file_count']) for r in imports]
        assert imports[0]['state']=='completed' and imports[0]['file_count']==1
        assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok' and not c.execute('PRAGMA foreign_key_check').fetchall()
    assert {j['result']['status'] for j in parents}=={'import_queued','already_backed_up'}
    assert main.api_import_history()['total']==1
    assert hashlib.sha256(photo.read_bytes()).digest()==hashlib.sha256((other/photo.name).read_bytes()).digest()


@pytest.mark.parametrize('action',['cancel','restart','catalog_changed'])
def test_deferred_check_revalidates_and_preserves_source(fixture,monkeypatch,action):
    case,ws,reg,dbs,photo,context=setup_live_import(fixture,monkeypatch)
    other=photo.parent.with_name('OTHER');other.mkdir();shutil.copy2(photo,other/photo.name)
    monkeypatch.setattr(main,'IMPORT_ROOT',photo.parent.parent)
    raw=photo.read_bytes()
    def submit(name):return json.loads(main.api_run_folder_import({'source_root_key':'saved','source_relative_path':name,'source_mode':'folder','request_id':str(uuid.uuid4())}).body)
    submit('CARD');second=submit('OTHER')
    a=claim_next_job(dbs[0],operation='sd_recheck');b=claim_next_job(dbs[0],operation='sd_recheck')
    main.process_claimed_job(a,library_context=context)
    child=claim_next_job(dbs[0],operation='folder_import')
    if action=='catalog_changed':
        # Finish publication after the second check's origin snapshot, before
        # its handoff transaction. The epoch fence must reject that snapshot.
        signature=main.quick_source_signature
        def publish(source):
            main.process_claimed_job(child,library_context=context)
            return signature(source)
        monkeypatch.setattr(main,'quick_source_signature',publish)
    main.process_claimed_job(b,library_context=context)
    waiting=get_job(dbs[0],b['id'])
    assert waiting['state']=='queued' and waiting['stage']=='waiting_for_import',waiting
    if action!='catalog_changed':assert claim_next_job(dbs[0],operation='sd_recheck') is None
    if action=='cancel':
        assert main.api_cancel_import(b['id']).status_code==202
        assert get_job(dbs[0],b['id'])['stage']=='cancelled'
        main.process_claimed_job(child,library_context=context)
        second=submit('OTHER')
    elif action=='restart':
        # Persisted waiting state is queueable after the existing interrupted
        # import is recovered; resume must never cache its previous hashes.
        sr.resume(dbs[0]);assert claim_next_job(dbs[0],operation='sd_recheck') is None
        main.process_claimed_job(child,library_context=context)
    else:monkeypatch.setattr(main,'quick_source_signature',signature)
    job=claim_next_job(dbs[0],operation='sd_recheck');assert job and job['id']==second['task_id']
    hashes=[];actual=sr.folder_manifest
    def fresh(*a,**kw):hashes.append(True);return actual(*a,**kw)
    monkeypatch.setattr(sr,'folder_manifest',fresh)
    main.process_claimed_job(job,library_context=context)
    assert hashes and get_job(dbs[0],job['id'])['result']['status']=='already_backed_up'
    assert main.api_import_history()['total']==1 and photo.read_bytes()==(other/photo.name).read_bytes()==raw
    with database_connection(dbs[0]) as c:
        assert c.execute("SELECT COUNT(*) FROM jobs WHERE operation='folder_import'").fetchone()[0]==1
        assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok' and not c.execute('PRAGMA foreign_key_check').fetchall()


@pytest.mark.parametrize('kill_second',[False,True])
def test_two_real_process_checks_sigkill_and_three_restarts(fixture,monkeypatch,kill_second):
    import subprocess,sys,time,signal
    case,ws,reg,dbs,photo,context=setup_live_import(fixture,monkeypatch)
    other=photo.parent.with_name('OTHER');other.mkdir();shutil.copy2(photo,other/photo.name)
    monkeypatch.setattr(main,'IMPORT_ROOT',photo.parent.parent)
    ids=[]
    for name in ('CARD','OTHER'):ids.append(json.loads(main.api_run_folder_import({'source_root_key':'saved','source_relative_path':name,'source_mode':'folder'}).body)['task_id'])
    (case/'sd-case.json').write_text(json.dumps({'database':str(dbs[0]),'working':str(context.work_root)}))
    evidence=case/'process-overlap';evidence.mkdir();children=[]
    helper=str(__import__('pathlib').Path(__file__).with_name('rc6_handoff_worker.py'))
    try:
        for i in range(2):
            where=evidence/str(i);where.mkdir();log=(where/'log').open('w')
            p=subprocess.Popen([sys.executable,helper,str(case),'operate','overlap',str(where)],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            children.append((p,log,where))
        until=time.monotonic()+20
        while not all((where/'reached').exists() for _,_,where in children):
            assert all(p.poll() is None for p,_,_ in children),[(p.poll(),(w/'log').read_text()) for p,_,w in children]
            assert time.monotonic()<until,'actual source hash/signature barrier not reached'
            time.sleep(.02)
        # Real interruption after both manifests, before either handoff.
        if kill_second:
            os=__import__('os');os.killpg(children[1][0].pid,signal.SIGKILL);assert children[1][0].wait(timeout=10)==-9
        (evidence/'release').write_text('go')
        assert children[0][0].wait(timeout=30)==0,(children[0][2]/'log').read_text()
        if not kill_second:assert children[1][0].wait(timeout=30)==0,(children[1][2]/'log').read_text()
    finally:
        for p,log,_ in children:
            if p.poll() is None:__import__('os').killpg(p.pid,signal.SIGKILL);p.wait()
            log.close()
    for i in range(3):
        where=evidence/('restart'+str(i));where.mkdir()
        r=subprocess.run([sys.executable,helper,str(case),'restart','none',str(where)],capture_output=True,text=True,timeout=45)
        assert r.returncode==0,r.stdout+r.stderr
        (where/'log').write_text(r.stdout+r.stderr)
    # Explicitly schedule remaining queue entries. All processes used the real
    # startup; only background scheduling was suppressed by the adapter.
    for _ in range(6):
        job=claim_next_job(dbs[0],operation='folder_import') or claim_next_job(dbs[0],operation='sd_recheck')
        if not job:break
        main.process_claimed_job(job,library_context=context)
    assert all(get_job(dbs[0],jid)['state']=='completed' for jid in ids)
    assert main.api_import_history()['total']==1
    with database_connection(dbs[0]) as c:
        assert c.execute("SELECT COUNT(*) FROM jobs WHERE operation='folder_import'").fetchone()[0]==1
        assert c.execute('SELECT COUNT(*) FROM files').fetchone()[0]==1
        assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok' and not c.execute('PRAGMA foreign_key_check').fetchall()
    assert photo.read_bytes()==(other/photo.name).read_bytes()
