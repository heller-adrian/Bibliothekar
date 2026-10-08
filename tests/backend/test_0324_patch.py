from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from app import main, ui_shell
from app.database import create_job, database_connection, initialize_database
from app.event_change_request import (
    EventChangeRequestError,
    propose_archived_event_deletion,
)
from app.folder_import import quick_source_signature
from app.global_stock import (
    project_import_job,
    synchronize_central_stock_projections,
)
from app.pipeline import source_manifest
from tests.backend.test_0271_archive_assistant import _seed
from tests.backend.test_0311_global_stock import _insert_family_file, NOW


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_0324_source_filter_excludes_macos_trash_and_metadata_files(tmp_path: Path):
    source = tmp_path / "sd"
    real = source / "DCIM" / "100_FUJI" / "A.JPG"
    trash = source / ".Trashes" / "502" / "A.JPG"
    sidecar = source / "DCIM" / "100_FUJI" / "._A.JPG"
    ds_store = source / ".DS_Store"

    real.parent.mkdir(parents=True)
    trash.parent.mkdir(parents=True)
    real.write_bytes(b"real")
    trash.write_bytes(b"trash-copy")
    sidecar.write_bytes(b"resource-fork")
    ds_store.write_bytes(b"finder")

    first_signature = quick_source_signature(source)
    manifest = source_manifest(source)

    assert [row["relative_path"] for row in manifest] == [
        "DCIM/100_FUJI/A.JPG"
    ]

    # Änderungen ausschließlich im Papierkorb dürfen die Kameraquelle nicht
    # wie einen neuen/anderen Kartenbestand aussehen lassen.
    trash.write_bytes(b"changed-trash")
    assert quick_source_signature(source) == first_signature


def test_0324_library_bootstrap_runs_before_page_inline_scripts():
    html = """<!doctype html><html><head></head><body>
    <script>window.__pageFirstFetch = fetch('/api/events/search');</script>
    </body></html>"""

    rendered = ui_shell.apply_shell(
        html,
        active_area="workspace",
        subarea="events",
    )

    bootstrap_pos = rendered.index("window.__bkLibraryFetchInstalled")
    page_fetch_pos = rendered.index("window.__pageFirstFetch")
    late_shell_pos = rendered.rindex("bkRefreshCurrentLibraryName")

    assert bootstrap_pos < page_fetch_pos < late_shell_pos
    assert 'headers.set("X-Bibliothekar-Library", libraryId)' in rendered


def test_0324_cancel_mutation_reconciles_claims_and_central_stock(
    tmp_path: Path,
    monkeypatch,
):
    """0.44.3: Annahme ist sofort, Claims-/Stock-Abgleich liegt beim Worker."""
    import sqlite3

    database = tmp_path / "kamera.sqlite3"
    initialize_database(database)
    # Isolierter Eintrag für den Test; keine Importdateien erforderlich.
    with sqlite3.connect(database) as db:
        db.execute(
            """INSERT INTO event_mutations(
                id,job_id,anchor_event_id,mutation_kind,status,
                affected_event_ids_json,original_state_json,target_state_json,
                created_at,updated_at
            ) VALUES('MUT','JOB','EVT','edit','pending_apply','[]','{}','{}',
                     datetime('now'),datetime('now'))"""
        )
    called = {"cancel": 0, "claims": 0, "sync": 0}

    def fake_cancel(connection, mutation_id, job_id, *, workspace_path=None):
        called["cancel"] += 1
        connection.execute("UPDATE event_mutations SET status='cancelled' WHERE id=?", (mutation_id,))
        return {"status": "cancelled", "mutation_id": mutation_id}

    def fake_claims(*args, **kwargs):
        called["claims"] += 1
        assert kwargs["database_path"] == database
        assert kwargs["library_id"] == "test-library"
        return {"claim_count": 0, "reserved_count": 0, "owned_count": 0}

    def fake_sync():
        called["sync"] += 1
        return {}

    context = SimpleNamespace(
        library_id="test-library", database_path=database,
        workspace_root=tmp_path / "work",
    )
    monkeypatch.setattr("app.event_mutation.cancel_mutation", fake_cancel)
    monkeypatch.setattr(main, "current_database_file", lambda: database)
    monkeypatch.setattr(main, "list_active_library_contexts", lambda _: [context])
    monkeypatch.setattr(main, "ensure_library_database_schema", lambda _: None)
    monkeypatch.setattr(main, "backfill_library_claims", fake_claims)
    monkeypatch.setattr(main, "synchronize_global_central_stock", fake_sync)

    result = main.api_cancel_event_mutation("JOB", "MUT")
    assert result["status"] == "queued"
    assert called == {"cancel": 0, "claims": 0, "sync": 0}
    assert main.process_background_mutation_cancel() is True
    assert called == {"cancel": 1, "claims": 1, "sync": 1}
    from app.background_mutation_cancel import get
    assert get(database, result["id"])["status"] == "completed"


def test_0324_released_archive_assets_and_marker_project_between_libraries(
    tmp_path: Path,
):
    main_db = tmp_path / "database" / "kamera.sqlite3"
    other_db = tmp_path / "database" / "other.sqlite3"
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True)
    initialize_database(main_db)
    initialize_database(other_db)

    create_job(
        main_db,
        job_id="REL",
        kind="sd_import",
        trigger_type="approved_sd",
        source_path="/source",
        working_path=str(workspace / "SD-Kartensicherungen"),
        operation="folder_import",
    )
    camera_data = b"camera"
    family_id = _insert_family_file(
        main_db,
        job_id="REL",
        family_key="FAM",
        relative_path="DCIM/FAM.JPG",
        capture_time="2026-07-22T21:30:00",
        data=camera_data,
    )
    project_import_job(main_db, other_db, "REL")

    central_camera_rel = (
        "Freigewordene Archivdateien/2026/2026-07-22/FAM.JPG"
    )
    central_asset_rel = (
        "Freigewordene Archivdateien/2026/2026-07-22/FAM.xmp"
    )
    central = workspace / "SD-Kartensicherungen"
    camera_path = central / central_camera_rel
    asset_path = central / central_asset_rel
    camera_path.parent.mkdir(parents=True, exist_ok=True)
    camera_path.write_bytes(camera_data)
    asset_payload = b"<xmp/>"
    asset_path.write_bytes(asset_payload)

    with database_connection(main_db) as connection:
        file_id = int(connection.execute(
            "SELECT id FROM files WHERE family_id=?",
            (family_id,),
        ).fetchone()["id"])
        connection.execute(
            """UPDATE files
               SET current_relative_path=?,current_root_kind='shared_workspace'
               WHERE id=?""",
            (central_camera_rel, file_id),
        )
        connection.execute(
            """INSERT INTO released_free_families(
                   job_id,family_id,released_start_datetime,released_end_datetime,
                   created_at,archive_origin)
               VALUES ('REL',?,'2026-07-22T20:01:00','2026-07-22T23:59:59',?,1)""",
            (family_id, NOW),
        )
        connection.execute(
            """INSERT INTO released_archive_assets(
                   job_id,family_id,source_file_id,asset_kind,current_relative_path,
                   size_bytes,sha256,origin_change_request_id,created_at,updated_at)
               VALUES ('REL',?,?,'xmp',?,?,?,'CR',?,?)""",
            (
                family_id,
                file_id,
                central_asset_rel,
                len(asset_payload),
                _sha(asset_payload),
                NOW,
                NOW,
            ),
        )

    result = synchronize_central_stock_projections(
        [main_db, other_db],
        workspace,
    )
    assert result["central_release_family_count"] == 1
    assert result["central_release_asset_count"] == 1

    with database_connection(other_db) as connection:
        other_family = int(connection.execute(
            "SELECT id FROM file_families WHERE job_id='REL' AND family_key='FAM'"
        ).fetchone()["id"])
        marker = connection.execute(
            """SELECT archive_origin,released_start_datetime,released_end_datetime
               FROM released_free_families WHERE family_id=?""",
            (other_family,),
        ).fetchone()
        asset = connection.execute(
            """SELECT family_id,source_file_id,asset_kind,current_relative_path,sha256
               FROM released_archive_assets WHERE job_id='REL'"""
        ).fetchone()
        mapped_file = int(connection.execute(
            "SELECT id FROM files WHERE job_id='REL' AND original_relative_path='DCIM/FAM.JPG'"
        ).fetchone()["id"])

    assert marker is not None and int(marker["archive_origin"]) == 1
    assert marker["released_start_datetime"] == "2026-07-22T20:01:00"
    assert marker["released_end_datetime"] == "2026-07-22T23:59:59"
    assert asset is not None
    assert int(asset["family_id"]) == other_family
    assert int(asset["source_file_id"]) == mapped_file
    assert asset["asset_kind"] == "xmp"
    assert asset["current_relative_path"] == central_asset_rel

    # Wird der globale Rückkehrbestand physisch verbraucht, müssen die
    # Projektionen in allen Bibliotheken verschwinden.
    asset_path.unlink()
    camera_path.unlink()
    synchronize_central_stock_projections([main_db, other_db], workspace)
    with database_connection(other_db) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM released_archive_assets"
        ).fetchone()[0] == 0
        assert connection.execute(
            "SELECT COUNT(*) FROM released_free_families WHERE archive_origin=1"
        ).fetchone()[0] == 0


def test_0324_archived_delete_includes_live_xmp_asset(tmp_path: Path):
    db, workspace, archive, folder, family_id, _, _ = _seed(
        tmp_path,
        full_archive_triplet=True,
    )
    xmp = archive / "2026" / folder / "Alle" / "alt.xmp"
    xmp.write_bytes(b"<xmpmeta/>")

    result = propose_archived_event_deletion(
        db,
        "old",
        "archive",
        archive_root=archive,
    )

    assert result["released_file_count"] == 2
    assert result["released_asset_count"] == 1
    with database_connection(db) as connection:
        camera = connection.execute(
            """SELECT COUNT(*) FROM event_change_file_reviews
               WHERE change_request_id=? AND action='delete'""",
            (result["change_request_id"],),
        ).fetchone()[0]
        asset = connection.execute(
            """SELECT family_id,asset_kind,action,old_path
               FROM event_change_asset_reviews
               WHERE change_request_id=?""",
            (result["change_request_id"],),
        ).fetchone()

    assert camera == 1
    assert asset is not None
    assert int(asset["family_id"]) == family_id
    assert asset["asset_kind"] == "xmp"
    assert asset["action"] == "unresolved"
    assert str(asset["old_path"]).endswith("/Alle/alt.xmp")


def test_0324_archived_delete_blocks_unresolved_user_file(tmp_path: Path):
    db, workspace, archive, folder, _, _, _ = _seed(
        tmp_path,
        full_archive_triplet=True,
    )
    note = archive / "2026" / folder / "Alle" / "Notiz.txt"
    note.write_text("nicht zuordenbar", encoding="utf-8")

    with pytest.raises(EventChangeRequestError, match="nicht eindeutig zuordenbare"):
        propose_archived_event_deletion(
            db,
            "old",
            "archive",
            archive_root=archive,
        )


def test_0324_version_contract():
    assert main.DEPLOYMENT_VERSION == "0.44.3"
    assert "0.44.3 · Kamerakern 0.32.11" in ui_shell._shell_markup(
        "workspace",
        "events",
    )
