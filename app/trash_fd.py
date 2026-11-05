"""Small no-follow directory bindings for trash deletion and its recovery.

These bind path traversal, not an adversarial writer's final directory entry.
"""
from contextlib import contextmanager
import errno
import hashlib
import json
import os
from pathlib import Path
import stat
import uuid

from app.trash import TrashError


def identity(info):
    return info.st_dev, info.st_ino


@contextmanager
def parent(path, *, create=False):
    path = Path(os.path.abspath(path))
    descriptors = [os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)]
    bindings = []
    try:
        try:
            for part in path.parent.parts[1:]:
                if create:
                    try:
                        os.mkdir(part, mode=0o700, dir_fd=descriptors[-1])
                        os.fsync(descriptors[-1])
                    except FileExistsError:
                        pass
                fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                             dir_fd=descriptors[-1])
                bindings.append((descriptors[-1], part, fd))
                descriptors.append(fd)
        except OSError as error:
            if isinstance(error, FileNotFoundError):
                raise
            raise TrashError('Papierkorbpfad nicht sicher gebunden; Dateien und Journale bleiben erhalten: ' + str(path)) from error
        def check():
            try:
                for owner, name, fd in bindings:
                    current = os.stat(name, dir_fd=owner, follow_symlinks=False)
                    if not stat.S_ISDIR(current.st_mode) or identity(current) != identity(os.fstat(fd)):
                        raise TrashError('Papierkorbpfad während der Operation verändert; weitere Löschungen gestoppt.')
            except OSError as error:
                if isinstance(error, FileNotFoundError):
                    raise
                raise TrashError('Papierkorbpfad nicht sicher gebunden; Dateien und Journale bleiben erhalten: ' + str(path)) from error
        check()
        # A caller's operation is outside the path-validation error handler.
        yield descriptors[-1], path.name, check
    finally:
        for fd in reversed(descriptors):
            os.close(fd)


def verify_entry(parent_fd, name, info):
    current = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    if not stat.S_ISREG(current.st_mode) or identity(current) != identity(info):
        raise TrashError('Dateiidentität im Papierkorb verändert; weitere Löschungen gestoppt.')


@contextmanager
def file_at(parent_fd, name, sha256=None):
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent_fd)
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink < 1:
            raise TrashError('Papierkorbeintrag ist keine eindeutig gebundene reguläre Datei.')
        if sha256 is not None:
            value = hashlib.sha256()
            while block := os.read(fd, 1024 * 1024):
                value.update(block)
            after = os.fstat(fd)
            if value.hexdigest() != sha256 or (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns):
                raise TrashError('Prüfsummen- oder Identitätskonflikt im Papierkorb; weitere Löschungen gestoppt.')
            os.lseek(fd, 0, os.SEEK_SET)
        verify_entry(parent_fd, name, before)
        yield fd, before
    finally:
        os.close(fd)


def unlink(path, *, sha256=None, missing_ok=False):
    try:
        with parent(path) as (directory, name, check):
            with file_at(directory, name, sha256) as (_, info):
                check()
                verify_entry(directory, name, info)
                os.unlink(name, dir_fd=directory)
                os.fsync(directory)
    except FileNotFoundError:
        if not missing_ok:
            raise


def mkdir(path, *, mode=0o700):
    with parent(path, create=True) as (directory, name, check):
        check()
        try:
            os.mkdir(name, mode=mode, dir_fd=directory)
            os.fsync(directory)
        except FileExistsError:
            info = os.stat(name, dir_fd=directory, follow_symlinks=False)
            if not stat.S_ISDIR(info.st_mode):
                raise TrashError('Unsicherer Papierkorb-Verzeichniseintrag.')


def rmdir(path, *, ignore_nonempty=False):
    with parent(Path(path) / '.binding') as (directory, _, check):
        # Keep the directory open and verify its complete ancestor chain.
        with parent(path) as (owner, name, owner_check):
            check(); owner_check()
            if identity(os.stat(name, dir_fd=owner, follow_symlinks=False)) != identity(os.fstat(directory)):
                raise TrashError('Verzeichnisidentität im Papierkorb verändert.')
            try:
                os.rmdir(name, dir_fd=owner)
            except OSError as error:
                if ignore_nonempty and error.errno in {errno.ENOTEMPTY, errno.EEXIST}:
                    return False
                # Keep cleanup failures strict now that parent only translates
                # its own path-validation errors, not caller operation errors.
                raise TrashError('Papierkorbverzeichnis konnte nicht sicher bereinigt werden: ' + str(path)) from error
            os.fsync(owner)
            return True


def sync(path):
    with parent(Path(path) / '.binding') as (directory, _, check):
        check()
        os.fsync(directory)


def read_json(path):
    with parent(path) as (directory, name, check):
        with file_at(directory, name) as (fd, _):
            check()
            with os.fdopen(os.dup(fd)) as handle:
                return json.load(handle)


def atomic_json(path, value):
    with parent(path) as (directory, name, check):
        temporary = '.' + uuid.uuid4().hex + '.tmp'
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                     0o600, dir_fd=directory)
        try:
            with os.fdopen(fd, 'w') as handle:
                json.dump(value, handle, ensure_ascii=False, sort_keys=True)
                handle.flush(); os.fsync(handle.fileno())
            check()
            os.replace(temporary, name, src_dir_fd=directory, dst_dir_fd=directory)
            os.fsync(directory)
        finally:
            try: os.unlink(temporary, dir_fd=directory)
            except FileNotFoundError: pass
