"""F12: atomic publication and rollback preserve foreign names and import bytes."""
import ctypes
import errno
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace

import pytest
from app import folder_import as fi, import_publication as pub
from tests.backend.test_0562_process_recovery import isolated_process_environment


def seed(tmp_path, name='J', content=b'synthetic-import'):
    root = tmp_path / 'stock'
    original = root / '.incoming' / name / 'Original'
    original.mkdir(parents=True)
    source = original / 'S.JPG'; source.write_bytes(content)
    target = root / '2030' / 'T.JPG'
    plan = [dict(source_relative_path='S.JPG', destination_relative_path='2030/T.JPG',
                 size_bytes=len(content), sha256=hashlib.sha256(content).hexdigest())]
    return root, original, source, target, plan


def evidence(tmp_path, **data):
    data['files'] = {str(p.relative_to(tmp_path)): {'sha256': hashlib.sha256(p.read_bytes()).hexdigest(),
                    'inode': p.stat().st_ino, 'nlink': p.stat().st_nlink}
                    for p in tmp_path.rglob('*') if p.is_file() and not p.is_symlink()}
    (tmp_path / 'f12-evidence.json').write_text(json.dumps(data, indent=2))


def test_normal_publication_keeps_inode_and_completes_callback(tmp_path):
    root, original, source, target, plan = seed(tmp_path)
    identity = source.stat().st_ino; called = []
    fi.move_import_into_workspace(original, root, plan, post_move_callback=lambda p: called.append(p))
    assert target.read_bytes() == b'synthetic-import' and target.stat().st_ino == identity
    assert target.stat().st_nlink == 1 and not original.exists()
    assert called == [plan]
    assert json.loads((original.parent / 'move-journal.json').read_text())['files'][0]['inode'][1] == identity
    evidence(tmp_path, callback_count=len(called))


@pytest.mark.parametrize('kind', ['file', 'symlink', 'hardlink', 'directory'])
def test_late_target_collision_never_overwrites_or_removes_source(tmp_path, monkeypatch, kind):
    root, original, source, target, plan = seed(tmp_path)
    foreign = tmp_path / 'foreign'; foreign.write_bytes(b'synthetic-foreign')
    real = pub._native_rename; reached = []
    def boundary(*args):
        reached.append(True)
        if kind == 'file': target.write_bytes(b'synthetic-foreign')
        elif kind == 'symlink': target.symlink_to(foreign)
        elif kind == 'hardlink': os.link(foreign, target)
        else: target.mkdir(); (target / 'foreign').write_bytes(b'synthetic-foreign')
        return real(*args)
    monkeypatch.setattr(pub, '_native_rename', boundary)
    with pytest.raises(fi.PipelineError, match='existiert bereits'):
        fi.move_import_into_workspace(original, root, plan)
    assert reached and source.read_bytes() == b'synthetic-import'
    assert (target / 'foreign' if kind == 'directory' else target).read_bytes() == b'synthetic-foreign'
    assert foreign.read_bytes() == b'synthetic-foreign'
    assert (original.parent / 'move-journal.json').is_file()
    evidence(tmp_path, collision=kind)


@pytest.mark.parametrize('key', ['source_relative_path', 'destination_relative_path'])
@pytest.mark.parametrize('value', ['', '../foreign', '/absolute', 'a//b', 'a\\b'])
def test_invalid_paths_are_rejected_before_publication(tmp_path, key, value):
    root, original, source, target, plan = seed(tmp_path)
    plan[0][key] = value
    with pytest.raises(fi.PipelineError, match='Unsicherer relativer Importpfad'):
        fi.move_import_into_workspace(original, root, plan)
    assert source.read_bytes() == b'synthetic-import' and not target.exists()


@pytest.mark.parametrize('kind', ['source', 'source_parent', 'target_parent', 'source_hardlink'])
def test_symlinks_and_unowned_source_aliases_fail_closed(tmp_path, kind):
    root, original, source, target, plan = seed(tmp_path)
    foreign = tmp_path / 'foreign'; foreign.mkdir()
    alias = foreign / 'S.JPG'; alias.write_bytes(b'synthetic-import')
    if kind == 'source': source.unlink(); source.symlink_to(alias)
    elif kind == 'source_parent':
        original.rename(original.with_name('saved')); original.symlink_to(foreign, target_is_directory=True)
    elif kind == 'target_parent': target.parent.symlink_to(foreign, target_is_directory=True)
    else: os.link(source, foreign / 'alias')
    with pytest.raises((fi.PipelineError, OSError)):
        fi.move_import_into_workspace(original, root, plan)
    assert alias.read_bytes() == b'synthetic-import'
    assert source.read_bytes() == b'synthetic-import'
    assert not (foreign / 'T.JPG').exists()


def test_second_collision_rolls_back_first_without_clobbering(tmp_path, monkeypatch):
    root, original, source, target, plan = seed(tmp_path)
    (original / 'B.JPG').write_bytes(b'other')
    plan.append(dict(source_relative_path='B.JPG', destination_relative_path='2030/B.JPG',
                     size_bytes=5, sha256=hashlib.sha256(b'other').hexdigest()))
    real = pub._native_rename
    def boundary(sfd, s, dfd, d):
        if d == 'B.JPG': (target.parent / d).write_bytes(b'foreign-B')
        return real(sfd, s, dfd, d)
    monkeypatch.setattr(pub, '_native_rename', boundary)
    with pytest.raises(fi.PipelineError): fi.move_import_into_workspace(original, root, plan)
    assert source.read_bytes() == b'synthetic-import'
    assert (original / 'B.JPG').read_bytes() == b'other'
    assert (target.parent / 'B.JPG').read_bytes() == b'foreign-B' and not target.exists()
    evidence(tmp_path, rollback='first file restored; foreign second target retained')


def test_rollback_late_source_collision_preserves_both_files_and_sqlite(tmp_path, monkeypatch):
    import sqlite3
    root, original, source, target, plan = seed(tmp_path)
    db = tmp_path / 'test.sqlite3'
    with sqlite3.connect(db) as c: c.execute('CREATE TABLE completed(value TEXT)')
    real = pub._native_rename
    def boundary(sfd, s, dfd, d):
        if d == 'S.JPG': source.write_bytes(b'foreign-original-name')
        return real(sfd, s, dfd, d)
    monkeypatch.setattr(pub, '_native_rename', boundary)
    def callback(_):
        with sqlite3.connect(db) as c:
            c.execute("INSERT INTO completed VALUES('pending')")
            raise RuntimeError('synthetic database failure')
    with pytest.raises(fi.PipelineError, match='Rollback unvollständig'):
        fi.move_import_into_workspace(original, root, plan, post_move_callback=callback)
    assert source.read_bytes() == b'foreign-original-name'
    assert target.read_bytes() == b'synthetic-import'
    assert (original.parent / 'move-journal.json').is_file()
    with sqlite3.connect(db) as c:
        assert c.execute('SELECT COUNT(*) FROM completed').fetchone()[0] == 0
        assert c.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
    evidence(tmp_path, rollback='conflict retained with journal; database rolled back')


def test_fsync_failure_after_rename_retains_original_and_journal(tmp_path, monkeypatch):
    root, original, source, target, plan = seed(tmp_path)
    rename = pub._native_rename; fsync = os.fsync; armed = False; fired = False
    def published(*a):
        nonlocal armed
        result = rename(*a); armed = True; return result
    def failure(fd):
        nonlocal fired
        if armed and not fired:
            fired = True; raise OSError(errno.EIO, 'synthetic directory sync failure')
        return fsync(fd)
    monkeypatch.setattr(pub, '_native_rename', published)
    monkeypatch.setattr(os, 'fsync', failure)
    with pytest.raises(OSError): fi.move_import_into_workspace(original, root, plan)
    assert fired and source.read_bytes() == b'synthetic-import' and not target.exists()
    assert (original.parent / 'move-journal.json').is_file()


@pytest.mark.parametrize('number', [errno.ENOSYS, errno.EINVAL, errno.EOPNOTSUPP, errno.EACCES, errno.EROFS])
def test_native_errors_never_fall_back_to_overwriting_rename(tmp_path, monkeypatch, number):
    root, original, source, target, plan = seed(tmp_path)
    def unsupported(*a): ctypes.set_errno(number); return -1
    monkeypatch.setattr(ctypes, 'CDLL', lambda *a, **k: SimpleNamespace(renameat2=unsupported, renameatx_np=unsupported))
    with pytest.raises(fi.PipelineError, match='verweigert'):
        fi.move_import_into_workspace(original, root, plan)
    assert source.read_bytes() == b'synthetic-import' and not target.exists()
    assert (original.parent / 'move-journal.json').is_file()


@pytest.mark.parametrize('identical', [False, True])
def test_two_processes_publish_same_target_at_shared_barrier(tmp_path, identical):
    a = seed(tmp_path, 'A', b'synthetic-A')
    b = seed(tmp_path, 'B', b'synthetic-A' if identical else b'synthetic-B')
    script = tmp_path / 'publisher.py'
    script.write_text('''import json,sys,time
from pathlib import Path
from app import folder_import as fi,import_publication as pub
source,root,control=map(Path,sys.argv[1:4]);plan=json.loads(sys.argv[4]);real=pub._native_rename
def barrier(*args):
 (control/'ready').write_text('ready')
 deadline=time.monotonic()+15
 while not (control.parent/'go').exists():
  assert time.monotonic()<deadline
  time.sleep(.01)
 return real(*args)
pub._native_rename=barrier
try:fi.move_import_into_workspace(source,root,plan);result={'published':True}
except fi.PipelineError as e:result={'published':False,'error':str(e)}
(control/'result.json').write_text(json.dumps(result))
''')
    processes = []
    try:
        for i, fixture in enumerate([a, b]):
            control = tmp_path / str(i); control.mkdir()
            processes.append(subprocess.Popen([sys.executable, str(script), str(fixture[1]), str(fixture[0]), str(control), json.dumps(fixture[4])], stdout=subprocess.PIPE, stderr=subprocess.PIPE))
        deadline = time.monotonic() + 20
        while not all((tmp_path / str(i) / 'ready').exists() for i in range(2)):
            assert all(p.poll() is None for p in processes)
            assert time.monotonic() < deadline
            time.sleep(.01)
        (tmp_path / 'go').write_text('go')
        for p in processes:
            stdout, stderr = p.communicate(timeout=20); assert p.returncode == 0, (stdout, stderr)
        results = [json.loads((tmp_path / str(i) / 'result.json').read_text()) for i in range(2)]
        assert sum(r['published'] for r in results) == 1
        winner = next(i for i, r in enumerate(results) if r['published']); loser = 1 - winner
        assert a[3].read_bytes() == (b'synthetic-A' if identical or winner == 0 else b'synthetic-B')
        assert [a, b][loser][2].read_bytes() == (b'synthetic-A' if identical or loser == 0 else b'synthetic-B')
        assert not [a, b][winner][2].exists()
        assert (a[1].parent / 'move-journal.json').is_file() and (b[1].parent / 'move-journal.json').is_file()
        evidence(tmp_path, publications=results, identical=identical)
    finally:
        for p in processes:
            if p.poll() is None: p.kill(); p.communicate(timeout=5)


def test_linux_cross_filesystem_refuses_without_copy_fallback(tmp_path):
    assert sys.platform == 'linux', 'BLOCKED: actual Linux second filesystem required'
    root, original, source, target, plan = seed(tmp_path)
    with tempfile.TemporaryDirectory(prefix='bibliothekar-f12-', dir='/dev/shm') as temporary:
        destination = Path(temporary) / 'T.JPG'
        assert destination.parent.stat().st_dev != source.stat().st_dev
        owned = {**plan[0], 'inode': pub.import_identity(source, plan[0])}
        with pytest.raises(fi.PipelineError, match='demselben Dateisystem'):
            pub.publish_import_file(source, destination, owned)
        assert source.read_bytes() == b'synthetic-import' and not destination.exists()


@pytest.mark.parametrize('platform', ['linux', 'darwin'])
def test_missing_native_symbol_fails_closed(tmp_path, monkeypatch, platform):
    root, original, source, target, plan = seed(tmp_path)
    monkeypatch.setattr(pub.sys, 'platform', platform)
    monkeypatch.setattr(ctypes, 'CDLL', lambda *a, **k: SimpleNamespace())
    with pytest.raises(fi.PipelineError, match='nicht verfügbar'):
        fi.move_import_into_workspace(original, root, plan)
    assert source.read_bytes() == b'synthetic-import' and not target.exists()


def test_directory_descriptor_never_follows_replaced_parent_symlink(tmp_path, monkeypatch):
    root, original, source, target, plan = seed(tmp_path)
    external = tmp_path / 'external'; external.mkdir()
    (external / 'T.JPG').write_bytes(b'foreign-external')
    real = pub._native_rename
    def changed(*args):
        target.parent.rename(root / 'saved-parent')
        target.parent.symlink_to(external, target_is_directory=True)
        return real(*args)
    monkeypatch.setattr(pub, '_native_rename', changed)
    with pytest.raises((fi.PipelineError, OSError)):
        fi.move_import_into_workspace(original, root, plan)
    assert (external / 'T.JPG').read_bytes() == b'foreign-external'
    assert (root / 'saved-parent' / 'T.JPG').read_bytes() == b'synthetic-import'
    assert (original.parent / 'move-journal.json').is_file()
    evidence(tmp_path, parent_swap='pinned directory used; unknown rollback path blocked')


@pytest.mark.parametrize('boundary', ['import.publish_before', 'import.publish_after', 'import.rollback_after'])
def test_real_sigkill_around_atomic_publication_and_three_startups(tmp_path, boundary):
    from tests.backend.test_0562_process_recovery import run_case, hash_file, business_rows
    output, case, data, before, crashed, restarts = run_case(tmp_path, 'import', boundary)
    for record, state in restarts: assert record['returncode'] == 0, record
    assert business_rows(restarts[0][1]) == business_rows(restarts[1][1]) == business_rows(restarts[2][1])
    for name, digest in data['expected'].items():
        assert hash_file(case / 'card' / name) == digest
        assert any(hash_file(p) == digest for p in (case / 'workspace').rglob('*.JPG'))
    assert list(case.rglob('move-journal.json'))
