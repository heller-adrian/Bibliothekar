"""Kernel evidence for the one-dataset adoption contract.

The container and the TrueNAS host share a kernel. A bind mount can change
the visible path and mount ID, but retains the ZFS source, device and inode.
"""
from dataclasses import dataclass
import os
from pathlib import Path, PurePosixPath
import re


class DatasetError(RuntimeError):
    pass


DATASET_REQUIRED = (
    "Quelle und Ziel liegen nicht auf demselben ZFS-Dataset. Die Bestandsübernahme "
    "unterstützt ausschließlich Verschiebungen innerhalb eines gemeinsamen Datasets. "
    "Kopiere deine bestehende Sammlung gegebenenfalls vorher auf das Dataset des Zielarchivs."
)


@dataclass(frozen=True)
class Mount:
    device: str
    root: PurePosixPath
    target: PurePosixPath
    filesystem: str
    source: str


def _unescape(field):
    return re.sub(r"\\([0-7]{3})", lambda match: chr(int(match[1], 8)), field)


def mount_table():
    mounts = {}
    for line in Path("/proc/self/mountinfo").read_text(errors="surrogateescape").splitlines():
        leading, following = line.split(" - ", 1)
        identity, _, device, root, target, *_ = leading.split()
        filesystem, source, *_ = following.split()
        mounts[int(identity)] = Mount(device, PurePosixPath(_unescape(root)),
                                      PurePosixPath(_unescape(target)), filesystem, _unescape(source))
    return mounts


def mount_id(descriptor):
    for line in Path(f"/proc/self/fdinfo/{descriptor}").read_text().splitlines():
        key, _, value = line.partition(":")
        if key == "mnt_id":
            return int(value.strip())
    raise DatasetError("Die aktive Einbindung des Übernahmeordners ist nicht nachweisbar.")


def _mounted_directory(path, descriptor, mounts):
    path = PurePosixPath(path)
    mount = mounts[mount_id(descriptor)]
    info = os.fstat(descriptor)
    if not path.is_relative_to(mount.target) or mount.device != f"{os.major(info.st_dev)}:{os.minor(info.st_dev)}":
        raise DatasetError("Der Dateisystemnachweis passt nicht zum geöffneten Übernahmeordner.")
    if any(item.target != path and item.target.is_relative_to(path) for item in mounts.values()):
        raise DatasetError("Im Übernahmeordner befindet sich eine weitere Einbindung.")
    return mount, mount.root / path.relative_to(mount.target)


def prove(source, archive, source_fd, archive_fd):
    """Prove both directories by their actual kernel mount and dataset identity."""
    try:
        mounts = mount_table()
        left, source_root = _mounted_directory(source, source_fd, mounts)
        right, archive_root = _mounted_directory(archive, archive_fd, mounts)
    except (OSError, KeyError, ValueError) as error:
        raise DatasetError("Die ZFS-Dataset-Zuordnung ist nicht zuverlässig nachweisbar.") from error
    if (left.filesystem != "zfs" or right.filesystem != "zfs" or not left.source
            or left.source in {"-", "none"} or (left.source, left.device) != (right.source, right.device)):
        raise DatasetError(DATASET_REQUIRED)
    if source_root.is_relative_to(archive_root) or archive_root.is_relative_to(source_root):
        raise DatasetError("Quell- und Archivordner überschneiden sich innerhalb des ZFS-Datasets.")
    return {"dataset": left.source, "device": left.device,
            "source_directory": str(source_root), "archive_directory": str(archive_root)}


def revalidate(expected, source, archive, source_fd, archive_fd):
    evidence = prove(source, archive, source_fd, archive_fd)
    if evidence != expected:
        raise DatasetError("Die nachgewiesene Dataset-Zuordnung hat sich seit der Auswahl geändert.")
    return evidence
