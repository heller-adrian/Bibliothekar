"""Bound complete provenance work, not wall time; preserve all safety decisions."""
from collections import Counter
from unittest.mock import patch
import pytest

from app import source_provenance as provenance
from app.database import database_connection
from app.global_library_inventory import backfill_library_inventory
from app.library_registry import LibraryRegistryError
from tests.backend.startup_inventory_fixture import seed


def test_secondary_startup_qualifies_main_once(tmp_path):
    registry,databases=seed(tmp_path/'stock',20)
    calls=Counter();original=provenance.registry_origins
    def observe(path,library):
        calls[library]+=1
        return original(path,library)
    with patch.object(provenance,'registry_origins',side_effect=observe):
        result=backfill_library_inventory(registry,database_path=databases[1],library_id='second',claim_all_owned=False)
    assert result['family_count']==20
    assert calls['main']<=2,dict(calls)


def test_new_projection_reuses_one_complete_authority(tmp_path):
    import sqlite3,json
    from tests.backend.test_rc13_provenance import origin
    registry,databases=seed(tmp_path/'stock',30)
    with sqlite3.connect(registry) as c:
        c.execute('PRAGMA foreign_keys=ON')
        c.execute("DELETE FROM source_backups WHERE backup_id='second:J'")
    before={k:[r for r in rows if not str(r[1] if k=='source_media' else r[0]).startswith('second:')]
            for k,rows in origin(registry).items()}
    original=provenance.registry_origins;calls=Counter()
    def observe(path,library):
        calls[library]+=1;return original(path,library)
    with patch.object(provenance,'registry_origins',side_effect=observe):
        backfill_library_inventory(registry,database_path=databases[1],library_id='second',claim_all_owned=False)
    assert calls['main']<=2,dict(calls)
    after={k:[r for r in rows if not str(r[1] if k=='source_media' else r[0]).startswith('second:')]
           for k,rows in origin(registry).items()}
    # Canonical timestamps may be refreshed by the established registration API;
    # immutable main source rows and membership remain byte-for-byte unchanged.
    for table in ('source_families','source_family_members','source_media'):assert before[table]==after[table]


def test_subsequent_backfill_reads_fresh_main_evidence(tmp_path):
    registry,databases=seed(tmp_path/'stock',25)
    backfill_library_inventory(registry,database_path=databases[1],library_id='second',claim_all_owned=False)
    with database_connection(databases[0]) as c:
        c.execute("UPDATE files SET sha256_original=? WHERE family_id=25",('f'*64,))
    # Even if the damaged main family is not projected locally, the FULL main
    # authority must still block; no old successful view survives this call.
    with database_connection(databases[1]) as c:c.execute('DELETE FROM files WHERE family_id=25')
    with pytest.raises(LibraryRegistryError,match='live member hash'):
        backfill_library_inventory(registry,database_path=databases[1],library_id='second',claim_all_owned=False)


def test_four_thousand_families_have_bounded_full_scans(tmp_path):
    registry,databases=seed(tmp_path/'stock',4000)
    calls=Counter();original=provenance.registry_origins
    def observe(path,library):calls[library]+=1;return original(path,library)
    with patch.object(provenance,'registry_origins',side_effect=observe):
        result=backfill_library_inventory(registry,database_path=databases[1],library_id='second',claim_all_owned=False)
    assert result=={'family_count':4000,'media_count':4000,'claim_count':0}
    assert calls=={'main':2,'second':1},dict(calls)


def test_startup_phase_reports_completion_and_preserves_exceptions(capsys):
    from app.main import _startup_step
    assert _startup_step('probe',lambda:42)==42
    with pytest.raises(ValueError,match='original cause'):
        _startup_step('probe',lambda:(_ for _ in ()).throw(ValueError('original cause')))
    text=capsys.readouterr().out
    assert 'completed in' in text and 'failed after' in text


@pytest.mark.parametrize('setting,expected',[(None,False),('false',False),('true',True),('yes',True),('0',False)])
def test_helper_is_only_enabled_by_explicit_environment(setting,expected):
    import os,subprocess,sys
    env=dict(os.environ)
    env.pop('KAMERA_SOURCE_HELPER_ENABLED',None)
    if setting is not None:env['KAMERA_SOURCE_HELPER_ENABLED']=setting
    value=subprocess.check_output([sys.executable,'-c','from app.container_supervisor import HELPER_ENABLED;print(HELPER_ENABLED)'],env=env,text=True)
    assert value.strip()==str(expected)
