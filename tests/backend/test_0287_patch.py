from __future__ import annotations

from pathlib import Path

from app import main
from app.database import database_connection, delete_planned_event, initialize_database, list_global_tasks
from app.global_workspace import build_global_workspace_summary
from app.planning import list_global_released_archive_groups
from app.workspace_layout import backup_root
from app.workspace_reconcile import (
    build_workspace_reconcile_plan,
    execute_workspace_reconcile_run,
    prepare_workspace_reconcile_run,
)
from app.sort_apply import CONFIRMATION_PHRASE
from app.workspace_ui import WORKSPACE_HTML
from app.events_ui import EVENTS_HTML
from tests.backend.test_0263_event_inventory import NOW, seed_job
from tests.backend.test_0283_structure_simplification import _seed_applied_workspace
from tests.backend.test_0286_patch import _seed_family_file


def _apply_delete_reconcile(db: Path, workspace: Path) -> dict:
    deleted = delete_planned_event(db, "j", "e")
    assert deleted["pending_delete"] is True
    plan = build_workspace_reconcile_plan(db, "j", "e", workspace)
    assert plan["summary"]["ready"] is True, plan["blockers"]
    run = prepare_workspace_reconcile_run(
        db,
        "j",
        "e",
        workspace,
        expected_plan_token=plan["plan_token"],
        confirmation_phrase=CONFIRMATION_PHRASE,
    )
    execute_workspace_reconcile_run(db, run["id"], workspace)
    return plan


def test_0287_delete_applied_flattens_xmp_and_export_into_free_day(tmp_path: Path):
    db = tmp_path / "db.sqlite3"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    event_root, _file_id = _seed_applied_workspace(db, workspace)

    plan = _apply_delete_reconcile(db, workspace)
    targets = {row["asset_kind"]: row["destination_relative_path"] for row in plan["assets"]}
    assert targets == {
        "xmp": "2026/2026-07-23/A.xmp",
        "export": "2026/2026-07-23/A_Export.jpg",
    }

    free_root = backup_root(workspace) / "2026" / "2026-07-23"
    assert (free_root / "A.JPG").read_bytes() == b"camera-a"
    assert (free_root / "A.xmp").read_bytes() == b"xmp-a"
    assert (free_root / "A_Export.jpg").read_bytes() == b"export-a"
    assert not (event_root / "Alle").exists()
    assert not (event_root / "Export").exists()


def test_0287_delete_applied_archive_origin_flattens_all_assets_in_archive_release_stock(tmp_path: Path):
    db = tmp_path / "db.sqlite3"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    event_root, _file_id = _seed_applied_workspace(db, workspace)

    with database_connection(db) as connection:
        family_id = int(connection.execute("SELECT id FROM file_families LIMIT 1").fetchone()[0])
        connection.execute(
            """INSERT INTO released_free_families(
                   job_id,family_id,released_start_datetime,released_end_datetime,
                   created_at,archive_origin
               ) VALUES ('j',?,'2026-07-23T00:00:00','2026-07-23T23:59:59',?,1)""",
            (family_id, NOW),
        )

    plan = _apply_delete_reconcile(db, workspace)
    prefix = "Freigewordene Archivdateien/2026/2026-07-23/"
    targets = {row["asset_kind"]: row["destination_relative_path"] for row in plan["assets"]}
    assert targets == {
        "xmp": prefix + "A.xmp",
        "export": prefix + "A_Export.jpg",
    }

    free_root = backup_root(workspace) / "Freigewordene Archivdateien" / "2026" / "2026-07-23"
    assert (free_root / "A.JPG").read_bytes() == b"camera-a"
    assert (free_root / "A.xmp").read_bytes() == b"xmp-a"
    assert (free_root / "A_Export.jpg").read_bytes() == b"export-a"
    assert not (event_root / "Alle").exists()
    assert not (event_root / "Export").exists()


def test_0287_released_archive_groups_merge_same_interval_across_backups(tmp_path: Path):
    db = tmp_path / "db.sqlite3"
    initialize_database(db)
    with database_connection(db) as connection:
        seed_job(connection, "a")
        seed_job(connection, "b")
        fa, _ = _seed_family_file(
            connection, job_id="a", stem="A", capture="2026-07-20T10:00:00",
            current_path="Freigewordene Archivdateien/2026/2026-07-20/A.JPG", content=b"a",
        )
        fb, _ = _seed_family_file(
            connection, job_id="b", stem="B", capture="2026-07-20T11:00:00",
            current_path="Freigewordene Archivdateien/2026/2026-07-20/B.JPG", content=b"b",
        )
        connection.executemany(
            """INSERT INTO released_free_families(
                   job_id,family_id,released_start_datetime,released_end_datetime,
                   created_at,archive_origin
               ) VALUES (?, ?, '2026-07-20T00:00:00', '2026-07-20T23:59:59', ?, 1)""",
            [("a", fa, NOW), ("b", fb, NOW)],
        )

    groups = list_global_released_archive_groups(db)
    assert len(groups) == 1
    group = groups[0]
    assert set(group["family_ids"]) == {fa, fb}
    assert set(group["source_job_ids"]) == {"a", "b"}
    assert group["family_count"] == 2
    assert group["source_label"] == "2 Sicherungen"
    assert {source["job_id"] for source in group["source_groups"]} == {"a", "b"}

    filtered = build_global_workspace_summary(db, ["a"])["released_archive_groups"]
    assert len(filtered) == 1
    assert set(filtered[0]["family_ids"]) == {fa, fb}
    assert set(filtered[0]["source_job_ids"]) == {"a", "b"}


def test_0287_day_controls_lock_month_and_year_and_archive_selection_stays_global():
    assert main.RELEASE_VERSION == "0.55.2"
    assert 'subeventDayControl("data-create-child-start-date"' in WORKSPACE_HTML
    assert "data-create-child-start-month-year" in WORKSPACE_HTML
    assert "data-create-child-end-month-year" in WORKSPACE_HTML
    assert "<select data-segment-day" in WORKSPACE_HTML
    assert "Freigewordene Archivaufnahmen aus der Ursprungssicherung ausgewählt." not in WORKSPACE_HTML
    assert "&& group.released_archive" not in WORKSPACE_HTML

    assert 'editSubeventDayControl("data-child-start-date"' in EVENTS_HTML
    assert "data-child-start-month-year" in EVENTS_HTML
    assert "data-child-end-month-year" in EVENTS_HTML
    assert "<select data-segment-day" in EVENTS_HTML


def test_0287_released_archive_task_is_global_across_backups(tmp_path: Path):
    db = tmp_path / "db.sqlite3"
    initialize_database(db)
    with database_connection(db) as connection:
        seed_job(connection, "a")
        seed_job(connection, "b")
        fa, _ = _seed_family_file(
            connection, job_id="a", stem="A", capture="2026-07-20T10:00:00",
            current_path="Freigewordene Archivdateien/2026/2026-07-20/A.JPG", content=b"a",
        )
        fb, _ = _seed_family_file(
            connection, job_id="b", stem="B", capture="2026-07-20T11:00:00",
            current_path="Freigewordene Archivdateien/2026/2026-07-20/B.JPG", content=b"b",
        )
        connection.executemany(
            """INSERT INTO released_free_families(
                   job_id,family_id,released_start_datetime,released_end_datetime,
                   created_at,archive_origin
               ) VALUES (?, ?, '2026-07-20T00:00:00', '2026-07-20T23:59:59', ?, 1)""",
            [("a", fa, NOW), ("b", fb, NOW)],
        )

    tasks = [
        task for task in list_global_tasks(db)
        if task.get("kind") == "released_archive_families"
    ]
    assert len(tasks) == 1
    assert tasks[0]["family_count"] == 2
    assert tasks[0]["detail"] == "2 Familien"


def test_0287_released_archive_card_hides_backup_origin():
    assert 'group.released_archive ? `<span>Herkunft:' not in WORKSPACE_HTML
    assert "Auswahl verwendet automatisch die jeweilige Ursprungssicherung." not in WORKSPACE_HTML
    assert "Offene Aufgabe: In dieser Sicherung gibt es noch nicht zugeordnete Familien." not in WORKSPACE_HTML
