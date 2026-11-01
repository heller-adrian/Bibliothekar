"""Fixed physical names and protection with manual restoration outside the app."""
from pathlib import Path
from contextlib import closing
import hashlib,json,os,signal,sqlite3,subprocess,sys,time
import pytest
from app import main,root_operations as ro
from app.storage_config import ENGLISH_STORAGE_DEFAULTS,LEGACY_STORAGE_DEFAULTS,load_storage_settings,save_storage_settings,storage_paths
from app.workspace_layout import ensure_workspace_layout
from app.managed_storage_health import inspect_storage,require_storage
from app.library_registry import initialize_library_registry,register_library,ensure_library_identity
from app.database import initialize_database
from app.library_context import resolve_library_context


def stable(case):
    files={};dbs={}
    for p in sorted(case.rglob('*')):
        if p.is_symlink():files[str(p.relative_to(case))]={'link':os.readlink(p)}
        elif p.is_file() and not p.name.endswith(('-wal','-shm')):
            files[str(p.relative_to(case))]={'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'inode':p.stat().st_ino}
            if p.suffix=='.sqlite3':
                with closing(sqlite3.connect(p.as_uri()+'?mode=ro',uri=True)) as c:
                    tables=[x[0] for x in c.execute("SELECT name FROM sqlite_master WHERE type='table'")]
                    dbs[str(p.relative_to(case))]={'integrity':c.execute('PRAGMA integrity_check').fetchone()[0],'foreign_keys':c.execute('PRAGMA foreign_key_check').fetchall(),'tables':{t:c.execute('SELECT * FROM "'+t.replace('"','""')+'"').fetchall() for t in tables}}
    return {'files':files,'databases':dbs}


@pytest.fixture
def home(tmp_path,monkeypatch):
    case=tmp_path/'case';case.mkdir();ws=case/'workspace';ws.mkdir();reg=case/'registry.sqlite3';db=case/'main.sqlite3';config=case/'settings.json';config.write_text('{}')
    for key,value in {'KAMERA_WORKSPACE':ws,'KAMERA_CONFIG':config,'KAMERA_REGISTRY_DATABASE':reg}.items():monkeypatch.setenv(key,str(value))
    for name in ENGLISH_STORAGE_DEFAULTS.values():(ws/name).mkdir()
    layout=ensure_workspace_layout(ws);initialize_database(db);ensure_library_identity(db,'main');initialize_library_registry(reg)
    work=Path(layout['workspaces_root'])/'main';work.mkdir();(work/'original.JPG').write_bytes(b'synthetic-original');archive=case/'archive';archive.mkdir()
    register_library(reg,library_id='main',display_name='Synthetic',database_path=db,workspace_root=ws,work_root=work,archive_root=archive,is_main=True)
    with ro.reserve(ws,library_id='main',database=db,paths=list(storage_paths(ws).values()),kind='startup'):pass
    ctx=resolve_library_context(reg,'main')
    for key,value in {'WORKSPACE_PATH':ws,'DATABASE_FILE':db,'REGISTRY_DATABASE_FILE':reg,'CONFIG_PATH':config,'MAIN_LIBRARY_CONTEXT':ctx}.items():monkeypatch.setattr(main,key,value)
    return case,ws,reg,db,ctx


@pytest.mark.parametrize('language',['de','en'])
def test_f14_new_install_names_ignore_ui_and_legacy_environment(tmp_path,monkeypatch,language):
    ws=tmp_path/'workspace';ws.mkdir();monkeypatch.setenv('KAMERA_WORKSPACE',str(ws));monkeypatch.setenv('KAMERA_CONFIG',str(tmp_path/'settings.json'));monkeypatch.setenv('KAMERA_REGISTRY_DATABASE',str(tmp_path/'registry.sqlite3'));monkeypatch.setenv('BIBLIOTHEKAR_DEFAULT_DIRECTORY_LANGUAGE',language)
    assert load_storage_settings()==ENGLISH_STORAGE_DEFAULTS
    assert inspect_storage(ws)['can_initialize']
    ensure_workspace_layout(ws)
    assert {p.name for p in ws.iterdir()}==set(ENGLISH_STORAGE_DEFAULTS.values())
    assert (ws/'Metadata Correction/General').is_dir() and (ws/'Metadata Correction/Batch Correction').is_dir()
    from app.event_naming import normalize_event_naming
    assert normalize_event_naming({})['no_event_label']=='No Event'


@pytest.mark.parametrize('kind',['undated','metadata_general','metadata_multiple','assign_later','released_archive','reversal','restoration','import_protocol','simulated_sd'])
def test_f14_new_subdirectory_names_and_legacy_preservation(tmp_path,kind):
    from app.managed_directory_names import NAME_PAIRS,directory_name
    old,new=NAME_PAIRS[kind]
    assert directory_name(tmp_path,kind)==new
    legacy=tmp_path/old;legacy.mkdir();(legacy/'original.bin').write_bytes(b'synthetic-legacy')
    assert directory_name(tmp_path,kind)==old
    assert not (tmp_path/new).exists()


@pytest.mark.parametrize('entry',['api','helper','internal-settings'])
def test_f14_removed_mutators_never_change_files_or_catalog(home,entry):
    case,ws,reg,db,ctx=home;before=stable(case)
    if entry=='internal-settings':
        with pytest.raises(Exception):save_storage_settings({'trash_directory_name':'Anything'})
    else:
        call=main.api_set_storage_paths if entry=='api' else main._set_storage_paths
        for payload in [{},{'trash_directory_name':'Other'},ENGLISH_STORAGE_DEFAULTS]:
            with pytest.raises(main.HTTPException) as error:call(payload)
            assert error.value.status_code==410
    assert stable(case)==before


def test_f14_settings_ui_has_no_desktop_or_mobile_name_editor():
    from app.ui_shell import BIBLIOTHEKAR_JS,_shell_markup
    BIBLIOTHEKAR_SHELL=_shell_markup("settings",None)
    for token in ['bk-storage-backup-name','bk-storage-workspaces-name','bk-storage-metadata-name','bk-storage-trash-name','bk-storage-save']:
        assert token not in BIBLIOTHEKAR_JS+BIBLIOTHEKAR_SHELL


@pytest.mark.parametrize('variant',['legacy','custom'])
def test_f14_existing_names_never_migrate(tmp_path,monkeypatch,variant):
    ws=tmp_path/'workspace';ws.mkdir();config=tmp_path/'settings.json';names=dict(LEGACY_STORAGE_DEFAULTS)
    if variant=='custom':names['trash_directory_name']='My Old Trash';config.write_text(json.dumps({'storage':names}))
    monkeypatch.setenv('KAMERA_WORKSPACE',str(ws));monkeypatch.setenv('KAMERA_CONFIG',str(config));monkeypatch.setenv('KAMERA_REGISTRY_DATABASE',str(tmp_path/'registry.sqlite3'))
    for name in names.values():(ws/name).mkdir();(ws/name/'original.bin').write_bytes(b'synthetic-legacy')
    initialize_library_registry(tmp_path/'registry.sqlite3')
    from app.managed_directory_names import directory_name
    metadata=storage_paths(ws)['metadata_root']
    for kind in ('metadata_general','metadata_multiple'):(metadata/directory_name(metadata,kind)).mkdir()
    before=stable(tmp_path);ensure_workspace_layout(ws)
    assert load_storage_settings()==names
    assert all((ws/name/'original.bin').read_bytes()==b'synthetic-legacy' for name in names.values())
    assert not any((ws/name).exists() for name in ENGLISH_STORAGE_DEFAULTS.values())


@pytest.mark.parametrize('key',list(ENGLISH_STORAGE_DEFAULTS))
@pytest.mark.parametrize('change',['missing','renamed','replaced','symlink','unreadable'])
def test_f14_known_root_changes_pause_before_claim_and_never_recreate(home,monkeypatch,key,change):
    case,ws,reg,db,ctx=home;root=ws/ENGLISH_STORAGE_DEFAULTS[key];retained=case/('retained-'+key)
    if change=='unreadable':root.chmod(0o000)
    else:
        root.rename(retained)
        if change=='replaced':root.mkdir();(root/'foreign.bin').write_bytes(b'synthetic-foreign')
        if change=='symlink':root.symlink_to(retained,target_is_directory=True)
    try:
        status=inspect_storage(ws,database=db);assert not status['ready'] and not status['can_initialize']
        assert 'recovery_available' not in status and 'empty_creation_available' not in status
        called=[];monkeypatch.setattr(main,'claim_next_job',lambda *a,**k:called.append('claim'))
        with pytest.raises(ro.RootOperationError):main._claim_context_job(ctx)
        assert not called
        with pytest.raises(ro.RootOperationError):ensure_workspace_layout(ws)
        if change in {'missing','renamed'}:assert not root.exists()
        if change=='replaced':assert (root/'foreign.bin').read_bytes()==b'synthetic-foreign'
        (case/'health-result.json').write_text(json.dumps(status,indent=2))
    finally:
        if change=='unreadable':root.chmod(0o775)


def test_f14_unknown_partial_install_is_not_completed_automatically(tmp_path,monkeypatch):
    ws=tmp_path/'workspace';ws.mkdir();(ws/'SD Card Backups').mkdir();(ws/'SD Card Backups/original.JPG').write_bytes(b'synthetic')
    monkeypatch.setenv('KAMERA_CONFIG',str(tmp_path/'missing-settings.json'));monkeypatch.setenv('KAMERA_REGISTRY_DATABASE',str(tmp_path/'registry.sqlite3'));monkeypatch.setenv('KAMERA_WORKSPACE',str(ws))
    before=stable(tmp_path)
    with pytest.raises(ro.RootOperationError):ensure_workspace_layout(ws)
    assert stable(tmp_path)==before and not (ws/'Trash').exists()


def test_f14_warning_and_health_reachable_without_domain_schema_write(home,monkeypatch):
    from fastapi.testclient import TestClient
    case,ws,reg,db,ctx=home;(ws/'SD Card Backups').rename(case/'accidentally-renamed');called=[]
    monkeypatch.setattr(main,'ensure_library_database_schema',lambda *a:called.append('schema'))
    client=TestClient(main.app);page=client.get('/');status=client.get('/api/settings/storage-health');blocked=client.get('/api/jobs')
    assert page.status_code==200 and '<dialog' in page.text and 'storage-protection' in page.text
    assert 'storage-retry' in page.text and '<button disabled' not in page.text
    assert status.status_code==200 and not status.json()['ready']
    assert blocked.status_code==409 and not called
    assert not (ws/'SD Card Backups').exists()
    assert client.put('/api/settings/storage-paths',json={'trash_directory_name':'Other'}).status_code==410


def test_f14_warning_escapes_paths_and_uses_existing_i18n():
    from app.storage_warning_ui import storage_warning_html
    from app.ui_i18n import UI_TRANSLATIONS
    html=storage_warning_html({'issues':[{'path':'<b>synthetic</b>','code':'missing'}]})
    assert '<b>synthetic</b>' not in html and '&lt;b&gt;synthetic&lt;/b&gt;' in html
    assert UI_TRANSLATIONS['Erneut prüfen']=='Check Again'
    assert 'NAS filesystem' in UI_TRANSLATIONS['Bitte stellen Sie den ursprünglichen Ordner gegebenenfalls außerhalb der App im NAS-Dateisystem wieder her. Prüfen Sie die Einbindung und den erwarteten Pfad. Es werden keine Ordner automatisch ersetzt.']
    assert '<button disabled' not in html


def child(case,control,boundary='none',paused=False):
    control.mkdir();worker=Path(__file__).with_name('f14_storage_worker.py');log=(control/'process.log').open('w')
    p=subprocess.Popen([sys.executable,str(worker),str(case),str(control),boundary],stdout=log,stderr=subprocess.STDOUT,env=dict(os.environ),start_new_session=True)
    if paused:
        until=time.monotonic()+20
        while p.poll() is None and time.monotonic()<until:
            if (control/'checkpoint.json').exists():return p,log
            time.sleep(.01)
        if p.poll() is None:os.killpg(p.pid,signal.SIGKILL);p.wait()
        log.close();raise AssertionError((control/'process.log').read_text())
    try:assert p.wait(timeout=30)==0,(control/'process.log').read_text()
    finally:
        if p.poll() is None:os.killpg(p.pid,signal.SIGKILL);p.wait()
        log.close()
    return json.loads((control/'result.json').read_text())


def test_f14_real_new_install_startup_and_three_restarts(tmp_path):
    case=tmp_path/'case';case.mkdir();ws=case/'workspace';ws.mkdir();(case/'settings.json').write_text('{}')
    (case/'database').mkdir();(case/'archive').mkdir()
    for n in range(4):
        result=child(case,tmp_path/f'boot-{n}');assert result['error'] is None,result
        assert all((ws/name).is_dir() for name in ENGLISH_STORAGE_DEFAULTS.values())
        assert not any((ws/name).exists() for name in LEGACY_STORAGE_DEFAULTS.values())
    (tmp_path/'final-state.json').write_text(json.dumps(stable(case),indent=2))


def test_f14_three_actual_startups_do_not_recreate_missing_established_root(home,tmp_path):
    case,ws,reg,db,ctx=home;old=ws/'SD Card Backups';old.rename(case/'old-backups');before=stable(case)
    for n in range(3):
        result=child(case,tmp_path/f'blocked-{n}');assert result['error'] is not None
        assert not old.exists() and stable(case)==before
        assert (ctx.work_root/'original.JPG').read_bytes()==b'synthetic-original'


@pytest.mark.parametrize('boundary',['SD Card Backups','Trash'])
def test_f14_sigkill_during_initialization_preserves_pending_evidence(tmp_path,boundary):
    case=tmp_path/'case';case.mkdir();ws=case/'workspace';ws.mkdir();(case/'settings.json').write_text('{}')
    (case/'database').mkdir();(case/'archive').mkdir()
    p,log=child(case,tmp_path/'kill-point',boundary,paused=True)
    try:os.killpg(p.pid,signal.SIGKILL);assert p.wait(timeout=10)==-9
    finally:log.close()
    parent=case/'database/.bibliothekar-root-control';assert list(parent.rglob('operation-*.json'))
    for n in range(3):
        result=child(case,tmp_path/f'restart-{n}');assert result['error'] is None,result
        assert all((ws/name).is_dir() for name in ENGLISH_STORAGE_DEFAULTS.values())
    assert not list(parent.rglob('operation-*.json'))
    (tmp_path/'preserved-state.json').write_text(json.dumps(stable(case),indent=2))


def test_f14_storage_warning_does_not_bypass_owner_authentication(home,monkeypatch):
    from fastapi.testclient import TestClient
    case,ws,reg,db,ctx=home;(ws/'Trash').rename(case/'old-trash')
    monkeypatch.setenv('BIBLIOTHEKAR_AUTH_TEST_BYPASS','false')
    client=TestClient(main.app)
    before=stable(case)
    assert client.post('/api/settings/storage-recheck').status_code==401
    assert stable(case)==before
    assert client.get('/api/settings/storage-health').status_code==401
    assert client.get('/',follow_redirects=False).status_code==303
    assert client.get('/login').status_code==200


def test_f14_library_images_remain_editable_and_independent_relink_works(home):
    from app.library_registry import update_library_paths
    case,ws,reg,db,ctx=home;db2=case/'second.sqlite3';initialize_database(db2);ensure_library_identity(db2,'second')
    work2=ws/'Library Workspaces/second';work2.mkdir();archive2=case/'archive2';archive2.mkdir();next_archive=case/'new-archive2';next_archive.mkdir()
    register_library(reg,library_id='second',display_name='Second',database_path=db2,workspace_root=ws,work_root=work2,archive_root=archive2)
    with ro.reserve(ws,library_id='main',database=db,paths=[ctx.work_root]):
        image=ctx.work_root/'original.JPG';image.write_bytes(b'synthetic-external-edit');image.rename(ctx.work_root/'edited.JPG')
        (ctx.work_root/'manual-subfolder').mkdir()
        changed=update_library_paths(reg,'second',archive_root=next_archive)
        assert changed['archive_root']==str(next_archive)
    assert (ctx.work_root/'edited.JPG').read_bytes()==b'synthetic-external-edit'
    assert not (ctx.work_root/'original.JPG').exists()


@pytest.mark.parametrize('component',['existing','new','workspace','parent','dangling'])
def test_f14_removed_rename_preserves_foreign_content_at_all_old_symlink_boundaries(home,monkeypatch,component):
    case,ws,reg,db,ctx=home;outside=case/'outside';outside.mkdir();sentinel=outside/'sentinel';sentinel.write_bytes(b'synthetic-foreign');inode=sentinel.stat().st_ino
    if component in {'existing','dangling'}:
        (ws/'Trash').rename(case/'original-trash');(ws/'Trash').symlink_to(outside if component=='existing' else case/'not-present',target_is_directory=True)
    elif component=='new':(ws/'RenamedTrash').symlink_to(outside,target_is_directory=True)
    elif component=='workspace':
        link=case/'alias';link.symlink_to(ws,target_is_directory=True);monkeypatch.setattr(main,'WORKSPACE_PATH',link)
    else:
        link=case/'parent';link.symlink_to(case,target_is_directory=True);monkeypatch.setattr(main,'WORKSPACE_PATH',link/'workspace')
    before=stable(case)
    with pytest.raises(main.HTTPException) as error:main.api_set_storage_paths({'trash_directory_name':'RenamedTrash'})
    assert error.value.status_code==410
    assert sentinel.read_bytes()==b'synthetic-foreign' and sentinel.stat().st_ino==inode
    assert stable(case)==before


def test_f14_metadata_recovery_existing_assertions_with_complete_storage_fixture(tmp_path,monkeypatch):
    # Preserve the original test and every assertion. Only this new probe makes
    # all four required roots explicitly available before starting recovery.
    from tests.backend import test_0561_recovery as original
    seed=original.general_case
    def complete_fixture(*args,**kwargs):
        result=seed(*args,**kwargs);workspace=result[1]
        for root in storage_paths(workspace).values():root.mkdir(exist_ok=True)
        return result
    monkeypatch.setattr(original,'general_case',complete_fixture)
    original.test_startup_recovers_general_swap_before_onboarding_worker(tmp_path,monkeypatch)


def test_f14_capacity_preferences_do_not_prove_a_previous_storage_layout(tmp_path,monkeypatch):
    ws=tmp_path/'workspace';ws.mkdir();config=tmp_path/'settings.json';config.write_text(json.dumps({'storage':{'processing_buffer_percent':5,'safety_reserve_gib':2}}))
    monkeypatch.setenv('KAMERA_WORKSPACE',str(ws));monkeypatch.setenv('KAMERA_CONFIG',str(config));monkeypatch.setenv('KAMERA_REGISTRY_DATABASE',str(tmp_path/'registry.sqlite3'))
    assert inspect_storage(ws)['can_initialize']
    ensure_workspace_layout(ws)
    assert all((ws/name).is_dir() for name in ENGLISH_STORAGE_DEFAULTS.values())


def test_f14_missing_registered_catalog_is_not_reinitialized(home,monkeypatch):
    case,ws,reg,db,ctx=home;retained=case/'retained-main.sqlite3';db.rename(retained);calls=[]
    status=inspect_storage(ws,database=db)
    assert not status['ready'] and any(i['code']=='catalog_unavailable' for i in status['issues'])
    monkeypatch.setattr(main,'initialize_database',lambda *a,**k:calls.append('schema'))
    with pytest.raises(ro.RootOperationError):main.ensure_library_database_schema(ctx)
    assert not calls and not db.exists()


def test_f14_explicit_recheck_after_manual_restoration_retries_actual_startup(home,tmp_path):
    case,ws,reg,db,ctx=home
    original=ctx.work_root/'original.JPG';content=original.read_bytes();inode=original.stat().st_ino
    result=child(case,tmp_path/'manual-recheck','manual-recheck')
    assert result['error'] is None
    assert json.loads((tmp_path/'manual-recheck/rechecks.json').read_text())==[True,True,True]
    assert original.read_bytes()==content and original.stat().st_ino==inode
    evidence=stable(case)
    assert all(d['integrity']=='ok' and not d['foreign_keys'] for d in evidence['databases'].values())
    (tmp_path/'manual-recheck/integrity.json').write_text(json.dumps(evidence,indent=2))


def test_f14_recheck_never_clears_unrelated_recovery_error(home,monkeypatch):
    case,ws,reg,db,ctx=home;before=stable(case)
    monkeypatch.setattr(main,'_STORAGE_STARTUP_PAUSED',False)
    monkeypatch.setattr(main,'DATABASE_INITIALIZATION_ERROR','synthetic unresolved journal')
    calls=[];monkeypatch.setattr(main,'startup_database',lambda:calls.append('unsafe retry'))
    with pytest.raises(main.HTTPException) as error:main.api_recheck_storage()
    assert error.value.status_code==409 and not calls and stable(case)==before


def test_f14_four_empty_directories_are_not_a_startup_mount_certificate(tmp_path,monkeypatch):
    case=tmp_path/'case';case.mkdir();ws=case/'workspace';ws.mkdir()
    private=case/'database';private.mkdir();archive=case/'archive';archive.mkdir()
    for name in ENGLISH_STORAGE_DEFAULTS.values():(ws/name).mkdir()
    monkeypatch.setenv('KAMERA_CONFIG',str(case/'settings.json'))
    monkeypatch.setenv('KAMERA_REGISTRY_DATABASE',str(private/'registry.sqlite3'))
    monkeypatch.setenv('KAMERA_ARCHIVE_ROOT',str(archive))
    before=stable(case)
    result=inspect_storage(ws,database=private/'main.sqlite3')
    assert result['ready'] and result['can_initialize'],result
    assert result['mount_evidence']=='administrator_responsibility'
    assert stable(case)==before


@pytest.mark.parametrize('used',[False,True])
def test_f14_fresh_schema_vs_used_empty_catalogue(tmp_path,monkeypatch,used):
    case=tmp_path/'case';case.mkdir();ws=case/'workspace';ws.mkdir();private=case/'database';private.mkdir();db=private/'main.sqlite3';archive=case/'archive';archive.mkdir()
    monkeypatch.setenv('KAMERA_CONFIG',str(case/'settings.json'));monkeypatch.setenv('KAMERA_REGISTRY_DATABASE',str(private/'registry.sqlite3'));monkeypatch.setenv('KAMERA_ARCHIVE_ROOT',str(archive))
    initialize_database(db)
    if used:
        from app.database import create_job
        create_job(db,job_id='HISTORY',kind='sd_import',trigger_type='manual',operation='folder_import')
    before=stable(case);status=inspect_storage(ws,database=db)
    assert status['can_initialize']==(not used)
    assert stable(case)==before and not list(ws.iterdir())


def test_fresh_technical_schema_starts_with_english_event_defaults(tmp_path):
    case=tmp_path/'case';case.mkdir();(case/'workspace').mkdir();(case/'settings.json').write_text('{}')
    (case/'database').mkdir();(case/'archive').mkdir();initialize_database(case/'database/main.sqlite3')
    result=child(case,tmp_path/'startup')
    assert result['error'] is None,result
    with sqlite3.connect(case/'database/main.sqlite3') as c:
        setting=json.loads(c.execute("SELECT value_json FROM app_settings WHERE setting_key='event_folder_layout_default'").fetchone()[0])
    (case/'fresh-schema-default.json').write_text(json.dumps(setting,indent=2))
    assert setting['input_path']=='All','Fresh technical schema retained German event defaults'
