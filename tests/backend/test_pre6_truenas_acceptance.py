"""Synthetic reproduction of all physical/plan boundaries in the Pre.5 report."""
from pathlib import Path
import hashlib
import json
import os
import pytest

from app.database import (database_connection, initialize_database, create_planned_event,
                          assign_free_families_to_existing_no_event)
from app.event_structure import build_event_preview
from app.sort_plan import build_event_sort_plan
from app.sort_apply import prepare_sort_run, execute_sort_run, CONFIRMATION_PHRASE
from app.central_stock_reconcile import reconcile_central_free_stock
from app.external_changes import list_external_change_state
from app.workspace_layout import ensure_workspace_layout
from tests.backend.legacy_storage_fixture import provision_legacy_storage
from tests.backend.test_0412_consistency_semantics import _seed_free_file


def seed_collection(tmp_path, monkeypatch):
    db = tmp_path / 'catalog.sqlite3'
    ws = tmp_path / 'workspace'; ws.mkdir()
    monkeypatch.setenv('KAMERA_WORKSPACE', str(ws))
    monkeypatch.setenv('KAMERA_CONFIG', str(tmp_path / 'settings.json'))
    (tmp_path / 'settings.json').write_text('{}')
    monkeypatch.setenv('KAMERA_REGISTRY_DATABASE', str(tmp_path / 'registry.sqlite3'))
    from app.library_registry import initialize_library_registry
    initialize_library_registry(tmp_path / 'registry.sqlite3')
    provision_legacy_storage(ws)
    layout = ensure_workspace_layout(ws)
    initialize_database(db)
    central = Path(layout['backup_root'])
    old = []
    for i in range(8):
        fid, file_id, rel = _seed_free_file(db, family_key=f'old{i}', filename=f'OLD{i}.JPG',
                                         day='2026-07-22', data=f'old-{i}'.encode())
        path = central / rel; path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f'old-{i}'.encode()); old.append(fid)
    preview = build_event_preview({'event_kind':'no_event', 'no_event_segments':[
        {'day_key':'2026-07-22', 'start_time':'00:00', 'end_time':'23:59'}]},
        [{'family_id':fid, 'selected_capture_time':'2026-07-22T12:00:00'} for fid in old])
    event = create_planned_event(db, 'J', preview)['parent_event']
    plan = build_event_sort_plan(db, 'J', event['id'], ws)
    assert plan['summary']['ready'], plan['blockers']
    run = prepare_sort_run(db, 'J', event['id'], ws, expected_plan_token=plan['plan_token'],
                           confirmation_phrase=CONFIRMATION_PHRASE)
    execute_sort_run(db, run['id'], ws)
    incoming = []
    for i in range(16):
        fid, file_id, rel = _seed_free_file(db, family_key=f'new{i}', filename=f'NEW{i}.JPG',
                                         day='2026-07-24', data=f'new-{i}'.encode())
        path = central / rel; path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f'new-{i}'.encode()); incoming.append((fid, file_id, rel))
    return db, ws, central, event, incoming


def bytes_at(root):
    return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file() and not p.name.startswith('.')}


def extend(db, event, incoming):
    return assign_free_families_to_existing_no_event(db, 'J', event['id'],
        [{'day_key':'2026-07-24', 'start_time':'00:00', 'end_time':'23:59'}],
        family_ids=[fid for fid, _, _ in incoming])


def test_applied_extension_keeps_sixteen_unmoved_files_out_of_external_drift(tmp_path, monkeypatch):
    db, ws, central, event, incoming = seed_collection(tmp_path, monkeypatch)
    before = bytes_at(ws)
    assert reconcile_central_free_stock(db, ws, library_id='main')['misplaced_file_count'] == 0
    result = extend(db, event, incoming)
    assert result['resort_required']
    assert bytes_at(ws) == before, 'Saving a plan physically changed files'
    for _ in range(2):
        observed = reconcile_central_free_stock(db, ws, library_id='main')
        assert observed['misplaced_file_count'] == 0, observed
        assert list_external_change_state(db)['required_count'] == 0
        assert bytes_at(ws) == before
    plan = build_event_sort_plan(db, 'J', event['id'], ws, allow_reapply=True)
    assert plan['summary']['ready'], plan['blockers']
    planned = {int(item['file_id']):item for item in plan['files']}
    records = []
    with database_connection(db) as c:
        for family_id, file_id, rel in incoming:
            row = c.execute('SELECT current_relative_path,sha256_current,size_bytes FROM files WHERE id=?',(file_id,)).fetchone()
            records.append({'family_id':family_id,'file_id':file_id,'physical_path':str(central / rel),
                'catalogue_path':row['current_relative_path'],'planned_path':planned[file_id]['destination_relative_path'],
                'sha256':row['sha256_current'],'size':row['size_bytes'],'mutation':'pending_apply'})
    (Path(os.environ.get('AUDIT_OUTPUT',str(tmp_path))) / 'pre6-sixteen-unmoved-files.json').write_text(
        json.dumps({'kind':'synthetic_reproduction_not_NAS_inventory','files':records},indent=2))


@pytest.mark.parametrize('when', ['before_save', 'after_save'])
def test_pending_extension_never_hides_real_external_move(tmp_path, monkeypatch, when):
    db, ws, central, event, incoming = seed_collection(tmp_path, monkeypatch)
    if when == 'after_save': extend(db, event, incoming)
    _, file_id, rel = incoming[0]
    wrong = central / '2026/2026-07-25/NEW0.JPG'; wrong.parent.mkdir(parents=True)
    (central / rel).rename(wrong)
    if when == 'before_save': extend(db, event, incoming)
    for _ in range(2):
        observed = reconcile_central_free_stock(db, ws, library_id='main')
        assert observed['misplaced_file_count'] == 1, observed
    with database_connection(db) as c:
        notices = c.execute("SELECT file_id FROM external_change_notices WHERE status='open' AND kind='placement_conflict'").fetchall()
    assert [int(n['file_id']) for n in notices] == [file_id]
    assert wrong.read_bytes() == b'new-0'


def test_extension_apply_preserves_bytes_then_two_catalogue_reopens(tmp_path, monkeypatch):
    from app.workspace_reconcile import (build_workspace_reconcile_plan,
        prepare_workspace_reconcile_run, execute_workspace_reconcile_run)
    db, ws, central, event, incoming = seed_collection(tmp_path, monkeypatch)
    extend(db, event, incoming)
    plan = build_workspace_reconcile_plan(db, 'J', event['id'], ws)
    assert plan['summary']['ready'], plan['blockers']
    run = prepare_workspace_reconcile_run(db, 'J', event['id'], ws,
        expected_plan_token=plan['plan_token'], confirmation_phrase=CONFIRMATION_PHRASE)
    execute_workspace_reconcile_run(db, run['id'], ws)
    for _ in range(2):
        assert reconcile_central_free_stock(db, ws, library_id='main')['misplaced_file_count'] == 0
        with database_connection(db) as c:
            assert c.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
            assert c.execute("SELECT status FROM event_mutations").fetchone()[0] == 'completed'
            for _, file_id, rel in incoming:
                actual = c.execute('SELECT current_relative_path,sha256_current FROM files WHERE id=?',(file_id,)).fetchone()
                target = Path(plan['target_root']) / actual['current_relative_path']
                assert hashlib.sha256(target.read_bytes()).hexdigest() == actual['sha256_current']
                assert not (central / rel).exists()


def test_prior_applied_member_moved_out_is_still_a_conflict(tmp_path, monkeypatch):
    db, ws, central, event, incoming = seed_collection(tmp_path, monkeypatch)
    extend(db, event, incoming)
    with database_connection(db) as c:
        old = c.execute("SELECT id,current_relative_path FROM files WHERE original_filename='OLD0.JPG'").fetchone()
    original = Path(build_event_sort_plan(db, 'J', event['id'], ws, allow_reapply=True)['target_root']) / old['current_relative_path']
    wrong = central / '2026/2026-07-22/OLD0.JPG'; wrong.parent.mkdir(parents=True, exist_ok=True)
    original.rename(wrong)
    assert reconcile_central_free_stock(db, ws, library_id='main')['misplaced_file_count'] == 1
    assert wrong.read_bytes() == b'old-0'


@pytest.mark.parametrize('case_only', [False, True])
def test_sort_collision_preserves_all_bytes_and_catalogue(tmp_path, monkeypatch, case_only):
    from app.workspace_reconcile import build_workspace_reconcile_plan
    db, ws, central, event, incoming = seed_collection(tmp_path, monkeypatch)
    filename = 'OLD0.jpg' if case_only else 'OLD0.JPG'
    fid, file_id, rel = _seed_free_file(db, family_key='collision', filename=filename,
        day='2026-07-24', data=b'different-camera-image')
    source = central / rel; source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b'different-camera-image')
    assign_free_families_to_existing_no_event(db, 'J', event['id'],
        [{'day_key':'2026-07-24', 'start_time':'00:00', 'end_time':'23:59'}], family_ids=[fid])
    before = bytes_at(ws)
    with database_connection(db) as c:
        before_rows = [tuple(r) for r in c.execute('SELECT * FROM files ORDER BY id')]
    for _ in range(2):
        plan = build_workspace_reconcile_plan(db, 'J', event['id'], ws)
        assert not plan['summary']['ready']
        collisions = [b for b in plan['blockers'] if b['code'] == 'duplicate_destination']
        assert collisions and len(collisions[0]['sources']) == 2
        assert not collisions[0]['duplicate_content_verified']
        assert bytes_at(ws) == before
        with database_connection(db) as c:
            assert [tuple(r) for r in c.execute('SELECT * FROM files ORDER BY id')] == before_rows


def test_identical_content_import_partition_uses_hash_not_name():
    from app.folder_import import partition_import_entries
    digest = hashlib.sha256(b'photo').hexdigest()
    entries = [{'relative_path':'another-name.JPG','size_bytes':5,'sha256':digest},
               {'relative_path':'same-name.JPG','size_bytes':5,'sha256':hashlib.sha256(b'other').hexdigest()}]
    new, duplicates, details = partition_import_entries(entries, {(5,digest)})
    assert [e['relative_path'] for e in duplicates] == ['another-name.JPG']
    assert [e['relative_path'] for e in new] == ['same-name.JPG']



def test_existing_pre5_false_notices_resolve_only_after_physical_recheck(tmp_path, monkeypatch):
    from app import central_stock_reconcile as cs
    db, ws, central, event, incoming = seed_collection(tmp_path, monkeypatch)
    extend(db, event, incoming)
    original = cs._pending_no_event_family_ids
    with monkeypatch.context() as old:
        old.setattr(cs, '_pending_no_event_family_ids', lambda connection: set())
        assert cs.reconcile_central_free_stock(db, ws, library_id='main')['misplaced_file_count'] == 16
    assert len(list_external_change_state(db)['required']) == 16
    before = bytes_at(ws)
    assert cs.reconcile_central_free_stock(db, ws, library_id='main')['misplaced_file_count'] == 0
    assert list_external_change_state(db)['required_count'] == 0
    assert bytes_at(ws) == before


def test_invalid_pending_snapshot_is_never_a_free_stock_certificate(tmp_path, monkeypatch):
    db, ws, central, event, incoming = seed_collection(tmp_path, monkeypatch)
    extend(db, event, incoming)
    with database_connection(db) as c:
        c.execute("UPDATE event_mutations SET original_state_json='{}'")
    before = bytes_at(ws)
    with pytest.raises((KeyError, ValueError)):
        reconcile_central_free_stock(db, ws, library_id='main')
    assert bytes_at(ws) == before
