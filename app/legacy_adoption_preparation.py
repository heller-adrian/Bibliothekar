"""Durable, server-owned preparation progress for confirmed *script* adoption.

The progress record is an atomic, private AppData file bound to the current
library/job/plan. It remains readable while the manifest transaction holds a
catalogue write lock. It never authorizes filesystem moves by itself.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import os
import stat

from app.appdata import root as appdata_root
from app.legacy_adoption_package import PACKAGE_ROOT, _package, _read_json
from app import legacy_adoption_host as host
from app.legacy_adoption_paths import AdoptionError


_PROGRESS_FILE = "preparation.json"


@contextmanager
def exclusive_preparation_worker(job_id):
    """Only one OS process can execute a long hash-bound preparation at once.

    Keep this separate from the short package metadata lock, which progress
    checkpoint writers need to acquire while the job is hashing files.
    """
    with _package(job_id) as package:
        fd = os.open(
            "preparation-worker.lock",
            os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK,
            0o600, dir_fd=package,
        )
        try:
            host.check_child(package, "preparation-worker.lock", fd)
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise AdoptionError("Der Sperrnachweis zur Vorbereitung ist keine reguläre Datei.")
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                yield False
                return
            try:
                yield True
            finally:
                fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def _time():
    return datetime.now(timezone.utc).isoformat()


def _base(library, job_id, plan_id, probe_digest):
    return {
        "library_id": library.library_id, "job_id": job_id,
        "plan_id": plan_id, "probe_sha256": probe_digest,
        "method": "script", "state": "queued", "phase": "waiting",
        "processed": 0, "total": 0,
        "bytes_processed": 0, "bytes_total": 0,
        "error": None, "updated_at": _time(),
    }


def _assert_identity(record, library, job_id, plan_id):
    if (record["library_id"] != library.library_id
            or record["job_id"] != job_id or record["plan_id"] != plan_id
            or record.get("method") != "script"):
        raise AdoptionError("Der Fortschrittsnachweis gehört zu einem anderen Übernahmeplan.")


def _write(descriptor, record):
    host.write_atomic(descriptor, _PROGRESS_FILE, host.json_bytes({
        **record, "updated_at": _time(),
    }))


def preparation_status(library, job_id, plan_id):
    """Read an already existing private record without creating directories."""
    appdata = appdata_root()
    if appdata is None or not (appdata / PACKAGE_ROOT / job_id).is_dir():
        return None
    with _package(job_id) as descriptor:
        record = _read_json(descriptor, _PROGRESS_FILE)
    if record is not None:
        _assert_identity(record, library, job_id, plan_id)
        # Do not leak the probe digest to a caller that only polls progress.
        return {key: value for key, value in record.items() if key != "probe_sha256"}
    return None


def _active_worker(package):
    """Check for a worker in any process without trusting HTTP-local state."""
    fd = os.open(
        "preparation-worker.lock",
        os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK,
        0o600, dir_fd=package,
    )
    try:
        host.check_child(package, "preparation-worker.lock", fd)
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise AdoptionError("Ungültige Vorbereitungs-Sperrdatei.")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        fcntl.flock(fd, fcntl.LOCK_UN)
        return False
    finally:
        os.close(fd)


def reserve_preparation(library, job_id, plan_id, probe_digest):
    """Durably record an accepted attempt; lock the immutable host package."""
    with _package(job_id) as descriptor, host.package_lock(descriptor):
        record = _read_json(descriptor, _PROGRESS_FILE)
        if record is not None:
            _assert_identity(record, library, job_id, plan_id)
            if record.get("probe_sha256") != probe_digest:
                raise AdoptionError("Der Hostnachweis passt nicht zum bereits begonnenen Auftrag.")
            if record.get("state") == "completed" or _active_worker(descriptor):
                return {key: value for key, value in record.items() if key != "probe_sha256"}
        initial = _base(library, job_id, plan_id, probe_digest)
        _write(descriptor, initial)
        return {key: value for key, value in initial.items() if key != "probe_sha256"}


def record_preparation(library, job_id, plan_id, probe_digest, state, *,
                       phase=None, processed=None, total=None,
                       bytes_processed=None, bytes_total=None, error=None,
                       descriptor=None):
    """Checkpoint one state; use the already held package lock when supplied."""
    def update(package):
        record = _read_json(package, _PROGRESS_FILE)
        if record is None:
            raise AdoptionError("Der bestätigte Vorbereitungsauftrag ist verschwunden.")
        _assert_identity(record, library, job_id, plan_id)
        if record.get("probe_sha256") != probe_digest:
            raise AdoptionError("Der Hostnachweis für die Vorbereitung wurde ausgetauscht.")
        new = dict(record)
        new["state"] = state
        if phase is not None:
            new["phase"] = phase
        for name, value in (
            ("processed", processed), ("total", total),
            ("bytes_processed", bytes_processed), ("bytes_total", bytes_total),
        ):
            if value is not None:
                new[name] = int(value)
        new["error"] = error
        _write(package, new)

    if descriptor is not None:
        update(descriptor)
    else:
        with _package(job_id) as package, host.package_lock(package):
            update(package)
