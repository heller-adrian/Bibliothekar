"""Explicit retry after real process death; archive remains externally writable.

B is an explicitly injected QA comparison. Native C never silently falls back.
Historical automatic-resume assertions are preserved under qa/f13/history.
"""
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import pytest

from app import ssd_archive_guard as guard
from app import ssd_release as release
from app import ssd_release_background as background
from app.database import database_connection
from qa.f13.test_f13_ssd_guard import RehashOnly, release_fixture


def journal(db):
    with database_connection(db) as connection:
        return {table: [dict(row) for row in connection.execute(
            f'SELECT * FROM {table} ORDER BY id'
        )] for table in ('event_ssd_releases', 'event_ssd_release_files',
                        'event_ssd_release_assets')}


def files(ws, archive):
    return {name: {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
                   for p in sorted(root.rglob('*')) if p.is_file()}
            for name, root in [('ssd', ws), ('archive', archive)]}


@pytest.mark.parametrize('mode', ['B', 'C_native'])
@pytest.mark.parametrize('conflict', [None, 'ssd_B', 'archive_A', 'archive_B'])
def test_explicit_retry_after_sigkill_rechecks_entire_journal(tmp_path, monkeypatch, mode, conflict):
    if mode == 'C_native':
        assert sys.platform == 'linux', 'BLOCKED: native Linux/inotify required'
    else:
        monkeypatch.setattr(guard, 'InotifyWatcher', RehashOnly)
    db, ws, archive, rel = release_fixture(tmp_path)
    before = files(ws, archive)
    task = background.enqueue_release(db, 'j', 'e')
    marker = tmp_path / 'first-unlink-committed'
    script = tmp_path / 'kill_release.py'
    script.write_text('''import os, signal, sys
from pathlib import Path
from app import ssd_archive_guard as guard, ssd_release_background as bg
from app.database import database_connection
db, ws, archive, marker = map(Path, sys.argv[1:5])
if sys.argv[5] == 'B':
 from qa.f13.test_f13_ssd_guard import RehashOnly
 guard.InotifyWatcher = RehashOnly
real = guard.ArchiveGuard.check
def committed_boundary(self):
 real(self)
 with database_connection(db) as c:
  row = c.execute('SELECT deleted_file_count FROM event_ssd_releases').fetchone()
 if row and row['deleted_file_count'] == 1:
  marker.write_text(str(os.getpid()))
  os.kill(os.getpid(), signal.SIGSTOP)
  raise RuntimeError('unexpected continuation')
guard.ArchiveGuard.check = committed_boundary
bg.process_release(db, ws, archive, bg.claim_release(db))
''')
    process = subprocess.Popen([sys.executable, str(script), str(db), str(ws),
                                str(archive), str(marker), mode],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               start_new_session=True)
    try:
        deadline = time.monotonic() + 20
        while not marker.exists() and process.poll() is None and time.monotonic() < deadline:
            time.sleep(.01)
        assert marker.exists(), process.communicate(timeout=1)
        os.killpg(process.pid, signal.SIGKILL)
        stdout, stderr = process.communicate(timeout=5)
        assert process.returncode == -signal.SIGKILL, (stdout, stderr)
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=5)
    partial = journal(db)
    assert partial['event_ssd_releases'][0]['deleted_file_count'] == 1
    assert not (ws / 'Arbeitsbereich' / rel / 'A.JPG').exists()
    assert (ws / 'Arbeitsbereich' / rel / 'B.JPG').read_bytes() == b'synthetic-B'
    assert len(partial['event_ssd_release_files']) == 2
    after_kill = files(ws, archive)
    restarts = []
    for index in range(3):
        # Independent interpreters execute the actual queue-recovery routine.
        result = subprocess.run([sys.executable, '-c', '''import json,sys
from pathlib import Path
from app.ssd_release_background import recover_releases,claim_release,get_release_task
db=Path(sys.argv[1]); count=recover_releases(db)
assert claim_release(db) is None
print(json.dumps({'recovered':count,'task':get_release_task(db,'j','e')}))
''', str(db)], capture_output=True, text=True, timeout=20, check=True)
        state = json.loads(result.stdout)
        assert state['recovered'] == (1 if index == 0 else 0)
        assert state['task']['id'] == task['id']
        assert state['task']['status'] == 'failed'
        assert 'Keine automatische Fortsetzung' in state['task']['error_message']
        assert 'nicht wiederhergestellt' in state['task']['error_message']
        assert journal(db) == partial
        assert files(ws, archive) == after_kill
        restarts.append(state)

    if conflict:
        target = ((ws / 'Arbeitsbereich' / rel / 'B.JPG') if conflict == 'ssd_B'
                  else archive / rel / ('A.JPG' if conflict == 'archive_A' else 'B.JPG'))
        target.write_bytes(b'X' * len(target.read_bytes()))
    pre_retry = files(ws, archive)
    explicitly_requested = background.enqueue_release(db, 'j', 'e')
    assert explicitly_requested['id'] != task['id']
    claimed = background.claim_release(db)
    assert claimed['id'] == explicitly_requested['id']
    checked_archive = []
    checked_source = []
    unlinked = []
    control_unlinks = []
    real_verify = guard.ArchiveGuard.verify
    real_source_verify = release._verify_regular_file
    real_unlink = Path.unlink
    def verify(self, relative, *args, **kwargs):
        checked_archive.append(str(relative))
        return real_verify(self, relative, *args, **kwargs)
    def verify_source(path, *args, **kwargs):
        if Path(path).is_relative_to(ws):
            checked_source.append(str(path))
        return real_source_verify(path, *args, **kwargs)
    def unlink(path, *args, **kwargs):
        if path.is_relative_to(ws):
            unlinked.append(str(path))
        else:
            # F14 also removes its completed private reservation receipts.
            # Keep these distinct from the SSD unlink assertions below.
            from app.root_operations import _control_location
            assert path.is_relative_to(_control_location(ws))
            control_unlinks.append(str(path))
        return real_unlink(path, *args, **kwargs)
    monkeypatch.setattr(guard.ArchiveGuard, 'verify', verify)
    monkeypatch.setattr(release, '_verify_regular_file', verify_source)
    monkeypatch.setattr(Path, 'unlink', unlink)
    background.process_release(db, ws, archive, claimed)
    finished = background.get_release_task(db, 'j', 'e')
    final = journal(db)
    assert final['event_ssd_releases'][0]['id'] == partial['event_ssd_releases'][0]['id']
    assert len(final['event_ssd_releases']) == 1
    assert len(final['event_ssd_release_files']) == 2
    assert [(row['id'], row['expected_sha256']) for row in final['event_ssd_release_files']] == [
        (row['id'], row['expected_sha256']) for row in partial['event_ssd_release_files']]
    assert not (ws / 'Arbeitsbereich' / rel / 'A.JPG').exists()
    assert files(ws, archive)['archive'] == pre_retry['archive']
    if conflict:
        assert finished['status'] == 'failed'
        assert unlinked == []
        assert files(ws, archive)['ssd'] == pre_retry['ssd']
    else:
        assert finished['status'] == 'completed'
        assert finished['result']['released'] is True
        assert finished['result']['details']['deleted_file_count'] == 1
        assert finished['result']['details']['already_released_file_count'] == 1
        assert {Path(row['source_relative_path']).name: row['status']
                for row in final['event_ssd_release_files']} == {
                    'A.JPG': 'already_released', 'B.JPG': 'deleted'}
        assert not (ws / 'Arbeitsbereich' / rel / 'B.JPG').exists()
        assert {str(Path(rel) / name) for name in ['A.JPG', 'B.JPG']} <= set(checked_archive)
        assert str(ws / 'Arbeitsbereich' / rel / 'B.JPG') in checked_source
        assert unlinked == [str(ws / 'Arbeitsbereich' / rel / 'B.JPG')]
        assert background.recover_releases(db) == 0
        assert background.claim_release(db) is None
        with pytest.raises(ValueError, match='bereits freigegeben'):
            background.enqueue_release(db, 'j', 'e')
    with database_connection(db) as connection:
        old = connection.execute('SELECT status FROM ssd_release_tasks WHERE id=?', (task['id'],)).fetchone()
        assert old['status'] == 'failed'
        assert connection.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
    (tmp_path / 'followup-evidence.json').write_text(json.dumps({
        'mode': mode, 'conflict': conflict, 'kill': {'pid': process.pid, 'returncode': process.returncode},
        'before': before, 'after_kill': after_kill, 'journal_after_kill': partial,
        'restarts': restarts, 'before_explicit_retry': pre_retry,
        'final_files': files(ws, archive), 'final_journal': final, 'final_task': finished,
        'archive_checked': checked_archive, 'source_checked': checked_source, 'unlinked': unlinked, 'control_unlinks': control_unlinks,
    }, indent=2))


@pytest.mark.parametrize('conflict', [False, True])
def test_C_native_worker_releases_watches_without_restricting_external_edits(tmp_path, monkeypatch, conflict):
    assert sys.platform == 'linux', 'BLOCKED: native Linux/inotify required'
    db, ws, archive, rel = release_fixture(tmp_path)
    path = archive / rel / 'A.JPG'
    before_modes = {str(p): p.stat().st_mode for p in [archive, path.parent, path]}
    before_xattrs = {str(p): {k: os.getxattr(p, k) for k in os.listxattr(p)} for p in [archive, path]}
    def watches():
        result = []
        for fd in Path('/proc/self/fd').iterdir():
            try:
                if 'inotify' in os.readlink(fd): result.append(fd.name)
            except FileNotFoundError: pass
        return result
    baseline = watches()
    real_check = guard.ArchiveGuard.check
    changed = False
    # A writer opened before the worker must remain writable, including after failure.
    with path.open('r+b', buffering=0) as writer:
        def interleave(self):
            nonlocal changed
            if conflict and not changed:
                changed = True
                writer.seek(0); writer.write(b'X' * 11); os.fsync(writer.fileno())
            return real_check(self)
        monkeypatch.setattr(guard.ArchiveGuard, 'check', interleave)
        task = background.enqueue_release(db, 'j', 'e')
        background.process_release(db, ws, archive, background.claim_release(db))
        state = background.get_release_task(db, 'j', 'e')
        assert state['status'] == ('failed' if conflict else 'completed')
        assert watches() == baseline
        assert {p: Path(p).stat().st_mode for p in before_modes} == before_modes
        assert {p: {k: os.getxattr(p, k) for k in os.listxattr(p)} for p in before_xattrs} == before_xattrs
        writer.seek(0); writer.write(b'editable!!!'); os.fsync(writer.fileno())
    assert path.read_bytes() == b'editable!!!'
    moved = path.with_name('externally-renamed.JPG')
    path.rename(moved)
    moved.unlink()
    if conflict:
        assert (ws / 'Arbeitsbereich' / rel / 'A.JPG').read_bytes() == b'synthetic-A'
        assert (ws / 'Arbeitsbereich' / rel / 'B.JPG').read_bytes() == b'synthetic-B'
    (tmp_path / 'followup-evidence.json').write_text(json.dumps({
        'conflict': conflict, 'task': task['id'], 'final_status': state['status'],
        'inotify_fds_before': baseline, 'inotify_fds_after': watches(),
        'permissions_unchanged': True, 'xattrs_unchanged': True,
        'external_write_rename_delete_succeeded': True,
    }, indent=2))
