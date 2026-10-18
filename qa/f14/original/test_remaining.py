from pathlib import Path
import json, threading, hashlib
from contextlib import contextmanager
import pytest
from test_interleavings import seed,thread_call
from test_more import start,release,end
from test_process_crashes import snapshot
from app import main
from app.database import database_connection


def test_delayed_metadata_propagation(tmp_path,monkeypatch):
    case,ev,data,db,ws=seed(tmp_path,'metadata_projection','P406-delayed-metadata',monkeypatch)
    from app import metadata_correction as mc,global_stock as gs
    paths=[Path(p) for p in data['databases']]
    first=mc.apply_metadata_correction(db,data['task'],workspace_root=ws,library_id='main')
    reached=threading.Event();proceed=threading.Event();old_thread=[None];real=gs.database_connection
    @contextmanager
    def delayed(path):
        if threading.current_thread() is old_thread[0] and Path(path)==paths[1]:
            reached.set();assert proceed.wait(30)
        with real(path) as c:yield c
    monkeypatch.setattr(gs,'database_connection',delayed)
    def old():
        old_thread[0]=threading.current_thread()
        return main._sync_completed_library_metadata_correction(main.MAIN_LIBRARY_CONTEXT,first)
    t,older=thread_call(old);assert reached.wait(10)
    # Use the public task creation/apply core with real JPEG and real ExifTool.
    second=mc.create_metadata_correction(db,area='library',relative_path='Ohne_Datum/IMG_0001.JPG',family_id=data['family'],proposed_datetime='2026-07-21T16:17:18',workspace_root=ws,library_id='main')
    second=mc.apply_metadata_correction(db,second['id'],workspace_root=ws,library_id='main')
    newer=main._sync_completed_library_metadata_correction(main.MAIN_LIBRARY_CONTEXT,second)
    snapshot(case,ev/'newer-completed-before-old-write.json')
    proceed.set();t.join(30);assert not t.is_alive()
    restarts=end(case,ev,{'order':['first correction physically completes','old propagation snapshots source and pauses before first target','second correction plus all projections completes','old propagation overwrites targets','three startups'],'old':older,'new':newer})
    assert all(r['returncode']==0 for r in restarts),restarts
    assert older[0]['ok'],older
    observed=[]
    for path in paths:
        with database_connection(path) as c:observed.append(dict(c.execute('SELECT sha256_current,selected_capture_time FROM files').fetchone()))
    (ev/'final-projections.json').write_text(json.dumps(observed,indent=2))
    assert all(row==observed[0] for row in observed),observed


def test_inventory_during_sort(tmp_path,monkeypatch):
    case,ev,data,db,ws=seed(tmp_path,'sort','P407-inventory-sort',monkeypatch)
    from app.central_stock_reconcile import reconcile_central_free_stock
    child,control,log=start(case,'sort','sort.move1',ev)
    try:
        scans=[reconcile_central_free_stock(db,ws,library_id='main') for _ in range(2)]
        snapshot(case,ev/'during-sort-after-two-scans.json')
    finally:result=release(child,control,log)
    restarts=end(case,ev,{'order':['sort first move before catalog commit','two central inventory reconciliations','sort completes','three startups'],'scans':scans,'sort':result})
    assert all(r['returncode']==0 for r in restarts),restarts
    assert all(s['deleted_file_count']==0 for s in scans),scans
    with database_connection(db) as c:assert c.execute('SELECT COUNT(*) FROM files').fetchone()[0]==3


def test_cancel_active_reconcile(tmp_path,monkeypatch):
    case,ev,data,db,ws=seed(tmp_path,'reconcile','P404-cancel-active-reconcile',monkeypatch)
    from app.event_mutation import cancel_mutation
    child,control,log=start(case,'reconcile','reconcile.move1',ev)
    try:
        with database_connection(db) as c:
            mutation=c.execute("SELECT id FROM event_mutations WHERE status IN ('pending_apply','pending_reassignment','manual_archive')").fetchone()
            assert mutation is not None
            c.execute('BEGIN IMMEDIATE')
            with pytest.raises(ValueError,match='aktiven Sortierlaufs') as error:cancel_mutation(c,mutation['id'],data['job'],workspace_path=ws)
        snapshot(case,ev/'rejected-cancel.json')
    finally:result=release(child,control,log)
    restarts=end(case,ev,{'order':['reconcile first move','cancel under actual BEGIN IMMEDIATE','reject active run','reconcile completes'],'error':str(error.value),'reconcile':result})
    assert result['status']=='ok',result
    assert all(r['returncode']==0 for r in restarts),restarts


def test_duplicate_reconcile_prepare(tmp_path,monkeypatch):
    case,ev,data,db,ws=seed(tmp_path,'reconcile','P404-duplicate-reconcile-verified',monkeypatch)
    from app import workspace_reconcile as wr
    with database_connection(db) as c:c.execute("UPDATE sort_runs SET status='rolled_back' WHERE id=?",(data['run'],))
    barrier=threading.Barrier(2);real=wr.build_workspace_reconcile_plan
    def plan(*a,**kw):
        result=real(*a,**kw);barrier.wait(timeout=10);return result
    monkeypatch.setattr(wr,'build_workspace_reconcile_plan',plan)
    def prepare():return wr.prepare_workspace_reconcile_run(db,data['job'],data['event'],ws,expected_plan_token=data['plan']['plan_token'],confirmation_phrase=wr.CONFIRMATION_PHRASE)
    a,x=thread_call(prepare);b,y=thread_call(prepare);a.join(15);b.join(15)
    assert not a.is_alive() and not b.is_alive()
    monkeypatch.setattr(wr,'build_workspace_reconcile_plan',real)
    results=x+y
    restarts=end(case,ev,{'order':['both prepare fresh same plan','barrier before BEGIN IMMEDIATE','competing insert active run'],'results':results})
    assert sum(r['ok'] for r in results)==1,results
    assert all(r['returncode']==0 for r in restarts),restarts

@pytest.mark.parametrize('kind,boundary,setting',[('reconcile','reconcile.move1','workspaces_directory_name'),('ssd','ssd.archive_verified','workspaces_directory_name')])
def test_rename_remaining_workers(tmp_path,monkeypatch,kind,boundary,setting):
    case,ev,data,db,ws=seed(tmp_path,kind,'P403-managed-rename-'+kind+('-final' if kind=='ssd' else ''),monkeypatch)
    from app.storage_config import load_storage_settings
    from app.library_registry import update_library_paths
    legacy=ws/'Arbeitsbereich';managed=ws/'Arbeitsbereiche'/'main'
    managed.parent.mkdir(exist_ok=True);legacy.rename(managed);legacy.symlink_to(managed,target_is_directory=True)
    update_library_paths(db.parent/'registry.sqlite3','main',work_root=managed)
    if kind=='reconcile':
        from app.workspace_reconcile import build_workspace_reconcile_plan
        plan=build_workspace_reconcile_plan(db,data['job'],data['event'],ws)
        assert plan['summary']['ready'],plan
        with database_connection(db) as c:
            c.execute('UPDATE sort_runs SET source_root=?,target_root=?,plan_token=? WHERE id=?',(str(managed),str(managed),plan['plan_token'],data['run']))
        data['plan']=plan;(case/'case.json').write_text(json.dumps(data))
    snapshot(case,ev/'before-managed-operation.json')
    child,control,log=start(case,kind,boundary,ev)
    old=ws/load_storage_settings()[setting]
    try:
        settings=load_storage_settings();settings[setting]='RenamedWork'
        try:main.api_set_storage_paths(settings);answer={'accepted':True}
        except Exception as e:answer={'accepted':False,'error':repr(e)}
        snapshot(case,ev/'after-rename-before-resume.json')
    finally:result=release(child,control,log)
    restarts=end(case,ev,{'order':['worker first file operation','rename work root','worker resumes','three startups'],'rename':answer,'worker':result})
    assert all(r['returncode']==0 for r in restarts),restarts
    if answer['accepted']:
        assert not old.exists(),'Worker recreated old root'
        if kind=='ssd':
            assert result['status']=='error' and 'SsdReleaseError' in result['error'],result
            # Safe refusal is permitted: preserve every SSD source and independently matching archive.
            with database_connection(db) as c:
                rows=c.execute('SELECT * FROM files').fetchall();assert len(rows)==2
                assert c.execute("SELECT COUNT(*) FROM event_ssd_releases WHERE status='completed'").fetchone()[0]==0
                for row in rows:
                    for root in (ws/'RenamedWork'/'main',case/'archive'):
                        path=root/row['current_relative_path']
                        assert hashlib.sha256(path.read_bytes()).hexdigest()==row['sha256_current']
        else:assert result['status']=='ok',result
