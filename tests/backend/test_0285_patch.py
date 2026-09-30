from __future__ import annotations

from pathlib import Path

from app.database import database_connection
from app.event_change_apply import confirm_event_change, verify_event_change
from app.event_change_request import get_event_change_files, propose_event_change
from app.event_inventory import scan_event_inventory
from app.event_layout import (
    get_event_layout,
    layout_role_paths,
    normalize_layout,
    update_event_layout,
)
from tests.backend.test_0283_structure_simplification import (
    NOW,
    _archived_layout_preview,
    _seed_archived_layout_event,
)


def test_0285_layout_export_role_is_optional_and_can_move_from_legacy_export():
    no_role = normalize_layout({
        "version": 2,
        "nodes": [
            {"id": "legacy-alle", "name": "Alle", "children": []},
            {"id": "legacy-export", "name": "Export", "children": []},
        ],
    })
    assert layout_role_paths(no_role, "export") == []

    master = normalize_layout({
        "version": 2,
        "nodes": [
            {"id": "legacy-alle", "name": "Alle", "children": []},
            {"id": "legacy-export", "name": "Export", "children": []},
            {"id": "master", "name": "Master", "role": "export", "children": []},
        ],
    })
    assert layout_role_paths(master, "export") == ["Master"]


def test_0285_arbitrary_image_is_advisory_but_configured_master_is_export(tmp_path: Path):
    db = tmp_path / "db.sqlite3"
    workspace = tmp_path / "workspace"
    archive = tmp_path / "archive"
    workspace.mkdir()
    archive.mkdir()
    event_root, family_id, state = _seed_archived_layout_event(
        db, workspace, archive, structure_enabled=True
    )

    # Completely unrelated user image outside the configured export role.
    (event_root / "Bibliothekar WebApp IOS MockUp 3.png").write_bytes(b"mockup")

    first = scan_event_inventory(
        db,
        archive,
        "j",
        "e",
        root_kind="camera_archive",
        persist=True,
        update_known_file_locations=True,
    )
    foreign = next(
        row for row in first["files"]
        if row["filename"] == "Bibliothekar WebApp IOS MockUp 3.png"
    )
    assert foreign["family_id"] is None
    assert foreign["asset_kind"] != "export"

    proposed = propose_event_change(
        db,
        "j",
        "e",
        _archived_layout_preview(family_id, state, True),
        event_name="Trip",
        archive_root=archive,
    )
    rows = get_event_change_files(db, proposed["change_request_id"])
    foreign_review = next(
        row for row in rows
        if row["old_path"].endswith("/Bibliothekar WebApp IOS MockUp 3.png")
    )
    assert foreign_review["advisory"] is True
    assert foreign_review["advisory_reason"] == "unmanaged_user_file"

    confirm_event_change(db, proposed["change_request_id"], archive)
    verified = verify_event_change(db, proposed["change_request_id"], archive)
    assert verified["complete"] is True
    assert verified["verified_file_count"] == verified["file_count"]
    assert verified["advisory_count"] == 1

    # A custom folder can carry the export role even though it is not named Export.
    with database_connection(db) as connection:
        current = get_event_layout(connection, "e")
        custom = {
            "version": 2,
            "nodes": [
                {"id": "legacy-alle", "name": "Alle", "children": []},
                {"id": "legacy-sortiert", "name": "Sortiert", "children": []},
                {"id": "master", "name": "Master", "role": "export", "children": []},
            ],
        }
        update_event_layout(
            connection,
            "e",
            structure_enabled=True,
            input_path=current["input_path"],
            layout=custom,
            updated_at=NOW,
        )

    (event_root / "Export").rename(event_root / "Master")
    (event_root / "Master" / "freie-variante.png").write_bytes(b"master-export")
    second = scan_event_inventory(
        db,
        archive,
        "j",
        "e",
        root_kind="camera_archive",
        persist=True,
        update_known_file_locations=False,
    )
    master_asset = next(
        row for row in second["files"] if row["filename"] == "freie-variante.png"
    )
    assert master_asset["asset_kind"] == "export"


def test_0285_lightroom_export_variants_share_camera_family(tmp_path: Path):
    db = tmp_path / "db.sqlite3"
    workspace = tmp_path / "workspace"
    archive = tmp_path / "archive"
    workspace.mkdir()
    archive.mkdir()
    event_root, family_id, _state = _seed_archived_layout_event(
        db, workspace, archive, structure_enabled=True
    )

    for name, payload in [
        ("A_Export.jpg", b"variant-0"),
        ("A_Export_1.jpg", b"variant-1"),
        ("A_Export_2.jpg", b"variant-2"),
    ]:
        (event_root / "Export" / name).write_bytes(payload)

    inventory = scan_event_inventory(
        db,
        archive,
        "j",
        "e",
        root_kind="camera_archive",
        persist=True,
        update_known_file_locations=False,
    )
    variants = [
        row for row in inventory["files"]
        if row["filename"] in {"A_Export.jpg", "A_Export_1.jpg", "A_Export_2.jpg"}
    ]
    assert len(variants) == 3
    assert all(row["asset_kind"] == "export" for row in variants)
    assert all(row["family_id"] == family_id for row in variants)


def test_0285_identical_xmp_and_export_copies_are_advisory_and_deletable(tmp_path: Path):
    db = tmp_path / "db.sqlite3"
    workspace = tmp_path / "workspace"
    archive = tmp_path / "archive"
    workspace.mkdir()
    archive.mkdir()
    event_root, family_id, state = _seed_archived_layout_event(
        db, workspace, archive, structure_enabled=True
    )

    # Two byte-identical copies per managed derived role.
    (event_root / "Alle" / "A Kopie.xmp").write_bytes(b"xmp-a")
    (event_root / "Export" / "A Kopie.jpg").write_bytes(b"export-a")

    proposed = propose_event_change(
        db,
        "j",
        "e",
        _archived_layout_preview(family_id, state, True),
        event_name="Trip",
        archive_root=archive,
    )
    cr_id = proposed["change_request_id"]
    rows = get_event_change_files(db, cr_id)
    duplicate_rows = [
        row for row in rows
        if row["review_kind"] == "asset"
        and row.get("advisory_reason") == "redundant_duplicate"
    ]
    assert len(duplicate_rows) == 2
    assert {row["asset_kind"] for row in duplicate_rows} == {"xmp", "export"}

    # Delete the canonical names and leave only the copy names. SHA-256 and
    # collision aliases must allow the remaining copies to satisfy the managed
    # representation, while the advisory copies never block completion.
    (event_root / "Alle" / "A.xmp").unlink()
    (event_root / "Export" / "A.jpg").unlink()

    confirm_event_change(db, cr_id, archive)
    verified = verify_event_change(db, cr_id, archive)
    assert verified["complete"] is True
    assert verified["verified_file_count"] == verified["file_count"]
    assert verified["advisory_count"] == 2
