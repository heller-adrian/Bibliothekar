"""Read-only filesystem bindings shared by legacy inventory and verification."""
from contextlib import contextmanager
import os
from pathlib import Path
import stat

from app.pipeline import sha256_stream


class AdoptionError(RuntimeError):
    pass


_DIRECTORY = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
_FILE = os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW


def directory_identity(info):
    return info.st_dev, info.st_ino


def file_identity(info):
    return (*directory_identity(info), info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def absolute_root(value: Path) -> Path:
    path = Path(value)
    if path.anchor != "/" or ".." in path.parts:
        raise AdoptionError("Die Übernahme benötigt einen absoluten, eindeutigen Ordnerpfad.")
    return path


@contextmanager
def bound_directory(path: Path, expected=None):
    path = absolute_root(path)
    descriptors = [os.open("/", _DIRECTORY)]
    try:
        for part in path.parts[1:]:
            descriptors.append(os.open(part, _DIRECTORY, dir_fd=descriptors[-1]))
        descriptor = descriptors[-1]
        if expected is not None and directory_identity(os.fstat(descriptor)) != expected:
            raise AdoptionError("Die Identität des Übernahmeordners hat sich geändert.")
        yield descriptor
        for owner, part, opened in zip(descriptors, path.parts[1:], descriptors[1:]):
            named = os.stat(part, dir_fd=owner, follow_symlinks=False)
            if directory_identity(named) != directory_identity(os.fstat(opened)):
                raise AdoptionError("Der Übernahmeordner wurde während der Prüfung ausgetauscht.")
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


@contextmanager
def bound_child_directory(parent, name, expected):
    descriptor = os.open(name, _DIRECTORY, dir_fd=parent)
    try:
        if directory_identity(os.fstat(descriptor)) != expected:
            raise AdoptionError("Ein Unterordner wurde während der Prüfung ausgetauscht.")
        yield descriptor
        named = os.stat(name, dir_fd=parent, follow_symlinks=False)
        if directory_identity(named) != expected:
            raise AdoptionError("Ein Unterordner wurde während der Prüfung ausgetauscht.")
    finally:
        os.close(descriptor)


@contextmanager
def bound_file(parent, name, expected=None):
    descriptor = os.open(name, _FILE, dir_fd=parent)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode):
            raise AdoptionError("Der Pfad bezeichnet keine reguläre Datei.")
        identity = file_identity(info)
        if expected is not None and identity != expected:
            raise AdoptionError("Die Datei wurde während der Prüfung ausgetauscht.")
        yield descriptor, info
        if (
            file_identity(os.fstat(descriptor)) != identity
            or file_identity(os.stat(name, dir_fd=parent, follow_symlinks=False)) != identity
        ):
            raise AdoptionError("Die Datei wurde während der Prüfung verändert.")
    finally:
        os.close(descriptor)


def bound_sha256(descriptor, cancellation_callback=None):
    with os.fdopen(os.dup(descriptor), "rb") as handle:
        handle.seek(0)
        return sha256_stream(handle, cancellation_callback)
