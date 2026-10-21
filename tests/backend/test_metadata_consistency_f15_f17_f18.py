"""Deterministic metadata coordination; historical assertions remain unchanged."""
from pathlib import Path
import os,signal,subprocess,sys,time,json
import pytest
from app.metadata_swap_recovery import metadata_write_guard,MetadataSwapRecoveryError,recover_metadata_swaps
from app.metadata_correction import _mark_task_writing,MetadataCorrectionError
from app.database import database_connection
from tests.backend.test_0562_process_recovery import isolated_process_environment

@pytest.mark.parametrize('case',['f15_current','f17_current','f18_false','f18_true'])
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
