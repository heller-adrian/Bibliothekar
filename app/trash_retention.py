"""Private failed-restore retention; no workspace metadata is a trust anchor.

Trust: the app UID, root and the system administrator groups 0/544.
Other apps sharing those credentials are
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
    from app.private_storage_security import attributes
    return attributes(fd)


def check_acl(fd, users, *, sticky=False, existing_ancestor=False):
    from app.private_storage_security import check_acl as qualify_acl, PrivateStorageError
    try:
        return qualify_acl(fd, users, sticky=sticky, existing_ancestor=existing_ancestor, reader=_attributes)
    except PrivateStorageError as error:
        # Keep the retention API's established domain error contract.
        if isinstance(error.__cause__, PermissionError): raise error.__cause__
        prefix = 'Fremde Schreib-/Löschrechte im privaten Verwaltungsbereich. ' if error.code in ('private_acl_untrusted_write','private_owner_untrusted') else 'Nicht qualifizierte private ACL. '
        raise TrashError(prefix + str(error)) from error


@contextmanager
def qualified(path, users, *, directory=False):
    """Hold and qualify every ancestor, including the mount-visible namespace."""
    path = Path(os.path.abspath(path))
    from app.appdata import managed
    if managed(path):
        from app.private_storage_security import qualified as common
        with common(path,users,directory=directory) as value: yield value
        return
    fds = [os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)]
    links = []
    try:
        check_acl(fds[0], users, sticky=True, existing_ancestor=len(path.parts)>1)
        for i, part in enumerate(path.parts[1:]):
            last = i == len(path.parts)-2
            flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
            if not last or directory: flags |= os.O_DIRECTORY
            fd = os.open(part, flags, dir_fd=fds[-1])
            links.append((fds[-1], part, fd)); fds.append(fd)
            check_acl(fd, users, sticky=not last, existing_ancestor=not last)
        def check():
            for parent, name, fd in links:
                now = os.stat(name, dir_fd=parent, follow_symlinks=False)
                if trash_fd.identity(now) != trash_fd.identity(os.fstat(fd)):
                    raise TrashError('Privater Verwaltungsbereich wurde ausgetauscht.')
                check_acl(fd, users, sticky=fd != fds[-1], existing_ancestor=fd != fds[-1])
        check()
        yield fds[-1], check
    finally:
        for fd in reversed(fds): os.close(fd)


def authority(database, workspace):
    root = Path(database).absolute().parent
    ws = Path(workspace).absolute()
    if root == ws or ws in root.parents or root in ws.parents:
        raise TrashError('Private Retention und gemeinsamer Workspace müssen getrennt sein.')
    # Mount ownership alone never promotes an unrelated NAS user to admin.
    with trash_fd.parent(root/'.binding') as (fd, _, binding):
        users = {0, os.geteuid()}
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
                        from app.private_storage_security import check_acl as control_check_acl
                        control_check_acl(out, users, path=target)
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
