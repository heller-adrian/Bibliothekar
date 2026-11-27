import json
import urllib.error
from io import BytesIO

import pytest

from app import main
from app.database import database_connection, get_job, initialize_database
from app.source_profile import DISABLED_MESSAGE
from tests.backend.test_0263_event_inventory import NOW


def test_catalogue_profile_rejects_removable_routes_before_network(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "SOURCE_HELPER_ENABLED", False)
    monkeypatch.setattr(main, "REMOVABLE_ROOT", tmp_path)
    monkeypatch.setattr(main, "NAS_SOURCE_ROOT", tmp_path)
    monkeypatch.setattr(main, "IMPORT_ROOT", tmp_path)
    monkeypatch.setattr(main, "DATABASE_FILE", tmp_path / "test.sqlite")
    monkeypatch.setattr(main, "_folder_import_runtime_blocker", lambda: None)
    monkeypatch.setattr(main.urllib.request, "urlopen", lambda *a, **k: pytest.fail("helper was contacted"))

    operations = [
        main.api_source_devices,
        lambda: main.api_mount_source_device({"device_path": "/dev/test"}),
        lambda: main.api_unmount_source_device({"device_path": "/dev/test"}),
        lambda: main.api_source_folders("removable"),
        lambda: main.api_source_folder_summary("removable", "card"),
        lambda: main.api_run_folder_import.__wrapped__({"source_root_key": "removable", "source_mode": "folder"}),
        lambda: main.api_run_folder_import.__wrapped__({"source_root_key": "nas", "source_mode": "drive"}),
        lambda: main.api_run_folder_import.__wrapped__({"source_root_key": "removable", "source_mode": "sd_card"}),
    ]
    for action in operations:
        with pytest.raises(main.HTTPException) as error:
            action()
        assert (error.value.status_code, error.value.detail) == (409, DISABLED_MESSAGE)

    visited = []
    monkeypatch.setattr(main, "discover_import_sources", lambda key: visited.append(key) or [])
    main.api_import_sources(force_refresh=True)
    assert visited == ["saved"]
    assert main.api_source_folders("nas")["root_key"] == "nas"
    html = main.index()
    assert 'id="bk-source-picker"' not in html
    assert 'data-source-pane="folder" hidden' not in html
    assert 'id="folder-import-button"' in html
    assert '<option value="saved">' in html


def test_enabled_gateway_forwards_operations_and_distinguishes_unreachable(monkeypatch):
    monkeypatch.setattr(main, "SOURCE_HELPER_ENABLED", True)
    calls = []

    def forward(request, **kwargs):
        calls.append((request.method, request.full_url.rsplit(":", 1)[-1].split("/", 1)[-1], request.data))
        return BytesIO(b'{"ok":true}')

    monkeypatch.setattr(main.urllib.request, "urlopen", forward)
    assert main.api_source_devices() == {"ok": True}
    assert main.api_mount_source_device({"device_path": "/dev/test"}) == {"ok": True}
    assert main.api_unmount_source_device({"device_path": "/dev/test"}) == {"ok": True}
    assert [item[:2] for item in calls] == [("GET", "devices"), ("POST", "mount"), ("POST", "unmount")]
    assert json.loads(calls[-1][2]) == {"device_path": "/dev/test"}

    def unreachable(*args, **kwargs):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(main.urllib.request, "urlopen", unreachable)
    with pytest.raises(main.HTTPException) as error:
        main.api_source_devices()
    assert error.value.status_code == 503
    assert error.value.detail != DISABLED_MESSAGE
    assert main.index().count('class="bk-source-option') == 6  # three cards and their icons


def test_catalogue_queue_preserves_removable_imports_until_reenabled(tmp_path, monkeypatch):
    db = tmp_path / "db.sqlite"
    initialize_database(db)
    monkeypatch.setattr(main, "DATABASE_FILE", db)
    monkeypatch.setattr(main, "REMOVABLE_ROOT", tmp_path / "removable")
    with database_connection(db) as connection:
        for job, root in [("A-CARD", "removable"), ("B-FOLDER", "nas")]:
            connection.execute(
                """INSERT INTO jobs(id,kind,trigger_type,state,stage,source_path,operation,
                                    result_json,created_at,updated_at)
                   VALUES (?,'archive_verification','manual','queued','queued',?,'sd_recheck',?,?,?)""",
                (job, str(tmp_path / root / "batch"), json.dumps({"source_root_key": root}), NOW, NOW),
            )
    monkeypatch.setattr(main, "SOURCE_HELPER_ENABLED", False)
    assert main._claim_profile_job(db)["id"] == "B-FOLDER"
    assert main._claim_profile_job(db) is None
    assert get_job(db, "A-CARD")["state"] == "queued"
    with pytest.raises(main.HTTPException) as error:
        main.api_sd_recheck("A-CARD")
    assert error.value.status_code == 409
    assert main.api_sd_recheck("B-FOLDER")["id"] == "B-FOLDER"
    monkeypatch.setattr(main, "SOURCE_HELPER_ENABLED", True)
    assert main._claim_profile_job(db)["id"] == "A-CARD"
