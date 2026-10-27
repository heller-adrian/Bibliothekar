"""Private helper ledger. No inferred ownership of existing mounts.

The web UID must not be able to modify this namespace or privileged code.
External CAP_SYS_ADMIN/root actors are outside this isolation boundary.
"""
from __future__ import annotations
from contextlib import contextmanager
import ctypes
import fcntl
import json
import os
from pathlib import Path
import stat
import subprocess
import sys


class UnsafeMount(RuntimeError):
    pass


def protected_directory(path: Path) -> None:
    """Qualify existing parents; never repair host permissions or follow symlinks.

    POSIX ACL write grants require a writable group mask and are rejected along
    with group/other write bits. Non-POSIX ACL platforms need qualification.
    """
    if not path.is_absolute() or '..' in path.parts:
        raise UnsafeMount('Helper directory must be an absolute, bounded path.')
    if os.geteuid() == int(os.environ.get('KAMERA_WEB_UID', '568')):
        raise UnsafeMount('Helper and web application must use different UIDs.')
    from app.appdata import root as appdata_root, mount
    base = appdata_root()
    runtime = base/'removable-sources' if base else None
    if runtime and (path == runtime or path == runtime/'.bibliothekar-helper'):
        info = runtime.lstat(); current = mount(runtime)
        if current['target'] != str(runtime) or current['filesystem'] != 'tmpfs' or info.st_uid != 0 or info.st_mode & 0o022:
            raise UnsafeMount('RC12 removable helper needs its root-owned private tmpfs mount')
        from app.import_publication import _parent
        with _parent(path/'.probe'):
            pass  # no symlink in any component
        # A mounted child cannot be unlinked/replaced by the web UID. This
        # runtime filesystem has no inherited host NFSv4 ACLs.
        parts = [runtime] if path == runtime else [runtime,path]
    else:
        parts = list(reversed((path, *path.parents)))
    for part in parts:
        info = part.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid not in (0, os.geteuid()):
            raise UnsafeMount('Untrusted helper directory: ' + str(part))
        # Sticky system temporary ancestors cannot replace our owned child.
        sticky_ancestor = part != path and info.st_uid == 0 and bool(info.st_mode & stat.S_ISVTX)
        if info.st_mode & 0o022 and not sticky_ancestor:
            raise UnsafeMount('Helper parent is writable by other users: ' + str(part))
    if os.geteuid() == 0:
        # Ask the kernel under exactly the web credentials, including ACLs.
        # No files are created, no permissions changed; the child drops all groups.
        probe = subprocess.run([sys.executable, '-I', '-c',
            'import json,os,sys; os.setgroups([]); os.setgid(int(sys.argv[2])); '
            'os.setuid(int(sys.argv[1])); '
            'print(json.dumps([p for p in sys.argv[3:] if os.access(p,os.W_OK)]))',
            os.environ.get('KAMERA_WEB_UID', '568'), os.environ.get('KAMERA_WEB_GID', '568'),
            *[str(part) for part in parts if not (part != path and part.lstat().st_mode & stat.S_ISVTX)]],
            cwd='/', capture_output=True, text=True, timeout=10)
        if probe.returncode or json.loads(probe.stdout):
            raise UnsafeMount('Web UID can modify the helper namespace, or ACL isolation could not be verified.')


def directory_identity(path: Path) -> list[int]:
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        s = os.fstat(fd)
        return [s.st_dev, s.st_ino]
    finally:
        os.close(fd)


def mount_identity(path: Path) -> dict:
    """Unique, non-recycled kernel mount identity, scoped to boot + namespace.

    STATX_MNT_ID_UNIQUE requires Linux 6.8+ with actual statx mask support.
    Ordinary reusable mount IDs are intentionally not a fallback.
    """
    libc = ctypes.CDLL(None, use_errno=True)
    statx = getattr(libc, 'statx', None)
    if statx is None:
        raise UnsafeMount('Kernel cannot prove a unique mount identity (statx unavailable).')
    statx.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_uint, ctypes.c_void_p]
    statx.restype = ctypes.c_int
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        result = ctypes.create_string_buffer(256)
        if statx(fd, b'', 0x1000 | 0x100, 0x4000, result) != 0:
            raise UnsafeMount('Kernel cannot prove a unique mount identity.')
        mask = ctypes.c_uint32.from_buffer(result, 0).value
        unique = ctypes.c_uint64.from_buffer(result, 144).value
        if not mask & 0x4000 or not unique:
            raise UnsafeMount('STATX_MNT_ID_UNIQUE is required; mount remains unclaimed.')
        return {'unique': unique, 'boot': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                'namespace': os.stat('/proc/self/ns/mnt').st_ino,
                'directory': directory_identity(path)}
    finally:
        os.close(fd)


class Ledger:
    def __init__(self, root: Path):
        self.root = root
        self.private = root / '.bibliothekar-helper'
        self.fd = -1

    @contextmanager
    def locked(self):
        protected_directory(self.root)
        try:
            self.private.mkdir(mode=0o700)
        except FileExistsError:
            pass
        protected_directory(self.private)
        info = self.private.lstat()
        if info.st_mode & 0o077 or info.st_uid != os.geteuid():
            raise UnsafeMount('Private helper state must be owned by the helper with mode 0700.')
        self.fd = os.open(self.private, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        lock = -1
        try:
            lock = os.open('operations.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600, dir_fd=self.fd)
            s = os.fstat(lock)
            if not stat.S_ISREG(s.st_mode) or s.st_nlink != 1 or s.st_uid != os.geteuid() or s.st_mode & 0o077:
                raise UnsafeMount('Untrusted helper lock.')
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise UnsafeMount('Another helper operation is active; retry later.') from error
            yield self
        finally:
            if lock >= 0:
                os.close(lock)
            os.close(self.fd)
            self.fd = -1

    @staticmethod
    def name(device_id: str) -> str:
        import re
        if not re.fullmatch(r'media-[0-9a-f]{64}', device_id):
            raise UnsafeMount('Invalid managed device identity.')
        return device_id + '.json'

    def read(self, device_id: str) -> dict | None:
        try:
            fd = os.open(self.name(device_id), os.O_RDONLY | os.O_NOFOLLOW, dir_fd=self.fd)
        except FileNotFoundError:
            return None
        with os.fdopen(fd) as stream:
            s = os.fstat(stream.fileno())
            if not stat.S_ISREG(s.st_mode) or s.st_nlink != 1 or s.st_uid != os.geteuid() or s.st_mode & 0o077:
                raise UnsafeMount('Untrusted ownership record.')
            if s.st_size > 65536:
                raise UnsafeMount('Oversized ownership record.')
            record = json.load(stream)
            if not isinstance(record, dict):
                raise UnsafeMount("Invalid ownership record.")
            return record

    def write(self, device_id: str, record: dict):
        name = self.name(device_id)
        temporary = name + '.pending'
        # Interrupted temporary files are evidence; never overwrite them blindly.
        try:
            fd = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600, dir_fd=self.fd)
        except FileExistsError as error:
            raise UnsafeMount('Interrupted helper journal write needs inspection; no mount operation allowed.') from error
        with os.fdopen(fd, 'w') as stream:
            json.dump(record, stream, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, name, src_dir_fd=self.fd, dst_dir_fd=self.fd)
        os.fsync(self.fd)

    def delete(self, device_id: str):
        os.unlink(self.name(device_id), dir_fd=self.fd)
        os.fsync(self.fd)
