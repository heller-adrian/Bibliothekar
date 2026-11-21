"""RC2 durable preparation checkpoints without real media or TrueNAS mutations."""
from contextlib import contextmanager
import os
from types import SimpleNamespace

import pytest

from app import legacy_adoption_preparation as preparation
from app.legacy_adoption_paths import AdoptionError


@pytest.fixture
def private_package(tmp_path, monkeypatch):
    job_id, plan_id = "a" * 32, "b" * 32
    place = tmp_path / "legacy-adoption" / job_id
    place.mkdir(parents=True)
    (place / "execution.lock").write_bytes(b"")

    @contextmanager
    def package(identifier):
        assert identifier == job_id
        fd = os.open(place, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            yield fd
        finally:
            os.close(fd)

    monkeypatch.setattr(preparation, "_package", package)
    monkeypatch.setattr(preparation, "appdata_root", lambda: tmp_path)
    return SimpleNamespace(library_id="main"), job_id, plan_id, place


def test_durable_preparation_state_and_progress_survive_reload(private_package):
    library, job, plan, place = private_package
    digest = "c" * 64
    assert preparation.preparation_status(library, job, plan) is None
    reserved = preparation.reserve_preparation(library, job, plan, digest)
    assert reserved["state"] == "queued"
    assert "probe_sha256" not in reserved
    assert preparation.preparation_status(library, job, plan)["state"] == "queued"

    preparation.record_preparation(library, job, plan, digest, "running",
                                   phase="hashing", processed=32, total=10346,
                                   bytes_processed=2048, bytes_total=560000000000)
    # A cold read must see persisted numbers rather than a process-local cache.
    again = preparation.preparation_status(library, job, plan)
    assert again["processed"] == 32
    assert again["total"] == 10346
    assert again["bytes_processed"] == 2048
    assert again["bytes_total"] == 560000000000
    assert again["state"] == "running"
    assert "probe_sha256" not in again
    assert (place / "preparation.json").is_file()
    preparation.record_preparation(library, job, plan, digest, "completed",
                                   phase="manifest_ready", processed=10346)
    assert preparation.preparation_status(library, job, plan)["state"] == "completed"
    assert preparation.reserve_preparation(library, job, plan, digest)["state"] == "completed"


def test_restart_retry_and_failure_have_durable_identity(private_package):
    library, job, plan, _place = private_package
    digest = "d" * 64
    preparation.reserve_preparation(library, job, plan, digest)
    preparation.record_preparation(library, job, plan, digest, "failed",
                                   error="synthetic interrupted read")
    assert preparation.preparation_status(library, job, plan)["error"] == "synthetic interrupted read"
    assert preparation.reserve_preparation(library, job, plan, digest)["state"] == "queued"
    assert preparation.preparation_status(library, job, plan)["error"] is None
    with pytest.raises(AdoptionError, match="Hostnachweis"):
        preparation.reserve_preparation(library, job, plan, "e" * 64)
    with pytest.raises(AdoptionError, match="anderen Übernahmeplan"):
        preparation.preparation_status(library, job, "f" * 32)
    with pytest.raises(AdoptionError, match="anderen Übernahmeplan"):
        preparation.preparation_status(SimpleNamespace(library_id="second"), job, plan)
