"""Open F14 counterexample; expected availability assertion is intentionally strict."""
import hashlib
import pytest
from app import backup_management as module,root_operations as ro
from app.database import get_job,database_connection
from tests.backend.test_0500_backup_delete_recovery import _seed
from tests.backend.test_f14_root_operations import snapshot


def test_f14_verified_backup_rollback_should_allow_later_root_change(tmp_path,monkeypatch):
    db,registry,root,original,family=_seed(tmp_path)
    expected=hashlib.sha256(original.read_bytes()).hexdigest();inode=original.stat().st_ino
    def fail(*args):raise RuntimeError('synthetic main-commit failure')
    with monkeypatch.context() as fault:
        fault.setattr(module,'_delete_job_row',fail)
        with pytest.raises(module.BackupDeletionError):module.delete_backup(db,registry,root,'IMPORT_0400')
    assert module.recover_backup_deletions(db,registry,root)['blocked']==0
    assert hashlib.sha256(original.read_bytes()).hexdigest()==expected and original.stat().st_ino==inode
    assert get_job(db,'IMPORT_0400')['state']=='completed'
    with database_connection(db) as connection:
        assert connection.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert not connection.execute('PRAGMA foreign_key_check').fetchall()
    snapshot(tmp_path,tmp_path/'preserved-proof.json')
    # A safely rolled-back deletion must not force the owner to delete it again
    # merely to regain the ability to change a root. No warning/XFAIL is used.
    with ro.mutate(root.parent,databases=[db]):pass


@pytest.mark.parametrize('boundary',['before-receipt','receipt','journal-removed'])
def test_f14_backup_rollback_receipt_survives_real_sigkill(tmp_path,monkeypatch,boundary):
    import json,os,signal,subprocess,sys,time
    from pathlib import Path
    from tests.backend import test_0562_process_recovery as recovery
    db,registry,root,original,family=_seed(tmp_path)
    monkeypatch.setenv('KAMERA_REGISTRY_DATABASE',str(registry))
    monkeypatch.setenv('KAMERA_CONFIG',str(tmp_path/'settings.json'))
    ev=tmp_path/'completion-evidence';ev.mkdir()
    expected=hashlib.sha256(original.read_bytes()).hexdigest();inode=original.stat().st_ino
    data={'db':str(db),'registry':str(registry),'central':str(root),'job':'IMPORT_0400'}
    (tmp_path/'backup-case.json').write_text(json.dumps(data))
    (tmp_path/'case.json').write_text(json.dumps({**data,'workspace':str(root.parent),'kind':'trash','databases':[str(db)],'expected':{'source':expected}}))
    snapshot(tmp_path,ev/'before.json')
    def child(action,point,label,kill):
        control=ev/label;control.mkdir()
        worker=Path(__file__).with_name('f14_backup_worker.py')
        with (control/'process.log').open('w') as log:
            p=subprocess.Popen([sys.executable,str(worker),str(tmp_path),str(control),action,point],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            try:
                if kill:
                    deadline=time.monotonic()+15
                    while not (control/'checkpoint.json').exists():
                        assert p.poll() is None,(control/'process.log').read_text()
                        assert time.monotonic()<deadline;time.sleep(.01)
                    assert json.loads((control/'checkpoint.json').read_text())['pid']==p.pid
                    os.killpg(p.pid,signal.SIGKILL)
                p.wait(timeout=15);assert p.returncode==(-9 if kill else 0),(control/'process.log').read_text()
                (control/'exit.json').write_text(json.dumps({'pid':p.pid,'code':p.returncode}))
            finally:
                if p.poll() is None:os.killpg(p.pid,signal.SIGKILL);p.wait()
    child('delete',boundary,'first-kill',True)
    snapshot(tmp_path,ev/'after-first-kill.json')
    if boundary!='journal-removed':
        # Recovery itself is interrupted a second time at its durable receipt.
        child('recover','receipt','recovery-kill',True)
        with pytest.raises(ro.RootOperationError):
            with ro.mutate(root.parent,databases=[db]):pytest.fail('journal still present')
    child('recover','none','completed-recovery',False)
    for n in range(3):
        started=recovery.invoke(tmp_path,'startup','none',ev/('application-start-'+str(n)))
        assert started['returncode']==0,started
        assert not started.get('result',{}).get('error'),started
        assert hashlib.sha256(original.read_bytes()).hexdigest()==expected and original.stat().st_ino==inode
        assert get_job(db,'IMPORT_0400')['state']=='completed'
        state=snapshot(tmp_path,ev/('after-start-'+str(n)+'.json'))
        for database in state['databases'].values():assert database['integrity']=='ok' and not database['foreign_keys']
    with ro.mutate(root.parent,databases=[db]):pass
    assert hashlib.sha256(original.read_bytes()).hexdigest()==expected
