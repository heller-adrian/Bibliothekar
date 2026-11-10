import hashlib
import os
from pathlib import Path
import shutil

import pytest

from app.database import initialize_database
from app.legacy_adoption_inventory import (
    create_job, discard_job, inventory_errors, inventory_families, inventory_status, scan_inventory,
)
from app.legacy_adoption_paths import AdoptionError
from app.library_context import LibraryContext
from app.library_registry import ensure_library_identity


@pytest.fixture
def synthetic_dataset(monkeypatch):
    from app import legacy_adoption_dataset

    def prove(source, archive, source_fd, archive_fd):
        left, right = os.fstat(source_fd), os.fstat(archive_fd)
        assert left.st_dev == right.st_dev
        return {"dataset": "synthetic/test", "device": str(left.st_dev),
                "source_directory": str(left.st_ino), "archive_directory": str(right.st_ino)}

    monkeypatch.setattr(legacy_adoption_dataset, "prove", prove)


@pytest.fixture
def library(tmp_path, synthetic_dataset):
    root = tmp_path.resolve()
    for name in ("archive", "workspace", "source"):
        (root / name).mkdir()
    library = LibraryContext(
        "test-library", "Synthetisch", root / "private" / "catalogue.db",
        root / "workspace", root / "workspace" / "work", root / "archive", True, {},
    )
    initialize_database(library.database_path)
    ensure_library_identity(library.database_path, library.library_id)
    return library, root / "source"


def test_inventory_read_only_restart_and_discard(library, monkeypatch):
    context, source = library
    day = source / "2020" / "01" / "2020-01-02"
    day.mkdir(parents=True)
    originals = {"pair.RAF": b"raw", "pair.jpg": b"jpg", "solo.DNG": b"raw-only",
                 "pair.xmp": b"sidecar", "clip.mov": b"video", "notes.txt": b"ignored"}
    for name, contents in originals.items():
        (day / name).write_bytes(contents)
    (day / "link.jpg").symlink_to(day / "pair.jpg")
    job = create_job(context, source)
    scans = []

    def metadata(descriptors, _cancel):
        scans.extend(descriptors)
        return {fd: {"EXIF:ExifIFD:DateTimeOriginal": "2020:01:02 12:00:00"}
                for fd in descriptors}

    monkeypatch.setattr("app.legacy_adoption_inventory.read_bound_metadata", metadata)
    assert scan_inventory(context, job)["files"] == 5
    assert len(scans) == 5
    families = inventory_families(context, job)
    assert {Path(row["family_key"]).name: row["member_count"] for row in families} == {
        "clip": 1, "pair": 3, "solo": 1,
    }
    assert all(row["selected_capture_time"].startswith("2020-01-02") for row in families)
    assert len(inventory_errors(context, job)) == 1

    (day / "pair.jpg").write_bytes(b"changed")
    (day / "clip.mov").unlink()
    assert scan_inventory(context, job)["files"] == 4
    assert len(scans) == 6
    assert inventory_status(context, job)["families"] == 2
    assert not list(context.archive_root.iterdir())
    discard_job(context, job)
    assert inventory_status(context, job)["state"] == "discarded"
    assert (day / "solo.DNG").read_bytes() == originals["solo.DNG"]
    assert (day / "link.jpg").is_symlink()


def test_inventory_persists_batches_after_interruption(library, monkeypatch):
    context, source = library
    for number in range(120):
        (source / f"{number}.raf").write_bytes(str(number).encode())
    calls = []

    def interrupt_second_batch(descriptors, _cancel):
        calls.append(len(descriptors))
        if len(calls) == 2:
            raise InterruptedError("synthetischer Neustart")
        return {}

    monkeypatch.setattr("app.legacy_adoption_inventory.read_bound_metadata", interrupt_second_batch)
    job = create_job(context, source)
    with pytest.raises(InterruptedError):
        scan_inventory(context, job)
    assert inventory_status(context, job)["files"] == 48
    assert inventory_status(context, job)["state"] == "scanning"
    calls.clear()
    monkeypatch.setattr(
        "app.legacy_adoption_inventory.read_bound_metadata",
        lambda descriptors, _cancel: calls.append(len(descriptors)) or {},
    )
    assert scan_inventory(context, job)["files"] == 120
    assert sum(calls) == 72
    assert all(row["status"] == "review_required" for row in inventory_families(context, job, limit=120))


def test_source_and_library_identity(library):
    context, source = library
    alias = source.parent / "alias"
    alias.symlink_to(source, target_is_directory=True)
    with pytest.raises(OSError):
        create_job(context, alias)
    with pytest.raises(AdoptionError):
        create_job(context, context.archive_root)
    job = create_job(context, source)
    source.rename(source.with_name("moved"))
    source.mkdir()
    with pytest.raises(AdoptionError, match="Identität"):
        scan_inventory(context, job)


@pytest.mark.skipif(shutil.which("exiftool") is None, reason="ExifTool fehlt")
def test_exiftool_reads_xmp_by_bound_descriptor(library):
    from app.database import database_connection

    context, source = library
    sidecar = source / "image.xmp"
    content = (b'<x:xmpmeta xmlns:x="adobe:ns:meta/">'
               b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
               b'<rdf:Description xmlns:xmp="http://ns.adobe.com/xap/1.0/" '
               b'xmp:CreateDate="2020-01-02T12:34:56+01:00"/></rdf:RDF></x:xmpmeta>')
    sidecar.write_bytes(content)
    before = os.stat(sidecar)
    job = create_job(context, source)
    assert scan_inventory(context, job)["files"] == 1
    family = inventory_families(context, job)[0]
    assert family["selected_capture_time"] == "2020-01-02T12:34:56+01:00"
    with database_connection(context.database_path) as connection:
        digest = connection.execute("SELECT sha256 FROM legacy_adoption_inventory").fetchone()[0]
    assert digest == hashlib.sha256(content).hexdigest()
    assert os.stat(sidecar).st_mtime_ns == before.st_mtime_ns


def test_large_inventory_and_compound_xmp_names(library, monkeypatch):
    context, source = library
    for index in range(2500):
        (source / f"{index:05}.raf").write_bytes(str(index).encode())
    (source / "00001.RAF.xmp").write_bytes(b"sidecar")
    monkeypatch.setattr("app.legacy_adoption_inventory.read_bound_metadata", lambda _files, _cancel: {})
    job = create_job(context, source)
    status = scan_inventory(context, job)
    assert status["files"] == 2501
    assert status["families"] == 2500
    assert inventory_families(context, job, after="00000", limit=1)[0]["member_count"] == 2


def test_conflicting_capture_times_remain_unconfirmed(library, monkeypatch):
    context, source = library
    (source / "mixed.raf").write_bytes(b"raw")
    (source / "mixed.jpg").write_bytes(b"jpeg")
    monkeypatch.setattr(
        "app.legacy_adoption_inventory.read_bound_metadata",
        lambda descriptors, _cancel: {
            fd: {"EXIF:ExifIFD:DateTimeOriginal": f"2026:07:{index + 20:02} 10:00:00"}
            for index, fd in enumerate(descriptors)
        },
    )
    job = create_job(context, source)
    scan_inventory(context, job)
    [family] = inventory_families(context, job, day="")
    assert family["selected_capture_time"] is None
    assert family["status"] == "review_required"


def test_upgrades_1_0_0_catalogue_and_registry_without_touching_existing_rows(tmp_path, monkeypatch):
    from app import database, library_registry

    db, registry = tmp_path / "library.db", tmp_path / "registry.db"
    migrations = database.available_migrations()
    registry_migrations = library_registry.REGISTRY_MIGRATIONS
    with monkeypatch.context() as version_1_0_0:
        version_1_0_0.setattr(database, "available_migrations", lambda: [item for item in migrations if item[0] <= 55])
        version_1_0_0.setattr(library_registry, "REGISTRY_MIGRATIONS",
                             {version: sql for version, sql in registry_migrations.items() if version <= 3})
        version_1_0_0.setattr(library_registry, "REGISTRY_SCHEMA_VERSION", 3)
        initialize_database(db)
        ensure_library_identity(db, "historic")
        library_registry.initialize_library_registry(registry)
        library_registry.register_source_backup(
            registry, backup_id="historic", source_kind="import", source_identity="old", backup_path="/synthetic",
        )
    assert initialize_database(db)["newly_applied_versions"] == [56, 57, 58, 59, 60]
    assert library_registry.initialize_library_registry(registry)["newly_applied_versions"] == [4, 5, 6]
    assert library_registry.read_library_identity(db) == "historic"
    assert library_registry.get_source_backup(registry, "historic")["source_identity"] == "old"
