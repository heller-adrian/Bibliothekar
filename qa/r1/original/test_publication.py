from pathlib import Path
import hashlib,threading,shutil
from test_interleavings import seed,thread_call
from test_more import end
from test_process_crashes import snapshot
from app import main
from app.database import database_connection,create_job


def test_restore_atomic_destination_collision(tmp_path,monkeypatch):
    case,ev,data,db,ws=seed(tmp_path,'trash','P402-restore-publication-collision',monkeypatch)
    from app import trash_restore as tr
    real=tr.os.link;reached=threading.Event();proceed=threading.Event();target=[]
    def link(source,destination,*a,**kw):
        if Path(source)==ws/'Papierkorb/A.JPG':
            target.append(Path(destination));reached.set();assert proceed.wait(10)
        return real(source,destination,*a,**kw)
    monkeypatch.setattr(tr.os,'link',link)
    def restore():return tr.restore_trash_files([Path(p) for p in data['databases']],ws,relative_paths=['A.JPG'])
    t,result=thread_call(restore);assert reached.wait(10)
    foreign=b'synthetic-foreign-target';target[0].write_bytes(foreign)
    snapshot(case,ev/'foreign-before-link.json');proceed.set();t.join(10);assert not t.is_alive()
    restarts=end(case,ev,{'order':['real restore plans target and journals','barrier before atomic link','other writer publishes foreign target','link rejects existing target','three startups'],'result':result,'target':str(target[0])})
    assert not result[0]['ok'],result
    assert target[0].read_bytes()==foreign
    assert (ws/'Papierkorb/A.JPG').read_bytes()==b'synthetic-trash-A.JPG'
    for path in data['databases']:
        with database_connection(Path(path)) as c:
            row=c.execute("SELECT current_relative_path,current_root_kind FROM files WHERE original_filename='A.JPG'").fetchone()
            assert row is not None and row['current_relative_path']=='A.JPG' and row['current_root_kind']=='trash',row
    assert all(r['returncode']==0 for r in restarts),restarts


def test_one_worker_serializes_two_imports(tmp_path,monkeypatch):
    case,ev,data,db,ws=seed(tmp_path,'import','P402-two-imports-one-worker',monkeypatch)
    from app import folder_import as fi
    second=case/'card2';shutil.copytree(case/'card',second)
    for path in second.iterdir():
        with path.open('ab') as f:f.write(b'synthetic-distinct-second-import')
    create_job(db,job_id='J2',kind='sd_import',trigger_type='approved_sd',operation='folder_import',source_path=str(second))
    monkeypatch.setattr(main,'CONFIG_PATH',db.parent/'settings.json')
    stop=threading.Event();monkeypatch.setattr(main,'WORKER_STOP',stop)
    reached=threading.Event();proceed=threading.Event();replaced=fi.os.replace;first=[True]
    def move(s,d):
        result=replaced(s,d)
        if first[0] and '/Original/' in str(s) and '.incoming' not in str(d):
            first[0]=False;reached.set();assert proceed.wait(20)
        return result
    monkeypatch.setattr(fi.os,'replace',move)
    actual=main.process_claimed_job;trace=[]
    def process(job,**kw):
        trace.append({'job':job['id'],'step':'start'})
        try:return actual(job,**kw)
        finally:
            trace.append({'job':job['id'],'step':'end'})
            if job['id']=='J2':stop.set()
    monkeypatch.setattr(main,'process_claimed_job',process)
    t,result=thread_call(main.worker_loop);assert reached.wait(20)
    with database_connection(db) as c:queued=c.execute("SELECT state FROM jobs WHERE id='J2'").fetchone()[0]
    snapshot(case,ev/'first-moving-second-queued.json');proceed.set();t.join(45)
    if t.is_alive():stop.set();t.join(5)
    assert not t.is_alive()
    restarts=end(case,ev,{'order':['both real imports queued with same filenames and different bytes','one real worker loop first import paused during move','second remains queued','first ends then second runs'],'queue_state':queued,'worker':result,'execution':trace})
    assert queued=='queued' and [r['job']+r['step'] for r in trace]==['Jstart','Jend','J2start','J2end'],trace
    with database_connection(db) as c:
        states={r['id']:r['state'] for r in c.execute("SELECT id,state FROM jobs WHERE id IN ('J','J2')")}
        assert states=={'J':'completed','J2':'completed'},states
        rows=c.execute('SELECT * FROM files').fetchall();assert len(rows)==6
        for row in rows:
            path=ws/'SD-Kartensicherungen'/row['current_relative_path']
            assert hashlib.sha256(path.read_bytes()).hexdigest()==row['sha256_current']
    assert all(r['returncode']==0 for r in restarts),restarts
