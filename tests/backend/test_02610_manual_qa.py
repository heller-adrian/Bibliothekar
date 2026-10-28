from app import __version__ as PACKAGE_VERSION
"""0.26.11 regressions found by the manual 0.26.9 deep test."""

import json

from app.database import database_connection, delete_planned_event
from app.main import APP_VERSION
from app.obsolete_structure import cleanup_obsolete_structure
from app.sort_apply import CONFIRMATION_PHRASE, get_sort_run
from app.workspace_reconcile import (
    build_workspace_reconcile_plan,
    execute_workspace_reconcile_run,
    prepare_workspace_reconcile_run,
)
from app.events_ui import EVENTS_HTML
from app.workspace_ui import WORKSPACE_HTML
from app.ui_shell import BIBLIOTHEKAR_CSS, BIBLIOTHEKAR_JS
from tests.backend.test_0260_free_stock import _seed_cross_job_shift


def test_02610_version():
    assert APP_VERSION == PACKAGE_VERSION


def test_removed_empty_child_directory_is_cleaned_but_desired_empty_child_survives(tmp_path):
    root = tmp_path / "Arbeitsbereich"
    event_root = root / "2026" / "07-23 - Test"
    for branch in ("Alle", "Sortiert", "Export"):
        (event_root / branch).mkdir(parents=True)
        (event_root / "Teil A" / branch).mkdir(parents=True)
        (event_root / "Teil B" / branch).mkdir(parents=True)
    (event_root / "event.json").write_text(json.dumps({
        "source": "kamera-automatisierung",
        "event": {"id": "e", "preserve_day_folders": False},
        "child_events": [
            {"folder_name": "Teil A"},
            {"folder_name": "Teil B"},
        ],
    }))

    desired = [
        event_root / branch for branch in ("Alle", "Sortiert", "Export")
    ] + [
        event_root / "Teil A" / branch for branch in ("Alle", "Sortiert", "Export")
    ]
    cleanup_obsolete_structure(
        root, [], [], {"e"},
        managed_event_roots=[event_root],
        desired_directories=desired,
    )

    assert event_root.is_dir()
    assert (event_root / "event.json").is_file()
    assert (event_root / "Teil A").is_dir()
    assert not (event_root / "Teil B").exists()


def test_applied_delete_preview_removes_event_tree_and_completed_run_stays_pollable(tmp_path):
    db, workspace, file_ids = _seed_cross_job_shift(tmp_path)
    root = workspace / "Arbeitsbereich"
    event_root = root / "2026" / "07-23 - First"

    with database_connection(db) as connection:
        connection.execute(
            """INSERT INTO events(
                   id,job_id,parent_event_id,event_level,name,start_datetime,end_datetime,
                   uses_time_range,folder_name,status,created_at,updated_at,event_kind,
                   revision,applied_at,time_model_version
               ) VALUES (
                   'empty-child','first','first-event','child','Teil B',
                   '2026-07-23T10:30:00','2026-07-23T10:45:59',1,'Teil B',
                   'applied','now','now','event',1,'now',2
               )"""
        )

    for branch in ("Alle", "Sortiert", "Export"):
        (event_root / branch).mkdir(parents=True, exist_ok=True)
        (event_root / "Teil B" / branch).mkdir(parents=True, exist_ok=True)
    (event_root / "event.json").write_text(json.dumps({
        "source": "kamera-automatisierung",
        "event": {"id": "first-event", "preserve_day_folders": False},
        "child_events": [{"folder_name": "Teil B"}],
    }))

    prepared = delete_planned_event(db, "first", "first-event")
    assert prepared["pending_delete"] is True
    plan = build_workspace_reconcile_plan(db, "first", "first-event", workspace)
    assert plan["summary"]["ready"], plan["blockers"]
    assert "07-23 - First" not in plan["structure_text"]
    assert all(
        "07-23 - First" not in str(item["relative_path"])
        for item in plan["directories"]
    )

    run = prepare_workspace_reconcile_run(
        db, "first", "first-event", workspace,
        expected_plan_token=plan["plan_token"],
        confirmation_phrase=CONFIRMATION_PHRASE,
    )
    run_id = run["id"]
    execute_workspace_reconcile_run(db, run_id, workspace)

    with database_connection(db) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM events WHERE id='first-event'"
        ).fetchone()[0] == 0
        # Historical FK behavior still removes the physical run row.
        assert connection.execute(
            "SELECT COUNT(*) FROM sort_runs WHERE id=?", (run_id,)
        ).fetchone()[0] == 0

    receipt = get_sort_run(db, "first", run_id)
    assert receipt is not None
    assert receipt["status"] == "applied"
    assert receipt["terminal"] is True
    assert receipt["progress_percent"] == 100
    assert not event_root.exists()

    free_file = workspace / "SD-Kartensicherungen" / next(
        item["destination_relative_path"]
        for item in plan["files"] if item["file_id"] == file_ids["event"]
    )
    assert free_file.read_bytes() == b"event"


def test_02610_ui_contracts_from_manual_deep_test():
    assert "function scheduleTreeFit(root)" in WORKSPACE_HTML
    assert "scheduleTreeFit(structurePreview);" in WORKSPACE_HTML
    assert "function scheduleVisibleTreeFit(root=document)" in EVENTS_HTML
    assert "const minimum=10;" in EVENTS_HTML
    assert "while(node.scrollWidth>node.clientWidth+1 && size>minimum)" in EVENTS_HTML
    assert "Math.max(0,node.clientWidth-safety)" not in EVENTS_HTML
    assert 'sortPlanCloseButton.textContent = "Schließen";' in EVENTS_HTML
    assert ".child-segment-top" in EVENTS_HTML
    assert ".child-segment-boundaries" in EVENTS_HTML
    assert "minmax(140px,.82fr)" in EVENTS_HTML
    assert "minmax(140px,.82fr)" in WORKSPACE_HTML
    assert "grid-template-columns:minmax(190px,1.55fr) 118px 118px auto" in WORKSPACE_HTML
    assert "minmax(160px,1.25fr) minmax(130px,.75fr)" in WORKSPACE_HTML
    assert "minmax(160px,1.25fr) minmax(130px,.75fr)" in EVENTS_HTML
    assert "const minimum=10;" in WORKSPACE_HTML
    assert "while(node.scrollWidth>node.clientWidth+1 && size>minimum)" in WORKSPACE_HTML
    assert "padding-right:4px;" in WORKSPACE_HTML
    assert "box-sizing:border-box;" in WORKSPACE_HTML
    assert "structureFitMutationObserver.observe(structurePreview" in WORKSPACE_HTML
    assert 'root.matches?.(".structure-lines,.plan-tree")' in WORKSPACE_HTML
    assert 'root.matches?.(".tree,.structure-lines,.plan-tree")' not in WORKSPACE_HTML
    assert WORKSPACE_HTML.index("const structurePreview =") < WORKSPACE_HTML.index("structureFitMutationObserver.observe(structurePreview")
    assert "@media (max-width:440px){.edit-boundary{grid-template-columns:1fr}}" in EVENTS_HTML
    assert "width: fit-content;" in WORKSPACE_HTML
    assert "@media (max-width:460px){.event-boundary,.create-subevent-boundary{grid-template-columns:1fr}" in WORKSPACE_HTML
    assert "background: color-mix(in srgb, var(--bk-page-bg) 98%, transparent);" in BIBLIOTHEKAR_CSS
    assert 'html[data-bk-theme="light"] body.bibliothekar-redesign .selection-bar.is-header-docked' in WORKSPACE_HTML
    assert "background:transparent !important;" in WORKSPACE_HTML
    assert ".bk-workspace-subnav.is-stuck {" in BIBLIOTHEKAR_CSS
    assert "Uhrzeiten berücksichtigen" not in WORKSPACE_HTML
    assert 'id="event-start-time-label"><span>Startzeit</span>' in WORKSPACE_HTML
    assert 'id="event-end-time-label"><span>Endzeit</span>' in WORKSPACE_HTML
    assert 'id="existing-parent-state"' not in WORKSPACE_HTML
    assert "Bestehender Stand · schreibgeschützt" not in WORKSPACE_HTML
    assert "Neue Unterereignisse im Erweiterungsbereich" not in WORKSPACE_HTML
    assert "renderExistingSubeventCards" in WORKSPACE_HTML
    assert 'createSubeventHeading.textContent="Unterereignisse"' in WORKSPACE_HTML
    assert "extensionSelectionForParent" in WORKSPACE_HTML
    assert 'preserveDayFoldersRow.hidden=true' in WORKSPACE_HTML
    assert ".bk-menu.bk-menu-portaled" in BIBLIOTHEKAR_CSS
    assert "function openMenu()" in BIBLIOTHEKAR_JS
    assert 'document.body.appendChild(menu);' in BIBLIOTHEKAR_JS
    assert 'id="change-request-inline-error"' in EVENTS_HTML
    assert "Zielstruktur-Vorschau" in EVENTS_HTML
    assert "Freigewordene Archivdateien werden zuerst sicher in den Arbeitsbereich zurückgeholt." in EVENTS_HTML
    assert "Freigewordene Archivaufnahmen" in WORKSPACE_HTML
