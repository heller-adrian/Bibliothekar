import base64
import ctypes
import errno
import hashlib
import json
import os
import signal
import sys
from pathlib import Path

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
def package(tmp_path, monkeypatch, request):
    private = tmp_path / "appdata"
    native = os.environ.get("ADOPTION_ZFS_ROOT") if getattr(request, "param", None) else None
    media = Path(native) / tmp_path.name if native else tmp_path
    media.mkdir(exist_ok=True)
    source = media / "source"
    archive = media / "archive"
    for directory in (private, source, archive, archive / "event"):
        directory.mkdir()
    for name in ("execution.lock", "journal.jsonl"):
        (private / name).touch()
    (source / "photo.raf").write_bytes(b"raw")
    (source / "photo.raf.xmp").write_bytes(b"sidecar")
    old_document = archive / "event/event.json"
    old_document.write_bytes(b'{"old":true}')
    new_document = b'{"new":true}'
    evidence = {"dataset": "fixture/media"}
    if native:
        from app.legacy_adoption_dataset import prove
        with host.directory(str(source), host.inode(source.stat())) as left, \
                host.directory(str(archive), host.inode(archive.stat())) as right:
            evidence = prove(source, archive, left, right)
    else:
        monkeypatch.setattr(host, "revalidate", lambda *args: None)
    if sys.platform == "darwin":
        monkeypatch.setattr(host, "mount_id", lambda _fd: 1)
        monkeypatch.setattr(host, "rename_noreplace", _macos_rename)
    plan = {
        "format": 1,
        "plan_id": "b" * 32, "job_id": "a" * 32, "library_id": "secondary",
        "dataset": evidence,
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


@pytest.mark.parametrize("package", [True], indirect=True, ids=["native-zfs"])
def test_metadata_only_identity_change_resumes_after_partial_move(package, monkeypatch):
    private, source, archive, plan, _ = package
    untouched = source / "photo.raf.xmp"
    expected = plan["moves"][1]
    rename = host.rename_noreplace

    def interrupt(src, src_name, dst, dst_name):
        rename(src, src_name, dst, dst_name)
        raise KeyboardInterrupt

    _permit(package, "apply")
    with monkeypatch.context() as interrupted:
        interrupted.setattr(host, "rename_noreplace", interrupt)
        with pytest.raises(KeyboardInterrupt):
            host.main(_command(package, "apply"))
    moved = archive / "event/all/photo.raf"
    assert moved.read_bytes() == b"raw"
    existing_inode = moved.stat().st_ino
    untouched.chmod(untouched.stat().st_mode ^ 0o100)
    assert host.stamp(untouched.stat())[:4] == expected["stamp"][:4]
    assert host.stamp(untouched.stat())[4] != expected["stamp"][4]
    assert host.main(_command(package, "apply")) == 0
    assert moved.stat().st_ino == existing_inode
    assert (archive / "event/all/photo.raf.xmp").read_bytes() == b"sidecar"
    assert json.loads((private / "status.json").read_bytes())["state"] == "completed"

    _permit(package, "rollback")
    assert host.main(_command(package, "rollback")) == 0
    assert (source / "photo.raf").stat().st_ino == existing_inode
    assert untouched.read_bytes() == b"sidecar"
    assert not list((archive / "event/all").iterdir())


@pytest.mark.parametrize("replacement", [False, True])
def test_rejects_changed_content_even_with_original_size_and_mtime(package, replacement):
    private, source, archive, plan, _ = package
    original = source / "photo.raf"
    stamp = plan["moves"][0]["stamp"]
    if replacement:
        substitute = source / "substitute"
        substitute.write_bytes(b"raw")
        substitute.replace(original)
    else:
        original.write_bytes(b"bad")
    os.utime(original, ns=(original.stat().st_atime_ns, stamp[3]))
    assert original.stat().st_size == stamp[2]
    _permit(package, "apply")
    assert host.main(_command(package, "apply")) == 1
    status = json.loads((private / "status.json").read_bytes())
    assert ("inode" if replacement else "checksum") in status["error"]
    assert not (archive / "event/all/photo.raf").exists()
    assert original.exists()


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


def test_recognized_runner_refresh_preserves_manifest_and_durable_progress(package, monkeypatch):
    from app import legacy_adoption_package as app_package
    from app.legacy_adoption_paths import AdoptionError

    private, _, _, plan, binding = package
    old = {name: ("old bundled " + name).encode() for name in (*app_package.RUNNER_FILES, app_package.DISCOVERY_FILE)}
    for name, content in old.items():
        (private / name).write_bytes(content)
    monkeypatch.setattr(app_package, "_RC17_RUNNER_DIGESTS", {name: _sha(data) for name, data in old.items()})
    with host.directory(str(private), host.inode(private.stat())) as descriptor, host.package_lock(descriptor):
        with host.Journal(descriptor, binding) as journal:
            journal.append("media:photo.raf", "forward_done")
        log = (private / "journal.jsonl").read_bytes()
        sealed = (private / "manifest.json").read_bytes()
        script = {"manifest_sha256": binding, "host_json": json.dumps(plan["host"])}
        discovery = private / app_package.DISCOVERY_FILE
        discovery.write_bytes(b"unrecognized")
        with pytest.raises(AdoptionError, match="Skriptdateien"):
            app_package.permit(descriptor, script, "apply")
        assert (private / app_package.RUNNER_FILES[0]).read_bytes() == old[app_package.RUNNER_FILES[0]]
        discovery.write_bytes(old[app_package.DISCOVERY_FILE])
        assert " apply " in app_package.permit(descriptor, script, "apply")
        assert not app_package._runner_differences(descriptor)
        assert (private / "manifest.json").read_bytes() == sealed
        assert (private / "journal.jsonl").read_bytes() == log


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


def test_discovery_bootstrap_uses_bound_package_and_executes_only_verified_bytes(tmp_path, monkeypatch):
    import subprocess
    from app import legacy_adoption_discover as discovery

    root = tmp_path.resolve()
    package = root / "AppData's nested bind" / "legacy-adoption" / "one-job"
    package.mkdir(parents=True)
    info = package.stat()
    device = f"{os.major(info.st_dev)}:{os.minor(info.st_dev)}"
    bootstrap = root / "findmnt"
    mounts = [
        {"target": str(root), "fsroot": "/shadow", "maj:min": "0:0"},
        {"target": str(root), "fsroot": "/", "maj:min": device},
        {"target": str(package.parent.parent), "fsroot": "/bindings/app data", "maj:min": device},
    ]
    (root / "mounts.json").write_text(json.dumps({"filesystems": mounts}))
    bootstrap.write_text('#!/bin/sh\n/bin/cat "$MOUNTS_FIXTURE"\n')
    bootstrap.chmod(0o700)
    monkeypatch.setenv("MOUNTS_FIXTURE", str(root / "mounts.json"))
    monkeypatch.setenv("PATH", str(root))
    helper = package / "legacy_adoption_discover.py"
    code = (b'def check(path, identity, digest):\n    print(path, digest)\n    return 0\n'
            b'def execute(path, identity, mode, digest, source, archive):\n    print(mode, path, digest)\n    return 0\n')
    helper.write_bytes(code)
    arguments = [sys.executable, "-I", "-B", "-c", discovery.bootstrap(), "/bindings/app data/legacy-adoption/one-job",
                 device, str(info.st_ino), hashlib.sha256(code).hexdigest(), "approved-probe-digest"]
    accepted = subprocess.run(arguments, text=True, capture_output=True, check=True)
    assert accepted.stdout == f"{package} approved-probe-digest\n"
    direct = [sys.executable, "-I", "-B", "-c", discovery.bootstrap(automatic=False), str(package),
              device, str(info.st_ino), _sha(code), "apply", "approved-manifest-digest", "/source", "/archive"]
    accepted = subprocess.run(direct, text=True, capture_output=True, check=True)
    assert accepted.stdout == f"apply {package} approved-manifest-digest\n"

    helper.write_bytes(code + b'raise AssertionError("tampered helper was executed")\n')
    for command in (arguments, direct):
        rejected = subprocess.run(command, text=True, capture_output=True)
        assert rejected.returncode == 1 and "Approved AppData package not found" in rejected.stderr
        assert "tampered helper was executed" not in rejected.stderr


def test_review_cancel_returns_a_file_replaced_during_detachment(tmp_path, monkeypatch):
    from app import legacy_adoption_review_cancel as cancel
    from app.legacy_adoption_paths import AdoptionError, bound_directory, directory_identity

    general = tmp_path / "General"
    holding = general / "staging"
    holding.mkdir(parents=True)
    target = general / "photo.jpg"
    target.write_bytes(b"the working copy")
    identity = directory_identity(target.stat())
    original_rename = _macos_rename if sys.platform == "darwin" else host.rename_noreplace

    def replace_at_rename(source, name, destination, new_name):
        if new_name == ".cancel-proof":
            target.rename(general / "externally moved")
            target.write_bytes(b"another user's file")
        return original_rename(source, name, destination, new_name)

    monkeypatch.setattr(host, "rename_noreplace", replace_at_rename)
    with bound_directory(general.resolve()) as root, bound_directory(holding.resolve()) as quarantine:
        with pytest.raises(AdoptionError, match="Arbeitskopie"):
            cancel.remove_owned(root, target.name, quarantine, ".cancel-proof", identity)
    assert target.read_bytes() == b"another user's file"
    assert (general / "externally moved").read_bytes() == b"the working copy"
    assert not list(holding.iterdir())


def _rc2_edit_fixture(package):
    """Create a format-2 host manifest with a real Camera Raw reference."""
    private, source, archive, plan, _binding = package
    old_xmp = (
        b'<x:xmpmeta xmlns:x="adobe:ns:meta/">'
        b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
        b'<rdf:Description xmlns:crs="http://ns.adobe.com/camera-raw-settings/1.0/"'
        b' crs:RawFileName="photo.raf" crs:Exposure2012="+0.45"/></rdf:RDF></x:xmpmeta>'
    )
    new_xmp = old_xmp.replace(b'crs:RawFileName="photo.raf"',
                              b'crs:RawFileName="20260721_120000_Fuji.raf"')
    sidecar = source / "photo.raf.xmp"
    sidecar.write_bytes(old_xmp)
    plan["format"] = 2
    for row in plan["moves"]:
        if row["source"] == "photo.raf":
            row["target"] = "event/all/20260721_120000_Fuji.raf"
        elif row["source"] == "photo.raf.xmp":
            row["target"] = "event/all/20260721_120000_Fuji.xmp"
        row.update(_proof(source / row["source"]))
    plan["xmp_edits"] = [{
        "source": "photo.raf.xmp", "target": "event/all/20260721_120000_Fuji.xmp",
        "original_sha256": _sha(old_xmp), "sha256": _sha(new_xmp),
        "size_bytes": len(new_xmp),
        "content": base64.b64encode(new_xmp).decode("ascii"),
    }]
    encoded = host.json_bytes(plan)
    binding = _sha(encoded)
    (private / "manifest.json").write_bytes(encoded)
    return (private, source, archive, plan, binding), old_xmp, new_xmp


def test_rc2_xmp_edit_apply_and_rollback_are_byte_exact(package):
    edited, original, updated = _rc2_edit_fixture(package)
    private, source, archive, plan, _ = edited
    _permit(edited, "apply")
    assert host.main(_command(edited, "apply")) == 0
    assert (archive / "event/all/20260721_120000_Fuji.raf").read_bytes() == b"raw"
    assert (archive / "event/all/20260721_120000_Fuji.xmp").read_bytes() == updated
    backup = archive / ("." + "bibliothekar-adoption-" + plan["plan_id"])
    assert (backup / "original-xmp-0.xmp").read_bytes() == original
    assert not (source / "photo.raf.xmp").exists()
    _permit(edited, "rollback")
    assert host.main(_command(edited, "rollback")) == 0
    assert (source / "photo.raf.xmp").read_bytes() == original
    assert (source / "photo.raf").read_bytes() == b"raw"
    assert not (archive / "event/all/20260721_120000_Fuji.xmp").exists()


@pytest.mark.parametrize("interrupt_name", [
    "new-xmp-0.xmp",
    "20260721_120000_Fuji.xmp",
])
def test_rc2_xmp_edit_resumes_after_crash_between_intent_and_rename(package, monkeypatch,
                                                                  interrupt_name):
    edited, original, updated = _rc2_edit_fixture(package)
    _, source, archive, _plan, _ = edited
    _permit(edited, "apply")
    actual = host.rename_noreplace
    fired = False

    def interrupted(src, name, dst, new_name):
        nonlocal fired
        actual(src, name, dst, new_name)
        if name == interrupt_name and not fired:
            fired = True
            raise KeyboardInterrupt

    with monkeypatch.context() as before_crash:
        before_crash.setattr(host, "rename_noreplace", interrupted)
        with pytest.raises(KeyboardInterrupt):
            host.main(_command(edited, "apply"))
    assert fired
    assert host.main(_command(edited, "apply")) == 0
    assert (archive / "event/all/20260721_120000_Fuji.xmp").read_bytes() == updated
    _permit(edited, "rollback")
    assert host.main(_command(edited, "rollback")) == 0
    assert (source / "photo.raf.xmp").read_bytes() == original


def test_rc2_host_rejects_modified_xmp_payload_before_moving_files(package):
    edited, original, updated = _rc2_edit_fixture(package)
    _private, source, _archive, plan, _binding = edited
    plan["xmp_edits"][0]["content"] = base64.b64encode(updated + b"x").decode("ascii")
    with pytest.raises(host.ExecutionError, match="checksum"):
        host.validate_plan(plan)
    assert (source / "photo.raf.xmp").read_bytes() == original
