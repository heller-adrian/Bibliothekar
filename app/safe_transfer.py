from __future__ import annotations

from pathlib import Path
import errno
import hashlib
import os
import shutil
import stat
import uuid
from typing import Any


class SafeTransferError(RuntimeError):
    """Raised when a verified no-overwrite transfer cannot be completed safely."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def _fsync_directory(path: Path) -> None:
    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    descriptor = os.open(path, flags)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _verify_regular_file(
    path: Path,
    *,
    expected_size: int | None = None,
    expected_sha256: str | None = None,
) -> os.stat_result:
    try:
        info = os.lstat(path)
    except FileNotFoundError as error:
        raise SafeTransferError("Datei fehlt: " + str(path)) from error
    if not stat.S_ISREG(info.st_mode):
        raise SafeTransferError("Pfad ist keine reguläre Datei: " + str(path))
    if expected_size is not None and int(info.st_size) != int(expected_size):
        raise SafeTransferError("Dateigröße weicht ab: " + str(path))
    digest = str(expected_sha256 or "").strip()
    if digest and sha256_file(path) != digest:
        raise SafeTransferError("SHA-256-Summe weicht ab: " + str(path))
    return info


def _same_filesystem(source: Path, destination_parent: Path) -> bool:
    return int(os.lstat(source).st_dev) == int(os.lstat(destination_parent).st_dev)


def move_verified_no_overwrite(
    source: Path,
    destination: Path,
    *,
    expected_size: int | None = None,
    expected_sha256: str | None = None,
) -> dict[str, Any]:
    """Move one regular file without overwrite, safely across filesystems.

    Same-filesystem moves use link+unlink so the destination can never silently
    replace an existing file. Cross-filesystem moves copy to a private temporary
    file in the destination directory, fsync and verify it, publish it using a
    no-overwrite hardlink on the destination filesystem, verify again, and only
    then remove the source.
    """

    source = source.resolve(strict=False)
    destination = destination.resolve(strict=False)
    source_info = _verify_regular_file(
        source,
        expected_size=expected_size,
        expected_sha256=expected_sha256,
    )

    if destination.exists() or destination.is_symlink():
        raise SafeTransferError("Zieldatei existiert bereits: " + str(destination))

    destination.parent.mkdir(parents=True, exist_ok=True)

    hardlink_created = False
    if _same_filesystem(source, destination.parent):
        try:
            os.link(source, destination, follow_symlinks=False)
            hardlink_created = True
        except FileExistsError as error:
            raise SafeTransferError(
                "Zieldatei ist während der Übertragung entstanden: " + str(destination)
            ) from error
        except OSError as error:
            # Docker/TrueNAS-Bind-Mounts können dieselbe st_dev-ID melden,
            # obwohl ein Hardlink über die Mount-Grenze mit EXDEV verboten ist.
            # In genau diesem Fall fällt der Transfer auf den verifizierten
            # Copy-Verify-Delete-Pfad zurück.
            if error.errno != errno.EXDEV:
                raise SafeTransferError(
                    "Sicherer Hardlink-Schritt fehlgeschlagen: " + str(destination)
                ) from error

        if hardlink_created:
            try:
                destination_info = _verify_regular_file(
                    destination,
                    expected_size=expected_size,
                    expected_sha256=expected_sha256,
                )
                if (
                    int(destination_info.st_dev) != int(source_info.st_dev)
                    or int(destination_info.st_ino) != int(source_info.st_ino)
                ):
                    raise SafeTransferError(
                        "Der sichere Link-Schritt konnte nicht bestätigt werden: "
                        + str(destination)
                    )
                os.unlink(source)
                _fsync_directory(source.parent)
                _fsync_directory(destination.parent)
                return {"method": "link_unlink", "destination": str(destination)}
            except Exception:
                if destination.exists() and source.exists():
                    destination.unlink(missing_ok=True)
                    _fsync_directory(destination.parent)
                raise

    temporary = destination.parent / (
        "." + destination.name + ".bibliothekar-" + uuid.uuid4().hex + ".part"
    )
    published = False
    try:
        with source.open("rb") as source_handle, temporary.open("xb") as target_handle:
            shutil.copyfileobj(source_handle, target_handle, length=1024 * 1024)
            target_handle.flush()
            os.fsync(target_handle.fileno())

        os.utime(
            temporary,
            ns=(int(source_info.st_atime_ns), int(source_info.st_mtime_ns)),
        )
        _verify_regular_file(
            temporary,
            expected_size=expected_size,
            expected_sha256=expected_sha256,
        )

        try:
            os.link(temporary, destination, follow_symlinks=False)
        except FileExistsError as error:
            raise SafeTransferError(
                "Zieldatei ist während der Übertragung entstanden: " + str(destination)
            ) from error
        published = True
        temporary.unlink(missing_ok=True)
        _fsync_directory(destination.parent)

        _verify_regular_file(
            destination,
            expected_size=expected_size,
            expected_sha256=expected_sha256,
        )

        os.unlink(source)
        _fsync_directory(source.parent)
        return {"method": "copy_verify_delete", "destination": str(destination)}
    except Exception:
        temporary.unlink(missing_ok=True)
        if published and destination.exists() and source.exists():
            destination.unlink(missing_ok=True)
            _fsync_directory(destination.parent)
        raise


def reconcile_migrated_file(
    source: Path,
    destination: Path,
    *,
    expected_size: int,
    expected_sha256: str,
) -> dict[str, Any]:
    """Idempotently move a known file during layout migration."""

    source_exists = source.exists() or source.is_symlink()
    destination_exists = destination.exists() or destination.is_symlink()

    if source_exists and destination_exists:
        _verify_regular_file(
            source,
            expected_size=expected_size,
            expected_sha256=expected_sha256,
        )
        _verify_regular_file(
            destination,
            expected_size=expected_size,
            expected_sha256=expected_sha256,
        )
        source.unlink()
        _fsync_directory(source.parent)
        return {"status": "deduplicated_verified_destination"}

    if destination_exists and not source_exists:
        _verify_regular_file(
            destination,
            expected_size=expected_size,
            expected_sha256=expected_sha256,
        )
        return {"status": "already_migrated"}

    if source_exists and not destination_exists:
        result = move_verified_no_overwrite(
            source,
            destination,
            expected_size=expected_size,
            expected_sha256=expected_sha256,
        )
        return {"status": "migrated", **result}

    raise SafeTransferError(
        "Migration kann nicht fortgesetzt werden, weil Quelle und Ziel fehlen: "
        + str(source)
    )
