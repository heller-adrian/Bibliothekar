"""A dead RC14 validation intent can expose retry without erasing its evidence."""
import json
from pathlib import Path
import pytest

pytestmark = pytest.mark.usefixtures('isolated_registered_metadata_config')
from tests.backend.test_pre_metadata import real_family
from tests.backend.legacy_storage_fixture import provision_legacy_storage
from app import metadata_correction as mc,root_operations as ro
from app.database import database_connection
from app.storage_config import load_storage_settings
from app.metadata_reintegration_recovery import pending_reservations


@pytest.mark.parametrize('fault',[None,'hash','nonce','generation','unknown_function','journal','missing_database'])
def test_rc14_retry_scope_retains_original_intent(tmp_path,monkeypatch,fault):
    stamp='2025-12-07T15:04:37+13:00'
    db,ws,source,family,task=real_family(tmp_path,stamp)
    provision_legacy_storage(ws)
    mc.apply_metadata_correction(db,task,workspace_root=ws,library_id='main')
    with database_connection(db) as c:
        c.execute('UPDATE file_families SET selected_capture_time=?',(stamp[:19],))
        c.execute('UPDATE files SET selected_capture_time=?',(stamp[:19],))
        receipt=json.loads(c.execute('SELECT verification_json FROM metadata_corrections').fetchone()[0])
        receipt['proposed_datetime']=stamp[:19]
        c.execute('UPDATE metadata_corrections SET verification_json=?',(json.dumps(receipt),))
    with pytest.raises(mc.MetadataCorrectionError):
        # Restore the RC14 failure without invoking pre's repaired qualifier.
        with ro.reserve(ws,library_id='main',database=db,kind='metadata',
                        ids={'function':'app.metadata_correction.reintegrate_library_metadata_family'},
                        paths=[ws,*[ws/n for n in load_storage_settings(workspace_root=ws).values()]]):
            mc.verify_metadata_datetime(source,stamp[:19])
    parent=ro._control_location(ws);operation=next(parent.glob('operation-*.json'))
    state=ro._read(parent/'state.json');record=ro._read(operation)
    # Use the actual registered work/archive roots, not invented substitutes.
    owner=ro._registered(db)
    assert owner and owner['library_id']=='main'
    work=Path(owner['work_root']);archive=Path(owner['archive_root'])
    registry=tmp_path/'bibliothekar-global.sqlite3'
    assert registry.is_file()
    for path in [work,archive]:
        state['bindings'][str(path)]=ro._identity(path);record['bindings'][str(path)]=ro._identity(path)
    ro._write(parent/'state.json',state)
    if fault=='nonce':record['reservation_id']='unsafe'
    if fault=='generation':record['generation'][0]+=1
    if fault=='unknown_function':record['ids']['function']='unknown.operation'
    ro._write(operation,record)
    if fault=='hash':source.write_bytes(b'changed')
    if fault=='journal':
        directory=mc.storage_paths(ws)['metadata_root']/'.swap-journals';directory.mkdir(exist_ok=True);(directory/'unknown.json').write_text('{}')
    # Inspect the actual test registry, including the original RC14 key.
    if fault=='missing_database':db.unlink()
    before=operation.read_bytes();state_before=(parent/'state.json').read_bytes()
    if fault=='unknown_function':assert pending_reservations(ws,registry)==set()
    elif fault:
        with pytest.raises(ro.RootOperationError):pending_reservations(ws,registry)
    else:assert pending_reservations(ws,registry)=={str(operation)}
    if fault is None:
        # The RC14 key lacks family_id. A qualified check must not become a
        # license to start a different F14 mutation before the orphan is retired.
        from app.operation_health import qualified_retry
        with qualified_retry(ws,{str(operation)}):
            with pytest.raises(ro.RootOperationError,match='retry_original_reservation_identity_required'):
                with ro.reserve(ws,library_id='main',database=db,kind='metadata',
                                ids={'function':'app.metadata_correction.reintegrate_library_metadata_family',
                                     'family_id':str(family)},
                                paths=[ws,*[ws/n for n in load_storage_settings(workspace_root=ws).values()]]):
                    pytest.fail('An unrelated file mutation was admitted')
    assert operation.read_bytes()==before and (parent/'state.json').read_bytes()==state_before
    if fault=='missing_database':assert not db.exists()
