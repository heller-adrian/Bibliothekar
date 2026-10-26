"""Two independent chronological clean-slate states; never alter an installed NAS."""
import hashlib,json,os,shutil,sqlite3
from contextlib import closing
from pathlib import Path
import pytest
from app import root_operations as ro
from app.managed_storage_health import inspect_storage
from app.library_registry import initialize_library_registry
from tests.backend.test_rc6_legacy_setup import legacy
from tests.backend.test_rc5_practice_followup import empty_reset,setup_child


def technical_registry(case,ws,db,reg):
    initialize_library_registry(reg)
    with closing(sqlite3.connect(reg)) as c:
        c.execute("INSERT INTO libraries (library_id,display_name,database_path,workspace_root,work_root,archive_root,settings_json,is_main,is_active,is_registered,created_at,updated_at) VALUES ('main','Nicht eingerichtet',?,?,?,?,?,1,1,0,'synthetic','synthetic')",(str(db),str(ws),str(ws/'.bibliothekar-ohne-bibliothek'),str(case/'archive'),json.dumps({'bootstrap':True,'onboarding_required':True})))
        c.commit();c.execute('PRAGMA wal_checkpoint(TRUNCATE)')

@pytest.mark.parametrize('state',['A-roots','A-technical','B-missing'])
def test_two_independent_states_complete_real_onboarding(legacy,monkeypatch,state):
    case,ws,db,reg,parent,old=legacy;monkeypatch.setenv('KAMERA_ARCHIVE_ROOT',str(case/'archive'))
    technical_registry(case,ws,db,reg)
    if state=='A-technical':
        old={'format':1,'workspace':ro._identity(ws),'generation':0,'libraries':{},'bindings':{str(ws):ro._identity(ws)}};ro._write(parent/'state.json',old)
    elif state=='B-missing':shutil.rmtree(parent.parent)
    health=inspect_storage(ws,database=db)
    assert not health['ready'] and not health['can_initialize']
    assert health.get('can_setup_again'),health
    assert all(f['status']=='missing' for f in health['folders'])
    before=reg.read_bytes()
    result=setup_child(case,case/'reset','api-reset');assert result['error'] is None and result['ready'] and result['onboarding'],result
    assert reg.read_bytes()==before
    current=ro._read(parent/'state.json');history=ro._read(parent/current['setup_reset']['history'])
    assert history==(old if state!='B-missing' else {})
    assert current['setup_reset']['bootstrap_registry'][0]['settings_json']==json.dumps({'bootstrap':True,'onboarding_required':True})
    result=setup_child(case,case/'created','onboard');assert result['create_status']==201,result
    for n in range(3):
        boot=setup_child(case,case/f'restart-{n}');assert boot['ready'] and not boot['onboarding'] and boot['error'] is None,boot
    with sqlite3.connect(db) as c:assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok' and not c.execute('PRAGMA foreign_key_check').fetchall()


def test_missing_control_does_not_hide_private_retention(legacy,monkeypatch):
    case,ws,db,reg,parent,old=legacy;monkeypatch.setenv('KAMERA_ARCHIVE_ROOT',str(case/'archive'));shutil.rmtree(parent.parent)
    retained=db.parent/'.bibliothekar-restore-retention';retained.mkdir();(retained/'original.JPG').write_bytes(b'original')
    health=inspect_storage(ws,database=db)
    assert not health['can_initialize'] and not health.get('can_setup_again'),health
    assert (retained/'original.JPG').read_bytes()==b'original'

@pytest.mark.parametrize('missing',[False,True])
@pytest.mark.parametrize('unsafe',['registered','retired','unmarked','catalogue','workspace','retention','open-operation'])
def test_both_states_keep_real_history_blocked(legacy,monkeypatch,missing,unsafe):
    case,ws,db,reg,parent,old=legacy;monkeypatch.setenv('KAMERA_ARCHIVE_ROOT',str(case/'archive'));technical_registry(case,ws,db,reg)
    if missing:shutil.rmtree(parent.parent)
    if unsafe in {'registered','retired','unmarked'}:
        with sqlite3.connect(reg) as c:
            if unsafe=='registered':c.execute('UPDATE libraries SET is_registered=1')
            elif unsafe=='retired':c.execute("UPDATE libraries SET unregistered_at='was-used'")
            else:c.execute("UPDATE libraries SET settings_json='{}'")
    elif unsafe=='catalogue':
        from app.database import initialize_database,create_job
        initialize_database(db);create_job(db,job_id='PRESERVE',source_path=str(ws),working_path=str(ws),kind='sd_import',trigger_type='manual',operation='folder_import')
    elif unsafe=='workspace':(ws/'unidentified-original.JPG').write_bytes(b'keep')
    elif unsafe=='archive':(case/'archive/original.JPG').write_bytes(b'keep')
    elif unsafe=='retention':
        p=db.parent/'.bibliothekar-restore-retention';p.mkdir();(p/'original.JPG').write_bytes(b'keep')
    elif unsafe=='open-operation':
        ro._control(ws);ro._write(parent/'operation-unknown.json',{'keep':'recovery'})
    before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in case.rglob('*.JPG')}
    health=inspect_storage(ws,database=db);assert not health['can_initialize'] and not health.get('can_setup_again'),health
    with pytest.raises(ro.RootOperationError):ro.reset_empty_storage(ws,db,'0'*64)
    assert all(Path(p).exists() and hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in before.items())
    assert not list(parent.glob('setup-history-*.json'))


def test_bootstrap_registry_change_invalidates_confirmation(legacy,monkeypatch):
    case,ws,db,reg,parent,old=legacy;monkeypatch.setenv('KAMERA_ARCHIVE_ROOT',str(case/'archive'));technical_registry(case,ws,db,reg)
    token=inspect_storage(ws,database=db)['setup_token']
    with sqlite3.connect(reg) as c:c.execute("UPDATE libraries SET display_name='concurrent update'")
    with pytest.raises(ro.RootOperationError):ro.reset_empty_storage(ws,db,token)
    assert ro._read(parent/'state.json')==old and not list(parent.glob('setup-history-*.json'))


@pytest.mark.parametrize('missing',[False,True])
@pytest.mark.parametrize('boundary',['reset-history','reset-state'])
def test_two_states_sigkill_and_restarts_preserve_receipts(legacy,monkeypatch,missing,boundary):
    import signal
    case,ws,db,reg,parent,old=legacy;monkeypatch.setenv('KAMERA_ARCHIVE_ROOT',str(case/'archive'));technical_registry(case,ws,db,reg)
    if missing:shutil.rmtree(parent.parent)
    p,log=setup_child(case,case/'killed',boundary,paused=True)
    try:os.killpg(p.pid,signal.SIGKILL);assert p.wait(timeout=10)==-9
    finally:log.close()
    if boundary=='reset-history':setup_child(case,case/'confirmed','api-reset')
    for n in range(3):
        result=setup_child(case,case/f'boot-{n}');assert result['ready'] and result['error'] is None,result
    current=ro._read(parent/'state.json');assert ro._read(parent/current['setup_reset']['history'])==({} if missing else old)

@pytest.mark.parametrize('missing',[False,True])
def test_real_onboarding_read_does_not_turn_empty_registry_into_a_blocker(legacy,monkeypatch,missing):
    from app import main
    case,ws,db,reg,parent,old=legacy;monkeypatch.setenv('KAMERA_ARCHIVE_ROOT',str(case/'archive'))
    if missing:shutil.rmtree(parent.parent)
    assert not reg.exists()
    assert main._onboarding_required()  # Real _connect creates a SQLite header before SELECT fails.
    assert reg.exists()
    with closing(sqlite3.connect(reg.as_uri()+'?mode=ro',uri=True)) as c:
        assert not c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    health=inspect_storage(ws,database=db)
    assert health.get('can_setup_again') if not missing else health['can_initialize'],health
    if not missing:
        result=setup_child(case,case/'confirmed-header','api-reset');assert result['ready'],result
    else:
        result=setup_child(case,case/'fresh-header');assert result['ready'] and result['onboarding'],result
    result=setup_child(case,case/'header-onboard','onboard');assert result['create_status']==201,result

@pytest.mark.parametrize('marker',['user_version','application_id'])
def test_empty_looking_custom_registry_header_stays_blocked(legacy,monkeypatch,marker):
    from app import main
    case,ws,db,reg,parent,old=legacy;monkeypatch.setenv('KAMERA_ARCHIVE_ROOT',str(case/'archive'));main._onboarding_required()
    with closing(sqlite3.connect(reg)) as c:c.execute('PRAGMA '+marker+'=42');c.commit();c.execute('PRAGMA wal_checkpoint(TRUNCATE)')
    health=inspect_storage(ws,database=db);assert not health['can_initialize'] and not health.get('can_setup_again'),health
