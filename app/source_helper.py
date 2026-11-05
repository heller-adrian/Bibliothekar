from __future__ import annotations

from pathlib import Path
from typing import Any
import json
import hashlib
import os
import re
import stat
import subprocess

from fastapi import FastAPI, HTTPException
from app import __version__
from app.source_mount_state import Ledger, UnsafeMount, directory_identity, mount_identity, protected_directory

app = FastAPI(title="Kamera-Quellen-Helfer", version=__version__)
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
    return re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-.")[:100] or "medium"


def _kernel_name(node: dict[str, Any]) -> str:
    value = str(node.get("kname") or "").strip()
    if value:
        return Path(value).name
    value = str(node.get("path") or node.get("name") or "").strip()
    return Path(value).name


def _managed_device_node_path(kernel_name: str) -> Path:
    return DEVICE_NODE_ROOT / safe_id(kernel_name)


def _block_device_numbers(kernel_name: str) -> tuple[int, int]:
    if not re.fullmatch(r"[A-Za-z0-9_-][A-Za-z0-9_.-]*", kernel_name) or kernel_name in {".", ".."}:
        raise RuntimeError("Invalid kernel device name.")
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
        info = path.lstat()
    except OSError:
        return False
    return bool(
        stat.S_ISBLK(info.st_mode)
        and os.major(info.st_rdev) == major
        and os.minor(info.st_rdev) == minor
    )


def _ensure_mount_device_node(item: dict[str, Any]) -> tuple[str, bool]:
    original = Path(str(item.get("device_path") or ""))
    kernel_name = str(item.get("kernel_name") or "").strip()
    if not kernel_name:
        raise RuntimeError("Kernelname des Blockgeräts fehlt.")

    major, minor = _block_device_numbers(kernel_name)
    if original.exists() or original.is_symlink():
        protected_directory(original.parent)
        if not _node_matches_device(original, major, minor):
            raise RuntimeError("Source is not the selected block device.")
        return str(original), False

    protected_directory(DEVICE_NODE_ROOT.parent)
    DEVICE_NODE_ROOT.mkdir(mode=0o700, exist_ok=True)
    protected_directory(DEVICE_NODE_ROOT)
    managed = _managed_device_node_path(kernel_name)

    if managed.exists() or managed.is_symlink():
        if not _node_matches_device(managed, major, minor):
            raise RuntimeError("Unknown device node already exists; refusing replacement.")

    if not managed.exists():
        os.mknod(
            managed,
            stat.S_IFBLK | 0o600,
            os.makedev(major, minor),
        )

    if not _node_matches_device(managed, major, minor):
        raise RuntimeError(
            "Temporärer Geräte-Node stimmt nicht mit dem erkannten Blockgerät überein."
        )

    return str(managed), True


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
    # A path prefix or an absent device is not ownership proof. Disconnected
    # records are intentionally retained for explicit recovery/inspection.
    return None


def _device_binding(item: dict[str, Any]) -> dict[str, Any]:
    kernel = item['kernel_name']
    major, minor = _block_device_numbers(kernel)
    sysfs = Path('/sys/class/block') / kernel
    info = sysfs.stat()
    return {'major': major, 'minor': minor, 'sysfs': [info.st_dev, info.st_ino],
            'device_id': item['device_id'], 'filesystem': item['filesystem'],
            'diskseq': ((sysfs / 'diskseq') if (sysfs / 'diskseq').exists()
                        else sysfs.resolve().parent / 'diskseq').read_text().strip()}


def _readonly(info: dict[str, Any]) -> bool:
    options = set(str(info.get('options') or '').split(','))
    return {'ro', 'nosuid', 'nodev', 'noexec'} <= options and 'rw' not in options


def _verify_owned(record: dict | None, item: dict, target: Path, info: dict) -> None:
    if not record or record.get('state') not in {'mounted', 'unmounting'}:
        raise UnsafeMount('Existing mount has no completed helper ownership proof; it will remain untouched.')
    if (record.get('device') != _device_binding(item) or record.get('mount') != mount_identity(target)
            or record.get('source') != info.get('source') or info.get('fstype') != item['filesystem']
            or not _node_matches_device(Path(str(info.get('source') or '')),
                                        record['device']['major'], record['device']['minor'])):
        raise UnsafeMount('Kernel mount or device identity differs from the ownership record; refusing access.')


def _scan_devices() -> list[dict[str, Any]]:
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
        identity = {key: node.get(key) for key in ('uuid', 'partuuid', 'label', 'size')}
        identity.update(path=path, kernel=kernel_name, serial=parent.get('serial'))
        device_id = 'media-' + hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
        mount_path = str(MOUNT_ROOT / device_id)
        info = _mount_info(mount_path)
        is_mounted = bool(info)
        mount_options = str((info or {}).get("options") or "")
        mount_source = str((info or {}).get("source") or "")

        # Listing never changes or adopts any mount. Only mount_device can
        # establish an ownership proof, under the cross-process lock.
        mount_read_only = bool(is_mounted and _readonly(info or {}))

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


def devices() -> list[dict[str, Any]]:
    found = _scan_devices()
    # A raw kernel mount must never become an importable source solely because
    # findmnt reports RO. Listing also verifies ownership after helper restart.
    try:
        with Ledger(MOUNT_ROOT).locked() as ledger:
            for item in found:
                if not item['mounted']:
                    continue
                try:
                    target = MOUNT_ROOT / item['device_id']
                    _verify_owned(ledger.read(item['device_id']), item, target,
                                  _mount_info(str(target)) or {})
                    if not item['read_only']:
                        raise UnsafeMount('Mount is not verifiably read-only.')
                except (OSError, RuntimeError, ValueError, KeyError) as error:
                    _block_import(item, str(error))
    except (OSError, RuntimeError, ValueError) as error:
        for item in found:
            _block_import(item, str(error))
    return found


def _block_import(item: dict, reason: str):
    item.update(mounted=False, read_only=False, mount_path=None,
                host_mount_path=None, ownership_error=reason)


def selected_device(path: str) -> dict[str, Any]:
    for item in _scan_devices():
        if item["device_path"] == path:
            return item
    raise HTTPException(
        status_code=404,
        detail="Wechselmedium wurde nicht gefunden oder ist nicht zulaessig.",
    )


@app.get("/healthz")
def healthz():
    return {"status": "ok", "version": __version__, "mount_root": str(MOUNT_ROOT), "device_node_root": str(DEVICE_NODE_ROOT), "mode": "direct"}


@app.get("/devices")
def list_devices():
    found = devices()
    return {"count": len(found), "devices": found}


def _operation(payload: dict[str, Any], *, unmount: bool):
    try:
        with Ledger(MOUNT_ROOT).locked() as ledger:
            item = selected_device(str(payload.get('device_path') or '').strip())
            target = MOUNT_ROOT / item['device_id']
            record = ledger.read(item['device_id'])
            info = _mount_info(str(target))
            if info:
                _verify_owned(record, item, target, info)
                if not unmount:
                    if not _readonly(info):
                        raise UnsafeMount('Source is not verifiably read-only; import is blocked.')
                    return {'mounted': True, 'device': item}
                record['state'] = 'unmounting'
                ledger.write(item['device_id'], record)
                # Identity is checked again immediately before the syscall.
                _verify_owned(record, item, target, _mount_info(str(target)) or {})
                result = run("umount", str(target), check=False)
                if result.returncode or _mount_info(str(target)):
                    raise UnsafeMount('Unmount failed or mount changed; ownership evidence has been retained.')
                if directory_identity(target) != record['target']:
                    raise UnsafeMount('Mountpoint directory changed; refusing cleanup.')
                target.rmdir()  # only our recorded, empty directory
                ledger.delete(item['device_id'])
                return {'mounted': False, 'device': selected_device(item['device_path'])}
            if record:
                # A stopped helper never guesses that an existing/new mount is its own.
                if target.exists():
                    if directory_identity(target) != record['target']:
                        raise UnsafeMount('Interrupted mountpoint identity changed; manual inspection required.')
                    target.rmdir()  # nonempty and foreign content cannot be removed
                ledger.delete(item['device_id'])
            if unmount:
                return {'mounted': False, 'device': item}
            binding = _device_binding(item)
            # Qualify kernel identity capability before any mount or journal mutation.
            mount_identity(MOUNT_ROOT)
            target.mkdir(mode=0o755)  # EEXIST never means ownership
            record = {'state': 'prepared', 'device': binding, 'target': directory_identity(target)}
            ledger.write(item['device_id'], record)
            source, _managed = _ensure_mount_device_node(item)
            options = "ro,nosuid,nodev,noexec"
            if item['filesystem'] == 'vfat':
                options += ',utf8=1,uid=568,gid=568,fmask=0133,dmask=0022'
            elif item['filesystem'] in {'exfat', 'ntfs'}:
                options += ',uid=568,gid=568,umask=0022'
            if binding != _device_binding(selected_device(item['device_path'])):
                raise UnsafeMount('Device changed before mount.')
            result = run("mount", '-t', item['filesystem'], '-o', options, source, str(target), check=False)
            if result.returncode:
                raise UnsafeMount('Mount failed; prepared ownership record retained: ' + str(result.stderr or ''))
            info = _mount_info(str(target)) or {}
            record.update(state='mounted', mount=mount_identity(target), source=source)
            if binding != _device_binding(selected_device(item['device_path'])):
                raise UnsafeMount('Device changed during mount; uncertain mount remains untouched.')
            if (info.get('source') != source or info.get('fstype') != item['filesystem']
                    or not _node_matches_device(Path(source), binding['major'], binding['minor'])):
                raise UnsafeMount('Mounted source cannot be proven; uncertain mount remains untouched.')
            ledger.write(item['device_id'], record)
            if not _readonly(info):
                raise UnsafeMount("Die Quelle konnte nicht nachweislich nur lesend eingebunden werden.")
            return {'mounted': True, 'device': selected_device(item['device_path'])}
    except (OSError, RuntimeError, ValueError, KeyError) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.post('/mount')
def mount_device(payload: dict[str, Any]):
    return _operation(payload, unmount=False)


@app.post('/unmount')
def unmount_device(payload: dict[str, Any]):
    return _operation(payload, unmount=True)
