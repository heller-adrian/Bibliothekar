"""0.27.7: dynamischer Mischbestand aus Kameraoriginal, XMP und Export."""
from __future__ import annotations

from pathlib import Path

from app.archive_transfer import verify_event_archive
from app.database import database_connection, initialize_database, list_job_events
from app.event_inventory import scan_event_inventory
from app.sort_plan import build_event_sort_plan
from tests.backend.test_0263_event_inventory import (
    NOW,
    seed_event,
    seed_file_for_family,
    seed_job,
)


def _seed_family(connection, *, current_path: str, root_kind: str) -> tuple[int, int]:
    family_id = int(
        connection.execute(
            """INSERT INTO file_families(
                   job_id,family_key,original_stem,status,selected_capture_time,
                   capture_time_confidence
               ) VALUES (
                   'j','IMG_0001','IMG_0001','complete',
                   '2026-07-23T12:00:00','high'
               )"""
        ).lastrowid
    )
    file_id = seed_file_for_family(
        connection,
        family_id=family_id,
        content=b"camera-original",
        current_path=current_path,
        filename="IMG_0001.JPG",
    )
    connection.execute(
        """UPDATE files SET current_root_kind=? WHERE id=?""",
        (root_kind, file_id),
    )
    connection.execute(
        """INSERT INTO event_assignments(
               event_id,family_id,file_id,assignment_source,created_at
           ) VALUES ('e',?,NULL,'date_range',?)""",
        (family_id, NOW),
    )
    return family_id, file_id


def _write_mixed_event(root: Path, *, folder: str = "07-23 - Trip") -> None:
    event = root / "2026" / folder
    (event / "Alle").mkdir(parents=True, exist_ok=True)
    (event / "Export").mkdir(parents=True, exist_ok=True)
    (event / "Alle" / "IMG_0001.JPG").write_bytes(b"camera-original")
    (event / "Alle" / "IMG_0001.xmp").write_bytes(b"<xmp/>")
    (event / "Export" / "20260723_120000_IMG_0001.jpg").write_bytes(
        b"rendered-export"
    )


def test_0277_export_uses_filename_fallback_and_family_correction(tmp_path, monkeypatch):
    db = tmp_path / "db.sqlite3"
    initialize_database(db)
    archive = tmp_path / "archive"
    with database_connection(db) as connection:
        seed_job(connection)
        seed_event(connection, status="archived")
        family_id, _file_id = _seed_family(
            connection,
            current_path="2026/07-23 - Trip/Alle/IMG_0001.JPG",
            root_kind="camera_archive",
        )

    event = archive / "2026" / "07-23 - Trip"
    (event / "Alle").mkdir(parents=True)
    (event / "Export").mkdir(parents=True)
    (event / "Alle" / "IMG_0001.JPG").write_bytes(b"camera-original")
    # Falscher Schema-Zeitstempel, aber eindeutiger Kameraname:
    # die Familienzeit muss den Export korrigieren.
    (event / "Export" / "20260723_140000_IMG_0001.jpg").write_bytes(b"named")
    # Kein Kameraname: der kanonische Zeitstempel bleibt letzter Fallback.
    (event / "Export" / "20260723_120000_final.jpg").write_bytes(b"fallback")

    monkeypatch.setattr(
        "app.event_inventory.analyze_tree",
        lambda _root: {
            "files": [
                {
                    "relative_path": "Export/20260723_140000_IMG_0001.jpg",
                    "media_type": "jpeg",
                    "selected_capture_time": "2026-09-29T17:00:00+02:00",
                    "selected_capture_source": "EXIF:ExifIFD:CreateDate",
                    "capture_time_confidence": "high",
                },
                {
                    "relative_path": "Export/20260723_120000_final.jpg",
                    "media_type": "jpeg",
                    "selected_capture_time": None,
                    "selected_capture_source": None,
                    "capture_time_confidence": "missing",
                },
            ]
        },
    )

    inventory = scan_event_inventory(
        db, archive, "j", "e",
        root_kind="camera_archive",
        persist=True,
        update_known_file_locations=False,
    )
    named = next(
        row for row in inventory["files"]
        if row["filename"] == "20260723_140000_IMG_0001.jpg"
    )
    fallback = next(
        row for row in inventory["files"]
        if row["filename"] == "20260723_120000_final.jpg"
    )

    assert named["family_id"] == family_id
    assert named["selected_capture_time"] == "2026-07-23T12:00:00"
    assert named["selected_capture_source"] == "filename_family_correction"
    assert named["capture_time_confidence"] == "high"

    assert fallback["family_id"] is None
    assert fallback["selected_capture_time"] == "2026-07-23T12:00:00"
    assert fallback["selected_capture_source"] == "filename_schema"
    assert fallback["capture_time_confidence"] == "medium"


def test_0277_applied_archive_verification_counts_and_journals_xmp_export(
    tmp_path, monkeypatch
):
    db = tmp_path / "db.sqlite3"
    initialize_database(db)
    workspace = tmp_path / "workspace"
    work = workspace / "Arbeitsbereich"
    archive = tmp_path / "archive"

    with database_connection(db) as connection:
        seed_job(connection)
        seed_event(connection, status="applied")
        _seed_family(
            connection,
            current_path="2026/07-23 - Trip/Alle/IMG_0001.JPG",
            root_kind="shared_workspace",
        )

    _write_mixed_event(work)
    _write_mixed_event(archive)
    monkeypatch.setattr(
        "app.event_inventory.analyze_tree",
        lambda _root: {"files": []},
    )

    result = verify_event_archive(
        db, archive, "j", "e", workspace_path=workspace
    )
    assert result["verified"] is True
    assert result["file_count"] == 3
    assert result["camera_file_count"] == 1
    assert result["asset_file_count"] == 2
    assert result["verified_file_count"] == 3
    assert {row["asset_kind"] for row in result["assets"]} == {"xmp", "export"}

    with database_connection(db) as connection:
        journal = connection.execute(
            """SELECT asset_kind,status
               FROM event_archive_verification_assets
               WHERE verification_id=?
               ORDER BY asset_kind""",
            (result["id"],),
        ).fetchall()
    assert [(row["asset_kind"], row["status"]) for row in journal] == [
        ("export", "verified"),
        ("xmp", "verified"),
    ]

    event = next(row for row in list_job_events(db, "j") if row["id"] == "e")
    assert event["assigned_file_count"] == 3


def test_0277_reapply_plan_keeps_xmp_with_camera_and_export_in_export_branch(
    tmp_path, monkeypatch
):
    db = tmp_path / "db.sqlite3"
    initialize_database(db)
    workspace = tmp_path / "workspace"
    work = workspace / "Arbeitsbereich"

    with database_connection(db) as connection:
        seed_job(connection)
        connection.execute(
            """UPDATE jobs
               SET operation='folder_import', stage='event_sort_applied',
                   source_volume_label='TEST'
               WHERE id='j'"""
        )
        seed_event(connection, status="applied")
        connection.execute("UPDATE events SET resort_required=1 WHERE id='e'")
        _seed_family(
            connection,
            current_path="2026/07-23 - Trip/Alle/IMG_0001.JPG",
            root_kind="shared_workspace",
        )

    _write_mixed_event(work)
    monkeypatch.setattr(
        "app.event_inventory.analyze_tree",
        lambda _root: {"files": []},
    )

    plan = build_event_sort_plan(
        db, "j", "e", workspace, allow_reapply=True
    )
    assert plan["summary"]["ready"] is True
    assert plan["summary"]["file_count"] == 3
    assert plan["summary"]["asset_count"] == 2

    assets = {row["asset_kind"]: row for row in plan["assets"]}
    assert assets["xmp"]["destination_relative_path"].endswith(
        "/07-23 - Trip/Alle/IMG_0001.xmp"
    )
    assert assets["export"]["destination_relative_path"].endswith(
        "/07-23 - Trip/Export/20260723_120000_IMG_0001.jpg"
    )
