from contextlib import contextmanager
import os
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
def fresh_main(tmp_path, monkeypatch):
    case = tmp_path.resolve() / "first-install"
    workspace, private, archive = (case / name for name in ("workspace", "database", "archive"))
    for path in (workspace, private, archive):
        path.mkdir(parents=True)
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
    from app import legacy_adoption_dataset

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
    roots = _json(client, "GET", "/api/legacy-adoption/sources")
    assert roots["preferred"] == "nas"
    assert [item["key"] for item in roots["roots"]] == ["nas"]
    browse = _json(client, "GET", "/api/legacy-adoption/source?root=nas")
    assert browse["dataset"] == "pool/photos" and browse["folders"] == ["different-dataset"]
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


def test_wizard_and_f14_recovery_in_main_library(fresh_main, tmp_path, monkeypatch, synthetic_dataset):
    from io import BytesIO
    from app import legacy_adoption_registration as registration
    from app.legacy_adoption_paths import AdoptionError

    workspace, database, registry, _ = fresh_main
    source = tmp_path.resolve() / "legacy-source"
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
                         "preserve_day_folders":True}]}
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

    monkeypatch.setattr(registration, "source_registry_transaction", original)
    assert domain_recovery.replay(workspace, registry, database=database)
    assert operation_health.inspect(workspace)["writes_allowed"]
    assert pending_initial_setup(registry) is None
    assert _json(client, "GET", job, status=409)["code"] == "legacy_adoption_inactive"
    assert client.get("/workspace").status_code == 200
    assert _json(client, "POST", job + "/finalize", json={"plan_id": plan["id"]})["state"] == "completed"

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
    added = source / "extra.raf"
    added.write_bytes(b"second collection RAW bytes")
    (source / "same-photo.raf").write_bytes(b"synthetic RAW bytes")
    (source / "outside.raf").write_bytes(b"outside the saved period")
    assert _json(client, "GET", api + "/eligibility") == {"eligible": True, "blockers": []}
    assert client.get("/legacy-adoption?mode=library").status_code == 200
    second_id = _json(client, "POST", api + "/jobs?mode=library", status=201, json={"root": "nas"})["id"]
    second_job = api + "/jobs/" + second_id
    assert pending_initial_setup(registry) is None
    assert client.get("/workspace").headers["location"].endswith("job=" + second_id)
    _json(client, "POST", second_job + "/scan", status=202)
    matches = _json(client, "GET", second_job + "/events?day=2026-07-21")
    assert [item["id"] for item in matches] == [event_id]
    assert _json(client, "GET", second_job + "/events?day=2026-07-22") == []
    extension = {"events": [{"existing_id": event_id}]}
    assert _json(client, "POST", second_job + "/draft/check", json=extension)["events"][0]["families"] == 2
    saved = _json(client, "PUT", second_job + "/draft", json={**extension, "revision": 0})
    second_plan = _json(client, "POST", second_job + "/plan", json={"revision": saved["revision"]})
    assert second_plan["events"][0]["id"] == event_id and second_plan["counts"]["duplicate"] == 1
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
    assert Path(move["target"]).read_bytes() == b"synthetic RAW bytes"
    assert (source / "same-photo.raf").read_bytes() == b"synthetic RAW bytes"
    assert (source / "outside.raf").read_bytes() == b"outside the saved period"
    assert original_document.read_bytes() != previous_document
    with database_connection(database) as connection:
        extended_rows = event_file_rows(connection, event_id)
        assert {row["id"] for row in extended_rows} >= {media_row["id"]}
        assert len(extended_rows) == 2
        period = connection.execute("SELECT start_datetime, end_datetime FROM events WHERE id = ?", (event_id,)).fetchone()
        assert tuple(period) == ("2026-07-21T00:00:00", "2026-07-21T23:59:59")

    # Open, edit and delete through the same tools used by standard events.
    import shutil
    from app.archive_change_assistant import build_archive_change_assistant
    from app.archive_release_stock import verify_archive_release_copies, verify_archive_release_removal
    from app.event_change_apply import confirm_event_change, finish_event_change, verify_event_change
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
    assert verify_event_change(database, change_id, library.archive_root, workspace)["complete"]
    finish_event_change(database, change_id, library.archive_root, workspace)
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
    finish_event_change(database, deletion_id, library.archive_root, workspace)
    with database_connection(database) as connection:
        assert connection.execute("SELECT 1 FROM events WHERE id = ?", (event_id,)).fetchone() is None
        assert connection.execute("SELECT current_root_kind FROM files WHERE id = ?",
                                  (media_row["id"],)).fetchone()[0] == "shared_workspace"


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
    command = {"plan_id": plan["id"]}
    library = resolve_library_context(registry, "main")
    # Test automatic discovery against synthetic Docker metadata. The real
    # Linux/ZFS container run executes the returned shell command itself.
    from app import legacy_adoption_discover as discovery

    auto = _json(client, "POST", job + "/script/probe", json=command)
    assert auto["host"] is None and not auto["verified"]
    package_root = appdata / "legacy-adoption" / job_id
    assert {path.name for path in package_root.iterdir()} >= {"probe.json", "execution.lock", "journal.jsonl"}
    config = json.loads(shlex.split(auto["command"])[-1])
    mounts = [{"Destination": str(path), "Source": str(path), "Type": "bind"}
              for path in (appdata, source, library.archive_root)]
    monkeypatch.setattr(discovery, "load_runner", lambda *_: host)
    if sys.platform == "darwin":
        monkeypatch.setattr(host, "probe_roots", lambda *args: None)
    with pytest.raises(ValueError, match="complete host mapping"):
        discovery.main(config, [mounts[:-1]])
    assert not _json(client, "GET", job + "/script/probe")["verified"]
    discovery.main(config, [mounts])
    proved = _json(client, "GET", job + "/script/probe")
    assert proved["verified"] and proved["host"]["package"] == str(package_root)
    assert proved["dataset"] == "synthetic/test"
    assert original.read_bytes() == b"synthetic script photo"
    probe = _json(client, "POST", job + "/script/probe", json={
        **command, "appdata": str(appdata), "source": str(source), "archive": str(library.archive_root),
    })
    confirm = {**command, "method": "script", "acknowledged": True, "probe_sha256": probe["sha256"]}
    _json(client, "POST", job + "/confirm", json=confirm, status=409)

    def external(shell_command):
        subprocess.run(["/bin/sh", "-n", "-c", shell_command], check=True)
        args = shlex.split(shell_command)
        assert args[:2] == ["cd", probe["host"]["package"]]
        start = args.index("./legacy_adoption_host.py")
        return host.main(args[start + 1:])

    assert external(probe["command"]) == 0
    assert _json(client, "GET", job + "/script/probe")["verified"]
    assert _json(client, "POST", job + "/confirm", json=confirm)["execution"]["phase"] == "script_prepared"
    assert not _json(client, "GET", job + "/script").get("command")
    assert _json(client, "GET", job + "/download/documents", status=409)["detail"]
    apply = _json(client, "POST", job + "/script/release", json=command)["command"]
    _json(client, "POST", job + "/verify", json=command, status=409)
    # A reported completion is insufficient while the planned files are still at the source.
    package_root = Path(probe["host"]["package"])
    binding = json.loads((package_root / "permission.json").read_text())["manifest"]
    (package_root / "status.json").write_bytes(host.json_bytes({
        "manifest": binding, "mode": "apply", "state": "completed",
    }))
    assert _json(client, "POST", job + "/verify", json=command)["execution"]["phase"] == "repair"
    assert external(apply) == 1
    assert _json(client, "POST", job + "/script/release", json=command)["command"] == apply
    assert external(apply) == 0
    assert not original.exists()
    assert _json(client, "GET", job + "/script")["status"]["state"] == "completed"
    assert _json(client, "POST", job + "/verify", json=command)["execution"]["phase"] == "registration_pending"
    assert external(apply) == 1
    [move] = _json(client, "GET", job + "/moves")
    assert _json(client, "POST", job + "/finalize", json=command)["execution"]["phase"] == "completed"
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

    def interrupt_after_publication(src, src_name, dst, dst_name):
        rename(src, src_name, dst, dst_name)
        if src_name.startswith("legacy-"):
            raise OSError(errno.EIO, "synthetic interruption after workspace publication")

    with monkeypatch.context() as interrupted:
        interrupted.setattr(host, "rename_noreplace", interrupt_after_publication)
        _json(client, "POST", job + "/review/copy", status=409, json=command)
    assert _json(client, "GET", job + "/review")[0]["state"] == "copying"
    copied = _json(client, "POST", job + "/review/copy", json=command)
    assert copied["file_count"] == 3
    assert copied["state"] == "copied"
    assert _json(client, "POST", job + "/review/copy", json=command) == copied
    assert _json(client, "GET", job + "/review")[0]["state"] == "copied"
    assert all((source / name).read_bytes() == data for name, data in originals.items())
    draft = _json(client, "PUT", job + "/draft", json={"revision": 0, "events": [{
        "name": "Review fixture", "start_date": "2026-07-21", "end_date": "2026-07-21",
    }], "capture_overrides": {"bad": "2026-07-21T11:00:00"}})
    _json(client, "POST", job + "/plan", json={"revision": draft["revision"]})
    assert [move["relative_path"] for move in _json(client, "GET", job + "/moves")] == ["good.jpg"]
    _json(client, "DELETE", job)
    general = metadata_area_paths(area="general", workspace_root=workspace, library_id="main", create=False)["root"]
    assert not list((general / LEGACY_REVIEW_STAGING).iterdir())
    family = general / copied["target_relative"]
    assert {path.name: path.read_bytes() for path in family.iterdir()} == {
        key: data for key, data in originals.items() if key != "good.jpg"
    }
    library = resolve_library_context(registry, "main")
    monkeypatch.setattr("app.metadata.run_exiftool", lambda *_args, **_kwargs: [])
    scan = scan_metadata_area(area="general", workspace_root=workspace, library_id="main",
                              database_path=library.database_path)
    assert {item["filename"] for item in scan["files"]} == set(originals) - {"good.jpg"}


def test_review_capacity_gate_accounts_for_entire_family(monkeypatch):
    from types import SimpleNamespace
    from app.legacy_adoption_paths import AdoptionError
    from app.legacy_adoption_review import _check_capacity

    members = [("photo.raf", ".copy-0", {"size_bytes": 8192}),
               ("photo.raf.xmp", ".copy-1", {"size_bytes": 2048})]
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



@pytest.mark.parametrize("code,retries", [("legacy_adoption_busy", 1), ("legacy_adoption_active", 0)])
def test_container_probe_retries_only_the_explicit_temporary_lock(monkeypatch, code, retries):
    from io import BytesIO
    import json
    import urllib.error
    import urllib.request
    from qa.release import smoke_legacy_adoption as probe

    calls = []
    waits = []

    class Response(BytesIO):
        status = 201

    class Client:
        def open(self, request, timeout):
            calls.append(request)
            if len(calls) == 1:
                raise urllib.error.HTTPError(
                    request.full_url, 409, "Conflict", {},
                    BytesIO(json.dumps({"code": code}).encode()),
                )
            return Response(b'{"id":"one-job"}')

    monkeypatch.setattr(probe.time, "sleep", waits.append)
    request = urllib.request.Request("http://127.0.0.1/api/legacy-adoption/jobs", data=b"{}", method="POST")
    if retries:
        assert json.loads(probe.open_request(Client(), request, expected=201, retry_busy=True))["id"] == "one-job"
        assert len(calls) == 2 and waits == [0.25]
    else:
        with pytest.raises(AssertionError, match="legacy_adoption_active"):
            probe.open_request(Client(), request, expected=201, retry_busy=True)
        assert len(calls) == 1 and waits == []


@pytest.mark.parametrize("failure", [None, "startup_error", "storage", "orphan", "domain", "unknown", "timeout"])
def test_container_repeat_finalize_preserves_recovery_fences(monkeypatch, failure):
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
                raise urllib.error.HTTPError(request.full_url, 409, "Conflict", {},
                                             BytesIO(json.dumps({"detail": detail}).encode()))
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
        assert len(diagnostics) == (120 if failure == "timeout" else int(failure != "unknown"))
