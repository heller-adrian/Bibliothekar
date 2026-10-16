"""Directory capabilities for trash operations; no public-name unlink.

The internal deletion namespace must belong exclusively to the application UID.
Processes with that UID or DAC-bypass privileges are part of the trusted service.
"""
from contextlib import contextmanager
from contextvars import ContextVar
import ctypes
import errno
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import uuid

from app.trash import TrashError

ACTIVE = ContextVar('trash_directory_capability', default=None)


def identity(info):
    return [info.st_dev, info.st_ino]


def digest_fd(fd):
    os.lseek(fd, 0, os.SEEK_SET)
    value = hashlib.sha256()
    while True:
        data = os.read(fd, 1024 * 1024)
        if not data:
            break
        value.update(data)
    os.lseek(fd, 0, os.SEEK_SET)
    return value.hexdigest()


def rename_exclusive(source_fd, source_name, target_fd, target_name):
    """Atomic ownership transfer, never check-then-replace or unsafe fallback."""
    tree = ACTIVE.get()
    if sys.platform.startswith('linux'):
        if tree is None or not tree.confined:
            raise TrashError('Atomare Übernahme ohne Kernel-Zugriffsgrenze verweigert.')
        tree.native('rename', src=source_fd, source=source_name, dst=target_fd, target=target_name)
        return
    libc = ctypes.CDLL(None, use_errno=True)
    if sys.platform.startswith('linux') and hasattr(libc, 'renameat2'):
        function = libc.renameat2
        flag = 1  # RENAME_NOREPLACE
    elif sys.platform == 'darwin' and hasattr(libc, 'renameatx_np'):
        function = libc.renameatx_np
        flag = 4  # RENAME_EXCL; development platform only
    else:
        raise TrashError('Atomare kollisionsfreie Dateiübernahme ist nicht verfügbar.')
    function.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    function.restype = ctypes.c_int
    if function(source_fd, os.fsencode(source_name), target_fd, os.fsencode(target_name), flag):
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error), source_name)


class DirectoryTree:
    def __init__(self, workspace):
        self.workspace = Path(os.path.abspath(workspace))
        self.directories = {}
        self.parents = {}
        self.files = []
        self.record = None
        self.journal = None
        self.private_root = None
        self.confined = False

    def __enter__(self):
        try:
            self.directory(self.workspace)
            return self
        except BaseException:
            self.close()
            raise

    def __exit__(self, *unused):
        self.close()

    def close(self):
        for fd in reversed(self.files + list(self.directories.values())):
            os.close(fd)
        self.files = []
        self.directories = {}

    def native(self, operation, **fields):
        self.check_anchor()
        command = {'op': operation, 'root': self.directories[self.workspace], **fields}
        fds = {command['root']} | {value for key,value in fields.items() if key in {'src','dst'}}
        process = subprocess.run([sys.executable, '-B', str(Path(__file__).with_name('trash_native.py'))],
            input=json.dumps(command), capture_output=True, text=True, pass_fds=tuple(fds), timeout=10)
        try:
            result = json.loads(process.stdout)
        except ValueError as error:
            raise TrashError('Unklarer Abschluss der Kernel-Dateioperation; Journal bleibt erhalten.') from error
        if process.returncode or not result.get('ok'):
            code = result.get('errno', errno.EIO)
            if code == errno.ENOSYS:
                raise TrashError('Linux-Kernel-Zugriffsgrenze fehlt; Papierkorblöschung ist gesperrt.')
            raise OSError(code, result.get('error','Kernel-Dateioperation abgewiesen'))
        return result

    def check_anchor(self):
        root = os.fstat(self.directories[self.workspace])
        parent = os.fstat(self.directories[self.workspace.parent])
        if parent.st_uid not in {0, os.geteuid()} or (parent.st_mode & 0o022 and not (parent.st_mode & stat.S_ISVTX and root.st_uid in {0, os.geteuid()})):
            raise TrashError('Workspace-Anker ist extern austauschbar; sichere Löschung gesperrt.')

    def enable_confinement(self):
        self.check_anchor()
        if sys.platform.startswith('linux'):
            self.qualify_filesystem(self.directories[self.workspace.parent])
            self.native('probe')
        self.confined = True

    def link(self, source, target, *, src_dir_fd, dst_dir_fd, follow_symlinks=False):
        if sys.platform.startswith('linux') and self.confined:
            self.native('link', src=src_dir_fd, source=source, dst=dst_dir_fd, target=target)
        else:
            os.link(source,target,src_dir_fd=src_dir_fd,dst_dir_fd=dst_dir_fd,follow_symlinks=follow_symlinks)

    def copy(self, source_fd, target, parent):
        if sys.platform.startswith('linux') and self.confined:
            self.native('copy',src=source_fd,dst=parent,target=target)
            return
        fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=parent)
        with os.fdopen(fd,'wb') as out:
            os.lseek(source_fd,0,os.SEEK_SET)
            while True:
                data=os.read(source_fd,1024*1024)
                if not data:break
                out.write(data)
            out.flush();os.fsync(out.fileno())

    def directory(self, path, *, create=False, private=False):
        path = Path(os.path.abspath(path))
        if path in self.directories:
            self.check_binding(path)
            fd = self.directories[path]
        elif path == Path(path.anchor):
            fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            self.directories[path] = fd
        else:
            parent = self.directory(path.parent, create=create)
            missing = False
            if create:
                try:os.stat(path.name, dir_fd=parent, follow_symlinks=False)
                except FileNotFoundError:missing = True
            if missing:
                try:
                    if sys.platform.startswith('linux'):
                        self.native('mkdir',dst=parent,target=path.name)
                    else:
                        os.mkdir(path.name, 0o700, dir_fd=parent)
                        os.fsync(parent)
                except FileExistsError:
                    pass
            fd = os.open(path.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
            self.directories[path] = fd
            self.parents[path] = (path.parent, identity(os.fstat(fd)))
            self.check_binding(path)
        if private:
            self.check_private(fd)
        return fd

    def check_binding(self, path):
        if path not in self.parents:
            return
        parent, expected = self.parents[path]
        self.check_binding(parent)
        actual = os.stat(path.name, dir_fd=self.directories[parent], follow_symlinks=False)
        if not stat.S_ISDIR(actual.st_mode) or identity(actual) != expected:
            raise TrashError('Verzeichnisbindung wurde während der Papierkorboperation verändert.')

    def verify(self):
        for path in self.parents:
            self.check_binding(path)
        if self.private_root is not None:
            self.check_private(self.directories[self.private_root])

    @staticmethod
    def check_private(fd):
        info = os.fstat(fd)
        if info.st_uid != os.geteuid() or info.st_mode & 0o022:
            raise TrashError('Internes Papierkorb-Staging ist nicht ausschließlich durch die Anwendung beschreibbar.')
        # Linux POSIX ACL grants are capped by these group permission bits.
        # A non-POSIX inherited ACL must never silently become a privacy proof.
        try:
            names = os.listxattr(fd)
        except (AttributeError, TypeError, OSError) as error:
            if sys.platform != 'darwin':
                raise TrashError('Zugriffstrennung des internen Stagings ist nicht überprüfbar.') from error
            libc = ctypes.CDLL(None, use_errno=True)
            size = libc.flistxattr(fd, None, 0, 0)
            if size < 0:
                raise TrashError('Zugriffstrennung des internen Stagings ist nicht überprüfbar.') from error
            buffer = ctypes.create_string_buffer(size or 1)
            if libc.flistxattr(fd, buffer, size, 0) < 0:
                raise TrashError('ACL des internen Stagings ist nicht überprüfbar.')
            names = buffer.raw[:size].decode().split('\0')
        if any('nfs4' in name.lower() or 'ntacl' in name.lower() for name in names):
            raise TrashError('Nicht geprüfte ACL im internen Papierkorb-Staging; Löschung gesperrt.')
    @staticmethod
    def qualify_filesystem(fd):
        if sys.platform.startswith('linux'):
            buffer = ctypes.create_string_buffer(256)
            libc = ctypes.CDLL(None, use_errno=True)
            if libc.fstatfs(fd, buffer):
                raise TrashError('Dateisystem des internen Stagings ist nicht überprüfbar.')
            kind = ctypes.c_long.from_buffer(buffer).value & 0xffffffff
            # Qualified local POSIX filesystem families. ZFS/Samba/NFS need a
            # separate effective-ACL/platform proof before enabling deletion.
            if kind not in {0xef53, 0x58465342, 0x9123683e, 0x01021994, 0x794c7630}:
                raise TrashError('Zugriffstrennung auf diesem Dateisystem ist noch nicht abgenommen; Löschung gesperrt.')

    def parent_fd(self, path, *, create=False):
        path = Path(os.path.abspath(path))
        if not path.is_relative_to(self.workspace):
            raise TrashError('Dateioperation außerhalb des gebundenen Workspace verweigert.')
        return self.directory(path.parent, create=create), path.name

    def info(self, path):
        try:
            parent, name = self.parent_fd(path)
            return os.stat(name, dir_fd=parent, follow_symlinks=False)
        except FileNotFoundError:
            return None

    def open_file(self, path, *, expected=None):
        parent, name = self.parent_fd(path)
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        self.files.append(fd)
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or (expected is not None and identity(info) != expected):
            raise TrashError('Dateityp oder Dateiidentität ist nicht mehr eindeutig.')
        return fd

    def sha(self, path, *, expected=None):
        fd = self.open_file(path, expected=expected)
        try:
            return digest_fd(fd)
        finally:
            self.files.remove(fd)
            os.close(fd)

    def item(self, source, target):
        if self.record is None:
            raise TrashError('Dateiübernahme ohne Löschjournal verweigert.')
        for item in self.record['files']:
            if (source.name == Path(item['path']).name or target.name == Path(item['path']).name) and (str(source).endswith('/'+item['path']) or str(target).endswith('/'+item['path'])):
                return item
        raise TrashError('Datei gehört nicht zum gebundenen Löschjournal.')

    def private_path(self, path):
        path = Path(os.path.abspath(path))
        if self.private_root is None or not path.is_relative_to(self.private_root):
            raise TrashError('Unlink außerhalb des privaten Löschbereichs verweigert.')
        parent, name = self.parent_fd(path)
        self.check_private(parent)
        return parent, name

    def unlink_private(self, path, *, expected=None):
        parent, name = self.private_path(path)
        self.verify()
        info = os.stat(name, dir_fd=parent, follow_symlinks=False)
        if not stat.S_ISREG(info.st_mode) or (expected is not None and identity(info) != expected):
            raise TrashError('Unklare Datei im privaten Löschbereich; keine Bereinigung.')
        if sys.platform.startswith('linux') and self.confined:
            self.native('unlink',dst=parent,target=name,expected=identity(info))
        else:
            os.unlink(name, dir_fd=parent)
            os.fsync(parent)

    def atomic_json(self, path, value):
        parent, name = self.parent_fd(path)
        self.check_private(parent)
        self.verify()
        old = self.info(path)
        if old is not None and (not stat.S_ISREG(old.st_mode) or old.st_uid != os.geteuid() or old.st_mode & 0o022):
            raise TrashError('Unklarer Journalbesitz; keine Ersetzung.')
        if sys.platform.startswith('linux') and self.confined:
            self.native('json',dst=parent,target=name,value=value)
            return
        temporary = '.' + uuid.uuid4().hex + '.tmp'
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as handle:
                json.dump(value, handle, ensure_ascii=False, sort_keys=True)
                handle.flush()
                os.fsync(handle.fileno())
            self.verify()
            os.replace(temporary, name, src_dir_fd=parent, dst_dir_fd=parent)
            os.fsync(parent)
        finally:
            try:
                os.unlink(temporary, dir_fd=parent)
            except FileNotFoundError:
                pass

    def read_json(self, path):
        fd = self.open_file(path)
        info = os.fstat(fd)
        if info.st_uid != os.geteuid() or info.st_mode & 0o022:
            raise TrashError('Löschjournal ist fremd beschreibbar.')
        with os.fdopen(os.dup(fd), 'r', encoding='utf-8') as handle:
            return json.load(handle)

    def walk(self, root):
        fd = self.directory(root)
        for name in sorted(os.listdir(fd)):
            path = root / name
            info = os.stat(name, dir_fd=fd, follow_symlinks=False)
            yield path, info
            if stat.S_ISDIR(info.st_mode):
                yield from self.walk(path)

    def rmdir(self, path):
        parent, name = self.private_path(path)
        self.verify()
        if sys.platform.startswith('linux') and self.confined:
            self.native('rmdir',dst=parent,target=name,expected=identity(os.fstat(self.directory(path))))
        else:
            os.rmdir(name, dir_fd=parent)
            os.fsync(parent)
        fd = self.directories.pop(path, None)
        self.parents.pop(path, None)
        if fd is not None:
            os.close(fd)
