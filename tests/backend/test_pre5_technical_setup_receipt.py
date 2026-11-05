"""Only completed technical receipts qualify; all history/media gates remain."""
from pathlib import Path
import json
import pytest
from app import root_operations as ro,managed_storage_health as health
from app.operation_health import _TECHNICAL_STARTUP_IDS
from app.storage_config import ENGLISH_STORAGE_DEFAULTS
from app.managed_directory_names import directory_name
from tests.backend.test_rc6_legacy_setup import legacy
from tests.backend.test_rc5_practice_followup import empty_reset


@pytest.fixture
def technical(legacy,monkeypatch):
    from app.database import initialize_database
    from app.library_registry import initialize_library_registry
    case,ws,db,reg,parent,state=legacy
    monkeypatch.setenv('KAMERA_ARCHIVE_ROOT',str(case/'archive'))
    paths=[ws,*(ws/n for n in ENGLISH_STORAGE_DEFAULTS.values())]
    for path in paths[1:]:
        path.mkdir();state['bindings'][str(path)]=ro._identity(path)
    metadata=ws/ENGLISH_STORAGE_DEFAULTS['metadata_directory_name']
    for kind in ('metadata_general','metadata_multiple'):(metadata/directory_name(metadata,kind)).mkdir()
    ro._write(parent/'state.json',state);initialize_database(db);initialize_library_registry(reg)
    with ro.reserve(ws,library_id='main',database=db,kind='startup',ids=_TECHNICAL_STARTUP_IDS,paths=paths):pass
    receipt,=parent.glob('technical-startup-*.json')
    return case,ws,db,reg,parent,receipt


def test_real_technical_receipt_was_old_unknown_evidence_and_survives_two_explicit_resets(technical,monkeypatch):
    _,ws,db,_,parent,receipt=technical
    raw=receipt.read_bytes();state=(parent/'state.json').read_bytes()
    with monkeypatch.context() as old:
        # Reproduce precisely the missing recognition in the old whitelist;
        # no ACL, database, F14 lease or remaining emptiness gate is bypassed.
        old.setattr(health,'_technical_startup_evidence',lambda *args:set())
        assert health.setup_again_evidence(ws,database=db)=={'allowed':False,'reason':'unknown_control_evidence'}
    proof=health.setup_again_evidence(ws,database=db)
    assert proof['allowed'],proof
    assert receipt.read_bytes()==raw and (parent/'state.json').read_bytes()==state
    for _ in range(2):
        ro.reset_empty_storage(ws,db,proof['token'])
        proof=health.setup_again_evidence(ws,database=db);assert proof['allowed'],proof
        assert receipt.read_bytes()==raw
    assert len(list(parent.glob('setup-history-*.json')))==2


@pytest.mark.parametrize('damage',['kind','ids','database','binding','generation','nonce','extra_effect','malformed','unknown_json','open_operation','media','history_digest'])
def test_technical_prefix_never_waives_foreign_or_unresolved_evidence(technical,damage):
    _,ws,db,_,parent,path=technical
    receipt=ro._read(path);record=receipt['reservation']
    if damage=='kind':record['kind']='metadata'
    elif damage=='ids':record['ids']={'technical_setup':True,'protocol':'other'}
    elif damage=='database':record['database']=str(db.with_name('foreign.sqlite3'))
    elif damage=='binding':record['bindings'][str(ws/'Trash')]=[0,123]
    elif damage=='generation':record['generation'][0]+=1
    elif damage=='nonce':record['reservation_id']='f'*32
    elif damage=='extra_effect':record['effect_resources']=['metadata']
    elif damage=='malformed':receipt=[]
    elif damage=='unknown_json':ro._write(parent/'foreign.json',{'format':1})
    elif damage=='open_operation':ro._write(parent/('operation-'+'a'*64+'.json'),record)
    elif damage=='media':(ws/'Trash'/'keep.JPG').write_bytes(b'original media')
    elif damage=='history_digest':
        proof=health.setup_again_evidence(ws,database=db);assert proof['allowed']
        ro.reset_empty_storage(ws,db,proof['token'])
        state=ro._read(parent/'state.json');state['setup_reset']['previous_state_sha256']='0'*64;ro._write(parent/'state.json',state)
    if damage in {'kind','ids','database','binding','generation','nonce','extra_effect','malformed'}:ro._write(path,receipt)
    before={p:p.read_bytes() for p in parent.glob('*.json')}
    proof=health.setup_again_evidence(ws,database=db)
    assert not proof['allowed'],proof
    assert before=={p:p.read_bytes() for p in parent.glob('*.json')}
    with pytest.raises(ro.RootOperationError):ro.reset_empty_storage(ws,db,'not-a-qualified-token')
    assert before=={p:p.read_bytes() for p in parent.glob('*.json')}
    if damage=='media':assert (ws/'Trash'/'keep.JPG').read_bytes()==b'original media'
