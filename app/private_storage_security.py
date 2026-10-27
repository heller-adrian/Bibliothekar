"""Private control authority. Never repair ACLs or synthesize a native ACL.

Trust: root and app UID; admin groups 0/544.
An apps group is not the app UID. Allow entries granting mutation to anybody
else are conservatively rejected (even behind a deny), including inheritance.
TrueNAS native XDR definitions: truenas/nfs4xdr-acl-tools/include/nfs4.h.
"""
from contextlib import contextmanager
import ctypes
import errno
import hashlib
import json
import os
from pathlib import Path
import stat
import struct
import sys

NFS4 = ('system.nfs4_acl_xdr', 'security.nfs4acl_xdr')
WRITE = 0x2 | 0x4 | 0x10 | 0x40 | 0x100 | 0x10000 | 0x40000 | 0x80000
ADMIN_GROUPS = {0, 544}
LOCAL_FILESYSTEMS = {'ext2', 'ext3', 'ext4', 'xfs', 'btrfs', 'tmpfs', 'overlay', 'aufs', 'ramfs'}


class RootOperationError(RuntimeError):
    pass


class PrivateStorageError(RootOperationError):
    def __init__(self, code, path, detail):
        self.code, self.path, self.detail = code, str(path), detail
        super().__init__(f'{code}: {path}: {detail}')

    def issue(self):
        return {'code': self.code, 'path': self.path, 'detail': self.detail}


def filesystem(fd):
    """Kernel mount identity of the *held* descriptor, not path prefix guessing."""
    if sys.platform == 'darwin':
        return 'darwin'
    if sys.platform != 'linux':
        raise OSError('unsupported private ACL platform')
    info = Path(f'/proc/self/fdinfo/{fd}').read_text()
    mount_id = next(line.split(':', 1)[1].strip() for line in info.splitlines() if line.startswith('mnt_id:'))
    for line in Path('/proc/self/mountinfo').read_text().splitlines():
        fields = line.split()
        if fields[0] == mount_id:
            return fields[fields.index('-') + 1]
    raise OSError('descriptor mount not found')


def _darwin_attributes(fd):
    # fstatx_np proves absence; an ACL API failure is never absence.
    lib = ctypes.CDLL(None, use_errno=True)
    lib.filesec_init.restype = ctypes.c_void_p
    lib.filesec_free.argtypes = [ctypes.c_void_p]
    lib.fstatx_np.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p]
    lib.filesec_query_property.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_int)]
    section = lib.filesec_init()
    if not section:
        raise OSError('native ACL allocation failed')
    try:
        buffer = ctypes.create_string_buffer(2048)
        present = ctypes.c_int(-1)
        if lib.fstatx_np(fd, buffer, section) != 0 or lib.filesec_query_property(section, 5, ctypes.byref(present)) != 0:
            raise OSError('native ACL cannot be read')
        if present.value == 0:
            return {}
    finally:
        lib.filesec_free(section)
    # Conservatively reject nontrivial Darwin ACLs; no NFSv4 interpretation.
    raise OSError('nontrivial Darwin ACL requires administrative qualification')


def attributes(fd):
    if sys.platform == 'darwin':
        return _darwin_attributes(fd)
    kind = filesystem(fd)
    names = set(os.listxattr(fd))
    acl_names = {n for n in names if 'acl' in n.lower()} | set(NFS4) | {'system.posix_acl_access', 'system.posix_acl_default'}
    result = {}
    for name in sorted(acl_names):
        try:
            result[name] = os.getxattr(fd, name)
        except OSError as error:
            if error.errno not in {errno.ENODATA, errno.ENOTSUP, errno.EOPNOTSUPP}:
                raise
    native = {name for name in NFS4 if name in result}
    if native:
        # The security namespace is an application/synthetic ACL store. It is
        # not proof of Linux kernel enforcement, even when its XDR looks valid.
        if kind != 'zfs' or native != {NFS4[0]}:
            raise OSError(f'{kind}: unsupported/non-native ACL namespace {sorted(native)}; native ZFS system.nfs4_acl_xdr required')
    elif kind not in LOCAL_FILESYSTEMS:
        raise OSError(f'{kind}: native ACL unavailable; use a private dataset with an explicit, readable owner/admin-only native ACL')
    return result


def check_acl(fd, users, *, path='<descriptor>', sticky=False, existing_ancestor=False, reader=None):
    info = os.fstat(fd)
    if info.st_uid not in users:
        raise PrivateStorageError('private_owner_untrusted', path, f'uid={info.st_uid}; expected one of {sorted(users)}')
    try:
        attrs = (reader or attributes)(fd)
    except (OSError, ValueError, StopIteration) as error:
        raise PrivateStorageError('acl_backend_unavailable', path, str(error)) from error
    native = [(n, v) for n, v in attrs.items() if n in NFS4]
    other = set(attrs) - set(NFS4)
    if existing_ancestor:
        other.discard('system.posix_acl_default')
    if other or len(native) > 1:
        raise PrivateStorageError('private_acl_unknown', path, f'unsupported/conflicting ACL attributes: {sorted(attrs)}')
    if native:
        raw = native[0][1]
        if len(raw) < 28 or len(raw) > 20488 or (len(raw)-8) % 20:
            raise PrivateStorageError('private_acl_unknown', path, 'invalid native XDR length')
        flags, count = struct.unpack_from('!II', raw)
        if count != (len(raw)-8)//20 or flags & ~0x30007:
            raise PrivateStorageError('private_acl_unknown', path, 'invalid native header/count/flags')
        for index, (kind, ace_flags, special, mask, who) in enumerate(struct.iter_unpack('!IIIII', raw[8:])):
            if kind not in (0, 1, 2, 3) or ace_flags & ~0xff or special not in (0, 1) or mask & ~0x1f01ff:
                raise PrivateStorageError('private_acl_unknown', path, f'unknown ACE {index}')
            if special and who not in (1, 2, 3):
                raise PrivateStorageError('private_acl_unknown', path, f'unknown special principal ACE {index}')
            if kind != 0 or not mask & WRITE:
                continue
            group = bool(ace_flags & 0x40)
            if special:
                trusted = info.st_uid in users if who == 1 else info.st_gid in ADMIN_GROUPS if who == 2 else False
            else:
                trusted = who in (ADMIN_GROUPS if group else users)
            if not trusted:
                raise PrivateStorageError('private_acl_untrusted_write', path,
                    f'ACE {index}: principal={who}, group={group}, special={bool(special)}, mask=0x{mask:x}, flags=0x{ace_flags:x}; secure this private dataset and its parents administratively; workspace ACL need not change')
    elif info.st_mode & 0o022 and not (sticky and stat.S_ISDIR(info.st_mode) and info.st_mode & stat.S_ISVTX):
        raise PrivateStorageError('private_acl_untrusted_write', path, f'POSIX mode={stat.S_IMODE(info.st_mode):04o}; private parent must prevent replacement')
    if not stat.S_ISDIR(info.st_mode) and (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1):
        raise PrivateStorageError('private_file_invalid', path, 'regular, singly linked private file required')
    return {'identity': [info.st_dev, info.st_ino], 'acl_sha256': hashlib.sha256(
        b''.join(n.encode()+v for n, v in sorted(attrs.items()))).hexdigest()}


@contextmanager
def qualified(path, users=None, *, directory=False):
    path = Path(os.path.abspath(path))
    users = {0, os.geteuid()} if users is None else set(users)
    fds = [os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)]
    links = []
    try:
        def check():
            for i, fd in enumerate(fds):
                node = Path('/') if i == 0 else links[i-1][3]
                if i:
                    parent, name, child, _ = links[i-1]
                    current = os.stat(name, dir_fd=parent, follow_symlinks=False)
                    held = os.fstat(child)
                    if (current.st_dev, current.st_ino) != (held.st_dev, held.st_ino):
                        raise PrivateStorageError('private_identity_changed', node, 'private namespace replaced')
                check_acl(fd, users, path=node, sticky=i < len(fds)-1,
                          existing_ancestor=i < len(fds)-1)
        # Qualify every parent before descending or opening a private object.
        for i, part in enumerate(path.parts[1:]):
            check_acl(fds[-1], users, path=Path('/') if not links else links[-1][3], sticky=True, existing_ancestor=True)
            last = i == len(path.parts)-2
            flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
            if not last or directory:
                flags |= os.O_DIRECTORY
            node = Path('/').joinpath(*path.parts[1:i+2])
            try:
                fd = os.open(part, flags, dir_fd=fds[-1])
            except OSError as error:
                raise PrivateStorageError('private_path_unavailable', node, str(error)) from error
            links.append((fds[-1], part, fd, node)); fds.append(fd)
        check()
        yield fds[-1], check
        check()
    finally:
        for fd in reversed(fds):
            os.close(fd)


def qualify_existing(path):
    """Read-only qualification of an existing target or its nearest parent."""
    path = Path(os.path.abspath(path))
    while not path.exists() and not path.is_symlink():
        if path == path.parent:
            break
        path = path.parent
    with qualified(path, directory=path.is_dir()) as (_, check):
        check()
