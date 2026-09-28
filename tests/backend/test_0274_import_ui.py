"""0.27.4: Importquellen-UI, Laufwerksimport und Archiv-UI."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_0274_source_modes_are_exclusive_and_sd_is_its_own_pane():
    main = (ROOT / "app" / "main.py").read_text()
    shell = (ROOT / "app" / "ui_shell.py").read_text()
    assert 'id="sd-card-status" data-source-pane="sd"' in main
    assert 'class="import-controls sd-actions" data-source-pane="sd"' in main
    assert 'id="sd-source-detail" data-source-pane="sd"' in main
    assert 'pane.hidden = pane.dataset.sourcePane !== mode' in shell
    assert 'document.body.dataset.bkSourceMode = mode' in shell


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
    assert 'grid-template-columns:20px minmax(0,1fr) auto !important' in events
    assert 'width:20px;\n      font-size:18px' in events
    assert 'body[data-bk-area="import"] details > summary::before' in shell
    assert 'font-size: 18px' in shell


def test_0274_reversal_stepper_active_state_is_visible_while_disabled():
    events = (ROOT / "app" / "events_ui.py").read_text()
    assert '.change-step:disabled' in events
    assert 'opacity:1' in events
    assert '.change-step.active .change-step-number' in events
    assert 'border:2px solid var(--accent) !important' in events
