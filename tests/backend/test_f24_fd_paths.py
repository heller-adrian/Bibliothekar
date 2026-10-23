"""Regression of F24's two path redirections at actual FD operation boundaries."""
import hashlib
import os
from pathlib import Path
import subprocess
import sys

import pytest
from app import main, trash_selective as ts
from app.database import database_connection
from tests.backend.test_f11_trash_reservation import fixture
from tests.backend.test_0562_process_recovery import isolated_process_environment


def external_swap(source, saved, target):
    subprocess.run([sys.executable, '-c',
                    'import os,sys;os.rename(sys.argv[1],sys.argv[2]);os.symlink(sys.argv[3],sys.argv[1])',
                    str(source), str(saved), str(target)], check=True, timeout=10)


@pytest.mark.parametrize('mode', ['selective', 'full', 'nested', 'last_unlink'])
def test_f24_fd_preserves_external_file(tmp_path, monkeypatch, mode):
    case, evidence, data, db, ws = fixture(tmp_path, monkeypatch)
    root = ws / 'Papierkorb'
    bound_identity = (root.stat().st_dev, root.stat().st_ino)
    outside = case / 'outside'; outside.mkdir()
    foreign = outside / 'A.JPG'; raw = b'synthetic-trash-A.JPG'; foreign.write_bytes(raw)
    before = foreign.stat(); digest = hashlib.sha256(raw).hexdigest()
    selected = 'A.JPG'; hit = []
    if mode == 'nested':
        (root / 'nested').mkdir()
        (root / 'A.JPG').rename(root / 'nested/A.JPG')
        selected = 'nested/A.JPG'
        for database in data['databases']:
            with database_connection(Path(database)) as connection:
                connection.execute("UPDATE files SET current_relative_path=? WHERE current_root_kind='trash' AND current_relative_path='A.JPG'", (selected,))
        real = ts._move_checked
        def interleave(source, target, *args, **kwargs):
            if not hit:
                hit.append(mode)
                external_swap(root / 'nested', root / 'saved-nested', outside)
            return real(source, target, *args, **kwargs)
        monkeypatch.setattr(ts, '_move_checked', interleave)
    elif mode == 'last_unlink':
        real = os.unlink
        def interleave(name, *args, **kwargs):
            fd = kwargs.get('dir_fd')
            if name == 'A.JPG' and fd is not None and not hit and (os.fstat(fd).st_dev, os.fstat(fd).st_ino) == bound_identity:
                hit.append(mode)
                external_swap(root, ws / 'saved-trash', outside)
            return real(name, *args, **kwargs)
        monkeypatch.setattr(os, 'unlink', interleave)
    error = None
    try:
        if mode == 'full':
            main.api_empty_trash({'confirmation': main.TRASH_CONFIRMATION})
        else:
            ts.delete_selected_trash_files([Path(p) for p in data['databases']], ws, [selected])
    except ts.TrashError as exc:
        error = str(exc)
    assert foreign.read_bytes() == raw
    assert hashlib.sha256(foreign.read_bytes()).hexdigest() == digest
    assert (foreign.stat().st_dev, foreign.stat().st_ino) == (before.st_dev, before.st_ino)
    if mode in {'nested', 'last_unlink'}:
        assert hit == [mode]
        assert error
        assert any(not p.is_symlink() and p.resolve().is_relative_to(ws.resolve()) and hashlib.sha256(p.read_bytes()).hexdigest() == digest for p in ws.rglob('*.JPG'))
    else:
        assert error is None
        assert not (root / 'A.JPG').exists()
        if mode == 'full': assert not list(root.iterdir())
    for database in data['databases']:
        with database_connection(Path(database)) as connection:
            assert connection.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
            assert not connection.execute('PRAGMA foreign_key_check').fetchall()
