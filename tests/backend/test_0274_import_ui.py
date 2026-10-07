"""0.27.4: Importquellen-UI, Laufwerksimport und Archiv-UI."""
from pathlib import Path
import json

from app import main as app_main
from app.database import initialize_database

ROOT = Path(__file__).resolve().parents[2]


def test_0274_source_modes_are_exclusive_and_sd_is_its_own_pane():
    main = (ROOT / "app" / "main.py").read_text()
    shell = (ROOT / "app" / "ui_shell.py").read_text()
    assert 'id="sd-card-status" data-source-pane="sd"' in main
    assert 'class="import-controls sd-actions" data-source-pane="sd"' in main
    assert 'id="sd-source-detail" data-source-pane="sd"' in main
    assert 'pane.hidden = pane.dataset.sourcePane !== mode' in shell
    assert 'document.body.dataset.bkSourceMode = mode' in shell
    assert 'body[data-bk-area="import"] [data-source-pane][hidden]' in shell
    assert 'display: none !important' in shell


def test_0274_external_drive_supports_full_or_folder_import():
    main = (ROOT / "app" / "main.py").read_text()
    assert 'id="device-import-button"' in main
    assert 'Komplettes Laufwerk sichern' in main
    assert 'id="device-folder-button"' in main
    assert 'Ordner auswählen' in main
    assert 'id="drive-folder-browser"' in main
    assert 'loadDriveFolderBrowser' in main
    assert 'startFolderImportSelection(' in main
    assert '"removable",\n        device.device_id' in main
    assert 'relative_path:requested' in main
    assert 'requested.startsWith(driveFolderBoundary + "/")' in main


def test_0274_external_drive_actions_require_verified_read_only_mount():
    main = (ROOT / "app" / "main.py").read_text()
    assert 'const verifiedReadOnly = Boolean(device?.mounted && device?.read_only)' in main
    assert 'deviceImportButton.disabled = !verifiedReadOnly' in main
    assert 'deviceFolderButton.disabled = !verifiedReadOnly' in main
    assert 'Bitte das externe Laufwerk zuerst ausschließlich lesend einbinden.' in main


def test_0274_disclosure_triangles_are_large_and_uniform():
    events = (ROOT / "app" / "events_ui.py").read_text()
    shell = (ROOT / "app" / "ui_shell.py").read_text()
    assert 'grid-template-columns:22px minmax(0,1fr) auto !important' in events
    assert 'width:22px;\n      font-size:19px' in events
    assert 'body[data-bk-area="import"] main details > summary::before' in shell
    assert 'font-size: 18px' in shell


def test_0274_reversal_stepper_active_state_is_visible_while_disabled():
    events = (ROOT / "app" / "events_ui.py").read_text()
    assert '.change-step:disabled' in events
    assert 'opacity:1' in events
    assert '.change-step.active .change-step-number' in events
    assert 'border:2px solid var(--accent) !important' in events



def test_0274_removable_drive_root_and_subfolder_use_same_safe_import_endpoint(
    tmp_path: Path,
    monkeypatch,
):
    db = tmp_path / "kamera.sqlite3"
    initialize_database(db)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    removable = tmp_path / "removable"
    drive = removable / "DRIVE-1"
    selected = drive / "Auswahl"
    selected.mkdir(parents=True)
    (drive / "root.jpg").write_bytes(b"root-camera-file")
    (selected / "nested.jpg").write_bytes(b"nested-camera-file")

    monkeypatch.setattr(app_main, "DATABASE_FILE", db)
    monkeypatch.setattr(app_main, "WORKSPACE_PATH", workspace)
    monkeypatch.setattr(app_main, "REMOVABLE_ROOT", removable)

    listing = app_main.api_source_folders("removable", "DRIVE-1")
    assert listing["relative_path"] == "DRIVE-1"
    assert any(item["relative_path"] == "DRIVE-1/Auswahl" for item in listing["directories"])

    whole_response = app_main.api_run_folder_import({
        "source_root_key": "removable",
        "source_relative_path": "DRIVE-1",
        "display_name": "Testlaufwerk",
    })
    whole = json.loads(whole_response.body)
    assert whole["accepted"] is True
    assert whole["job"]["source_path"] == str(drive.resolve())
    assert whole["job"]["source_device_id"] == "DRIVE-1"

    folder_response = app_main.api_run_folder_import({
        "source_root_key": "removable",
        "source_relative_path": "DRIVE-1/Auswahl",
        "display_name": "Testlaufwerk · Auswahl",
    })
    folder = json.loads(folder_response.body)
    assert folder["accepted"] is True
    assert folder["job"]["source_path"] == str(selected.resolve())
    assert folder["job"]["source_device_id"] == "DRIVE-1"



def test_0274_sd_controls_are_compact_without_changing_import_logic():
    shell = (ROOT / "app" / "ui_shell.py").read_text()
    assert 'min-height: 56px !important' in shell
    assert 'padding: 8px 12px !important' in shell
    assert 'padding: 7px 11px !important' in shell
