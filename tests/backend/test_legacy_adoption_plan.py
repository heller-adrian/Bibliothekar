from pathlib import Path

import pytest

from app.database import database_connection
from app.legacy_adoption_inventory import create_job, inventory_chronology, scan_inventory
from app.legacy_adoption_paths import AdoptionError
from app.legacy_adoption_plan import create_plan, plan_moves
from app.library_registry import initialize_library_registry, register_source_backup, register_source_media
from tests.backend.test_legacy_adoption_inventory import library, synthetic_dataset


@pytest.fixture
def inventory(library, monkeypatch):
    context, source = library
    registry = source.parent / "private" / "registry.db"
    initialize_library_registry(registry)
    monkeypatch.setattr(
        "app.legacy_adoption_inventory.read_bound_metadata",
        lambda descriptors, _cancel: {
            fd: {"EXIF:ExifIFD:DateTimeOriginal": "2026:07:21 12:00:00"} for fd in descriptors
        },
    )
    return context, source, registry


def _draft(**extra):
    return {"events": [{"name": "Sommer", "start_date": "2026-07-20", "end_date": "2026-07-24", **extra}]}


def _scan(context, source):
    job = create_job(context, source)
    scan_inventory(context, job)
    return job


def _existing(context):
    event_id = "EXISTING"
    with database_connection(context.database_path) as connection:
        connection.execute(
            """INSERT INTO jobs (id, kind, trigger_type, state, stage, created_at, updated_at)
               VALUES ('old', 'sd_import', 'manual', 'completed', 'completed', '2026', '2026')"""
        )
        connection.execute(
            """INSERT INTO events (
                   id, job_id, event_level, name, start_datetime, end_datetime, folder_name, status,
                   created_at, updated_at, archived_at, time_model_version
               ) VALUES (?, 'old', 'parent', 'Urlaub', '2026-07-20T00:00:00', '2026-07-24T23:59:59',
                         'Urlaub', 'archived', '2026', '2026', '2026', 2)""", (event_id,),
        )
    folder = context.archive_root / "2026" / "Urlaub"
    folder.mkdir(parents=True)
    (folder / "event.json").write_text('{"event":{"id":"EXISTING"}}')
    return event_id


def test_new_plan_and_chronology(inventory):
    context, source, registry = inventory
    (source / "pair.jpg").write_bytes(b"jpg")
    (source / "pair.raf").write_bytes(b"raf")
    job = _scan(context, source)
    assert inventory_chronology(context, job) == [{"period": "2026", "families": 1, "review": 0}]
    assert inventory_chronology(context, job, year="2026")[0]["period"] == "2026-07-21"
    plan = create_plan(context, registry, job, _draft(
        preserve_day_folders=True, children=[{
            "name": "Ausflug", "start_datetime": "2026-07-21T10:00", "end_datetime": "2026-07-21T20:00",
        }],
    ))
    event = plan["events"][0]
    rows = plan_moves(context, job)
    assert {row["assigned_event_id"] for row in rows} == {event["children"][0]["id"]}
    assert all("/2026-07-21/Alle/" in row["target"] for row in rows)
    assert list(context.archive_root.iterdir()) == []
    with database_connection(context.database_path) as connection:
        assert connection.execute("SELECT count(*) FROM events").fetchone()[0] == 0
        assert connection.execute("SELECT count(*) FROM files").fetchone()[0] == 0


def test_existing_event_suggested_and_selected_without_catalogue_change(inventory):
    context, source, registry = inventory
    event_id = _existing(context)
    (source / "extra.jpg").write_bytes(b"extra")
    job = _scan(context, source)
    with pytest.raises(AdoptionError, match="Urlaub"):
        create_plan(context, registry, job, _draft())
    plan = create_plan(context, registry, job, {"events": [{"existing_id": event_id}]})
    assert plan["events"][0]["existing"]
    assert "/2026/Urlaub/" in plan_moves(context, job)[0]["target"]
    with database_connection(context.database_path) as connection:
        assert connection.execute("SELECT revision FROM events WHERE id=?", (event_id,)).fetchone()[0] == 1
        assert connection.execute("SELECT count(*) FROM event_assignments").fetchone()[0] == 0


def test_collision_and_exact_global_duplicates(inventory):
    import hashlib

    context, source, registry = inventory
    for directory, content in (("first", b"one"), ("second", b"two")):
        (source / directory).mkdir()
        (source / directory / "same.jpg").write_bytes(content)
    job = _scan(context, source)
    with pytest.raises(AdoptionError, match="dieselbe Zieldatei"):
        create_plan(context, registry, job, _draft())
    register_source_backup(
        registry, backup_id="older", source_kind="import", source_identity="older", backup_path="/synthetic/older",
    )
    register_source_media(
        registry, backup_id="older", relative_path="some-other-name.jpg", size_bytes=3,
        sha256=hashlib.sha256(b"one").hexdigest(), media_type="jpeg",
    )
    plan = create_plan(context, registry, job, _draft())
    assert plan["counts"] == {"duplicate": 1, "pending": 1}
    old, new = plan_moves(context, job)
    assert old["target"] is None
    assert Path(new["target"]).name == "same.jpg"


def test_disjoint_collection_segments(inventory):
    context, source, registry = inventory
    (source / "clip.mov").write_bytes(b"video")
    job = _scan(context, source)
    plan = create_plan(context, registry, job, {"events": [{
        "event_kind": "no_event", "segments": [
            {"day_key": "2026-07-21", "start_time": "11:30", "end_time": "12:15"},
            {"day_key": "2026-07-23"},
        ],
    }]})
    assert len(plan["events"][0]["segments"]) == 2


def test_verification_survives_partial_moves_and_detects_unexpected_files(inventory):
    from app.legacy_adoption_verify import plan_issues, reopen_plan, verify_media

    context, source, registry = inventory
    (source / "a.jpg").write_bytes(b"first")
    (source / "b.jpg").write_bytes(b"other")
    job = _scan(context, source)
    create_plan(context, registry, job, _draft())
    first, second = plan_moves(context, job)
    first_target, second_target = Path(first["target"]), Path(second["target"])
    for folder in ("Alle", "Sortiert", "Export"):
        (first_target.parent.parent / folder).mkdir(parents=True, exist_ok=True)

    Path(first["source"]).rename(first_target)
    assert verify_media(context, job)["counts"] == {"missing": 1, "verified": 1}
    with pytest.raises(AdoptionError, match="Verschiebeziel ist noch belegt"):
        reopen_plan(context, job)

    second_target.write_bytes(b"wrong")
    assert verify_media(context, job)["counts"] == {"sha256_mismatch": 1, "verified": 1}
    second_target.write_bytes(b"other")
    assert verify_media(context, job)["counts"] == {"source_present": 1, "verified": 1}
    Path(second["source"]).unlink()
    extra = first_target.with_name("unexpected.jpg")
    extra.write_bytes(b"unexpected")
    assert verify_media(context, job)["state"] == "prepared"
    assert any(row["relative_path"].endswith("unexpected.jpg") for row in plan_issues(context, job))
    extra.unlink()
    assert verify_media(context, job)["state"] == "media_verified"
    assert verify_media(context, job)["state"] == "media_verified"
    with database_connection(context.database_path) as connection:
        assert connection.execute("SELECT count(*) FROM files").fetchone()[0] == 0


def test_verification_detects_archived_media_changes(inventory):
    from app.legacy_adoption_verify import plan_issues, verify_media

    context, source, registry = inventory
    event_id = _existing(context)
    previous = context.archive_root / "2026/Urlaub/old.jpg"
    previous.write_bytes(b"original")
    (source / "extra.jpg").write_bytes(b"extra")
    job = _scan(context, source)
    create_plan(context, registry, job, {"events": [{"existing_id": event_id}]})
    move = plan_moves(context, job)[0]
    target = Path(move["target"])
    for folder in ("Alle", "Sortiert", "Export"):
        (target.parent.parent / folder).mkdir(exist_ok=True)
    Path(move["source"]).rename(target)
    assert verify_media(context, job)["state"] == "media_verified"
    previous.write_bytes(b"modified")
    assert verify_media(context, job)["state"] == "prepared"
    assert any(row["relative_path"].endswith("old.jpg") for row in plan_issues(context, job))


def test_manual_manifest_and_empty_scaffold(inventory):
    import json
    from zipfile import ZipFile

    from app.legacy_adoption_export import directory_scaffold, manual_manifest

    context, source, registry = inventory
    (source / "image.raf").write_bytes(b"data")
    job = _scan(context, source)
    plan = create_plan(context, registry, job, _draft())
    with directory_scaffold(context, job) as handle, ZipFile(handle) as archive:
        assert archive.infolist()
        assert all(entry.is_dir() and entry.file_size == 0 for entry in archive.infolist())
    header, record = map(json.loads, manual_manifest(context, job))
    assert header["plan"] == plan["id"]
    assert record["undo"] == {"from": record["target"], "to": record["source"]}
    assert record["size_bytes"] == 4
    assert list(context.archive_root.iterdir()) == []


def test_projects_canonical_event_documents_without_registering(inventory):
    import json
    from zipfile import ZipFile

    from app.legacy_adoption_catalogue import prepare_documents
    from app.legacy_adoption_export import directory_scaffold, event_documents
    from app.legacy_adoption_verify import verify_media

    context, source, registry = inventory
    event_id = _existing(context)
    (source / "pair.raf").write_bytes(b"raw")
    (source / "pair.xmp").write_bytes(b"sidecar")
    job = _scan(context, source)
    create_plan(context, registry, job, {"events": [{"existing_id": event_id}]})
    [document] = prepare_documents(context, job)
    with event_documents(context, job, originals=True) as handle, ZipFile(handle) as originals:
        assert json.loads(originals.read(document["relative_path"]))["event"]["id"] == event_id
    with directory_scaffold(context, job) as handle, ZipFile(handle) as scaffold:
        scaffold.extractall(context.archive_root)
    for move in plan_moves(context, job):
        Path(move["source"]).rename(Path(move["target"]))
    assert verify_media(context, job)["state"] == "prepared"
    with event_documents(context, job) as handle, ZipFile(handle) as documents:
        payload = json.loads(documents.read(document["relative_path"]))
        assert payload["event"]["id"] == event_id
        assert payload["event"]["status"] == "archived"
        assert len(payload["files"]) == 2
        assert len(payload["families"]) == 1
        documents.extractall(context.archive_root)
    assert verify_media(context, job)["state"] == "verified"
    with database_connection(context.database_path) as connection:
        assert connection.execute("SELECT revision FROM events WHERE id = ?", (event_id,)).fetchone()[0] == 1
        assert connection.execute("SELECT count(*) FROM files").fetchone()[0] == 0
        assert connection.execute("SELECT count(*) FROM event_archive_verifications").fetchone()[0] == 0


def test_confirmed_rollback_keeps_plan_and_requires_restored_bytes(inventory):
    from app.legacy_adoption_catalogue import prepare_documents
    from app.legacy_adoption_execution import change_phase, complete_rollback, confirm_plan, verify_execution
    from app.legacy_adoption_inventory import discard_job, inventory_status

    context, source, registry = inventory
    original = source / "original.jpg"
    original.write_bytes(b"original photo")
    job = _scan(context, source)
    plan = create_plan(context, registry, job, _draft())
    prepare_documents(context, job)
    plan_id = plan["id"]
    original.write_bytes(b"modified")
    with pytest.raises(AdoptionError, match="Quelldatei fehlt oder stimmt nicht"):
        confirm_plan(context, job, plan_id, "manual", acknowledged=True)
    original.write_bytes(b"original photo")
    assert confirm_plan(context, job, plan_id, "manual", acknowledged=True)["execution"]["phase"] == "manual"
    [move] = plan_moves(context, job)
    target = Path(move["target"])
    target.parent.mkdir(parents=True)
    original.rename(target)
    assert verify_execution(context, job, plan_id)["execution"]["phase"] == "repair"
    with pytest.raises(AdoptionError, match="kontrolliert zurückgenommen"):
        discard_job(context, job)
    change_phase(context, job, plan_id, "rolling_back", from_phases={"repair"})
    with pytest.raises(AdoptionError, match="Verschiebeziel ist noch belegt"):
        complete_rollback(context, job, plan_id)
    target.rename(original)
    original.write_bytes(b"modified")
    with pytest.raises(AdoptionError, match="Quelldatei fehlt oder stimmt nicht"):
        complete_rollback(context, job, plan_id)
    original.write_bytes(b"original photo")
    restored = complete_rollback(context, job, plan_id)
    assert restored["id"] == plan_id
    assert restored["execution"]["phase"] == "rolled_back"
    assert inventory_status(context, job)["state"] == "discarded"
    assert original.read_bytes() == b"original photo"


def _ready_for_registration(inventory, draft):
    from zipfile import ZipFile

    from app.legacy_adoption_catalogue import prepare_documents
    from app.legacy_adoption_execution import change_phase, confirm_plan, verify_execution
    from app.legacy_adoption_export import directory_scaffold, event_documents
    from app.library_registry import register_library

    context, source, registry = inventory
    context.work_root.mkdir()
    register_library.__wrapped__(
        registry, library_id=context.library_id, display_name=context.display_name,
        database_path=context.database_path, workspace_root=context.workspace_root,
        work_root=context.work_root, archive_root=context.archive_root, is_main=False,
    )
    (source / "adopted.raf").write_bytes(b"raw file in synthetic archive")
    job = _scan(context, source)
    plan = create_plan(context, registry, job, draft)
    prepare_documents(context, job)
    confirm_plan(context, job, plan["id"], "manual", acknowledged=True)
    with directory_scaffold(context, job) as handle, ZipFile(handle) as scaffold:
        scaffold.extractall(context.archive_root)
    for move in plan_moves(context, job):
        Path(move["source"]).rename(move["target"])
    with event_documents(context, job) as handle, ZipFile(handle) as documents:
        documents.extractall(context.archive_root)
    assert verify_execution(context, job, plan["id"])["execution"]["phase"] == "registration_pending"
    change_phase(context, job, plan["id"], "registering", from_phases={"registration_pending"})
    return job, plan


def test_registration_replays_after_registry_commit(inventory, monkeypatch):
    import sqlite3

    from app import legacy_adoption_registration as registration
    from app.global_library_inventory import backfill_library_inventory
    from app.event_access import event_file_rows

    context, _, registry = inventory
    job, plan = _ready_for_registration(inventory, _draft(preserve_day_folders=True))
    event_id = plan["events"][0]["id"]

    # Model a process dying after the registry's durable commit and before
    # the catalogue commits. No app rows should have escaped that transaction.
    original = registration.source_registry_transaction
    from contextlib import contextmanager

    @contextmanager
    def interrupt_after_commit(path):
        with original(path) as connection:
            yield connection
        raise InterruptedError("synthetic crash between commits")

    monkeypatch.setattr(registration, "source_registry_transaction", interrupt_after_commit)
    with pytest.raises(InterruptedError):
        registration.finalize_adoption.__wrapped__(context, registry, job, plan["id"])
    with database_connection(context.database_path) as connection:
        assert event_file_rows(connection, event_id) == []
    with sqlite3.connect(registry) as connection:
        assert connection.execute("SELECT count(*) FROM legacy_adoption_receipts").fetchone()[0] == 1
        assert connection.execute("SELECT count(*) FROM family_claims").fetchone()[0] == 1

    monkeypatch.setattr(registration, "source_registry_transaction", original)
    assert registration.finalize_adoption.__wrapped__(context, registry, job, plan["id"])["state"] == "completed"
    assert registration.finalize_adoption.__wrapped__(context, registry, job, plan["id"])["state"] == "completed"
    with database_connection(context.database_path) as connection:
        [adopted] = event_file_rows(connection, event_id)
        assert adopted["current_root_kind"] == "camera_archive"
        assert adopted["original_relative_path"] == "adopted.raf"
        assert connection.execute("SELECT status FROM events WHERE id = ?", (event_id,)).fetchone()[0] == "archived"
        assert connection.execute("SELECT count(*) FROM event_archive_verified_file_locations").fetchone()[0] == 1
    assert backfill_library_inventory(
        registry, database_path=context.database_path, library_id=context.library_id, claim_all_owned=False,
    )["family_count"] == 1
