from pathlib import Path

from app.event_structure import build_event_preview
from app.events_ui import EVENTS_HTML
from app.main import APP_VERSION
from app.ui_shell import BIBLIOTHEKAR_CSS, BIBLIOTHEKAR_JS, _shell_markup
from app.workspace_ui import WORKSPACE_HTML


ROOT = Path(__file__).resolve().parents[2]


def _source(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_0269_version():
    assert APP_VERSION == "0.26.9"


def test_0269_empty_subevent_is_detected_and_kept_in_preview_structure():
    families = [{
        "family_id": 1,
        "family_key": "DSCF1477",
        "has_date": True,
        "day_key": "2026-07-23",
        "selected_capture_time": "2026-07-23T18:01:49",
        "file_count": 2,
        "total_size_bytes": 100,
        "review_required_count": 0,
    }]
    preview = build_event_preview({
        "event_kind": "event",
        "event_name": "Applied Zeit-Test",
        "start_date": "2026-07-23",
        "end_date": "2026-07-24",
        "uses_time_range": True,
        "start_time": "13:00",
        "end_time": "18:00",
        "preserve_day_folders": False,
        "subevents": [
            {
                "name": "Teil A",
                "start_datetime": "2026-07-23T17:00:00",
                "end_datetime": "2026-07-23T20:00:59",
            },
            {
                "name": "Teil B",
                "start_datetime": "2026-07-24T10:00:00",
                "end_datetime": "2026-07-24T12:00:59",
            },
        ],
    }, families)

    assert [item["name"] for item in preview["empty_subevents"]] == ["Teil B"]
    assert "Teil A" in preview["structure_text"]
    assert "Teil B" in preview["structure_text"]


def test_0269_empty_subevents_require_explicit_confirmation_in_both_flows():
    main = _source("app/main.py")
    assert main.count('"confirmation_required": "empty_subevents"') >= 2
    assert "confirm_empty_subevents" in main
    assert "createEventWithEmptySubeventConfirmation" in WORKSPACE_HTML
    assert "confirmEditEmptySubevents" in EVENTS_HTML
    assert "Die leere Ordnerstruktur wird trotzdem angelegt" in WORKSPACE_HTML
    assert "Die leere Ordnerstruktur wird trotzdem angelegt" in EVENTS_HTML


def test_0269_sort_plan_materializes_empty_subevent_directories():
    sort_plan = _source("app/sort_plan.py")
    assert "child_definition_rows = connection.execute" in sort_plan
    assert "Organizational subevents are part of the target structure" in sort_plan
    assert 'planned_directories.add(str(child_root / "Alle"))' in sort_plan
    assert 'planned_directories.add(str(child_root / "Sortiert"))' in sort_plan
    assert 'planned_directories.add(str(child_root / "Export"))' in sort_plan
    assert '"code": "empty_subevent"' in sort_plan


def test_0269_applied_edit_and_delete_are_mandatory_transactions():
    database = _source("app/database.py")
    reconcile = _source("app/workspace_reconcile.py")

    assert 'status="pending_apply"' in database
    assert '"reassignment_required": False if is_applied else bool(removed_ids)' in database
    assert '"reassignment_required": False, "removed_family_ids": family_ids' in database
    assert "target_kind='released_free'" in reconcile

    assert 'let mandatoryMutationContext = null' in EVENTS_HTML
    assert 'sortPlanCloseButton.textContent = mandatoryMutationContext ? "Änderungen verwerfen" : "Schließen"' in EVENTS_HTML
    assert 'applyConfirmation.checked = true' in EVENTS_HTML
    assert 'if (mandatoryMutationContext) event.preventDefault();' in EVENTS_HTML
    assert 'event.status === "applied" ? "Änderungen anwenden" : "Änderungen speichern"' in EVENTS_HTML
    assert "discardMandatoryMutation()" in EVENTS_HTML


def test_0269_released_free_marker_is_not_an_open_task_or_reassignment():
    database = _source("app/database.py")
    reassignment = _source("app/event_reassignment.py")
    reconcile = _source("app/workspace_reconcile.py")
    planning = _source("app/planning.py")
    assert database.count("COALESCE(target_kind,'') <> 'released_free'") >= 3
    assert reassignment.count("COALESCE(target_kind,'') <> 'released_free'") >= 3
    assert "released_free_families" in database
    assert "released_free_families" in planning
    assert "INSERT OR REPLACE INTO released_free_families" in reconcile
    assert "reconcile_released_free_markers" in reassignment


def test_0269_workspace_header_is_static_and_morph_is_gone():
    assert 'selectionBar.classList.add("is-header-docked")' in WORKSPACE_HTML
    assert "function positionWorkspaceChrome()" in WORKSPACE_HTML
    assert 'captureSummarySlot.appendChild(summarySection)' in WORKSPACE_HTML
    assert ".summary.compact-heading-summary" in WORKSPACE_HTML
    assert "selectionMorphDistance" not in WORKSPACE_HTML
    assert "applySelectionMorphProgress" not in WORKSPACE_HTML
    assert "selectionFrameLeft" not in WORKSPACE_HTML
    assert 'window.addEventListener("scroll",updateSelectionDock' not in WORKSPACE_HTML


def test_0269_capture_heading_has_metric_slot_and_task_panel_is_portaled():
    markup = _shell_markup("workspace", "captures")
    assert 'id="bk-capture-summary-slot"' in markup
    assert ".bk-capture-heading" in BIBLIOTHEKAR_CSS
    assert ".bk-task-panel.bk-task-panel-portaled" in BIBLIOTHEKAR_CSS
    assert "document.body.appendChild(taskPanel)" in BIBLIOTHEKAR_JS
    assert "function restoreTaskPanel()" in BIBLIOTHEKAR_JS


def test_0269_structure_trees_never_wrap_and_fit_dynamically():
    assert "function fitTreeText(root)" in WORKSPACE_HTML
    assert "white-space: pre;" in WORKSPACE_HTML
    assert "function fitMonospaceTree(node)" in EVENTS_HTML
    assert "function fitVisibleTrees(root=document)" in EVENTS_HTML
    assert "white-space:pre;" in EVENTS_HTML or "white-space: pre;" in EVENTS_HTML


def test_0269_subevent_editor_uses_split_date_and_time_fields():
    assert 'data-child-start-date' in EVENTS_HTML
    assert 'data-child-start-time' in EVENTS_HTML
    assert 'data-child-end-date' in EVENTS_HTML
    assert 'data-child-end-time' in EVENTS_HTML
    assert ".child-segment-boundary" in EVENTS_HTML
    assert ".child-segment-end-row" in EVENTS_HTML
