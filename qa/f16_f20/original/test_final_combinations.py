from pathlib import Path
import threading,json,hashlib
import pytest
from test_interleavings import seed,thread_call
from test_more import start,release,end
from test_process_crashes import snapshot,invoke
from app import main
from app.database import database_connection

@pytest.mark.parametrize('journal_visible',[False,True])
def test_metadata_batches_overlap(tmp_path,monkeypatch,journal_visible):
    case,ev,data,db,ws=seed(tmp_path,'multiple_metadata','P404-metadata-batches-'+str(journal_visible),monkeypatch)
    from app import metadata_correction as mc,metadata_swap_recovery as ms
    real=ms.create_swap_journal;reached=threading.Event();resume=threading.Event();a_ident=[None]
    def create(*a,**kw):
        if threading.get_ident()==a_ident[0]:
            if journal_visible:
                result=real(*a,**kw);reached.set();assert resume.wait(20);return result
            reached.set();assert resume.wait(20)
        return real(*a,**kw)
    monkeypatch.setattr(ms,'create_swap_journal',create)
    def apply_a():
        a_ident[0]=threading.get_ident()
        return mc.apply_multiple_metadata_correction(workspace_root=ws,library_id='main',reference_relative_path='A.JPG',proposed_datetime='2026-10-01T12:34:56',expected_preview_fingerprint=data['preview'])
    t,first=thread_call(apply_a);assert reached.wait(15)
    preview=mc.preview_multiple_metadata_correction(workspace_root=ws,library_id='main',reference_relative_path='A.JPG',proposed_datetime='2026-10-01T12:45:56')
    try:second={'ok':True,'result':mc.apply_multiple_metadata_correction(workspace_root=ws,library_id='main',reference_relative_path='A.JPG',proposed_datetime='2026-10-01T12:45:56',expected_preview_fingerprint=preview['preview_fingerprint'])}
    except Exception as e:second={'ok':False,'error':repr(e)}
    snapshot(case,ev/'second-finished-before-first-resume.json');resume.set();t.join(25);assert not t.is_alive()
    restarts=end(case,ev,{'order':['A prepares all working copies','A pauses '+('after' if journal_visible else 'before')+' journal creation','B corrects same files to newer date','A resumes'],'A':first,'B':second})
    assert all(r['returncode']==0 for r in restarts),restarts
    assert sum(r['ok'] for r in first+[second])==1,(first,second)


def test_parallel_library_plans_and_promotion(tmp_path,monkeypatch):
    case,ev,data,db,ws=seed(tmp_path,'multi','P406-HTTP-secondary-ownership-deterministic',monkeypatch)
    assert invoke(case,'operate','none',ev/'initial-import')['returncode']==0
    from fastapi.testclient import TestClient
    from app.library_context import resolve_library_context
    from app.sort_plan import build_event_sort_plan
    from app.sort_apply import prepare_sort_run,CONFIRMATION_PHRASE
    monkeypatch.setattr(main,'current_database_file',lambda:main.current_library_context().database_path)
    monkeypatch.setattr(main,'CONFIG_PATH',db.parent/'settings.json')
    # Redirect only the hardcoded ephemeral compatibility root into this case.
    monkeypatch.setattr(main,'Path',lambda v:case/'compatibility' if str(v)=='/tmp/bibliothekar-library-workspaces' else Path(v))
    barrier=threading.Barrier(2);real=main.claim_event_families;secondary_done=threading.Event()
    def claim(*a,**kw):
        barrier.wait(timeout=15)
        if kw['library_id']=='main':assert secondary_done.wait(15);return real(*a,**kw)
        try:return real(*a,**kw)
        finally:secondary_done.set()
    monkeypatch.setattr(main,'claim_event_families',claim)
    payload={'event_name':'Parallel','start_date':'2026-10-01','end_date':'2026-10-01','start_time':'00:00','end_time':'23:59','uses_time_range':False,'selected_family_ids':[1,2,3],'confirm_cross_backup_membership':True,'preserve_day_folders':False}
    def request(lid):
        client=TestClient(main.app,headers={'X-Bibliothekar-Library':lid})
        try:
            r=client.post('/api/jobs/J/events',json=payload);return {'library':lid,'status':r.status_code,'body':r.json()}
        finally:client.close()
    a,x=thread_call(lambda:request('main'));b,y=thread_call(lambda:request('second1'));a.join(25);b.join(25)
    assert not a.is_alive() and not b.is_alive();results=x+y
    monkeypatch.setattr(main,'claim_event_families',real)
    snapshot(case,ev/'after-concurrent-plans.json')
    good=[r['value'] for r in results if r['ok'] and r['value']['status']==200]
    if len(good)==1:
        winner=good[0];context=resolve_library_context(main.REGISTRY_DATABASE_FILE,winner['library']);event=winner['body']['parent_event']['id']
        view=main.compatibility_workspace_root(context)
        plan=build_event_sort_plan(context.database_path,'J',event,view)
        run=prepare_sort_run(context.database_path,'J',event,view,expected_plan_token=plan['plan_token'],confirmation_phrase=CONFIRMATION_PHRASE)
        main._sort_run_thread_target(run['id'],context)
    restarts=end(case,ev,{'order':['real shared import projected into three libraries','both HTTP plans commit local event before registry claim barrier','one wins reservation, loser unwinds','winner actual sorting and claim promotion','three startups'],'responses':results})
    assert len(good)==1,results
    assert all(r['ok'] for r in results),results
    assert sorted(r['value']['status'] for r in results)==[200,409],results
    with database_connection(main.REGISTRY_DATABASE_FILE) as c:
        claims=c.execute('SELECT * FROM family_claims').fetchall();assert len(claims)==3
        assert all(r['library_id']==winner['library'] and r['claim_state']=='owned' for r in claims),[dict(r) for r in claims]
    assert all(r['returncode']==0 for r in restarts),restarts


def test_rename_after_ssd_unlink(tmp_path,monkeypatch):
    case,ev,data,db,ws=seed(tmp_path,'ssd','P403-rename-after-SSD-unlink-retry',monkeypatch)
    from app.library_registry import update_library_paths
    from app.storage_config import load_storage_settings
    legacy=ws/'Arbeitsbereich';managed=ws/'Arbeitsbereiche'/'main';managed.parent.mkdir(exist_ok=True);legacy.rename(managed);legacy.symlink_to(managed,target_is_directory=True)
    update_library_paths(main.REGISTRY_DATABASE_FILE,'main',work_root=managed)
    snapshot(case,ev/'before-managed-operation.json')
    child,control,log=start(case,'ssd','ssd.unlink1',ev)
    try:
        settings=load_storage_settings();settings['workspaces_directory_name']='RenamedWork'
        renamed=main.api_set_storage_paths(settings)
        snapshot(case,ev/'after-rename-before-resume.json')
    finally:result=release(child,control,log)
    restarts=end(case,ev,{'order':['first real SSD unlink','rename managed workspaces root','release resumes with old paths','three startups'],'worker':result,'rename':renamed})
    assert all(r['returncode']==0 for r in restarts),restarts
    retry=invoke(case,'retry','none',ev/'explicit-retry');snapshot(case,ev/'after-explicit-retry.json')
    assert retry['returncode']==0,retry
    with database_connection(db) as c:
        rows=c.execute('SELECT * FROM files').fetchall();assert len(rows)==2
        for row in rows:
            archive=case/'archive'/row['current_relative_path'];assert hashlib.sha256(archive.read_bytes()).hexdigest()==row['sha256_current']
        assert c.execute("SELECT COUNT(*) FROM event_ssd_releases WHERE status='completed'").fetchone()[0]==1,'Partial release not resumed after managed rename'
