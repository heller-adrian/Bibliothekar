from contextlib import contextmanager
import os
import shutil
import sys
from pathlib import Path
from zipfile import ZipFile

import pytest
from fastapi.testclient import TestClient

from app import domain_recovery, main, operation_health
from app.legacy_adoption_mode import pending_initial_setup
from app.database import database_connection
from app.event_access import event_file_rows
from app.event_inventory import scan_event_inventory
from app.legacy_adoption_catalogue import catalogue_job_id
from app.legacy_adoption_dataset import prove as kernel_dataset_proof
from app.library_context import resolve_library_context
from tests.backend.test_f14_root_operations import fixture
from tests.backend.test_pre4_operation_separation import ready
from tests.backend.test_legacy_adoption_plan import inventory, library
from tests.backend.test_legacy_adoption_inventory import synthetic_dataset


def _json(client, method, path, *, library="main", status=200, **kwargs):
    response = client.request(method, path, headers={"X-Bibliothekar-Library": library}, **kwargs)
    assert response.status_code == status, response.text
    return response.json()


@pytest.fixture
def fresh_main(tmp_path, monkeypatch, request):
    from app import legacy_adoption_api

    native = os.environ.get("ADOPTION_ZFS_ROOT")
    case = tmp_path.resolve() / "first-install"
    workspace, private = case / "workspace", case / "database"
    variant = getattr(request, "param", False)
    if variant == "review-unlinked":
        if sys.platform != "linux":
            pytest.skip("O_TMPFILE and descriptor linking require Linux")
        if acl_root := os.environ.get("ADOPTION_NFSV4_ROOT"):
            workspace = Path(acl_root).resolve(strict=True) / tmp_path.name / "workspace"
    elif variant == "cancel-zfs" and (workspace_dataset := os.environ.get("ADOPTION_ZFS_OTHER")):
        workspace = Path(workspace_dataset).resolve(strict=True) / tmp_path.name / "workspace"
    # Only the media pair belongs on synthetic ZFS. The legacy private
    # catalogue and operation records require a supported native ACL backend.
    native_media = native and variant
    media_root = Path(native) / tmp_path.name if native_media else case
    archive = media_root / "archive"
    for path in (workspace, private, archive):
        path.mkdir(parents=True)
    if native_media:
        assert archive.stat().st_dev != private.stat().st_dev
    config = case / "settings.json"
    config.write_text("{}")
    database, registry = private / "main.sqlite3", private / "registry.sqlite3"
    for key, path in {"WORKSPACE": workspace, "DATABASE_DIR": private, "REGISTRY_DATABASE": registry,
                      "CONFIG": config, "ARCHIVE_ROOT": archive, "LOG_DIR": case / "logs"}.items():
        monkeypatch.setenv("KAMERA_" + key, str(path))
    monkeypatch.delenv("BIBLIOTHEKAR_DEFAULT_DIRECTORY_LANGUAGE", raising=False)
    for key, path in {"WORKSPACE_PATH": workspace, "DATABASE_FILE": database, "DATABASE_DIRECTORY": private,
                      "REGISTRY_DATABASE_FILE": registry, "CONFIG_PATH": config, "ARCHIVE_ROOT": archive,
                      "LOG_PATH": case / "logs"}.items():
        monkeypatch.setattr(main, key, path)
    monkeypatch.setattr(main, "_mount_read_only", lambda path: True)
    monkeypatch.setattr(legacy_adoption_api, "browsable_folders", lambda *args: args[-1])
    monkeypatch.setattr(main, "MAIN_LIBRARY_CONTEXT", main.build_main_library_context())
    # Exercise real storage startup and HTTP registration without asynchronous claims.
    monkeypatch.setattr(main, "_start_runtime_workers", lambda **kwargs: None)
    return workspace, database, registry, archive


def _onboard(fresh_main):
    _, _, registry, archive = fresh_main
    main.startup_database()
    assert main.DATABASE_INITIALIZATION_ERROR is None
    client = TestClient(main.app, follow_redirects=False)
    before = client.get("/")
    assert before.status_code == 200 and "Set up your first library" in before.text
    assert client.get("/api/jobs").status_code == 409
    result = _json(client, "POST", "/api/libraries", status=201, json={
        "display_name": "Synthetic Main", "archive_root": str(archive),
    })
    assert result["library"]["library_id"] == "main"
    assert pending_initial_setup(registry) == {"library_id": "main", "decision": "choice"}
    return client


def _adopt(client):
    return _json(client, "POST", "/api/setup/adoption", json={"decision": "adopting"})


def test_adoption_source_browser_recommends_nas_and_rechecks_selected_folder(fresh_main, tmp_path, monkeypatch):
    from app import legacy_adoption_api, legacy_adoption_dataset

    client = _onboard(fresh_main)
    _adopt(client)
    nas = tmp_path.resolve() / "nas-source"
    other = nas / "different-dataset"
    other.mkdir(parents=True)
    saved = tmp_path.resolve() / "unqualified-backups"
    saved.mkdir()
    monkeypatch.setattr(main, "NAS_SOURCE_ROOT", nas)
    monkeypatch.setattr(main, "IMPORT_ROOT", saved)

    def prove(source, archive, source_fd, archive_fd):
        if source != nas:
            raise legacy_adoption_dataset.DatasetError(legacy_adoption_dataset.DATASET_REQUIRED)
        return {"dataset": "pool/photos", "device": str(os.fstat(source_fd).st_dev)}

    monkeypatch.setattr(legacy_adoption_dataset, "prove", prove)
    monkeypatch.setattr(legacy_adoption_api, "browsable_folders", lambda *args: [])
    roots = _json(client, "GET", "/api/legacy-adoption/sources")
    assert roots["preferred"] == "nas"
    assert [item["key"] for item in roots["roots"]] == ["nas"]
    browse = _json(client, "GET", "/api/legacy-adoption/source?root=nas")
    assert browse["dataset"] == "pool/photos" and browse["folders"] == []
    incompatible = _json(client, "GET", "/api/legacy-adoption/source?root=nas&relative=different-dataset")
    assert incompatible["dataset"] is None and incompatible["reason"] == legacy_adoption_dataset.DATASET_REQUIRED

    # A stale selection is never sufficient to create an inventory job.
    response = _json(client, "POST", "/api/legacy-adoption/jobs", status=409,
                     json={"root": "nas", "relative": "different-dataset"})
    assert response["detail"] == legacy_adoption_dataset.DATASET_REQUIRED


def test_first_setup_choice_blocks_regular_work_and_skip_is_permanent(fresh_main):
    from app.ui_shell import BIBLIOTHEKAR_JS

    client = _onboard(fresh_main)
    for path in ("/", "/workspace?library=second", "/transfer", "/?settings=libraries", "/legacy-adoption"):
        response = client.get(path)
        assert response.status_code == 303 and response.headers["location"] == "/setup/adoption"
    choice = client.get("/setup/adoption")
    assert choice.status_code == 200 and choice.headers["cache-control"] == "no-store"
    assert "Do you have an existing photo collection?" in choice.text
    assert "Adopt an existing collection" in choice.text and "Start with an empty library" in choice.text
    assert 'id="bk-settings-dialog"' not in choice.text and 'class="bk-shell"' not in choice.text
    for method, path in (("GET", "/api/jobs"), ("POST", "/api/jobs/folder-import"),
                         ("GET", "/api/libraries"), ("POST", "/api/libraries"),
                         ("GET", "/api/settings/event-folder-layout"),
                         ("PUT", "/api/settings/event-folder-layout"),
                         ("GET", "/api/operations/catalogue"), ("POST", "/api/legacy-adoption/jobs")):
        assert _json(client, method, path, status=409)["code"] == "initial_setup_required"
    assert client.get("/healthz").status_code == 200
    assert client.get("/api/settings/storage-health").status_code == 200
    # Run actual technical startup against the same persisted registry.
    main.startup_database()
    restarted = TestClient(main.app, follow_redirects=False)
    assert restarted.get("/workspace").headers["location"] == "/setup/adoption"
    assert _json(restarted, "POST", "/api/setup/adoption", json={"decision": "skipped"}) == {"next": "/"}
    main.ADOPTION_STARTUP_THREAD.join(timeout=10)
    assert not main.ADOPTION_STARTUP_THREAD.is_alive()
    assert restarted.get("/").status_code == 200
    assert restarted.get("/legacy-adoption").headers["location"] == "/"
    assert "data-bk-library-adopt" in BIBLIOTHEKAR_JS
    second_archive = fresh_main[3].with_name("second-archive")
    second_archive.mkdir()
    second = _json(restarted, "POST", "/api/libraries", status=201, json={
        "display_name": "Other library", "archive_root": str(second_archive),
    })["library"]
    assert second["library_id"] != "main" and pending_initial_setup(fresh_main[2]) is None
    assert _json(restarted, "POST", "/api/setup/adoption", status=409, json={"decision": "adopting"})[
        "code"
    ] == "legacy_adoption_inactive"


def test_existing_catalogue_blocks_adoption_and_is_preserved(fresh_main):
    from tests.backend.test_legacy_adoption_plan import _existing

    _, database, registry, _ = fresh_main
    client = _onboard(fresh_main)
    library = resolve_library_context(registry, "main")
    _existing(library)
    assert "verwaltete Daten" in _json(client, "POST", "/api/setup/adoption", status=409,
                                       json={"decision": "adopting"})["detail"]
    assert pending_initial_setup(registry)["decision"] == "choice"
    _json(client, "POST", "/api/setup/adoption", json={"decision": "skipped"})
    assert _json(client, "POST", "/api/legacy-adoption/jobs", status=409, json={"root": "nas"})[
        "code"
    ] == "legacy_adoption_inactive"
    with database_connection(database) as connection:
        assert tuple(connection.execute("SELECT id, name, revision FROM events").fetchone()) == (
            "EXISTING", "Urlaub", 1,
        )


def test_later_adoption_rechecks_incomplete_library_and_operations(ready):
    from app.root_operations import reserve
    from tests.backend.test_legacy_adoption_plan import _existing

    _, workspace, registry, databases, _ = ready
    library = resolve_library_context(registry, "second")
    _existing(library)
    client = TestClient(main.app, follow_redirects=False)
    api = "/api/legacy-adoption"
    wizard = "/legacy-adoption?library=second&mode=library"

    def blockers():
        return _json(client, "GET", api + "/eligibility", library="second")["blockers"]

    def blocked_start():
        assert client.get(wizard).status_code == 409
        _json(client, "POST", api + "/jobs?mode=library", library="second", status=409, json={"root": "nas"})

    assert blockers() == []
    assert client.get(wizard).status_code == 200
    for status in ("planned", "applied"):
        with database_connection(databases[1]) as connection:
            connection.execute("UPDATE events SET status = ?", (status,))
        assert any("Urlaub" in item for item in blockers())
        blocked_start()
    with database_connection(databases[1]) as connection:
        connection.execute("UPDATE events SET status = 'archived'")
        connection.execute(
            """INSERT INTO event_change_requests (
                 id, event_id, job_id, event_name, notes, parent_folder, start_date, end_date, selected_family_ids,
                 proposed_at, created_at, updated_at
               ) VALUES ('pending', 'EXISTING', 'old', 'Urlaub', '', 'Urlaub', '2026', '2026', '[]', 'now', 'now', 'now')"""
        )
    assert blockers() == ["Schließe offene Archivänderungen ab."]
    blocked_start()
    with database_connection(databases[1]) as connection:
        connection.execute("UPDATE event_change_requests SET status = 'aenderbar_abgebrochen'")
        connection.execute("UPDATE jobs SET state = 'queued'")
    assert blockers() == ["Schließe offene Import- und Hintergrundaufträge ab."]
    blocked_start()
    with database_connection(databases[1]) as connection:
        connection.execute("UPDATE jobs SET state = 'completed'")
    with reserve(workspace, library_id="second", database=databases[1], kind="synthetic-adoption-blocker"):
        assert blockers() == ["Schließe laufende Vorgänge oder offene Wiederherstellungen ab."]
        blocked_start()
    assert blockers() == []
    with database_connection(databases[1]) as connection:
        assert connection.execute("SELECT count(*) FROM legacy_adoption_jobs").fetchone()[0] == 0


def test_first_setup_uses_the_normal_authentication_and_csrf_guard(fresh_main, monkeypatch):
    _onboard(fresh_main)
    password = "synthetic-setup-authorization"
    monkeypatch.delenv("BIBLIOTHEKAR_AUTH_TEST_BYPASS")
    monkeypatch.delenv("BIBLIOTHEKAR_ADMIN_PASSWORD_FILE", raising=False)
    monkeypatch.setenv("BIBLIOTHEKAR_ADMIN_PASSWORD", password)
    client = TestClient(main.app, follow_redirects=False)
    assert client.get("/workspace").headers["location"].startswith("/login")
    assert client.post("/api/setup/adoption", json={"decision": "skipped"}).status_code == 401
    _json(client, "POST", "/auth/login", json={"password": password})
    assert _json(client, "GET", "/auth/status")["authenticated"]
    assert client.get("/workspace").headers["location"] == "/setup/adoption"
    assert client.post("/api/setup/adoption", json={"decision": "skipped"}).status_code == 403
    headers = {"X-Bibliothekar-CSRF": client.cookies["bibliothekar_csrf"]}
    forbidden = client.post("/api/setup/adoption", headers={**headers, "Origin": "https://wrong.invalid"},
                            json={"decision": "skipped"})
    assert forbidden.status_code == 403
    assert client.post("/api/setup/adoption", headers=headers, json={"decision": "skipped"}).status_code == 200
    assert client.get("/workspace").status_code == 200


@pytest.mark.parametrize("confirmed", [False, True], ids=["draft", "confirmed"])
def test_rc1_registry_upgrade_keeps_active_job_for_recovery_only(
    ready, tmp_path, monkeypatch, synthetic_dataset, confirmed,
):
    from app.legacy_adoption_catalogue import prepare_documents
    from app.legacy_adoption_execution import confirm_plan
    from app.legacy_adoption_inventory import create_job, scan_inventory
    from app.legacy_adoption_mode import reserve_adoption
    from app.legacy_adoption_plan import create_plan, plan_moves
    from app.library_registry import initialize_library_registry
    from tests.backend.test_legacy_adoption_plan import _draft

    _, _, registry, _, _ = ready
    library = resolve_library_context(registry, "second")
    source = tmp_path.resolve() / "rc1-source"
    source.mkdir()
    original = source / "unmodified.raf"
    original.write_bytes(b"existing original")
    job_id = create_job(library, source)
    if confirmed:
        monkeypatch.setattr("app.legacy_adoption_inventory.read_bound_metadata",
                            lambda descriptors, _: {fd: {"EXIF:ExifIFD:DateTimeOriginal": "2026:07:21 12:00:00"}
                                                     for fd in descriptors})
        scan_inventory(library, job_id)
        plan = create_plan(library, registry, job_id, _draft())
        prepare_documents(library, job_id)
        confirm_plan(library, job_id, plan["id"], "manual", acknowledged=True)
        # RC1 jobs have no record of which directories were created.
        with database_connection(library.database_path) as connection:
            connection.execute("DELETE FROM legacy_adoption_manual_directories WHERE plan_id=?", (plan["id"],))
        target = Path(plan_moves(library, job_id)[0]["target"])
        target.parent.mkdir(parents=True)
        original.rename(target)
    reserve_adoption(registry, library.library_id, job_id)
    with database_connection(registry) as connection:
        connection.execute("DROP TABLE initial_library_setup")
        connection.execute("ALTER TABLE legacy_adoption_active DROP COLUMN access_kind")
        connection.execute("DELETE FROM registry_schema_versions WHERE version >= 7")
    initialize_library_registry(registry)
    assert pending_initial_setup(registry) is None
    client = TestClient(main.app, follow_redirects=False)
    response = client.get("/workspace")
    assert response.status_code == 303
    assert 'data-recovery-only="true"' in client.get(response.headers["location"]).text
    job = "/api/legacy-adoption/jobs/" + job_id
    assert _json(client, "GET", job)["id"] == job_id
    assert _json(client, "POST", job + "/scan", status=409)["code"] == "legacy_adoption_recovery_only"
    assert _json(client, "PUT", job + "/draft", status=409, json={"revision": 0})[
        "code"
    ] == "legacy_adoption_recovery_only"
    if confirmed:
        command = {"plan_id": plan["id"]}
        assert target.read_bytes() == b"existing original" and not original.exists()
        _json(client, "DELETE", job, status=409)
        _json(client, "POST", job + "/finalize", status=409, json=command)
        assert _json(client, "POST", job + "/rollback/start", json=command)["execution"]["phase"] == "rolling_back"
        _json(client, "POST", job + "/rollback/check", status=409, json=command)
        target.rename(original)
        assert _json(client, "POST", job + "/rollback/check", json=command)["execution"]["phase"] == "rolled_back"
    else:
        _json(client, "DELETE", job)
    assert client.get("/workspace").status_code == 200
    assert _json(client, "POST", "/api/legacy-adoption/jobs", status=409, json={"root": "nas"})[
        "code"
    ] == "legacy_adoption_inactive"
    assert original.read_bytes() == b"existing original"


def test_deferred_adoption_startup_waits_for_finalization_lease(fresh_main, monkeypatch):
    from threading import Event
    from app.legacy_adoption_mode import adoption_execution_access

    _, _, registry, _ = fresh_main
    waiting, started = Event(), Event()

    class Stop(Event):
        def wait(self, timeout=None):
            waiting.set()
            return super().wait(timeout)

    stop = Stop()
    monkeypatch.setattr(main, "WORKER_STOP", stop)
    monkeypatch.setattr(main, "ADOPTION_STARTUP_THREAD", None)
    try:
        with adoption_execution_access(registry):
            main._defer_startup_for_adoption(started.set)
            assert waiting.wait(5)
            assert not started.is_set()
        assert started.wait(5)
    finally:
        stop.set()
        main.ADOPTION_STARTUP_THREAD.join(5)


@pytest.mark.parametrize("fresh_main", [True], indirect=True, ids=["lifecycle"])
def test_wizard_and_f14_recovery_in_main_library(fresh_main, monkeypatch, synthetic_dataset):
    from io import BytesIO
    from app import legacy_adoption_registration as registration
    from app.legacy_adoption_paths import AdoptionError

    workspace, database, registry, archive = fresh_main
    source = archive.parent / "legacy-source"
    if os.environ.get("ADOPTION_ZFS_ROOT"):
        monkeypatch.setattr("app.legacy_adoption_dataset.prove", kernel_dataset_proof)
    day = source / "2026" / "07" / "2026-07-21"
    day.mkdir(parents=True)
    media = day / "adopted.raf"
    media.write_bytes(b"synthetic RAW bytes")
    monkeypatch.setattr(main, "NAS_SOURCE_ROOT", source)
    monkeypatch.setattr(main, "DATABASE_INITIALIZATION_ERROR", None)
    monkeypatch.setattr(
        "app.legacy_adoption_inventory.read_bound_metadata",
        lambda descriptors, _cancel: {
            fd: {"EXIF:ExifIFD:DateTimeOriginal":
                 "2026:07:25 12:00:00" if os.pread(fd, 7, 0) == b"outside" else "2026:07:21 12:00:00"}
            for fd in descriptors
        },
    )
    client = _onboard(fresh_main)
    assert _adopt(client) == {"next": "/legacy-adoption"}
    library = resolve_library_context(registry, "main")
    wizard = client.get("/legacy-adoption?library=second")
    assert wizard.status_code == 200
    assert 'data-library="main"' in wizard.text
    api = "/api/legacy-adoption"
    assert _json(client, "GET", api + "/source")["folders"] == ["2026"]
    job_id = _json(client, "POST", api + "/jobs", status=201, json={"root":"nas"})["id"]
    job = api + "/jobs/" + job_id
    _json(client, "POST", job + "/scan", status=202)
    assert _json(client, "GET", job)["state"] == "inventoried"
    assert _json(client, "GET", job + "/chronology?year=2026") == [
        {"period": "2026-07-21", "families": 1, "review": 0},
    ]
    assert _json(client, "GET", job, library="main")["id"] == job_id
    assert _json(client, "GET", api + "/jobs/other", status=409)["code"] == "legacy_adoption_active"
    assert _json(client, "POST", api + "/jobs", library="main", status=409, json={"root": "nas"})[
        "code"
    ] == "legacy_adoption_active"
    other = TestClient(main.app, follow_redirects=False)
    for old_url in ("/", "/workspace?library=main", "/legacy-adoption?library=main"):
        redirect = other.get(old_url)
        assert redirect.status_code == 303
        assert redirect.headers["location"] == f"/legacy-adoption?library=main&job={job_id}"
    wizard = other.get(redirect.headers["location"], headers={"X-Bibliothekar-Library": "main"})
    assert wizard.status_code == 200 and 'data-library="main"' in wizard.text
    assert _json(other, "GET", "/api/jobs", status=409)["code"] == "legacy_adoption_active"
    assert _json(other, "POST", "/api/jobs", status=409)["code"] == "legacy_adoption_active"
    assert other.get("/healthz").status_code == 200
    draft = {"events": [{"name":"Synthetisch", "start_date":"2026-07-21", "end_date":"2026-07-21",
                         "preserve_day_folders":True, "folder_layout": {"input_path": "All", "layout": {
                             "version": 2, "nodes": [{"id": "all", "name": "All"},
                                                       {"id": "sorted", "name": "Sorted"}],
                         }}}]}
    revision = _json(client, "PUT", job + "/draft", json={**draft, "revision": 0})["revision"]
    assert revision == 1
    assert _json(other, "GET", job)["draft"]["events"][0]["name"] == "Synthetisch"
    _json(other, "PUT", job + "/draft", json={"revision": revision, "events": [{"existing_id": "archive"}]}, status=409)
    _json(other, "POST", "/api/setup/adoption", json={"decision": "skipped"}, status=409)
    _json(other, "PUT", job + "/draft", json={**draft, "revision": 0}, status=409)
    _json(other, "POST", job + "/plan", json={"revision": 0}, status=409)
    plan = _json(client, "POST", job + "/plan", json={"revision": revision})
    assert plan["folder_moves"][0]["source_path"] == "2026/07/2026-07-21"
    _json(client, "POST", job + "/documents")
    command = {"plan_id": plan["id"]}
    confirm = {**command, "method": "manual", "acknowledged": True}
    _json(client, "POST", job + "/verify", json=command, status=409)
    _json(client, "GET", job + "/download/folders", status=409)
    _json(client, "POST", job + "/confirm", json={**confirm, "acknowledged": False}, status=409)
    assert _json(client, "POST", job + "/confirm", json=confirm)["execution"]["phase"] == "manual"
    _json(other, "POST", job + "/reopen", status=409)
    _json(other, "POST", job + "/documents", status=409)
    _json(other, "DELETE", job, status=409)
    for item in ("folders", "documents"):
        response = client.get(job + "/download/" + item, headers={"X-Bibliothekar-Library":"second"})
        assert response.status_code == 200, response.text
        with ZipFile(BytesIO(response.content)) as archive:
            archive.extractall(library.archive_root)
    move = _json(client, "GET", job + "/moves")[0]
    media.rename(move["target"])
    checked = _json(client, "POST", job + "/verify", json=command)
    assert checked["state"] == "verified"
    assert checked["execution"]["phase"] == "registration_pending"

    original = registration.source_registry_transaction
    @contextmanager
    def crash_after_commit(path):
        with original(path) as connection:
            yield connection
        raise AdoptionError("synthetic crash after registry commit")

    monkeypatch.setattr(registration, "source_registry_transaction", crash_after_commit)
    _json(client, "POST", job + "/finalize", json={"plan_id": plan["id"]}, status=409)
    [lease] = operation_health.inspect(workspace)["reservations"]
    assert lease["ids"]["operation_id"] == plan["id"]
    assert lease["library"] == "main"
    assert not lease["live"]
    event_id = plan["events"][0]["id"]
    with database_connection(database) as connection:
        assert event_file_rows(connection, event_id) == []
    assert client.get(f"/legacy-adoption/history?library=main&job={job_id}").status_code == 303

    monkeypatch.setattr(registration, "source_registry_transaction", original)
    assert domain_recovery.replay(workspace, registry, database=database)
    assert operation_health.inspect(workspace)["writes_allowed"]
    assert pending_initial_setup(registry) is None
    assert _json(client, "GET", job, status=409)["code"] == "legacy_adoption_inactive"
    assert client.get("/workspace").status_code == 200

    def startup_blocks_write_validation():
        # Startup can begin after request admission while the client repeats a
        # successful finalize after losing the first response.
        raise AdoptionError("operation_recovery_required: synthetic concurrent startup")

    with monkeypatch.context() as restarting:
        restarting.setattr(registration, "validate_active_roots", startup_blocks_write_validation)
        _json(client, "POST", job + "/finalize", json={"plan_id": "f" * 32}, status=409)
        assert _json(client, "POST", job + "/finalize", json=command)["state"] == "completed"
        assert operation_health.inspect(workspace)["reservations"] == []

    history_path = "/legacy-adoption/history?library=main"
    completion_path = f"{history_path}&job={job_id}"
    recovered_wizard = client.get(f"/legacy-adoption?library=main&job={job_id}")
    assert recovered_wizard.status_code == 303 and recovered_wizard.headers["location"] == completion_path
    completion = client.get(completion_path)
    assert completion.status_code == 200
    assert "Bestandsübernahme abgeschlossen" in completion.text
    assert "Prüfnachweis anzeigen" in completion.text
    assert f"/events?library=main&amp;job={catalogue_job_id(plan)}&amp;event={event_id}" in completion.text
    assert f"{history_path}&amp;job={job_id}" in client.get(history_path).text
    assert client.get(f"{history_path}&job={'f' * 32}").status_code == 404
    from dataclasses import replace
    from app.legacy_adoption_history import completed_adoptions
    assert completed_adoptions(replace(library, library_id="another"), registry) == ([], False)

    inventory = scan_event_inventory(
        database, library.archive_root, catalogue_job_id(plan), event_id,
        root_kind="camera_archive",
    )
    with database_connection(database) as connection:
        [media_row] = event_file_rows(connection, event_id)
        assert media_row["current_root_kind"] == "camera_archive"
        assert media_row["sha256_original"] == move["sha256"]
    assert inventory["files"][0]["relative_path"] == move["target_path"]
    assert Path(move["target"]).read_bytes() == b"synthetic RAW bytes"


    # A second collection extends the same event after the initial setup has completed.
    from app.event_inventory import event_root_relative
    original_document = library.archive_root / event_root_relative(plan["events"][0]) / "event.json"
    previous_document = original_document.read_bytes()
    added = source / "same-photo.jpg"
    added.write_bytes(b"new JPEG despite a name shared with the repeated RAW")
    standalone_duplicate = source / "copied-under-another-name.raf"
    standalone_duplicate.write_bytes(b"synthetic RAW bytes")
    (source / "same-photo.raf").write_bytes(b"synthetic RAW bytes")
    detached = source / "same-photo.raf.xmp"
    detached.write_bytes(b"new sidecar for the known RAW")
    (source / "outside.raf").write_bytes(b"outside the saved period")
    assert _json(client, "GET", api + "/eligibility") == {"eligible": True, "blockers": []}
    assert client.get("/legacy-adoption?mode=library").status_code == 200
    second_id = _json(client, "POST", api + "/jobs?mode=library", status=201, json={"root": "nas"})["id"]
    second_job = api + "/jobs/" + second_id
    assert pending_initial_setup(registry) is None
    assert client.get("/workspace").headers["location"].endswith("job=" + second_id)
    _json(client, "POST", second_job + "/scan", status=202)
    status = _json(client, "GET", second_job)
    assert (status["duplicate_files"], status["detached_files"]) == (2, 1)
    assert _json(client, "GET", second_job + "/inventory-exclusions") == [
        {"relative_path": "copied-under-another-name.raf", "disposition": "duplicate"},
        {"relative_path": "same-photo.raf", "disposition": "duplicate"},
        {"relative_path": "same-photo.raf.xmp", "disposition": "detached"},
    ]
    [family] = _json(client, "GET", second_job + "/families?day=2026-07-21")
    assert family["family_key"] == "same-photo" and len(family["files"]) == 1
    matches = _json(client, "GET", second_job + "/events?day=2026-07-21")
    assert [item["id"] for item in matches] == [event_id]
    assert _json(client, "GET", second_job + "/events?day=2026-07-22") == []
    availability = _json(client, "POST", second_job + "/draft/check", json={"events": []})
    assert [item["day_key"] for item in availability["free_segments"]] == ["2026-07-25"]
    assert [(item["event_name"], item["families"]) for item in availability["archive_segments"]] == [("Synthetisch", 1)]
    extension = {"events": [{"existing_id": event_id}]}
    assert _json(client, "POST", second_job + "/draft/check", json=extension)["events"][0]["families"] == 1
    saved = _json(client, "PUT", second_job + "/draft", json={**extension, "revision": 0})
    second_plan = _json(client, "POST", second_job + "/plan", json={"revision": saved["revision"]})
    assert second_plan["events"][0]["id"] == event_id
    assert second_plan["inventory_duplicates"] == 2 and second_plan["counts"] == {"pending": 1}
    _json(client, "POST", second_job + "/reopen")
    revision = _json(client, "GET", second_job)["draft_revision"]
    second_plan = _json(client, "POST", second_job + "/plan", json={"revision": revision})
    assert second_plan["counts"] == {"pending": 1}
    assert second_plan["move_files"] == second_plan["move_families"] == 1
    assert any(item["family_key"] == "outside" and "unassigned_event" in item["reasons"]
               for item in _json(client, "GET", second_job + "/review"))
    assert original_document.read_bytes() == previous_document
    _json(client, "POST", second_job + "/documents")
    second_command = {"plan_id": second_plan["id"]}
    _json(client, "POST", second_job + "/confirm",
          json={**second_command, "method": "manual", "acknowledged": True})
    for item in ("folders", "documents"):
        response = client.get(second_job + "/download/" + item)
        assert response.status_code == 200
        with ZipFile(BytesIO(response.content)) as archive:
            archive.extractall(library.archive_root)
    [extra_move] = [item for item in _json(client, "GET", second_job + "/moves") if item["target"]]
    added.rename(extra_move["target"])
    assert _json(client, "POST", second_job + "/verify", json=second_command)["state"] == "verified"
    assert _json(client, "POST", second_job + "/finalize", json=second_command)["state"] == "completed"
    assert _json(client, "POST", second_job + "/finalize", json=second_command)["state"] == "completed"
    assert pending_initial_setup(registry) is None and client.get("/").status_code == 200
    extension_receipt = client.get(f"{history_path}&job={second_id}")
    assert extension_receipt.status_code == 200
    assert f"/events?library=main&amp;job={catalogue_job_id(plan)}&amp;event={event_id}" in extension_receipt.text
    assert f"{history_path}&amp;job={second_id}" in client.get(history_path).text
    assert Path(move["target"]).read_bytes() == b"synthetic RAW bytes"
    assert (source / "same-photo.raf").read_bytes() == b"synthetic RAW bytes"
    assert standalone_duplicate.read_bytes() == b"synthetic RAW bytes"
    assert detached.read_bytes() == b"new sidecar for the known RAW"
    assert (source / "outside.raf").read_bytes() == b"outside the saved period"
    assert original_document.read_bytes() != previous_document
    with database_connection(database) as connection:
        extended_rows = event_file_rows(connection, event_id)
        assert {row["id"] for row in extended_rows} >= {media_row["id"]}
        assert len(extended_rows) == 2
        assert len({row["sha256_original"] for row in extended_rows}) == 2
        period = connection.execute("SELECT start_datetime, end_datetime FROM events WHERE id = ?", (event_id,)).fetchone()
        assert tuple(period) == ("2026-07-21T00:00:00", "2026-07-21T23:59:59")

    # A later scan also excludes the content added by the second adoption.
    (source / "extension-copy.jpg").write_bytes(Path(extra_move["target"]).read_bytes())
    third_id = _json(client, "POST", api + "/jobs?mode=library", status=201, json={"root": "nas"})["id"]
    third_job = api + "/jobs/" + third_id
    _json(client, "POST", third_job + "/scan", status=202)
    assert _json(client, "GET", third_job)["duplicate_files"] == 3
    assert _json(client, "GET", third_job + "/families?day=2026-07-21") == []
    _json(client, "DELETE", third_job)
    assert Path(extra_move["target"]).read_bytes() == (source / "extension-copy.jpg").read_bytes()

    # Open, edit and delete through the same tools used by standard events.
    from app.archive_change_assistant import build_archive_change_assistant
    from app.archive_release_stock import verify_archive_release_copies, verify_archive_release_removal
    from app.event_change_apply import confirm_event_change, verify_event_change
    from app.event_change_request import get_event_change_files, propose_archived_event_deletion, propose_event_change
    from app.workspace_layout import backup_root

    anchor_job = catalogue_job_id(plan)
    event = plan["events"][0]
    old_folder = library.archive_root / event_root_relative(event)
    renamed = "07-21 - Umbenannt"
    preview = {
        "event_kind": "event", "event_name": "Umbenannt", "parent_folder": renamed, "child_folder": "",
        "uses_time_range": False, "preserve_day_folders": True, "start_date": "2026-07-21",
        "end_date": "2026-07-21", "start_time": "00:00", "end_time": "23:59",
        "selected_day_keys": ["2026-07-21"], "selected_family_ids": [row["family_id"] for row in extended_rows],
        "_folder_layout_explicit": True, "folder_layout": event["folder_layout"],
    }
    request = propose_event_change(database, anchor_job, event_id, preview, event_name="Umbenannt",
                                   archive_root=library.archive_root, workspace_path=workspace)
    change_id = request["change_request_id"]
    confirm_event_change(database, change_id, library.archive_root, workspace)
    assistant = build_archive_change_assistant(database, library.archive_root, workspace, change_id, scan_live=True)
    assert [item["kind"] for item in assistant["operations"]] == ["rename_archive_folder", "replace_event_document"]
    assert not verify_event_change(database, change_id, library.archive_root, workspace)["complete"]
    new_folder = old_folder.with_name(renamed)
    old_folder.rename(new_folder)
    replacement = assistant["operations"][1]
    source_relative = replacement["source"].split("/", 1)[1]
    from app.workspace_layout import shared_work_root
    shutil.copyfile(shared_work_root(workspace) / source_relative, new_folder / "event.json")
    assert not list(new_folder.rglob("Export"))
    sorted_folder = next(new_folder.rglob("Sorted"))
    sorted_folder.rmdir()
    rejected = _json(client, "POST", f"/api/change-requests/{change_id}/archive", status=400)
    incomplete = rejected["verification"]
    assert not incomplete["complete"]
    assert [item["path"] for item in incomplete["directories"] if item["status"] == "missing"] == [
        sorted_folder.relative_to(library.archive_root).as_posix()
    ]
    sorted_folder.mkdir()
    _json(client, "POST", f"/api/change-requests/{change_id}/archive")
    with database_connection(database) as connection:
        assert connection.execute("SELECT name FROM events WHERE id = ?", (event_id,)).fetchone()[0] == "Umbenannt"

    deletion = propose_archived_event_deletion(database, anchor_job, event_id, archive_root=library.archive_root)
    deletion_id = deletion["change_request_id"]
    confirm_event_change(database, deletion_id, library.archive_root, workspace)
    release_rows = [row for row in get_event_change_files(database, deletion_id)
                    if row.get("workspace_release_path")]
    assert release_rows
    for row in release_rows:
        released = backup_root(workspace) / row["workspace_release_path"]
        released.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(library.archive_root / row["old_path"], released)
    assert verify_archive_release_copies(database, library.archive_root, workspace, deletion_id)["complete"]
    # The synthetic user removes the event folder only after the release copy is verified.
    shutil.rmtree(new_folder)
    assert verify_archive_release_removal(database, library.archive_root, workspace, deletion_id)["complete"]
    assert verify_event_change(database, deletion_id, library.archive_root, workspace)["complete"]
    _json(client, "POST", f"/api/change-requests/{deletion_id}/archive")
    with database_connection(database) as connection:
        assert connection.execute("SELECT 1 FROM events WHERE id = ?", (event_id,)).fetchone() is None
        assert connection.execute("SELECT current_root_kind FROM files WHERE id = ?",
                                  (media_row["id"],)).fetchone()[0] == "shared_workspace"
    summary_path = "/api/workspace/summary?jobs=&physical_refresh=false"
    response = client.get(summary_path)
    assert response.status_code == 200, response.text
    summary = response.json()
    assert summary["selected_job_ids"] == []
    groups = summary["released_archive_groups"]
    assert len(groups) == 1
    released_family_ids = [row["family_id"] for row in extended_rows]
    assert set(groups[0]["family_ids"]) == set(released_family_ids)
    assert summary["statistics"]["family_count"] == len(released_family_ids)
    assert summary["statistics"]["file_count"] == len(extended_rows)
    new_event = client.post(f"/api/jobs/{anchor_job}/events", json={
        "event_kind": "event", "event_name": "Wieder eingeordnet", "start_date": "2026-07-21",
        "end_date": "2026-07-21", "selected_day_keys": ["2026-07-21"],
        "selected_family_ids": released_family_ids,
        "subevents": [{"name": "Neu sortiert", "start_datetime": "2026-07-21T11:30",
                       "end_datetime": "2026-07-21T12:30", "folder_layout": {
                           "input_path": "Aufnahmen", "layout": {"version": 2, "nodes": [
                               {"id": "aufnahme", "name": "Aufnahmen"},
                               {"id": "abzug", "name": "Abzüge", "role": "export"},
                               {"id": "sort", "name": "Sortierung", "children": [
                                   {"id": "selection", "name": "Auswahl", "children": [
                                       {"id": "detail", "name": "Details"},
                                   ]},
                               ]},
                           ]},
                       }}],
    })
    assert new_event.status_code == 200, new_event.text
    summary = client.get(summary_path).json()
    assert summary["released_archive_groups"] == []
    assert [group["event_name"] for group in summary["planning_overview"]["event_groups"]] == ["Wieder eingeordnet"]
    from app.archive_transfer import verify_event_archive
    from app.sort_apply import CONFIRMATION_PHRASE, execute_sort_run, prepare_sort_run
    from app.sort_plan import build_event_sort_plan
    from app.ssd_release import finalize_manually_moved_event_if_verified

    refiled = new_event.json()["parent_event"]
    new_event_id, new_job = refiled["id"], refiled["job_id"]
    from app.database import get_event_edit_context, update_event_definition
    from app.event_structure import build_event_preview

    for boundary in ("12:15", "12:30"):
        context = get_event_edit_context(database, new_job, new_event_id)
        child = context["child_events"][0]
        edited_child = {"id": child["id"], "name": child["name"], "start_datetime": child["start_datetime"],
                        "end_datetime": f"2026-07-21T{boundary}"}
        empty_child = {"name": "Später", "start_datetime": "2026-07-21T16:00",
                       "end_datetime": "2026-07-21T17:00", "folder_layout": {
                           "structure_enabled": False, "input_path": "",
                       }}
        subevents = [edited_child, empty_child]
        if len(context["child_events"]) > 1:
            empty_child["id"] = context["child_events"][1]["id"]
        edit = build_event_preview({
            "event_kind": "event", "event_name": refiled["name"], "start_date": "2026-07-21", "end_date": "2026-07-21",
            "folder_layout": context["folder_layout"], "subevents": subevents,
        }, context["families"])
        update_event_definition(database, new_job, new_event_id, edit,
                                event_name=refiled["name"], notes="", expected_revision=context["event"]["revision"])
    compat = main.compatibility_workspace_root(library)
    sorting = build_event_sort_plan(database, new_job, new_event_id, compat, verify_sha256=True)
    assert sorting["summary"]["ready"], sorting["blockers"]
    sort_run = prepare_sort_run(
        database, new_job, new_event_id, compat,
        expected_plan_token=sorting["plan_token"], confirmation_phrase=CONFIRMATION_PHRASE,
    )
    execute_sort_run(database, sort_run["id"], compat)
    work_root = shared_work_root(compat)
    relative_root = Path(refiled["start_datetime"][:4], refiled["folder_name"])
    moved = work_root / relative_root
    shutil.copytree(moved, library.archive_root / relative_root)
    shutil.rmtree(moved)
    verification = verify_event_archive(database, library.archive_root, new_job, new_event_id,
                                        workspace_path=compat)
    assert verification["verified"], verification
    finalized = finalize_manually_moved_event_if_verified(
        database, compat, library.archive_root, new_job, new_event_id, verification,
    )
    assert finalized["manual_archive_finalized"]
    with database_connection(database) as connection:
        registered = event_file_rows(connection, new_event_id)
        assert {(row["id"], row["family_id"], row["sha256_current"]) for row in registered} == {
            (row["id"], row["family_id"], row["sha256_current"]) for row in extended_rows
        }
        assert all(row["current_root_kind"] == "camera_archive" for row in registered)
        assert all(Path(row["current_relative_path"]).parent.name == "Aufnahmen" for row in registered)
    import json
    from app.event_document import build_event_document_from_db
    from app.event_structure_changes import detect_event_structure_change
    child, empty = get_event_edit_context(database, new_job, new_event_id)["child_events"]
    assert child["folder_layout"]["input_path"] == "Aufnahmen"
    archived_tree = library.archive_root / relative_root
    assert list((archived_tree / empty["folder_name"]).iterdir()) == []
    archived_document = json.loads((archived_tree / "event.json").read_text())
    saved_document = build_event_document_from_db(database, compat, new_job, new_event_id, include_archived=True)
    for key in ("structure", "leaf_folder_layouts", "folder_layout"):
        assert archived_document[key] == saved_document[key]
    scan_event_inventory(database, library.archive_root, new_job, new_event_id, root_kind="camera_archive")
    assert detect_event_structure_change(database, new_event_id) is None
    published_directory = library.archive_root / relative_root / child["folder_name"] / "Sortierung" / "Auswahl" / "Details"
    published_directory.rename(published_directory.with_name("Extern"))
    scan_event_inventory(database, library.archive_root, new_job, new_event_id, root_kind="camera_archive")
    detected = detect_event_structure_change(database, new_event_id)
    assert detected is not None
    published_directory.with_name("Extern").rename(published_directory)
    scan_event_inventory(database, library.archive_root, new_job, new_event_id, root_kind="camera_archive")
    assert detect_event_structure_change(database, new_event_id) is None
    edited = dict(preview, event_name="Neu organisiert", parent_folder="07-21 - Neu organisiert",
                  selected_family_ids=released_family_ids,
                  subevents=[{"id": child["id"], "name": child["name"],
                              "start_datetime": child["start_datetime"], "end_datetime": child["end_datetime"],
                              "create_subfolder": False}])
    change = propose_event_change(database, new_job, new_event_id, edited, event_name="Neu organisiert",
                                  archive_root=library.archive_root, workspace_path=workspace)
    change_id = change["change_request_id"]
    changed_rows = [row for row in get_event_change_files(database, change_id) if row["new_path"]]
    changed_targets = [row["new_path"] for row in changed_rows]
    assert changed_targets and all(child["folder_name"] not in Path(target).parts for target in changed_targets)
    confirm_event_change(database, change_id, library.archive_root, workspace)
    assistant = build_archive_change_assistant(database, library.archive_root, workspace, change_id, scan_live=True)
    preparation = assistant['preparation']
    document_path = preparation['event_document']['target_relative_path']
    staged_document = shared_work_root(workspace) / preparation['staging_root'].split('/', 1)[1] / document_path
    for row in changed_rows:
        old_path = library.archive_root / row['old_path']
        new_path = library.archive_root / row['new_path']
        new_path.parent.mkdir(parents=True, exist_ok=True)
        if old_path != new_path:
            old_path.rename(new_path)
    target_root = library.archive_root / '2026' / edited['parent_folder']
    for item in verify_event_change(database, change_id, library.archive_root, workspace)['directories']:
        if item['status'] == 'missing':
            (library.archive_root / item['path']).mkdir(parents=True, exist_ok=True)
    shutil.copyfile(staged_document, target_root / 'event.json')
    shutil.rmtree(library.archive_root / relative_root)
    verified = verify_event_change(database, change_id, library.archive_root, workspace)
    assert verified['complete'], verified
    _json(client, 'POST', f'/api/change-requests/{change_id}/archive')
    [child] = get_event_edit_context(database, new_job, new_event_id)['child_events']
    assert child['folder_name'] == '' and child['folder_layout'] is None
    old_receipt = client.get(completion_path)
    assert old_receipt.status_code == 200 and "Nicht mehr im Archiv" in old_receipt.text
    assert f"&amp;event={event_id}" not in old_receipt.text


@pytest.mark.parametrize("fresh_main", [True], indirect=True, ids=["segments"])
def test_adopted_time_segments_survive_verified_archive_deletion_and_restart(
    fresh_main, monkeypatch, synthetic_dataset,
):
    import hashlib
    from io import BytesIO
    import json

    from app import archive_staging
    from app.archive_release_stock import verify_archive_release_copies, verify_archive_release_removal
    from app.event_change_apply import confirm_event_change, verify_event_change
    from app.event_change_request import get_event_change_files, propose_archived_event_deletion
    from app.event_inventory import event_root_relative
    from app.workspace_layout import backup_root

    workspace, database, registry, archive = fresh_main
    source = archive.parent / "legacy-source"
    source.mkdir()
    if os.environ.get("ADOPTION_ZFS_ROOT"):
        monkeypatch.setattr("app.legacy_adoption_dataset.prove", kernel_dataset_proof)
    captures = {b"raw": "12:59:59", b"jpg": "12:59:59", b"first": "13:00:00",
                b"last": "15:00:59", b"after": "15:01:00", b"other-day": "10:30:00"}
    originals = {"pair.raf": b"raw", "pair.jpg": b"jpg", "first.jpg": b"first", "last.jpg": b"last",
                 "after.jpg": b"after", "other-day.jpg": b"other-day"}
    for name, content in originals.items():
        (source / name).write_bytes(content)

    def metadata(descriptors, _cancel):
        results = {}
        for fd in descriptors:
            content = os.pread(fd, 32, 0)
            day = "22" if content == b"other-day" else "21"
            results[fd] = {"EXIF:ExifIFD:DateTimeOriginal": f"2026:07:{day} {captures[content]}"}
        return results

    monkeypatch.setattr(main, "NAS_SOURCE_ROOT", source)
    monkeypatch.setattr(main, "DATABASE_INITIALIZATION_ERROR", None)
    monkeypatch.setattr("app.legacy_adoption_inventory.read_bound_metadata", metadata)
    client = _onboard(fresh_main)
    _adopt(client)
    api = "/api/legacy-adoption"
    job = api + "/jobs/" + _json(client, "POST", api + "/jobs", status=201, json={"root": "nas"})["id"]
    _json(client, "POST", job + "/scan", status=202)
    day = "2026-07-21"
    child_layout = {"input_path": "Originals", "layout": {"version": 2, "nodes": [
        {"id": "originals", "name": "Originals"}, {"id": "prints", "name": "Prints", "role": "export"},
    ]}}
    event = {"name": "Afternoon", "start_date": day, "end_date": day,
             "start_time": "13:00", "end_time": "15:00", "children": [
                 {"name": "First", "start_datetime": day + "T13:00", "end_datetime": day + "T13:00",
                  "folder_layout": child_layout},
                 {"name": "Last", "start_datetime": day + "T13:01", "end_datetime": day + "T15:00",
                  "create_subfolder": False},
             ]}
    preview = _json(client, "POST", job + "/draft/check", json={"events": [event]})
    slots = preview["free_segments"]
    assert [(item["day_key"], item["start_time"], item["end_time"], item["families"], item["files"])
            for item in slots] == [(day, "00:00", "12:59", 1, 2), (day, "15:01", "23:59", 1, 1),
                                   ("2026-07-22", "00:00", "23:59", 1, 1)]
    assert preview["events"][0]["files"] == 2
    collection = {"event_kind": "no_event", "preserve_day_folders": True,
                  "folder_layout": {"structure_enabled": False, "input_path": ""},
                  "segments": [{key: segment[key] for key in ("day_key", "start_time", "end_time")}
                               for segment in slots[:2]]}
    another = {"name": "Another day", "start_date": "2026-07-22", "end_date": "2026-07-22"}
    draft = {"events": [event, collection, another]}
    assert _json(client, "POST", job + "/draft/check", json=draft)["free_segments"] == []
    revision = _json(client, "PUT", job + "/draft", json={**draft, "revision": 0})["revision"]
    plan = _json(client, "POST", job + "/plan", json={"revision": revision})
    command = {"plan_id": plan["id"]}
    _json(client, "POST", job + "/documents")
    _json(client, "POST", job + "/confirm", json={**command, "method": "manual", "acknowledged": True})
    for item in ("folders", "documents"):
        response = client.get(job + "/download/" + item)
        assert response.status_code == 200, response.text
        with ZipFile(BytesIO(response.content)) as package:
            package.extractall(archive)
    for item in _json(client, "GET", job + "/moves"):
        Path(item["source"]).rename(item["target"])
    assert _json(client, "POST", job + "/verify", json=command)["state"] == "verified"
    assert _json(client, "POST", job + "/finalize", json=command)["state"] == "completed"

    parent, collection, another = plan["events"]
    parent_root = archive / event_root_relative(parent)
    assert (parent_root / parent["children"][0]["folder_name"] / "Originals" / "first.jpg").is_file()
    assert (parent_root / parent["children"][0]["folder_name"] / "Prints").is_dir()
    [flat] = list(parent_root.rglob("last.jpg"))
    assert len(flat.relative_to(parent_root).parts) <= 2
    collection_id = collection["id"]
    anchor = catalogue_job_id(plan)
    collection_root = archive / event_root_relative(collection)
    document = json.loads((collection_root / "event.json").read_text())
    assert document["event"]["id"] == collection_id
    retained = {path: hashlib.sha256(path.read_bytes()).hexdigest()
                for item in (parent, another)
                for path in (archive / event_root_relative(item)).rglob("*") if path.is_file()}
    assert len(retained) >= 5
    with database_connection(database) as connection:
        assert tuple(connection.execute("SELECT start_datetime,end_datetime,uses_time_range FROM events WHERE id=?",
                                        (parent["id"],)).fetchone()) == (day + "T13:00:00", day + "T15:00:59", 0)
        members = event_file_rows(connection, collection_id)
        assert {row["original_filename"] for row in members} == {"pair.raf", "pair.jpg", "after.jpg"}
        assert document["event"]["occupied_intervals"] == [
            {key: item[key] for key in ("start_datetime", "end_datetime")} for item in collection["segments"]
        ]
        assert connection.execute("SELECT count(*) FROM event_time_segments WHERE event_id=?",
                                  (collection_id,)).fetchone()[0] == 2
        for child, name in zip(parent["children"], ("first.jpg", "last.jpg"), strict=True):
            assert [row[0] for row in connection.execute(
                "SELECT files.original_filename FROM event_assignments JOIN files USING(family_id) WHERE event_id=?",
                (child["id"],),
            )] == [name]

    request = propose_archived_event_deletion(database, anchor, collection_id, archive_root=archive)
    change = request["change_request_id"]
    confirm_event_change(database, change, archive, workspace)
    copies = {}
    for row in get_event_change_files(database, change):
        if not row.get("workspace_release_path"):
            continue
        dest = backup_root(workspace) / row["workspace_release_path"]
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(archive / row["old_path"], dest)
        copies[dest] = hashlib.sha256(dest.read_bytes()).hexdigest()
    assert len(copies) == 3 and verify_archive_release_copies(database, archive, workspace, change)["complete"]
    shutil.rmtree(collection_root)
    assert verify_archive_release_removal(database, archive, workspace, change)["complete"]
    assert verify_event_change(database, change, archive, workspace)["verified_file_count"] == 3

    def interrupt_completion(*_args, **_kwargs):
        raise RuntimeError("synthetic outage after verification")

    finish = f"/api/change-requests/{change}/archive"
    with monkeypatch.context() as interruption:
        interruption.setattr(archive_staging, "cleanup_archive_change_staging", interrupt_completion)
        assert "synthetic outage after verification" in _json(client, "POST", finish, status=500)["detail"]
    assert not operation_health.inspect(workspace)["writes_allowed"]
    main.startup_database()
    reopened = TestClient(main.app, follow_redirects=False)
    result = _json(reopened, "POST", finish)
    assert result["event_deleted"] and result["verified_file_count"] == 3
    assert _json(reopened, "POST", finish) == result
    assert operation_health.inspect(workspace)["writes_allowed"]
    assert all(hashlib.sha256(path.read_bytes()).hexdigest() == checksum for path, checksum in (retained | copies).items())
    with database_connection(database) as connection:
        assert connection.execute("SELECT 1 FROM events WHERE id=?", (collection_id,)).fetchone() is None
        assert not connection.execute("PRAGMA foreign_key_check").fetchall()
    summary = _json(reopened, "GET", "/api/workspace/summary?jobs=&physical_refresh=false")
    groups = summary["released_archive_groups"]
    assert len(groups) == 2
    released_ids = {family_id for group in groups for family_id in group["family_ids"]}
    assert released_ids == {row["family_id"] for row in members}
    refiled = _json(reopened, "POST", f"/api/jobs/{anchor}/events", json={
        "event_kind": "no_event", "no_event_segments": collection["segments"],
        "selected_family_ids": sorted(released_ids),
    })
    assert refiled["parent_event"]["id"] != collection_id
    assert _json(reopened, "GET", "/api/workspace/summary?jobs=&physical_refresh=false")["released_archive_groups"] == []


def test_exclusive_mode_holds_until_explicit_skip(
    fresh_main, tmp_path, monkeypatch, synthetic_dataset,
):
    from app.legacy_adoption_mode import active_adoption, adoption_access

    _, _, registry, _ = fresh_main
    source = tmp_path.resolve() / "legacy-source"
    source.mkdir()
    monkeypatch.setattr(main, "NAS_SOURCE_ROOT", source)
    monkeypatch.setattr(main, "DATABASE_INITIALIZATION_ERROR", None)
    client = _onboard(fresh_main)
    assert _adopt(client) == {"next": "/legacy-adoption"}
    jobs = "/api/legacy-adoption/jobs"
    with adoption_access(registry):
        result = _json(client, "POST", jobs, status=409, json={"root": "nas"})
        assert result["code"] == "legacy_adoption_busy"
    assert active_adoption(registry) is None

    job_id = _json(client, "POST", jobs, status=201, json={"root": "nas"})["id"]
    assert active_adoption(registry)["job_id"] == job_id
    assert active_adoption(registry)["library_id"] == "main"

    calls = []
    stop = main.WORKER_STOP
    monkeypatch.setattr(stop, "wait", lambda seconds: stop.set())
    monkeypatch.setattr(main, "_claim_runtime_job", calls.append)
    main.worker_loop()
    assert calls == []
    _json(client, "DELETE", jobs + "/" + job_id)
    assert active_adoption(registry) is None
    assert _json(client, "GET", "/api/jobs", status=409)["code"] == "initial_setup_required"
    restarted = TestClient(main.app, follow_redirects=False)
    assert restarted.get("/setup/adoption").status_code == 200
    assert _json(restarted, "POST", "/api/setup/adoption", json={"decision": "skipped"}) == {"next": "/"}
    assert pending_initial_setup(registry) is None
    assert _json(restarted, "GET", "/api/jobs", library="main")["count"] == 0
    stop.clear()
    main.worker_loop()
    assert calls == [None]
    assert _json(restarted, "POST", jobs, status=409, json={"root": "nas"})["code"] == "legacy_adoption_inactive"


def test_script_host_proof_release_and_independent_archive_verification(
    fresh_main, tmp_path, monkeypatch, synthetic_dataset,
):
    import json
    import shlex
    import subprocess

    from pathlib import PurePosixPath
    from app import legacy_adoption_dataset as dataset, legacy_adoption_discover as discovery, legacy_adoption_verify
    from app import legacy_adoption_host as host, legacy_adoption_package as package
    from tests.backend.test_legacy_adoption_host import _macos_rename

    _, _, registry, _ = fresh_main
    root = tmp_path.resolve()
    source = root / "source with space"
    appdata = root / "app's data"
    source.mkdir()
    appdata.mkdir()
    original = source / "proof.raf"
    original.write_bytes(b"synthetic script photo")
    evidence = {"dataset": "synthetic/test", "device": "0:42",
                "source_directory": "/source with space", "archive_directory": "/first-install/archive"}
    monkeypatch.setattr(dataset, "prove", lambda *args: evidence)
    monkeypatch.setattr(main, "NAS_SOURCE_ROOT", source)
    monkeypatch.setattr(main, "DATABASE_INITIALIZATION_ERROR", None)
    monkeypatch.setattr(package, "appdata_root", lambda: appdata)
    monkeypatch.setattr(host, "revalidate", lambda *args: None)
    monkeypatch.setattr(
        "app.legacy_adoption_inventory.read_bound_metadata",
        lambda descriptors, _cancel: {
            fd: {"EXIF:ExifIFD:DateTimeOriginal": "2026:07:21 12:00:00"} for fd in descriptors
        },
    )
    if sys.platform == "darwin":
        monkeypatch.setattr(host, "mount_id", lambda _fd: 1)
        monkeypatch.setattr(host, "rename_noreplace", _macos_rename)
    client = _onboard(fresh_main)
    _adopt(client)
    api = "/api/legacy-adoption"
    job_id = _json(client, "POST", api + "/jobs", status=201, json={"root": "nas"})["id"]
    job = api + "/jobs/" + job_id
    _json(client, "POST", job + "/scan", status=202)
    saved = _json(client, "PUT", job + "/draft", json={"revision": 0, "events": [{
        "name": "Skript", "start_date": "2026-07-21", "end_date": "2026-07-21",
    }]})
    plan = _json(client, "POST", job + "/plan", json={"revision": saved["revision"]})
    _json(client, "POST", job + "/documents")
    manual_id = plan["id"]
    [manual_move] = _json(client, "GET", job + "/moves")
    assert Path(manual_move["target_path"]).name == "proof.raf"
    plan = _json(client, "POST", job + "/execution-method", json={"plan_id": manual_id, "method": "script"})
    assert plan["id"] != manual_id and plan["documents_at"] and plan["filename_method"] == "script"
    assert _json(client, "POST", job + "/confirm", status=409,
                 json={"plan_id": plan["id"], "method": "manual", "acknowledged": True})
    [script_move] = _json(client, "GET", job + "/moves?renamed=true")
    assert Path(script_move["target_path"]).name == "20260721_120000_Unbekanntes-Gerät.raf"
    command = {"plan_id": plan["id"]}
    library = resolve_library_context(registry, "main")
    # Exercise the host mapping with a synthetic mount table. The real
    # Linux/ZFS container run executes the returned shell command itself.
    monkeypatch.setattr(package, "_package_mount", lambda path, fd: {"directory": str(path), "device": "0:42"})

    auto = _json(client, "POST", job + "/script/probe", json=command)
    assert auto["host"] is None and not auto["verified"]
    package_root = appdata / "legacy-adoption" / job_id
    assert {path.name for path in package_root.iterdir()} >= {
        "probe.json", "execution.lock", "journal.jsonl", "legacy_adoption_discover.py",
    }
    assert "\n" not in auto["command"] and shlex.split(auto["command"])[:3] == ["sudo", "python3", "-I"]
    with monkeypatch.context() as simulated_host:
        simulated_host.setitem(sys.modules, "legacy_adoption_dataset", dataset)
        simulated_host.setattr(discovery, "load_runner", lambda *_: host)
        simulated_host.setattr(dataset, "mount_table", lambda: {})
        if sys.platform == "darwin":
            simulated_host.setattr(host, "probe_roots", lambda *args: None)
        args = (str(package_root), host.inode(package_root.stat()), auto["sha256"], {})
        with pytest.raises(ValueError, match="No native ZFS mount"):
            discovery.verify(*args)
        failure = _json(client, "GET", job + "/script/probe")
        assert not failure["verified"] and "No native ZFS mount" in failure["diagnostic"]
        mount = dataset.Mount("0:42", PurePosixPath("/"), PurePosixPath(root), "zfs", "synthetic/test")
        simulated_host.setattr(dataset, "mount_table", lambda: {1: mount})
        discovery.verify(*args)
    proved = _json(client, "GET", job + "/script/probe")
    assert proved["verified"] and proved["host"]["package"] == str(package_root)
    assert proved["dataset"] == "synthetic/test"
    assert proved["diagnostic"] is None
    assert original.read_bytes() == b"synthetic script photo"
    probe = _json(client, "POST", job + "/script/probe", json={
        **command, "appdata": str(appdata), "source": str(source), "archive": str(library.archive_root),
    })
    confirm = {**command, "method": "script", "acknowledged": True, "probe_sha256": probe["sha256"]}
    _json(client, "POST", job + "/confirm", json=confirm, status=409)

    def external(shell_command):
        subprocess.run(["/bin/sh", "-n", "-c", shell_command], check=True)
        args = shlex.split(shell_command)
        assert args[:5] == ["sudo", "python3", "-I", "-B", "-c"]
        path, device, inode, _, mode, digest, source_path, archive_path = args[6:]
        assert path == probe["host"]["package"]
        major, minor = map(int, device.split(":"))
        return host.main([mode, "--package", path, "--source", source_path, "--archive", archive_path,
                          "--sha256", digest, "--package-device", str(os.makedev(major, minor)),
                          "--package-inode", inode])

    assert external(probe["command"]) == 0
    assert _json(client, "GET", job + "/script/probe")["verified"]
    assert _json(client, "POST", job + "/confirm", json=confirm)["execution"]["phase"] == "script_prepared"
    assert not _json(client, "GET", job + "/script").get("command")
    assert _json(client, "GET", job + "/download/documents", status=409)["detail"]
    apply = _json(client, "POST", job + "/script/release", json=command)["command"]
    _json(client, "POST", job + "/finalize", json=command, status=409)
    # A reported completion is insufficient while the planned files are still at the source.
    package_root = Path(probe["host"]["package"])
    binding = json.loads((package_root / "permission.json").read_text())["manifest"]
    (package_root / "status.json").write_bytes(host.json_bytes({
        "manifest": binding, "mode": "apply", "state": "completed",
    }))
    assert _json(client, "POST", job + "/finalize", json=command)["execution"]["phase"] == "repair"
    assert external(apply) == 1
    assert _json(client, "POST", job + "/script/release", json=command)["command"] == apply
    assert external(apply) == 0
    assert not original.exists()
    assert _json(client, "GET", job + "/script")["status"]["state"] == "completed"
    [move] = _json(client, "GET", job + "/moves")
    observed_hashes = []
    checksum = legacy_adoption_verify.bound_sha256

    def count_hash(descriptor):
        observed_hashes.append(os.fstat(descriptor).st_ino)
        return checksum(descriptor)

    monkeypatch.setattr(legacy_adoption_verify, "bound_sha256", count_hash)
    assert _json(client, "POST", job + "/finalize", json=command)["execution"]["phase"] == "completed"
    assert observed_hashes.count(Path(move["target"]).stat().st_ino) == 1
    assert len(observed_hashes) == 2  # One photo and its event document.
    assert external(apply) == 1
    assert Path(move["target"]).read_bytes() == b"synthetic script photo"


def test_review_family_is_copied_to_general_once_and_survives_discard(
    fresh_main, tmp_path, monkeypatch, synthetic_dataset,
):
    import errno
    from app import legacy_adoption_host as host
    from app.metadata_correction import metadata_area_paths, scan_metadata_area
    from app.source_filter import LEGACY_REVIEW_STAGING
    from tests.backend.test_legacy_adoption_host import _macos_rename

    workspace, _, registry, _ = fresh_main
    source = tmp_path.resolve() / "legacy-source"
    source.mkdir()
    originals = {"bad.raf": b"raw", "bad.jpg": b"jpeg", "bad.raf.xmp": b"sidecar", "good.jpg": b"good"}
    for name, content in originals.items():
        (source / name).write_bytes(content)
    monkeypatch.setattr(main, "NAS_SOURCE_ROOT", source)
    monkeypatch.setattr(main, "DATABASE_INITIALIZATION_ERROR", None)
    monkeypatch.setattr(
        "app.legacy_adoption_inventory.read_bound_metadata",
        lambda descriptors, _cancel: {
            fd: {"EXIF:ExifIFD:DateTimeOriginal": "2026:07:21 12:00:00"} if os.pread(fd, 4, 0) == b"good" else {}
            for fd in descriptors
        },
    )
    if sys.platform == "darwin":
        monkeypatch.setattr(host, "rename_noreplace", _macos_rename)
    client = _onboard(fresh_main)
    _adopt(client)
    api = "/api/legacy-adoption"
    job_id = _json(client, "POST", api + "/jobs", status=201, json={"root": "nas"})["id"]
    job = api + "/jobs/" + job_id
    _json(client, "POST", job + "/scan", status=202)
    assert _json(client, "GET", job)["review_count"] == 1
    [case] = _json(client, "GET", job + "/review")
    assert case["family_key"] == "bad"
    assert case["state"] == "open"
    assert "missing_capture_time" in case["reasons"]
    assert {item["relative_path"] for item in case["files"]} == set(originals) - {"good.jpg"}
    command = {"family_key": case["family_key"]}
    rename = host.rename_noreplace
    general = metadata_area_paths(area="general", workspace_root=workspace, library_id="main", create=False)["root"]
    (general / "bad.NEF").write_bytes(b"existing unrelated family")

    def interrupt_after_publication(src, src_name, dst, dst_name):
        rename(src, src_name, dst, dst_name)
        if dst_name == "bad_1.jpg":
            raise OSError(errno.EIO, "synthetic interruption after workspace publication")

    with monkeypatch.context() as interrupted:
        interrupted.setattr(host, "rename_noreplace", interrupt_after_publication)
        _json(client, "POST", job + "/review/copy", status=409, json=command)
    assert _json(client, "GET", job + "/review")[0]["state"] == "copying"
    assert (general / "bad_1.jpg").read_bytes() == originals["bad.jpg"]
    _json(client, "DELETE", job, status=409)
    (general / "bad_1.RAF").write_bytes(b"late foreign collision")
    copied = _json(client, "POST", job + "/review/copy", json=command)
    assert copied["file_count"] == 3
    assert copied["state"] == "copied"
    assert set(copied["target_files"]) == {"bad_2.jpg", "bad_2.raf", "bad_2.raf.xmp"}
    assert (general / "bad.NEF").read_bytes() == b"existing unrelated family"
    assert (general / "bad_1.RAF").read_bytes() == b"late foreign collision"
    assert not (general / "bad_1.jpg").exists()
    assert _json(client, "POST", job + "/review/copy", json=command) == copied
    assert _json(client, "GET", job + "/review")[0]["state"] == "copied"
    assert all((source / name).read_bytes() == data for name, data in originals.items())
    draft = _json(client, "PUT", job + "/draft", json={"revision": 0, "events": [{
        "name": "Review fixture", "start_date": "2026-07-21", "end_date": "2026-07-21",
    }], "capture_overrides": {"bad": "2026-07-21T11:00:00"}})
    _json(client, "POST", job + "/plan", json={"revision": draft["revision"]})
    assert [move["relative_path"] for move in _json(client, "GET", job + "/moves")] == ["good.jpg"]
    _json(client, "DELETE", job)
    assert not list((general / LEGACY_REVIEW_STAGING).iterdir())
    assert not list(general.glob("legacy-*"))
    assert {name: (general / name).read_bytes() for name in copied["target_files"]} == {
        "bad_2" + key[3:]: data for key, data in originals.items() if key != "good.jpg"
    }
    library = resolve_library_context(registry, "main")
    monkeypatch.setattr("app.metadata.run_exiftool", lambda *_args, **_kwargs: [])
    scan = scan_metadata_area(area="general", workspace_root=workspace, library_id="main",
                              database_path=library.database_path)
    assert {item["filename"] for item in scan["files"]} == set(copied["target_files"]) | {"bad.NEF", "bad_1.RAF"}

    from hashlib import sha256

    older = b"RC12 working copy"
    (source / "older.jpg").write_bytes(older)
    nested = general / ("legacy-" + sha256(host.json_bytes([("older.jpg", sha256(older).hexdigest())])).hexdigest())
    nested.mkdir()
    (nested / "older.jpg").write_bytes(older)
    new_id = _json(client, "POST", api + "/jobs", status=201, json={"root": "nas"})["id"]
    again = api + "/jobs/" + new_id
    _json(client, "POST", again + "/scan", status=202)
    assert _json(client, "POST", again + "/review/copy", json=command)["target_files"] == copied["target_files"]
    legacy = _json(client, "POST", again + "/review/copy", json={"family_key": "older"})
    assert legacy["state"] == "copied" and legacy["target_relative"] == nested.name
    assert not (general / "older.jpg").exists()
    assert (nested / "older.jpg").read_bytes() == older
    assert not list(general.glob("bad_3*"))

@pytest.mark.parametrize("fresh_main", [True, "review-unlinked"], indirect=True, ids=["review-zfs", "review-unlinked"])
def test_review_batch_resumes_after_interruption_and_reintegrates_corrected_copy(
    fresh_main, monkeypatch, synthetic_dataset, request,
):
    import errno
    from threading import Event, Thread

    from PIL import Image
    from app import legacy_adoption_review as review
    from app import legacy_adoption_review_cancel as cancellation
    from app import legacy_adoption_host as host
    from app import legacy_adoption_review_progress as progress
    from app.database import get_job
    from app.source_filter import LEGACY_REVIEW_PRIVATE_STAGING, LEGACY_REVIEW_STAGING, LEGACY_REVIEW_VERIFIED_STAGING
    from app.metadata_correction import execute_metadata_correction, metadata_area_paths, scan_metadata_area
    from tests.backend.test_legacy_adoption_host import _macos_rename

    unlinked = request.node.callspec.id == "review-unlinked"
    native_acl = unlinked and os.environ.get("ADOPTION_NFSV4_ROOT")
    workspace, db, registry, archive = fresh_main
    source = archive.parent / "legacy-review-source"
    source.mkdir()
    if os.environ.get("ADOPTION_ZFS_ROOT"):
        monkeypatch.setattr("app.legacy_adoption_dataset.prove", kernel_dataset_proof)
    if sys.platform == "darwin":
        monkeypatch.setattr(host, "rename_noreplace", _macos_rename)
    for i in range(61):
        (source / f"photo-{i:03}.jpg").write_bytes(f"synthetic {i}".encode())
    (source / "photo-001.raf").write_bytes(b"raw data" + b"x" * (3 * 1024 * 1024))
    (source / "photo-001.raf.xmp").write_bytes(b"sidecar data")
    exif = Image.Exif()
    exif[271] = "Synthetic RC11 Camera"
    Image.new("RGB", (8, 8), "green").save(source / "photo-000.jpg", exif=exif)
    originals = {p.name: p.read_bytes() for p in source.iterdir()}
    monkeypatch.setattr(main, "NAS_SOURCE_ROOT", source)
    monkeypatch.setattr(main, "DATABASE_INITIALIZATION_ERROR", None)
    reading, read_release = Event(), Event()

    def metadata(descriptors, _cancel):
        reading.set()
        assert read_release.wait(10)
        dates = {b"raw data": "2026:07:20 10:00:00", b"synthetic 1": "2026:07:21 10:00:00"}
        return {fd: ({"EXIF:ExifIFD:DateTimeOriginal": dates[match]} if
                     (match := (b"raw data" if data.startswith(b"raw data") else data)) in dates else {})
                for fd in descriptors if (data := os.pread(fd, 13, 0))}

    monkeypatch.setattr("app.legacy_adoption_inventory.read_bound_metadata", metadata)
    client = _onboard(fresh_main)
    _adopt(client)
    api = "/api/legacy-adoption"
    job_id = _json(client, "POST", api + "/jobs", status=201, json={"root": "nas"})["id"]
    job = api + "/jobs/" + job_id

    inventory_responses = []
    scan = Thread(target=lambda: inventory_responses.append(client.post(job + "/scan")))
    scan.start()
    try:
        assert reading.wait(10)
        reopened = TestClient(main.app, follow_redirects=False)
        assert _json(reopened, "GET", job)["scan_running"]
    finally:
        read_release.set()
        scan.join(15)
    assert [r.status_code for r in inventory_responses] == [202]
    page = _json(reopened, "GET", job + "/review")
    assert len(page) == 60 and _json(reopened, "GET", job)["review_count"] == 61
    available = _json(reopened, "GET", job + "/review/selection")
    assert len(available) == 61 and available[-1] == "photo-060"
    assert page[0]["reasons"] == ["missing_capture_time"]
    assert page[1]["reasons"] == ["conflicting_capture_time"]
    assert any(file["metadata"]["selected_capture_source"] for file in page[1]["files"])

    general = metadata_area_paths(area="general", workspace_root=workspace, library_id="main", create=False)["root"]
    if unlinked:
        from app.private_storage_security import NFS4
        verified_root = general / LEGACY_REVIEW_VERIFIED_STAGING
        if native_acl:
            import struct
            import subprocess

            dataset = subprocess.check_output(["findmnt", "-n", "-o", "SOURCE", "-T", general], text=True).strip()
            assert os.geteuid() != 0
            properties = subprocess.check_output(
                ["zfs", "get", "-Hp", "-o", "value", "acltype,aclmode,aclinherit", dataset], text=True,
            ).splitlines()
            assert properties == ["nfsv4", "restricted", "passthrough"]
            inherited = struct.pack("!II10I", 0, 2,
                0, 0x03, 1, 0x1f01ff, 1,  # owner@, inherited by files and directories
                0, 0x43, 0, 0x1301ff, 65531,  # another group with inherited modify access
            )
            os.setxattr(general, NFS4[0], inherited)
            original_acl = os.getxattr(general, NFS4[0])
            with review.bound_directory(general) as descriptor:
                assert review._native_staging(descriptor)
            verified_root.mkdir()
            from app.private_storage_security import _native_entries

            acl = os.getxattr(verified_root, NFS4[0])
            assert any(kind == 0 and not special and who == 65531 and flags & 0x80 and mask & 0x2
                       for _, kind, flags, special, mask, who in _native_entries(acl, str(verified_root)))
            with pytest.raises(PermissionError) as restricted_chmod:
                verified_root.chmod(0o700)
            assert restricted_chmod.value.errno == errno.EPERM
            verified_root.rmdir()
        else:
            # Ubuntu's upstream OpenZFS can exercise the real Linux opening,
            # linking, restart and publication syscalls on a local filesystem.
            monkeypatch.setattr(review, "_native_staging", lambda _fd: True)

        def refuse_acl_write(*_args, **_kwargs):
            raise PermissionError(errno.EPERM, "application has no WRITE_ACL capability")

        monkeypatch.setattr(os, "setxattr", refuse_acl_write)
        unsafe = verified_root
    else:
        unsafe = general / LEGACY_REVIEW_PRIVATE_STAGING

    # RC10 leaves this empty directory behind when inheritance broadens mkdir(0700).
    legacy_staging = general / LEGACY_REVIEW_STAGING
    legacy_staging.mkdir(mode=0o750)
    if not native_acl:
        legacy_staging.chmod(0o750)
    unsafe.symlink_to(legacy_staging, target_is_directory=True)
    _json(reopened, "POST", job + "/review/batch", status=202, json={"family_keys": available})
    assert _json(reopened, "GET", job + "/review/batch")["failed"] == len(available)
    assert unsafe.is_symlink() and not list(legacy_staging.iterdir())
    assert not list(general.glob("legacy-*"))
    unsafe.unlink()
    publish = review._publish_copy
    entered, release = Event(), Event()
    writing, release_write = Event(), Event()

    def measure_write(count):
        wrote(count)
        if count == 1024 * 1024 and not writing.is_set():
            writing.set()
            assert release_write.wait(20)

    wrote = progress.wrote

    def interrupt(library, adoption, members, destination):
        if members[0][0] == "photo-001.jpg":
            if unlinked:
                link = os.link

                def interrupt_partial(source, name, **kwargs):
                    assert os.fstat(int(source.rsplit("/", 1)[-1])).st_nlink == 0
                    if name == "photo-001.raf":
                        raise RuntimeError("simulate loss before linking a verified inode")
                    return link(source, name, **kwargs)

                with monkeypatch.context() as interrupted:
                    interrupted.setattr(os, "link", interrupt_partial)
                    with pytest.raises(RuntimeError, match="simulate loss before linking"):
                        publish(library, adoption, members, destination)
                with database_connection(db) as connection:
                    stage = cancellation.journal(connection, job_id, "photo-001")
                linked = verified_root / cancellation.folder_name(stage)
                assert {file.name: file.read_bytes() for file in linked.iterdir()} == {
                    "photo-001.jpg": originals["photo-001.jpg"],
                }
                from app.source_filter import should_ignore_source_path
                assert should_ignore_source_path(general, linked / "photo-001.jpg")
            else:
                publish(library, adoption, members, destination)
            entered.set()
            assert release.wait(10)
            raise RuntimeError("simulate process loss after atomic family publication")
        publish(library, adoption, members, destination)

    responses = []
    with monkeypatch.context() as stopped:
        stopped.setattr(review, "_publish_copy", interrupt)
        stopped.setattr(progress, "wrote", measure_write)
        copy = Thread(target=lambda: responses.append(reopened.post(job + "/review/batch", json={"family_keys": None})))
        copy.start()
        try:
            assert writing.wait(20)
            browser = TestClient(main.app, follow_redirects=False)
            live = _json(browser, "GET", job + "/review/batch?details=true")
            assert live["bytes_total"] == sum(map(len, originals.values()))
            assert live["bytes_written"] > live["bytes_verified"]
            assert live["active"]["family_key"] == "photo-001"
            assert live["active"]["bytes_verified"] < live["active"]["bytes_written"] < live["active"]["bytes_total"]
            release_write.set()
            assert entered.wait(20)
            assert _json(browser, "GET", job + "/review/batch") == {
                "total": 61, "copied": 1, "failed": 0, "pending": 60, "running": True,
                "batch_id": live["batch_id"], "state": "active", "cancel_error": None,
            }
            _json(browser, "DELETE", job, status=409)
            _json(browser, "POST", job + "/scan", status=409)
            _json(browser, "POST", job + "/review/batch", status=409, json={"family_keys": None})
        finally:
            release_write.set()
            release.set()
            copy.join(20)
    assert [r.status_code for r in responses] == [202]
    main.startup_database()
    assert main.DATABASE_INITIALIZATION_ERROR is None
    if main.ADOPTION_STARTUP_THREAD:
        main.ADOPTION_STARTUP_THREAD.join(timeout=15)
    browser = TestClient(main.app, follow_redirects=False)
    assert _json(browser, "GET", job + "/review/batch") == {
        "total": 61, "copied": 1, "failed": 0, "pending": 60, "running": False,
        "batch_id": live["batch_id"], "state": "active", "cancel_error": None,
    }
    restarted = _json(browser, "GET", job + "/review/batch?details=true")
    assert restarted["active"] is None and restarted["bytes_written"] == restarted["bytes_verified"] > 0

    def no_space(library, adoption, members, destination):
        if members[0][0] == "photo-002.jpg":
            raise OSError(errno.ENOSPC, "simulated insufficient space")
        publish(library, adoption, members, destination)

    with monkeypatch.context() as full:
        full.setattr(review, "_publish_copy", no_space)
        _json(browser, "POST", job + "/review/batch/resume", status=202)
    assert _json(browser, "GET", job + "/review/batch") == {
        "total": 61, "copied": 60, "failed": 1, "pending": 0, "running": False,
        "batch_id": live["batch_id"], "state": "finished", "cancel_error": None,
    }
    page = _json(browser, "GET", job + "/review")
    assert page[2]["can_copy"] and "nicht genug Speicherplatz" in page[2]["copy_error"]
    _json(browser, "POST", job + "/review/batch", status=409, json={"family_keys": ["photo-001"]})
    _json(browser, "POST", job + "/review/batch", status=202,
          json={"family_keys": ["photo-001", "photo-002", "photo-002"]})
    assert _json(browser, "GET", job + "/review/batch")["copied"] == 1
    page = _json(browser, "GET", job + "/review")
    remaining = _json(browser, "GET", job + "/review", params={"after": page[-1]["family_key"]})
    assert len(remaining) == 1 and remaining[0]["state"] == "copied"
    if unlinked:
        assert not list(verified_root.iterdir())
        assert not list(legacy_staging.iterdir())
        if native_acl:
            assert os.getxattr(general, NFS4[0]) == original_acl
    else:
        assert unsafe.stat().st_mode & 0o777 == 0o700
        assert legacy_staging.stat().st_mode & 0o777 == 0o750
    assert not _json(browser, "GET", job + "/review/selection")
    assert not list(general.glob("legacy-*"))
    assert len([item for item in general.iterdir() if item.is_file()]) == 63

    _json(browser, "DELETE", job)
    _json(browser, "POST", "/api/setup/adoption", json={"decision": "skipped"})
    assert browser.get("/").status_code == 200
    if main.ADOPTION_STARTUP_THREAD:
        main.ADOPTION_STARTUP_THREAD.join(timeout=15)
    assert operation_health.inspect(workspace)["writes_allowed"]
    relatives = {f["relative_path"] for f in scan_metadata_area(
        area="general", workspace_root=workspace, library_id="main", database_path=db,
    )["files"]}
    assert {p: (general / p).read_bytes() for p in page[1]["target_files"]} == {
        filename: originals[filename] for filename in ("photo-001.jpg", "photo-001.raf", "photo-001.raf.xmp")
    }
    [relative] = page[0]["target_files"]
    assert relative == "photo-000.jpg"
    assert relative in relatives
    assert (general / relative).read_bytes() == originals["photo-000.jpg"]
    with Image.open(general / relative) as image:
        assert image.getexif()[271] == "Synthetic RC11 Camera"
    stamp = "2026-07-19T17:51:50+02:00"
    correction = execute_metadata_correction(db, area="general", relative_path=relative,
        proposed_datetime=stamp, workspace_root=workspace, library_id="main")
    assert correction["status"] == "completed"
    monkeypatch.setattr(main, "load_settings", lambda: {"storage": {"safety_reserve_gib": 0, "processing_buffer_percent": 0}})
    transfer = _json(browser, "POST", "/api/metadata-correction/general/reintegrate", status=202,
                     json={"items": [{"relative_path": relative}]})
    queued = main.claim_next_job(db, operation="metadata_general_import")
    assert queued and queued["id"] == transfer["job"]["id"]
    main.process_claimed_job(queued, library_context=resolve_library_context(registry, "main"))
    assert get_job(db, queued["id"])["state"] == "completed"
    assert not (general / relative).exists()
    with database_connection(db) as connection:
        allocated = connection.execute(
            "SELECT current_relative_path, sha256_current FROM files WHERE job_id = ?", (queued["id"],),
        ).fetchone()
    assert "2026-07-19" in allocated["current_relative_path"]
    assert allocated["sha256_current"] == correction["output_sha256"]
    assert {p.name: p.read_bytes() for p in source.iterdir()} == originals
    assert not list(archive.iterdir())


@pytest.mark.skipif(sys.platform != "linux", reason="O_TMPFILE requires Linux")
def test_review_never_links_an_unverified_inode(tmp_path, monkeypatch):
    from app import legacy_adoption_review as review

    directory = tmp_path.resolve()
    member = {"size_bytes": 4, "sha256": "incorrect-digest"}

    def write_bad_copy(_source, output, _member):
        output.write(b"test")
        output.flush()
        assert os.fstat(output.fileno()).st_nlink == 0
        assert not list(directory.iterdir())

    monkeypatch.setattr(review, "_write_member", write_bad_copy)
    with review.bound_directory(directory) as stage:
        with pytest.raises(review.AdoptionError, match="weicht von der Inventur ab"):
            review._copy_unnamed_member(None, stage, "photo.jpg", member)
    assert not list(directory.iterdir())


def test_review_capacity_gate_accounts_for_entire_family(monkeypatch):
    from types import SimpleNamespace
    from app.legacy_adoption_paths import AdoptionError
    from app.legacy_adoption_review import _check_capacity

    members = [{"size_bytes": 8192}, {"size_bytes": 2048}]
    monkeypatch.setattr(os, "fstatvfs", lambda _descriptor: SimpleNamespace(f_bavail=4, f_frsize=4096))
    with pytest.raises(AdoptionError, match="nicht genug Speicherplatz"):
        _check_capacity(0, members)
    monkeypatch.setattr(os, "fstatvfs", lambda _descriptor: SimpleNamespace(f_bavail=5, f_frsize=4096))
    _check_capacity(0, members)


@pytest.mark.skipif(
    sys.platform != "linux" or os.environ.get("GITHUB_ACTIONS") != "true",
    reason="Der echte Read-only-Bind-Mount läuft auf dem isolierten Linux-Runner.",
)
def test_adoption_reads_actual_read_only_archive(inventory, monkeypatch):
    import errno
    import subprocess
    from dataclasses import replace

    from app.legacy_adoption_inventory import create_job, scan_inventory
    from app.legacy_adoption_plan import create_plan
    from tests.backend.test_legacy_adoption_plan import _draft

    context, fixture_source, registry = inventory
    physical, source = context.archive_root, fixture_source
    native_dataset = os.environ.get("ADOPTION_ZFS_ROOT")
    if native_dataset:
        from app import legacy_adoption_dataset
        from app.legacy_adoption_paths import bound_directory

        monkeypatch.setattr(legacy_adoption_dataset, "prove", kernel_dataset_proof)
        physical = Path(native_dataset) / "archive"
        source = Path(native_dataset) / "source"
        physical.mkdir()
        source.mkdir()
        other = Path(os.environ["ADOPTION_ZFS_OTHER"])
        with bound_directory(source) as left, bound_directory(other) as right:
            with pytest.raises(legacy_adoption_dataset.DatasetError, match="nicht auf demselben"):
                kernel_dataset_proof(source, other, left, right)

    mount = context.archive_root.with_name("read-only-archive")
    source_mount = context.archive_root.with_name("read-only-source")
    mounted = []
    try:
        for native, view in ((physical, mount), (source, source_mount)):
            view.mkdir()
            subprocess.run(["sudo", "-n", "mount", "--bind", str(native), str(view)], check=True)
            mounted.append(view)
            subprocess.run(["sudo", "-n", "mount", "-o", "remount,bind,ro", str(view)], check=True)
            assert os.statvfs(view).f_flag & os.ST_RDONLY
            with pytest.raises(OSError) as denied:
                (view / "attempt").write_bytes(b"must fail")
            assert denied.value.errno == errno.EROFS
        if native_dataset:
            nested = source / "nested"
            nested.mkdir()
            subprocess.run(["sudo", "-n", "mount", "--bind", str(other), str(source_mount / "nested")], check=True)
            mounted.append(source_mount / "nested")
            with bound_directory(source_mount) as left, bound_directory(mount) as right:
                with pytest.raises(legacy_adoption_dataset.DatasetError, match="weitere Einbindung"):
                    kernel_dataset_proof(source_mount, mount, left, right)
            subprocess.run(["sudo", "-n", "umount", str(mounted[-1])], check=True)
            mounted.pop()
            nested.rmdir()
        library = replace(context, archive_root=mount)
        from app.library_registry import register_library
        library.work_root.mkdir()
        register_library.__wrapped__(
            registry, library_id=library.library_id, display_name=library.display_name,
            database_path=library.database_path, workspace_root=library.workspace_root,
            work_root=library.work_root, archive_root=library.archive_root,
        )
        # The fixture stands in for the user's manual writable SMB view. The
        # application reads the same archive through a kernel read-only mount.
        def writable_target(path):
            return physical / Path(path).relative_to(mount)

        (source / "proof.raf").write_bytes(b"RO archive synthetic")
        job = create_job(library, source_mount)
        scan_inventory(library, job)
        plan = create_plan(library, registry, job, _draft())
        if native_dataset:
            assert plan["dataset"]["dataset"].endswith("/media")
        from app.legacy_adoption_catalogue import prepare_documents
        from app.legacy_adoption_export import directory_scaffold, event_documents
        from app.legacy_adoption_plan import plan_moves
        from app.legacy_adoption_execution import change_phase, confirm_plan, verify_execution

        prepare_documents(library, job)
        confirm_plan(library, job, plan["id"], "manual", acknowledged=True)
        for factory in (directory_scaffold, event_documents):
            with factory(library, job) as handle, ZipFile(handle) as files:
                files.extractall(physical)
        for move in plan_moves(library, job):
            original = source / Path(move["source"]).relative_to(source_mount)
            original.rename(writable_target(move["target"]))
        assert verify_execution(library, job, plan["id"])["state"] == "verified"
        change_phase(library, job, plan["id"], "registering", from_phases={"registration_pending"})
        from app.legacy_adoption_registration import finalize_adoption
        assert finalize_adoption.__wrapped__(library, registry, job, plan["id"])["state"] == "completed"
        assert os.statvfs(mount).f_flag & os.ST_RDONLY
    finally:
        for view in reversed(mounted):
            subprocess.run(["sudo", "-n", "umount", str(view)], check=True)



@pytest.mark.parametrize("path,code,expected,attempts", [
    ("/api/libraries", "legacy_adoption_busy", 201, 2),
    ("/api/setup/adoption", "legacy_adoption_busy", 200, 2),
    ("/api/legacy-adoption/jobs?mode=library", "legacy_adoption_busy", 201, 2),
    ("/api/legacy-adoption/jobs", "legacy_adoption_busy", 409, 2),
    ("/api/legacy-adoption/jobs", "legacy_adoption_active", 201, 1),
    ("/api/legacy-adoption/jobs", "legacy_adoption_active", 409, 1),
    ("/api/libraries/check", "legacy_adoption_busy", 200, 1),
])
def test_container_probe_retries_only_the_explicit_temporary_lock(monkeypatch, path, code, expected, attempts):
    from io import BytesIO
    import json
    import urllib.error
    import urllib.request
    from qa.release import smoke_legacy_adoption as probe

    calls = []
    waits = []

    class Response(BytesIO):
        status = expected

    class Client:
        def open(self, request, timeout):
            calls.append(request)
            if len(calls) == 1 or expected == 409:
                response_code = code if len(calls) == 1 else "legacy_adoption_inactive"
                raise urllib.error.HTTPError(
                    request.full_url, 409, "Conflict", {},
                    BytesIO(json.dumps({"code": response_code}).encode()),
                )
            return Response(b'{"created":true}')

    monkeypatch.setattr(probe.time, "sleep", waits.append)
    request = urllib.request.Request("http://127.0.0.1" + path, data=b"{}", method="POST")
    if expected == 409:
        result = json.loads(probe.open_request(Client(), request, expected=expected))
        assert result["code"] == (code if attempts == 1 else "legacy_adoption_inactive")
    elif attempts == 2:
        assert json.loads(probe.open_request(Client(), request, expected=expected)) == {"created": True}
    else:
        with pytest.raises(AssertionError, match=code):
            probe.open_request(Client(), request, expected=expected)
    assert len(calls) == attempts and waits == [0.25] * (attempts - 1)


def test_container_probe_creates_main_library_once_after_lock_release(fresh_main):
    from contextlib import ExitStack
    from io import BytesIO
    import json
    import urllib.error
    import urllib.request
    from app.legacy_adoption_mode import adoption_access
    from qa.release import smoke_legacy_adoption as probe

    _, _, registry, archive = fresh_main
    main.startup_database()
    client = TestClient(main.app, follow_redirects=False)
    responses = []

    class HTTPAdapter:
        def open(self, request, timeout):
            response = client.post(request.selector, content=request.data, headers=request.headers)
            responses.append(response.status_code)
            body = BytesIO(response.content)
            if response.status_code == 409:
                assert pending_initial_setup(registry) is None
                lock.close()
                raise urllib.error.HTTPError(request.full_url, 409, "Conflict", {}, body)
            body.status = response.status_code
            return body

    request = urllib.request.Request("http://127.0.0.1/api/libraries", method="POST",
                                     headers={"Content-Type": "application/json"}, data=json.dumps({
                                         "display_name": "Smoke", "archive_root": str(archive),
                                     }).encode())
    with ExitStack() as lock:
        lock.enter_context(adoption_access(registry))
        result = json.loads(probe.open_request(HTTPAdapter(), request, expected=201))
    assert responses == [409, 201]
    assert result["library"]["library_id"] == "main"
    assert pending_initial_setup(registry) == {"library_id": "main", "decision": "choice"}
    assert _json(client, "POST", "/api/setup/adoption", json={"decision": "skipped"}) == {"next": "/"}
    assert client.get("/").status_code == 200


@pytest.mark.parametrize(("response_format", "failure"), [
    (fmt, failure) for fmt in ("text", "json")
    for failure in (None, "startup_error", "storage", "orphan", "domain", "unknown", "timeout")
] + [("json", failure) for failure in ("response_orphan", "response_domain", "response_storage")])
def test_container_repeat_finalize_preserves_recovery_fences(monkeypatch, failure, response_format):
    from io import BytesIO
    import json
    import urllib.error
    import urllib.request
    from qa.release import smoke_legacy_adoption as probe

    recovery = {"phase": "recovery_in_progress", "scope": "workspace"}
    status = {"ready": True, "startup_error": None, "operation_health": {
        "writes_allowed": False, "issues": [recovery], "reservations": [],
    }}
    if failure == "startup_error":
        status["startup_error"] = "Technical startup failed"
    elif failure == "storage":
        status["ready"] = False
    elif failure == "orphan":
        status["operation_health"]["reservations"] = [{"live": False}]
    elif failure == "domain":
        status["operation_health"]["issues"].append({"phase": "startup-recovery", "scope": "workspace"})
    calls, waits, diagnostics = [], [], []

    class Response(BytesIO):
        status = 200

    class Client:
        def open(self, request, timeout):
            calls.append(request)
            if len(calls) == 1 or failure == "timeout":
                detail = "other_conflict" if failure == "unknown" else (
                    "operation_recovery_required: workspace writes paused; storage may remain READY; " + str(recovery)
                )
                body = {"detail": detail}
                if response_format == "json" and failure != "unknown":
                    body = {"detail": "operation_recovery_required", "storage_state": "READY",
                            "operations": {"writes_allowed": False, "issues": [recovery],
                                           "reservations": []}}
                    if failure == "response_orphan":
                        body["operations"]["reservations"] = [{"live": False}]
                    elif failure == "response_domain":
                        body["operations"]["issues"].append({"phase": "startup-recovery", "scope": "workspace"})
                    elif failure == "response_storage":
                        body["storage_state"] = "UNAVAILABLE"
                raise urllib.error.HTTPError(request.full_url, 409, "Conflict", {},
                                             BytesIO(json.dumps(body).encode()))
            return Response(b'{"state":"completed"}')

    def inspect():
        diagnostics.append(status)
        return status

    monkeypatch.setattr(probe.time, "sleep", waits.append)
    request = urllib.request.Request("http://127.0.0.1/api/legacy-adoption/jobs/one/finalize",
                                     data=b"{}", method="POST")
    if failure is None:
        assert json.loads(probe.open_request(Client(), request, expected=200,
                                             recovery_status=inspect))["state"] == "completed"
        assert len(calls) == 2 and len(diagnostics) == 1 and waits == [0.25]
    else:
        with pytest.raises(AssertionError):
            probe.open_request(Client(), request, expected=200, recovery_status=inspect)
        assert len(calls) == (121 if failure == "timeout" else 1)
        assert waits == ([0.25] * 120 if failure == "timeout" else [])
        expected_inspections = 0 if failure == "unknown" or failure.startswith("response_") else 1
        assert len(diagnostics) == (120 if failure == "timeout" else expected_inspections)


@pytest.mark.parametrize("fresh_main", [True], indirect=True, ids=["metadata-zfs"])
def test_review_metadata_stages_distinct_times_and_adopts_into_existing_draft(
    fresh_main, monkeypatch, synthetic_dataset,
):
    from hashlib import sha256
    from io import BytesIO
    from app.event_inventory import event_root_relative

    workspace, database, registry, archive = fresh_main
    source = archive.parent / "legacy-review-metadata"
    source.mkdir()
    if os.environ.get("ADOPTION_ZFS_ROOT"):
        monkeypatch.setattr("app.legacy_adoption_dataset.prove", kernel_dataset_proof)
    names = ["first.jpg", "first.raf", "first.raf.xmp", "second.jpg", "changed.jpg", "invalid.jpg", "invalid.raf"]
    originals = {name: name.encode() for name in names}
    for name, content in originals.items():
        (source / name).write_bytes(content)
    captured = {
        "first.jpg": "13:05:00", "first.raf": "13:05:00",
        "second.jpg": "14:07:00", "changed.jpg": "14:09:00",
        "invalid.jpg": "13:15:00", "invalid.raf": "13:17:00",
    }
    tag = "EXIF:ExifIFD:DateTimeOriginal"
    create = "EXIF:ExifIFD:CreateDate"

    def metadata(descriptors, _cancel):
        records = {}
        for fd in descriptors:
            name = os.pread(fd, 80, 0).decode()
            clock = captured.get(name)
            records[fd] = {tag: "2026:07:21 " + clock + "+02:00",
                           create: "2026:07:21 15:30:00+02:00"} if clock else {}
        return records

    monkeypatch.setattr(main, "NAS_SOURCE_ROOT", source)
    monkeypatch.setattr(main, "DATABASE_INITIALIZATION_ERROR", None)
    monkeypatch.setattr("app.legacy_adoption_inventory.read_bound_metadata", metadata)
    client = _onboard(fresh_main)
    _adopt(client)
    jobs = "/api/legacy-adoption/jobs"
    job = jobs + "/" + _json(client, "POST", jobs, status=201, json={"root": "nas"})["id"]
    _json(client, "POST", job + "/scan", status=202)
    assert _json(client, "GET", job)["review_count"] == 4
    day = "2026-07-21"
    event = {"name": "Afternoon", "start_date": day, "end_date": day,
             "start_time": "13:00", "end_time": "18:00", "children": [
                 {"name": "Early", "start_datetime": day + "T13:00", "end_datetime": day + "T14:00"},
             ]}
    metadata_path = job + "/review/metadata"
    rev = _json(client, "PUT", job + "/draft", json={"events": [event], "revision": 0})["revision"]
    first = _json(client, "PUT", metadata_path, json={
        "revision": rev, "family_keys": ["second"], "source": create, "individual": True,
    })
    assert first["staged"] == 1
    keys = _json(client, "GET", job + "/review/selection?metadata=true")
    assert set(keys) == {"first", "second", "invalid", "changed"}
    options = _json(client, "POST", metadata_path + "/sources", json={
        "revision": first["revision"], "family_keys": keys,
    })
    assert options["sources"][tag] == 2
    batch = _json(client, "PUT", metadata_path, json={
        "revision": first["revision"], "family_keys": keys, "source": tag,
    })
    assert batch["staged"] == 2
    assert batch["rejected"] == {"invalid": "source_unavailable", "second": "already_selected"}
    reopened = TestClient(main.app, follow_redirects=False)
    state = _json(reopened, "GET", job)
    pending = state["draft"]["metadata_review_pending"]
    assert pending["first"]["time"] == day + "T13:05:00+02:00"
    assert pending["second"]["source"] == create
    assert state["draft"].get("capture_overrides") == {} and state["review_count"] == 4
    assert _json(reopened, "GET", job + "/families?day=" + day) == []
    _json(reopened, "POST", metadata_path + "/apply", status=409, json={"revision": first["revision"]})
    (source / "changed.jpg").write_bytes(b"changed since the scan")
    applied = _json(reopened, "POST", metadata_path + "/apply", json={"revision": batch["revision"]})
    assert applied["applied"] == 2 and applied["rejected"] == {"changed": "source_changed"}
    state = _json(reopened, "GET", job)
    assert state["review_count"] == 2
    assert all((source / n).read_bytes() == originals[n] for n in originals if n != "changed.jpg")
    assert {f["family_key"] for f in _json(reopened, "GET", job + "/families?day=" + day)} == {"first","second"}
    assert _json(reopened, "GET", job + "/chronology?year=2026") == [{"period": day, "families": 2, "review": 0}]
    checked = _json(reopened, "POST", job + "/draft/check", json=state["draft"])
    assert checked["events"][0]["families"] == 2 and checked["events"][0]["files"] == 4
    plan = _json(reopened, "POST", job + "/plan", json={"revision": applied["revision"]})
    moves = _json(reopened, "GET", job + "/moves")
    parent, = plan["events"]
    child, = parent["children"]
    assert {move["relative_path"] for move in moves} == {"first.jpg", "first.raf", "first.raf.xmp", "second.jpg"}
    assert all(child["folder_name"] in move["target_path"] for move in moves if move["relative_path"].startswith("first."))
    command = {"plan_id": plan["id"]}
    _json(reopened, "POST", job + "/documents")
    _json(reopened, "POST", job + "/confirm", json={**command, "method": "manual", "acknowledged": True})
    for item in ("folders", "documents"):
        response = reopened.get(job + "/download/" + item)
        assert response.status_code == 200
        with ZipFile(BytesIO(response.content)) as package:
            package.extractall(archive)
    for move in moves:
        Path(move["source"]).rename(move["target"])
    assert _json(reopened, "POST", job + "/verify", json=command)["state"] == "verified"
    assert _json(reopened, "POST", job + "/finalize", json=command)["state"] == "completed"
    for move in moves:
        name = move["relative_path"]
        assert sha256(Path(move["target"]).read_bytes()).digest() == sha256(originals[name]).digest()
    with database_connection(database) as connection:
        rows = connection.execute("SELECT original_filename, selected_capture_source FROM files").fetchall()
        assert dict(rows) == {name: create if name == "second.jpg" else tag for name in originals
                              if name.startswith("first.") or name == "second.jpg"}
    assert (archive / event_root_relative(parent) / "event.json").is_file()


@pytest.mark.parametrize("fresh_main", ["cancel-zfs", "review-unlinked"], indirect=True, ids=["cancel-zfs", "cancel-unlinked"])
def test_cancel_review_batch_rolls_back_only_its_files_and_resumes(fresh_main, monkeypatch, synthetic_dataset, request):
    from hashlib import sha256
    from threading import Event, Thread

    from app import legacy_adoption_host as host
    from app import legacy_adoption_review as review
    from app import legacy_adoption_review_cancel as cancellation
    from app import legacy_adoption_review_progress as progress
    from tests.backend.test_legacy_adoption_host import _macos_rename

    unlinked = request.node.callspec.id == "cancel-unlinked"
    native_acl = unlinked and os.environ.get("ADOPTION_NFSV4_ROOT")
    workspace, db, _, archive = fresh_main
    source = archive.parent / "legacy-cancel-source"
    source.mkdir()
    originals = {
        "a-jpeg.jpg": b"source jpeg", "b-raw.jpg": b"family jpeg", "b-raw.raf": b"family raw",
        "b-raw.raf.xmp": b"family sidecar", "c-video.mp4": b"video" * (4 * 1024 * 1024),
        "older.jpg": b"previous copy", "z-last.jpg": b"last", "valid.jpg": b"metadata source",
    }
    for name, content in originals.items():
        (source / name).write_bytes(content)
    monkeypatch.setattr(main, "NAS_SOURCE_ROOT", source)
    monkeypatch.setattr(main, "DATABASE_INITIALIZATION_ERROR", None)
    monkeypatch.setattr("app.legacy_adoption_inventory.read_bound_metadata", lambda descriptors, _check: {
        fd: {
            "EXIF:ExifIFD:DateTimeOriginal": "2026:07:21 12:00:00",
            "EXIF:ExifIFD:CreateDate": "2026:07:22 12:00:00",
        } if os.pread(fd, 8, 0) == b"metadata" else {} for fd in descriptors
    })
    if os.environ.get("ADOPTION_ZFS_ROOT"):
        monkeypatch.setattr("app.legacy_adoption_dataset.prove", kernel_dataset_proof)
    if sys.platform == "darwin":
        monkeypatch.setattr(host, "rename_noreplace", _macos_rename)
    client = _onboard(fresh_main)
    _adopt(client)
    api = "/api/legacy-adoption"

    def new_job():
        job_id = _json(client, "POST", api + "/jobs", status=201, json={"root": "nas"})["id"]
        job = api + "/jobs/" + job_id
        _json(client, "POST", job + "/scan", status=202)
        return job_id, job

    _, old_job = new_job()
    general = review._general(resolve_library_context(fresh_main[2], "main"))
    if native_acl:
        import struct
        from app.private_storage_security import NFS4

        acl = struct.pack("!II10I", 0, 2, 0, 0x03, 1, 0x1f01ff, 1, 0, 0x43, 0, 0x1301ff, 65531)
        os.setxattr(general, NFS4[0], acl)
        with review.bound_directory(general) as descriptor:
            assert review._native_staging(descriptor)
    elif unlinked:
        monkeypatch.setattr(review, "_native_staging", lambda _fd: True)

    _json(client, "POST", old_job + "/review/batch", status=202, json={"family_keys": ["older"]})
    assert (general / "older.jpg").read_bytes() == originals["older.jpg"]
    _json(client, "DELETE", old_job)
    (general / "a-jpeg.jpg").write_bytes(b"unrelated preexisting file")
    preserved = {item.name: sha256(item.read_bytes()).hexdigest() for item in general.iterdir() if item.is_file()}
    job_id, job = new_job()
    draft = _json(client, "PUT", job + "/draft", json={"revision": 0, "events": [{
        "name": "Plan survives cancel", "start_date": "2026-07-21", "end_date": "2026-07-21",
    }]})
    staged = _json(client, "PUT", job + "/review/metadata", json={
        "revision": draft["revision"], "family_keys": ["valid"], "source": "@detected", "individual": True,
    })
    assert staged["staged"] == 1
    original_draft = _json(client, "GET", job)["draft"]
    endpoint = job + "/review/batch"
    members = ["a-jpeg", "b-raw", "c-video", "older", "z-last"]
    publish, wrote = review._publish_copy, progress.wrote

    for phase in ("before", "video", "last"):
        entered, release = Event(), Event()
        responses = []

        def stop():
            entered.set()
            assert release.wait(20)
            progress.check(force=True)

        def pause_publication(library, adoption, files, destination):
            if phase == "before" and files[0][0] == "a-jpeg.jpg":
                stop()
            publish(library, adoption, files, destination)
            if phase == "last" and files[0][0] == "z-last.jpg":
                stop()

        def pause_video(count):
            wrote(count)
            if phase == "video" and progress.transfer().family == "c-video" and not entered.is_set():
                stop()

        with monkeypatch.context() as hooks:
            hooks.setattr(review, "_publish_copy", pause_publication)
            hooks.setattr(progress, "wrote", pause_video)
            transfer = Thread(target=lambda: responses.append(client.post(endpoint, json={"family_keys": members})))
            transfer.start()
            try:
                assert entered.wait(20)
                browser = TestClient(main.app, follow_redirects=False)
                active = _json(browser, "GET", endpoint + "?details=true")
                assert active["state"] == "active" and active["running"]
                assert active["copied"] == {"before": 0, "video": 2, "last": 4}[phase]
                assert active["active"]["family_key"] == {"before": "a-jpeg", "video": "c-video", "last": "z-last"}[phase]
                batch = {"batch_id": active["batch_id"]}
                _json(browser, "POST", endpoint + "/cancel", status=202, json=batch)
                _json(browser, "POST", endpoint + "/cancel", status=202, json=batch)
                assert _json(TestClient(main.app), "GET", endpoint)["state"] == "cancelling"
                _json(browser, "DELETE", job, status=409)
                if phase == "video":
                    rename = host.rename_noreplace

                    def interrupt_cleanup(src, filename, dst, target):
                        rename(src, filename, dst, target)
                        if target.startswith(".cancel-"):
                            raise RuntimeError("process lost after moving an owned inode")

                    hooks.setattr(host, "rename_noreplace", interrupt_cleanup)
                if phase == "last":
                    owned = general / "a-jpeg_1.jpg"
                    parked = general / "user-moved-original-work-copy"
                    owned.rename(parked)
                    owned.write_bytes(originals["a-jpeg.jpg"])  # same checksum, unrelated inode
            finally:
                release.set()
                transfer.join(25)
        assert [response.status_code for response in responses] == [202]
        if phase in {"video", "last"}:
            interrupted = _json(client, "GET", endpoint)
            assert interrupted["state"] == "cancelling" and not interrupted["running"]
            if phase == "last":
                assert interrupted["cancel_error"] == cancellation.UNPROVEN
                assert owned.read_bytes() == parked.read_bytes() == originals["a-jpeg.jpg"]
                owned.rename(general / "user replacement")
                parked.rename(owned)
                (general / "user replacement").unlink()
            else:
                assert any(item.name.startswith(".cancel-") for item in general.glob("*/*"))
            main.startup_database()
            assert main.DATABASE_INITIALIZATION_ERROR is None
            if main.ADOPTION_STARTUP_THREAD:
                main.ADOPTION_STARTUP_THREAD.join(timeout=15)
            _json(TestClient(main.app), "POST", endpoint + "/cancel", status=202, json=batch)

        cancelled = _json(client, "GET", endpoint + "?details=true")
        assert cancelled["state"] == "cancelled" and cancelled["copied"] == cancelled["pending"] == 0
        assert cancelled["failed"] == 0 and cancelled["active"] is None
        assert cancelled["bytes_written"] == cancelled["bytes_verified"] == 0
        _json(client, "POST", endpoint + "/cancel", status=202, json=batch)
        assert _json(client, "GET", job)["draft"] == original_draft
        assert set(_json(client, "GET", job + "/review/selection")) == set(members)
        assert {item.name: sha256(item.read_bytes()).hexdigest() for item in general.iterdir() if item.is_file()} == preserved
        assert all(not list(item.iterdir()) for item in general.iterdir() if item.is_dir())
        with database_connection(db) as connection:
            assert not connection.execute("SELECT 1 FROM legacy_adoption_review_copies WHERE job_id = ?", (job_id,)).fetchone()
            assert not connection.execute("SELECT 1 FROM legacy_adoption_flat_review_copies WHERE job_id = ?", (job_id,)).fetchone()

    completed = _json(client, "POST", endpoint, status=202, json={"family_keys": members})
    _json(client, "POST", endpoint + "/cancel", status=409, json=batch)
    _json(client, "POST", endpoint + "/cancel", status=409, json={"batch_id": completed["batch_id"]})
    result = _json(client, "GET", endpoint)
    assert result["state"] == "finished" and result["copied"] == len(members)
    assert (general / "a-jpeg_1.jpg").read_bytes() == originals["a-jpeg.jpg"]
    assert {item.name: sha256(item.read_bytes()).hexdigest() for item in source.iterdir()} == {
        name: sha256(content).hexdigest() for name, content in originals.items()
    }
    assert not list(archive.iterdir())


@pytest.mark.parametrize("fresh_main", [True], indirect=True, ids=["year-boundary"])
@pytest.mark.parametrize("execution", ["manual", "script"])
def test_repeated_camera_names_survive_cross_year_adoption_and_archive_lifecycle(
    fresh_main, monkeypatch, synthetic_dataset, execution,
):
    from hashlib import sha256
    from io import BytesIO
    import json

    from app.archive_change_assistant import build_archive_change_assistant
    from app.archive_release_stock import verify_archive_release_copies, verify_archive_release_removal
    from app.archive_transfer import verify_event_archive
    from app.event_change_apply import confirm_event_change, verify_event_change
    from app.event_change_request import get_event_change_files, propose_archived_event_deletion, propose_event_change
    from app.event_document import build_event_document_from_db
    from app.event_inventory import event_root_relative
    from app.metadata import family_member_ending
    from app.workspace_layout import backup_root, shared_work_root

    workspace, database, registry, archive = fresh_main
    source = archive.parent / "legacy-source"
    from app import legacy_adoption_host as host, legacy_adoption_package as package
    from tests.backend.test_legacy_adoption_host import _macos_rename

    appdata = database.parent / "script-appdata"
    appdata.mkdir()
    monkeypatch.setattr(package, "appdata_root", lambda: appdata)
    if sys.platform == "darwin":
        monkeypatch.setattr(host, "mount_id", lambda _fd: 1)
        monkeypatch.setattr(host, "rename_noreplace", _macos_rename)
    if os.environ.get("ADOPTION_ZFS_ROOT"):
        monkeypatch.setattr("app.legacy_adoption_dataset.prove", kernel_dataset_proof)
    monkeypatch.setattr(main, "NAS_SOURCE_ROOT", source)
    monkeypatch.setattr(
        "app.legacy_adoption_inventory.read_bound_metadata",
        lambda descriptors, _cancel: {
            fd: {"EXIF:ExifIFD:DateTimeOriginal": os.pread(fd, 19, 0).decode(),
                 "EXIF:IFD0:Make": "FUJIFILM", "EXIF:IFD0:Model": "X-T5",
                 "EXIF:ExifIFD:ImageUniqueID": sha256(os.pread(fd, 19, 0)).hexdigest()[:32]}
            for fd in descriptors
        },
    )
    locations = {".RAF": "RAW", ".JPG": "JPEG", ".dng": "DNG", ".RAF.xmp": "Sidecar"}
    extensions = tuple(locations)
    source_data = {}

    def photos(folder, date_time, stem="DSCF0763"):
        for extension, kind in locations.items():
            name = stem + "-renamed" if extension == ".JPG" else stem
            relative = f"{folder}/{kind}/{name}{extension}"
            (source / relative).parent.mkdir(parents=True)
            content = (date_time + " " + relative).encode()
            (source / relative).write_bytes(content)
            source_data[relative] = content

    def adopt(draft, *, later=False):
        api = "/api/legacy-adoption/jobs"
        job_id = _json(client, "POST", api + ("?mode=library" if later else ""), status=201, json={"root": "nas"})["id"]
        job = api + "/" + job_id
        _json(client, "POST", job + "/scan", status=202)
        preview = _json(client, "POST", job + "/draft/structure", json=draft)
        saved = _json(client, "PUT", job + "/draft", json={**draft, "revision": 0})
        plan = _json(client, "POST", job + "/plan",
                     json={"revision": saved["revision"], "filename_method": execution})
        moves = _json(client, "GET", job + "/moves")
        directories = set(_json(client, "GET", job + "/directories"))
        assert set(preview["directories"]) <= directories
        assert all(str(Path(move["target_path"]).parent) in directories for move in moves)
        _json(client, "POST", job + "/documents")
        command = {"plan_id": plan["id"]}
        renamed = _json(client, "GET", job + "/moves?renamed=true")
        assert [row["relative_path"] for row in renamed] == [
            row["relative_path"] for row in moves if Path(row["source"]).name != Path(row["target"]).name
        ]
        if execution == "manual":
            _json(client, "POST", job + "/confirm", json={**command, "acknowledged": True, "method": "manual"})
            result = client.get(job + "/download/manual-setup")
            assert result.status_code == 200, result.text
            with ZipFile(BytesIO(result.content)) as bundle:
                bundle.extractall(archive)
            for move in moves:
                assert not Path(move["target"]).exists()
                if move in renamed and not later and move["relative_path"].endswith(".JPG"):
                    observed = Path(move["target"]).with_name(Path(move["source"]).stem + " copy.JPG")
                    Path(move["source"]).rename(observed)
                    work = _json(client, "GET", job + "/manual-work?check=true")
                    [hint] = [item for step in work["steps"] for item in step["items"] if "observed_archive_path" in item]
                    assert not work["ready"]
                    assert hint["observed_archive_path"] == str(observed.relative_to(archive))
                    assert hint["expected_archive_path"] == move["target_path"]
                    assert _json(client, "POST", job + "/verify", json=command)["execution"]["phase"] == "repair"
                    observed.rename(move["target"])
                else:
                    Path(move["source"]).rename(move["target"])
        else:
            probe = _json(client, "POST", job + "/script/probe", json={
                **command, "appdata": str(appdata), "source": str(source), "archive": str(archive),
            })
            package_path = Path(probe["host"]["package"])
            device, inode = host.inode(package_path.stat())
            options = ["--package", str(package_path), "--source", str(source), "--archive", str(archive),
                       "--package-device", str(device), "--package-inode", str(inode)]
            assert host.main(["probe", *options, "--sha256", probe["sha256"]]) == 0
            _json(client, "POST", job + "/confirm", json={
                **command, "acknowledged": True, "method": "script", "probe_sha256": probe["sha256"],
            })
            _json(client, "POST", job + "/script/release", json=command)
            released = json.loads((package_path / "permission.json").read_text())
            manifest = json.loads((package_path / "manifest.json").read_text())
            assert {(row["source"], row["target"], row["sha256"]) for row in manifest["moves"]} == {
                (row["relative_path"], row["target_path"], row["sha256"]) for row in moves
            }
            assert host.main(["apply", *options, "--sha256", released["manifest"]]) == 0
        assert _json(client, "POST", job + "/verify", json=command)["state"] == "verified"
        assert _json(client, "POST", job + "/finalize", json=command)["state"] == "completed"
        return plan, {move["relative_path"]: move["target_path"] for move in moves}

    photos("2025/first", "2025:07:01 12:00:00")
    photos("2026/second", "2026:01:01 10:00:00")
    client = _onboard(fresh_main)
    _adopt(client)
    plan, paths = adopt({"events": [{
        "name": "Cross-year", "start_date": "2025-07-01", "end_date": "2026-01-01",
        "folder_layout": {"input_path": "All/JPG", "layout": {"version": 2, "nodes": [
            {"id": "all", "name": "All", "children": [{"id": "jpg", "name": "JPG"}]},
            {"id": "export", "name": "Export", "role": "export"},
        ]}},
    }]})
    [event] = plan["events"]
    event_id, anchor = event["id"], catalogue_job_id(plan)
    root = archive / event_root_relative(event)
    assert root.parent.name == "2025"
    stems = ("20250701_120000_Fuji-X-T5", "20260101_100000_Fuji-X-T5") if execution == "script" else (
        "DSCF0763", "DSCF0763_Adopted_001",
    )
    assert set(paths.values()) == {
        str((root / "All" / "JPG" / (stem + extension)).relative_to(archive))
        for stem in stems for extension in extensions
    }
    original = {path: (archive / path).read_bytes() for path in paths.values()}
    assert original == {target: source_data[relative] for relative, target in paths.items()}

    # Both execution methods see a complete, renamed family from the previous adoption.
    # The different captures sharing its original camera name still get distinct targets.
    copied = source / "already-archived"
    copied.mkdir()
    duplicated = {copied / ("renamed" + family_member_ending(relative)): data
                  for relative, data in source_data.items() if relative.startswith("2025/first/")}
    for path, data in duplicated.items():
        path.write_bytes(data)
    photos("extension", "2026:01:01 11:00:00", stem="dscf0763")
    assert _json(client, "GET", "/api/legacy-adoption/eligibility") == {"eligible": True, "blockers": []}
    extension, new_paths = adopt({"events": [{"existing_id": event_id}]}, later=True)
    assert extension["events"][0]["id"] == event_id
    assert extension["inventory_duplicates"] == len(extensions)
    assert {path: path.read_bytes() for path in duplicated} == duplicated
    assert {Path(target).name for target in new_paths.values()} == {
        ("20260101_110000_Fuji-X-T5" if execution == "script" else "dscf0763_Adopted_002") + suffix
        for suffix in extensions
    }
    paths.update(new_paths)
    assert all((archive / path).read_bytes() == data for path, data in original.items())
    assert sorted((p.name for p in root.iterdir())) == ["All", "Export", "event.json"]

    def check_catalogue(folder):
        with database_connection(database) as connection:
            files = event_file_rows(connection, event_id)
            saved_period = connection.execute(
                "SELECT start_datetime, end_datetime FROM events WHERE id=?", (event_id,),
            ).fetchone()
        assert tuple(saved_period) == ("2025-07-01T00:00:00", "2026-01-01T23:59:59")
        assert len({row["family_id"] for row in files}) == 3
        names = {Path(target).name: source_data[relative] for relative, target in paths.items()}
        assert len(files) == len(names) == 3 * len(extensions)
        for row in files:
            path = archive / row["current_relative_path"]
            assert row["sha256_current"] == sha256(path.read_bytes()).hexdigest()
            assert path.read_bytes() == names[path.name]
            assert path.parent == folder / "All" / "JPG"
        document = json.loads((folder / "event.json").read_text())
        saved = build_event_document_from_db(database, workspace, anchor, event_id, include_archived=True)
        for key in ("folder_layout", "structure"):
            assert document[key] == saved[key], key
        def file_proofs(payload):
            return {(file["relative_path"], file["sha256"], file["size_bytes"]) for file in payload["files"]}
        assert file_proofs(document) == file_proofs(saved)
        for key in ("id", "name", "folder_name", "start_datetime", "end_datetime", "revision"):
            assert document["event"][key] == saved["event"][key], key
        return files

    files = check_catalogue(root)
    verified = verify_event_archive(database, archive, anchor, event_id, workspace_path=workspace)
    assert verified["verified"], verified
    renamed = root.with_name("2025-07-01 - Renamed")
    preview = {
        "event_kind": "event", "event_name": "Renamed", "parent_folder": renamed.name,
        "child_folder": "", "uses_time_range": False, "preserve_day_folders": False,
        "start_date": "2025-07-01", "end_date": "2026-01-01", "start_time": "00:00", "end_time": "23:59",
        "selected_day_keys": ["2025-07-01", "2026-01-01"],
        "selected_family_ids": sorted({row["family_id"] for row in files}),
        "_folder_layout_explicit": True, "folder_layout": event["folder_layout"],
    }
    change = propose_event_change(database, anchor, event_id, preview, event_name="Renamed",
                                  archive_root=archive, workspace_path=workspace)["change_request_id"]
    confirm_event_change(database, change, archive, workspace)
    assistant = build_archive_change_assistant(database, archive, workspace, change, scan_live=True)
    assert [item["kind"] for item in assistant["operations"]] == ["rename_archive_folder", "replace_event_document"]
    root.rename(renamed)
    document_source = assistant["operations"][1]["source"].split("/", 1)[1]
    shutil.copyfile(shared_work_root(workspace) / document_source, renamed / "event.json")
    change_check = verify_event_change(database, change, archive, workspace)
    assert change_check["complete"], change_check
    _json(client, "POST", f"/api/change-requests/{change}/archive")
    check_catalogue(renamed)

    deletion = propose_archived_event_deletion(database, anchor, event_id, archive_root=archive)["change_request_id"]
    confirm_event_change(database, deletion, archive, workspace)
    copies = [row for row in get_event_change_files(database, deletion) if row.get("workspace_release_path")]
    assert len(copies) == len(files)
    for row in copies:
        released = backup_root(workspace) / row["workspace_release_path"]
        released.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(archive / row["old_path"], released)
    assert verify_archive_release_copies(database, archive, workspace, deletion)["complete"]
    shutil.rmtree(renamed)
    assert verify_archive_release_removal(database, archive, workspace, deletion)["complete"]
    assert verify_event_change(database, deletion, archive, workspace)["complete"]
    _json(client, "POST", f"/api/change-requests/{deletion}/archive")
    with database_connection(database) as connection:
        assert connection.execute("SELECT 1 FROM events WHERE id=?", (event_id,)).fetchone() is None
        for row in files:
            released = connection.execute(
                "SELECT current_root_kind, current_relative_path FROM files WHERE id=?", (row["id"],),
            ).fetchone()
            assert released["current_root_kind"] == "shared_workspace"
            assert sha256((backup_root(workspace) / released["current_relative_path"]).read_bytes()).hexdigest() == row["sha256_current"]
    summary = _json(client, "GET", "/api/workspace/summary?jobs=&physical_refresh=false")
    assert summary["statistics"]["family_count"] == 3
    assert summary["statistics"]["file_count"] == 3 * len(extensions)

    # Reuse all three released families via the normal Workspace sort and archive flow.
    from app.sort_apply import CONFIRMATION_PHRASE, execute_sort_run, prepare_sort_run
    from app.sort_plan import build_event_sort_plan
    from app.ssd_release import finalize_manually_moved_event_if_verified

    refiling = _json(client, "POST", f"/api/jobs/{anchor}/events", json={
        "event_kind": "event", "event_name": "Refiled", "start_date": "2025-07-01", "end_date": "2026-01-01",
        "selected_day_keys": ["2025-07-01", "2026-01-01"],
        "selected_family_ids": sorted({row["family_id"] for row in files}),
        "folder_layout": event["folder_layout"],
    })["parent_event"]
    new_event, new_job = refiling["id"], refiling["job_id"]
    library = resolve_library_context(registry, "main")
    compat = main.compatibility_workspace_root(library)
    sorting = build_event_sort_plan(database, new_job, new_event, compat, verify_sha256=True)
    assert sorting["summary"]["ready"], sorting["blockers"]
    run = prepare_sort_run(database, new_job, new_event, compat,
                           expected_plan_token=sorting["plan_token"], confirmation_phrase=CONFIRMATION_PHRASE)
    execute_sort_run(database, run["id"], compat)
    relative = event_root_relative(refiling)
    staged = shared_work_root(compat) / relative
    shutil.copytree(staged, archive / relative)
    shutil.rmtree(staged)
    proof = verify_event_archive(database, archive, new_job, new_event, workspace_path=compat)
    assert proof["verified"], proof
    finalized = finalize_manually_moved_event_if_verified(database, compat, archive, new_job, new_event, proof)
    assert finalized["manual_archive_finalized"]
    with database_connection(database) as connection:
        refiled = event_file_rows(connection, new_event)
    def links(rows):
        return {(row["id"], row["family_id"], row["sha256_current"]) for row in rows}
    assert links(refiled) == links(files)
    assert {(archive / row["current_relative_path"]).name for row in refiled} == {
        Path(target).name for target in paths.values()
    }


@pytest.mark.parametrize("fresh_main", [True], indirect=True, ids=["native"])
@pytest.mark.parametrize("finish", ["register", "restore", "restore-unstarted"])
def test_manual_adoption_steps_follow_smb_changes_and_require_verification(
    fresh_main, monkeypatch, synthetic_dataset, finish,
):
    from io import BytesIO
    from time import sleep

    _, database, _, archive = fresh_main
    source = archive.parent / "legacy-source"
    for directory in ("first", "second"):
        (source / directory).mkdir(parents=True)
    if os.environ.get("ADOPTION_ZFS_ROOT"):
        monkeypatch.setattr("app.legacy_adoption_dataset.prove", kernel_dataset_proof)
    monkeypatch.setattr(main, "NAS_SOURCE_ROOT", source)
    monkeypatch.setattr("app.legacy_adoption_inventory.read_bound_metadata", lambda descriptors, _cancel: {
        fd: {"EXIF:ExifIFD:DateTimeOriginal": "2026:01:01 12:30:00",
             "EXIF:IFD0:Make": "Synthetic", "EXIF:IFD0:Model": "Camera",
             "EXIF:ExifIFD:ImageUniqueID": "00112233445566778899aabbccddeeff"
             if os.pread(fd, 6, 0) == b"camera" else ""} for fd in descriptors
    })
    originals = {"first/one.jpg": b"camera JPEG", "first/one.raf": b"camera RAW",
                 "first/one.raf.xmp": b"camera XMP", "second/one.dng": b"camera DNG",
                 "second/two.jpg": b"second photo"}
    first_paths = tuple(path for path in originals if path.startswith("first/"))
    second_paths = tuple(path for path in originals if path.startswith("second/"))
    for path, content in originals.items():
        (source / path).write_bytes(content)

    client = _onboard(fresh_main)
    _adopt(client)
    root = "/api/legacy-adoption/jobs"
    job_id = _json(client, "POST", root, status=201, json={"root": "nas"})["id"]
    job = f"{root}/{job_id}"
    _json(client, "POST", job + "/scan", status=202)
    draft = {"events": [{"name": "SMB test", "start_date": "2026-01-01", "end_date": "2026-01-01"}]}
    saved = _json(client, "PUT", job + "/draft", json={**draft, "revision": 0})
    plan = _json(client, "POST", job + "/plan", json={"revision": saved["revision"]})
    command = {"plan_id": plan["id"]}
    _json(client, "POST", job + "/documents")
    _json(client, "GET", job + "/manual-work", status=409)
    _json(client, "POST", job + "/confirm", json={**command, "method": "manual", "acknowledged": True})

    def work(check=True):
        return _json(client, "GET", job + "/manual-work" + ("?check=true" if check else ""))

    def extract(item, destination):
        download = client.get(job + "/download/" + item)
        assert download.status_code == 200, download.text
        with ZipFile(BytesIO(download.content)) as bundle:
            bundle.extractall(destination)
            return bundle.namelist()

    first = work(False)
    assert first["checked"] is False and first["ready"] is False
    assert [step["kind"] for step in first["steps"]] == ["prepare", "move", "move"]
    assert all(step["state"] == "unchecked" for step in first["steps"])
    prepared, first_files, second_files = work()["steps"]
    assert prepared["state"] == first_files["state"] == second_files["state"] == "pending"
    assert first_files["from"] == "first" and second_files["from"] == "second"
    assert {item["from"] for item in first_files["items"]} == {Path(path).name for path in first_paths}

    if finish == "restore-unstarted":
        assert _json(client, "POST", job + "/rollback/start", json=command)["execution"]["phase"] == "rolling_back"
        assert work()["ready"]
        assert _json(client, "POST", job + "/rollback/check", json=command)["execution"]["phase"] == "rolled_back"
        assert {path: (source / path).read_bytes() for path in originals} == originals
        assert not list(archive.iterdir())
        return

    paths = extract("manual-setup", archive)
    [event_document] = [path for path in paths if path.endswith("/event.json")]
    assert any(path.endswith("/") for path in paths)
    assert work()["steps"][0]["state"] == "done"

    moves = {row["relative_path"]: Path(row["target"]) for row in _json(client, "GET", job + "/moves")}
    for path in first_paths:
        (source / path).rename(moves[path])
    states = work()
    assert not states["ready"]
    assert [step["state"] for step in states["steps"]] == ["done", "done", "pending"]

    # An actual duplicate at the old location must never get a green badge.
    (source / "first/one.jpg").write_bytes(originals["first/one.jpg"])
    assert work()["steps"][1]["state"] == "attention"
    (source / "first/one.jpg").unlink()

    assert main.DATABASE_INITIALIZATION_ERROR is None
    main.startup_database()
    client = TestClient(main.app, follow_redirects=False)
    assert work()["steps"][1]["state"] == "done"
    assert client.get(f"/legacy-adoption?job={job_id}&library=main&step=execute").status_code == 200

    if finish == "register":
        early = _json(client, "POST", job + "/finalize", json=command)
        assert early["execution"]["phase"] == "repair"
        [event] = plan["events"]
        with database_connection(database) as connection:
            assert event_file_rows(connection, event["id"]) == []
        for path in second_paths:
            (source / path).rename(moves[path])
        assert work()["ready"]
        assert _json(client, "POST", job + "/finalize", json=command)["state"] == "completed"
        with database_connection(database) as connection:
            files = event_file_rows(connection, event["id"])
        assert len(files) == len(originals)
        assert len({file["family_id"] for file in files}) == 2
        assert all(file["current_root_kind"] == "camera_archive" for file in files)
        assert {path: target.read_bytes() for path, target in moves.items()} == originals

        # A later adoption replaces an existing event document only with the
        # prepared version. Reversal must recover the original document bytes.
        original_document = (archive / event_document).read_bytes()
        extra = source / "first/later.raf"
        extra.write_bytes(b"unmoved additional photo")
        # The completed HTTP request may still be releasing its shared
        # adoption lock. Retry only the middleware's explicit transient reply.
        for attempt in range(21):
            later_start = client.post(root + "?mode=library", json={"root": "nas"},
                                      headers={"X-Bibliothekar-Library": "main"})
            if (later_start.status_code != 409 or later_start.json().get("code") != "legacy_adoption_busy"
                    or attempt == 20):
                break
            sleep(0.25)
        assert later_start.status_code == 201, later_start.text
        later_id = later_start.json()["id"]
        job = f"{root}/{later_id}"
        _json(client, "POST", job + "/scan", status=202)
        later = _json(client, "PUT", job + "/draft", json={"revision": 0, "events": [{"existing_id": event["id"]}]})
        extension = _json(client, "POST", job + "/plan", json={"revision": later["revision"]})
        command = {"plan_id": extension["id"]}
        _json(client, "POST", job + "/documents")
        _json(client, "POST", job + "/confirm", json={**command, "method": "manual", "acknowledged": True})
        extract("manual-setup", archive)
        assert (archive / event_document).read_bytes() != original_document
        _json(client, "POST", job + "/rollback/start", json=command)
        restore = next(step for step in work()["steps"] if step["kind"] == "restore_documents")
        assert restore["items"] == [{"path": event_document, "state": "pending", "operation": "restore"}]
        _json(client, "POST", job + "/rollback/check", status=409, json=command)
        extract("original-documents", archive)
        assert work()["ready"]
        _json(client, "POST", job + "/rollback/check", json=command)
        assert extra.read_bytes() == b"unmoved additional photo"
        assert (archive / event_document).read_bytes() == original_document
        assert {path: target.read_bytes() for path, target in moves.items()} == originals
        return

    (source / "first").rmdir()
    _json(client, "POST", job + "/rollback/start", json=command)
    reversal = work()
    assert reversal["reverse"] and not reversal["ready"]
    assert [step["state"] for step in reversal["steps"][:3]] == ["pending", "pending", "done"]
    assert reversal["steps"][1]["to"] == "first"
    assert "first/" in extract("original-folders", source)
    for path in first_paths:
        moves[path].rename(source / path)
    assert [step["state"] for step in work()["steps"][:4]] == ["done", "done", "done", "pending"]
    (archive / event_document).unlink()
    guard = moves["first/one.jpg"].parent / "unrelated.dat"
    guard.write_bytes(b"must stay")
    cleanup = work()["steps"][-1]
    assert cleanup["kind"] == "remove_directories"
    assert not any(item["state"] == "pending" and (archive / item["path"]) == guard.parent for item in cleanup["items"])
    _json(client, "POST", job + "/rollback/check", status=409, json=command)
    assert guard.read_bytes() == b"must stay"
    # The synthetic external owner moves the unrelated file elsewhere.
    guard.rename(archive / "unrelated.dat")
    # Remove only currently empty, planned directories, from the leaves up.
    for _ in range(6):
        cleanup = work()["steps"][-1]
        if cleanup["state"] == "done":
            break
        for item in cleanup["items"]:
            if item["state"] == "pending":
                (archive / item["path"]).rmdir()
    assert work()["ready"]
    assert _json(client, "POST", job + "/rollback/check", json=command)["execution"]["phase"] == "rolled_back"
    assert {path: (source / path).read_bytes() for path in originals} == originals
    assert (archive / "unrelated.dat").read_bytes() == b"must stay"
    with database_connection(database) as connection:
        assert connection.execute("SELECT count(*) FROM events").fetchone()[0] == 0


@pytest.mark.parametrize("fresh_main", [True], indirect=True, ids=["native-zfs"])
def test_regular_import_recognizes_adopted_file_family_before_any_regular_import(
    fresh_main, monkeypatch, synthetic_dataset,
):
    from hashlib import sha256
    from io import BytesIO
    import subprocess

    from PIL import Image
    from app.database import claim_next_job, get_job, list_imported_media_origins
    from app.source_reimport import retained_origins

    workspace, database, registry, archive = fresh_main
    original = archive.parent / "old-collection"
    original.mkdir()
    legacy = original / "DSCF0763.JPG"
    Image.new("RGB", (8, 8), "red").save(legacy)
    subprocess.run(["exiftool", "-overwrite_original", "-DateTimeOriginal=2026:07:19 17:11:37",
                    "-SubSecTimeOriginal=100", "-Make=FUJIFILM", "-Model=X-E5", str(legacy)],
                   check=True, capture_output=True)
    raw = legacy.with_suffix(".RAF")
    raw.write_bytes(b"synthetic Fujifilm RAW paired with JPEG")
    sidecar = legacy.with_suffix(".RAF.xmp")
    sidecar.write_bytes(b"synthetic matching sidecar")
    contents = {path.name: path.read_bytes() for path in (legacy, raw, sidecar)}
    monkeypatch.setattr(main, "NAS_SOURCE_ROOT", original)
    monkeypatch.setattr("app.legacy_adoption_inventory.read_bound_metadata", lambda descriptors, _cancel: {
        fd: {"EXIF:ExifIFD:DateTimeOriginal": "2026:07:19 17:11:37",
             "EXIF:ExifIFD:SubSecTimeOriginal": "100"} for fd in descriptors
    })
    if os.environ.get("ADOPTION_ZFS_ROOT"):
        monkeypatch.setattr("app.legacy_adoption_dataset.prove", kernel_dataset_proof)

    client = _onboard(fresh_main)
    _adopt(client)
    route = "/api/legacy-adoption/jobs"
    job = route + "/" + _json(client, "POST", route, status=201, json={"root": "nas"})["id"]
    _json(client, "POST", job + "/scan", status=202)
    draft = {"events": [{"name": "Adopted", "start_date": "2026-07-19", "end_date": "2026-07-19"}]}
    revision = _json(client, "PUT", job + "/draft", json={**draft, "revision": 0})["revision"]
    plan = _json(client, "POST", job + "/plan", json={"revision": revision})
    _json(client, "POST", job + "/documents")
    command = {"plan_id": plan["id"]}
    _json(client, "POST", job + "/confirm", json={**command, "method": "manual", "acknowledged": True})
    with ZipFile(BytesIO(client.get(job + "/download/manual-setup").content)) as bundle:
        bundle.extractall(archive)
    for item in _json(client, "GET", job + "/moves"):
        Path(item["source"]).rename(item["target"])
    assert _json(client, "POST", job + "/finalize", json=command)["state"] == "completed"
    if main.ADOPTION_STARTUP_THREAD:
        main.ADOPTION_STARTUP_THREAD.join(15)

    # Drive the real worker synchronously so the assertions can see both jobs.
    from types import SimpleNamespace
    monkeypatch.setattr(main, "WORKER_THREAD", SimpleNamespace(is_alive=lambda: True))
    context = resolve_library_context(registry, "main")
    source_root = original.parent / "import-source"
    duplicates = source_root / "duplicates"
    duplicates.mkdir(parents=True)
    for name, data in contents.items():
        (duplicates / name.replace("DSCF0763", "renamed-camera-original")).write_bytes(data)
    monkeypatch.setattr(main, "NAS_SOURCE_ROOT", source_root)
    main.CONFIG_PATH.write_text('{"storage": {"safety_reserve_gib": 0, "processing_buffer_percent": 0}}')
    origins = list_imported_media_origins(database)
    assert {row["job_id"] for row in origins} == {catalogue_job_id(plan)}
    assert {row["sha256"] for row in retained_origins(registry, origins)} == {
        sha256(data).hexdigest() for data in contents.values()
    }

    def process():
        queued = claim_next_job(database)
        assert queued is not None
        main.process_claimed_job(queued, library_context=context)
        completed = get_job(database, queued["id"])
        assert completed["state"] == "completed", completed
        return completed

    import_route = "/api/jobs/folder-import"
    payload = {"source_root_key": "nas", "source_relative_path": "duplicates", "source_mode": "folder"}
    _json(client, "POST", import_route, status=202, json=payload)
    assert process()["result"]["status"] == "already_backed_up"
    assert claim_next_job(database) is None

    mixed = source_root / "mixed"
    mixed.mkdir()
    for name, data in contents.items():
        (mixed / name.replace("DSCF0763", "renamed-camera-original")).write_bytes(data)
    new = mixed / "JPEG" / "DSCF0763.JPG"
    new.parent.mkdir()
    Image.new("RGB", (8, 8), "green").save(new)
    subprocess.run(["exiftool", "-overwrite_original", "-DateTimeOriginal=2026:07:19 17:11:37",
                    "-SubSecTimeOriginal=800", "-Make=FUJIFILM", "-Model=X-E5", str(new)],
                   check=True, capture_output=True)
    from app import metadata as metadata_module

    source_members = (new, mixed / "RAW/DSCF0763.RAF", mixed / "DNG/DSCF0763.dng", mixed / "RAW/DSCF0763.RAF.xmp")
    for member in source_members[1:]:
        member.parent.mkdir(exist_ok=True)
        member.write_text(member.relative_to(mixed).as_posix())
    read_fixture = metadata_module.run_exiftool
    def read_split_capture(root, **kwargs):
        records = read_fixture(root, **kwargs)
        synthetic = [{
            "SourceFile": str(root / member.relative_to(mixed)),
            "EXIF:ExifIFD:DateTimeOriginal": "2026:07:19 17:11:37",
            "EXIF:ExifIFD:SubSecTimeOriginal": "800",
            "EXIF:IFD0:Make": "FUJIFILM", "EXIF:IFD0:Model": "X-E5",
            "EXIF:ExifIFD:ImageUniqueID": "00112233445566778899aabbccddeeff",
        } for member in source_members if (root / member.relative_to(mixed)).is_file()]
        fixture_paths = {row["SourceFile"] for row in synthetic}
        return [row for row in records if row["SourceFile"] not in fixture_paths] + synthetic

    monkeypatch.setattr(metadata_module, "run_exiftool", read_split_capture)
    payload["source_relative_path"] = "mixed"
    _json(client, "POST", import_route, status=202, json=payload)
    assert process()["result"]["status"] == "import_queued"
    regular = process()
    assert regular["result"]["source"]["duplicate_file_count"] == len(contents)
    with database_connection(database) as connection:
        imported = connection.execute("SELECT * FROM files WHERE job_id=?", (regular["id"],)).fetchall()
        assert len(imported) == len(source_members)
        assert len({row["family_id"] for row in imported}) == 1
        assert {row["sha256_original"] for row in imported} == {
            sha256(path.read_bytes()).hexdigest() for path in source_members
        }
        [event] = plan["events"]
        archived = event_file_rows(connection, event["id"])
        assert len({row["family_id"] for row in archived}) == 1
        assert {row["sha256_original"] for row in archived} == {sha256(data).hexdigest() for data in contents.values()}
        assert not connection.execute("PRAGMA foreign_key_check").fetchall()
    assert {Path(row["current_relative_path"]).name: (archive / row["current_relative_path"]).read_bytes()
            for row in archived} == contents

    # The regular import's catalogue is the same physical identity index used by adoption.
    # Scan here independently of the API, since the test still has an open Workspace import.
    from app.legacy_adoption_inventory import create_job, inventory_families, scan_inventory

    comparison = archive.parent / "adoption-after-regular-import"
    comparison.mkdir()
    renamed = comparison / "renamed.JPG"
    renamed.write_bytes(new.read_bytes())
    new_same_name = comparison / new.name
    Image.new("RGB", (8, 8), "blue").save(new_same_name)
    comparison_id = create_job(context, comparison)
    scan = scan_inventory(context, comparison_id, registry_path=registry)
    assert scan["duplicate_files"] == 1
    [family] = inventory_families(context, comparison_id)
    assert family["family_key"] == new.stem
    assert renamed.read_bytes() == new.read_bytes()


@pytest.mark.parametrize("fresh_main", ["large-inventory"], indirect=True, ids=["large-inventory"])
def test_large_adoption_restores_review_and_plans_from_saved_inventory(fresh_main, monkeypatch, synthetic_dataset):
    from hashlib import sha256

    _, database, _, archive = fresh_main
    source = archive.parent / "large-source"
    source.mkdir()
    if os.environ.get("ADOPTION_ZFS_ROOT"):
        monkeypatch.setattr("app.legacy_adoption_dataset.prove", kernel_dataset_proof)
    monkeypatch.setattr(main, "NAS_SOURCE_ROOT", source)
    date_taken = "EXIF:ExifIFD:DateTimeOriginal"
    creation = "EXIF:ExifIFD:CreateDate"
    total = 10_347

    def metadata(descriptors, _cancel):
        rows = {}
        for descriptor in descriptors:
            number = int(os.pread(descriptor, 16, 0))
            rows[descriptor] = {date_taken: "2026:01:01 12:00:00"}
            if number < 26:
                rows[descriptor] = {date_taken: "2022:06:03 12:00:00", creation: "2022:06:03 14:00:00"}
            elif number >= total - 2:
                rows[descriptor].update({
                    "EXIF:IFD0:Make": "Synthetic", "EXIF:IFD0:Model": "Camera",
                    "EXIF:ExifIFD:ImageUniqueID": "00112233445566778899aabbccddeeff",
                })
        return rows

    monkeypatch.setattr("app.legacy_adoption_inventory.read_bound_metadata", metadata)
    for start in range(0, total - 2, 300):
        folder = source / f"camera-{start:05}"
        folder.mkdir()
        for number in range(start, min(start + 300, total - 2)):
            (folder / f"DSC{number:05}.jpg").write_bytes(str(number).encode())
    for folder, extra in (("RAW", "DNG"), ("JPEG", "JPG")):
        (source / folder).mkdir()
        number = total - (2 if extra == "DNG" else 1)
        (source / folder / f"split.{extra}").write_bytes(str(number).encode())

    client = _onboard(fresh_main)
    _adopt(client)
    root = "/api/legacy-adoption/jobs"
    job = root + "/" + _json(client, "POST", root, status=201, json={"root": "nas"})["id"]
    _json(client, "POST", job + "/scan", status=202)
    state = _json(client, "GET", job)
    assert (state["files"], state["families"], state["review_count"], state["errors"]) == (total, total - 1, 26, 0)
    review = _json(client, "GET", job + "/review")
    assert all("conflicting_capture_time" in row["reasons"] for row in review)
    selected = _json(client, "GET", job + "/review/selection?metadata=true")
    assert selected == [row["family_key"] for row in review] and len(selected) == 26
    sources = _json(client, "POST", job + "/review/metadata/sources",
                    json={"revision": state["draft_revision"], "family_keys": selected})
    assert sources["sources"][date_taken] == sources["sources"][creation] == 26
    revision = state["draft_revision"]
    for keys, tag in ((selected[:1], creation), (selected[1:], date_taken)):
        staged = _json(client, "PUT", job + "/review/metadata", json={
            "revision": revision, "family_keys": keys, "source": tag,
        })
        assert staged["staged"] == len(keys)
        revision = staged["revision"]

    # Recreate startup state and the client while the choices are still pending.
    main.startup_database()
    client = TestClient(main.app, follow_redirects=False)
    resumed = _json(client, "GET", job)
    assert resumed["draft_revision"] == revision
    assert set(resumed["draft"]["metadata_review_pending"]) == set(selected)
    applied = _json(client, "POST", job + "/review/metadata/apply", json={"revision": revision})
    assert applied["applied"] == 26 and applied["rejected"] == {}
    _json(client, "POST", job + "/review/metadata/apply", json={"revision": revision}, status=409)
    state = _json(client, "GET", job)
    assert state["draft"]["metadata_review_result"] == {"applied": 26, "remaining": 0}
    assert _json(client, "GET", job + "/review") == []
    years = _json(client, "GET", job + "/chronology")
    assert years == [{"period": "2022", "families": 26, "review": 0},
                     {"period": "2026", "families": total - 27, "review": 0}]

    day = "2026-01-01"
    proposal = {"events": [{"name": "Large event", "start_date": day, "end_date": day}],
                "capture_overrides": state["draft"]["capture_overrides"]}
    preview = _json(client, "POST", job + "/draft/check", json=proposal)
    assert preview["valid"] and preview["events"][0]["families"] == total - 27
    assert preview["events"][0]["files"] == total - 26
    saved = _json(client, "PUT", job + "/draft", json={**proposal, "revision": applied["revision"]})
    assert _json(client, "GET", job)["draft_revision"] == saved["revision"]
    [day_preview] = _json(client, "GET", job + "/chronology?year=2026")
    assert day_preview["families"] == total - 27
    first_page = _json(client, "GET", job + "/families?day=" + day)
    assert len(first_page) == 60
    assert not list(archive.iterdir())
    assert sum(1 for _ in source.rglob("*.jpg")) == total - 2
    for path in source.rglob("*.jpg"):
        assert path.read_bytes() == str(int(path.stem[3:])).encode()
    assert (source / "RAW" / "split.DNG").read_bytes() == str(total - 2).encode()
    assert (source / "JPEG" / "split.JPG").read_bytes() == str(total - 1).encode()
    with database_connection(database) as connection:
        assert not connection.execute("PRAGMA foreign_key_check").fetchall()
        assert connection.execute("SELECT count(*) FROM events").fetchone()[0] == 0
        split = connection.execute(
            "SELECT relative_path, family_key, sha256 FROM legacy_adoption_inventory WHERE relative_path LIKE '%/split.%'",
        ).fetchall()
        assert {row["family_key"] for row in split} == {"RAW/split"}
        assert {row["relative_path"]: row["sha256"] for row in split} == {
            "RAW/split.DNG": sha256(str(total - 2).encode()).hexdigest(),
            "JPEG/split.JPG": sha256(str(total - 1).encode()).hexdigest(),
        }
