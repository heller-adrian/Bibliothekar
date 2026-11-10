from contextlib import contextmanager
import os
import sys
from pathlib import Path
from zipfile import ZipFile

import pytest
from fastapi.testclient import TestClient

from app import domain_recovery, main, operation_health
from app.database import database_connection
from app.event_access import event_file_rows
from app.event_inventory import scan_event_inventory
from app.legacy_adoption_catalogue import catalogue_job_id
from app.library_context import resolve_library_context
from tests.backend.test_f14_root_operations import fixture
from tests.backend.test_pre4_operation_separation import ready
from tests.backend.test_legacy_adoption_plan import inventory, library
from tests.backend.test_legacy_adoption_inventory import synthetic_dataset


def _json(client, method, path, *, library="second", status=200, **kwargs):
    response = client.request(method, path, headers={"X-Bibliothekar-Library": library}, **kwargs)
    assert response.status_code == status, response.text
    return response.json()


def test_wizard_and_f14_recovery_in_secondary_library(ready, tmp_path, monkeypatch, synthetic_dataset):
    from io import BytesIO
    from app import legacy_adoption_registration as registration
    from app.legacy_adoption_paths import AdoptionError

    _, workspace, registry, databases, _ = ready
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
            fd: {"EXIF:ExifIFD:DateTimeOriginal": "2026:07:21 12:00:00"} for fd in descriptors
        },
    )
    library = resolve_library_context(registry, "second")
    client = TestClient(main.app)
    wizard = client.get("/legacy-adoption?library=second")
    assert wizard.status_code == 200
    assert 'data-library="second"' in wizard.text
    api = "/api/legacy-adoption"
    assert _json(client, "GET", api + "/source")["folders"] == ["2026"]
    job_id = _json(client, "POST", api + "/jobs", status=201, json={"root":"nas"})["id"]
    job = api + "/jobs/" + job_id
    _json(client, "POST", job + "/scan", status=202)
    assert _json(client, "GET", job)["state"] == "inventoried"
    assert _json(client, "GET", api + "/jobs", library="main") == []
    assert _json(client, "GET", job, library="main", status=409)["detail"]
    draft = {"events": [{"name":"Synthetisch", "start_date":"2026-07-21", "end_date":"2026-07-21",
                         "preserve_day_folders":True}]}
    _json(client, "PUT", job + "/draft", json=draft)
    assert _json(client, "GET", job)["draft"]["events"][0]["name"] == "Synthetisch"
    plan = _json(client, "POST", job + "/plan", json=draft)
    assert plan["folder_moves"][0]["source_path"] == "2026/07/2026-07-21"
    _json(client, "POST", job + "/documents")
    for item in ("folders", "documents"):
        response = client.get(job + "/download/" + item, headers={"X-Bibliothekar-Library":"second"})
        assert response.status_code == 200, response.text
        with ZipFile(BytesIO(response.content)) as archive:
            archive.extractall(library.archive_root)
    move = _json(client, "GET", job + "/moves")[0]
    media.rename(move["target"])
    assert _json(client, "POST", job + "/verify")["state"] == "verified"

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
    assert lease["library"] == "second"
    assert not lease["live"]
    event_id = plan["events"][0]["id"]
    with database_connection(databases[1]) as connection:
        assert event_file_rows(connection, event_id) == []

    monkeypatch.setattr(registration, "source_registry_transaction", original)
    assert domain_recovery.replay(workspace, registry, database=databases[0])
    assert operation_health.inspect(workspace)["writes_allowed"]
    assert _json(client, "GET", job)["plan"]["state"] == "completed"
    assert _json(client, "POST", job + "/finalize", json={"plan_id": plan["id"]})["state"] == "completed"

    inventory = scan_event_inventory(
        databases[1], library.archive_root, catalogue_job_id(plan), event_id,
        root_kind="camera_archive",
    )
    with database_connection(databases[1]) as connection:
        [media_row] = event_file_rows(connection, event_id)
        assert media_row["current_root_kind"] == "camera_archive"
        assert media_row["sha256_original"] == move["sha256"]
    assert inventory["files"][0]["relative_path"] == move["target_path"]
    assert Path(move["target"]).read_bytes() == b"synthetic RAW bytes"


    # Open, edit and delete through the same tools used by standard events.
    import shutil
    from app.archive_change_assistant import build_archive_change_assistant
    from app.archive_release_stock import verify_archive_release_copies, verify_archive_release_removal
    from app.event_change_apply import confirm_event_change, finish_event_change, verify_event_change
    from app.event_change_request import get_event_change_files, propose_archived_event_deletion, propose_event_change
    from app.event_inventory import event_root_relative
    from app.workspace_layout import backup_root

    anchor_job = catalogue_job_id(plan)
    event = plan["events"][0]
    old_folder = library.archive_root / event_root_relative(event)
    renamed = "07-21 - Umbenannt"
    preview = {
        "event_kind": "event", "event_name": "Umbenannt", "parent_folder": renamed, "child_folder": "",
        "uses_time_range": False, "preserve_day_folders": True, "start_date": "2026-07-21",
        "end_date": "2026-07-21", "start_time": "00:00", "end_time": "23:59",
        "selected_day_keys": ["2026-07-21"], "selected_family_ids": [media_row["family_id"]],
    }
    request = propose_event_change(databases[1], anchor_job, event_id, preview, event_name="Umbenannt",
                                   archive_root=library.archive_root, workspace_path=workspace)
    change_id = request["change_request_id"]
    confirm_event_change(databases[1], change_id, library.archive_root, workspace)
    assistant = build_archive_change_assistant(databases[1], library.archive_root, workspace, change_id, scan_live=True)
    assert [item["kind"] for item in assistant["operations"]] == ["rename_archive_folder", "replace_event_document"]
    assert not verify_event_change(databases[1], change_id, library.archive_root, workspace)["complete"]
    new_folder = old_folder.with_name(renamed)
    old_folder.rename(new_folder)
    replacement = assistant["operations"][1]
    source_relative = replacement["source"].split("/", 1)[1]
    from app.workspace_layout import shared_work_root
    shutil.copyfile(shared_work_root(workspace) / source_relative, new_folder / "event.json")
    assert verify_event_change(databases[1], change_id, library.archive_root, workspace)["complete"]
    finish_event_change(databases[1], change_id, library.archive_root, workspace)
    with database_connection(databases[1]) as connection:
        assert connection.execute("SELECT name FROM events WHERE id = ?", (event_id,)).fetchone()[0] == "Umbenannt"

    deletion = propose_archived_event_deletion(databases[1], anchor_job, event_id, archive_root=library.archive_root)
    deletion_id = deletion["change_request_id"]
    confirm_event_change(databases[1], deletion_id, library.archive_root, workspace)
    release_rows = [row for row in get_event_change_files(databases[1], deletion_id)
                    if row.get("workspace_release_path")]
    assert release_rows
    for row in release_rows:
        released = backup_root(workspace) / row["workspace_release_path"]
        released.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(library.archive_root / row["old_path"], released)
    assert verify_archive_release_copies(databases[1], library.archive_root, workspace, deletion_id)["complete"]
    # The synthetic user removes the event folder only after the release copy is verified.
    shutil.rmtree(new_folder)
    assert verify_archive_release_removal(databases[1], library.archive_root, workspace, deletion_id)["complete"]
    assert verify_event_change(databases[1], deletion_id, library.archive_root, workspace)["complete"]
    finish_event_change(databases[1], deletion_id, library.archive_root, workspace)
    with database_connection(databases[1]) as connection:
        assert connection.execute("SELECT 1 FROM events WHERE id = ?", (event_id,)).fetchone() is None
        assert connection.execute("SELECT current_root_kind FROM files WHERE id = ?",
                                  (media_row["id"],)).fetchone()[0] == "shared_workspace"


@pytest.mark.skipif(
    sys.platform != "linux" or os.environ.get("GITHUB_ACTIONS") != "true",
    reason="Der echte Read-only-Bind-Mount läuft auf dem isolierten Linux-Runner.",
)
def test_adoption_reads_actual_read_only_archive(inventory):
    import errno
    import subprocess
    from dataclasses import replace

    from app.legacy_adoption_inventory import create_job, scan_inventory
    from app.legacy_adoption_plan import create_plan
    from tests.backend.test_legacy_adoption_plan import _draft

    context, source, registry = inventory
    physical = context.archive_root
    mount = physical.with_name("read-only-archive")
    mount.mkdir()
    subprocess.run(["sudo", "-n", "mount", "--bind", str(physical), str(mount)], check=True)
    try:
        subprocess.run(["sudo", "-n", "mount", "-o", "remount,bind,ro", str(mount)], check=True)
        assert os.statvfs(mount).f_flag & os.ST_RDONLY
        with pytest.raises(OSError) as denied:
            (mount / "attempt").write_bytes(b"must fail")
        assert denied.value.errno == errno.EROFS
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
        job = create_job(library, source)
        scan_inventory(library, job)
        plan = create_plan(library, registry, job, _draft())
        from app.legacy_adoption_catalogue import prepare_documents
        from app.legacy_adoption_export import directory_scaffold, event_documents
        from app.legacy_adoption_plan import plan_moves
        from app.legacy_adoption_verify import verify_media

        prepare_documents(library, job)
        for factory in (directory_scaffold, event_documents):
            with factory(library, job) as handle, ZipFile(handle) as files:
                files.extractall(physical)
        for move in plan_moves(library, job):
            Path(move["source"]).rename(writable_target(move["target"]))
        assert verify_media(library, job)["state"] == "verified"
        from app.legacy_adoption_registration import finalize_adoption
        assert finalize_adoption.__wrapped__(library, registry, job, plan["id"])["state"] == "completed"
        assert os.statvfs(mount).f_flag & os.ST_RDONLY
    finally:
        subprocess.run(["sudo", "-n", "umount", str(mount)], check=True)
