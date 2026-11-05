from pathlib import Path
import threading,hashlib,subprocess
from test_interleavings import seed,thread_call
from test_more import end
from test_process_crashes import snapshot
from app import main
from app.database import database_connection,create_job


def test_import_restore_same_target_queue(tmp_path,monkeypatch):
    case,ev,data,db,ws=seed(tmp_path,'trash','P402-import-restore-identical-goal-verified',monkeypatch)
    from PIL import Image
    from app import folder_import as fi
    with database_connection(db) as c:date=c.execute("SELECT selected_capture_time FROM files WHERE original_filename='A.JPG'").fetchone()[0]
    from datetime import datetime
    collision=datetime.fromisoformat(date).strftime('%Y%m%d_%H%M%S')+'_Unbekanntes-Gerät.JPG'
    (ws/'Papierkorb/A.JPG').rename(ws/'Papierkorb'/collision)
    for raw in data['databases']:
        with database_connection(Path(raw)) as c:c.execute("UPDATE files SET current_relative_path=? WHERE current_root_kind='trash' AND current_relative_path='A.JPG'",(collision,))
    snapshot(case,ev/'before-identical-goal-fixture.json')
    card=case/'card';photo=card/'A.JPG';Image.new('RGB',(16,16),(20,40,60)).save(photo)
    subprocess.run(['exiftool','-overwrite_original','-DateTimeOriginal='+date.replace('-',':',2).replace('T',' '),str(photo)],check=True,capture_output=True)
    digest=hashlib.sha256(photo.read_bytes()).hexdigest()
    create_job(db,job_id='I',kind='sd_import',trigger_type='approved_sd',operation='folder_import',source_path=str(card))
    restore=main.api_restore_trash({'relative_paths':[collision]});jid=restore['job_id']
    monkeypatch.setattr(main,'CONFIG_PATH',db.parent/'settings.json')
    stop=threading.Event();monkeypatch.setattr(main,'WORKER_STOP',stop)
    reached=threading.Event();resume=threading.Event();real=fi.os.replace;once=[True]
    def move(s,d):
        value=real(s,d)
        if once[0] and '/Original/' in str(s) and '.incoming' not in str(d):once[0]=False;reached.set();assert resume.wait(15)
        return value
    monkeypatch.setattr(fi.os,'replace',move)
    actual=main.process_claimed_job;trace=[]
    def process(job,**kw):
        trace.append(job['id'])
        try:return actual(job,**kw)
        finally:
            if job['id']==jid:stop.set()
    monkeypatch.setattr(main,'process_claimed_job',process)
    t,result=thread_call(main.worker_loop);assert reached.wait(15)
    with database_connection(db) as c:queued=c.execute('SELECT state FROM jobs WHERE id=?',(jid,)).fetchone()[0]
    snapshot(case,ev/'import-published-restore-queued.json');resume.set();t.join(30)
    if t.is_alive():stop.set();t.join(5)
    assert not t.is_alive()
    restarts=end(case,ev,{'order':['known trash A reserved','folder import with different A bytes and same capture date queued','actual worker prioritizes import, pauses after publication','restore remains queued','restore sees existing foreign destination and rejects'],'execution':trace,'queued_state':queued,'worker':result})
    assert trace==['I',jid] and queued=='queued',trace
    assert (ws/'Papierkorb'/collision).read_bytes()==b'synthetic-trash-A.JPG'
    with database_connection(db) as c:
        row=c.execute("SELECT current_relative_path FROM files WHERE job_id='I'").fetchone();assert row is not None
        assert hashlib.sha256((ws/'SD-Kartensicherungen'/row[0]).read_bytes()).hexdigest()==digest
        assert c.execute("SELECT state FROM jobs WHERE id='I'").fetchone()[0]=='completed'
        assert c.execute('SELECT state FROM jobs WHERE id=?',(jid,)).fetchone()[0]=='failed'
    assert all(r['returncode']==0 for r in restarts),restarts
