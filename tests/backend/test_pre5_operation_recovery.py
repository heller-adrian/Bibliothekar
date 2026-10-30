"""pre.5: reproductions use only pytest's synthetic, registered workspaces."""
from contextlib import closing
from itertools import combinations
import shutil

import pytest
from fastapi.testclient import TestClient

from app import main, root_operations as ro, operation_health as operations
from app.central_stock_reconcile import reconcile_central_free_stock
from app.database import database_connection
from app.library_context import resolve_library_context
from app.storage_config import storage_paths
from tests.backend.test_pre4_operation_separation import ready
from tests.backend.test_f14_root_operations import fixture
from tests.backend.test_0412_consistency_semantics import _seed_free_file
from tests.backend.test_0501_external_event_deletion import _event


def inventory_orphan(ws, db):
    with pytest.raises(RuntimeError, match='synthetic interrupted scan'):
        with ro.reserve(ws, library_id='main', database=db, kind='inventory', ids={
            'function': 'app.central_stock_reconcile.reconcile_central_free_stock',
        }):
            raise RuntimeError('synthetic interrupted scan')
    return tuple(ro._control_location(ws).glob('operation-*.json'))


@pytest.mark.parametrize('refresh', ['false', 'true'])
def test_workspace_get_after_interrupted_inventory(ready, refresh):
    _, ws, _, dbs, _ = ready
    records = inventory_orphan(ws, dbs[0])
    before = {p: p.read_bytes() for p in records}
    # No lifespan: this specifically exercises the original request failure.
    with closing(TestClient(main.app, raise_server_exceptions=False)) as client:
        response = client.get('/api/workspace/summary?physical_refresh=' + refresh)
        assert response.status_code == 200, response.text[:1000]
    assert before == {p: p.read_bytes() for p in records}


@pytest.mark.parametrize('actions', [c for n in (1, 2, 3) for c in combinations(('applied', 'archived', 'day'), n)])
def test_three_reported_file_changes_before_metadata(ready, actions):
    _, ws, reg, dbs, _ = ready
    db = dbs[0]
    context = resolve_library_context(reg, 'main')
    paths = storage_paths(ws)
    general = paths['metadata_root'] / 'Allgemein'
    general.mkdir(exist_ok=True)
    # These production fixture helpers create actual files, catalogue rows,
    # assignments and scan results, not a hypothetical recovery receipt.
    events = {}
    for status, day in [('applied', '2026-07-19'), ('archived', '2026-07-20')]:
        root = context.archive_root if status == 'archived' else context.work_root
        events[status] = _event(db, root, name=status, day=day,
            items=[(status + '.JPG', b'synthetic-' + status.encode(), 'Alle')], status=status)[1]
    _, _, rel = _seed_free_file(db, family_key='day', filename='day.JPG',
        day='2026-07-21', data=b'synthetic-day')
    day_file = paths['backup_root'] / rel
    day_file.parent.mkdir(parents=True, exist_ok=True)
    day_file.write_bytes(b'synthetic-day')
    for action in actions:
        source = day_file if action == 'day' else events[action] / 'Alle' / (action + '.JPG')
        if action == 'archived':
            shutil.copyfile(source, general / source.name)
        else:
            source.rename(general / source.name)
    for _ in range(3):
        result = reconcile_central_free_stock(db, ws, library_id='main')
        assert result['ready'], result
    assert operations.inspect(ws)['writes_allowed'], operations.inspect(ws)
    with database_connection(db) as c:
        assert c.execute('PRAGMA quick_check').fetchone()[0] == 'ok'
    assert (events['archived'] / 'Alle/archived.JPG').read_bytes() == b'synthetic-archived'


def test_inventory_exception_then_retry_does_not_poison_other_library(ready):
    _, ws, reg, dbs, _ = ready
    inventory_orphan(ws, dbs[0])
    context = resolve_library_context(reg, 'second')
    # A read/SQLite-only inventory interruption cannot claim unknown writes
    # throughout another library. All root and generation checks still apply.
    with ro.reserve(ws, library_id='second', database=dbs[1], paths=[context.work_root], kind='plan'):
        with database_connection(dbs[1]) as c:
            c.execute("INSERT INTO settings(key,value) VALUES ('pre5-independent','written')")
