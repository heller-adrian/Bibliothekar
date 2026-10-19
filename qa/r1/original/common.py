from pathlib import Path
import os,json,hashlib,sys,inspect
from test_process_crashes import invoke,snapshot
from app import main,security
from app.database import database_connection
OUT=Path(os.environ['AUDIT_OUTPUT'])
SECRET='synthetic-phase5-owner-password-2026'

def setup(tmp_path,name,monkeypatch,kind='trash'):
    assert 'BIBLIOTHEKAR_AUTH_TEST_BYPASS' not in os.environ and not security._is_test_bypass()
    case=tmp_path/'case';case.mkdir();ev=OUT/name;ev.mkdir()
    assert invoke(case,'seed',kind,ev/'seed')['returncode']==0
    data=json.loads((case/'case.json').read_text());db=Path(data['db']);ws=Path(data['workspace'])
    from app.library_context import resolve_library_context
    for k,v in dict(DATABASE_FILE=db,REGISTRY_DATABASE_FILE=db.parent/'registry.sqlite3',WORKSPACE_PATH=ws,MAIN_LIBRARY_CONTEXT=resolve_library_context(db.parent/'registry.sqlite3','main'),CONFIG_PATH=db.parent/'settings.json',LOG_PATH=case/'logs').items():monkeypatch.setattr(main,k,v)
    monkeypatch.setattr(main,'current_database_file',lambda:main.current_library_context().database_path)
    monkeypatch.setenv('KAMERA_CONFIG',str(db.parent/'settings.json'));monkeypatch.setenv('BIBLIOTHEKAR_ADMIN_PASSWORD',SECRET)
    monkeypatch.delenv('BIBLIOTHEKAR_ADMIN_PASSWORD_FILE',raising=False)
    security._SESSIONS.clear();security._FAILURES.clear()
    snapshot(case,ev/'before.json')
    (ev/'isolation.json').write_text(json.dumps({'bypass_env_absent':True,'guard_bypass':security._is_test_bypass(),'pytest_current_test_present':bool(os.environ.get('PYTEST_CURRENT_TEST')),'network':'denied','source_writes':'denied','data':'synthetic'}))
    return case,ev,data,db,ws

def finish(case,ev,result):
    snapshot(case,ev/'after.json');(ev/'result.json').write_text(json.dumps(result,indent=2,default=str))

def login(client):
    r=client.post('/auth/login',json={'password':SECRET},headers={'Origin':str(client.base_url).rstrip('/')});assert r.status_code==200,r.text
    return client.cookies.get('bibliothekar_csrf')

def location(fn):
    try:return {'file':str(Path(inspect.getsourcefile(fn)).relative_to(Path(os.environ['AUDIT_SOURCE']))),'function':fn.__name__,'line':inspect.getsourcelines(fn)[1]}
    except Exception:return {'function':repr(fn)}
