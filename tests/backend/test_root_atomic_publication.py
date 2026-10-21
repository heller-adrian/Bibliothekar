"""Read legitimate atomic state publications without accepting unsafe inodes."""
import os
from pathlib import Path
from types import SimpleNamespace

import pytest
from app import root_operations as ro


def replace_on_open(monkeypatch, path, action, *, repeat=False):
    real_open = os.open
    seen = []
    def interleave(name, flags, *args, **kwargs):
        fd = real_open(name, flags, *args, **kwargs)
        if Path(name) == path and (repeat or not seen):
            old = os.fstat(fd)
            action()
            after = os.fstat(fd)
            seen.append((old.st_ino, after.st_nlink))
        return fd
    monkeypatch.setattr(ro.os, 'open', interleave)
    return seen


def test_atomic_state_reopens_verified_replacement(tmp_path, monkeypatch):
    path = tmp_path / 'state.json'
    ro._write(path, {'generation': 0})
    seen = replace_on_open(monkeypatch, path, lambda: ro._write(path, {'generation': 1}))
    assert ro._read(path) == {'generation': 1}
    assert len(seen) == 1 and seen[0][1] == 0
    assert path.stat().st_nlink == 1


def test_repeated_publications_are_bounded(tmp_path, monkeypatch):
    path = tmp_path / 'state.json'
    ro._write(path, {'generation': 0})
    seen = replace_on_open(monkeypatch, path, lambda: ro._write(path, {'generation': 1}), repeat=True)
    with pytest.raises(ro.RootOperationError):
        ro._read(path)
    assert len(seen) == 3 and all(nlink == 0 for _, nlink in seen)


@pytest.mark.parametrize('kind', ['symlink', 'hardlink', 'writable', 'directory', 'missing', 'foreign'])
def test_unsafe_replacement_is_rejected(tmp_path, monkeypatch, kind):
    path = tmp_path / 'state.json'
    ro._write(path, {'generation': 0})
    foreign = tmp_path / 'foreign'
    ro._write(foreign, {'foreign': True})
    original = foreign.read_bytes()
    def replace():
        path.unlink()
        if kind == 'symlink': path.symlink_to(foreign)
        elif kind == 'hardlink': os.link(foreign, path)
        elif kind == 'directory': path.mkdir()
        elif kind != 'missing':
            ro._write(path, {'generation': 1})
            if kind == 'writable': path.chmod(0o666)
    if kind == 'foreign':
        real_stat = os.stat
        def fake_stat(name, *args, **kwargs):
            info = real_stat(name, *args, **kwargs)
            if Path(name) == path and kwargs.get('follow_symlinks') is False:
                return SimpleNamespace(st_mode=info.st_mode, st_uid=os.getuid()+1,
                                       st_nlink=info.st_nlink, st_dev=info.st_dev, st_ino=info.st_ino)
            return info
        monkeypatch.setattr(ro.os, 'stat', fake_stat)
    replace_on_open(monkeypatch, path, replace)
    with pytest.raises(ro.RootOperationError): ro._read(path)
    assert foreign.read_bytes() == original


@pytest.mark.parametrize('kind', ['symlink', 'hardlink', 'writable', 'foreign'])
def test_initial_unsafe_state_is_rejected(tmp_path, monkeypatch, kind):
    path = tmp_path / 'state.json'
    ro._write(path, {'generation': 0})
    if kind == 'symlink':
        path.rename(tmp_path / 'target'); path.symlink_to(tmp_path / 'target')
    elif kind == 'hardlink': os.link(path, tmp_path / 'alias')
    elif kind == 'writable': path.chmod(0o666)
    else:
        real_fstat = os.fstat
        def foreign(fd):
            info = real_fstat(fd)
            return SimpleNamespace(st_mode=info.st_mode, st_uid=os.getuid()+1,
                                   st_nlink=info.st_nlink)
        monkeypatch.setattr(ro.os, 'fstat', foreign)
    with pytest.raises(ro.RootOperationError): ro._read(path)


def test_other_unlinked_control_files_are_not_retried(tmp_path, monkeypatch):
    path = tmp_path / 'mutation.json'
    ro._write(path, {'generation': 0})
    seen = replace_on_open(monkeypatch, path, lambda: ro._write(path, {'generation': 1}))
    with pytest.raises(ro.RootOperationError): ro._read(path)
    assert len(seen) == 1


def test_initial_missing_state_keeps_default(tmp_path):
    assert ro._read(tmp_path / 'state.json', {'generation': 0}) == {'generation': 0}
