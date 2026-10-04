from __future__ import annotations

from pathlib import Path
import hashlib

from app import main
from app.database import database_connection, initialize_database, list_global_tasks
from app.metadata_correction_ui import METADATA_CORRECTION_HTML
from app.workspace_ui import WORKSPACE_HTML


def _insert_undated_task_fixture(
    database: Path,
    *,
    selected_capture_time: str | None,
) -> None:
    payload = b"undated"
    digest = hashlib.sha256(payload).hexdigest()
    with database_connection(database) as connection:
        connection.execute(
            """INSERT INTO jobs(
                   id,kind,trigger_type,state,stage,operation,
                   source_volume_label,source_path,created_at,updated_at
               ) VALUES (
                   'JOB_META','sd_import','manual','completed','organized_verified',
                   'folder_import','Importtest','/source',
                   '2026-10-03T18:00:00+02:00','2026-10-03T18:00:00+02:00'
               )"""
        )
        family_id = int(
            connection.execute(
                """INSERT INTO file_families(
                       job_id,family_key,original_stem,status,
                       selected_capture_time,capture_time_confidence
                   ) VALUES (
                       'JOB_META','FAMILY','PRUEFFALL','complete',?,?
                   )""",
                (
                    selected_capture_time,
                    "high" if selected_capture_time else "missing",
                ),
            ).lastrowid
        )
        connection.execute(
            """INSERT INTO files(
                   job_id,family_id,original_relative_path,current_relative_path,
                   original_filename,extension,media_type,size_bytes,
                   sha256_original,sha256_current,selected_capture_time,
                   selected_capture_source,capture_time_confidence,review_status,
                   metadata_write_status,current_root_kind,created_at,updated_at
               ) VALUES (
                   'JOB_META',?,'PRUEFFALL.JPG','Ohne_Datum/PRUEFFALL.JPG',
                   'PRUEFFALL.JPG','.JPG','jpeg',?,?,?,?,?,?,
                   ?,'written','shared_workspace',
                   '2026-10-03T18:00:00+02:00','2026-10-03T18:00:00+02:00'
               )""",
            (
                family_id,
                len(payload),
                digest,
                digest,
                selected_capture_time,
                "metadata_correction" if selected_capture_time else None,
                "high" if selected_capture_time else "missing",
                "corrected" if selected_capture_time else "required",
            ),
        )
        connection.commit()


def test_0335_undated_review_is_one_global_task(tmp_path: Path):
    database = tmp_path / "kamera.sqlite3"
    initialize_database(database)
    _insert_undated_task_fixture(database, selected_capture_time=None)

    tasks = list_global_tasks(database)
    review = [task for task in tasks if task.get("kind") == "metadata_review"]

    assert len(review) == 1
    assert review[0]["title"] == "Prüffälle bearbeiten"
    assert review[0]["review_count"] == 1
    assert review[0]["ready_count"] == 0
    assert review[0]["href"] == "/metadata-correction?area=library"


def test_0335_corrected_undated_family_waits_for_sort_without_unassigned_duplicate(
    tmp_path: Path,
):
    database = tmp_path / "kamera.sqlite3"
    initialize_database(database)
    _insert_undated_task_fixture(
        database,
        selected_capture_time="2026-10-03T20:15:30",
    )

    tasks = list_global_tasks(database)
    review = [task for task in tasks if task.get("kind") == "metadata_review"]
    unassigned = [task for task in tasks if task.get("kind") == "unassigned_families"]

    assert len(review) == 1
    assert review[0]["title"] == "Korrigierte Aufnahmen einsortieren"
    assert review[0]["review_count"] == 0
    assert review[0]["ready_count"] == 1
    assert unassigned == []


def test_0335_metadata_ui_is_flat_selectable_and_two_step():
    assert "nach Herkunftsbibliothek gruppiert" not in METADATA_CORRECTION_HTML
    assert "Gemeinsamer Ohne-Datum-Bestand" in METADATA_CORRECTION_HTML
    assert 'id="meta-select-all"' in METADATA_CORRECTION_HTML
    assert "event.shiftKey" in METADATA_CORRECTION_HTML
    assert "/api/metadata-correction/reintegrate" in METADATA_CORRECTION_HTML
    assert "In Tagesbestand einsortieren" in METADATA_CORRECTION_HTML
    assert "selectedFiles()" in METADATA_CORRECTION_HTML
    assert "files.every(file=>file.reintegration_ready)" in METADATA_CORRECTION_HTML
    assert "for(const item of files)" in METADATA_CORRECTION_HTML
    assert "Einträge ausgewählt.</strong></div>" in METADATA_CORRECTION_HTML
    assert "0.34.0" not in METADATA_CORRECTION_HTML
    assert "Metadaten werden sicher auf Arbeitskopien geschrieben" not in METADATA_CORRECTION_HTML
    assert "outline:2px" not in METADATA_CORRECTION_HTML
    assert "box-shadow:inset" in METADATA_CORRECTION_HTML
    assert "user-select:none" in METADATA_CORRECTION_HTML


def test_0335_workspace_supports_shift_range_and_select_all():
    assert 'id="day-select-all"' in WORKSPACE_HTML
    assert "event.shiftKey && lastSelectedDayKey" in WORKSPACE_HTML
    assert "selectDayRange" in WORKSPACE_HTML
    assert "user-select: none" in WORKSPACE_HTML
    assert 'id="select-all-button"' not in WORKSPACE_HTML
    assert 'id="clear-selection-button"' not in WORKSPACE_HTML
    assert "Alle auswählen" in WORKSPACE_HTML
    assert "Auswahl aufheben" in WORKSPACE_HTML


def test_0335_import_history_starts_with_five_and_can_expand():
    source = Path("app/main.py").read_text(encoding="utf-8")
    assert "let jobHistoryLimit = 5;" in source
    assert "jobHistoryJobs.slice(0, jobHistoryLimit)" in source
    assert "jobHistoryLimit += 5;" in source
    assert "Mehr anzeigen" in source


def test_0335_deployment_version():
    assert main.DEPLOYMENT_VERSION == "0.40.0"
