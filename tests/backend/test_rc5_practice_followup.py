"""RC5 practice regressions; synthetic paths, no real NAS or devices."""
import json,os,hashlib,shutil,uuid,threading
from pathlib import Path
import pytest
from app import main,root_operations as ro,sd_recheck as sr
from app.managed_storage_health import inspect_storage
from app.storage_config import ENGLISH_STORAGE_DEFAULTS
from app.database import database_connection,claim_next_job,get_job
from tests.backend.test_f14_root_operations import fixture
from tests.backend.test_rc1_sd_reimport import setup_live_import,queue_and_run,direct_import_lifecycle

@pytest.fixture
def empty_reset(tmp_path,monkeypatch):
    case=tmp_path/'case';case.mkdir();ws=case/'workspace';ws.mkdir();private=case/'database';private.mkdir();db=private/'main.sqlite3';reg=private/'registry.sqlite3';config=case/'settings.json';config.write_text('{}')
    for k,v in {'KAMERA_WORKSPACE':ws,'KAMERA_CONFIG':config,'KAMERA_REGISTRY_DATABASE':reg,'KAMERA_DATABASE_DIR':private}.items():monkeypatch.setenv(k,str(v))
    for name in ENGLISH_STORAGE_DEFAULTS.values():(ws/name).mkdir()
    # Historical RC5/RC10 fixture, not an incomplete RC11 bootstrap. Preserve
    # the original format-1 state explicitly: RC11 requires a real receipt.
    _,parent=ro._control(ws)
    state={'format':1,'workspace':ro._identity(ws),'generation':0,'libraries':{},
           'bindings':{str(p):ro._identity(p) for p in [ws,*(ws/n for n in ENGLISH_STORAGE_DEFAULTS.values())]},
           'storage_names':dict(ENGLISH_STORAGE_DEFAULTS),
           'storage_initialization':{'phase':'completed','names':dict(ENGLISH_STORAGE_DEFAULTS),'database':str(db)}}
    ro._write(parent/'state.json',state)
    old=ro._read(parent/'state.json')
    for n in ENGLISH_STORAGE_DEFAULTS.values():
        (ws/n).rename(case/('old-'+n));(ws/n).mkdir()
    for k,v in {'WORKSPACE_PATH':ws,'DATABASE_FILE':db,'REGISTRY_DATABASE_FILE':reg,'CONFIG_PATH':config}.items():monkeypatch.setattr(main,k,v)
    return case,ws,db,reg,parent,old


def test_empty_explicit_reset_is_offered_but_not_automatically_rebound(empty_reset):
    case,ws,db,reg,parent,old=empty_reset
    status=inspect_storage(ws,database=db)
    assert not status['ready'] and not status['can_initialize']
    roots=[f for f in status['folders'] if f['key'] in ENGLISH_STORAGE_DEFAULTS]
    children=[f for f in status['folders'] if f['key'] in {'metadata_general','metadata_multiple'}]
    assert len(roots)==4 and all(f['status']=='identity_changed' for f in roots)
    assert len(children)==2 and all(f['status']=='missing' and f['identity_evidence']=='not_observed' for f in children)
    assert status.get('can_setup_again') is True
    assert ro._read(parent/'state.json')==old


def test_folder_duplicate_admission_is_background_not_regular_import(fixture,monkeypatch):
    case,ws,reg,dbs,source,context=setup_live_import(fixture,monkeypatch)
    queue_and_run(dbs[0],context)
    monkeypatch.setattr(main,'IMPORT_ROOT',source.parent.parent)
    before=main.api_import_history()['total']
    response=main.api_run_folder_import({'source_root_key':'saved','source_relative_path':'CARD','source_mode':'folder','confirm_reimport':True,'request_id':str(uuid.uuid4())})
    data=json.loads(response.body)
    assert data['status']=='sd_check' and data['job']['operation']=='sd_recheck'
    job=claim_next_job(dbs[0]);main.process_claimed_job(job,library_context=context)
    done=get_job(dbs[0],job['id']);assert done['state']=='completed' and done['result']['status']=='already_backed_up',done
    assert claim_next_job(dbs[0]) is None and main.api_import_history()['total']==before


def test_reset_preserves_old_evidence_and_resumes(empty_reset,monkeypatch):
    case,ws,db,reg,parent,old=empty_reset
    # The canonical Linux harness supplies an independent bootstrap archive.
    # Both parent and subprocess must attest the identical synthetic mount.
    (case/'archive').mkdir()
    monkeypatch.setenv('KAMERA_ARCHIVE_ROOT',str(case/'archive'))
    proof=inspect_storage(ws,database=db)
    ro.reset_empty_storage(ws,db,proof['setup_token'])
    new=ro._read(parent/'state.json');archive=parent/new['setup_reset']['history']
    assert ro._read(archive)==old and new['generation']==old['generation']+1
    assert inspect_storage(ws,database=db)['can_initialize']
    for n in range(3):
        result=setup_child(case,case/('boot-'+str(n)))
        assert result['error'] is None and result['ready'] and result['onboarding'],result

    assert ro._read(archive)==old


@pytest.mark.parametrize('unsafe',['media','symlink','private-retention','library','job','mutation','workspace-replaced','acl','stale-token'])
def test_reset_refuses_preserved_evidence(empty_reset,monkeypatch,unsafe):
    case,ws,db,reg,parent,old=empty_reset;token=inspect_storage(ws,database=db)['setup_token']
    if unsafe=='media':(ws/'Trash'/'original.JPG').write_bytes(b'do not lose')
    elif unsafe=='symlink':(ws/'Trash').rmdir();(ws/'Trash').symlink_to(case/'old-Trash',target_is_directory=True)
    elif unsafe=='private-retention':
        ret=db.parent/'.bibliothekar-restore-retention';ret.mkdir();(ret/'retained.JPG').write_bytes(b'retention')
    elif unsafe=='library':
        from app.library_registry import initialize_library_registry,register_library
        from app.database import initialize_database
        initialize_database(db);initialize_library_registry(reg)
        work=case/'work';work.mkdir();archive=case/'archive';archive.mkdir()
        # Model a surviving registered pre-reset catalogue through the schema;
        # the API correctly refuses introducing a new library into this conflict.
        import sqlite3
        with sqlite3.connect(reg) as c:
            c.execute("INSERT INTO libraries (library_id,display_name,database_path,workspace_root,work_root,archive_root,is_main,is_active,is_registered,created_at,updated_at) VALUES ('main','Real',?,?,?,?,1,1,1,'now','now')",(str(db),str(ws),str(work),str(archive)))
    elif unsafe=='job':
        from app.database import initialize_database,create_job
        initialize_database(db);create_job(db,job_id='OLD',source_path=str(ws),working_path=str(ws),kind='sd_import',trigger_type='manual',operation='folder_import')
    elif unsafe=='mutation':ro._write(parent/'mutation.json',{'pending':'keep'})
    elif unsafe=='archive':
        archive=case/'archive';archive.mkdir();(archive/'old.JPG').write_bytes(b'archive')
        state=ro._read(parent/'state.json');state['bindings'][str(archive)]=ro._identity(archive);ro._write(parent/'state.json',state)
    elif unsafe=='workspace-replaced':ws.rename(case/'old-workspace');ws.mkdir()
    elif unsafe=='acl':
        from app import trash_retention as rt
        monkeypatch.setattr(rt,'check_acl',lambda *a,**kw:(_ for _ in ()).throw(ValueError('foreign ACL writer')))
    elif unsafe=='stale-token':token='0'*64
    before=(parent/'state.json').read_bytes()
    with pytest.raises(ro.RootOperationError):ro.reset_empty_storage(ws,db,token)
    assert (parent/'state.json').read_bytes()==before
    assert not list(parent.glob('setup-history-*.json'))


def test_folder_worker_missing_copy_and_mixed_files(fixture,monkeypatch):
    from PIL import Image
    from app.storage_config import storage_paths
    case,ws,reg,dbs,source,context=setup_live_import(fixture,monkeypatch);queue_and_run(dbs[0],context)
    with database_connection(dbs[0]) as c:relative=c.execute('SELECT current_relative_path FROM files LIMIT 1').fetchone()[0]
    target=storage_paths(ws)['backup_root']/relative;original=target.read_bytes();target.unlink()
    Image.new('RGB',(8,8),'blue').save(source.with_name('new.JPG'))
    monkeypatch.setattr(main,'IMPORT_ROOT',source.parent.parent)
    data=json.loads(main.api_run_folder_import({'source_root_key':'saved','source_relative_path':'CARD','source_mode':'folder'}).body)
    job=claim_next_job(dbs[0]);assert job['id']==data['task_id'];main.process_claimed_job(job,library_context=context)
    final=get_job(dbs[0],job['id']);assert final['state']=='completed',final
    child=claim_next_job(dbs[0]);assert child['id']==final['result']['import_job_id']
    main.process_claimed_job(child,library_context=context);done=get_job(dbs[0],child['id']);assert done['state']=='completed',done
    assert done['result']['organization']['file_count']==2 and target.read_bytes()==original
    with database_connection(dbs[0]) as c:
        assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok' and not c.execute('PRAGMA foreign_key_check').fetchall()


@pytest.mark.parametrize('mode',['queued','running'])
def test_folder_check_cancel_preserves_media_and_never_hands_off(fixture,monkeypatch,mode):
    case,ws,reg,dbs,source,context=setup_live_import(fixture,monkeypatch)
    monkeypatch.setattr(main,'IMPORT_ROOT',source.parent.parent)
    data=json.loads(main.api_run_folder_import({'source_root_key':'saved','source_relative_path':'CARD','source_mode':'folder'}).body);raw=source.read_bytes()
    if mode=='running':
        job=claim_next_job(dbs[0]);main.api_cancel_import(job['id']);main.process_claimed_job(job,library_context=context)
    else:main.api_cancel_import(data['task_id'])
    assert get_job(dbs[0],data['task_id'])['stage']=='cancelled'
    assert claim_next_job(dbs[0]) is None and source.read_bytes()==raw
    assert main.api_import_history()['total']==0


def setup_child(case,output,mode='startup',paused=False):
    import subprocess,sys,time,signal
    log=output.with_suffix('.log').open('w')
    p=subprocess.Popen([sys.executable,str(Path(__file__).with_name('rc5_setup_worker.py')),str(case),str(output),mode],stdout=log,stderr=subprocess.STDOUT,env=dict(os.environ),start_new_session=True)
    if paused:
        until=time.monotonic()+20
        while p.poll() is None and time.monotonic()<until:
            if output.with_suffix('.checkpoint').exists():return p,log
            time.sleep(.01)
        if p.poll() is None:os.killpg(p.pid,signal.SIGKILL);p.wait()
        log.close();raise AssertionError(output.with_suffix('.log').read_text())
    try:assert p.wait(timeout=30)==0,output.with_suffix('.log').read_text()
    finally:
        if p.poll() is None:os.killpg(p.pid,signal.SIGKILL);p.wait()
        log.close()
    return json.loads(output.read_text())


@pytest.mark.parametrize('boundary',['reset-history','reset-state'])
def test_reset_real_sigkill_and_three_restarts(empty_reset,boundary):
    import signal
    case,ws,db,reg,parent,old=empty_reset
    (case/'archive').mkdir()  # The child configures this actual, accessible archive.
    p,log=setup_child(case,case/'killed',boundary,paused=True)
    try:os.killpg(p.pid,signal.SIGKILL);assert p.wait(timeout=10)==-9
    finally:log.close()
    if boundary=='reset-history':
        assert ro._read(parent/'state.json')==old
        status=inspect_storage(ws,database=db);ro.reset_empty_storage(ws,db,status['setup_token'])
    for n in range(3):
        result=setup_child(case,case/('restart-'+str(n)));assert result['error'] is None and result['ready'],result
    assert list(parent.glob('setup-history-*.json'))


@pytest.mark.parametrize('precreated',[False,True])
def test_fresh_real_startup_and_actual_onboarding(empty_reset,precreated):
    case,ws,db,reg,parent,old=empty_reset
    # Separate genuinely new fixture: no existing private coordination evidence.
    shutil.rmtree(parent.parent)
    if not precreated:
        for n in ENGLISH_STORAGE_DEFAULTS.values():(ws/n).rmdir()
    (case/'archive').mkdir()
    result=setup_child(case,case/'first','onboard')
    assert result['error'] is None and result['ready'] and result['onboarding'],result
    assert result['check']['valid'] and result['create_status']==201,result
    assert all((ws/n).is_dir() for n in ENGLISH_STORAGE_DEFAULTS.values())


@pytest.mark.parametrize('change',['added','corrupt','link','source_changed'])
def test_folder_check_conflicts_never_create_empty_import(fixture,monkeypatch,change):
    from app.storage_config import storage_paths
    case,ws,reg,dbs,source,context=setup_live_import(fixture,monkeypatch);queue_and_run(dbs[0],context)
    monkeypatch.setattr(main,'IMPORT_ROOT',source.parent.parent)
    with database_connection(dbs[0]) as c:relative=c.execute('SELECT current_relative_path FROM files LIMIT 1').fetchone()[0]
    target=storage_paths(ws)['backup_root']/relative
    payload={'source_root_key':'saved','source_relative_path':'CARD','source_mode':'folder','request_id':str(uuid.uuid4())}
    queued=json.loads(main.api_run_folder_import(payload).body)
    if change=='added':source.with_name('same.JPG').write_bytes(source.read_bytes())
    elif change=='corrupt':target.write_bytes(b'foreign damaged copy')
    elif change=='link':source.with_name('link.JPG').symlink_to(source)
    else:
        actual=sr.retained_origins
        def changed(*a,**kw):
            result=actual(*a,**kw);source.write_bytes(source.read_bytes()+b'external change');return result
        monkeypatch.setattr(sr,'retained_origins',changed)
    kept=target.read_bytes();job=claim_next_job(dbs[0]);main.process_claimed_job(job,library_context=context);done=get_job(dbs[0],job['id'])
    assert target.read_bytes()==kept and claim_next_job(dbs[0]) is None
    assert done['state']==('completed' if change=='added' else 'failed'),done
    assert main.api_import_history()['total']==1


def test_hundred_known_files_no_import_and_no_managed_folders(fixture,monkeypatch):
    from PIL import Image
    from app.storage_config import storage_paths
    case,ws,reg,dbs,source,context=setup_live_import(fixture,monkeypatch)
    import subprocess
    for n in range(1,100):Image.new('RGB',(8,8),(n,n//2,255-n)).save(source.parent/(str(n)+'.JPG'))
    subprocess.run(['exiftool','-overwrite_original','-DateTimeOriginal=2026:07:22 10:14:04',str(source.parent)],check=True,capture_output=True)
    queue_and_run(dbs[0],context);monkeypatch.setattr(main,'IMPORT_ROOT',source.parent.parent)
    paths=set(p.relative_to(ws).as_posix() for p in ws.rglob('*'));hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in source.parent.iterdir()}
    before=main.api_import_history()['total'];token=str(uuid.uuid4());payload={'source_root_key':'saved','source_relative_path':'CARD','source_mode':'folder','request_id':token}
    first=json.loads(main.api_run_folder_import(payload).body);assert json.loads(main.api_run_folder_import(payload).body)['task_id']==first['task_id']
    job=claim_next_job(dbs[0]);main.process_claimed_job(job,library_context=context);done=get_job(dbs[0],job['id'])
    assert done['state']=='completed' and done['result']['media_file_count']==100,done
    assert done['result']['status']=='already_backed_up' and claim_next_job(dbs[0]) is None
    assert main.api_import_history()['total']==before
    assert paths==set(p.relative_to(ws).as_posix() for p in ws.rglob('*'))
    assert hashes=={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in source.parent.iterdir()}


def test_large_source_http_is_nonhashing_and_browser_close_keeps_queue(fixture,monkeypatch):
    from fastapi.testclient import TestClient
    from time import monotonic
    case,ws,reg,dbs,source,context=setup_live_import(fixture,monkeypatch)
    # Sparse file: represents 5.5GiB without copying/reading that payload.
    large=source.with_name('large.MOV')
    with large.open('wb') as f:f.truncate(11*1024**3//2)
    monkeypatch.setattr(main,'IMPORT_ROOT',source.parent.parent)
    monkeypatch.setattr(sr,'folder_manifest',lambda *a:pytest.fail('HTTP must never hash'))
    payload={'source_root_key':'saved','source_relative_path':'CARD','source_mode':'folder','request_id':str(uuid.uuid4())}
    client=TestClient(main.app);start=monotonic();response=client.post('/api/jobs/folder-import',json=payload);elapsed=monotonic()-start;client.close()
    assert response.status_code==202 and elapsed<2
    second=TestClient(main.app);repeat=second.post('/api/jobs/folder-import',json=payload);second.close()
    assert repeat.json()['task_id']==response.json()['task_id']
    assert get_job(dbs[0],response.json()['task_id'])['state']=='queued'
    assert main.api_import_history()['total']==0


def test_missing_catalog_with_existing_media_stays_blocked(empty_reset):
    case,ws,db,reg,parent,old=empty_reset
    shutil.rmtree(parent.parent)
    (ws/'Library Workspaces'/'original.JPG').write_bytes(b'cannot abandon')
    status=inspect_storage(ws,database=db)
    assert not status['ready'] and not status['can_initialize'] and not status['can_setup_again']
    assert any(i['code']=='catalog_unavailable' for i in status['issues'])


def test_reset_http_requires_auth_confirmation_and_fresh_state(empty_reset,monkeypatch):
    from fastapi.testclient import TestClient
    case,ws,db,reg,parent,old=empty_reset;client=TestClient(main.app)
    status=client.get('/api/settings/storage-health').json();page=client.get('/')
    assert 'storage-initialize' in page.text and 'storage-setup-result' in page.text
    assert client.post('/api/settings/storage-initialize',json={'token':status['setup_token']}).status_code==422
    monkeypatch.setenv('BIBLIOTHEKAR_AUTH_TEST_BYPASS','false')
    assert client.post('/api/settings/storage-initialize',json={'token':status['setup_token'],'confirmation':'SET UP AGAIN'}).status_code==401
    assert ro._read(parent/'state.json')==old


@pytest.mark.parametrize('boundary',['hash','handoff','after_handoff'])
def test_folder_actual_sigkill_atomic_handoff_and_three_restarts(fixture,monkeypatch,tmp_path,boundary):
    import subprocess,sys
    from app.storage_config import storage_paths
    from tests.backend import test_rc4_sd_recheck as original
    data=setup_live_import(fixture,monkeypatch);queue_and_run(data[3][0],data[5])
    monkeypatch.setattr(main,'IMPORT_ROOT',data[4].parent.parent)
    def request():return json.loads(main.api_run_folder_import({'source_root_key':'saved','source_relative_path':'CARD','source_mode':'folder'}).body)
    def child(sd,mode,point,evidence):
        case,ws,reg,dbs,source,context=sd
        (case/'sd-case.json').write_text(json.dumps({'database':str(dbs[0]),'working':str(storage_paths(ws)['backup_root'])}))
        env=dict(os.environ,KAMERA_CONFIG=str(case/'settings.json'),KAMERA_WORKSPACE=str(ws),KAMERA_REGISTRY_DATABASE=str(reg),KAMERA_DATABASE_DIR=str(case),KAMERA_ARCHIVE_ROOT=str(context.archive_root))
        return subprocess.Popen([sys.executable,'-B',str(Path(__file__).with_name('rc5_import_worker.py')),str(case),mode,point,str(evidence)],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    monkeypatch.setattr(original,'request',request);monkeypatch.setattr(original,'child',child)
    # Run every original file/journal/hash/SQLite/restart assertion unchanged
    # at the generic folder queue's actual FD-hash and transactional boundaries.
    original.test_sigkill_real_startup_and_three_independent_restarts(data,tmp_path,boundary)


def test_reset_concurrency_and_changed_after_history_stays_safe(empty_reset,monkeypatch):
    case,ws,db,reg,parent,old=empty_reset;token=inspect_storage(ws,database=db)['setup_token'];actual=ro._write
    def interfered(path,value):
        actual(path,value)
        if path.name.startswith('setup-history-'):(ws/'Trash'/'new-original.JPG').write_bytes(b'new foreign bytes')
    monkeypatch.setattr(ro,'_write',interfered)
    with pytest.raises(ro.RootOperationError):ro.reset_empty_storage(ws,db,token)
    assert ro._read(parent/'state.json')==old and (ws/'Trash'/'new-original.JPG').read_bytes()==b'new foreign bytes'
    assert ro._read(next(parent.glob('setup-history-*.json')))==old


def test_two_reset_requests_do_not_rebind_twice(empty_reset):
    case,ws,db,reg,parent,old=empty_reset;token=inspect_storage(ws,database=db)['setup_token'];barrier=threading.Barrier(2);results=[]
    def attempt():
        barrier.wait()
        try:ro.reset_empty_storage(ws,db,token);results.append('committed')
        except ro.RootOperationError:results.append('refused')
    workers=[threading.Thread(target=attempt) for _ in range(2)]
    for w in workers:w.start()
    for w in workers:w.join(10);assert not w.is_alive()
    assert sorted(results)==['committed','refused']
    assert ro._read(parent/'state.json')['generation']==old['generation']+1
    assert len(list(parent.glob('setup-history-*.json')))==1


def test_all_new_folder_queues_one_real_import(fixture,monkeypatch):
    case,ws,reg,dbs,source,context=setup_live_import(fixture,monkeypatch);raw=source.read_bytes()
    monkeypatch.setattr(main,'IMPORT_ROOT',source.parent.parent)
    payload={'source_root_key':'saved','source_relative_path':'CARD','source_mode':'folder'}
    response=main.api_run_folder_import(payload);assert response.status_code==202
    parent=claim_next_job(dbs[0]);main.process_claimed_job(parent,library_context=context)
    child=claim_next_job(dbs[0]);assert child and child['operation']=='folder_import'
    main.process_claimed_job(child,library_context=context)
    done=get_job(dbs[0],child['id']);assert done['state']=='completed' and done['result']['organization']['file_count']==1,done
    assert main.api_import_history()['total']==1 and claim_next_job(dbs[0]) is None and source.read_bytes()==raw


@pytest.mark.parametrize('kind',['archive-only','sqlite-sidecar','private-hardlink','unknown-control','config-symlink'])
def test_surviving_private_or_archive_evidence_disallows_reset(empty_reset,monkeypatch,kind):
    case,ws,db,reg,parent,old=empty_reset
    if kind=='archive-only':
        archive=case/'archive';archive.mkdir();(archive/'original.JPG').write_bytes(b'archive-original');monkeypatch.setenv('KAMERA_ARCHIVE_ROOT',str(archive))
    elif kind=='sqlite-sidecar':db.with_name(db.name+'-wal').write_bytes(b'preserve-wal')
    elif kind=='private-hardlink':
        from app.database import initialize_database
        initialize_database(db);os.link(db,case/'external.sqlite3')
    elif kind=='unknown-control':ro._write(parent/'unknown.json',{'preserve':True})
    else:
        settings=case/'settings.json';settings.rename(case/'old-settings.json');settings.symlink_to(case/'old-settings.json')
    status=inspect_storage(ws,database=db)
    assert status.get('can_setup_again') is (kind=='archive-only'),status
    assert ro._read(parent/'state.json')==old


def test_new_setup_action_preserves_csrf_enforcement(empty_reset,monkeypatch):
    from fastapi.testclient import TestClient
    case,ws,db,reg,parent,old=empty_reset;monkeypatch.setenv('BIBLIOTHEKAR_AUTH_TEST_BYPASS','false')
    client=TestClient(main.app)
    login=client.post('/auth/login',json={'password':os.environ['BIBLIOTHEKAR_ADMIN_PASSWORD']},headers={'Origin':'http://testserver'})
    assert login.status_code==200,login.text
    assert client.post('/api/settings/storage-initialize',json={'confirmation':'SET UP AGAIN','token':inspect_storage(ws,database=db)['setup_token']},headers={'Origin':'http://testserver'}).status_code==403
    assert ro._read(parent/'state.json')==old


def test_missing_other_registered_catalog_never_means_no_duplicates(fixture,monkeypatch):
    case,ws,reg,dbs,source,context=setup_live_import(fixture,monkeypatch);queue_and_run(dbs[0],context)
    monkeypatch.setattr(main,'IMPORT_ROOT',source.parent.parent)
    main.api_run_folder_import({'source_root_key':'saved','source_relative_path':'CARD','source_mode':'folder'})
    dbs[1].rename(case/'preserved-second.sqlite3')
    job=claim_next_job(dbs[0]);main.process_claimed_job(job,library_context=context)
    assert get_job(dbs[0],job['id'])['state']=='failed' and claim_next_job(dbs[0]) is None
    assert source.exists() and main.api_import_history()['total']==1


def test_same_process_warning_to_confirmed_setup_api(empty_reset):
    case,ws,db,reg,parent,old=empty_reset
    (case/'archive').mkdir()  # Match the configured archive in rc5_setup_worker.
    result=setup_child(case,case/'confirmed-setup','api-reset')
    assert result['error'] is None and result['ready'] and result['onboarding'],result
    assert ro._read(next(parent.glob('setup-history-*.json')))==old


def test_setup_and_check_translations_are_in_delivered_javascript():
    from app.ui_i18n import I18N_UI_JS
    for text in ['Set up again','Cancel check','Check cancelled. No files were changed.','Checking the complete source.','Source check is waiting to run.']:
        assert text in I18N_UI_JS


@pytest.mark.parametrize('mode',['unsupported','sd_card'])
def test_invalid_folder_mode_cannot_bypass_background_check(fixture,monkeypatch,mode):
    case,ws,reg,dbs,source,context=setup_live_import(fixture,monkeypatch);monkeypatch.setattr(main,'IMPORT_ROOT',source.parent.parent)
    with pytest.raises(main.HTTPException) as e:main.api_run_folder_import({'source_root_key':'saved','source_relative_path':'CARD','source_mode':mode})
    assert e.value.status_code==422 and main.api_import_history()['total']==0 and claim_next_job(dbs[0]) is None


def test_stock_registry_without_libraries_is_not_a_fresh_installation(empty_reset):
    from app.library_registry import initialize_library_registry
    case,ws,db,reg,parent,old=empty_reset;initialize_library_registry(reg)
    with __import__('sqlite3').connect(reg) as c:
        c.execute("INSERT INTO canonical_families VALUES ('old-family','original-fingerprint','now','now')")
    c.close()  # Release the fixture's WAL writer before testing persisted registry history.
    status=inspect_storage(ws,database=db)
    assert not status['can_setup_again'] and status['setup_blocker']=='library_or_stock_registry_history',status
    assert ro._read(parent/'state.json')==old


def test_empty_registry_readers_shm_is_not_abandoned_media(empty_reset):
    from app.library_registry import initialize_library_registry
    case,ws,db,reg,parent,old=empty_reset;initialize_library_registry(reg)
    status=inspect_storage(ws,database=db)
    assert status['can_setup_again'],status
    assert ro._read(parent/'state.json')==old


def test_orphan_sqlite_shm_still_blocks_setup(empty_reset):
    case,ws,db,reg,parent,old=empty_reset;db.with_name(db.name+'-shm').write_bytes(b'orphan-shm')
    status=inspect_storage(ws,database=db)
    assert not status['can_setup_again'] and ro._read(parent/'state.json')==old
