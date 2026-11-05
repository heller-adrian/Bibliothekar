"""Exclusive same-filesystem import publication; never fall back to replace.

Directory descriptors prevent symlink traversal. Kernel exclusive rename keeps
the original inode and leaves both names untouched on a destination collision.
This is not protection against an external writer changing an owned file later.
"""
from contextlib import contextmanager
import ctypes
import errno
import hashlib
import os
from pathlib import Path
import stat
import sys

from app.pipeline import PipelineError
from app.root_operations import validate_active_roots


@contextmanager
def _parent(path: Path, *, create: bool = False):
    if '\0' in os.fspath(path):
        raise PipelineError('Unsicherer Importpfad: NUL-Zeichen ist nicht zulässig.')
    path = Path(os.path.abspath(path))
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        for component in path.parent.parts[1:]:
            if component in ('.', '..'):
                raise PipelineError('Unsicherer Importpfad.')
            try:
                child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
            except FileNotFoundError:
                if not create:
                    raise
                try:
                    validate_active_roots()
                    os.mkdir(component, dir_fd=fd)
                    os.fsync(fd)
                except FileExistsError:
                    pass
                child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
            os.close(fd)
            fd = child
        yield fd, path.name
    finally:
        os.close(fd)


def _identity(info):
    return [int(info.st_dev), int(info.st_ino)]


def _verified(fd, name, item):
    handle = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK, dir_fd=fd)
    try:
        before = os.fstat(handle)
        if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1
                or before.st_size != int(item['size_bytes'])
                or (item.get('inode') is not None and _identity(before) != item['inode'])):
            raise PipelineError('Importdatei oder Besitznachweis wurde verändert: ' + name)
        digest = hashlib.sha256()
        while block := os.read(handle, 1024 * 1024):
            digest.update(block)
        after = os.fstat(handle)
        fields = lambda s: (s.st_dev, s.st_ino, s.st_mode, s.st_nlink, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
        if digest.hexdigest() != item['sha256'] or fields(before) != fields(after):
            raise PipelineError('SHA-256 oder Dateiidentität der Importdatei weicht ab: ' + name)
        os.fsync(handle)
        return before
    finally:
        os.close(handle)


def import_identity(source: Path, item: dict) -> list[int]:
    with _parent(source) as (fd, name):
        return _identity(_verified(fd, name, item))


def _native_rename(source_fd, source_name, destination_fd, destination_name):
    if b'\0' in os.fsencode(source_name) or b'\0' in os.fsencode(destination_name):
        raise PipelineError('Unsicherer Importname: NUL-Zeichen ist nicht zulässig.')
    # Both APIs implement exclusive rename in the kernel. Unsupported flags
    # or filesystems fail closed; no check-then-rename/copy/link fallback.
    validate_active_roots()
    libc = ctypes.CDLL(None, use_errno=True)
    if sys.platform == 'linux':
        symbol, flag = 'renameat2', 1  # RENAME_NOREPLACE
    elif sys.platform == 'darwin':
        symbol, flag = 'renameatx_np', 4  # RENAME_EXCL
    else:
        raise PipelineError('Atomare Importveröffentlichung wird auf dieser Plattform nicht unterstützt.')
    function = getattr(libc, symbol, None)
    if function is None:
        raise PipelineError('Atomare Importveröffentlichung ist nicht verfügbar; Quelldatei bleibt erhalten.')
    function.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    function.restype = ctypes.c_int
    if function(source_fd, os.fsencode(source_name), destination_fd, os.fsencode(destination_name), flag):
        number = ctypes.get_errno()
        if number == errno.EEXIST:
            raise PipelineError('Zieldatei existiert bereits; Import und fremdes Ziel bleiben erhalten: ' + destination_name)
        raise PipelineError('Atomare Importveröffentlichung verweigert (' + os.strerror(number) + '): ' + destination_name)


def publish_import_file(source: Path, destination: Path, item: dict) -> None:
    with _parent(source) as (source_fd, source_name), _parent(destination, create=True) as (destination_fd, destination_name):
        info = _verified(source_fd, source_name, item)
        if info.st_dev != os.fstat(destination_fd).st_dev:
            raise PipelineError('Importquelle und Ziel liegen nicht auf demselben Dateisystem.')
        _native_rename(source_fd, source_name, destination_fd, destination_name)
        published = os.stat(destination_name, dir_fd=destination_fd, follow_symlinks=False)
        if _identity(published) != _identity(info) or not stat.S_ISREG(published.st_mode):
            raise PipelineError('Importziel änderte sich nach der Veröffentlichung; Journal bleibt erhalten.')
        os.fsync(destination_fd)
        os.fsync(source_fd)


def rollback_import_file(source: Path, destination: Path, item: dict) -> None:
    # Never replace a newly appeared original name or move an unowned target.
    # A failed rollback retains the journal and surviving file for recovery.
    with _parent(source, create=True) as (source_fd, source_name):
        try:
            current = os.stat(source_name, dir_fd=source_fd, follow_symlinks=False)
        except FileNotFoundError:
            current = None
        if current is not None:
            if _identity(current) != item['inode'] or not stat.S_ISREG(current.st_mode):
                raise PipelineError('Rollbackziel ist fremd belegt; beide Bestände bleiben erhalten.')
            _verified(source_fd, source_name, item)
            return
    with _parent(destination) as (fd, name):
        _verified(fd, name, item)
    publish_import_file(destination, source, item)
