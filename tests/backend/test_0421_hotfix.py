from pathlib import Path

from app.database import database_connection, initialize_database, list_global_tasks
from app.workspace_ui import WORKSPACE_HTML
from app.global_workspace import _workspace_group_sort_key

NOW = "2026-10-07T17:10:00+02:00"


def _job(db: Path, job_id: str, operation: str, label: str) -> None:
    with database_connection(db) as connection:
        connection.execute(
            """INSERT INTO jobs(
                   id,kind,trigger_type,state,stage,operation,
                   source_volume_label,created_at,updated_at
               ) VALUES (?, 'sd_import','manual','completed','done',?,?,?,?)""",
            (job_id, operation, label, NOW, NOW),
        )


def _family(db: Path, job_id: str, key: str, stamp: str) -> None:
    with database_connection(db) as connection:
        connection.execute(
            """INSERT INTO file_families(
                   job_id,family_key,original_stem,status,
                   selected_capture_time,capture_time_confidence
               ) VALUES (?,?,?,'complete',?,'high')""",
            (job_id, key, key, stamp),
        )


def test_0421_unassigned_families_are_one_global_task_across_jobs(tmp_path: Path):
    db = tmp_path / "kamera.sqlite3"
    initialize_database(db)
    _job(db, "IMPORT", "folder_import", "12-04 - Neuseeland")
    _job(db, "META", "metadata_general_import", "Metadatenkorrektur · Allgemein")

    _family(db, "IMPORT", "A", "2026-02-24T09:00:00")
    _family(db, "IMPORT", "B", "2026-02-26T10:00:00")
    _family(db, "META", "C", "2026-02-27T11:00:00")

    tasks = [task for task in list_global_tasks(db) if task["kind"] == "unassigned_families"]

    assert len(tasks) == 1
    assert tasks[0]["family_count"] == 3
    assert tasks[0]["job_count"] == 2
    assert tasks[0]["detail"] == "3 Familien · freier Tagesbestand"
    assert tasks[0]["href"] == "/workspace?task=free"
    assert "job_id" not in tasks[0]


def test_0421_internal_metadata_transfers_are_hidden_from_import_history(tmp_path, monkeypatch):
    from app import main
    db = tmp_path / "history.sqlite3"
    initialize_database(db)
    _job(db, "IMPORT", "folder_import", "Kamera")
    _job(db, "GENERAL", "metadata_general_import", "Metadaten · Allgemein")
    _job(db, "MULTIPLE", "metadata_multiple_import", "Metadaten · Mehrfach")
    monkeypatch.setattr(main, "DATABASE_FILE", db)

    visible = main.api_import_history(limit=20)["jobs"]
    assert [row["id"] for row in visible] == ["IMPORT"]
    assert main.api_import_history()["total"] == 1
    for job_id in ("GENERAL", "MULTIPLE"):
        try:
            main.api_import_history_visibility(job_id, {"hidden": True})
        except Exception as exc:
            assert getattr(exc, "status_code", None) == 409
        else:
            raise AssertionError("Metadatenübertragungen dürfen nicht im Importverlauf ausblendbar sein.")


def test_0421_without_date_is_review_card_not_event_selection():
    html = WORKSPACE_HTML

    assert "name.textContent=reviewCount?'Prüffälle · Ohne Datum':readyCount?'Bereit zum Einsortieren · Ohne Datum':'Ohne Datum'" in html
    assert 'card.className = "day-card without-date review-card"' in html
    assert '.filter(group => group.has_date)' in html
    assert 'new Set(selectableDayKeys())' in html
    assert 'location.href = "/metadata-correction?area=library"' in html
    assert 'data-open-metadata-review' in html
    assert "Nicht für Ereignisse auswählbar" in html
    render_days = html.split("function renderDays()", 1)[1]
    assert "planningOverview().timeline_groups" in "".join(render_days.split())


def test_0421_server_workspace_puts_undated_review_stock_first():
    dated = {
        "group_type": "day",
        "has_date": True,
        "day_key": "2026-02-24",
        "start_datetime": "2026-02-24T00:00:00",
    }
    event = {
        "group_type": "event",
        "start_datetime": "2026-02-23T00:00:00",
    }
    undated = {
        "group_type": "day",
        "has_date": False,
        "day_key": None,
        "start_datetime": None,
    }

    ordered = sorted([dated, event, undated], key=_workspace_group_sort_key)

    assert ordered[0] is undated
    assert ordered[1] is event
    assert ordered[2] is dated
