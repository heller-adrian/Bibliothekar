"""0.27.2: UI-Feinschliff für den Archivänderungsworkflow."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def test_0272_archive_change_dialog_opens_before_slow_proposal():
    source = (ROOT / "app" / "events_ui.py").read_text()
    archived = source.index("if (context.archived_change_request)")
    proposal = source.index("/propose?job_id=", archived)
    open_dialog = source.index("changeRequestDialog.showModal()", archived)
    assert open_dialog < proposal
    assert "Archivänderung wird vorbereitet" in source[archived:proposal]

def test_0272_finder_has_live_refresh_and_status_badges():
    source = (ROOT / "app" / "events_ui.py").read_text()
    assert "data-cr-refresh-live" in source
    assert "refreshLive:true" in source
    assert "?refresh=true" in source
    assert "Erledigt" in source
    assert "Ausstehend" in source

def test_0272_workspace_explanations_are_compact_and_readable():
    source = (ROOT / "app" / "workspace_ui.py").read_text()
    assert "formatStoredDateTime" in source
    assert "Datenbank-Zeitraum:</strong> von" in source
    assert 'class="bk-help"' in source
    assert 'data-help="Sicher aus dem Archiv auf die SSD zurückgeholter freier Bestand.' in source
    assert 'title="Sicher aus dem Archiv auf die SSD zurückgeholter freier Bestand.' not in source
    assert '<div class="muted" style="margin-top:3px">Sicher aus dem Archiv' not in source

def test_0272_completion_message_is_not_misleading_counter_summary():
    source = (ROOT / "app" / "events_ui.py").read_text()
    assert 'setStatus("Archivänderung abgeschlossen.", false, true)' in source
    assert "SSD-Dateien freigegeben ·" not in source
