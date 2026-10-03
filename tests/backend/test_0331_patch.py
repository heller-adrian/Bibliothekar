from __future__ import annotations

from pathlib import Path

import app.metadata_correction as metadata_correction
from app.database import create_job, database_connection, initialize_database, list_imported_media_origins
from app.event_naming import normalize_event_naming, render_no_event_folder_name
from app.global_stock import propagate_corrected_family
from app.metadata_correction import (
    apply_metadata_correction,
    create_metadata_correction,
    metadata_area_paths,
    scan_metadata_area,
)
from app.metadata_correction_ui import METADATA_CORRECTION_HTML
from app.ui_shell import apply_shell


def _insert_undated_family(
    database: Path,
    *,
    job_id: str = "JOB",
    family_key: str = "DCIM/IMG_0001",
    relative: str = "Ohne_Datum/IMG_0001.JPG",
    original: str = "DCIM/IMG_0001.JPG",
    payload: bytes = b"camera-payload",
) -> tuple[int, int]:
    create_job(
        database,
        job_id=job_id,
        kind="sd_import",
        trigger_type="manual",
        operation="folder_import",
    )
    with database_connection(database) as connection:
        family_id = int(connection.execute(
            """INSERT INTO file_families(
                   job_id,family_key,original_stem,status,
                   selected_capture_time,capture_time_confidence
               )
               VALUES (?,?,?,'review_required',NULL,'missing')""",
            (job_id, family_key, "IMG_0001"),
        ).lastrowid)
        file_id = int(connection.execute(
            """INSERT INTO files(
                   job_id,family_id,original_relative_path,current_relative_path,
                   current_root_kind,original_filename,extension,media_type,
                   size_bytes,source_size_bytes,sha256_original,sha256_current,
                   selected_capture_time,selected_capture_source,
                   capture_time_confidence,review_status,metadata_write_status,
                   created_at,updated_at
               )
               VALUES (?,?,?,?,?,'IMG_0001.JPG','.JPG','jpeg',
                       ?,?,'ORIGINAL-SHA','CURRENT-SHA',
                       NULL,NULL,'missing','required','not_requested',
                       '2026-10-03T12:00:00+00:00','2026-10-03T12:00:00+00:00')""",
            (
                job_id,
                family_id,
                original,
                relative,
                "shared_workspace",
                len(payload),
                len(payload),
            ),
        ).lastrowid)
    return family_id, file_id


def test_0331_naming_separates_normal_event_from_collection_year():
    naming = normalize_event_naming({
        "include_year": True,
        "include_time": True,
        "date_mode": "range",
        "no_event_label": "Unsortiert",
        "no_event_include_year": False,
    })
    assert naming["include_year"] is True
    assert naming["include_time"] is True
    assert naming["date_mode"] == "range"
    assert naming["no_event_include_year"] is False
    assert render_no_event_folder_name("2026-07", naming) == "07 - Unsortiert"

    naming["no_event_include_year"] = True
    assert render_no_event_folder_name("2026-07", naming) == "2026-07 - Unsortiert"


def test_0331_metadata_paths_never_create_technical_main_tree(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    paths = metadata_area_paths(
        area="general",
        workspace_root=workspace,
        library_id="main",
        create=True,
    )
    assert paths["root"] == workspace / "Metadatenkorrektur" / "Allgemein"
    assert paths["input_root"] == paths["root"]
    assert paths["output_root"] == paths["root"]
    assert not (workspace / "Metadatenkorrektur" / "Bibliothek" / "main").exists()

    library = metadata_area_paths(
        area="library",
        workspace_root=workspace,
        library_id="main",
        create=True,
    )
    assert library["input_root"] == workspace / "SD-Kartensicherungen" / "Ohne_Datum"
    assert library["output_root"] == workspace / "SD-Kartensicherungen"
    assert not library["input_root"].exists()


def test_0331_empty_legacy_metadata_tree_is_removed_but_user_file_is_kept(tmp_path: Path):
    workspace = tmp_path / "workspace"
    legacy = workspace / "Metadatenkorrektur" / "Bibliothek" / "main"
    (legacy / "Eingang").mkdir(parents=True)
    (legacy / "Ausgang").mkdir()

    metadata_area_paths(
        area="general",
        workspace_root=workspace,
        library_id="main",
        create=True,
    )
    assert not (workspace / "Metadatenkorrektur" / "Bibliothek").exists()

    legacy = workspace / "Metadatenkorrektur" / "Bibliothek" / "main" / "Eingang"
    legacy.mkdir(parents=True)
    protected = legacy / "nicht-loeschen.JPG"
    protected.write_bytes(b"user-data")
    metadata_area_paths(
        area="general",
        workspace_root=workspace,
        library_id="main",
        create=True,
    )
    assert protected.read_bytes() == b"user-data"


def test_0331_compose_has_no_separate_metadata_general_mount():
    compose = Path("compose.example.yaml").read_text(encoding="utf-8")
    assert "KAMERA_METADATA_GENERAL_ROOT" not in compose
    assert "BIBLIOTHEKAR_METADATA_GENERAL_DIR" not in compose
    assert "/metadata-general" not in compose


def test_0331_settings_use_collapsed_cards_and_compact_naming_controls():
    from app import ui_shell

    shell = ui_shell._shell_markup("workspace", "captures")
    assert '<details class="bk-settings-card" id="bk-folder-layout-settings">' in shell
    assert "<span>Normale Ereignisse</span>" in shell
    assert "<span>Sammelordner</span>" in shell
    assert 'id="bk-event-date-range" type="checkbox"' in shell
    assert 'id="bk-event-include-year" type="checkbox"' in shell
    assert 'id="bk-event-include-time" type="checkbox"' in shell
    assert 'id="bk-no-event-include-year" type="checkbox"' in shell
    assert "Bezeichnung für Sammelordner" in shell
    assert 'id="bk-event-naming-preview"' in shell
    assert '<details class="bk-library-card"' in ui_shell.BIBLIOTHEKAR_JS
    assert "bkUpdateSettingsPreview();" in ui_shell.BIBLIOTHEKAR_JS


def test_0331_metadata_page_uses_shell_and_second_header():
    html = apply_shell(
        METADATA_CORRECTION_HTML,
        active_area="metadata",
        subarea="library",
    )
    assert '<header class="bk-shell">' in html
    assert 'data-bk-area="metadata"' in html
    assert 'class="bk-workspace-subnav bk-metadata-subnav"' in html
    assert '/metadata-correction?area=library' in html
    assert '/metadata-correction?area=general' in html
    assert '/metadata-correction?area=multiple' in html
    assert "Mehrfachkorrektur" in html


def test_0331_library_correction_reintegrates_family_into_day_stock(
    tmp_path: Path,
    monkeypatch,
):
    database = tmp_path / "kamera.sqlite3"
    workspace = tmp_path / "workspace"
    central = workspace / "SD-Kartensicherungen"
    source = central / "Ohne_Datum" / "IMG_0001.JPG"
    source.parent.mkdir(parents=True)
    payload = b"camera-payload"
    source.write_bytes(payload)

    initialize_database(database)
    family_id, file_id = _insert_undated_family(
        database,
        payload=payload,
    )

    # Freeze the real physical hash into the test database.
    digest = metadata_correction._sha256(source)
    with database_connection(database) as connection:
        connection.execute(
            """UPDATE files
               SET sha256_original=?,sha256_current=?,source_size_bytes=NULL
               WHERE id=?""",
            (digest, digest, file_id),
        )

    def fake_analysis(root: Path, include_other: bool = False):
        root = Path(root)
        if root.name == "Ohne_Datum":
            relative = "IMG_0001.JPG"
            capture = None
            confidence = "missing"
        else:
            relative = "DCIM/IMG_0001.JPG"
            capture = "2026-07-20T14:15:30"
            confidence = "high"
        return {
            "files": [{
                "relative_path": relative,
                "filename": "IMG_0001.JPG",
                "family_key": "DCIM/IMG_0001",
                "media_type": "jpeg",
                "selected_capture_time": capture,
                "selected_capture_source": "EXIF:DateTimeOriginal" if capture else None,
                "capture_time_confidence": confidence,
                "review_required": capture is None,
                "camera_make": "FUJIFILM",
                "camera_model": "X-E5",
                "metadata_candidates": [],
            }],
            "families": [{
                "family_key": "DCIM/IMG_0001",
                "selected_capture_time": capture,
                "capture_time_confidence": confidence,
            }],
        }

    monkeypatch.setattr(metadata_correction, "analyze_tree", fake_analysis)
    monkeypatch.setattr(
        metadata_correction,
        "write_metadata_datetime",
        lambda path, media_type, value: None,
    )
    monkeypatch.setattr(
        metadata_correction,
        "verify_metadata_datetime",
        lambda path, expected: {
            "expected_datetime": expected,
            "matching_tags": [{"tag": "EXIF:DateTimeOriginal", "value": expected}],
            "observed_tags": [],
        },
    )

    scan = scan_metadata_area(
        area="library",
        workspace_root=workspace,
        library_id="library-a",
        database_path=database,
        library_name="Kamera",
        allowed_job_ids={"JOB"},
    )
    assert scan["summary"]["family_count"] == 1
    assert scan["files"][0]["family_id"] == family_id
    assert scan["files"][0]["library_name"] == "Kamera"

    task = create_metadata_correction(
        database,
        area="library",
        relative_path="Ohne_Datum/IMG_0001.JPG",
        family_id=family_id,
        proposed_datetime="2026-07-20T14:15:30",
        workspace_root=workspace,
        library_id="library-a",
        library_name="Kamera",
        allowed_job_ids={"JOB"},
    )
    completed = apply_metadata_correction(
        database,
        str(task["id"]),
        workspace_root=workspace,
        library_id="library-a",
    )
    assert completed["status"] == "completed"
    assert not source.exists()

    with database_connection(database) as connection:
        family = connection.execute(
            "SELECT selected_capture_time,capture_time_confidence FROM file_families WHERE id=?",
            (family_id,),
        ).fetchone()
        file_row = connection.execute(
            """SELECT current_relative_path,size_bytes,source_size_bytes,
                      selected_capture_time,review_status,metadata_write_status
               FROM files WHERE id=?""",
            (file_id,),
        ).fetchone()

    assert family["selected_capture_time"] == "2026-07-20T14:15:30"
    assert family["capture_time_confidence"] == "high"
    assert file_row["selected_capture_time"] == "2026-07-20T14:15:30"
    assert file_row["review_status"] == "corrected"
    assert file_row["metadata_write_status"] == "written"
    assert file_row["source_size_bytes"] == len(payload)
    assert not str(file_row["current_relative_path"]).startswith("Ohne_Datum/")
    destination = central / str(file_row["current_relative_path"])
    assert destination.is_file()
    assert destination.read_bytes() == payload


def test_0331_corrected_family_state_is_propagated_without_touching_source_size(
    tmp_path: Path,
):
    source_db = tmp_path / "source.sqlite3"
    target_db = tmp_path / "target.sqlite3"
    for database in (source_db, target_db):
        initialize_database(database)
        family_id, file_id = _insert_undated_family(database)
        with database_connection(database) as connection:
            connection.execute(
                "UPDATE files SET sha256_original='ORIGINAL',sha256_current='ORIGINAL' WHERE id=?",
                (file_id,),
            )

    with database_connection(source_db) as connection:
        connection.execute(
            """UPDATE file_families
               SET selected_capture_time='2026-07-20T14:15:30',
                   capture_time_confidence='high',status='complete'
               WHERE job_id='JOB' AND family_key='DCIM/IMG_0001'"""
        )
        connection.execute(
            """UPDATE files
               SET current_relative_path='2026/2026-07-20/20260720_141530_Fuji-X-E5.JPG',
                   size_bytes=99,sha256_current='NEW',
                   selected_capture_time='2026-07-20T14:15:30',
                   selected_capture_source='metadata_correction',
                   capture_time_confidence='high',
                   review_status='corrected',metadata_write_status='written'
               WHERE job_id='JOB'"""
        )

    result = propagate_corrected_family(
        source_db,
        [source_db, target_db],
        job_id="JOB",
        family_key="DCIM/IMG_0001",
    )
    assert result["updated_databases"] == 1
    assert result["updated_files"] == 1

    with database_connection(target_db) as connection:
        row = connection.execute(
            """SELECT f.current_relative_path,f.size_bytes,f.source_size_bytes,
                      f.sha256_current,f.selected_capture_time,
                      ff.selected_capture_time AS family_time
               FROM files f
               JOIN file_families ff ON ff.id=f.family_id
               WHERE f.job_id='JOB'"""
        ).fetchone()
    assert row["current_relative_path"].startswith("2026/2026-07-20/")
    assert row["size_bytes"] == 99
    assert row["source_size_bytes"] == len(b"camera-payload")
    assert row["sha256_current"] == "NEW"
    assert row["selected_capture_time"] == "2026-07-20T14:15:30"
    assert row["family_time"] == "2026-07-20T14:15:30"

def test_0331_reimport_duplicate_origin_keeps_original_source_size(tmp_path: Path):
    database = tmp_path / "kamera.sqlite3"
    initialize_database(database)
    _family_id, file_id = _insert_undated_family(database, payload=b"original-size")
    with database_connection(database) as connection:
        connection.execute(
            """UPDATE jobs
               SET state='completed',stage='completed',
                   finished_at='2026-10-03T12:30:00+00:00',
                   updated_at='2026-10-03T12:30:00+00:00'
               WHERE id='JOB'"""
        )
        connection.execute(
            """UPDATE files
               SET source_size_bytes=?,
                   size_bytes=?,
                   sha256_original='SOURCE-HASH',
                   sha256_current='CORRECTED-HASH'
               WHERE id=?""",
            (len(b"original-size"), 999, file_id),
        )

    origins = list_imported_media_origins(database)
    assert len(origins) == 1
    assert origins[0]["size_bytes"] == len(b"original-size")
    assert origins[0]["sha256"] == "SOURCE-HASH"

