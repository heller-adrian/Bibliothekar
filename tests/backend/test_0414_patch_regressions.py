from pathlib import Path


def test_0414_planned_save_uses_fast_post_write_refresh_only():
    main = Path("app/main.py").read_text(encoding="utf-8")
    workspace = Path("app/workspace_ui.py").read_text(encoding="utf-8")

    assert "physical_refresh: bool = True" in main
    assert "must_check = physical_refresh or view_cache.needs_first_physical_check(db_path)" in main
    assert "loadWorkspace({physicalRefresh=false}={})" in workspace
    assert 'physical_refresh=${physicalRefresh ? "true" : "false"}' in workspace
    assert "fastPlannedRefresh" in workspace
    assert "loadWorkspace({physicalRefresh: !fastPlannedRefresh})" in workspace


def test_0414_loading_contract_covers_requested_nearby_surfaces():
    shell = Path("app/ui_shell.py").read_text(encoding="utf-8")
    workspace = Path("app/workspace_ui.py").read_text(encoding="utf-8")
    events = Path("app/events_ui.py").read_text(encoding="utf-8")
    archive = Path("app/transfer_ui.py").read_text(encoding="utf-8")
    main = Path("app/main.py").read_text(encoding="utf-8")

    assert "@keyframes bk-spin" in shell
    assert ".bk-loading-status::before" in shell
    assert 'saveEventButton.classList.add("bk-busy")' in workspace
    assert 'statusElement.classList.add("bk-loading-status")' in workspace
    assert 'statusElement.classList.add("bk-loading-status")' in events
    assert "Archiv wird geladen …" in archive
    assert "button.classList.add('bk-busy')" in archive
    assert 'refreshButton.classList.add("bk-busy")' in main
    assert 'noticeElement.classList.add("bk-loading-status")' in main


def test_0414_settings_styles_are_component_scoped_on_import_page():
    shell = Path("app/ui_shell.py").read_text(encoding="utf-8")

    assert 'body[data-bk-area="import"] details > summary {' not in shell
    assert 'body[data-bk-area="import"] main details > summary {' in shell
    assert "#bk-settings-dialog .bk-settings-preview-case {" in shell
    assert "background:transparent !important;" in shell
    assert "min-height: 46px;" in shell


def test_0414_failed_repair_stays_open_and_explains_manual_fallback():
    shell = Path("app/ui_shell.py").read_text(encoding="utf-8")

    assert "Automatisches Rückgängigmachen fehlgeschlagen. Die Aufgabe bleibt offen." in shell
    assert "Erwarteter Sollort:" in shell
    assert "Du kannst die Datei notfalls selbst an den Sollort zurücklegen" in shell
    assert 'repairButton.textContent = "Erneut prüfen"' in shell
    assert "[data-bk-archive-review]:focus-visible" in shell
