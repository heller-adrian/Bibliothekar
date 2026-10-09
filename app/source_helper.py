from __future__ import annotations

from pathlib import Path
from typing import Any
import json
import os
import re
import stat
import subprocess

from fastapi import FastAPI, HTTPException

app = FastAPI(title="Kamera-Quellen-Helfer", version="0.47.0")
MOUNT_ROOT = Path(
    os.environ.get(
        "KAMERA_REMOVABLE_MOUNT_ROOT",
        "/sources/removable",
    )
)
# Kompatibilitaetsalias fuer bestehende Tests/Diagnosecode. In 0.29.1
# gibt es keinen separaten Host-Mount-Namespace mehr.
HOST_MOUNT_ROOT = MOUNT_ROOT
DEVICE_NODE_ROOT = Path(
    os.environ.get(
        "KAMERA_DEVICE_NODE_ROOT",
        "/dev/bibliothekar",
    )
)
ALLOWED_FS = {"vfat", "exfat", "ntfs", "ext2", "ext3", "ext4", "xfs", "btrfs"}


def run(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(list(args), check=check, capture_output=True, text=True)


def lsblk() -> dict[str, Any]:
    result = run(
        "lsblk",
        "--json",
        "--bytes",
        "--paths",
        "--output",
        "NAME,KNAME,PATH,PKNAME,TYPE,SIZE,FSTYPE,FSVER,LABEL,UUID,PARTUUID,MOUNTPOINTS,RM,HOTPLUG,TRAN,MODEL,VENDOR,SERIAL,RO",
    )
    return json.loads(result.stdout)


def flattened(nodes: list[dict[str, Any]], parent: dict[str, Any] | None = None):
    for node in nodes:
        item = dict(node)
        item["_parent"] = parent
        yield item
        yield from flattened(node.get("children") or [], item)


def safe_id(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-")[:100] or "medium"


def _kernel_name(node: dict[str, Any]) -> str:
    value = str(node.get("kname") or "").strip()
    if value:
        return Path(value).name
    value = str(node.get("path") or node.get("name") or "").strip()
    return Path(value).name


def _managed_device_node_path(kernel_name: str) -> Path:
    return DEVICE_NODE_ROOT / safe_id(kernel_name)


def _block_device_numbers(kernel_name: str) -> tuple[int, int]:
    sysfs_path = Path("/sys/class/block") / kernel_name / "dev"
    try:
        value = sysfs_path.read_text(encoding="utf-8").strip()
        major_text, minor_text = value.split(":", 1)
        major = int(major_text)
        minor = int(minor_text)
    except (OSError, ValueError) as error:
        raise RuntimeError(
            "Major/Minor des Blockgeräts konnten nicht gelesen werden: "
            + str(sysfs_path)
        ) from error
    if major < 0 or minor < 0:
        raise RuntimeError("Ungültige Major/Minor-Werte für Blockgerät.")
    return major, minor


def _node_matches_device(path: Path, major: int, minor: int) -> bool:
    try:
        info = path.stat()
    except OSError:
        return False
    return bool(
        stat.S_ISBLK(info.st_mode)
        and os.major(info.st_rdev) == major
        and os.minor(info.st_rdev) == minor
    )


def _ensure_mount_device_node(item: dict[str, Any]) -> tuple[str, bool]:
    original = Path(str(item.get("device_path") or ""))
    if original.exists():
        return str(original), False

    kernel_name = str(item.get("kernel_name") or "").strip()
    if not kernel_name:
        raise RuntimeError("Kernelname des Blockgeräts fehlt.")

    major, minor = _block_device_numbers(kernel_name)
    DEVICE_NODE_ROOT.mkdir(parents=True, exist_ok=True)
    managed = _managed_device_node_path(kernel_name)

    if managed.exists() or managed.is_symlink():
        if not _node_matches_device(managed, major, minor):
            managed.unlink(missing_ok=True)

    if not managed.exists():
        os.mknod(
            managed,
            stat.S_IFBLK | 0o600,
            os.makedev(major, minor),
        )

    if not _node_matches_device(managed, major, minor):
        managed.unlink(missing_ok=True)
        raise RuntimeError(
            "Temporärer Geräte-Node stimmt nicht mit dem erkannten Blockgerät überein."
        )

    return str(managed), True


def _remove_managed_device_node(kernel_name: str) -> None:
    if not kernel_name:
        return
    path = _managed_device_node_path(kernel_name)
    try:
        if path.exists() or path.is_symlink():
            path.unlink()
    except OSError:
        return
    try:
        DEVICE_NODE_ROOT.rmdir()
    except OSError:
        pass


def classify(parent: dict[str, Any], partition: dict[str, Any]) -> str:
    size = int(partition.get("size") or parent.get("size") or 0)
    removable = bool(parent.get("rm") or parent.get("hotplug"))
    transport = str(parent.get("tran") or "")
    model = (
        str(parent.get("model") or "") + " " + str(parent.get("vendor") or "")
    ).lower()
    if (
        removable
        and transport == "usb"
        and size <= 2 * 1024**4
        and any(word in model for word in ("card", "reader", "massstorage", "generic", "sd"))
    ):
        return "sd_card"
    return "external_drive"


def _mount_info(mount_path: str) -> dict[str, str] | None:
    result = run(
        "findmnt",
        "--json",
        "--target",
        mount_path,
        "--output",
        "TARGET,SOURCE,FSTYPE,OPTIONS",
        check=False,
    )
    if result.returncode != 0:
        return None
    try:
        rows = json.loads(result.stdout).get("filesystems") or []
        if not rows:
            return None
        info = dict(rows[0])
        actual_target = os.path.normpath(str(info.get("target") or ""))
        expected_target = os.path.normpath(str(mount_path))
        if actual_target != expected_target:
            return None
        return info
    except (ValueError, TypeError, IndexError):
        return None


def _same_device_source(actual_source: str, expected_path: str) -> bool:
    if not actual_source or not expected_path:
        return False
    try:
        return os.path.realpath(actual_source) == os.path.realpath(expected_path)
    except OSError:
        return actual_source == expected_path


def _flatten_findmnt_rows(rows: list[dict[str, Any]]):
    for row in rows:
        yield row
        yield from _flatten_findmnt_rows(row.get("children") or [])


def _cleanup_stale_managed_mounts(active_device_paths: set[str]) -> None:
    result = run(
        "findmnt",
        "--json",
        "--output",
        "TARGET,SOURCE,FSTYPE,OPTIONS",
        check=False,
    )
    if result.returncode != 0:
        return
    try:
        rows = list(
            _flatten_findmnt_rows(
                json.loads(result.stdout).get("filesystems") or []
            )
        )
    except (ValueError, TypeError):
        return

    for row in rows:
        target = str(row.get("target") or "")
        source = str(row.get("source") or "")
        if target == str(MOUNT_ROOT) or not target.startswith(str(MOUNT_ROOT) + "/"):
            continue
        if any(_same_device_source(source, path) for path in active_device_paths):
            continue
        run("umount", target, check=False)
        run("rmdir", target, check=False)

    # Legacy-Versionen verwendeten Mountpunkte wie dev-sde1/dev-sdf1.
    # Nach erfolgreichem Aushaengen koennen leere Reste gefahrlos entfernt werden.
    run(
        "find",
        str(MOUNT_ROOT),
        "-mindepth",
        "1",
        "-maxdepth",
        "1",
        "-type",
        "d",
        "-name",
        "dev-*",
        "-empty",
        "-delete",
        check=False,
    )


def devices() -> list[dict[str, Any]]:
    data = lsblk()
    flat = list(flattened(data.get("blockdevices") or []))
    active_device_paths: set[str] = set()
    for node in flat:
        if node.get("type") != "part" or not node.get("fstype"):
            continue
        path = str(node.get("path") or node.get("name") or "")
        if path:
            active_device_paths.add(path)
        kernel_name = _kernel_name(node)
        if kernel_name:
            active_device_paths.add(str(_managed_device_node_path(kernel_name)))
    _cleanup_stale_managed_mounts(active_device_paths)

    results = []
    for node in flat:
        if node.get("type") != "part" or not node.get("fstype"):
            continue
        parent = node.get("_parent") or {}
        if not (parent.get("rm") or parent.get("hotplug") or parent.get("tran") == "usb"):
            continue

        fstype = str(node.get("fstype") or "").lower()
        if fstype not in ALLOWED_FS:
            continue

        path = str(node.get("path") or node.get("name") or "")
        kernel_name = _kernel_name(node)
        managed_device_path = (
            str(_managed_device_node_path(kernel_name))
            if kernel_name
            else ""
        )
        parent_serial = str(parent.get("serial") or "").strip()
        serial_identity = (
            parent_serial + "-" + str(node.get("size") or "")
            if parent_serial
            else ""
        )
        stable_identity = (
            node.get("uuid")
            or node.get("partuuid")
            or node.get("label")
            or serial_identity
            or path
        )
        device_id = safe_id(str(stable_identity))
        mount_path = str(MOUNT_ROOT / device_id)
        info = _mount_info(mount_path)
        is_mounted = bool(info)
        mount_options = str((info or {}).get("options") or "")
        mount_source = str((info or {}).get("source") or "")

        if (
            is_mounted
            and not _same_device_source(mount_source, path)
            and not _same_device_source(mount_source, managed_device_path)
        ):
            # Staler Mount: derselbe Mountpunkt gehoert nicht mehr zur aktuell
            # erkannten Geraeteinstanz. Sicher loesen und als unmounted melden.
            run("umount", mount_path, check=False)
            run("rmdir", mount_path, check=False)
            is_mounted = False
            mount_options = ""
            mount_source = ""

        mount_read_only = bool(
            is_mounted
            and "ro" in {part.strip() for part in mount_options.split(",")}
        )

        results.append(
            {
                "device_path": path,
                "kernel_name": kernel_name,
                "device_id": device_id,
                "kind": classify(parent, node),
                "size_bytes": int(node.get("size") or 0),
                "filesystem": fstype,
                "label": str(node.get("label") or "").strip(),
                "uuid": str(node.get("uuid") or "").strip(),
                "model": str(parent.get("model") or "").strip(),
                "vendor": str(parent.get("vendor") or "").strip(),
                "serial": str(parent.get("serial") or "").strip(),
                "mounted": is_mounted,
                "mount_path": mount_path if is_mounted else None,
                # Feld bleibt fuer API-Kompatibilitaet erhalten. Seit 0.29.1
                # ist Host- und App-Mountpfad identisch.
                "host_mount_path": mount_path if is_mounted else None,
                "mount_source": mount_source if is_mounted else None,
                "mount_options": mount_options if is_mounted else None,
                "read_only": bool(is_mounted and mount_read_only),
            }
        )
    return results


def selected_device(path: str) -> dict[str, Any]:
    for item in devices():
        if item["device_path"] == path:
            return item
    raise HTTPException(
        status_code=404,
        detail="Wechselmedium wurde nicht gefunden oder ist nicht zulaessig.",
    )


@app.get("/healthz")
def healthz():
    return {"status": "ok", "version": "0.47.0", "mount_root": str(MOUNT_ROOT), "device_node_root": str(DEVICE_NODE_ROOT), "mode": "direct"}


@app.get("/devices")
def list_devices():
    found = devices()
    return {"count": len(found), "devices": found}


@app.post("/mount")
def mount_device(payload: dict[str, Any]):
    path = str(payload.get("device_path") or "").strip()
    item = selected_device(path)
    mount_path = MOUNT_ROOT / item["device_id"]

    run("mkdir", "-p", str(mount_path))
    if item["mounted"]:
        return {"mounted": True, "device": item}

    options = "ro,nosuid,nodev,noexec"
    if item["filesystem"] == "vfat":
        options += ",utf8=1,uid=568,gid=568,fmask=0133,dmask=0022"
    elif item["filesystem"] in {"exfat", "ntfs"}:
        options += ",uid=568,gid=568,umask=0022"

    try:
        mount_source, managed_node = _ensure_mount_device_node(item)
    except (OSError, RuntimeError) as error:
        run("rmdir", str(mount_path), check=False)
        raise HTTPException(
            status_code=500,
            detail=(
                "Blockgerät ist im Container nicht direkt verfügbar und "
                "konnte nicht sicher bereitgestellt werden: "
                + str(error)
            ),
        ) from error

    result = run(
        "mount",
        "-t",
        item["filesystem"],
        "-o",
        options,
        mount_source,
        str(mount_path),
        check=False,
    )
    if result.returncode != 0:
        run("rmdir", str(mount_path), check=False)
        if managed_node:
            _remove_managed_device_node(str(item.get("kernel_name") or ""))
        raise HTTPException(
            status_code=500,
            detail=(
                result.stderr
                or result.stdout
                or "Einbinden fehlgeschlagen."
            ).strip(),
        )

    refreshed = selected_device(path)
    if not refreshed.get("read_only"):
        run("umount", str(mount_path), check=False)
        run("rmdir", str(mount_path), check=False)
        if managed_node:
            _remove_managed_device_node(str(item.get("kernel_name") or ""))
        raise HTTPException(
            status_code=500,
            detail="Die Quelle konnte nicht nachweislich nur lesend eingebunden werden.",
        )
    return {"mounted": True, "device": refreshed}


@app.post("/unmount")
def unmount_device(payload: dict[str, Any]):
    path = str(payload.get("device_path") or "").strip()
    item = selected_device(path)
    if not item["mounted"]:
        return {"mounted": False, "device": item}

    mount_path = MOUNT_ROOT / item["device_id"]
    result = run("umount", str(mount_path), check=False)
    if result.returncode != 0:
        raise HTTPException(
            status_code=409,
            detail=(
                result.stderr
                or "Aushaengen fehlgeschlagen; moeglicherweise wird die Quelle noch verwendet."
            ).strip(),
        )
    run("rmdir", str(mount_path), check=False)
    _remove_managed_device_node(str(item.get("kernel_name") or ""))
    return {"mounted": False, "device": selected_device(path)}
