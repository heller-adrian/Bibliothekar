"""Actual archive copy in another process against library root rebinding."""
from pathlib import Path
import hashlib,json,os,signal,subprocess,sys,time
import pytest
from app import library_registry as registry,root_operations as ro
from app.database import database_connection
from app.event_change_apply import cancel_event_change
from app.library_context import resolve_library_context
from app.archive_release_stock import describe_archive_release_stock
from tests.backend.test_0271_archive_release_stock import _release_case
from tests.backend.test_f14_root_operations import snapshot


@pytest.mark.parametrize('replace_archive',[False,True])
def test_f14_archive_copy_process_reserves_current_root_until_completion(tmp_path,monkeypatch,replace_archive):
    config=tmp_path/'settings.json';config.write_text('{}');reg=tmp_path/'registry.sqlite3'
    monkeypatch.setenv('KAMERA_CONFIG',str(config));monkeypatch.setenv('KAMERA_REGISTRY_DATABASE',str(reg))
    # The inherited archive fixture stores literal German catalogue paths.
    from app.storage_config import LEGACY_STORAGE_DEFAULTS
    for name in LEGACY_STORAGE_DEFAULTS.values():
        (tmp_path/'workspace'/name).mkdir(parents=True,exist_ok=True)
    monkeypatch.setenv('KAMERA_WORKSPACE',str(tmp_path/'workspace'))
    case=_release_case(tmp_path);db,ws,archive=case['db'],case['workspace'],case['archive']
    registry.initialize_library_registry(reg);registry.ensure_library_identity(db,'main')
    registry.register_library(reg,library_id='main',display_name='Synthetic Archive',database_path=db,workspace_root=ws,work_root=case['work'],archive_root=archive,is_main=True)
    control=tmp_path/'archive-process';control.mkdir();casefile=control/'case.json';casefile.write_text(json.dumps({k:str(case[k]) for k in ['db','workspace','archive','cr_id']}))
    before={str(p.relative_to(archive)):{'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'inode':p.stat().st_ino} for p in archive.rglob('*') if p.is_file()}
    (control/'archive-before.json').write_text(json.dumps(before,indent=2))
    log=(control/'process.log').open('w');p=subprocess.Popen([sys.executable,str(Path(__file__).with_name('f14_archive_worker.py')),str(casefile),str(control)],env=dict(os.environ),stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    try:
        until=time.monotonic()+20
        while not (control/'checkpoint.json').exists() and p.poll() is None and time.monotonic()<until:time.sleep(.01)
        assert (control/'checkpoint.json').exists(),(control/'process.log').read_text()
        new=tmp_path/'requested-archive';new.mkdir()
        with pytest.raises(registry.LibraryRegistryError):registry.update_library_paths(reg,'main',archive_root=new)
        assert registry.get_library(reg,'main')['archive_root']==str(archive)
        if replace_archive:
            retained=tmp_path/'retained-archive';archive.rename(retained);archive.mkdir()
            foreign=archive/'foreign.JPG';foreign.write_bytes(b'synthetic-foreign-archive')
        (control/'continue').write_text('continue');result=p.wait(timeout=25)
        answer=json.loads((control/'result.json').read_text())
        if replace_archive:
            assert result!=0 and answer['failed']
            assert foreign.read_bytes()==b'synthetic-foreign-archive'
            assert all(hashlib.sha256((retained/n).read_bytes()).hexdigest()==v['sha256'] and (retained/n).stat().st_ino==v['inode'] for n,v in before.items())
            assert list(ro._control_location(ws).glob('operation-*.json'))
            with pytest.raises(registry.LibraryRegistryError):registry.update_library_paths(reg,'main',archive_root=new)
        else:
            assert result==0 and answer['complete']
            rows=describe_archive_release_stock(db,case['cr_id'])['rows']
            assert rows
            for row in rows:
                target=case['central']/row['workspace_release_path'];source=archive/row['old_path']
                assert hashlib.sha256(target.read_bytes()).hexdigest()==hashlib.sha256(source.read_bytes()).hexdigest()==row['expected_sha256']
            assert all(hashlib.sha256((archive/n).read_bytes()).hexdigest()==v['sha256'] and (archive/n).stat().st_ino==v['inode'] for n,v in before.items())
            # The prepared change request is still a legitimate blocker even
            # though this particular copy lease completed.
            with pytest.raises(registry.LibraryRegistryError):registry.update_library_paths(reg,'main',archive_root=new)
            cancelled=cancel_event_change(db,case['cr_id'],archive,ws)
            assert cancelled['status']=='abgebrochen'
            changed=registry.update_library_paths(reg,'main',archive_root=new)
            assert changed['archive_root']==str(new)
        state=snapshot(tmp_path,control/'final-snapshot.json')
        assert all(d['integrity']=='ok' and not d['foreign_keys'] for d in state['databases'].values())
    finally:
        if p.poll() is None:os.killpg(p.pid,signal.SIGKILL);p.wait()
        log.close()
