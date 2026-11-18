"""Archive batches reuse the real catalogue, verification and release journals."""
import os
from pathlib import Path
import sys

import pytest

from app import archive_batches, background_activity, operation_health
from app.archive_transfer import verify_event_archive
from app.database import create_planned_event, database_connection, initialize_database
from app.workspace_layout import ensure_workspace_layout
from tests.backend.test_0412_consistency_semantics import NOW, _event_preview, _seed_free_file
from tests.backend.test_legacy_adoption_integration import _json, _onboard, fresh_main


def _add_event(db, work, archive, index, *, corrupt=False, status="applied", resort=0):
    name = f"Photo-{index}.JPG"
    day = f"2026-10-{index:02}"
    content = f"Camera bytes {index}".encode()
    family_id, file_id, _ = _seed_free_file(db, family_key=name, filename=name, day=day, data=content)
    event = create_planned_event(db, "J", _event_preview(family_id, day))["parent_event"]
    relative = Path("2026", event["folder_name"], name)
    for storage, data in ((work, content), (archive, b"x" * len(content) if corrupt else content)):
        path = storage / relative
        path.parent.mkdir(parents=True)
        path.write_bytes(data)
    with database_connection(db) as connection:
        connection.execute("UPDATE events SET status=?,applied_at=?,updated_at=?,resort_required=? WHERE id=?",
                           (status, NOW, NOW, resort, event["id"]))
        connection.execute("UPDATE files SET current_relative_path=? WHERE id=?", (relative.as_posix(), file_id))
    return event["id"], work / relative, archive / relative, content


@pytest.fixture
def catalogue(tmp_path):
    root = tmp_path.resolve()
    db = root / "catalogue.sqlite3"
    archive = Path(os.environ["ADOPTION_ZFS_ROOT"]) / root.name / "archive" if os.environ.get("ADOPTION_ZFS_ROOT") else root / "archive"
    workspace = Path(os.environ["ADOPTION_ZFS_OTHER"]) / root.name / "workspace" if os.environ.get("ADOPTION_ZFS_OTHER") else root / "workspace"
    for directory in (archive, workspace):
        directory.mkdir(parents=True)
    initialize_database(db)
    work = Path(ensure_workspace_layout(workspace)["work_root"])

    def add(index, **options):
        return _add_event(db, work, archive, index, **options)

    return db, workspace, archive, add


def _drain(db, workspace, archive):
    while archive_batches.process_next(db, lambda: workspace, archive):
        pass


def test_archive_batch_api_uses_the_registered_background_worker(fresh_main, monkeypatch):
    from app import main
    from app.library_context import resolve_library_context

    _, db, registry, archive = fresh_main
    http = _onboard(fresh_main)
    _json(http, "POST", "/api/setup/adoption", json={"decision": "skipped"})
    if main.ADOPTION_STARTUP_THREAD:
        main.ADOPTION_STARTUP_THREAD.join(timeout=15)
    monkeypatch.setattr(main, "start_release_worker", lambda: None)
    context = resolve_library_context(registry, "main")
    first = _add_event(db, context.work_root, archive, 1)
    second = _add_event(db, context.work_root, archive, 2, corrupt=True)
    endpoint = "/api/archive/batch"
    assert _json(http, "GET", endpoint)["candidate_count"] == 2
    _json(http, "POST", endpoint + "/release", json={}, status=422)
    proof = _json(http, "POST", endpoint + "/verify", json={}, status=202)
    assert _json(http, "POST", endpoint + "/verify", json={}, status=202)["id"] == proof["id"]
    assert main.process_background_release()
    assert _json(http, "GET", endpoint)["batch"]["processed"] == 1
    assert main.process_background_release() and not main.process_background_release()
    state = _json(http, "GET", endpoint)
    assert state["batch"]["status"] == "failed" and state["release_ready_count"] == 1
    _json(http, "POST", endpoint + "/release", json={"verification_batch_id": "unrelated"}, status=409)
    release = _json(http, "POST", endpoint + "/release", json={"verification_batch_id": proof["id"]}, status=202)
    assert [item["event_id"] for item in release["items"]] == [first[0]]
    activities = _json(http, "GET", "/api/background-activity")["operations"]
    assert [item["kind"] for item in activities if item["active"]] == ["archive_batch"]
    assert first[1].read_bytes() == first[3] and second[1].read_bytes() == second[3]


def test_archive_verify_batch_filters_candidates_and_retains_individual_outcomes(catalogue):
    db, workspace, archive, add = catalogue
    good = add(1)
    bad = add(2, corrupt=True)
    planned = add(3, status="planned")
    archived = add(4, status="archived")
    resort = add(5, resort=1)
    queued = archive_batches.enqueue(db, "verify")
    assert set(item["event_id"] for item in queued["items"]) == {good[0],bad[0]}
    assert archive_batches.enqueue(db, "verify")["id"] == queued["id"]
    with pytest.raises(ValueError, match="läuft bereits"):
        archive_batches.enqueue(db, "release", queued["id"])
    assert [entry["kind"] for entry in background_activity.current_activity(db,db)["operations"]] == ["archive_batch"]
    assert archive_batches.process_next(db, lambda: workspace, archive)
    partial = archive_batches.dashboard(db)["batch"]
    assert partial["processed"] == partial["progress_percent"] // 50 == 1
    _drain(db, workspace, archive)
    observed = archive_batches.dashboard(db)
    batch = observed["batch"]
    assert batch["status"] == "failed" and batch["successful"] == observed["release_ready_count"] == 1
    results = {item["event_id"]: item for item in batch["items"]}
    assert results[good[0]]["status"] == "verified" and results[good[0]]["verified_file_count"] == 1
    assert results[bad[0]]["status"] == "failed"
    assert results[bad[0]]["missing_file_count"] + results[bad[0]]["mismatched_file_count"] == 1
    release = archive_batches.enqueue(db, "release", batch["id"])
    assert [item["event_id"] for item in release["items"]] == [good[0]]
    assert all(item[1].read_bytes() == item[3] for item in (good,bad,planned,archived,resort))
    with database_connection(db) as connection:
        assert not connection.execute("SELECT 1 FROM ssd_release_tasks").fetchone()
        assert not connection.execute("SELECT 1 FROM event_ssd_releases").fetchone()


def test_archive_verification_restart_reuses_its_persisted_proof(catalogue, monkeypatch):
    db, workspace, archive, add = catalogue
    event, *_ = add(1)
    batch = archive_batches.enqueue(db, "verify")
    verify = archive_batches.verify_archive_for_release

    # Throw outside the domain exception handler, after the authoritative proof.
    class WorkerLost(BaseException):
        pass

    def lose_worker(*args, **kwargs):
        assert verify(*args, **kwargs)["verified"]
        raise WorkerLost

    monkeypatch.setattr(archive_batches,"verify_archive_for_release",lose_worker)
    with pytest.raises(WorkerLost):
        _drain(db,workspace,archive)
    pending = archive_batches.dashboard(db)["batch"]
    assert pending["status"] == "running"
    proof = pending["items"][0]["verification_id"]
    archive_batches.recover_batches(db)
    monkeypatch.setattr(archive_batches,"verify_archive_for_release",verify)
    _drain(db,workspace,archive)
    assert archive_batches.dashboard(db)["verification_batch_id"] == batch["id"]
    with database_connection(db) as connection:
        rows = connection.execute("SELECT id FROM event_archive_verifications WHERE event_id=?", (event,)).fetchall()
    assert [row[0] for row in rows] == [proof]


@pytest.mark.skipif(sys.platform!="linux", reason="normal release requires the real Linux inotify guard")
def test_archive_release_batch_rechecks_stale_and_damaged_events_on_zfs(catalogue):
    db, workspace, archive, add = catalogue
    ready = add(1)
    damaged = add(2)
    stale = add(3)
    verify = archive_batches.enqueue(db,"verify")
    _drain(db,workspace,archive)
    release = archive_batches.enqueue(db,"release",verify["id"])
    # External file corruption preserves size. The very next stage must
    # recalculate SHA. A separately invalidated catalogue proof must fail too.
    damaged[2].write_bytes(b"x" * len(damaged[3]))
    verify_event_archive(db,archive,"J",stale[0],workspace_path=workspace)
    _drain(db,workspace,archive)
    final = archive_batches.dashboard(db)["batch"]
    assert final["id"] == release["id"] and final["status"] == "failed" and final["successful"] == 1, final
    assert {item["event_id"]:item["status"] for item in final["items"]} == {
        ready[0]:"released",damaged[0]:"failed",stale[0]:"failed",
    }
    assert not ready[1].exists() and ready[2].read_bytes() == ready[3]
    assert damaged[1].read_bytes() == damaged[3] and stale[1].read_bytes() == stale[3]
    assert archive_batches.enqueue(db,"release",verify["id"])["id"] == release["id"]
    with database_connection(db) as connection:
        rows=connection.execute("SELECT event_id,status FROM event_ssd_releases").fetchall()
        assert [tuple(row) for row in rows] == [(ready[0],"completed")]
        assert not connection.execute("SELECT 1 FROM ssd_release_tasks").fetchone()
    assert len([task for task in background_activity.current_activity(db,db)["operations"]
                if task["id"]==release["id"]]) == 1


@pytest.mark.skipif(sys.platform!="linux", reason="normal release requires the real Linux inotify guard")
def test_archive_release_resumes_only_its_original_operation_on_zfs(catalogue, monkeypatch):
    db,workspace,archive,add=catalogue
    album=add(1)
    waiting=add(2)
    verify=archive_batches.enqueue(db,"verify")
    _drain(db,workspace,archive)
    release=archive_batches.enqueue(db,"release",verify["id"])
    first = release["items"][0]
    target = album if first["event_id"] == album[0] else waiting
    pending = waiting if target is album else album
    unlink=Path.unlink

    class WorkerLost(BaseException):
        pass

    def interrupt_after_delete(path,*args,**kwargs):
        unlink(path,*args,**kwargs)
        if path==target[1]:
            raise WorkerLost

    with monkeypatch.context() as interrupted:
        interrupted.setattr(Path,"unlink",interrupt_after_delete)
        with pytest.raises(WorkerLost):
            _drain(db,workspace,archive)
    health=operation_health.inspect(workspace)
    assert not health["writes_allowed"] and len(health["reservations"])==1
    stale=archive_batches.resumable_release(db,"shared","previous batch",health["reservations"])
    assert stale is None
    path,item=archive_batches.resumable_release(db,"shared",release["id"],health["reservations"])
    assert item["event_id"]==target[0] and not target[1].exists() and pending[1].exists()
    with operation_health.qualified_retry(workspace,{path}):
        archive_batches.resume_release(db,workspace,archive,item)
        operation_health.finish_qualified_retry(workspace)
    safe=archive_batches.dashboard(db)["batch"]
    assert safe["status"]=="interrupted" and safe["successful"]==1
    assert not archive_batches.process_next(db,lambda: workspace,archive)
    assert pending[1].exists() and target[2].read_bytes()==target[3]
    next_verify=archive_batches.enqueue(db,"verify")
    assert [item["event_id"] for item in next_verify["items"]]==[pending[0]]
    _drain(db,workspace,archive)
    archive_batches.enqueue(db,"release",next_verify["id"])
    _drain(db,workspace,archive)
    assert not pending[1].exists() and pending[2].read_bytes()==pending[3]
    with database_connection(db) as connection:
        assert connection.execute("SELECT count(*) FROM event_ssd_releases WHERE status='completed'").fetchone()[0]==2
