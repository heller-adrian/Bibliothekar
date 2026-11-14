"""TrueNAS RC1 ARC-001: synthetic registered archive, never NAS data."""
import hashlib
import shutil

import pytest

from app import library_registry, operation_health, root_operations
from app.archive_release_stock import verify_archive_release_copies, verify_archive_release_removal
from app.database import database_connection
from app.event_change_apply import EventChangeApplyError, confirm_event_change, finish_event_change, verify_event_change
from app.event_change_request import get_event_change_files, propose_archived_event_deletion
from app.storage_anchors import pin
from app.storage_config import LEGACY_STORAGE_DEFAULTS
from tests.backend.test_0271_archive_assistant import _seed


@pytest.fixture
def deletion(tmp_path, monkeypatch, request):
    config = tmp_path / 'settings.json'
    config.write_text('{}')
    registry = tmp_path / 'registry.sqlite3'
    workspace = tmp_path / 'workspace'
    for name in LEGACY_STORAGE_DEFAULTS.values():
        (workspace / name).mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv('KAMERA_CONFIG', str(config))
    monkeypatch.setenv('KAMERA_REGISTRY_DATABASE', str(registry))
    monkeypatch.setenv('KAMERA_WORKSPACE', str(workspace))
    db, workspace, archive, folder, family, other_family, incoming = _seed(tmp_path, full_archive_triplet=True)
    with database_connection(db) as connection:
        original = dict(connection.execute('SELECT * FROM files WHERE family_id=?', (family,)).fetchone())
        original.pop('id')
        for index in range(1, 16):
            row = dict(original)
            relative = f'2026/{folder}/Alle/synthetic-{index}.JPG'
            content = f'synthetic archive bytes {index}'.encode()
            row.update(original_relative_path=relative, current_relative_path=relative,
                       original_filename=f'synthetic-{index}.JPG', size_bytes=len(content),
                       sha256_original=hashlib.sha256(content).hexdigest(),
                       sha256_current=hashlib.sha256(content).hexdigest())
            columns = ','.join(row)
            connection.execute(f'INSERT INTO files({columns}) VALUES ({",".join("?" for _ in row)})', tuple(row.values()))
            (archive / relative).write_bytes(content)
        event = dict(connection.execute("SELECT * FROM events WHERE id='archive'").fetchone())
        event.update(id='unrelated-archive', job_id='new', name='Unrelated archive event', folder_name='07-24 - Other',
                     start_datetime='2026-07-24T00:00:00', end_datetime='2026-07-24T23:59:59')
        connection.execute(f'INSERT INTO events({",".join(event)}) VALUES ({",".join("?" for _ in event)})', tuple(event.values()))
        connection.execute("INSERT INTO event_assignments(event_id,family_id,file_id,assignment_source,created_at) "
                           "VALUES ('unrelated-archive',?,NULL,'date_range',?)", (other_family, event['created_at']))
        connection.execute("UPDATE files SET current_relative_path='2026/07-24 - Other/All/retained.JPG', "
                           "current_root_kind='camera_archive' WHERE family_id=?", (other_family,))
    other = archive / '2026/07-24 - Other/All/retained.JPG'
    other.parent.mkdir(parents=True)
    (workspace / 'Arbeitsbereich' / incoming).rename(other)
    with root_operations.reserve(workspace, library_id='main', kind='startup', paths=[workspace]):
        pass
    library_registry.initialize_library_registry(registry)
    library_registry.ensure_library_identity(db, 'main')
    library_registry.register_library(registry, library_id='main', display_name='Synthetic ARC-001',
                                     database_path=db, workspace_root=workspace,
                                     work_root=workspace / 'Arbeitsbereich', archive_root=archive, is_main=True)
    pin(workspace)
    from app.global_library_inventory import register_analysis_inventory, promote_family_ids_owned
    with database_connection(db) as connection:
        rows = [dict(row) for row in connection.execute(
            'SELECT files.*,file_families.family_key FROM files JOIN file_families ON file_families.id=files.family_id')]
    for job_id, event_id, ids in [('old', 'archive', [family]), ('new', 'unrelated-archive', [other_family])]:
        members = [row for row in rows if row['job_id'] == job_id]
        register_analysis_inventory(registry, library_id='main', job_id=job_id, source_identity='synthetic-' + job_id,
                                    source_path='/synthetic/' + job_id,
                                    analysis={'files': [{'family_key': row['family_key'], 'relative_path': row['original_relative_path'],
                                                         'media_type': row['media_type']} for row in members]},
                                    checksums={row['original_relative_path']: row['sha256_original'] for row in members},
                                    sizes={row['original_relative_path']: row['size_bytes'] for row in members})
        promote_family_ids_owned(registry, database_path=db, library_id='main', event_id=event_id, family_ids=ids)
    from app import main
    from app.library_context import resolve_library_context
    for key, value in {'WORKSPACE_PATH': workspace, 'DATABASE_FILE': db, 'REGISTRY_DATABASE_FILE': registry, 'ARCHIVE_ROOT': archive,
                       'CONFIG_PATH': config, 'MAIN_LIBRARY_CONTEXT': resolve_library_context(registry, 'main')}.items():
        monkeypatch.setattr(main, key, value)
    from types import SimpleNamespace
    # macOS's /var temporary alias must not be mistaken for an admitted root.
    monkeypatch.setattr(main, '_COMPATIBILITY_DIRECTORY', SimpleNamespace(name=str(tmp_path.resolve() / 'views')))
    if getattr(request, 'param', None) == 'no_event':
        from app.event_timeline import normalize_no_event_segments, replace_event_segments
        with database_connection(db) as connection:
            connection.execute("UPDATE events SET event_kind='no_event',timeline_model='segments' WHERE id='archive'")
            replace_event_segments(
                connection, event_id='archive', job_id='old',
                segments=normalize_no_event_segments([{'day_key': '2026-07-22'}]),
                now=event['created_at'],
            )
    proposed = propose_archived_event_deletion(db, 'old', 'archive')
    cr_id = proposed['change_request_id']
    confirm_event_change(db, cr_id, archive, workspace)
    return db, workspace, archive, cr_id, folder, other


def manual_delete(case):
    db, workspace, archive, cr_id, folder, _ = case
    rows = get_event_change_files(db, cr_id)
    assert len(rows) == 16
    for row in rows:
        target = workspace / 'SD-Kartensicherungen' / row['workspace_release_path']
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(archive / row['old_path'], target)
    assert verify_archive_release_copies(db, archive, workspace, cr_id)['complete']
    for row in rows:
        (archive / row['old_path']).unlink()
    assert verify_archive_release_removal(db, archive, workspace, cr_id)['complete']
    shutil.rmtree(archive / '2026' / folder)


@pytest.mark.parametrize('deletion', ['event', 'no_event'], indirect=True)
def test_registered_sixteen_file_deletion_finishes(deletion):
    db, workspace, archive, cr_id, _, other = deletion
    manual_delete(deletion)
    verification = verify_event_change(db, cr_id, archive, workspace)
    assert verification['complete'] and verification['verified_file_count'] == 16
    result = finish_event_change(db, cr_id, archive, workspace)
    assert result['event_deleted'] and result['verified_file_count'] == 16
    assert finish_event_change(db, cr_id, archive, workspace) == result
    assert operation_health.inspect(workspace)['writes_allowed']
    assert other.read_bytes() == b'neu'


def test_early_finish_does_not_trap_verified_deletion(deletion):
    db, workspace, archive, cr_id, _, _ = deletion
    with pytest.raises(EventChangeApplyError):
        finish_event_change(db, cr_id, archive, workspace)
    manual_delete(deletion)
    assert verify_event_change(db, cr_id, archive, workspace)['complete']
    assert finish_event_change(db, cr_id, archive, workspace)['event_deleted']


def test_verified_delete_resumes_original_finish_reservation(deletion, monkeypatch):
    from app import archive_staging, main
    db, workspace, archive, cr_id, _, other = deletion
    manual_delete(deletion)
    assert verify_event_change(db, cr_id, archive, workspace)['verified_file_count'] == 16
    cleanup = archive_staging.cleanup_archive_change_staging

    def interrupted(*args, **kwargs):
        raise RuntimeError('synthetic interruption immediately before archive DB commit')

    monkeypatch.setattr(archive_staging, 'cleanup_archive_change_staging', interrupted)
    with pytest.raises(RuntimeError, match='synthetic interruption'):
        finish_event_change(db, cr_id, archive, workspace)
    original = operation_health.inspect(workspace)['reservations']
    assert len(original) == 1 and not original[0]['live']
    assert original[0]['ids'] == {'cr_id': cr_id, 'function': 'app.event_change_apply.finish_event_change'}
    import threading
    outside = []
    def fenced_cleanup(*args, **kwargs):
        def unrelated_request():
            status = operation_health.inspect(workspace)
            outside.append(any(issue.get('phase') == 'domain_recovery_in_progress' for issue in status['issues']))
            try:
                operation_health.require_write(workspace, candidate={'_resources': {'library:main', 'central_stock'}})
            except root_operations.RootOperationError as error:
                outside.append('operation_recovery_required' in str(error))
            else:
                outside.append(False)
        thread = threading.Thread(target=unrelated_request)
        thread.start()
        thread.join(timeout=5)
        assert not thread.is_alive()
        return cleanup(*args, **kwargs)
    monkeypatch.setattr(archive_staging, 'cleanup_archive_change_staging', fenced_cleanup)
    result = main.api_archive_change(cr_id)
    import json
    assert json.loads(result.body)['event_deleted']
    assert operation_health.inspect(workspace)['writes_allowed']
    assert outside == [True, True]
    assert other.exists()


@pytest.mark.parametrize('deletion', ['event', 'no_event'], indirect=True)
@pytest.mark.parametrize('phase', ['before_commit', 'after_commit'])
def test_sigkill_restart_repeats_exact_archive_completion(deletion, tmp_path, phase):
    import json
    import os
    from pathlib import Path
    import signal
    import subprocess
    import sys
    from app import main
    db, workspace, archive, cr_id, _, other = deletion
    manual_delete(deletion)
    assert verify_event_change(db, cr_id, archive, workspace)['complete']
    checkpoint = tmp_path / 'crash-checkpoint'
    case = tmp_path / 'crash-case.json'
    case.write_text(json.dumps({'db': str(db), 'workspace': str(workspace), 'archive': str(archive),
                               'cr_id': cr_id, 'phase': phase, 'checkpoint': str(checkpoint)}))
    worker = Path(__file__).with_name('rc2_archive_finish_worker.py')
    process = subprocess.run([sys.executable, str(worker), str(case)], timeout=30, capture_output=True,
                             env={**os.environ, 'PYTHONPATH': str(Path(__file__).resolve().parents[2])})
    assert process.returncode == -signal.SIGKILL, process.stderr.decode()
    assert checkpoint.read_text() == phase
    orphan = operation_health.inspect(workspace)['reservations']
    assert len(orphan) == 1 and orphan[0]['ids']['cr_id'] == cr_id and not orphan[0]['live']
    nonce = orphan[0]['reservation_id']
    reservation_path = Path(orphan[0]['path'])
    unchanged = reservation_path.read_bytes()
    with pytest.raises(main.HTTPException) as unrelated:
        main.api_archive_change(cr_id + '-other')
    assert unrelated.value.status_code == 409 and reservation_path.read_bytes() == unchanged
    resumed = []
    original = root_operations.validate_active_roots

    # Inspect the actual active lease, without replacing its root checks.
    from unittest.mock import patch
    def observe():
        for record in root_operations._ACTIVE.get():
            if record['ids'].get('function') == 'app.event_change_apply.finish_event_change':
                resumed.append((record['reservation_id'], record['_resumed']))
        return original()
    with patch.object(root_operations, 'validate_active_roots', observe):
        result = json.loads(main.api_archive_change(cr_id).body)
    assert result['event_deleted'] and result['verified_file_count'] == 16
    assert resumed and all(value == (nonce, True) for value in resumed)
    assert json.loads(main.api_archive_change(cr_id).body) == result
    assert operation_health.inspect(workspace)['writes_allowed']
    assert other.read_bytes() == b'neu'
    assert not list(root_operations._control_location(workspace).glob('domain-recovery-intent-*.json'))
    with database_connection(db) as connection:
        assert connection.execute("SELECT COUNT(*) FROM audit_log WHERE action='archived_event_deleted_after_release'").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM events WHERE id='unrelated-archive'").fetchone()[0] == 1
        assert connection.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        assert not connection.execute('PRAGMA foreign_key_check').fetchall()
    from app.global_library_inventory import occurrence_key
    from app.library_registry import get_source_family_local_claims
    registry = main.REGISTRY_DATABASE_FILE
    claims = get_source_family_local_claims(registry, [occurrence_key('main', 'old', 'ALT'), occurrence_key('main', 'new', 'NEU')], 'main')
    assert occurrence_key('main', 'old', 'ALT') not in claims
    assert claims[occurrence_key('main', 'new', 'NEU')]['event_id'] == 'unrelated-archive'


def test_unrelated_orphan_stays_fenced(deletion):
    from app import main
    db, workspace, _, cr_id, _, _ = deletion
    with pytest.raises(RuntimeError):
        with root_operations.reserve(workspace, library_id='main', database=db,
                                     kind='unknown-synthetic-operation', ids={'id': 'unrelated'}):
            raise RuntimeError('synthetic unknown operation')
    records = {path: path.read_bytes() for path in root_operations._control_location(workspace).glob('operation-*.json')}
    with pytest.raises(main.HTTPException) as error:
        main.api_archive_change(cr_id)
    assert error.value.status_code == 409
    assert records == {path: path.read_bytes() for path in records}
    assert not operation_health.inspect(workspace)['writes_allowed']


def test_completed_delete_rechecks_retained_bytes(deletion):
    db, workspace, archive, cr_id, _, _ = deletion
    manual_delete(deletion)
    assert verify_event_change(db, cr_id, archive, workspace)['complete']
    result = finish_event_change(db, cr_id, archive, workspace)
    assert result['event_deleted']
    with database_connection(db) as connection:
        relative = connection.execute("SELECT current_relative_path FROM files WHERE job_id='old' ORDER BY id LIMIT 1").fetchone()[0]
    target = workspace / 'SD-Kartensicherungen' / relative
    target.write_bytes(b'changed synthetic copy')
    with pytest.raises(EventChangeApplyError, match='archive_completion_return_copy_changed'):
        finish_event_change(db, cr_id, archive, workspace)
    assert target.read_bytes() == b'changed synthetic copy'


def test_http_library_view_verifies_finishes_and_repeats(deletion):
    from fastapi.testclient import TestClient
    from app import main
    db, workspace, archive, cr_id, _, _ = deletion
    client = TestClient(main.app)
    url = '/api/change-requests/' + cr_id
    early = client.post(url + '/archive', json={})
    assert early.status_code == 400, early.text
    assert operation_health.inspect(workspace)['writes_allowed']
    manual_delete(deletion)
    verified = client.post(url + '/verify', json={})
    assert verified.status_code == 200 and verified.json()['verified_file_count'] == 16, verified.text
    finished = client.post(url + '/archive', json={})
    assert finished.status_code == 200 and finished.json()['event_deleted'], finished.text
    repeated = client.post(url + '/archive', json={})
    assert repeated.status_code == 200 and repeated.json() == finished.json(), repeated.text
