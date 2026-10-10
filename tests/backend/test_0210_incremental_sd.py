from __future__ import annotations

from app import __version__ as PACKAGE_VERSION
from pathlib import Path
import hashlib
import json
import subprocess

from app import main
from app.database import (
    create_job,
    get_job,
    initialize_database,
    list_imported_source_files,
    store_imported_source_files,
)
from app import source_helper


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_0210_version_and_schema(tmp_path: Path):
    assert main.APP_VERSION == PACKAGE_VERSION
    assert main.RELEASE_VERSION == "0.50.0"
    db = tmp_path / "kamera.sqlite3"
    status = initialize_database(db)
    assert 38 in status["applied_versions"]
    assert max(status["applied_versions"]) >= 38
    assert "imported_source_files" in status["tables"]


def test_create_job_keeps_source_device_id(tmp_path: Path):
    db = tmp_path / "kamera.sqlite3"
    initialize_database(db)
    create_job(
        db,
        job_id="JOB_1",
        kind="sd_import",
        trigger_type="manual",
        operation="folder_import",
        source_path="/media/card",
        source_device_id="ABCD-1234",
    )
    assert get_job(db, "JOB_1")["source_device_id"] == "ABCD-1234"


def test_import_history_persists_exact_file_identity(tmp_path: Path):
    db = tmp_path / "kamera.sqlite3"
    initialize_database(db)
    store_imported_source_files(
        db,
        source_device_id="CARD-1",
        job_id="JOB-OLD",
        entries=[{
            "relative_path": "DCIM/101_FUJI/DSCF0001.JPG",
            "size_bytes": 4,
            "modified_at_ns": 123,
            "sha256": _sha(b"same"),
        }],
    )
    rows = list_imported_source_files(db, "CARD-1")
    assert len(rows) == 1
    assert rows[0]["relative_path"].endswith("DSCF0001.JPG")
    assert rows[0]["sha256"] == _sha(b"same")


def test_import_source_summary_counts_old_new_changed(tmp_path: Path, monkeypatch):
    db = tmp_path / "kamera.sqlite3"
    initialize_database(db)
    root = tmp_path / "removable"
    card = root / "CARD-1"
    card.mkdir(parents=True)
    old = card / "old.jpg"
    new = card / "new.jpg"
    changed = card / "changed.jpg"
    old.write_bytes(b"old")
    new.write_bytes(b"new")
    changed.write_bytes(b"changed-now")

    old_stat = old.stat()
    changed_stat = changed.stat()
    store_imported_source_files(
        db,
        source_device_id="CARD-1",
        job_id="JOB-OLD",
        entries=[
            {
                "relative_path": "old.jpg",
                "size_bytes": old_stat.st_size,
                "modified_at_ns": old_stat.st_mtime_ns,
                "sha256": _sha(b"old"),
            },
            {
                "relative_path": "changed.jpg",
                "size_bytes": changed_stat.st_size + 1,
                "modified_at_ns": changed_stat.st_mtime_ns - 1,
                "sha256": _sha(b"different"),
            },
        ],
    )
    monkeypatch.setattr(main, "DATABASE_FILE", db)
    summary = main.import_source_summary(card, "removable", root)
    assert summary["already_imported_file_count"] == 1
    assert summary["new_file_count"] == 1
    assert summary["changed_file_count"] == 1


def test_source_helper_rejects_stale_mount_for_current_device(monkeypatch):
    data = {
        "blockdevices": [{
            "name": "/dev/sde",
            "path": "/dev/sde",
            "type": "disk",
            "size": 32_000_000_000,
            "rm": True,
            "hotplug": True,
            "tran": "usb",
            "model": "MassStorageClass",
            "vendor": "",
            "serial": "",
            "children": [{
                "name": "/dev/sde1",
                "path": "/dev/sde1",
                "type": "part",
                "fstype": "vfat",
                "size": 32_000_000_000,
                "uuid": "",
                "label": "",
                "mountpoints": [],
            }],
        }]
    }
    monkeypatch.setattr(source_helper, "lsblk", lambda: data)
    calls: list[tuple[str, ...]] = []

    def fake_run(*args: str, check: bool = True):
        calls.append(tuple(args))
        if "--submounts" in args:
            return subprocess.CompletedProcess(args, 0, json.dumps({"filesystems": []}), "")
        if "findmnt" in args and "--target" in args:
            return subprocess.CompletedProcess(
                args,
                0,
                json.dumps({"filesystems": [{
                    "target": str(source_helper.HOST_MOUNT_ROOT / "dev-sde1"),
                    "source": "/dev/sdf1",
                    "fstype": "vfat",
                    "options": "ro,nosuid,nodev,noexec",
                }]}),
                "",
            )
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(source_helper, "run", fake_run)
    devices = source_helper.devices()
    assert len(devices) == 1
    assert devices[0]["device_path"] == "/dev/sde1"
    assert devices[0]["mounted"] is False
    assert any("umount" in call for call in calls)
