from pathlib import Path

import pytest

from app.database import _validated_adjacent_extension
from app.obsolete_structure import cleanup_obsolete_structure
from app.workspace_reconcile import _workspace_structure_text
from app.events_ui import EVENTS_HTML
from app.workspace_ui import WORKSPACE_HTML
from app.ui_shell import BIBLIOTHEKAR_CSS, BIBLIOTHEKAR_JS, _shell_markup


def test_0268_cleanup_keeps_empty_standard_branches_for_active_target(tmp_path: Path):
    root = tmp_path / "Arbeitsbereich"
    event = root / "2026" / "07-19 - Applied Kernlauf bearbeitet"
    alle = event / "Alle"
    sortiert = event / "Sortiert"
    export = event / "Export"
    for directory in (alle, sortiert, export):
        directory.mkdir(parents=True, exist_ok=True)
    file_path = alle / "IMG_0001.JPG"
    file_path.write_bytes(b"x")

    removed = cleanup_obsolete_structure(
        root,
        [file_path],
        [file_path],
        {"EVENT_ACTIVE"},
    )

    assert alle.is_dir()
    assert sortiert.is_dir()
    assert export.is_dir()
    assert str(sortiert) not in removed
    assert str(export) not in removed


def test_0268_cleanup_still_removes_empty_obsolete_standard_branches(tmp_path: Path):
    root = tmp_path / "Arbeitsbereich"
    old = root / "2026" / "07-19 - Alt"
    for branch in ("Alle", "Sortiert", "Export"):
        (old / branch).mkdir(parents=True, exist_ok=True)

    new = root / "2026" / "07-19 - Neu" / "Alle"
    new.mkdir(parents=True, exist_ok=True)
    destination = new / "IMG_0001.JPG"

    cleanup_obsolete_structure(
        root,
        [old / "Alle" / "IMG_0001.JPG"],
        [destination],
        {"EVENT_ACTIVE"},
    )

    assert not (old / "Sortiert").exists()
    assert not (old / "Export").exists()


def test_0268_reconcile_tree_is_real_folder_tree():
    tree = _workspace_structure_text([
        {"relative_path": "2026/07-19 - Applied Kernlauf bearbeitet/Alle"},
        {"relative_path": "2026/07-19 - Applied Kernlauf bearbeitet/Sortiert"},
        {"relative_path": "2026/07-19 - Applied Kernlauf bearbeitet/Export"},
        {"relative_path": "2026/07-20 - Applied Rest/Alle"},
        {"relative_path": "2026/07-20 - Applied Rest/Sortiert"},
        {"relative_path": "2026/07-20 - Applied Rest/Export"},
    ])

    assert tree.startswith("2026\n")
    assert "07-19 - Applied Kernlauf bearbeitet" in tree
    assert "07-20 - Applied Rest" in tree
    assert "Gemeinsamer Arbeitsbereich-Abgleich" not in tree
    assert tree.index("Alle") < tree.index("Sortiert") < tree.index("Export")


def test_0268_applied_state_copy_and_refresh_contract():
    assert "⚠ Neu-Zuordnung offen" not in EVENTS_HTML
    assert "⚠ Nachsortierung offen" not in EVENTS_HTML
    assert "⚠ Änderung noch nicht angewendet" not in EVENTS_HTML
    assert "Neu-Zuordnung fortsetzen" in EVENTS_HTML
    assert "Änderung fortsetzen" in EVENTS_HTML
    assert 'data-cancel-mutation=' in EVENTS_HTML
    assert "await loadEvents({reset:true});" in EVENTS_HTML
    assert 'applyButton.textContent = "Schließen"' in EVENTS_HTML
    assert 'applyButton.dataset.completed = "true"' in EVENTS_HTML


def test_0268_reconcile_target_is_not_independent_apply_ui():
    assert "Ziel einer offenen gemeinsamen Nachsortierung" in WORKSPACE_HTML
    assert 'applySavedEventButton.dataset.action = "reconcile"' in WORKSPACE_HTML
    assert "Nachsortierung unter Ereignisse öffnen" in WORKSPACE_HTML
    assert "Boolean(Number(event.reconcile_target||0))" in WORKSPACE_HTML
    assert "if (dated.some(group => Boolean(group.reassignment_pending))) return [];" in WORKSPACE_HTML
    assert "Bestehendes Ereignis erweitern" in WORKSPACE_HTML


def test_0268_sort_plan_modal_is_compact_and_disclosed():
    assert "inline-size: min(1240px" in EVENTS_HTML
    assert "grid-template-columns: repeat(7, minmax(0, 1fr))" in EVENTS_HTML
    assert EVENTS_HTML.count('class="sort-plan-section sort-plan-disclosure"') >= 3
    assert '<summary>Sicherheitsstatus</summary>' in EVENTS_HTML
    assert '<summary>Arbeitsbestand</summary>' in EVENTS_HTML
    assert '<summary>Zielstruktur</summary>' in EVENTS_HTML


def test_0268_workspace_subnav_keeps_page_background():
    markup = _shell_markup("workspace", "events")
    assert 'class="bk-workspace-subnav"' in markup
    assert 'data-bk-workspace-subarea="events"' in markup
    assert "background: color-mix(in srgb, var(--bk-page-bg) 98%, transparent);" in BIBLIOTHEKAR_CSS
    assert ".bk-workspace-subnav.is-stuck {" in BIBLIOTHEKAR_CSS
    assert "var(--bk-page-bg) 98%" in BIBLIOTHEKAR_CSS


def test_0268_sort_apply_panel_is_compact_and_messages_are_deduped():
    assert "const seenMessages = new Set();" in EVENTS_HTML
    assert "const uniqueItems = (items || []).filter" in EVENTS_HTML
    assert 'class="sort-apply-head"' in EVENTS_HTML
    assert 'class="bk-help"' in EVENTS_HTML
    assert "grid-template-columns: minmax(0, 1fr) auto" in EVENTS_HTML
    assert "align-items: center;" in EVENTS_HTML
    assert "Ich bestätige diesen Zielplan; verändert wird ausschließlich" in EVENTS_HTML


def test_0268_event_viewer_edit_action_is_in_header():
    assert 'id="event-edit-header-button"' in EVENTS_HTML
    assert 'id="inspect-edit-event"' not in EVENTS_HTML
    assert "eventEditHeaderButton.hidden = false;" in EVENTS_HTML
    assert "eventEditHeaderButton.onclick = () => renderEventEditor(context);" in EVENTS_HTML


def test_0268_existing_event_extension_is_bidirectional_and_existing_structure_locked():
    assert "function extensionSelectionForParent(parent, dated)" in WORKSPACE_HTML
    assert 'direction="after"' in WORKSPACE_HTML
    assert 'direction="before"' in WORKSPACE_HTML
    assert 'dialogTitle.textContent="Ereignis erweitern"' in WORKSPACE_HTML
    assert "activeExtension=extension;" in WORKSPACE_HTML
    assert "useTimeRange.disabled=true" in WORKSPACE_HTML
    assert "preserveDayFolders.disabled=true" in WORKSPACE_HTML
    assert "preserveDayFoldersRow.hidden=true" in WORKSPACE_HTML
    assert "createSubevents.hidden=false" in WORKSPACE_HTML
    assert "base.subevents = [];" not in WORKSPACE_HTML
    assert "base.preserve_day_folders = Boolean(parent.preserve_day_folders);" in WORKSPACE_HTML
    assert "Bestehender Stand · schreibgeschützt" not in WORKSPACE_HTML
    assert "renderExistingSubeventCards" in WORKSPACE_HTML
    assert 'row.dataset.existingSubevent="1"' in WORKSPACE_HTML
    assert 'createSubeventHeading.textContent="Unterereignisse"' in WORKSPACE_HTML
    assert "Neue Unterereignisse dürfen nur innerhalb des neu hinzugefügten Erweiterungsbereichs liegen." in WORKSPACE_HTML


def test_0268_adjacent_extension_guard_accepts_both_sides():
    after = _validated_adjacent_extension(
        ("2026-07-20T00:00:00", "2026-07-20T23:59:59"),
        [{"start_datetime": "2026-07-21T00:00:00", "end_datetime": "2026-07-21T18:30:59"}],
    )
    assert after["direction"] == "after"
    assert after["new_start"] == "2026-07-20T00:00:00"
    assert after["new_end"] == "2026-07-21T18:30:59"

    before = _validated_adjacent_extension(
        ("2026-07-20T00:00:00", "2026-07-20T23:59:59"),
        [{"start_datetime": "2026-07-19T06:15:00", "end_datetime": "2026-07-19T23:59:59"}],
    )
    assert before["direction"] == "before"
    assert before["new_start"] == "2026-07-19T06:15:00"
    assert before["new_end"] == "2026-07-20T23:59:59"

    with pytest.raises(ValueError, match="unmittelbar angrenzende"):
        _validated_adjacent_extension(
            ("2026-07-20T00:00:00", "2026-07-20T23:59:59"),
            [{"start_datetime": "2026-07-22T00:00:00", "end_datetime": "2026-07-22T23:59:59"}],
        )


def test_0268_dialog_errors_are_red_only_and_success_box_is_success_only():
    assert 'saveResult.hidden=true;\n        saveResult.textContent="";\n        dialogError.hidden=false;' in WORKSPACE_HTML
    assert "saveResult.textContent=error.message" not in WORKSPACE_HTML
    assert "function clearDialogFeedbackForEdit()" in WORKSPACE_HTML


def test_0268_workspace_cards_show_pending_resort_badge():
    planning = (Path(__file__).resolve().parents[2] / "app/planning.py").read_text(encoding="utf-8")
    assert "root.resort_required AS root_resort_required" in planning
    assert 'group.status === "applied" && Boolean(group.resort_required)' in WORKSPACE_HTML
    assert "Nachsortierung ausstehend" in WORKSPACE_HTML
    assert 'class="timeline-event-statuses"' in WORKSPACE_HTML


def test_0268_task_panel_is_portaled_above_static_workspace_header():
    assert ".bk-task-panel.bk-task-panel-portaled" in BIBLIOTHEKAR_CSS
    assert "z-index: 10000" in BIBLIOTHEKAR_CSS
    assert "function openTaskPanel()" in BIBLIOTHEKAR_JS
    assert "document.body.appendChild(taskPanel)" in BIBLIOTHEKAR_JS
    assert "function restoreTaskPanel()" in BIBLIOTHEKAR_JS


def test_0268_selection_summary_targets_workspace_tab_geometry():
    assert "const workspaceTab=document.querySelector('.bk-tab[data-area=\"workspace\"]');" in WORKSPACE_HTML
    assert "function alignHeaderSelectionSummary()" in WORKSPACE_HTML
    assert 'selectionSummary.style.left=(tabRect.left+tabRect.width/2-barRect.left)+"px"' in WORKSPACE_HTML
    assert "selectionMorphDistance" not in WORKSPACE_HTML
