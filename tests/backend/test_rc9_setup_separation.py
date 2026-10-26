"""Regression tests for independent archives, old F14 bindings and setup."""
import pytest
from app import root_operations as ro
from app.managed_storage_health import inspect_storage
from app.storage_warning_ui import storage_warning_html
from tests.backend.test_rc6_legacy_setup import legacy
from tests.backend.test_rc7_reset_states import technical_registry
from tests.backend.test_rc5_practice_followup import setup_child

@pytest.mark.parametrize('state',['legacy_roots','technical_control'])
def test_populated_unregistered_archive_allows_first_library_setup(legacy,monkeypatch,state):
    case,ws,db,reg,parent,old=legacy
    archive=case/'archive'
    picture=archive/'old-photo.JPG'
    picture.write_bytes(b'old archive photography must survive')
    monkeypatch.setenv('KAMERA_ARCHIVE_ROOT',str(archive))
    technical_registry(case,ws,db,reg)
    if state=='technical_control':
        old={'format':1,'workspace':ro._identity(ws),'generation':0,
             'libraries':{},'bindings':{str(ws):ro._identity(ws)}}
        ro._write(parent/'state.json',old)
    health=inspect_storage(ws,database=db)
    assert health['can_setup_again'],health
    assert not any(i['code']=='catalog_unavailable' for i in health['issues']),health
    result=setup_child(case,case/('archive-'+state),'api-reset')
    assert result['ready'] and result['onboarding'] and result['error'] is None,result
    assert picture.read_bytes()==b'old archive photography must survive'

def test_stale_root_bootstrap_requires_explicit_rebind(legacy,monkeypatch):
    case,ws,db,reg,parent,old=legacy
    monkeypatch.setenv('KAMERA_ARCHIVE_ROOT',str(case/'archive'))
    for name in ('SD Card Backups','Library Workspaces','Metadata Correction','Trash'):
        (ws/name).mkdir()
    state=ro._read(parent/'state.json')
    state['storage_initialization']={'phase':'initializing','names':state['storage_names'],'database':str(db)}
    ro._write(parent/'state.json',state)
    health=inspect_storage(ws,database=db)
    assert not health['can_initialize'] and health['can_setup_again'],health
    result=setup_child(case,case/'stale-root-reset','api-reset')
    assert result['ready'] and result['onboarding'] and result['error'] is None,result

def test_recovery_entry_is_visible_even_if_preserved_media_blocks_reset(legacy,monkeypatch):
    case,ws,db,reg,parent,old=legacy
    monkeypatch.setenv('KAMERA_ARCHIVE_ROOT',str(case/'archive'))
    (ws/'real-media.JPG').write_bytes(b'preserve')
    health=inspect_storage(ws,database=db)
    assert not health['can_setup_again'] and not health['can_initialize'],health
    html=storage_warning_html(health)
    assert 'id="storage-recovery-open"' in html
    assert 'id="storage-recovery-panel"' in html
    assert 'id="storage-initialize"' not in html
    assert (ws/'real-media.JPG').read_bytes()==b'preserve'
