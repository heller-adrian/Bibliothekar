"""Deterministic metadata coordination; historical assertions remain unchanged."""
from pathlib import Path
import os,signal,subprocess,sys,time,json
import pytest
from app.metadata_swap_recovery import metadata_write_guard,MetadataSwapRecoveryError,recover_metadata_swaps
from app.metadata_correction import _mark_task_writing,MetadataCorrectionError
from app.database import database_connection
from tests.backend.test_0562_process_recovery import isolated_process_environment

@pytest.mark.parametrize('case',['f15_active','f15_pending','f17_current','f18_false','f18_true'])
def test_metadata_safety_contract(tmp_path,case):
    source=Path(__file__).resolve().parents[2];out=tmp_path/case
    result=subprocess.run([sys.executable,str(source/'qa/metadata_consistency/run_original.py'),str(source),str(out),case],timeout=80)
    assert result.returncode==0,(out/'stdout.log').read_text()[-5000:]

@pytest.mark.parametrize('kill',[False,True])
def test_process_writer_and_recovery_exclusion_then_reacquire(tmp_path,kill):
    root=tmp_path/'metadata';root.mkdir();(root/'.swap-journals').mkdir()
    original=root/'synthetic-original';original.write_bytes(b'unchanged-original')
    code="""from pathlib import Path
import sys,time
from app.metadata_swap_recovery import metadata_write_guard
root=Path(sys.argv[1])
with metadata_write_guard(root):
 (root/'ready').write_text('held')
 while not (root/'release').exists():time.sleep(.01)
"""
    child=subprocess.Popen([sys.executable,'-c',code,str(root)])
    try:
        deadline=time.monotonic()+10
        while not (root/'ready').exists() and child.poll() is None and time.monotonic()<deadline:time.sleep(.01)
        assert (root/'ready').is_file()
        with pytest.raises(MetadataSwapRecoveryError):
            with metadata_write_guard(root):pytest.fail('Concurrent writer admitted')
        with pytest.raises(MetadataSwapRecoveryError):recover_metadata_swaps(root)
        assert original.read_bytes()==b'unchanged-original' and not list((root/'.swap-journals').iterdir())
        if kill:child.send_signal(signal.SIGKILL)
        else:(root/'release').write_text('release')
        assert child.wait(timeout=5)==(-signal.SIGKILL if kill else 0)
        for _ in range(3):
            result=subprocess.run([sys.executable,'-c',"from pathlib import Path;import sys;from app.metadata_swap_recovery import recover_metadata_swaps;assert recover_metadata_swaps(Path(sys.argv[1]))['blocked']==0",str(root)],timeout=10)
            assert result.returncode==0 and original.read_bytes()==b'unchanged-original'
    finally:
        if child.poll() is None:child.kill();child.wait(timeout=5)


def test_independent_metadata_areas_remain_usable(tmp_path):
    a=tmp_path/'a';b=tmp_path/'b';a.mkdir();b.mkdir()
    with metadata_write_guard(a):
        with metadata_write_guard(b):pass


def test_task_claim_is_atomic_without_changing_completed_or_writing(tmp_path):
    db=tmp_path/'claims.sqlite3'
    with database_connection(db) as c:
        c.execute('CREATE TABLE metadata_corrections(id TEXT PRIMARY KEY,status TEXT,updated_at TEXT,error_message TEXT)')
        c.execute("INSERT INTO metadata_corrections VALUES('T','prepared',NULL,NULL)")
    _mark_task_writing(db,'T')
    with pytest.raises(MetadataCorrectionError):_mark_task_writing(db,'T')
    with database_connection(db) as c:
        assert c.execute("SELECT status FROM metadata_corrections").fetchone()[0]=='writing'
        c.execute("UPDATE metadata_corrections SET status='completed'")
    with pytest.raises(MetadataCorrectionError):_mark_task_writing(db,'T')
    with database_connection(db) as c:assert c.execute("SELECT status FROM metadata_corrections").fetchone()[0]=='completed'


@pytest.mark.parametrize('journal_visible',[False,True])
def test_rejected_batch_does_not_orphan_the_active_writer(tmp_path,monkeypatch,journal_visible):
    """Real batch/ExifTool calls: rejected B must not poison A's SQL/F14 fence."""
    import threading
    from tests.backend.test_0562_process_recovery import invoke
    from app import metadata_correction as mc,metadata_swap_recovery as ms,root_operations as ro
    case=tmp_path/'case';case.mkdir();evidence=tmp_path/'admission-evidence'
    seeded=invoke(case,'seed','multiple_metadata',evidence/'seed')
    assert seeded['returncode']==0,(evidence/'seed/process.log').read_text()
    data=json.loads((case/'case.json').read_text());ws=Path(data['workspace'])
    monkeypatch.setenv('KAMERA_WORKSPACE',str(ws))
    monkeypatch.setenv('KAMERA_CONFIG',str(case/'settings.json'))
    monkeypatch.setenv('KAMERA_REGISTRY_DATABASE',str(case/'registry.sqlite3'))
    real=ms.create_swap_journal;ready=threading.Event();resume=threading.Event();outcomes=[]
    def pause(*a,**kw):
        result=real(*a,**kw) if journal_visible else None
        ready.set()
        assert resume.wait(20)
        return result if journal_visible else real(*a,**kw)
    monkeypatch.setattr(ms,'create_swap_journal',pause)
    arguments=dict(workspace_root=ws,library_id='main',reference_relative_path='A.JPG',
                   proposed_datetime='2026-10-01T12:34:56',expected_preview_fingerprint=data['preview'])
    def writer():
        try:outcomes.append(mc.apply_multiple_metadata_correction(**arguments))
        except BaseException as error:outcomes.append(error)
    first=threading.Thread(target=writer);first.start()
    try:
        assert ready.wait(15)
        parent=ro._control_location(ws)
        before={p.name:p.read_bytes() for p in parent.glob('operation-*.json')}
        assert len(before)==1
        with pytest.raises(mc.MetadataCorrectionError):mc.apply_multiple_metadata_correction(**arguments)
        assert {p.name:p.read_bytes() for p in parent.glob('operation-*.json')}==before
    finally:
        resume.set();first.join(25)
    assert not first.is_alive() and len(outcomes)==1 and not isinstance(outcomes[0],BaseException),outcomes
    assert not list(parent.glob('operation-*.json'))
    from app.storage_config import storage_paths
    metadata_root=storage_paths(ws)['metadata_root']
    assert not list((metadata_root/'.swap-journals').glob('*.json'))
    batch_root=mc.metadata_area_paths(area='multiple',workspace_root=ws,library_id='main',create=False)['root']
    for filename in ('A.JPG','B.JPG'):
        assert mc.verify_metadata_datetime(batch_root/filename,
                                           '2026-10-01T12:34:56')['matching_tags']
    for number in (1,2):
        restarted=invoke(case,'startup','none',evidence/('restart'+str(number)))
        assert restarted['returncode']==0,restarted
