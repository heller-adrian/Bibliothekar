"""Disposable RC6 containers only. Never invoke against an installed system."""
import hashlib,json,os,sys
from pathlib import Path
from app import root_operations as ro
from app.managed_storage_health import inspect_storage
from app.storage_config import ENGLISH_STORAGE_DEFAULTS
from app.library_registry import list_libraries
from app.database import database_connection
assert sys.platform=='linux' and os.environ.get('RC6_SYNTHETIC_QA')=='1'
assert (os.geteuid(),os.getegid())==(568,568)
ws=Path('/workspace');db=Path('/database/kamera.sqlite3');reg=Path('/database/global.sqlite3');mode=sys.argv[1]
record=Path('/logs/rc6-setup-original.json')
if mode=='seed-reset':
    assert not any(ws.iterdir()) and not list(db.parent.glob('*.sqlite3'))
    Path('/config/settings.json').write_text('{}')
    for name in ENGLISH_STORAGE_DEFAULTS.values():(ws/name).mkdir()
    with ro.reserve(ws,library_id='main',paths=[ws,*(ws/n for n in ENGLISH_STORAGE_DEFAULTS.values())],database=db,kind='startup',ids={'initialize_storage':True}):pass
    parent=ro._control_location(ws)
    with ro._lock(parent/'state.lock',exclusive=True):
        state=ro._read(parent/'state.json');state['storage_initialization']['phase']='completed';ro._write(parent/'state.json',state)
    record.write_text(json.dumps(state))
    for name in ENGLISH_STORAGE_DEFAULTS.values():
        (ws/name).rename(Path('/logs')/('old-empty-'+name));(ws/name).mkdir()
    result={'seed':'empty synthetic old identity state','old_state_sha256':hashlib.sha256(record.read_bytes()).hexdigest()}
elif mode=='check-reset':
    parent=ro._control_location(ws);state=ro._read(parent/'state.json')
    assert ro._read(parent/state['setup_reset']['history'])==json.loads(record.read_text())
    assert inspect_storage(ws,database=db)['ready']
    result={'confirmed_reset':'PASS','old_identity_evidence_retained':'PASS'}
elif mode=='seed-damage':
    rows=list_libraries(reg,active_only=False,registered_only=True);assert len(rows)==1
    original=Path(rows[0]['work_root'])/'preserved.JPG';original.write_bytes(b'RC6 damaged-installation sentinel')
    (ws/'Trash').rename(Path('/logs/held-Trash'))
    result={'damage':'synthetic removed root with registered library and original retained'}
elif mode=='check-damage':
    health=inspect_storage(ws,database=db)
    assert not health['ready'] and not health['can_initialize'] and not health.get('can_setup_again'),health
    assert not (ws/'Trash').exists() and Path('/logs/held-Trash').is_dir()
    rows=list_libraries(reg,active_only=False,registered_only=True)
    assert (Path(rows[0]['work_root'])/'preserved.JPG').read_bytes()==b'RC6 damaged-installation sentinel'
    result={'damaged_used_installation_blocked':'PASS','original_retained':'PASS','storage':health}
elif mode=='prepare-import':
    # Only the synthetic test's resource budget is zeroed; production defaults
    # and the independent private retention reserve are untouched.
    from app.main import load_settings,CONFIG_PATH
    settings=load_settings();settings['storage']={**settings.get('storage',{}),'processing_buffer_percent':0,'safety_reserve_gib':0}
    CONFIG_PATH.write_text(json.dumps(settings))
    result={'synthetic_import_reserve':0}
elif mode=='check-import':
    rows=list_libraries(reg,active_only=False,registered_only=True);assert len(rows)==1
    with database_connection(Path(rows[0]['database_path'])) as c:
        jobs=c.execute("SELECT id,state,file_count FROM jobs WHERE operation='folder_import'").fetchall()
        assert len(jobs)==1 and jobs[0]['state']=='completed' and jobs[0]['file_count']==1,[tuple(r) for r in jobs]
        assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok' and not c.execute('PRAGMA foreign_key_check').fetchall()
    result={'duplicate_sources_regular_import_count':1,'sqlite':'PASS'}
else:raise AssertionError(mode)
print(json.dumps(result))
