"""0.27.0: Pflichttransaktionen und minimale Archiv-Hilfsstruktur."""
from pathlib import PurePosixPath

from app.archive_staging import _desired_directory_plan
from app.events_ui import EVENTS_HTML


def test_0270_archive_staging_contains_only_real_target_directories():
    preview = {
        "start_date": "2026-07-22",
        "parent_folder": "07-22 - Test Archiv 2",
        "subevents": [
            {
                "name": "Teil A",
                "folder_name": "07-22 00-00...23-59 - Teil A",
                "start_datetime": "2026-07-22T00:00:00",
                "end_datetime": "2026-07-22T23:59:59",
            },
            {
                "name": "Leer",
                "folder_name": "07-23 00-00...12-00 - Leer",
                "start_datetime": "2026-07-23T00:00:00",
                "end_datetime": "2026-07-23T12:00:00",
            },
        ],
    }
    plan = {
        "families_with_plans": [
            {
                "action": "move",
                "source_root_kind": "shared_workspace",
                "new_path": "2026/07-22 - Test Archiv 2/07-22 00-00...23-59 - Teil A/Alle/neu.JPG",
            },
            {
                "action": "keep",
                "source_root_kind": "camera_archive",
                "new_path": "2026/07-22 - Test Archiv 2/07-22 00-00...23-59 - Teil A/Export/alt.JPG",
            },
        ],
        "assets_with_plans": [],
    }

    dirs = _desired_directory_plan(preview, plan)
    root = PurePosixPath("2026/07-22 - Test Archiv 2")
    assert dirs == {
        root,
        root / "07-22 00-00...23-59 - Teil A",
        root / "07-22 00-00...23-59 - Teil A" / "Alle",
        root / "07-22 00-00...23-59 - Teil A" / "Sortiert",
        root / "07-22 00-00...23-59 - Teil A" / "Export",
    }
    assert root / "07-23 00-00...12-00 - Leer" not in dirs


def test_0270_archive_change_dialog_is_mandatory_and_reload_safe():
    html = EVENTS_HTML
    assert "let mandatoryArchiveChangeContext = null;" in html
    assert 'window.addEventListener("beforeunload"' in html
    assert 'changeRequestDialog.addEventListener("cancel"' in html
    assert 'changeRequestClose.textContent = String(cr.status)==="aenderbar_vorschlagen"' in html
    assert 'bk0511EventLabel("Änderung verwerfen","Discard change")' in html
    assert 'bk0511EventLabel("Änderung sicher zurücknehmen","Safely reverse change")' in html
    assert "findOpenArchiveChangeRequest(eventId)" in html
    assert "await showChangeRequestDetail(pendingChange.id, {resume:true})" in html
    assert "await showChangeRequestDetail(pendingArchive.id, {resume:true})" in html
    assert "clearChangeTaskFromUrl(crId)" in html


def test_0271_archive_change_ui_is_compact_three_step_assistant():
    html = EVENTS_HTML
    assert "Vorbereiten" in html
    assert "Manuelle Arbeit" in html
    assert "Prüfen & Abschließen" in html
    assert "Hilfsbereich vorbereiten" in html
    assert "Manuelle Arbeit prüfen · weiter" in html
    assert "Technische Details" in html
    assert "Freigewordene Archivdateien werden zuerst sicher in den Arbeitsbereich zurückgeholt." in html
    assert "Änderung abschließen & Arbeitsbereich freigeben" in html
    assert 'id="change-work-progress"' in html
    assert 'bk0511EventLabel("Arbeitsbereich und Hilfslinks sicher freigeben …","Safely releasing workspace and helper links…")' in html
    assert "change_step" in html
    assert "change-arrow" not in html
    assert ">↓<" not in html
    assert "NOCH ZU ENTFERNEN" in html
    assert "Alter Ordner noch vorhanden" in html
    assert "Freigewordene Archivdateien im Arbeitsbereich sichern" in html
    assert "Arbeitsbereich-Kopien prüfen" in html
    assert "Bestätigte Archivoriginale entfernen" in html
    assert "Entfernung aus dem Archiv prüfen" in html
    assert "Zielstruktur-Vorschau" in html
    assert "Zielstruktur-Vorschau" in html
    assert 'id="change-request-inline-error"' in html


def test_0270_applied_reload_keeps_mandatory_transaction():
    html = EVENTS_HTML
    assert "mandatory: Boolean(target?.mutation_id && target.id === target.mutation_anchor_event_id)" in html
    assert "mandatory: Boolean(targetEvent?.mutation_id && targetEvent.id === targetEvent.mutation_anchor_event_id)" in html
