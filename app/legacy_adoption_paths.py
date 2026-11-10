"""Read-only filesystem bindings shared by legacy inventory and verification."""
from contextlib import contextmanager
import os
from pathlib import Path
import stat
import sys

from app.legacy_adoption_dataset import mount_id

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
        if sys.platform == "linux" and mount_id(parent) != mount_id(descriptor):
            raise AdoptionError("Ein Unterordner führt über eine Mountgrenze.")
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


@contextmanager
def relative_parent(root_fd, relative: str):
    """Open the parent under a held root without traversing another filesystem."""
    from contextlib import ExitStack

    parts = relative.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise AdoptionError("Ungültiger relativer Dateipfad.")
    device = os.fstat(root_fd).st_dev
    with ExitStack() as stack:
        directory = root_fd
        for part in parts[:-1]:
            info = os.stat(part, dir_fd=directory, follow_symlinks=False)
            if info.st_dev != device or not stat.S_ISDIR(info.st_mode):
                raise AdoptionError("Der relative Pfad führt über einen Link oder eine Dateisystemgrenze.")
            directory = stack.enter_context(bound_child_directory(directory, part, directory_identity(info)))
        yield directory, parts[-1]


def target_key(relative: str) -> str:
    from unicodedata import normalize

    return normalize("NFC", relative).casefold()


def validate_target(relative: str) -> None:
    from app.event_structure import _clean_name, EventPreviewError

    for part in relative.split("/"):
        if not part or part.strip() != part or len(part.encode("utf-8")) > 255:
            raise AdoptionError("Für SMB ungeeigneter Zielpfad: " + relative)
        try:
            _clean_name(part, "Zielpfad")
        except EventPreviewError as error:
            raise AdoptionError(f"{error} ({relative})") from error


def walk_bound_files(root_fd, prefix, on_directory=None):
    """Yield each regular file under an event, with its held directory."""
    device = os.fstat(root_fd).st_dev

    def walk(directory, relative, depth):
        if depth > 80:
            raise AdoptionError("Die Verzeichnistiefe überschreitet das Limit.")
        original = file_identity(os.fstat(directory))
        with os.scandir(directory) as entries:
            for entry in entries:
                path = relative / entry.name
                validate_target(str(path))
                info = entry.stat(follow_symlinks=False)
                if info.st_dev != device:
                    raise AdoptionError("Dateisystemgrenze im Archiv: " + str(path))
                if stat.S_ISDIR(info.st_mode):
                    with bound_child_directory(directory, entry.name, directory_identity(info)) as child:
                        yield from walk(child, path, depth + 1)
                elif stat.S_ISREG(info.st_mode):
                    yield str(path), directory, entry.name, info
                else:
                    raise AdoptionError("Unzulässiger Archivpfad: " + str(path))
        if original != file_identity(os.fstat(directory)):
            raise AdoptionError("Archivordner während der Prüfung verändert: " + str(relative))
        if on_directory is not None:
            on_directory(str(relative), original)

    with relative_parent(root_fd, str(prefix / ".binding")) as (directory, _):
        yield from walk(directory, prefix, 0)
