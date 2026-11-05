from __future__ import annotations

from tests.backend.legacy_storage_fixture import provision_legacy_storage

import hashlib
from pathlib import Path

import pytest

from app import main
from app.database import (
    create_planned_event,
    database_connection,
    delete_planned_event,
    initialize_database,
    update_event_definition,
)
from app.global_library_inventory import (
    backfill_library_claims,
    backfill_library_inventory,
    occurrence_key,
)
from app.library_context import LibraryContext
from app.library_registry import (
    MAIN_LIBRARY_ID,
    claim_source_family,
    ensure_library_identity,
    get_source_family_claim,
    initialize_library_registry,
    register_library,
)
from app.library_runtime import reset_current_library, set_current_library
from app.sort_apply import CONFIRMATION_PHRASE, execute_sort_run, prepare_sort_run
from app.sort_plan import build_event_sort_plan
from app.workspace_layout import ensure_workspace_layout
from app.workspace_reconcile import (
    build_workspace_reconcile_plan,
    execute_workspace_reconcile_run,
    prepare_workspace_reconcile_run,
)


NOW = "2026-10-03T12:00:00+00:00"
DAY = "2026-07-20"
JOB = "BUSINESS_JOB"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _insert_job(database: Path, central: Path) -> None:
    with database_connection(database) as connection:
        connection.execute(
            """INSERT INTO jobs(
                   id,kind,trigger_type,state,stage,operation,working_path,
                   created_at,updated_at
               )
               VALUES (?,'sd_import','approved_sd','completed','organized_verified',
                       'folder_import',?,?,?)""",
            (JOB, str(central), NOW, NOW),
        )


def _insert_family(
    database: Path,
    central: Path,
    *,
    key: str,
    capture: str,
    filename: str,
    payload: bytes,
) -> int:
    relative = f"2026/{DAY}/{filename}"
    digest = _sha(payload)
    with database_connection(database) as connection:
        family_id = int(connection.execute(
            """INSERT INTO file_families(
                   job_id,family_key,original_stem,status,
                   selected_capture_time,capture_time_confidence
               )
               VALUES (?,?,?,'complete',?,'high')""",
            (JOB, key, key, capture),
        ).lastrowid)
        connection.execute(
            """INSERT INTO files(
                   job_id,family_id,original_relative_path,current_relative_path,
                   original_filename,extension,media_type,size_bytes,
                   sha256_original,sha256_current,selected_capture_time,
                   selected_capture_source,capture_time_confidence,review_status,
                   metadata_write_status,current_root_kind,created_at,updated_at
               )
               VALUES (?,?,?,?,?,'.JPG','jpeg',?,?,?,?,
                       'DateTimeOriginal','high','not_required','not_requested',
                       'shared_workspace',?,?)""",
            (
                JOB, family_id, relative, relative, filename, len(payload),
                digest, digest, capture, NOW, NOW,
            ),
        )
    target = central / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
    return family_id


def _preview(
    family_ids: list[int],
    *,
    start: str = "14:00",
    end: str = "15:00",
) -> dict:
    return {
        "event_kind": "event",
        "event_name": "Business Test",
        "start_date": DAY,
        "end_date": DAY,
        "start_time": start,
        "end_time": end,
        "uses_time_range": True,
        "preserve_day_folders": False,
        "parent_folder": "07-20 - Business Test",
        "child_folder": None,
        "child_event_name": None,
        "subevents": [],
        "child_segments": [],
        "selected_family_ids": list(family_ids),
        "selected_day_keys": [DAY],
        "structure_lines": [],
    }


def _compatibility_root(tmp_path: Path, central: Path, work: Path) -> Path:
    compat = tmp_path / "compat"
    compat.mkdir()
    (compat / "SD-Kartensicherungen").symlink_to(
        central,
        target_is_directory=True,
    )
    (compat / "Arbeitsbereich").symlink_to(
        work,
        target_is_directory=True,
    )
    return compat


def _event_revision(database: Path, event_id: str) -> int:
    with database_connection(database) as connection:
        return int(connection.execute(
            "SELECT revision FROM events WHERE id=?",
            (event_id,),
        ).fetchone()["revision"])


def _apply_reconcile(
    database: Path,
    event_id: str,
    compat: Path,
) -> dict:
    plan = build_workspace_reconcile_plan(
        database,
        JOB,
        event_id,
        compat,
    )
    assert plan["summary"]["ready"] is True, plan["blockers"]
    run = prepare_workspace_reconcile_run(
        database,
        JOB,
        event_id,
        compat,
        expected_plan_token=plan["plan_token"],
        confirmation_phrase=CONFIRMATION_PHRASE,
    )
    execute_workspace_reconcile_run(database, run["id"], compat)
    return plan


def _secondary_foundation(tmp_path: Path):
    database = tmp_path / "database" / "business.sqlite3"
    registry = tmp_path / "database" / "registry.sqlite3"
    workspace = tmp_path / "workspace"
    archive = tmp_path / "archive-business"
    work = workspace / "Arbeitsbereiche" / "Business"
    workspace.mkdir()
    archive.mkdir()
    work.mkdir(parents=True)
    provision_legacy_storage(workspace)
    ensure_workspace_layout(workspace)
    central = workspace / "SD-Kartensicherungen"
    initialize_database(database)
    ensure_library_identity(database, "business")
    initialize_library_registry(registry)
    register_library(
        registry,
        library_id="business",
        display_name="Business",
        database_path=database,
        workspace_root=workspace,
        work_root=work,
        archive_root=archive,
        is_main=False,
        is_active=True,
    )
    compat = _compatibility_root(tmp_path, central, work)
    _insert_job(database, central)
    return database, registry, workspace, central, work, archive, compat


def test_03211_secondary_applied_edit_delete_uses_work_and_central_stock(
    tmp_path: Path,
):
    (
        database,
        registry,
        workspace,
        central,
        work,
        archive,
        compat,
    ) = _secondary_foundation(tmp_path)

    before = _insert_family(
        database, central,
        key="before", capture=f"{DAY}T11:00:00",
        filename="BEFORE.JPG", payload=b"before",
    )
    inside_first = _insert_family(
        database, central,
        key="inside-first", capture=f"{DAY}T14:15:00",
        filename="INSIDE_FIRST.JPG", payload=b"inside-first",
    )
    inside_second = _insert_family(
        database, central,
        key="inside-second", capture=f"{DAY}T14:45:00",
        filename="INSIDE_SECOND.JPG", payload=b"inside-second",
    )
    after = _insert_family(
        database, central,
        key="after", capture=f"{DAY}T22:00:00",
        filename="AFTER.JPG", payload=b"after",
    )

    created = create_planned_event(
        database,
        JOB,
        _preview([inside_first, inside_second]),
    )
    event_id = str(created["parent_event"]["id"])

    initial_plan = build_event_sort_plan(
        database,
        JOB,
        event_id,
        compat,
    )
    assert initial_plan["summary"]["ready"] is True, initial_plan["blockers"]
    initial_run = prepare_sort_run(
        database,
        JOB,
        event_id,
        compat,
        expected_plan_token=initial_plan["plan_token"],
        confirmation_phrase=CONFIRMATION_PHRASE,
    )
    execute_sort_run(database, initial_run["id"], compat)

    backfill_library_inventory(
        registry,
        database_path=database,
        library_id="business",
        claim_all_owned=False,
    )
    backfill_library_claims(
        registry,
        database_path=database,
        library_id="business",
    )
    first_key = occurrence_key("business", JOB, "inside-first")
    second_key = occurrence_key("business", JOB, "inside-second")
    assert get_source_family_claim(registry, first_key)["claim_state"] == "owned"
    assert get_source_family_claim(registry, second_key)["claim_state"] == "owned"

    # Shrink: one applied family falls out. It is still physically owned by
    # Business until reconcile moves it from Business work back to central stock.
    update_event_definition(
        database,
        JOB,
        event_id,
        _preview([inside_first], end="14:30"),
        workspace_path=compat,
        event_name="Business Test",
        notes="",
        expected_revision=_event_revision(database, event_id),
    )
    backfill_library_claims(
        registry,
        database_path=database,
        library_id="business",
    )
    assert get_source_family_claim(registry, second_key)["claim_state"] == "owned"

    shrink_plan = build_workspace_reconcile_plan(
        database,
        JOB,
        event_id,
        compat,
    )
    assert shrink_plan["summary"]["ready"] is True, shrink_plan["blockers"]
    shrink_by_family = {
        int(row["family_id"]): row
        for row in shrink_plan["files"]
        if row.get("family_id") is not None
    }
    assert shrink_by_family[inside_second]["physical_source_kind"] == "shared_workspace"
    assert Path(shrink_by_family[inside_second]["source_absolute_path"]).is_relative_to(work)
    assert Path(shrink_by_family[inside_second]["destination_absolute_path"]).is_relative_to(central)
    assert shrink_by_family[before]["physical_source_kind"] == "central_stock"
    assert shrink_by_family[after]["physical_source_kind"] == "central_stock"
    _apply_reconcile(database, event_id, compat)

    backfill_library_claims(
        registry,
        database_path=database,
        library_id="business",
    )
    assert get_source_family_claim(registry, first_key)["claim_state"] == "owned"
    assert get_source_family_claim(registry, second_key) is None

    # Expand again: the previously released family now comes from central stock
    # and must be moved back into the configured Business work area.
    update_event_definition(
        database,
        JOB,
        event_id,
        _preview([inside_first, inside_second]),
        workspace_path=compat,
        event_name="Business Test",
        notes="",
        expected_revision=_event_revision(database, event_id),
    )
    backfill_library_claims(
        registry,
        database_path=database,
        library_id="business",
    )
    assert get_source_family_claim(registry, second_key)["claim_state"] == "owned"

    expand_plan = build_workspace_reconcile_plan(
        database,
        JOB,
        event_id,
        compat,
    )
    assert expand_plan["summary"]["ready"] is True, expand_plan["blockers"]
    expand_by_family = {
        int(row["family_id"]): row
        for row in expand_plan["files"]
        if row.get("family_id") is not None
    }
    assert expand_by_family[inside_second]["physical_source_kind"] == "central_stock"
    assert Path(expand_by_family[inside_second]["source_absolute_path"]).is_relative_to(central)
    assert Path(expand_by_family[inside_second]["destination_absolute_path"]).is_relative_to(work)
    _apply_reconcile(database, event_id, compat)

    # Delete: claims remain owned while the event is only logically deleted.
    deleted = delete_planned_event(database, JOB, event_id)
    assert deleted["pending_delete"] is True
    backfill_library_claims(
        registry,
        database_path=database,
        library_id="business",
    )
    assert get_source_family_claim(registry, first_key)["claim_state"] == "owned"
    assert get_source_family_claim(registry, second_key)["claim_state"] == "owned"

    delete_plan = _apply_reconcile(database, event_id, compat)
    delete_by_family = {
        int(row["family_id"]): row
        for row in delete_plan["files"]
        if row.get("family_id") is not None
    }
    for family_id in (before, inside_first, inside_second, after):
        assert Path(
            delete_by_family[family_id]["destination_relative_path"]
        ).parent.as_posix() == f"2026/{DAY}"

    backfill_library_claims(
        registry,
        database_path=database,
        library_id="business",
    )
    assert get_source_family_claim(registry, first_key) is None
    assert get_source_family_claim(registry, second_key) is None
    merged = central / "2026" / DAY
    assert merged.is_dir()
    assert len(list(merged.glob("*.JPG"))) == 4
    assert not (central / "2026" / f"{DAY} · 00-00–13-59").exists()
    assert not (central / "2026" / f"{DAY} · 15-01–23-59").exists()
    with database_connection(database) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM events WHERE id=?",
            (event_id,),
        ).fetchone()[0] == 0


def test_03211_applied_edit_reservation_closes_multi_library_race(
    tmp_path: Path,
    monkeypatch,
):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    provision_legacy_storage(workspace)
    ensure_workspace_layout(workspace)
    central = workspace / "SD-Kartensicherungen"

    database_dir = tmp_path / "database"
    business_db = database_dir / "business.sqlite3"
    main_db = database_dir / "main.sqlite3"
    registry = database_dir / "registry.sqlite3"
    main_work = workspace / "Arbeitsbereiche" / "Main"
    business_work = workspace / "Arbeitsbereiche" / "Business"
    main_archive = tmp_path / "archive-main"
    business_archive = tmp_path / "archive-business"
    main_work.mkdir(parents=True)
    business_work.mkdir(parents=True)
    main_archive.mkdir()
    business_archive.mkdir()

    initialize_database(main_db)
    ensure_library_identity(main_db, MAIN_LIBRARY_ID)
    initialize_database(business_db)
    ensure_library_identity(business_db, "business")
    initialize_library_registry(registry)
    register_library(
        registry,
        library_id=MAIN_LIBRARY_ID,
        display_name="Main",
        database_path=main_db,
        workspace_root=workspace,
        work_root=main_work,
        archive_root=main_archive,
        is_main=True,
        is_active=True,
    )
    register_library(
        registry,
        library_id="business",
        display_name="Business",
        database_path=business_db,
        workspace_root=workspace,
        work_root=business_work,
        archive_root=business_archive,
        is_main=False,
        is_active=True,
    )
    compat = _compatibility_root(tmp_path, central, business_work)
    _insert_job(business_db, central)

    current_family = _insert_family(
        business_db, central,
        key="current", capture=f"{DAY}T14:15:00",
        filename="CURRENT.JPG", payload=b"current",
    )
    blocked_family = _insert_family(
        business_db, central,
        key="blocked", capture=f"{DAY}T14:45:00",
        filename="BLOCKED.JPG", payload=b"blocked",
    )
    created = create_planned_event(
        business_db,
        JOB,
        _preview([current_family], end="14:30"),
    )
    event_id = str(created["parent_event"]["id"])
    plan = build_event_sort_plan(business_db, JOB, event_id, compat)
    assert plan["summary"]["ready"] is True, plan["blockers"]
    run = prepare_sort_run(
        business_db,
        JOB,
        event_id,
        compat,
        expected_plan_token=plan["plan_token"],
        confirmation_phrase=CONFIRMATION_PHRASE,
    )
    execute_sort_run(business_db, run["id"], compat)

    backfill_library_inventory(
        registry,
        database_path=business_db,
        library_id="business",
        claim_all_owned=False,
    )
    backfill_library_claims(
        registry,
        database_path=business_db,
        library_id="business",
    )
    blocked_key = occurrence_key("business", JOB, "blocked")
    claim_source_family(
        registry,
        source_family_key=blocked_key,
        library_id=MAIN_LIBRARY_ID,
        event_id="MAIN_PENDING",
        claim_state="reserved",
    )

    context = LibraryContext(
        library_id="business",
        display_name="Business",
        database_path=business_db,
        workspace_root=workspace,
        work_root=business_work,
        archive_root=business_archive,
        is_main=False,
        settings={},
    )
    token = set_current_library(context)
    try:
        monkeypatch.setattr(main, "REGISTRY_DATABASE_FILE", registry)
        monkeypatch.setattr(main, "current_workspace_root", lambda: compat)
        # Simulate the exact race: the UI/preflight snapshot did not yet see
        # the other library's new claim. The atomic registry reservation below
        # must still stop the edit before SQLite is mutated.
        monkeypatch.setattr(main, "blocked_family_ids", lambda *args, **kwargs: set())

        before = None
        with database_connection(business_db) as connection:
            before = dict(connection.execute(
                "SELECT revision,start_datetime,end_datetime,resort_required FROM events WHERE id=?",
                (event_id,),
            ).fetchone())

        payload = _preview(
            [current_family, blocked_family],
            end="15:00",
        )
        payload.update({
            "event_name": "Business Test",
            "revision": before["revision"],
            "notes": "",
        })
        with pytest.raises(main.HTTPException) as exc:
            main.api_update_event(JOB, event_id, payload)
        assert exc.value.status_code == 409

        with database_connection(business_db) as connection:
            after_row = dict(connection.execute(
                "SELECT revision,start_datetime,end_datetime,resort_required FROM events WHERE id=?",
                (event_id,),
            ).fetchone())
            assigned = {
                int(row["family_id"])
                for row in connection.execute(
                    "SELECT family_id FROM event_assignments WHERE family_id IS NOT NULL"
                ).fetchall()
            }
        assert after_row == before
        assert blocked_family not in assigned
        claim = get_source_family_claim(registry, blocked_key)
        assert claim is not None
        assert claim["library_id"] == MAIN_LIBRARY_ID
        assert claim["claim_state"] == "reserved"
    finally:
        reset_current_library(token)



def _insert_cross_job_family(
    database: Path,
    central: Path,
    *,
    job_id: str,
    day: str,
    key: str,
    capture: str,
    filename: str,
    payload: bytes,
) -> int:
    with database_connection(database) as connection:
        connection.execute(
            """INSERT INTO jobs(
                   id,kind,trigger_type,state,stage,operation,working_path,
                   created_at,updated_at
               )
               VALUES (?,'sd_import','approved_sd','completed','organized_verified',
                       'folder_import',?,?,?)""",
            (job_id, str(central), NOW, NOW),
        )
        relative = f"2026/{day}/{filename}"
        digest = _sha(payload)
        family_id = int(connection.execute(
            """INSERT INTO file_families(
                   job_id,family_key,original_stem,status,
                   selected_capture_time,capture_time_confidence
               )
               VALUES (?,?,?,'complete',?,'high')""",
            (job_id, key, key, capture),
        ).lastrowid)
        connection.execute(
            """INSERT INTO files(
                   job_id,family_id,original_relative_path,current_relative_path,
                   original_filename,extension,media_type,size_bytes,
                   sha256_original,sha256_current,selected_capture_time,
                   selected_capture_source,capture_time_confidence,review_status,
                   metadata_write_status,current_root_kind,created_at,updated_at
               )
               VALUES (?,?,?,?,?,'.JPG','jpeg',?,?,?,?,
                       'DateTimeOriginal','high','not_required','not_requested',
                       'shared_workspace',?,?)""",
            (
                job_id, family_id, relative, relative, filename, len(payload),
                digest, digest, capture, NOW, NOW,
            ),
        )
    target = central / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
    return family_id


def _apply_initial_event(
    database: Path,
    job_id: str,
    event_id: str,
    compat: Path,
) -> None:
    plan = build_event_sort_plan(database, job_id, event_id, compat)
    assert plan["summary"]["ready"] is True, plan["blockers"]
    run = prepare_sort_run(
        database,
        job_id,
        event_id,
        compat,
        expected_plan_token=plan["plan_token"],
        confirmation_phrase=CONFIRMATION_PHRASE,
    )
    execute_sort_run(database, run["id"], compat)


def test_03211_applied_event_extension_absorbs_free_family_from_other_backup(
    tmp_path: Path,
    monkeypatch,
):
    (
        database,
        registry,
        workspace,
        central,
        work,
        archive,
        compat,
    ) = _secondary_foundation(tmp_path)

    day20_family = _insert_family(
        database, central,
        key="day20", capture="2026-07-20T12:00:00",
        filename="DAY20.JPG", payload=b"day20",
    )
    day21_family = _insert_cross_job_family(
        database,
        central,
        job_id="FOLLOW_JOB",
        day="2026-07-21",
        key="day21",
        capture="2026-07-21T12:00:00",
        filename="DAY21.JPG",
        payload=b"day21",
    )

    created = create_planned_event(
        database,
        JOB,
        {
            "event_kind": "event",
            "event_name": "Test",
            "start_date": "2026-07-20",
            "end_date": "2026-07-20",
            "start_time": "00:00",
            "end_time": "23:59",
            "uses_time_range": True,
            "preserve_day_folders": False,
            "parent_folder": "07-20 - Test",
            "child_folder": None,
            "child_event_name": None,
            "selected_family_ids": [day20_family],
            "structure_lines": [],
        },
    )
    event_id = str(created["parent_event"]["id"])
    _apply_initial_event(database, JOB, event_id, compat)

    backfill_library_inventory(
        registry,
        database_path=database,
        library_id="business",
        claim_all_owned=False,
    )
    backfill_library_claims(
        registry,
        database_path=database,
        library_id="business",
    )

    context = LibraryContext(
        library_id="business",
        display_name="Business",
        database_path=database,
        workspace_root=workspace,
        work_root=work,
        archive_root=archive,
        is_main=False,
        settings={},
    )
    token = set_current_library(context)
    try:
        monkeypatch.setattr(main, "REGISTRY_DATABASE_FILE", registry)
        monkeypatch.setattr(main, "current_workspace_root", lambda: compat)

        with database_connection(database) as connection:
            revision = int(connection.execute(
                "SELECT revision FROM events WHERE id=?",
                (event_id,),
            ).fetchone()["revision"])

        result = main.api_update_event(
            JOB,
            event_id,
            {
                "revision": revision,
                "event_name": "Test",
                "notes": "",
                "event_kind": "event",
                "start_date": "2026-07-20",
                "end_date": "2026-07-21",
                "start_time": "00:00",
                "end_time": "23:59",
                "uses_time_range": True,
                "preserve_day_folders": False,
                "subevents": [],
            },
        )
        assert result["resort_required"] is True
        assert result["mutation_id"]

        with database_connection(database) as connection:
            assigned = {
                int(row["family_id"])
                for row in connection.execute(
                    """SELECT ea.family_id
                       FROM event_assignments ea
                       JOIN events e ON e.id=ea.event_id
                       WHERE COALESCE(e.parent_event_id,e.id)=?
                         AND ea.family_id IS NOT NULL""",
                    (event_id,),
                ).fetchall()
            }
        assert assigned == {day20_family, day21_family}

        plan = build_workspace_reconcile_plan(
            database,
            JOB,
            event_id,
            compat,
        )
        assert plan["summary"]["ready"] is True, plan["blockers"]
        by_family = {
            int(row["family_id"]): row
            for row in plan["files"]
            if row.get("family_id") is not None
        }
        assert by_family[day21_family]["physical_source_kind"] == "central_stock"
        assert Path(
            by_family[day21_family]["source_absolute_path"]
        ).is_relative_to(central)
        assert Path(
            by_family[day21_family]["destination_absolute_path"]
        ).is_relative_to(work)
    finally:
        reset_current_library(token)


def test_03211_applied_no_event_extension_absorbs_other_backup(
    tmp_path: Path,
    monkeypatch,
):
    (
        database,
        registry,
        workspace,
        central,
        work,
        archive,
        compat,
    ) = _secondary_foundation(tmp_path)

    day20_family = _insert_family(
        database, central,
        key="noevent-day20", capture="2026-07-20T12:00:00",
        filename="NOEVENT20.JPG", payload=b"noevent20",
    )
    day21_family = _insert_cross_job_family(
        database,
        central,
        job_id="NOEVENT_FOLLOW",
        day="2026-07-21",
        key="noevent-day21",
        capture="2026-07-21T12:00:00",
        filename="NOEVENT21.JPG",
        payload=b"noevent21",
    )

    created = create_planned_event(
        database,
        JOB,
        {
            "event_kind": "no_event",
            "event_name": "Ohne Ereignis",
            "start_date": "2026-07-20",
            "end_date": "2026-07-20",
            "start_time": "00:00",
            "end_time": "23:59",
            "uses_time_range": False,
            "preserve_day_folders": False,
            "parent_folder": "07 - Ohne Ereignis",
            "child_folder": None,
            "child_event_name": None,
            "selected_family_ids": [day20_family],
            "selected_day_keys": ["2026-07-20"],
            "no_event_segments": [
                {
                    "day_key": "2026-07-20",
                    "start_time": "00:00",
                    "end_time": "23:59",
                }
            ],
            "structure_lines": [],
        },
    )
    event_id = str(created["parent_event"]["id"])
    _apply_initial_event(database, JOB, event_id, compat)

    backfill_library_inventory(
        registry,
        database_path=database,
        library_id="business",
        claim_all_owned=False,
    )
    backfill_library_claims(
        registry,
        database_path=database,
        library_id="business",
    )

    context = LibraryContext(
        library_id="business",
        display_name="Business",
        database_path=database,
        workspace_root=workspace,
        work_root=work,
        archive_root=archive,
        is_main=False,
        settings={},
    )
    token = set_current_library(context)
    try:
        monkeypatch.setattr(main, "REGISTRY_DATABASE_FILE", registry)
        monkeypatch.setattr(main, "current_workspace_root", lambda: compat)

        with database_connection(database) as connection:
            revision = int(connection.execute(
                "SELECT revision FROM events WHERE id=?",
                (event_id,),
            ).fetchone()["revision"])

        result = main.api_update_event(
            JOB,
            event_id,
            {
                "revision": revision,
                "event_name": "Ohne Ereignis",
                "notes": "",
                "event_kind": "no_event",
                "start_date": "2026-07-20",
                "end_date": "2026-07-21",
                "uses_time_range": False,
                "preserve_day_folders": False,
                "no_event_segments": [
                    {
                        "day_key": "2026-07-20",
                        "start_time": "00:00",
                        "end_time": "23:59",
                    },
                    {
                        "day_key": "2026-07-21",
                        "start_time": "00:00",
                        "end_time": "23:59",
                    },
                ],
            },
        )
        assert result["resort_required"] is True
        assert result["mutation_id"]

        with database_connection(database) as connection:
            assigned = {
                int(row["family_id"])
                for row in connection.execute(
                    """SELECT ea.family_id
                       FROM event_assignments ea
                       JOIN events e ON e.id=ea.event_id
                       WHERE COALESCE(e.parent_event_id,e.id)=?
                         AND ea.family_id IS NOT NULL""",
                    (event_id,),
                ).fetchall()
            }
        assert assigned == {day20_family, day21_family}

        plan = build_workspace_reconcile_plan(
            database,
            JOB,
            event_id,
            compat,
        )
        assert plan["summary"]["ready"] is True, plan["blockers"]
        by_family = {
            int(row["family_id"]): row
            for row in plan["files"]
            if row.get("family_id") is not None
        }
        assert by_family[day21_family]["physical_source_kind"] == "central_stock"
        assert Path(
            by_family[day21_family]["destination_absolute_path"]
        ).is_relative_to(work)
    finally:
        reset_current_library(token)
