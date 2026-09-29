from __future__ import annotations

import hashlib
from pathlib import Path

from app.archive_transfer import verify_event_archive
from app.database import database_connection, initialize_database
from app.event_change_request import get_event_change_files, propose_event_change
from app.event_inventory import scan_event_inventory
from app.ssd_release import release_event_ssd


NOW = "2026-09-23T18:00:00+00:00"


def seed_job(connection, job_id: str = "j") -> None:
    connection.execute(
        """INSERT INTO jobs(id,kind,trigger_type,state,stage,created_at,updated_at)
           VALUES (?,'sd_import','manual','completed','done',?,?)""",
        (job_id, NOW, NOW),
    )


def seed_event(
    connection,
    *,
    status: str,
    event_id: str = "e",
    job_id: str = "j",
    folder: str = "07-23 - Trip",
) -> None:
    connection.execute(
        """INSERT INTO events(
               id,job_id,parent_event_id,event_level,name,start_datetime,end_datetime,
               uses_time_range,folder_name,status,created_at,updated_at,event_kind,
               preserve_day_folders,revision,applied_at,archived_at,resort_required,
               time_model_version,timeline_model
           ) VALUES (?,?,NULL,'parent','Trip','2026-07-23T00:00:00',
                     '2026-07-23T23:59:59',0,?,?,?,?, 'event',0,1,?,?,0,2,'continuous')""",
        (
            event_id,
            job_id,
            folder,
            status,
            NOW,
            NOW,
            NOW if status in {"applied", "archived"} else None,
            NOW if status == "archived" else None,
        ),
    )


def seed_family(connection, *, content: bytes, current_path: str) -> tuple[int, int]:
    family_id = int(
        connection.execute(
            """INSERT INTO file_families(
                   job_id,family_key,original_stem,status,selected_capture_time,
                   capture_time_confidence
               ) VALUES ('j','A','A','complete','2026-07-23T12:00:00','high')"""
        ).lastrowid
    )
    file_id = seed_file_for_family(
        connection,
        family_id=family_id,
        content=content,
        current_path=current_path,
        filename="A.JPG",
    )
    connection.execute(
        """INSERT INTO event_assignments(
               event_id,family_id,file_id,assignment_source,created_at
           ) VALUES ('e',?,NULL,'manual',?)""",
        (family_id, NOW),
    )
    return family_id, file_id


def seed_file_for_family(
    connection,
    *,
    family_id: int,
    content: bytes,
    current_path: str,
    filename: str,
) -> int:
    digest = hashlib.sha256(content).hexdigest()
    return int(
        connection.execute(
            """INSERT INTO files(
                   job_id,family_id,original_relative_path,current_relative_path,
                   original_filename,extension,media_type,size_bytes,
                   sha256_original,sha256_current,selected_capture_time,
                   selected_capture_source,capture_time_confidence,review_status,
                   metadata_write_status,created_at,updated_at,current_root_kind
               ) VALUES ('j',?, ?, ?, ?, '.JPG','jpeg',?,?,?,?, 'DateTimeOriginal',
                         'high','not_required','not_requested',?,?,'camera_archive')""",
            (
                family_id,
                "DCIM/" + filename,
                current_path,
                filename,
                len(content),
                digest,
                digest,
                "2026-07-23T12:00:00",
                NOW,
                NOW,
            ),
        ).lastrowid
    )


def test_0263_archive_inventory_tracks_real_location_and_accepts_later_manual_delete(tmp_path):
    db = tmp_path / "db.sqlite3"
    initialize_database(db)
    archive = tmp_path / "archive"
    camera = b"camera-a"
    with database_connection(db) as connection:
        seed_job(connection)
        seed_event(connection, status="archived")
        family_id, file_id = seed_family(
            connection,
            content=camera,
            current_path="2026/07-23 - Trip/Alle/A.JPG",
        )

    event_root = archive / "2026" / "07-23 - Trip"
    sorted_dir = event_root / "Sortiert"
    sorted_dir.mkdir(parents=True)
    (sorted_dir / "A.JPG").write_bytes(camera)
    (sorted_dir / "A.xmp").write_text("<xmp/>", encoding="utf-8")

    first = scan_event_inventory(
        db,
        archive,
        "j",
        "e",
        root_kind="camera_archive",
        persist=True,
        update_known_file_locations=True,
    )
    camera_row = next(row for row in first["files"] if row["asset_kind"] == "camera_original")
    xmp_row = next(row for row in first["files"] if row["asset_kind"] == "xmp")
    assert camera_row["relative_path"].endswith("/Sortiert/A.JPG")
    assert xmp_row["family_id"] == family_id
    assert xmp_row["source_file_id"] == file_id

    with database_connection(db) as connection:
        stored = connection.execute(
            "SELECT current_relative_path FROM files WHERE id=?",
            (file_id,),
        ).fetchone()[0]
    assert stored.endswith("/Sortiert/A.JPG")

    # Manuelle spätere Archivlöschung ist kein Integritätsfehler. Der nächste
    # Scan bildet nur den neuen IST-Bestand ab.
    (sorted_dir / "A.JPG").unlink()
    second = scan_event_inventory(
        db,
        archive,
        "j",
        "e",
        root_kind="camera_archive",
        persist=True,
        update_known_file_locations=True,
    )
    assert file_id in second["summary"]["missing_known_file_ids"]
    assert all(row.get("known_file_id") != file_id for row in second["files"])


def test_0263_archived_edit_rescans_sortiert_xmp_export_and_ignores_deleted_db_file(tmp_path, monkeypatch):
    db = tmp_path / "db.sqlite3"
    initialize_database(db)
    archive = tmp_path / "archive"
    camera = b"camera-a"
    with database_connection(db) as connection:
        seed_job(connection)
        seed_event(connection, status="archived")
        family_id, file_id = seed_family(
            connection,
            content=camera,
            current_path="2026/07-23 - Trip/Alle/A.JPG",
        )
        missing_file_id = seed_file_for_family(
            connection,
            family_id=family_id,
            content=b"deleted-camera-member",
            current_path="2026/07-23 - Trip/Alle/B.JPG",
            filename="B.JPG",
        )

    event_root = archive / "2026" / "07-23 - Trip"
    (event_root / "Sortiert").mkdir(parents=True)
    (event_root / "Export").mkdir(parents=True)
    (event_root / "Sortiert" / "A.JPG").write_bytes(camera)
    (event_root / "Sortiert" / "A.xmp").write_text("<xmp/>", encoding="utf-8")
    (event_root / "Export" / "final.jpg").write_bytes(b"exported-jpeg")

    def fake_analyze_tree(_root):
        return {
            "files": [
                {
                    "relative_path": "Export/final.jpg",
                    "media_type": "jpeg",
                    "selected_capture_time": "2026-07-23T12:00:00+02:00",
                    "selected_capture_source": "EXIF:ExifIFD:DateTimeOriginal",
                    "capture_time_confidence": "high",
                }
            ]
        }

    monkeypatch.setattr("app.event_inventory.analyze_tree", fake_analyze_tree)

    preview = {
        "event_kind": "event",
        "event_name": "Trip neu",
        "parent_folder": "07-23 - Trip neu",
        "start_date": "2026-07-23",
        "end_date": "2026-07-23",
        "start_time": "00:00",
        "end_time": "23:59",
        "uses_time_range": False,
        "preserve_day_folders": False,
        "selected_family_ids": [family_id],
        "selected_day_keys": ["2026-07-23"],
    }
    result = propose_event_change(
        db,
        "j",
        "e",
        preview,
        event_name="Trip neu",
        archive_root=archive,
    )
    rows = get_event_change_files(db, result["change_request_id"])

    camera_rows = [row for row in rows if row["review_kind"] == "camera"]
    asset_rows = [row for row in rows if row["review_kind"] == "asset"]
    assert len(camera_rows) == 1
    assert camera_rows[0]["file_id"] == file_id
    assert camera_rows[0]["old_path"].endswith("/Sortiert/A.JPG")
    assert camera_rows[0]["new_path"].endswith("/07-23 - Trip neu/Sortiert/A.JPG")
    assert all(row.get("file_id") != missing_file_id for row in camera_rows)

    xmp = next(row for row in asset_rows if row["asset_kind"] == "xmp")
    export = next(row for row in asset_rows if row["asset_kind"] == "export")
    assert xmp["new_path"].endswith("/07-23 - Trip neu/Sortiert/A.xmp")
    assert export["new_path"].endswith("/07-23 - Trip neu/Export/final.jpg")
    assert export["action"] == "move"


def test_0263_archive_verification_finds_camera_original_anywhere_in_event(tmp_path):
    db = tmp_path / "db.sqlite3"
    initialize_database(db)
    archive = tmp_path / "archive"
    camera = b"camera-a"
    with database_connection(db) as connection:
        seed_job(connection)
        seed_event(connection, status="applied")
        _family_id, file_id = seed_family(
            connection,
            content=camera,
            current_path="2026/07-23 - Trip/Alle/A.JPG",
        )

    target = archive / "2026" / "07-23 - Trip" / "Sortiert" / "A.JPG"
    target.parent.mkdir(parents=True)
    target.write_bytes(camera)

    result = verify_event_archive(db, archive, "j", "e")
    assert result["verified"] is False
    assert result["missing_file_count"] == 1
    assert result["files"][0]["status"] == "missing"
    assert result["files"][0]["expected_relative_path"].endswith("/Alle/A.JPG")
    assert "IST:" in result["files"][0]["error_message"]
    assert "SOLL:" in result["files"][0]["error_message"]
    assert result["files"][0]["file_id"] == file_id


def test_0263_ssd_release_protects_camera_xmp_and_export_independent_of_subfolder(tmp_path):
    db = tmp_path / "db.sqlite3"
    initialize_database(db)
    workspace = tmp_path / "workspace"
    archive = tmp_path / "archive"
    camera = b"camera-a"
    xmp = b"<xmp/>"
    export = b"finished-export"

    with database_connection(db) as connection:
        seed_job(connection)
        seed_event(connection, status="applied")
        _family_id, file_id = seed_family(
            connection,
            content=camera,
            current_path="2026/07-23 - Trip/Alle/A.JPG",
        )
        connection.execute(
            "UPDATE files SET current_root_kind='shared_workspace' WHERE id=?",
            (file_id,),
        )

    work_event = workspace / "Arbeitsbereich" / "2026" / "07-23 - Trip"
    (work_event / "Sortiert").mkdir(parents=True)
    (work_event / "Export").mkdir(parents=True)
    (work_event / "Sortiert" / "A.JPG").write_bytes(camera)
    (work_event / "Sortiert" / "A.xmp").write_bytes(xmp)
    (work_event / "Export" / "final.jpg").write_bytes(export)

    archive_event = archive / "2026" / "07-23 - Trip"
    (archive_event / "Alle").mkdir(parents=True)
    (archive_event / "Sortiert").mkdir(parents=True)
    (archive_event / "Export").mkdir(parents=True)
    # Der Ort des Kameraoriginals darf zwischen SSD und Archiv verschieden sein.
    (archive_event / "Alle" / "A.JPG").write_bytes(camera)
    (archive_event / "Sortiert" / "A.xmp").write_bytes(xmp)
    (archive_event / "Export" / "final.jpg").write_bytes(export)

    result = release_event_ssd(db, workspace, archive, "j", "e")
    assert result["released"] is True
    assert result["details"]["camera_file_count"] == 1
    assert result["details"]["asset_file_count"] == 2
    assert not (work_event / "Sortiert" / "A.JPG").exists()
    assert not (work_event / "Sortiert" / "A.xmp").exists()
    assert not (work_event / "Export" / "final.jpg").exists()

    with database_connection(db) as connection:
        file_row = connection.execute(
            "SELECT current_relative_path,current_root_kind FROM files WHERE id=?",
            (file_id,),
        ).fetchone()
        asset_rows = connection.execute(
            """SELECT asset_kind,status FROM event_ssd_release_assets
               WHERE release_id=? ORDER BY asset_kind""",
            (result["id"],),
        ).fetchall()
    assert tuple(file_row) == (
        "2026/07-23 - Trip/Alle/A.JPG",
        "camera_archive",
    )
    assert {tuple(row) for row in asset_rows} == {
        ("export", "deleted"),
        ("xmp", "deleted"),
    }


def test_0263_xmp_links_to_family_when_raf_and_jpeg_share_stem(tmp_path):
    db = tmp_path / "db.sqlite3"
    initialize_database(db)
    archive = tmp_path / "archive"
    jpg = b"camera-jpg"
    raf = b"camera-raf"
    with database_connection(db) as connection:
        seed_job(connection)
        seed_event(connection, status="archived")
        family_id, jpg_id = seed_family(
            connection,
            content=jpg,
            current_path="2026/07-23 - Trip/Sortiert/A.JPG",
        )
        raf_id = seed_file_for_family(
            connection,
            family_id=family_id,
            content=raf,
            current_path="2026/07-23 - Trip/Sortiert/A.RAF",
            filename="A.RAF",
        )

    sorted_dir = archive / "2026" / "07-23 - Trip" / "Sortiert"
    sorted_dir.mkdir(parents=True)
    (sorted_dir / "A.JPG").write_bytes(jpg)
    (sorted_dir / "A.RAF").write_bytes(raf)
    (sorted_dir / "A.xmp").write_text("<xmp/>", encoding="utf-8")

    inventory = scan_event_inventory(
        db,
        archive,
        "j",
        "e",
        root_kind="camera_archive",
        persist=True,
        update_known_file_locations=True,
    )
    xmp = next(row for row in inventory["files"] if row["asset_kind"] == "xmp")
    assert xmp["family_id"] == family_id
    assert xmp["source_file_id"] is None
    assert xmp["selected_capture_time"].startswith("2026-07-23T12:00:00")
    assert {row["known_file_id"] for row in inventory["files"] if row["known_file_id"]} == {jpg_id, raf_id}


def test_0263_export_create_date_is_not_mistaken_for_capture_time(tmp_path, monkeypatch):
    db = tmp_path / "db.sqlite3"
    initialize_database(db)
    archive = tmp_path / "archive"
    with database_connection(db) as connection:
        seed_job(connection)
        seed_event(connection, status="archived")

    export_dir = archive / "2026" / "07-23 - Trip" / "Export"
    export_dir.mkdir(parents=True)
    (export_dir / "final.jpg").write_bytes(b"export")

    monkeypatch.setattr(
        "app.event_inventory.analyze_tree",
        lambda _root: {
            "files": [{
                "relative_path": "Export/final.jpg",
                "media_type": "jpeg",
                "selected_capture_time": "2026-09-23T20:00:00+02:00",
                "selected_capture_source": "EXIF:ExifIFD:CreateDate",
                "capture_time_confidence": "high",
            }]
        },
    )

    inventory = scan_event_inventory(
        db,
        archive,
        "j",
        "e",
        root_kind="camera_archive",
        persist=True,
        update_known_file_locations=False,
    )
    export = next(row for row in inventory["files"] if row["asset_kind"] == "export")
    assert export["selected_capture_time"] is None
    assert export["selected_capture_source"] is None
    assert export["capture_time_confidence"] == "missing"


def test_0263_export_datetimeoriginal_wins_over_export_createdate(tmp_path, monkeypatch):
    db = tmp_path / "db.sqlite3"
    initialize_database(db)
    archive = tmp_path / "archive"
    with database_connection(db) as connection:
        seed_job(connection)
        seed_event(connection, status="archived")

    export_dir = archive / "2026" / "07-23 - Trip" / "Export"
    export_dir.mkdir(parents=True)
    (export_dir / "final.jpg").write_bytes(b"export")

    monkeypatch.setattr(
        "app.event_inventory.analyze_tree",
        lambda _root: {
            "files": [{
                "relative_path": "Export/final.jpg",
                "media_type": "jpeg",
                "selected_capture_time": "2026-07-23T12:00:00+02:00",
                "selected_capture_source": "EXIF:ExifIFD:DateTimeOriginal",
                "capture_time_confidence": "conflict",
                "metadata_candidates": [
                    {
                        "tag_name": "EXIF:ExifIFD:DateTimeOriginal",
                        "normalized_datetime": "2026-07-23T12:00:00+02:00",
                        "usable": True,
                    },
                    {
                        "tag_name": "EXIF:ExifIFD:CreateDate",
                        "normalized_datetime": "2026-09-23T20:00:00+02:00",
                        "usable": True,
                    },
                ],
            }]
        },
    )

    inventory = scan_event_inventory(
        db,
        archive,
        "j",
        "e",
        root_kind="camera_archive",
        persist=True,
        update_known_file_locations=False,
    )
    export = next(row for row in inventory["files"] if row["asset_kind"] == "export")
    assert export["selected_capture_time"] == "2026-07-23T12:00:00+02:00"
    assert export["selected_capture_source"] == "EXIF:ExifIFD:DateTimeOriginal"
    assert export["capture_time_confidence"] == "high"
