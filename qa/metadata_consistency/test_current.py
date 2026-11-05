from pathlib import Path
from contextlib import contextmanager
import threading,hashlib,json
import pytest
from test_interleavings import seed,thread_call
from test_more import end
from app import main
from app.database import database_connection
from app.library_context import resolve_library_context

@pytest.mark.parametrize('phase',['active_projection','pending_projection'])
def test_conflict_then_explicit_retry_preserves_newest(tmp_path,monkeypatch,phase):
    case,ev,data,db,ws=seed(tmp_path,'metadata_projection','F15-current-'+phase,monkeypatch)
    from app import metadata_correction as mc,global_stock as gs
    paths=[Path(p) for p in data['databases']];family=mc.get_metadata_correction(db,data['task'])['detected'];reg=db.parent/'registry.sqlite3'
    from app import root_operations as ro
    def reservations():
        return {p.name:p.read_bytes() for p in ro._control_location(ws).glob('operation-*.json')}
    def context(lid):return resolve_library_context(reg,lid)
    def create(path,lid,date='2026-07-21T16:17:18'):
        with database_connection(path) as c:fid=c.execute('SELECT id FROM file_families WHERE job_id=? AND family_key=?',(family['job_id'],family['family_key'])).fetchone()[0]
        return mc.create_metadata_correction(path,area='library',relative_path='Ohne_Datum/IMG_0001.JPG',family_id=fid,proposed_datetime=date,workspace_root=ws,library_id=lid)
    if phase=='active_projection':
        first=mc.apply_metadata_correction(db,data['task'],workspace_root=ws,library_id='main')
        ready=threading.Event();go=threading.Event();real=gs.database_connection;role=[None]
        @contextmanager
        def pause(path):
            if threading.get_ident()==role[0] and Path(path)==paths[1]:ready.set();assert go.wait(20)
            with real(path) as c:yield c
        monkeypatch.setattr(gs,'database_connection',pause)
        def sync():role[0]=threading.get_ident();return main._sync_completed_library_metadata_correction(context('main'),first)
        child,result=thread_call(sync);assert ready.wait(10)
        task=create(db,'main')
        before_rejection=reservations()
        try:
            with pytest.raises(mc.MetadataCorrectionError):mc.apply_metadata_correction(db,task['id'],workspace_root=ws,library_id='main')
            assert reservations()==before_rejection, 'Rejected request created or changed a durable media intent'
            assert hashlib.sha256(Path(first['output_path']).read_bytes()).hexdigest()==first['output_sha256']
        finally:go.set();child.join(20)
        assert not child.is_alive() and result[0]['ok'],result
        monkeypatch.setattr(gs,'database_connection',real)
        target=db;lid='main'
    else:
        # A real correction in library two remains durable but unprojected.
        target=paths[1];lid='second1';first_task=create(target,lid,'2026-07-20T14:15:30')
        first=mc.apply_metadata_correction(target,first_task['id'],workspace_root=ws,library_id=lid)
        other=paths[2];task=create(other,'second2')
        before_rejection=reservations()
        with pytest.raises(mc.MetadataCorrectionError):mc.apply_metadata_correction(other,task['id'],workspace_root=ws,library_id='second2')
        assert reservations()==before_rejection, 'Pending projection rejection changed F14 evidence'
        assert hashlib.sha256(Path(first['output_path']).read_bytes()).hexdigest()==first['output_sha256']
        main._sync_completed_library_metadata_correction(context(lid),first)
        target=other;lid='second2'
    # An explicit retry remains fully functional after the previous projection.
    task=create(target,lid);latest=mc.apply_metadata_correction(target,task['id'],workspace_root=ws,library_id=lid)
    main._sync_completed_library_metadata_correction(context(lid),latest)
    for path in paths:
        with database_connection(path) as c:
            row=c.execute('SELECT sha256_current,selected_capture_time FROM files').fetchone()
            assert row['sha256_current']==latest['output_sha256'] and row['selected_capture_time']=='2026-07-21T16:17:18'
            assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok' and not c.execute('PRAGMA foreign_key_check').fetchall()
    assert hashlib.sha256(Path(latest['output_path']).read_bytes()).hexdigest()==latest['output_sha256']
    restarts=end(case,ev,{'phase':phase,'latest':latest['id'],'sha256':latest['output_sha256']})
    assert all(x['returncode']==0 for x in restarts),restarts
