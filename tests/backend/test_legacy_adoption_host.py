import base64
import ctypes
import errno
import hashlib
import json
import os
import signal
import sys

import pytest

from app import legacy_adoption_host as host


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _proof(path):
    return {"stamp": host.stamp(path.stat()), "sha256": _sha(path.read_bytes())}


def _macos_rename(source, source_name, target, target_name):
    rename = ctypes.CDLL(None, use_errno=True).renameatx_np
    rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    rename.restype = ctypes.c_int
    if rename(source, os.fsencode(source_name), target, os.fsencode(target_name), 4):  # RENAME_EXCL
        code = ctypes.get_errno()
        raise OSError(code, os.strerror(code), target_name)


@pytest.fixture
def package(tmp_path, monkeypatch):
    private = tmp_path / "appdata"
    source = tmp_path / "source"
    archive = tmp_path / "archive"
    for directory in (private, source, archive, archive / "event"):
        directory.mkdir()
    for name in ("execution.lock", "journal.jsonl"):
        (private / name).touch()
    (source / "photo.raf").write_bytes(b"raw")
    (source / "photo.raf.xmp").write_bytes(b"sidecar")
    old_document = archive / "event/event.json"
    old_document.write_bytes(b'{"old":true}')
    new_document = b'{"new":true}'
    monkeypatch.setattr(host, "revalidate", lambda *args: None)
    if sys.platform == "darwin":
        monkeypatch.setattr(host, "mount_id", lambda _fd: 1)
        monkeypatch.setattr(host, "rename_noreplace", _macos_rename)
    plan = {
        "format": 1,
        "plan_id": "b" * 32, "job_id": "a" * 32, "library_id": "secondary",
        "dataset": {"dataset": "fixture/media"},
        "source_inode": host.inode(source.stat()), "archive_inode": host.inode(archive.stat()),
        "host": {"package": str(private), "source": str(source), "archive": str(archive)},
        "directories": ["event/all"],
        "moves": [{"source": path.name, "target": "event/all/" + path.name, **_proof(path)}
                  for path in sorted(source.iterdir())],
        "documents": [{"path": "event/event.json", "original": _proof(old_document),
                       "sha256": _sha(new_document), "content": base64.b64encode(new_document).decode("ascii")}],
    }
    encoded = host.json_bytes(plan)
    binding = _sha(encoded)
    (private / "manifest.json").write_bytes(encoded)
    return private, source, archive, plan, binding


def _command(package, mode):
    private, source, archive, _, binding = package
    device, inode = host.inode(private.stat())
    return [mode, "--package", str(private), "--source", str(source), "--archive", str(archive),
            "--sha256", binding, "--package-device", str(device), "--package-inode", str(inode)]


def _permit(package, mode):
    private, _, _, _, binding = package
    (private / "permission.json").write_bytes(host.json_bytes({"manifest": binding, "mode": mode}))


def test_resume_after_rename_and_keep_original_event_document(package, monkeypatch):
    private, source, archive, plan, _ = package
    rename = host.rename_noreplace

    def interrupt(src, src_name, dst, dst_name):
        rename(src, src_name, dst, dst_name)
        if src_name == "photo.raf":
            raise KeyboardInterrupt

    _permit(package, "apply")
    with monkeypatch.context() as interrupted:
        interrupted.setattr(host, "rename_noreplace", interrupt)
        with pytest.raises(KeyboardInterrupt):
            host.main(_command(package, "apply"))
    assert not (source / "photo.raf").exists()
    assert (archive / "event/all/photo.raf").read_bytes() == b"raw"
    assert json.loads((private / "status.json").read_bytes())["state"] == "running"
    # A torn append cannot hide the durable forward intent.
    with (private / "journal.jsonl").open("ab") as stream:
        stream.write(b'{"incomplete":')
    assert host.main(_command(package, "apply")) == 0
    assert host.main(_command(package, "apply")) == 0
    assert (archive / "event/event.json").read_bytes() == b'{"new":true}'
    holding = archive / (".bibliothekar-adoption-" + plan["plan_id"])
    assert (holding / "original-0.json").read_bytes() == b'{"old":true}'
    assert (archive / "event/all/photo.raf.xmp").read_bytes() == b"sidecar"
    assert json.loads((private / "status.json").read_bytes())["state"] == "completed"

    _permit(package, "rollback")
    assert host.main(_command(package, "rollback")) == 0
    assert host.main(_command(package, "rollback")) == 0
    assert (archive / "event/event.json").read_bytes() == b'{"old":true}'
    assert (source / "photo.raf").read_bytes() == b"raw"
    assert (source / "photo.raf.xmp").read_bytes() == b"sidecar"
    assert not list((archive / "event/all").iterdir())
    assert json.loads((private / "status.json").read_bytes())["state"] == "rolled_back"


@pytest.mark.parametrize("point", ["before", "after"])
def test_real_sigkill_during_media_move_resumes_from_journal(package, point):
    _, source, archive, _, _ = package
    rename = host.rename_noreplace
    _permit(package, "apply")

    def kill_at_rename(src, src_name, dst, dst_name):
        if src_name != "photo.raf":
            return rename(src, src_name, dst, dst_name)
        if point == "after":
            rename(src, src_name, dst, dst_name)
        os.kill(os.getpid(), signal.SIGKILL)

    child = os.fork()
    if child == 0:
        host.rename_noreplace = kill_at_rename
        os._exit(host.main(_command(package, "apply")))
    _, status = os.waitpid(child, 0)
    assert os.WIFSIGNALED(status) and os.WTERMSIG(status) == signal.SIGKILL
    assert (source / "photo.raf").exists() == (point == "before")
    assert host.main(_command(package, "apply")) == 0
    assert (archive / "event/all/photo.raf").read_bytes() == b"raw"
    assert not (source / "photo.raf").exists()


def test_script_rechecks_dataset_permissions_and_source_identity(package, monkeypatch):
    private, source, archive, _, _ = package
    _permit(package, "apply")

    def wrong_dataset(*_args):
        raise host.DatasetError("synthetic host dataset changed")

    with monkeypatch.context() as rejected:
        rejected.setattr(host, "revalidate", wrong_dataset)
        assert host.main(_command(package, "apply")) == 1
        assert not (archive / "event/all").exists()
    with monkeypatch.context() as denied:
        denied.setattr(host.os, "access", lambda *args, **kwargs: False)
        assert host.main(_command(package, "apply")) == 1
        assert not (archive / "event/all").exists()
    (source / "photo.raf").write_bytes(b"changed")
    assert host.main(_command(package, "apply")) == 1
    assert (source / "photo.raf").read_bytes() == b"changed"
    assert not (archive / "event/all/photo.raf").exists()
    assert json.loads((private / "status.json").read_bytes())["state"] == "attention_required"


def test_conflicting_file_and_cross_mount_error_do_not_replace_or_copy(package, monkeypatch):
    private, source, archive, _, _ = package
    _permit(package, "apply")
    (archive / "event/all").mkdir()
    existing = archive / "event/all/photo.raf"
    existing.write_bytes(b"unrelated")
    assert host.main(_command(package, "apply")) == 1
    assert existing.read_bytes() == b"unrelated"
    assert (source / "photo.raf").read_bytes() == b"raw"
    existing.unlink()

    def cross_mount(*args):
        raise OSError(errno.EXDEV, "synthetic mount boundary")

    monkeypatch.setattr(host, "rename_noreplace", cross_mount)
    assert host.main(_command(package, "apply")) == 1
    assert not existing.exists()
    assert (source / "photo.raf").read_bytes() == b"raw"
    assert json.loads((private / "status.json").read_bytes())["state"] == "attention_required"


def test_manifest_binding_and_interprocess_lock(package):
    private, source, archive, plan, _ = package
    _permit(package, "apply")
    with host.directory(str(private), host.inode(private.stat())) as descriptor, host.package_lock(descriptor):
        assert host.main(_command(package, "apply")) == 1
    assert (source / "photo.raf").exists()
    plan["moves"][0]["target"] = "event/other.raf"
    (private / "manifest.json").write_bytes(host.json_bytes(plan))
    assert host.main(_command(package, "apply")) == 1
    assert not (archive / "event/other.raf").exists()
    assert not (private / "status.json").exists()


def test_refuses_symlink_parent_and_unreleased_command(package, tmp_path):
    private, source, archive, _, _ = package
    outside = tmp_path / "outside"
    outside.mkdir()
    (archive / "event/all").symlink_to(outside, target_is_directory=True)
    _permit(package, "rollback")
    assert host.main(_command(package, "apply")) == 1
    assert not (private / "status.json").exists()
    _permit(package, "apply")
    assert host.main(_command(package, "apply")) == 1
    assert not list(outside.iterdir())
    assert (source / "photo.raf").exists()
