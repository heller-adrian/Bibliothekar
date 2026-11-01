"""Rejected restores must never publish another orphaned writer lease."""
import pytest
from app import root_operations as ro,trash_restore as tr,main
from tests.backend import test_r1_restore_recovery as r1
from tests.backend.test_0562_process_recovery import isolated_process_environment


@pytest.mark.parametrize('failure',['missing','invalid_relative','foreign_target','reserved'])
def test_rejected_restore_keeps_original_evidence_without_new_reservation(tmp_path,monkeypatch,failure):
    case,ev,data,ws=r1.seed(tmp_path,monkeypatch)
    selection=['A.JPG'];foreign=None
    if failure=='missing':selection=['no-such-media.JPG']
    elif failure=='invalid_relative':selection=['../A.JPG']
    elif failure=='foreign_target':
        _,_,_,plans=tr._plan_restore(data['dbs'],ws,relative_paths=selection)
        foreign=plans[0]['target'];foreign.parent.mkdir(parents=True,exist_ok=True);foreign.write_bytes(b'foreign target retained')
    else:assert main.api_restore_trash({'relative_paths':selection})['status']=='queued'
    parent=ro._control_location(ws);before={p.name:p.read_bytes() for p in parent.glob('*.json')}
    original=(ws/'Papierkorb/A.JPG').read_bytes()
    with pytest.raises(r1.TrashError):tr.restore_trash_files(iter(data['dbs']),ws,relative_paths=selection)
    assert {p.name:p.read_bytes() for p in parent.glob('*.json')}==before
    assert (ws/'Papierkorb/A.JPG').read_bytes()==original
    if foreign:assert foreign.read_bytes()==b'foreign target retained'


def test_valid_restore_materializes_database_iterator_once(tmp_path,monkeypatch):
    case,ev,data,ws=r1.seed(tmp_path,monkeypatch)
    result=tr.restore_trash_files(iter(data['dbs']),ws,relative_paths=['A.JPG'])
    assert result['restored_file_count']==1 and not (ws/'Papierkorb/A.JPG').exists()
    assert not list(ro._control_location(ws).glob('operation-*.json'))
    state=r1.starts(case,ev)
    for db in ('kamera.sqlite3','second1.sqlite3'):
        assert sum(x['action']=='trash_file_restored' for x in r1.r.db_rows(state,'audit_log',db))==1
