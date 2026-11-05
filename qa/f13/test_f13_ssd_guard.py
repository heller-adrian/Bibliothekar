"""B tests inject no notifications explicitly. Native tests require Linux.

No production toggle selects the B model. Residual data-loss assertions live
in qa/f13 and intentionally remain red, outside the normal regression suite.
"""
import hashlib
import os
from pathlib import Path
import struct
import subprocess
import sys
import time

import pytest
from app import ssd_archive_guard as guard


class RehashOnly:
    count = 0
    def watch(self, fd, children=None): pass
    def check(self): pass
    def close(self): pass


@pytest.fixture
def b_only(monkeypatch):
    monkeypatch.setattr(guard, 'InotifyWatcher', RehashOnly)


def media(tmp_path):
    root = (tmp_path / 'archive').resolve()
    root.mkdir()
    p = root / 'event' / 'A.JPG'
    p.parent.mkdir()
    raw = b'synthetic-original' * 100
    p.write_bytes(raw)
    return root, p, raw, hashlib.sha256(raw).hexdigest()


def test_B_descriptor_hash_and_metrics(tmp_path, b_only):
    root, p, raw, digest = media(tmp_path)
    g = guard.ArchiveGuard(root, ['event/A.JPG'])
    try:
        g.verify('event/A.JPG', len(raw), digest)
        assert g.metrics()['archive_rehash_bytes'] == len(raw)
        assert g.metrics()['archive_rehash_seconds'] >= 0
    finally: g.close()


@pytest.mark.parametrize('change', ['overwrite', 'replace', 'delete', 'rename', 'hardlink', 'symlink_parent'])
def test_B_changes_block(tmp_path, b_only, change):
    root, p, raw, digest = media(tmp_path)
    g = guard.ArchiveGuard(root, ['event/A.JPG'])
    try:
        if change == 'overwrite': p.write_bytes(b'X' * len(raw))
        elif change == 'replace':
            q = root / 'replacement'; q.write_bytes(raw); os.replace(q, p)
        elif change == 'delete': p.unlink()
        elif change == 'rename': p.rename(root / 'moved')
        elif change == 'hardlink': os.link(p, root / 'alias')
        else:
            (root/'event').rename(root/'old'); (root/'event').symlink_to(root/'old', target_is_directory=True)
        with pytest.raises(guard.ArchiveConflict): g.verify('event/A.JPG', len(raw), digest)
    finally: g.close()


def test_B_same_inode_not_independent(tmp_path, b_only):
    root, p, raw, digest = media(tmp_path)
    g = guard.ArchiveGuard(root, ['event/A.JPG'])
    try:
        with pytest.raises(guard.ArchiveConflict, match='unabhängig'):
            g.verify('event/A.JPG', len(raw), digest, p.stat())
    finally: g.close()


def test_B_writer_during_hash(tmp_path, b_only, monkeypatch):
    root, p, raw, digest = media(tmp_path)
    g = guard.ArchiveGuard(root, ['event/A.JPG'])
    read = os.read
    done = False
    def change(fd, count):
        nonlocal done
        block = read(fd, count)
        if block and not done:
            done = True
            p.write_bytes(b'Z' * len(raw))
        return block
    monkeypatch.setattr(guard.os, 'read', change)
    try:
        with pytest.raises(guard.ArchiveConflict): g.verify('event/A.JPG', len(raw), digest)
    finally: g.close()


@pytest.mark.parametrize('mask', [0x4000, 0x8000, 0x2000])
def test_C_event_loss_latches(mask):
    w = object.__new__(guard.InotifyWatcher)
    w.scopes = {1: None}
    with pytest.raises(guard.ArchiveConflict):
        w._consume(struct.pack('iIII', -1 if mask == 0x4000 else 1, mask, 0, 0))


def test_C_malformed_event():
    w = object.__new__(guard.InotifyWatcher); w.scopes = {1: None}
    with pytest.raises(guard.ArchiveConflict): w._consume(b'x')


def test_C_error_persists_and_no_fallback(monkeypatch):
    w = object.__new__(guard.InotifyWatcher); w.fd = -1; w.error = None; w.scopes = {}
    def fail(*args): raise OSError('synthetic reader failure')
    monkeypatch.setattr(guard.os, 'read', fail)
    with pytest.raises(guard.ArchiveConflict): w.check()
    assert w.error
    with pytest.raises(guard.ArchiveConflict): w.check()


@pytest.mark.parametrize('err', [PermissionError('EACCES'), OSError(28, 'ENOSPC'), OSError(24, 'EMFILE')])
def test_C_watch_install_failure_closes(tmp_path, monkeypatch, err):
    root, p, raw, digest = media(tmp_path)
    closed = []
    class Failure(RehashOnly):
        def watch(self, *args): raise err
        def close(self): closed.append(True)
    monkeypatch.setattr(guard, 'InotifyWatcher', Failure)
    with pytest.raises(OSError): guard.ArchiveGuard(root, ['event/A.JPG'])
    assert closed and p.read_bytes() == raw


@pytest.mark.parametrize('change', ['old_writer', 'replace', 'rename', 'unlink', 'hardlink_alias'])
def test_C_native_external_process(tmp_path, change):
    assert sys.platform == 'linux', 'BLOCKED: actual Linux-inotify test requires Linux'
    root, p, raw, digest = media(tmp_path)
    # Writer opens before watches exist, and keeps the descriptor open until
    # after the parent's check. This tests MODIFY, not a CLOSE_WRITE shortcut.
    script = '''import os,sys
p=sys.argv[1];action=sys.argv[2]
f=open(p,'r+b');print('opened',flush=True);sys.stdin.readline()
if action=='old_writer': f.write(b'X');f.flush();os.fsync(f.fileno())
elif action=='replace':
 q=p+'.new';open(q,'wb').write(b'new');os.replace(q,p)
elif action=='rename': os.rename(p,p+'.moved')
elif action=='unlink': os.unlink(p)
else:
 q=p+'.alias';os.link(p,q);open(q,'r+b').write(b'X')
print('changed',flush=True);sys.stdin.readline();f.close()
'''
    process = subprocess.Popen([sys.executable,'-c',script,str(p),change], stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
    g = None
    try:
        assert process.stdout.readline().strip() == 'opened'
        g = guard.ArchiveGuard(root, ['event/A.JPG'])
        process.stdin.write('\n'); process.stdin.flush()
        assert process.stdout.readline().strip() == 'changed'
        with pytest.raises(guard.ArchiveConflict): g.check()
        with pytest.raises(guard.ArchiveConflict): g.check()
    finally:
        if g: g.close()
        process.communicate('\n', timeout=10)
        assert process.returncode == 0


def test_C_native_unrelated_activity_and_no_fd_leak(tmp_path):
    assert sys.platform == 'linux', 'BLOCKED: Linux required'
    root, p, raw, digest = media(tmp_path)
    initial = len(os.listdir('/proc/self/fd'))
    for _ in range(3):
        g = guard.ArchiveGuard(root, ['event/A.JPG'])
        try:
            (tmp_path/'unrelated').write_text('unrelated')
            g.verify('event/A.JPG', len(raw), digest)
            assert g.metrics()['watch_count'] >= 2
        finally: g.close()
    assert len(os.listdir('/proc/self/fd')) == initial


def test_recovery_pauses_and_explicit_enqueue_is_new(tmp_path):
    from tests.backend.test_0476_archive_recovery_and_release import _seed
    from app.database import database_connection
    from app.ssd_release_background import enqueue_release, claim_release, recover_releases, get_release_task
    db, workspace, archive, folder, old_family, new_family, _ = _seed(tmp_path)
    with database_connection(db) as c: c.execute("UPDATE events SET status='applied',archived_at=NULL WHERE id='archive'")
    first = enqueue_release(db, 'old', 'archive')
    assert claim_release(db)['id'] == first['id']
    assert recover_releases(db) == 1
    assert claim_release(db) is None
    state = get_release_task(db,'old','archive')
    assert state['status'] == 'failed' and 'Keine automatische' in state['error_message']
    assert recover_releases(db) == 0
    second = enqueue_release(db,'old','archive')
    assert second['id'] != first['id']


def release_fixture(tmp_path):
    from app.database import initialize_database, database_connection
    from tests.backend.test_0263_event_inventory import seed_job, seed_event, seed_family, seed_file_for_family
    db = tmp_path/'db.sqlite3'; initialize_database(db)
    ws = tmp_path/'workspace'; archive = tmp_path/'archive'
    # Complete the historical synthetic installation before the operation.
    for name in ['SD-Kartensicherungen', 'Arbeitsbereiche', 'Metadatenkorrektur', 'Papierkorb']:
        (ws / name).mkdir(parents=True, exist_ok=True)
    rel = '2026/07-23 - Trip/Alle/'
    with database_connection(db) as c:
        seed_job(c); seed_event(c,status='applied')
        fid, _ = seed_family(c,content=b'synthetic-A',current_path=rel+'A.JPG')
        seed_file_for_family(c,family_id=fid,content=b'synthetic-B',current_path=rel+'B.JPG',filename='B.JPG')
        c.execute("UPDATE files SET current_root_kind='shared_workspace'")
    for name in ['A.JPG','B.JPG']:
        for root in [ws/'Arbeitsbereich',archive]:
            p=root/rel/name; p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(('synthetic-'+name[0]).encode())
    return db,ws,archive,rel


def test_B_worker_change_before_last_hash_preserves_source(tmp_path, b_only, monkeypatch):
    from app.ssd_release import release_event_ssd, SsdReleaseError
    db,ws,archive,rel=release_fixture(tmp_path)
    real=guard.ArchiveGuard.verify; calls=0
    def changed(self,*args,**kwargs):
        nonlocal calls
        calls+=1
        if calls==3: (archive/rel/'A.JPG').write_bytes(b'X'*11)
        return real(self,*args,**kwargs)
    monkeypatch.setattr(guard.ArchiveGuard,'verify',changed)
    with pytest.raises(SsdReleaseError):release_event_ssd(db,ws,archive,'j','e')
    assert (ws/'Arbeitsbereich'/rel/'A.JPG').read_bytes()==b'synthetic-A'
    assert (ws/'Arbeitsbereich'/rel/'B.JPG').read_bytes()==b'synthetic-B'


@pytest.mark.parametrize('persist_failure',[False,True])
def test_C_native_partial_release_stops_next_file(tmp_path,monkeypatch,persist_failure):
    assert sys.platform=='linux','BLOCKED: native Linux required'
    from app import ssd_release
    from app.database import database_connection
    import sqlite3
    db,ws,archive,rel=release_fixture(tmp_path)
    src=ws/'Arbeitsbereich'/rel/'A.JPG';real=Path.unlink
    def changed(path,*args,**kwargs):
        value=real(path,*args,**kwargs)
        if path==src: (archive/rel/'A.JPG').write_bytes(b'X'*11)
        return value
    monkeypatch.setattr(Path,'unlink',changed)
    if persist_failure:
        def failed(*args):raise sqlite3.OperationalError('synthetic write failure')
        monkeypatch.setattr(ssd_release,'_mark_release_failed',failed)
    with pytest.raises((ssd_release.SsdReleaseError,sqlite3.OperationalError)):
        ssd_release.release_event_ssd(db,ws,archive,'j','e')
    assert not src.exists()
    assert (ws/'Arbeitsbereich'/rel/'B.JPG').read_bytes()==b'synthetic-B'
    with database_connection(db) as c:
        assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        if not persist_failure:
            row=c.execute('SELECT status,deleted_file_count,error_message FROM event_ssd_releases').fetchone()
            assert row['status']=='failed' and row['deleted_file_count']==1
            assert 'nicht wiederhergestellt' in row['error_message']


def test_C_native_real_queue_overflow(tmp_path):
    assert sys.platform=='linux','BLOCKED: real Linux queue required'
    limit=int(Path('/proc/sys/fs/inotify/max_queued_events').read_text())
    assert limit<=32768,'BLOCKED: no unbounded overflow load permitted'
    a=tmp_path/'a'; b=tmp_path/'b';a.write_bytes(b'a');b.write_bytes(b'b')
    fds=[os.open(p,os.O_RDWR) for p in [a,b]]
    w=guard.InotifyWatcher();overflow=None
    try:
        for fd in fds:w.watch(fd)
        for i in range(limit+8):os.pwrite(fds[i%2],b'X',0)
        while True:
            try:data=os.read(w.fd,65536)
            except BlockingIOError:break
            pos=0
            while pos<len(data):
                wd,mask,cookie,length=struct.unpack_from('iIII',data,pos)
                size=16+length
                if mask&0x4000:overflow=data[pos:pos+size]
                pos+=size
        assert overflow is not None,'Real kernel overflow was not observed'
        with pytest.raises(guard.ArchiveConflict,match='Queueüberlauf'):w._consume(overflow)
    finally:
        w.close()
        for fd in fds:os.close(fd)


def test_B_source_disappearing_after_verification_is_not_already_released(tmp_path,b_only,monkeypatch):
    from app import ssd_release
    from app.database import database_connection
    db,ws,archive,rel=release_fixture(tmp_path)
    real=database_connection;fired=False
    from contextlib import contextmanager
    @contextmanager
    def boundary(path):
        nonlocal fired
        with real(path) as c:
            yield c
        with real(path) as c:
            row=c.execute("SELECT 1 FROM event_ssd_releases WHERE status='deleting'").fetchone()
        if row and not fired:
            fired=True
            (ws/'Arbeitsbereich'/rel/'A.JPG').rename(ws/'moved-A.JPG')
    monkeypatch.setattr(ssd_release,'database_connection',boundary)
    with pytest.raises(ssd_release.SsdReleaseError,match='unerwartet verschwunden'):
        ssd_release.release_event_ssd(db,ws,archive,'j','e')
    assert (ws/'moved-A.JPG').read_bytes()==b'synthetic-A'
    assert (ws/'Arbeitsbereich'/rel/'B.JPG').read_bytes()==b'synthetic-B'


def test_C_native_worker_change_before_last_hash(tmp_path,monkeypatch):
    assert sys.platform=='linux','BLOCKED: native Linux required'
    # Same unchanged conservation assertions as B, using real inotify.
    test_B_worker_change_before_last_hash_preserves_source(tmp_path,None,monkeypatch)


def test_C_native_sigkill_conflict_and_recovery_commits(tmp_path):
    assert sys.platform=='linux','BLOCKED: actual Linux/inotify/SIGKILL required'
    import signal
    from app.database import database_connection
    from app.ssd_release_background import recover_releases,claim_release,enqueue_release,process_release,get_release_task
    db,ws,archive,rel=release_fixture(tmp_path)
    with database_connection(db) as c:
        c.execute("CREATE TRIGGER synthetic_failure BEFORE UPDATE ON event_ssd_releases WHEN NEW.status='failed' BEGIN SELECT RAISE(ABORT, 'synthetic audit persistence failure'); END")
    script=tmp_path/'crash_probe.py'
    script.write_text('''import os,signal,sys,sqlite3
from pathlib import Path
from contextlib import contextmanager
from app import ssd_release as sr,ssd_release_background as bg
from app.database import database_connection
db,ws,archive=map(Path,sys.argv[1:4]);mode=sys.argv[4];marker=Path(sys.argv[5])
def stop():
 marker.write_text(str(os.getpid()));os.kill(os.getpid(),signal.SIGSTOP)
 raise RuntimeError('unexpected resume')
if mode=='conflict':
 task=bg.enqueue_release(db,'j','e');task=bg.claim_release(db)
 real=Path.unlink
 def changed(p,*a,**k):
  result=real(p,*a,**k)
  if p.name=='A.JPG':(archive/'2026/07-23 - Trip/Alle/A.JPG').write_bytes(b'X'*11)
  return result
 Path.unlink=changed
 # A simulated DB-write failure reaches the durable task's still-running
 # boundary; kill before background's error completion can be recorded.
 real_failed=sr._mark_release_failed
 def failed(*a):
  try:real_failed(*a)
  except sqlite3.Error:stop()
 sr._mark_release_failed=failed
 bg.process_release(db,ws,archive,task)
else:
 @contextmanager
 def commit_then_stop(path):
  with database_connection(path) as c:yield c
  stop()
 bg.database_connection=commit_then_stop
 bg.recover_releases(db)
''')
    executions=[]
    for index,mode in enumerate(['conflict','recovery','recovery']):
        marker=tmp_path/f'marker{index}'
        p=subprocess.Popen([sys.executable,str(script),str(db),str(ws),str(archive),mode,str(marker)],start_new_session=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        deadline=time.monotonic()+15
        try:
            while not marker.exists() and p.poll() is None and time.monotonic()<deadline:time.sleep(.01)
            assert marker.exists(),p.communicate(timeout=1)
            os.killpg(p.pid,signal.SIGKILL);p.communicate(timeout=5)
            assert p.returncode==-signal.SIGKILL
            executions.append({'mode':mode,'pid':p.pid,'returncode':p.returncode})
        finally:
            if p.poll() is None:os.killpg(p.pid,signal.SIGKILL);p.wait(timeout=5)
    assert recover_releases(db)==0 and claim_release(db) is None
    assert get_release_task(db,'j','e')['status']=='failed'
    assert not (ws/'Arbeitsbereich'/rel/'A.JPG').exists()
    assert (ws/'Arbeitsbereich'/rel/'B.JPG').read_bytes()==b'synthetic-B'
    explicit=enqueue_release(db,'j','e');task=claim_release(db)
    assert task['id']==explicit['id']
    process_release(db,ws,archive,task)
    assert get_release_task(db,'j','e')['status']=='failed'
    assert (ws/'Arbeitsbereich'/rel/'B.JPG').read_bytes()==b'synthetic-B'
    with database_connection(db) as c:assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    import json
    (tmp_path/'sigkill-conflict-evidence.json').write_text(json.dumps(executions))


def test_C_native_change_during_finalization_is_not_success(tmp_path,monkeypatch):
    assert sys.platform=='linux','BLOCKED: native Linux required'
    from app import ssd_release
    from app.database import database_connection
    db,ws,archive,rel=release_fixture(tmp_path)
    real=ssd_release._finalize_release
    def interleave(*args,**kwargs):
        result=real(*args,**kwargs)
        (archive/rel/'A.JPG').write_bytes(b'X'*11)
        return result
    monkeypatch.setattr(ssd_release,'_finalize_release',interleave)
    with pytest.raises(ssd_release.SsdReleaseError):ssd_release.release_event_ssd(db,ws,archive,'j','e')
    assert not (ws/'Arbeitsbereich'/rel/'A.JPG').exists()
    with database_connection(db) as c:
        row=c.execute('SELECT status,deleted_file_count FROM event_ssd_releases').fetchone()
        assert row['status']=='failed' and row['deleted_file_count']==2
