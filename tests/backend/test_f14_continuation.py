"""F14 continuation: creator-bound views and mutation scope counterexamples."""
from pathlib import Path
from types import SimpleNamespace
import hashlib
import pytest
from app import root_operations as ro
from app.library_registry import register_library, LibraryRegistryError
from tests.backend.test_f14_root_operations import fixture, snapshot


def legacy(tmp_path, monkeypatch):
    monkeypatch.setenv('KAMERA_CONFIG',str(tmp_path/'settings.json'))
    monkeypatch.setenv('KAMERA_REGISTRY_DATABASE',str(tmp_path/'absent-registry.sqlite3'))
    ws=tmp_path/'workspace';ws.mkdir();work=tmp_path/'work';work.mkdir()
    backup=ws/'SD-Kartensicherungen';backup.mkdir();view=tmp_path/'view';view.mkdir()
    (view/'Arbeitsbereich').symlink_to(work,target_is_directory=True)
    (view/'SD-Kartensicherungen').symlink_to(backup,target_is_directory=True)
    db=tmp_path/'library.sqlite3'
    return ws,work,backup,view,db


@pytest.mark.parametrize('change',['none','alias','parent','generation','different-database'])
def test_f14_creator_binding(tmp_path,monkeypatch,change):
    ws,work,backup,view,db=legacy(tmp_path,monkeypatch)
    ro.attest_legacy_plan_view(db,view,work,backup)
    marker=work/'original.JPG';marker.write_bytes(b'original')
    digest=hashlib.sha256(marker.read_bytes()).hexdigest();seen=[]
    @ro.protect(workspace_arg='workspace',kind='sort')
    def operation(database_path,workspace):seen.append('executed')
    if change=='alias':
        foreign=tmp_path/'foreign';foreign.mkdir()
        (view/'Arbeitsbereich').unlink();(view/'Arbeitsbereich').symlink_to(foreign,target_is_directory=True)
    elif change=='parent':
        view.rename(tmp_path/'old-view');view.mkdir()
        (view/'Arbeitsbereich').symlink_to(work,target_is_directory=True)
        (view/'SD-Kartensicherungen').symlink_to(backup,target_is_directory=True)
    elif change=='generation':
        with ro.mutate(ws,rollback_check=lambda:True):pass
    elif change=='different-database':db=tmp_path/'foreign.sqlite3'
    if change=='none':
        operation(db,view);assert seen==['executed']
    else:
        with pytest.raises(ro.RootOperationError):operation(db,view)
        assert not seen
    assert hashlib.sha256(marker.read_bytes()).hexdigest()==digest


def test_f14_unattested_and_external_view_rejected(tmp_path,monkeypatch):
    ws,work,backup,view,db=legacy(tmp_path,monkeypatch)
    @ro.protect(workspace_arg='workspace',kind='sort')
    def operation(database_path,workspace):raise AssertionError('must not enter')
    with pytest.raises(ro.RootOperationError):operation(db,view)
    foreign=tmp_path.parent/'foreign-work';foreign.mkdir(exist_ok=True)
    with pytest.raises(ro.RootOperationError):ro.attest_legacy_plan_view(db,view,foreign,backup)


@pytest.mark.parametrize('target',[None,'second'])
def test_f14_local_mutation_cannot_escalate(fixture,target):
    case,ws,reg,dbs,ev=fixture
    with ro.mutate(ws,library_id='main',databases=[dbs[0]],rollback_check=lambda:True):
        with pytest.raises(ro.RootOperationError):
            with ro.mutate(ws,library_id=target):pytest.fail('scope escalation')
    assert ro.generation(ws,'main')==(0,1)
    assert ro.generation(ws,'second')==(0,0)
    snapshot(case,ev/'scope.json')


def test_f14_global_mutation_owns_nested_local_scope(fixture):
    case,ws,reg,dbs,ev=fixture
    with ro.mutate(ws,databases=dbs,rollback_check=lambda:True):
        with ro.mutate(ws,library_id='main',precondition=lambda:True):pass
    assert ro.generation(ws,'main')==(1,0)
    assert ro.generation(ws,'second')==(1,0)


def test_f14_database_relink_cannot_bypass_other_library(fixture):
    case,ws,reg,dbs,ev=fixture;replacement=case/'new-main.sqlite3'
    import sqlite3
    with sqlite3.connect(dbs[0]) as source,sqlite3.connect(replacement) as target:source.backup(target)
    with ro.reserve(ws,library_id='second',paths=[ws],database=dbs[1]):
        with pytest.raises(LibraryRegistryError):
            register_library(reg,library_id='main',display_name='main',database_path=replacement,
                             workspace_root=ws,work_root=ws/'Arbeitsbereiche/main',
                             archive_root=case/'archive-main',is_main=True)
    from app.library_registry import get_library
    assert get_library(reg,'main')['database_path']==str(dbs[0])
    register_library(reg,library_id='main',display_name='main',database_path=replacement,
                     workspace_root=ws,work_root=ws/'Arbeitsbereiche/main',
                     archive_root=case/'archive-main',is_main=True)
    assert ro.generation(ws,'second')==(1,0)
    snapshot(case,ev/'db-relink.json')


def test_f14_direct_database_repair_is_global(fixture):
    case,ws,reg,dbs,ev=fixture;replacement=case/'repaired-main.sqlite3'
    import sqlite3
    from app.library_registry import update_library_database_path,get_library
    with sqlite3.connect(dbs[0]) as source,sqlite3.connect(replacement) as target:source.backup(target)
    with ro.reserve(ws,library_id='second',paths=[ws],database=dbs[1]):
        with pytest.raises(LibraryRegistryError):update_library_database_path(reg,'main',replacement)
    assert get_library(reg,'main')['database_path']==str(dbs[0])
    with ro.mutate(ws,library_id='main',databases=[dbs[0]],rollback_check=lambda:True):
        with pytest.raises(LibraryRegistryError):update_library_database_path(reg,'main',replacement)
    update_library_database_path(reg,'main',replacement)
    assert ro.generation(ws,'second')==(1,0)
    snapshot(case,ev/'direct-db-repair.json')


@pytest.mark.parametrize('kind',['shared_workspace','camera_archive'])
def test_f14_stale_inventory_root_never_enters_scanner(fixture,kind):
    case,ws,reg,dbs,ev=fixture
    from app.event_inventory import scan_event_inventory,EventInventoryError
    foreign=case/'stale-root';foreign.mkdir();marker=foreign/'foreign.JPG';marker.write_bytes(b'foreign')
    inode=marker.stat().st_ino
    with pytest.raises(EventInventoryError,match='aktuelle registrierte Dateiwurzel'):
        scan_event_inventory(dbs[0],foreign,'absent-job','absent-event',root_kind=kind)
    assert marker.read_bytes()==b'foreign' and marker.stat().st_ino==inode
    snapshot(case,ev/'stale-inventory.json')


def test_f14_stale_backup_root_rejected_before_deletion(fixture):
    case,ws,reg,dbs,ev=fixture
    from app.backup_management import delete_backup,BackupDeletionError
    foreign=case/'stale-central';foreign.mkdir();marker=foreign/'foreign.JPG';marker.write_bytes(b'foreign')
    with pytest.raises(BackupDeletionError,match='veraltete zentrale'):
        delete_backup(dbs[0],reg,foreign,'absent-job')
    assert marker.read_bytes()==b'foreign'
    snapshot(case,ev/'stale-backup.json')


def test_f14_two_library_mutations_preserve_first_intent(fixture):
    import threading
    case,ws,reg,dbs,ev=fixture;entered=threading.Event();release=threading.Event();errors=[]
    parent=ro._control_location(ws)
    def first():
        try:
            with ro.mutate(ws,library_id='main',databases=[dbs[0]],rollback_check=lambda:True):
                entered.set();assert release.wait(10)
        except BaseException as error:errors.append(repr(error))
    thread=threading.Thread(target=first);thread.start();assert entered.wait(10)
    try:
        original=(parent/'mutation.json').read_bytes()
        with pytest.raises(ro.RootOperationError):
            with ro.mutate(ws,library_id='second',databases=[dbs[1]]):pytest.fail('intent overwritten')
        assert (parent/'mutation.json').read_bytes()==original
        # An unrelated library's file worker remains usable during this intent.
        with ro.reserve(ws,library_id='second',paths=[ws],database=dbs[1]):
            assert (ws/'Arbeitsbereiche/second/original.JPG').read_bytes()==b'synthetic-second'
    finally:release.set();thread.join(10)
    assert not thread.is_alive() and not errors
    snapshot(case,ev/'parallel-intents.json')


@pytest.mark.parametrize('conflict',['database','generation','new-root'])
def test_f14_nested_operation_does_not_bypass_binding(fixture,conflict):
    case,ws,reg,dbs,ev=fixture;extra=case/'extra';extra.mkdir()
    with ro.reserve(ws,library_id='main',paths=[ws],database=dbs[0]) as outer:
        if conflict=='new-root':
            with ro.reserve(ws,library_id='main',paths=[extra],database=dbs[0]):pass
            assert str(extra) in ro._read(outer['_path'])['bindings']
            extra.rename(case/'original-extra');extra.mkdir()
        with pytest.raises(ro.RootOperationError):
            with ro.reserve(ws,library_id='main',paths=[extra] if conflict=='new-root' else [ws],
                            database=dbs[1] if conflict=='database' else dbs[0],
                            expected_generation=(9,9) if conflict=='generation' else None):
                pytest.fail('nested binding bypass')
        if conflict=='new-root':
            extra.rmdir();(case/'original-extra').rename(extra)
    snapshot(case,ev/('nested-'+conflict+'.json'))


def test_f14_exception_retains_unproven_reservation(fixture):
    case,ws,reg,dbs,ev=fixture
    with pytest.raises(RuntimeError,match='synthetic'):
        with ro.reserve(ws,library_id='main',paths=[ws],database=dbs[0],kind='unknown-operation'):
            raise RuntimeError('synthetic interrupted operation')
    parent=ro._control_location(ws)
    assert len(list(parent.glob('operation-*.json')))==1
    with pytest.raises(ro.RootOperationError,match='operation_recovery_required'):
        with ro.mutate(ws,databases=dbs):pytest.fail('unknown operation silently discarded')
    with ro.reserve(ws,library_id='main',paths=[ws],database=dbs[0],kind='unknown-operation'):pass
    assert not list(parent.glob('operation-*.json'))
    snapshot(case,ev/'explicit-retry.json')


def test_f14_finished_receipt_survives_repeated_sigkill(fixture):
    import json,os,signal,subprocess,sys,time
    case,ws,reg,dbs,ev=fixture
    worker=Path(__file__).with_name('f14_root_worker.py')
    parent=ro._control_location(ws)
    def stop_and_kill(action):
        control=ev/action;control.mkdir()
        with (control/'process.log').open('w') as log:
            p=subprocess.Popen([sys.executable,str(worker),str(ws),str(control),action],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            try:
                deadline=time.monotonic()+10
                while not (control/'checkpoint.json').exists():
                    assert p.poll() is None,(control/'process.log').read_text()
                    assert time.monotonic()<deadline
                    time.sleep(.01)
                marker=json.loads((control/'checkpoint.json').read_text());assert marker['pid']==p.pid
                os.killpg(p.pid,signal.SIGKILL);p.wait(timeout=5);assert p.returncode==-9
                (control/'exit.json').write_text(json.dumps({'pid':p.pid,'returncode':p.returncode}))
            finally:
                if p.poll() is None:os.killpg(p.pid,signal.SIGKILL);p.wait()
    stop_and_kill('reserve-finished')
    record=ro._read(next(parent.glob('operation-*.json')))
    assert ro._completed(record)
    stop_and_kill('retire-finished')
    assert ro._completed(record)
    from tests.backend import test_0562_process_recovery as recovery
    for n in range(3):
        # Every probe is a new process, followed by a full application start.
        control=ev/('probe-'+str(n));control.mkdir()
        result=subprocess.run([sys.executable,str(worker),str(ws),str(control),'probe'],capture_output=True,text=True,timeout=15)
        (control/'exit.json').write_text(json.dumps({'code':result.returncode,'stdout':result.stdout,'stderr':result.stderr}))
        assert result.returncode==0
        recovery.invoke(case,'startup','none',ev/('application-start-'+str(n)))
        assert (ws/'Arbeitsbereiche/main/original.JPG').read_bytes()==b'synthetic-main'
    assert not list(parent.glob('operation-*.json'))
    snapshot(case,ev/'receipt-recovery.json')


def test_f14_ambiguous_registry_cannot_split_lock_namespace(fixture,monkeypatch):
    import sqlite3
    case,ws,reg,dbs,ev=fixture;other=case/'other-registry.sqlite3'
    with sqlite3.connect(reg) as source,sqlite3.connect(other) as target:source.backup(target)
    parent=ro._control_location(ws)
    with ro.reserve(ws,library_id='main',paths=[ws],database=dbs[0]):
        # Same registered workspace in a second, independent registry must not
        # yield another set of locks while the first reservation is active.
        monkeypatch.setenv('KAMERA_REGISTRY_DATABASE',str(other))
        with pytest.raises(ro.RootOperationError,match='Mehrere unabhängige Registries'):
            with ro.mutate(ws):pytest.fail('second lock namespace')
        monkeypatch.setenv('KAMERA_REGISTRY_DATABASE',str(reg))
    assert ro._control_location(ws)==parent
    snapshot(case,ev/'registry-ambiguity.json')


def test_f14_shared_stock_blocks_relink_but_not_independent_file_read(fixture):
    case,ws,reg,dbs,ev=fixture;new=case/'second-work';new.mkdir()
    from app.library_registry import update_library_paths,get_library
    with ro.reserve(ws,library_id='main',paths=[ws],database=dbs[0],kind='backup'):
        with pytest.raises(LibraryRegistryError):update_library_paths(reg,'second',work_root=new)
        with ro.reserve(ws,library_id='second',paths=[ws],database=dbs[1],kind='inventory'):
            assert (ws/'Arbeitsbereiche/second/original.JPG').read_bytes()==b'synthetic-second'
    update_library_paths(reg,'second',work_root=new)
    assert get_library(reg,'second')['work_root']==str(new)
    snapshot(case,ev/'shared-stock.json')


def test_f14_nested_shared_scope_requires_prior_reservation(fixture):
    case,ws,reg,dbs,ev=fixture
    with ro.reserve(ws,library_id='main',paths=[ws],database=dbs[0],kind='inventory'):
        with pytest.raises(ro.RootOperationError,match='vorab erworbene'):
            with ro.reserve(ws,library_id='main',paths=[ws],database=dbs[0],kind='trash'):
                pytest.fail('local reservation upgraded after library lock')



def test_f14_orphan_shared_reservation_blocks_other_library_after_sigkill(fixture):
    import json,os,signal
    from tests.backend.test_f14_root_operations import spawn
    from tests.backend import test_0562_process_recovery as recovery
    from app.library_registry import update_library_paths
    case,ws,reg,dbs,ev=fixture;new=case/'new-second';new.mkdir()
    process,control,log=spawn(case,ws,reg,ev,'reserve-shared')
    try:
        os.killpg(process.pid,signal.SIGKILL);process.wait(timeout=5);assert process.returncode==-9
    finally:log.close()
    records=list(ro._control_location(ws).glob('operation-*.json'));assert len(records)==1
    original=records[0].read_bytes();assert json.loads(original)['shared'] is True
    for n in range(3):
        recovery.invoke(case,'startup','none',ev/('shared-orphan-start-'+str(n)))
        with pytest.raises(LibraryRegistryError,match='operation_recovery_required'):
            update_library_paths(reg,'second',work_root=new)
        assert records[0].read_bytes()==original
        assert (ws/'Arbeitsbereiche/main/original.JPG').read_bytes()==b'synthetic-main'
        assert (ws/'Arbeitsbereiche/second/original.JPG').read_bytes()==b'synthetic-second'
    snapshot(case,ev/'shared-orphan-after-three-starts.json')
