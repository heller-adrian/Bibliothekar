"""Synthetic incomplete reset; original identities and all surviving data protected."""
import json,os,shutil,signal,subprocess,sys,time
from pathlib import Path
import pytest
from app import root_operations as ro,main
from app.managed_storage_health import inspect_storage
from app.storage_config import ENGLISH_STORAGE_DEFAULTS
from tests.backend.test_rc5_practice_followup import empty_reset,setup_child

@pytest.fixture
def legacy(empty_reset):
    case,ws,db,reg,parent,old=empty_reset
    archive=case/'archive';archive.mkdir()
    state=ro._read(parent/'state.json');state.pop('storage_initialization',None)
    state['bindings'][str(archive)]=ro._identity(archive)
    ro._write(parent/'state.json',state)
    for name in ENGLISH_STORAGE_DEFAULTS.values():(ws/name).rmdir()
    return case,ws,db,reg,parent,state


def test_historical_missing_intent_offers_confirmed_setup(legacy,monkeypatch):
    case,ws,db,reg,parent,old=legacy;monkeypatch.setenv('KAMERA_ARCHIVE_ROOT',str(case/'archive'))
    health=inspect_storage(ws,database=db)
    assert not health['ready'] and not health['can_initialize']
    roots=[row for row in health['folders'] if row['key'] in ENGLISH_STORAGE_DEFAULTS]
    children=[row for row in health['folders'] if row['key'] in {'metadata_general','metadata_multiple'}]
    assert len(roots)==4 and all(row['status']=='missing' and row['identity_evidence']=='previously_observed' for row in roots)
    assert len(children)==2 and all(row['status']=='missing' and row['identity_evidence']=='not_observed' for row in children)
    assert health.get('can_setup_again'),health
    assert ro._read(parent/'state.json')==old
    result=setup_child(case,case/'reset','api-reset');assert result['error'] is None and result['ready'] and result['onboarding'],result
    assert ro._read(next(parent.glob('setup-history-*.json')))==old
    created=setup_child(case,case/'onboard','onboard');assert created['create_status']==201 and created['check']['valid'],created


def test_catalog_issue_is_not_duplicated_and_blocker_is_explained(legacy,monkeypatch):
    from app.storage_warning_ui import storage_warning_html
    case,ws,db,reg,parent,old=legacy;archive=case/'archive';(archive/'original.JPG').write_bytes(b'must keep')
    monkeypatch.setenv('KAMERA_ARCHIVE_ROOT',str(archive))
    health=inspect_storage(ws,database=db)
    assert len([i for i in health['issues'] if i['code']=='catalog_unavailable' and i['path']==str(db)])==1,health
    assert health['can_setup_again'],health
    html=storage_warning_html(health)
    assert 'id="storage-initialize"' in html and (archive/'original.JPG').read_bytes()==b'must keep'


@pytest.mark.parametrize('variant',['absent','no_names','partial_phase','partial_names','partial_database'])
def test_legacy_variants_require_complete_independent_root_evidence(legacy,monkeypatch,variant):
    case,ws,db,reg,parent,old=legacy;monkeypatch.setenv('KAMERA_ARCHIVE_ROOT',str(case/'archive'))
    state=dict(old)
    if variant=='no_names':state.pop('storage_names')
    elif variant=='partial_phase':state['storage_initialization']={'phase':'completed'}
    elif variant=='partial_names':state['storage_initialization']={'names':dict(ENGLISH_STORAGE_DEFAULTS)}
    elif variant=='partial_database':state['storage_initialization']={'database':str(db)}
    ro._write(parent/'state.json',state)
    status=inspect_storage(ws,database=db);assert status['can_setup_again'],status
    ro.reset_empty_storage(ws,db,status['setup_token'])
    new=ro._read(parent/'state.json');assert ro._read(parent/new['setup_reset']['history'])==state
    assert new['setup_reset']['database']==str(db)
    assert inspect_storage(ws,database=db)['can_initialize']


@pytest.mark.parametrize('unsafe',['workspace_media','catalogue','registry','f14_library','retention','missing_archive','changed_archive','missing_external','missing_identity','german_bindings','changed_database','changed_names','changed_workspace','operation','symlink','hardlink_config','acl'])
def test_legacy_reset_never_discards_surviving_evidence(legacy,monkeypatch,unsafe):
    case,ws,db,reg,parent,old=legacy;archive=case/'archive';monkeypatch.setenv('KAMERA_ARCHIVE_ROOT',str(archive))
    if unsafe=='workspace_media':(ws/'Trash').mkdir();(ws/'Trash/original.JPG').write_bytes(b'original')
    elif unsafe=='catalogue':
        from app.database import initialize_database,create_job
        initialize_database(db);create_job(db,job_id='PRESERVE',source_path=str(ws),working_path=str(ws),kind='sd_import',trigger_type='manual',operation='folder_import')
    elif unsafe=='registry':
        from app.library_registry import initialize_library_registry
        initialize_library_registry(reg)
        with __import__('sqlite3').connect(reg) as c:c.execute("INSERT INTO canonical_families VALUES ('old-family','fingerprint','now','now')")
    elif unsafe=='f14_library':
        old['libraries']={'main':{'database':str(db)}};ro._write(parent/'state.json',old)
    elif unsafe=='retention':
        p=db.parent/'.bibliothekar-restore-retention';p.mkdir();(p/'original.JPG').write_bytes(b'private')
    elif unsafe=='archive':(archive/'original.JPG').write_bytes(b'archive')
    elif unsafe=='missing_archive':archive.rmdir()
    elif unsafe=='changed_archive':archive.rename(case/'held-archive');archive.mkdir()
    elif unsafe=='missing_external':
        old['bindings'][str(case/'missing-external')]=[1,123];ro._write(parent/'state.json',old)
    elif unsafe=='missing_identity':
        old['bindings'].pop(str(ws/'Trash'));ro._write(parent/'state.json',old)
    elif unsafe=='german_bindings':
        old['bindings'][str(ws/'Papierkorb')]=[1,123];ro._write(parent/'state.json',old)
    elif unsafe=='changed_database':
        old['storage_initialization']={'database':str(case/'different-db/main.sqlite3')};ro._write(parent/'state.json',old)
    elif unsafe=='changed_names':
        old['storage_initialization']={'names':{'trash_directory_name':'Different'}};ro._write(parent/'state.json',old)
    elif unsafe=='changed_workspace':ws.rename(case/'held-workspace');ws.mkdir()
    elif unsafe=='operation':ro._write(parent/'operation-preserve.json',{'unfinished':'must retain'})
    elif unsafe=='symlink':(ws/'Trash').symlink_to(archive,target_is_directory=True)
    elif unsafe=='hardlink_config':os.link(case/'settings.json',case/'settings-hardlink')
    elif unsafe=='acl':
        from app import trash_retention as rt
        monkeypatch.setattr(rt,'check_acl',lambda *a,**kw:(_ for _ in ()).throw(ValueError('foreign ACL writer')))
    raw=(parent/'state.json').read_bytes();health=inspect_storage(ws,database=db)
    assert not health.get('can_setup_again') and not health['can_initialize'],health
    with pytest.raises(ro.RootOperationError):ro.reset_empty_storage(ws,db,'0'*64)
    assert (parent/'state.json').read_bytes()==raw and not list(parent.glob('setup-history-*.json'))


def test_legacy_archive_change_during_reset_preserves_state_and_new_file(legacy,monkeypatch):
    case,ws,db,reg,parent,old=legacy;archive=case/'archive';monkeypatch.setenv('KAMERA_ARCHIVE_ROOT',str(archive))
    token=inspect_storage(ws,database=db)['setup_token'];write=ro._write
    def changed(path,value):
        write(path,value)
        if path.name.startswith('setup-history-'):(archive/'new.JPG').write_bytes(b'foreign archive bytes')
    monkeypatch.setattr(ro,'_write',changed)
    ro.reset_empty_storage(ws,db,token)
    assert (archive/'new.JPG').read_bytes()==b'foreign archive bytes'
    assert ro._read(next(parent.glob('setup-history-*.json')))==old


@pytest.mark.parametrize('point',['reset-history','reset-state'])
def test_legacy_reset_sigkill_and_three_independent_restarts(legacy,monkeypatch,point):
    case,ws,db,reg,parent,old=legacy;monkeypatch.setenv('KAMERA_ARCHIVE_ROOT',str(case/'archive'))
    p,log=setup_child(case,case/'killed',point,paused=True)
    try:os.killpg(p.pid,signal.SIGKILL);assert p.wait(timeout=10)==-9
    finally:log.close()
    if point=='reset-history':
        assert ro._read(parent/'state.json')==old
        status=inspect_storage(ws,database=db);ro.reset_empty_storage(ws,db,status['setup_token'])
    for i in range(3):
        result=setup_child(case,case/('restart-'+str(i)));assert result['ready'] and result['error'] is None,result
    assert ro._read(next(parent.glob('setup-history-*.json')))==old


def test_warning_explains_blocked_state_without_html_injection():
    from app.storage_warning_ui import storage_warning_html
    from app.ui_i18n import I18N_UI_JS
    status={'issues':[{'code':'missing','path':'<img src=x onerror=alert(1)>'}],'can_setup_again':False,'setup_blocker':'<script>unsafe</script>'}
    page=storage_warning_html(status)
    assert '<img src=x' not in page and '<script>unsafe</script>' not in page
    assert 'id="storage-setup-blocker"' in page and 'id="storage-recovery-help"' in page and 'id="storage-initialize"' not in page
    assert 'New setup is currently blocked' in I18N_UI_JS and 'Historical setup records are incomplete or contradictory.' in I18N_UI_JS


def worker(case,output,mode):
    log=output.with_suffix('.log').open('w')
    p=subprocess.Popen([sys.executable,str(Path(__file__).with_name('rc6_legacy_worker.py')),str(case),str(output),mode],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    return p,log


def wait_file(p,path,seconds=25):
    until=time.monotonic()+seconds
    while not path.exists():
        assert p.poll() is None,path.with_suffix('.log').read_text() if path.with_suffix('.log').exists() else str(p.returncode)
        assert time.monotonic()<until,str(path)
        time.sleep(.02)


def test_incomplete_live_wipe_then_process_restart_and_confirmed_onboarding(legacy,monkeypatch):
    from app.database import initialize_database
    case,ws,db,reg,parent,old=legacy;monkeypatch.setenv('KAMERA_ARCHIVE_ROOT',str(case/'archive'))
    # An existing legacy F14 installation can start with intact directories and
    # schema while lacking the newer storage_initialization field entirely.
    for name in ENGLISH_STORAGE_DEFAULTS.values():
        (ws/name).mkdir();old['bindings'][str(ws/name)]=ro._identity(ws/name)
    from app.managed_directory_names import directory_name
    metadata=ws/ENGLISH_STORAGE_DEFAULTS['metadata_directory_name']
    for kind in ('metadata_general','metadata_multiple'):
        (metadata/directory_name(metadata,kind)).mkdir()
    from app.library_registry import initialize_library_registry
    ro._write(parent/'state.json',old);initialize_database(db);initialize_library_registry(reg);(case/'logs').mkdir()
    output=case/'live';p,log=worker(case,output,'live')
    try:
        wait_file(p,output);before=json.loads(output.read_text());assert before['worker_alive'] and not before['state'].get('storage_initialization')
        # Reproduce an incomplete live deletion: open SQLite data are unlinked,
        # config/log/workspace emptied, hidden private F14 evidence survives.
        # This does not claim why the user's private evidence survived deletion.
        for base in [db.parent,case/'logs',ws]:
            for child in list(base.iterdir()):
                if child==parent.parent:continue
                if child.is_dir():shutil.rmtree(child)
                else:child.unlink()
        (case/'settings.json').unlink(missing_ok=True)
        output.with_suffix('.observe').write_text('inspect')
        wait_file(p,output.with_suffix('.observed'));health=json.loads(output.with_suffix('.observed').read_text())
        assert not health['ready'] and not health['can_initialize'] and health['can_setup_again'],health
        assert all(r['status']=='missing' and r['identity_evidence']=='previously_observed' for r in health['folders'])
        # The live admitted worker still owns a shared F14 lock. Even a
        # matching confirmation cannot reset it until that process stops.
        with pytest.raises(ro.RootOperationError):ro.reset_empty_storage(ws,db,health['setup_token'])
        assert not list(parent.glob('setup-history-*.json'))
        os.killpg(p.pid,signal.SIGKILL);assert p.wait(timeout=10)==-9
    finally:
        if p.poll() is None:os.killpg(p.pid,signal.SIGKILL);p.wait()
        log.close()
    saved=ro._read(parent/'state.json')
    for i in range(3):
        dest=case/('blocked-'+str(i));p,log=worker(case,dest,'inspect')
        try:assert p.wait(timeout=30)==0,dest.with_suffix('.log').read_text()
        finally:log.close()
        result=json.loads(dest.read_text());assert not result['database_exists'] and not result['health']['ready'] and result['health']['can_setup_again'],result
        assert ro._read(parent/'state.json')==saved
    dest=case/'confirmed';p,log=worker(case,dest,'confirm')
    try:assert p.wait(timeout=35)==0,dest.with_suffix('.log').read_text()
    finally:log.close()
    result=json.loads(dest.read_text());assert result['health']['ready'] and result['worker_alive'] and result['library']['library']['is_registered'],result
    assert ro._read(next(parent.glob('setup-history-*.json')))==saved


@pytest.mark.parametrize('partial',[{'database':'CURRENT'},False,{'phase':'unknown'},{'names':{'trash_directory_name':'Different'}}])
def test_partial_or_malformed_intent_cannot_replace_missing_root_evidence(legacy,monkeypatch,partial):
    case,ws,db,reg,parent,old=legacy;monkeypatch.setenv('KAMERA_ARCHIVE_ROOT',str(case/'archive'))
    old['storage_initialization']={'database':str(db)} if partial=={'database':'CURRENT'} else partial
    old['bindings'].pop(str(ws/'Trash'));ro._write(parent/'state.json',old)
    status=inspect_storage(ws,database=db);assert not status.get('can_setup_again'),status
    assert ro._read(parent/'state.json')==old


def test_legacy_setup_keeps_authentication_and_csrf(legacy,monkeypatch):
    from fastapi.testclient import TestClient
    case,ws,db,reg,parent,old=legacy;monkeypatch.setenv('KAMERA_ARCHIVE_ROOT',str(case/'archive'))
    monkeypatch.setenv('BIBLIOTHEKAR_AUTH_TEST_BYPASS','false')
    client=TestClient(main.app)
    assert client.get('/api/settings/storage-health').status_code==401
    login=client.post('/auth/login',json={'password':os.environ['BIBLIOTHEKAR_ADMIN_PASSWORD']},headers={'Origin':'http://testserver'})
    assert login.status_code==200,login.text
    payload={'confirmation':'SET UP AGAIN','token':inspect_storage(ws,database=db)['setup_token']}
    assert client.post('/api/settings/storage-initialize',json=payload,headers={'Origin':'http://testserver'}).status_code==403
    assert ro._read(parent/'state.json')==old and not list(parent.glob('setup-history-*.json'))


def test_legacy_warning_delivered_scripts_and_css_are_valid(legacy,monkeypatch,tmp_path):
    from app.storage_warning_ui import storage_warning_html
    from qa.release.check_web_assets import check_pages
    case,ws,db,reg,parent,old=legacy;monkeypatch.setenv('KAMERA_ARCHIVE_ROOT',str(case/'archive'))
    allowed=inspect_storage(ws,database=db);assert allowed['can_setup_again']
    (case/'archive/original.JPG').write_bytes(b'archive must remain')
    assert inspect_storage(ws,database=db)['can_setup_again']
    (ws/'unmanaged-original.JPG').write_bytes(b'workspace data must remain')
    blocked=inspect_storage(ws,database=db);assert not blocked['can_setup_again']
    result=check_pages({'setup_allowed':storage_warning_html(allowed),'setup_blocked':storage_warning_html(blocked)},tmp_path/'assets')
    assert result['pages']==2 and result['scripts']==6 and result['styles']==2
