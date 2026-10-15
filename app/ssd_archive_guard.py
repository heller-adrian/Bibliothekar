"""Best-effort conflict detection, never a write lock or an immutable copy.

The final check and SSD unlink are separate operations. External writers may
still win that race. No kernel notification can reconstruct deleted bytes.
"""
from __future__ import annotations

import ctypes
import hashlib
import os
from pathlib import Path, PurePosixPath
import stat
import struct
import sys
import time


class ArchiveConflict(RuntimeError):
    pass


def identity(st):
    return (st.st_dev, st.st_ino)


def version(st):
    return (*identity(st), st.st_mode, st.st_size, st.st_mtime_ns,
            st.st_ctime_ns, st.st_nlink)


def mount_id(fd):
    if sys.platform != 'linux':
        return None
    for line in Path(f'/proc/self/fdinfo/{fd}').read_text().splitlines():
        if line.startswith('mnt_id:'):
            return int(line.split(':', 1)[1])
    raise ArchiveConflict('Mountidentität des Archivzugangs ist nicht nachweisbar.')


def require_local_filesystem(fd):
    if sys.platform != 'linux':
        return
    mid = mount_id(fd)
    for line in Path('/proc/self/mountinfo').read_text().splitlines():
        left, right = line.split(' - ', 1)
        if int(left.split()[0]) == mid:
            fs = right.split()[0]
            if fs not in {'ext2', 'ext3', 'ext4', 'xfs', 'btrfs', 'f2fs', 'zfs', 'tmpfs', 'overlay'}:
                raise ArchiveConflict('Archiv-Dateisystem ' + fs + ' besitzt keinen zugelassenen lokalen inotify-Pfad; kein stiller B-Fallback.')
            return fs
    raise ArchiveConflict('Archiv-Mounttyp ist nicht nachweisbar.')


class InotifyWatcher:
    # No access/open/close-read events: our own hashes must not dirty the run.
    MASK = 0x00000002 | 0x00000004 | 0x00000008 | 0x00000040 | 0x00000080 | 0x00000100 | 0x00000200 | 0x00000400 | 0x00000800
    FATAL = 0x00002000 | 0x00004000 | 0x00008000  # unmount, overflow, ignored

    def __init__(self):
        self.fd = -1
        self.scopes = {}
        self.error = None
        if sys.platform != 'linux':
            raise ArchiveConflict('SSD-Freigabe gesperrt: Linux-inotify ist auf dieser Plattform nicht verfügbar. Kein automatischer Fallback auf reines Nachhashen.')
        self.libc = ctypes.CDLL(None, use_errno=True)
        self.libc.inotify_init1.argtypes = [ctypes.c_int]
        self.libc.inotify_init1.restype = ctypes.c_int
        self.libc.inotify_add_watch.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_uint32]
        self.libc.inotify_add_watch.restype = ctypes.c_int
        self.fd = self.libc.inotify_init1(os.O_NONBLOCK | os.O_CLOEXEC)
        if self.fd < 0:
            raise OSError(ctypes.get_errno(), 'inotify_init1')

    @property
    def count(self):
        return len(self.scopes)

    def watch(self, fd, children=None):
        # Follow only our already-open descriptor, not a newly resolved user path.
        wd = self.libc.inotify_add_watch(self.fd, os.fsencode(f'/proc/self/fd/{fd}'), self.MASK)
        if wd < 0:
            raise OSError(ctypes.get_errno(), 'inotify_add_watch')
        scope = None if children is None else set(children)
        if wd in self.scopes:
            old = self.scopes[wd]
            scope = None if old is None or scope is None else old | scope
        self.scopes[wd] = scope

    def _consume(self, data):
        offset = 0
        while offset < len(data):
            if len(data) - offset < 16:
                raise ArchiveConflict('Unvollständiges inotify-Ereignis.')
            wd, mask, cookie, length = struct.unpack_from('iIII', data, offset)
            offset += 16
            if length > len(data) - offset:
                raise ArchiveConflict('Ungültiges inotify-Ereignis.')
            name = os.fsdecode(data[offset:offset + length].split(b'\0', 1)[0])
            offset += length
            if mask & self.FATAL or wd not in self.scopes:
                raise ArchiveConflict('Archivüberwachung verloren (Watchverlust/Queueüberlauf/Unmount).')
            scope = self.scopes[wd]
            if (mask & self.MASK) and (scope is None or not name or name in scope):
                raise ArchiveConflict('Archivänderung während SSD-Freigabe beobachtet; weitere Löschungen gesperrt.')

    def check(self):
        if self.error:
            raise ArchiveConflict(self.error)
        try:
            for _ in range(16):
                try:
                    data = os.read(self.fd, 65536)
                except BlockingIOError:
                    return
                except InterruptedError:
                    continue
                if not data:
                    raise ArchiveConflict('Archivüberwachung unerwartet beendet.')
                self._consume(data)
            raise ArchiveConflict('Archivereignisqueue wird nicht ruhig; weitere Löschungen gesperrt.')
        except (OSError, ArchiveConflict) as exc:
            self.error = str(exc)
            raise ArchiveConflict(self.error) from exc

    def close(self):
        if self.fd >= 0:
            os.close(self.fd)
            self.fd = -1


class ArchiveGuard:
    """Bind paths via no-follow directory FDs; watch all members until close.

    Production always constructs InotifyWatcher. Dependency injection belongs
    only in tests; there is no environment flag or HTTP downgrade to mode B.
    """
    def __init__(self, root: Path, relatives):
        self.root = Path(root).absolute()
        self.anchors = {}
        self.files = {}
        self.watcher = None
        self.hash_bytes = 0
        self.hash_seconds = 0.0
        try:
            self.watcher = InotifyWatcher()
            for raw in set(str(p) for p in relatives):
                relative = PurePosixPath(raw)
                if relative.is_absolute() or not relative.parts or any(p in ('.', '..') for p in raw.split('/')):
                    raise ArchiveConflict('Ungültiger relativer Archivpfad.')
                fd = self._open(relative, register=True)
                try:
                    st = os.fstat(fd)
                    self._regular(st)
                    require_local_filesystem(fd)
                    self.files[relative.as_posix()] = (version(st), mount_id(fd))
                    self.watcher.watch(fd)
                finally:
                    os.close(fd)
            self.check()
        except BaseException:
            self.close()
            raise

    @staticmethod
    def _regular(st):
        if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1:
            raise ArchiveConflict('Archivdatei ist nicht regulär oder besitzt weitere Hardlinks; Freigabe gesperrt.')

    def _open(self, relative, *, register=False):
        # Open from /, disallow symlinks in every component. Mount IDs detect
        # aliasing by a different bind mount even where dev/ino are identical.
        parts = (*self.root.parts[1:], *relative.parts)
        fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
        key = Path('/')
        try:
            for index, part in enumerate(parts):
                anchor = (*identity(os.fstat(fd)), mount_id(fd))
                if register:
                    if str(key) in self.anchors and self.anchors[str(key)] != anchor:
                        raise ArchiveConflict('Archivverzeichnis änderte sich beim Aufbau der Überwachung.')
                    self.anchors[str(key)] = anchor
                    self.watcher.watch(fd, {part})
                elif self.anchors.get(str(key)) != anchor:
                    raise ArchiveConflict('Archivverzeichnis oder Mountbindung wurde geändert.')
                final = index == len(parts) - 1
                newfd = os.open(part, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW |
                                (os.O_NONBLOCK if final else os.O_DIRECTORY), dir_fd=fd)
                os.close(fd)
                fd = newfd
                key /= part
            return fd
        except BaseException:
            os.close(fd)
            raise

    def check(self):
        if self.watcher is None:
            raise ArchiveConflict('Archivüberwachung fehlt.')
        self.watcher.check()

    def verify(self, relative, expected_size, expected_hash, source_stat=None):
        relative = PurePosixPath(str(relative))
        fd = -1
        try:
            self.check()
            fd = self._open(relative)
            before = os.fstat(fd)
            self._regular(before)
            baseline = self.files[relative.as_posix()]
            if (version(before), mount_id(fd)) != baseline or before.st_size != expected_size:
                raise ArchiveConflict('Archivdatei oder Pfadidentität wurde geändert.')
            if source_stat is not None and (identity(before) == identity(source_stat) or source_stat.st_nlink != 1):
                raise ArchiveConflict('SSD- und Archivkopie sind nicht unabhängig oder SSD-Hardlinks sind unklar.')
            digest = hashlib.sha256()
            start = time.perf_counter()
            while True:
                block = os.read(fd, 1024 * 1024)
                if not block:
                    break
                self.hash_bytes += len(block)
                digest.update(block)
                self.check()
            self.hash_seconds += time.perf_counter() - start
            if digest.hexdigest() != expected_hash or version(os.fstat(fd)) != version(before):
                raise ArchiveConflict('Archivinhalt änderte sich oder SHA-256 stimmt nicht überein.')
            again = self._open(relative)
            try:
                if (version(os.fstat(again)), mount_id(again)) != baseline:
                    raise ArchiveConflict('Archivpfad wurde während der Prüfung ersetzt.')
            finally:
                os.close(again)
            self.check()
            return before
        except (OSError, KeyError) as exc:
            raise ArchiveConflict('Archivzustand ist nicht eindeutig lesbar: ' + str(exc)) from exc
        finally:
            if fd >= 0:
                os.close(fd)

    def close(self):
        if self.watcher is not None:
            self.watcher.close()

    def metrics(self):
        return {'archive_rehash_bytes': self.hash_bytes, 'archive_rehash_seconds': self.hash_seconds,
                'watch_count': self.watcher.count if self.watcher else 0}
