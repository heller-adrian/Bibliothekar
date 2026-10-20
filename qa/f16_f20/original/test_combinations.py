from pathlib import Path
import json,threading,hashlib
from test_interleavings import seed,thread_call
from test_more import start,release,end
from test_process_crashes import invoke,snapshot
from app import main
from app.database import database_connection


def test_public_inventory_during_sort(tmp_path,monkeypatch):
    case,ev,data,db,ws=seed(tmp_path,'sort','P407-public-inventory-sort-verified',monkeypatch)
    from app.global_library_inventory import backfill_library_inventory,backfill_library_claims
    backfill_library_inventory(main.REGISTRY_DATABASE_FILE,database_path=db,library_id='main',claim_all_owned=False)
    backfill_library_claims(main.REGISTRY_DATABASE_FILE,database_path=db,library_id='main')
    child,control,log=start(case,'sort','sort.move1',ev)
    try:
        scans=[main.reconcile_global_central_stock_state(force=True) for _ in range(2)]
        snapshot(case,ev/'after-two-public-reconciliations.json')
    finally:result=release(child,control,log)
    restarts=end(case,ev,{'order':['real sort first move','two actual public central reconciliations with blocked-family filtering','sort continues'],'scans':scans,'worker':result})
    assert all(r['returncode']==0 for r in restarts),restarts
    with database_connection(db) as c:assert c.execute('SELECT COUNT(*) FROM files').fetchone()[0]==3,scans
    assert all(s['libraries']['main'].get('ready') and s['libraries']['main']['deleted_file_count']==0 for s in scans),scans


def test_two_library_http_contexts(tmp_path,monkeypatch):
    case,ev,data,db,ws=seed(tmp_path,'metadata_projection','P408-library-HTTP-contexts-verified',monkeypatch)
    from fastapi.testclient import TestClient
    monkeypatch.setattr(main,'current_database_file',lambda:main.current_library_context().database_path)
    barrier=threading.Barrier(2);real=main.request_library_context
    def read(request):
        barrier.wait(timeout=10)
        context=real(request)
        assert main.current_database_file()==context.database_path
        return context
    monkeypatch.setattr(main,'request_library_context',read)
    def request(lid):
        client=TestClient(main.app,headers={'X-Bibliothekar-Library':lid})
        try:
            response=client.get('/api/libraries/current')
            return {'library':lid,'status':response.status_code,'body':response.json()}
        finally:client.close()
    a,x=thread_call(lambda:request('main'));b,y=thread_call(lambda:request('second1'));a.join(15);b.join(15)
    assert not a.is_alive() and not b.is_alive()
    monkeypatch.setattr(main,'request_library_context',real)
    results=x+y
    restarts=end(case,ev,{'order':['separate sessions select different headers','barrier inside actual current-library route','context and database accessor remain request-local'],'responses':results})
    assert all(r['ok'] and r['value']['status']==200 and r['value']['body']['library_id']==r['value']['library'] for r in results),results
    assert all(r['returncode']==0 for r in restarts),restarts


def test_duplicate_reapply_prepare(tmp_path,monkeypatch):
    case,ev,data,db,ws=seed(tmp_path,'sort','P404-duplicate-reapply',monkeypatch)
    assert invoke(case,'operate','none',ev/'initial-sort')['returncode']==0
    with database_connection(db) as c:c.execute('UPDATE events SET resort_required=1 WHERE id=?',(data['event'],))
    from app import event_reapply as er
    plan=er.build_event_sort_plan(db,data['job'],data['event'],ws,verify_sha256=False,allow_reapply=True)
    assert plan['summary']['ready'],plan['blockers']
    real=er.build_event_sort_plan;barrier=threading.Barrier(2)
    def build(*a,**kw):
        p=real(*a,**kw);barrier.wait(timeout=10);return p
    monkeypatch.setattr(er,'build_event_sort_plan',build)
    def prepare():return er.prepare_reapply_sort_run(db,data['job'],data['event'],ws,expected_plan_token=plan['plan_token'],confirmation_phrase=er.CONFIRMATION_PHRASE)
    a,x=thread_call(prepare);b,y=thread_call(prepare);a.join(15);b.join(15)
    assert not a.is_alive() and not b.is_alive()
    monkeypatch.setattr(er,'build_event_sort_plan',real)
    restarts=end(case,ev,{'order':['event fully applied','two same reapply plans built','barrier before BEGIN IMMEDIATE','one run queued and second rejected'],'results':x+y})
    assert sum(r['ok'] for r in x+y)==1,x+y
    assert all(r['returncode']==0 for r in restarts),restarts


def test_overlapping_apply_batches(tmp_path,monkeypatch):
    case,ev,data,db,ws=seed(tmp_path,'sort','P404-overlapping-batches',monkeypatch)
    from app import operation_batches as ob
    with database_connection(db) as c:c.execute("UPDATE sort_runs SET status='rolled_back' WHERE id=?",(data['run'],))
    item={'job_id':data['job'],'event_id':data['event'],'plan_token':data['plan']['plan_token']}
    batches=[ob.create_apply_batch(db,[item],confirmation_phrase=ob.CONFIRMATION_PHRASE) for _ in range(2)]
    barrier=threading.Barrier(2);real=ob.prepare_sort_run
    def prepare(*a,**kw):barrier.wait(timeout=10);return real(*a,**kw)
    monkeypatch.setattr(ob,'prepare_sort_run',prepare)
    a,x=thread_call(lambda:ob.execute_apply_batch(db,batches[0]['id'],ws));b,y=thread_call(lambda:ob.execute_apply_batch(db,batches[1]['id'],ws));a.join(20);b.join(20)
    assert not a.is_alive() and not b.is_alive()
    restarts=end(case,ev,{'order':['two batches select identical event','barrier at sort prepare','competing transactions and actual file moves'],'results':x+y})
    assert sum(r['ok'] for r in x+y)==1,x+y
    with database_connection(db) as c:
        assert sorted(r[0] for r in c.execute('SELECT status FROM operation_batches'))==['applied','failed']
        assert c.execute("SELECT COUNT(*) FROM sort_runs WHERE status='applied'").fetchone()[0]==1
        rows=c.execute('SELECT * FROM files').fetchall();assert len(rows)==3
        for r in rows:
            p=ws/'Arbeitsbereich'/r['current_relative_path']
            assert hashlib.sha256(p.read_bytes()).hexdigest()==r['sha256_current']
    assert all(r['returncode']==0 for r in restarts),restarts
