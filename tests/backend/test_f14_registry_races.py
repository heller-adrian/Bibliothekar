"""Late metadata publication must not restore a stale root or database binding."""
import json,threading
from pathlib import Path
import pytest
from app import library_registry as registry,root_operations as ro
from app.library_context import resolve_library_context
from tests.backend.test_f14_root_operations import fixture,snapshot


@pytest.mark.parametrize('writer',['settings','activation','paths'])
def test_f14_late_registry_snapshot_must_not_restore_previous_root(fixture,monkeypatch,writer):
    case,ws,reg,dbs,ev=fixture;entered=threading.Event();release=threading.Event();outcome=[]
    original=registry.register_library
    def barrier(*args,**kwargs):
        if threading.current_thread().name=='old-snapshot':entered.set();assert release.wait(10)
        return original(*args,**kwargs)
    monkeypatch.setattr(registry,'register_library',barrier)
    next_archive=case/'new-archive';next_archive.mkdir()
    def stale_metadata():
        try:
            if writer=='settings':registry.update_library_settings(reg,'main',{'synthetic':'metadata'})
            elif writer=='activation':registry.set_library_active(reg,'second',False)
            else:registry.update_library_paths(reg,'main',work_root=ws/'Arbeitsbereiche/main')
            outcome.append({'accepted':True})
        except registry.LibraryRegistryError as e:outcome.append({'accepted':False,'detail':str(e)})
    lid='second' if writer=='activation' else 'main'
    thread=threading.Thread(target=stale_metadata,name='old-snapshot');thread.start();assert entered.wait(10)
    try:
        changed=registry.update_library_paths(reg,lid,archive_root=next_archive)
        assert changed['archive_root']==str(next_archive)
    finally:release.set();thread.join(10)
    assert not thread.is_alive() and len(outcome)==1,outcome
    row=registry.get_library(reg,lid,active_only=False)
    (ev/'race-outcome.json').write_text(json.dumps({'writer':writer,'thread_result':outcome,'registry':row,'generation':ro.generation(ws,lid)},indent=2))
    assert row['archive_root']==str(next_archive),'Late metadata snapshot republished an obsolete archive root'
    assert not outcome[0]['accepted'],'Stale root-bearing snapshot needs explicit rejection'
    state=snapshot(case,ev/'after-late-publication.json')
    assert all(db['integrity']=='ok' and not db['foreign_keys'] for db in state['databases'].values())
    assert (ws/'Arbeitsbereiche/main/original.JPG').read_bytes()==b'synthetic-main'


def test_f14_registered_missing_workspace_rejects_schema_before_sql(fixture,monkeypatch):
    from app import main
    case,ws,reg,dbs,ev=fixture;ctx=resolve_library_context(reg,'main');called=[]
    ws.rename(case/'retained-workspace')
    monkeypatch.setattr(main,'initialize_database',lambda *a,**k:called.append('schema-write'))
    with pytest.raises(ro.RootOperationError):main.ensure_library_database_schema(ctx)
    assert not called
    assert (case/'retained-workspace/Arbeitsbereiche/main/original.JPG').read_bytes()==b'synthetic-main'
    snapshot(case,ev/'registered-missing-schema.json')


@pytest.mark.parametrize('operation',['claim','schema','naming','layout','visibility','acknowledge','dismiss','clear'])
def test_f14_request_cannot_write_during_actual_registry_root_mutation(fixture,monkeypatch,operation):
    from app import main
    from tests.backend.test_f14_o2_policy import snapshot as stable_snapshot
    case,ws,reg,dbs,ev=fixture;ctx=resolve_library_context(reg,'main');entered=threading.Event();release=threading.Event();outcome=[];called=[]
    new=case/'new-archive';new.mkdir()
    actual=ro._write
    def pause(path,value):
        actual(path,value)
        if path.name=='mutation.json':entered.set();assert release.wait(10)
    monkeypatch.setattr(ro,'_write',pause)
    monkeypatch.setattr(main,'claim_next_job',lambda *a,**k:called.append('claim-sql'))
    monkeypatch.setattr(main,'initialize_database',lambda *a,**k:called.append('schema-sql'))
    monkeypatch.setattr(main,'database_connection',lambda *a,**k:called.append('callback-sql'))
    monkeypatch.setattr(main,'update_library_settings',lambda *a,**k:called.append('settings-sql'))
    def root_change():
        try:outcome.append(registry.update_library_paths(reg,'main',archive_root=new))
        except BaseException as error:outcome.append(repr(error))
    thread=threading.Thread(target=root_change);thread.start();assert entered.wait(10)
    try:
        before=stable_snapshot(case,ev/'mutation-before-callback.json')
        callbacks={
            'claim':lambda:main._claim_context_job(ctx),
            'schema':lambda:main.ensure_library_database_schema(ctx),
            'naming':lambda:main.api_set_event_naming({}),
            'layout':lambda:main.api_set_event_folder_layout({}),
            'visibility':lambda:main.api_import_history_visibility('synthetic',{'hidden':True}),
            'acknowledge':lambda:main.api_acknowledge_external_changes({}),
            'dismiss':lambda:main.api_dismiss_external_change('synthetic'),
            'clear':main.api_clear_background_activity,
        }
        expected=ro.RootOperationError if operation in {'claim','schema'} else main.HTTPException
        with pytest.raises(expected) as error:callbacks[operation]()
        if expected is main.HTTPException:assert error.value.status_code==409
        assert not called
        assert stable_snapshot(case,ev/'mutation-after-callback.json')==before
    finally:release.set();thread.join(10)
    assert not thread.is_alive() and len(outcome)==1 and isinstance(outcome[0],dict),outcome
    assert outcome[0]['archive_root']==str(new)
    assert (ws/'Arbeitsbereiche/main/original.JPG').read_bytes()==b'synthetic-main'
    state=stable_snapshot(case,ev/'root-change-complete.json')
    assert all(db['integrity']=='ok' and not db['foreign_keys'] for db in state['databases'].values())


@pytest.mark.parametrize('kind',['import','sort','ssd','archive','inventory','recovery'])
def test_f14_active_reservation_blocks_relink_then_allows_it_after_completion(fixture,kind):
    case,ws,reg,dbs,ev=fixture;entered=threading.Event();release=threading.Event();errors=[]
    next_archive=case/'new-archive';next_archive.mkdir()
    def worker():
        try:
            with ro.reserve(ws,library_id='main',database=dbs[0],kind=kind,paths=[ws/'Arbeitsbereiche/main']):entered.set();assert release.wait(10)
        except BaseException as e:errors.append(repr(e))
    thread=threading.Thread(target=worker);thread.start();assert entered.wait(10)
    try:
        with pytest.raises(registry.LibraryRegistryError):registry.update_library_paths(reg,'main',archive_root=next_archive)
        assert registry.get_library(reg,'main')['archive_root']==str(case/'archive-main')
    finally:release.set();thread.join(10)
    assert not thread.is_alive() and not errors
    assert registry.update_library_paths(reg,'main',archive_root=next_archive)['archive_root']==str(next_archive)
    assert (ws/'Arbeitsbereiche/main/original.JPG').read_bytes()==b'synthetic-main'
    snapshot(case,ev/'completed-then-relinked.json')


def test_f14_relinked_generation_rejects_stale_worker_before_body(fixture):
    case,ws,reg,dbs,ev=fixture;old=resolve_library_context(reg,'main');seen=[]
    next_archive=case/'new-archive';next_archive.mkdir()
    registry.update_library_paths(reg,'main',archive_root=next_archive)
    @ro.protect(context_provider=lambda a:a['library_context'])
    def operation(*,library_context):seen.append('entered')
    with pytest.raises(ro.RootOperationError):operation(library_context=old)
    with pytest.raises(ro.RootOperationError):
        with ro.reserve(ws,library_id='main',expected_generation=old.root_generation):raise AssertionError('stale reservation entered')
    assert not seen
    operation(library_context=resolve_library_context(reg,'main'))
    assert seen==['entered']
    snapshot(case,ev/'fresh-generation.json')


def test_f14_two_real_worker_processes_block_relink_and_preserve_bytes(fixture):
    import os,signal
    from app.storage_config import storage_paths
    from tests.backend.test_f14_root_operations import spawn
    case,ws,reg,dbs,ev=fixture;processes=[];new=case/'new-archive';new.mkdir()
    for lid in ['main','second']:(ws/('staged-'+lid+'.JPG')).write_bytes(b'transfer-'+lid.encode())
    try:
        for lid in ['main','second']:processes.append(spawn(case,ws,reg,ev,'reserve-live-'+lid))
        with pytest.raises(registry.LibraryRegistryError):registry.update_library_paths(reg,'main',archive_root=new)
        for process,control,log in processes:(control/'continue').write_text('continue')
        for process,control,log in processes:
            process.wait(timeout=10);assert process.returncode==0,(control/'process.log').read_text()
        for lid in ['main','second']:
            assert (storage_paths(ws)['workspaces_root']/lid/'moved.JPG').read_bytes()==b'transfer-'+lid.encode()
            assert not (ws/('staged-'+lid+'.JPG')).exists()
        assert registry.update_library_paths(reg,'main',archive_root=new)['archive_root']==str(new)
        state=snapshot(case,ev/'two-processes-completed.json')
        assert all(db['integrity']=='ok' and not db['foreign_keys'] for db in state['databases'].values())
    finally:
        for process,control,log in processes:
            if process.poll() is None:os.killpg(process.pid,signal.SIGKILL);process.wait()
            log.close()
