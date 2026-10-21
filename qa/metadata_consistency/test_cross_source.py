from pathlib import Path
from contextlib import contextmanager
import threading,hashlib,json
from test_interleavings import seed,thread_call
from test_more import end
from app.database import database_connection

def test_cross_library_projection_order(tmp_path,monkeypatch):
    case,ev,data,db,ws=seed(tmp_path,'metadata_projection','F15-cross-library-source',monkeypatch)
    from app import metadata_correction as mc,global_stock as gs
    paths=[Path(p) for p in data['databases']];a,b,c=paths
    main_task=mc.get_metadata_correction(a,data['task']);family=main_task['detected'];job=family['job_id'];key=family['family_key']
    def apply(path,lid,date):
        with database_connection(path) as conn:fid=conn.execute('SELECT id FROM file_families WHERE job_id=? AND family_key=?',(job,key)).fetchone()[0]
        task=mc.create_metadata_correction(path,area='library',relative_path='Ohne_Datum/IMG_0001.JPG',family_id=fid,proposed_datetime=date,workspace_root=ws,library_id=lid)
        return mc.apply_metadata_correction(path,task['id'],workspace_root=ws,library_id=lid)
    first=apply(b,'second1','2026-07-20T14:15:30')
    gs.propagate_corrected_family(b,[c],job_id=job,family_key=key)
    old_wait=threading.Event();old_go=threading.Event();new_wait=threading.Event();new_go=threading.Event();roles={};real=gs.database_connection
    @contextmanager
    def paused(path):
        role=roles.get(threading.get_ident())
        if role=='old' and Path(path)==a:old_wait.set();assert old_go.wait(20)
        if role=='new' and Path(path)==b:new_wait.set();assert new_go.wait(20)
        with real(path) as conn:yield conn
    monkeypatch.setattr(gs,'database_connection',paused)
    def propagate(role,path):
        roles[threading.get_ident()]=role
        return gs.propagate_corrected_family(path,paths,job_id=job,family_key=key)
    old,old_result=thread_call(lambda:propagate('old',b));assert old_wait.wait(10)
    second=apply(c,'second2','2026-07-21T16:17:18');expected=second['output_sha256']
    new,new_result=thread_call(lambda:propagate('new',c));assert new_wait.wait(10)
    try:
        old_go.set();old.join(15);assert not old.is_alive()
    finally:new_go.set();new.join(15)
    assert not new.is_alive() and old_result[0]['ok'] and new_result[0]['ok'],(old_result,new_result)
    monkeypatch.setattr(gs,'database_connection',real)
    observed=[]
    for path in paths:
        with database_connection(path) as conn:observed.append(dict(conn.execute('SELECT sha256_current,selected_capture_time FROM files').fetchone()))
    restarts=end(case,ev,{'old':old_result,'new':new_result,'expected':expected,'observed':observed})
    assert all(x['returncode']==0 for x in restarts),restarts
    assert all(row['sha256_current']==expected and row['selected_capture_time']=='2026-07-21T16:17:18' for row in observed),observed
