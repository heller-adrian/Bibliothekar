"""Private failed-restore retention; no workspace metadata is a trust anchor.

Trust: the app UID, root, the configured database-directory owner and the
system administrator groups 0/544. Other apps sharing those credentials are
inside this trust boundary. Native NFS4 ACLs are read, never changed.
"""
from contextlib import contextmanager
import ctypes
import errno
import hashlib
import os
from pathlib import Path
import stat
import struct
import sys

from app import trash_fd
from app.trash import TrashError

WRITE = 0x2 | 0x4 | 0x10 | 0x40 | 0x100 | 0x10000 | 0x40000 | 0x80000
NFS4 = ('system.nfs4_acl_xdr', 'security.nfs4acl_xdr')
ADMIN_GROUPS = {0, 544}


def _attributes(fd):
    if hasattr(os, 'listxattr'):
        # Probe native names explicitly: not every driver lists system attrs.
        names = {n for n in os.listxattr(fd) if 'acl' in n.lower()} | set(NFS4) | {'system.posix_acl_access', 'system.posix_acl_default'}
        attrs = {}
        for name in sorted(names):
            try: attrs[name] = os.getxattr(fd, name)
            except OSError as error:
                if error.errno not in {errno.ENODATA, errno.ENOTSUP, errno.EOPNOTSUPP}: raise
        return attrs
    if sys.platform != 'darwin':
        raise TrashError('ACL-Prüfung der privaten Retention ist nicht verfügbar.')
    # Query presence explicitly using fstatx/filesec (Darwin SDK sys/fcntl.h),
    # never interpret an acl_get_fd_np failure as a permission proof.
    lib = ctypes.CDLL(None, use_errno=True)
    lib.filesec_init.restype = ctypes.c_void_p
    lib.filesec_free.argtypes = [ctypes.c_void_p]
    lib.fstatx_np.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p]
    lib.filesec_query_property.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_int)]
    fsec = lib.filesec_init()
    if not fsec: raise TrashError('Native Verwaltungs-ACL nicht lesbar.')
    try:
        buffer = ctypes.create_string_buffer(2048); present = ctypes.c_int(-1)
        if lib.fstatx_np(fd, buffer, fsec) != 0 or lib.filesec_query_property(fsec, 5, ctypes.byref(present)) != 0:
            raise TrashError('Native Verwaltungs-ACL nicht lesbar.')
        if present.value == 0: return {}
    finally: lib.filesec_free(fsec)
    lib.acl_get_fd_np.argtypes = [ctypes.c_int, ctypes.c_int]
    lib.acl_get_fd_np.restype = ctypes.c_void_p
    lib.acl_get_entry.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_void_p)]
    lib.acl_get_tag_type.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int)]
    lib.acl_free.argtypes = [ctypes.c_void_p]
    acl = lib.acl_get_fd_np(fd, 0x100)
    if not acl: raise TrashError('Native Verwaltungs-ACL nicht lesbar.')
    try:
        entry = ctypes.c_void_p(); first = True
        while True:
            ctypes.set_errno(0)
            result = lib.acl_get_entry(acl, 0 if first else -1, ctypes.byref(entry)); first = False
            if result == -1 and ctypes.get_errno() == errno.EINVAL: break
            tag = ctypes.c_int()
            if result != 0 or lib.acl_get_tag_type(entry, ctypes.byref(tag)) != 0 or tag.value != 2:
                raise TrashError('Nicht qualifizierte native ACL im privaten Verwaltungsbereich.')
        return {}  # Every entry was ACL_EXTENDED_DENY; none grants access.
    finally: lib.acl_free(acl)


def check_acl(fd, users, *, sticky=False):
    info = os.fstat(fd)
    if info.st_uid not in users:
        raise TrashError('Fremder Eigentümer im privaten Verwaltungsbereich.')
    attrs = _attributes(fd)
    native = [(n, v) for n, v in attrs.items() if n in NFS4]
    if len(native) > 1 or any(n not in NFS4 for n in attrs):
        raise TrashError('Nicht qualifizierte ACL im privaten Verwaltungsbereich.')
    if native:
        raw = native[0][1]
        if len(raw) < 28 or len(raw) > 20488 or (len(raw)-8) % 20:
            raise TrashError('Ungültiges NFS4-ACL-Dokument.')
        flags, count = struct.unpack_from('!II', raw)
        if count != (len(raw)-8)//20 or flags & ~0x30007:
            raise TrashError('Unbekannte NFS4-ACL-Struktur.')
        for kind, flags, special, mask, who in struct.iter_unpack('!IIIII', raw[8:]):
            if kind not in (0, 1, 2, 3) or special not in (0, 1) or flags & ~0xff or mask & ~0x1f01ff:
                raise TrashError('Unbekannter NFS4-ACL-Eintrag.')
            if kind != 0 or not mask & WRITE:
                continue
            # Include inherit-only grants: they may affect newly created copies.
            group = bool(flags & 0x40)
            if special:
                if who == 1: trusted = info.st_uid in users
                elif who == 2: trusted = info.st_gid in ADMIN_GROUPS
                elif who == 3: trusted = False
                else: raise TrashError('Unbekannter NFS4-ACL-Prinzipal.')
            else:
                trusted = who in (ADMIN_GROUPS if group else users)
            if not trusted:
                raise TrashError('Fremde Schreib-/Löschrechte in privater NFS4-ACL.')
    elif info.st_mode & 0o022:
        if not (sticky and stat.S_ISDIR(info.st_mode) and info.st_mode & stat.S_ISVTX):
            raise TrashError('Fremde POSIX-Schreibrechte im privaten Verwaltungsbereich.')
    if not stat.S_ISDIR(info.st_mode) and (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1):
        raise TrashError('Private Datei ist nicht eindeutig oder hat Hardlinks.')
    return {'identity': list(trash_fd.identity(info)), 'acl_sha256':
            hashlib.sha256(b''.join(n.encode()+v for n, v in sorted(attrs.items()))).hexdigest()}


@contextmanager
def qualified(path, users, *, directory=False):
    """Hold and qualify every ancestor, including the mount-visible namespace."""
    path = Path(os.path.abspath(path))
    fds = [os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)]
    links = []
    try:
        check_acl(fds[0], users, sticky=True)
        for i, part in enumerate(path.parts[1:]):
            last = i == len(path.parts)-2
            flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
            if not last or directory: flags |= os.O_DIRECTORY
            fd = os.open(part, flags, dir_fd=fds[-1])
            links.append((fds[-1], part, fd)); fds.append(fd)
            check_acl(fd, users, sticky=not last)
        def check():
            for parent, name, fd in links:
                now = os.stat(name, dir_fd=parent, follow_symlinks=False)
                if trash_fd.identity(now) != trash_fd.identity(os.fstat(fd)):
                    raise TrashError('Privater Verwaltungsbereich wurde ausgetauscht.')
                check_acl(fd, users, sticky=fd != fds[-1])
        check()
        yield fds[-1], check
    finally:
        for fd in reversed(fds): os.close(fd)


def authority(database, workspace):
    root = Path(database).absolute().parent
    ws = Path(workspace).absolute()
    if root == ws or ws in root.parents or root in ws.parents:
        raise TrashError('Private Retention und gemeinsamer Workspace müssen getrennt sein.')
    # Ownership of the explicitly configured private app mount is an admin role,
    # not proof that its UID is isolated from other host processes.
    with trash_fd.parent(root/'.binding') as (fd, _, binding):
        users = {0, os.geteuid(), os.fstat(fd).st_uid}
        binding()
    with qualified(root, users, directory=True) as (_, check): check()
    return root, users


def ensure_directory(path, users):
    with qualified(Path(path).parent, users, directory=True) as (fd, check):
        try: os.mkdir(Path(path).name, 0o700, dir_fd=fd)
        except FileExistsError: pass
        check(); os.fsync(fd)
    with qualified(path, users, directory=True) as (fd, check):
        check(); os.fsync(fd)


def hash_fd(fd):
    value = hashlib.sha256(); os.lseek(fd, 0, os.SEEK_SET)
    while block := os.read(fd, 1024*1024): value.update(block)
    os.lseek(fd, 0, os.SEEK_SET)
    return value.hexdigest()


def manifest(root):
    """Complete enumeration, no symlinks/special files, held directory bindings."""
    result = []
    def walk(path, relative):
        if len(relative.parts)>128: raise TrashError('Restoreverzeichnis zu tief; Reservierung bleibt bestehen.')
        with trash_fd.parent(path/'.binding') as (fd, _, check):
            before = os.fstat(fd); names = sorted(os.listdir(fd))
            for name in names:
                rel = relative/name
                item = os.stat(name, dir_fd=fd, follow_symlinks=False)
                if stat.S_ISDIR(item.st_mode): walk(path/name, rel)
                else:
                    with trash_fd.file_at(fd, name) as (source, info):
                        sha = hash_fd(source)
                        after = os.fstat(source)
                        if (info.st_size, info.st_mtime_ns, info.st_ctime_ns) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns):
                            raise TrashError('Restoredatei während Manifestprüfung verändert.')
                        trash_fd.verify_entry(fd, name, info)
                        result.append({'relative_path': rel.as_posix(), 'size_bytes': info.st_size,
                                       'sha256': sha, 'identity': list(trash_fd.identity(info))})
            check(); after = os.fstat(fd)
            if names != sorted(os.listdir(fd)) or (before.st_mtime_ns, before.st_ctime_ns) != (after.st_mtime_ns, after.st_ctime_ns):
                raise TrashError('Restoreverzeichnis während Manifestprüfung verändert.')
    walk(Path(root), Path())
    return sorted(result, key=lambda r: r['relative_path'])


def retain(source, target, item, users, checkpoint):
    """Exclusive copy + fsync + read-back. A killed partial copy is kept and blocks."""
    # All subdirectories are constructed from validated relative manifest names.
    with trash_fd.parent(source) as (sdir, name, scheck):
        with trash_fd.file_at(sdir, name, item['sha256']) as (src, original):
            if list(trash_fd.identity(original)) != item['identity'] or original.st_size != item['size_bytes']:
                raise TrashError('Quellidentität der Rückfallkopie verändert.')
            with qualified(target.parent, users, directory=True) as (dst, check):
                try:
                    out = os.open(target.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=dst)
                except FileExistsError:
                    out = None
                if out is not None:
                    try:
                        check_acl(out, users)
                        while block := os.read(src, 1024*1024):
                            view = memoryview(block)
                            while view:
                                written = os.write(out, view)
                                if written<=0: raise OSError('Retentionskopie konnte nicht vollständig geschrieben werden.')
                                view = view[written:]
                            checkpoint('retention_writing')
                        os.fsync(out)
                    finally: os.close(out)
                    os.fsync(dst)
                scheck(); check(); trash_fd.verify_entry(sdir, name, original)
                if hash_fd(src) != item['sha256']: raise TrashError('Quelle während Retention verändert.')
            checkpoint('retention_copied')
    with qualified(target, users) as (fd, check):
        info = os.fstat(fd)
        if info.st_size != item['size_bytes'] or hash_fd(fd) != item['sha256'] or list(trash_fd.identity(info)) == item['identity']:
            raise TrashError('Private Retentionskopie ist unvollständig oder nicht unabhängig.')
        check(); os.fsync(fd)
        return {**item, 'retention_identity': list(trash_fd.identity(info))}
