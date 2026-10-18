"""Approved O2 fail-closed boundary; no mock is used as isolation evidence."""
from contextlib import closing
from pathlib import Path
import fcntl,hashlib,json,os,signal,sqlite3,subprocess,sys,time
import pytest
from app import main,root_operations as ro
from app.library_registry import get_library,update_library_paths
from app.library_context import resolve_library_context
from app.storage_config import load_storage_settings,storage_paths
from tests.backend.test_f14_root_operations import fixture,snapshot as _raw_snapshot,settings_change


def snapshot(case,path):
    # The inherited reader enumerates files before its SQLite connections open.
    # Warm those readers first, so WAL/SHM created by observation are included
    # in BOTH snapshots. Keep the full byte/inode/row assertion unchanged.
    _raw_snapshot(case,path.with_name(path.stem+'-reader-warmup.json'))
    result=_raw_snapshot(case,path)
    result['directories']={str(p.relative_to(case)):{'device':p.lstat().st_dev,'inode':p.lstat().st_ino,'mode':p.lstat().st_mode} for p in [case,*case.rglob('*')] if not p.is_symlink() and p.is_dir()}
    path.write_text(json.dumps(result,indent=2))
    # SQLite may recreate its own empty WAL/shared-memory coordination files
    # when another process closes a registry reader. Raw snapshots retain their
    # inodes; compare their bytes as well, but not those ephemeral inode numbers.
    # All database, evidence, original and foreign-entry inodes stay asserted.
    comparison=json.loads(json.dumps(result))
    for item in comparison['files']:
        if item['path'].endswith(('.sqlite3-shm','.sqlite3-wal')):item['inode']='sqlite-owned-ephemeral'
    return comparison


@pytest.mark.parametrize('key',list(load_storage_settings()))
@pytest.mark.parametrize('entry',['api','helper'])
def test_f14_o2_unattested_physical_rename_has_no_effect(fixture,key,entry):
    case,ws,reg,dbs,ev=fixture
    before=snapshot(case,ev/'before.json');generation=ro.generation(ws,'main')
    call=main.api_set_storage_paths if entry=='api' else main._set_storage_paths
    for attempt in range(3):
        with pytest.raises(main.HTTPException) as error:call({key:'RequestedNewRoot'})
        assert error.value.status_code==410
        assert 'nicht mehr änderbar' in error.value.detail
        assert snapshot(case,ev/f'after-{attempt}.json')==before
    assert ro.generation(ws,'main')==generation
    assert not list(ro._control_location(ws).glob('*.json'))


def test_f14_o2_noop_and_manual_image_edits_remain_possible(fixture):
    case,ws,reg,dbs,ev=fixture
    before=load_storage_settings()
    with pytest.raises(main.HTTPException) as error:main.api_set_storage_paths(before)
    assert error.value.status_code==410
    assert load_storage_settings()==before
    ctx=resolve_library_context(reg,'main')
    with ro.reserve(ws,library_id='main',paths=[ctx.work_root],database=dbs[0]):
        image=ctx.work_root/'original.JPG';image.write_bytes(b'synthetic-manual-edit')
        child=ctx.work_root/'manual-subfolder';child.mkdir();image.rename(child/'edited.JPG')
        ro.validate_active_roots()
    assert (child/'edited.JPG').read_bytes()==b'synthetic-manual-edit'
    assert load_storage_settings()==before
    snapshot(case,ev/'manual-edit.json')


def run_worker(case,ev,action):
    env=dict(os.environ,KAMERA_CONFIG=str(case/'settings.json'),KAMERA_REGISTRY_DATABASE=str(case/'registry.sqlite3'))
    control=ev/action;control.mkdir()
    log=(control/'process.log').open('w')
    p=subprocess.Popen([sys.executable,str(Path(__file__).with_name('f14_o2_worker.py')),str(case),str(control),action],env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    deadline=time.monotonic()+15
    while time.monotonic()<deadline and p.poll() is None:
        if (control/'checkpoint.json').exists():return p,control,log
        time.sleep(.01)
    if p.poll() is None:os.killpg(p.pid,signal.SIGKILL);p.wait()
    log.close();raise AssertionError((control/'process.log').read_text())


@pytest.mark.parametrize('replacement',['source-dir','source-symlink','parent-dir','target-dir','target-symlink'])
def test_f14_o2_external_same_uid_replacement_never_mutates_foreign_entry(fixture,replacement):
    case,ws,reg,dbs,ev=fixture
    p,control,log=run_worker(case,ev,'before-denial')
    try:
        # A real independent process exchanges the entries after API preflight.
        result=subprocess.run([sys.executable,str(Path(__file__).with_name('f14_o2_worker.py')),str(case),str(control),replacement],capture_output=True,text=True,timeout=15,env=dict(os.environ,KAMERA_CONFIG=str(case/'settings.json'),KAMERA_REGISTRY_DATABASE=str(reg)))
        assert result.returncode==0,result.stdout+result.stderr
        evidence=json.loads((control/'external.json').read_text());assert evidence['uid']==os.geteuid()
        before=snapshot(case,ev/'after-external-before-app.json')
        os.kill(p.pid,signal.SIGCONT);assert p.wait(timeout=15)==0
        assert snapshot(case,ev/'after-app.json')==before
        answer=json.loads((control/'answer.json').read_text());assert answer['status']==410
        assert not any(q.name=='mutation.json' for q in case.rglob('*.json'))
        assert (case/'external/original.JPG').read_bytes()==b'synthetic-foreign'
    finally:
        if p.poll() is None:os.killpg(p.pid,signal.SIGKILL);p.wait()
        log.close()


@pytest.mark.parametrize('boundary',['before-denial','after-denial'])
def test_f14_o2_sigkill_and_three_real_lifecycle_starts_preserve_state(fixture,boundary,monkeypatch):
    from tests.backend import test_0562_process_recovery as recovery
    case,ws,reg,dbs,ev=fixture;before=snapshot(case,ev/'before-kill.json')
    p,control,log=run_worker(case,ev,boundary)
    try:
        os.killpg(p.pid,signal.SIGKILL);assert p.wait(timeout=15)==-9
    finally:log.close()
    assert snapshot(case,ev/'after-kill.json')==before
    assert not list(ro._control_location(ws).glob('*.json'))
    for key,value in dict(AUDIT_SCRATCH=str(case.parent),AUDIT_SOURCE=str(Path(__file__).resolve().parents[2]),AUDIT_OUTPUT=str(ev),AUDIT_LABEL='f14-o2-lifecycle').items():monkeypatch.setenv(key,value)
    for restart in range(3):
        result=recovery.invoke(case,'startup','none',ev/f'start-{restart}')
        assert result['returncode']==0,result
        data=snapshot(case,ev/f'after-start-{restart}.json')
        assert all(db['integrity']=='ok' and not db['foreign_keys'] for db in data['databases'].values())
        for lid in ('main','second'):
            image=storage_paths(ws)['workspaces_root']/lid/'original.JPG'
            assert image.read_bytes()==b'synthetic-'+lid.encode()
        assert load_storage_settings()['workspaces_directory_name']=='Arbeitsbereiche'
        assert not (ro._control_location(ws)/'mutation.json').exists()
        with pytest.raises(main.HTTPException) as error:main.api_set_storage_paths(settings_change())
        assert error.value.status_code==410


def test_f14_o2_mode_0700_flock_and_open_directory_fd_do_not_bind_source_name(fixture):
    case,ws,reg,dbs,ev=fixture;source=ws/'Arbeitsbereiche';retained=ws/'verified-source';target='new-name'
    os.chmod(ws,0o700)  # Synthetic test permission only, never product behavior.
    parent_fd=os.open(ws,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    source_fd=os.open('Arbeitsbereiche',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=parent_fd)
    lock=os.open(ws/'.synthetic-lock',os.O_CREAT|os.O_RDWR,0o600)
    try:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);verified=os.fstat(source_fd)
        script="import os,sys;from pathlib import Path;p=Path(sys.argv[1]);(p/'Arbeitsbereiche').rename(p/'verified-source');(p/'Arbeitsbereiche').mkdir();(p/'Arbeitsbereiche/foreign.JPG').write_bytes(b'synthetic-foreign');print(os.geteuid())"
        result=subprocess.run([sys.executable,'-c',script,str(ws)],capture_output=True,text=True,timeout=15)
        assert result.returncode==0,result.stderr
        assert int(result.stdout)==os.geteuid()
        observed=os.stat('Arbeitsbereiche',dir_fd=parent_fd,follow_symlinks=False)
        assert (verified.st_dev,verified.st_ino)!=(observed.st_dev,observed.st_ino)
        # Destination is absent, so a no-replace flag would not reject this
        # source exchange. This is a controlled OS primitive probe, not the app.
        os.rename('Arbeitsbereiche',target,src_dir_fd=parent_fd,dst_dir_fd=parent_fd)
        assert (ws/target/'foreign.JPG').read_bytes()==b'synthetic-foreign'
        assert os.fstat(source_fd).st_ino==verified.st_ino
        assert (retained/'main/original.JPG').read_bytes()==b'synthetic-main'
        (ev/'primitive-proof.json').write_text(json.dumps({'same_uid':os.geteuid(),'mode':oct(ws.stat().st_mode&0o777),'verified_inode':verified.st_ino,'renamed_inode':(ws/target).stat().st_ino,'held_source_inode':os.fstat(source_fd).st_ino,'foreign_sha256':hashlib.sha256((ws/target/'foreign.JPG').read_bytes()).hexdigest(),'platform':sys.platform,'linux_renameat2_executed':False},indent=2))
    finally:os.close(lock);os.close(source_fd);os.close(parent_fd)
