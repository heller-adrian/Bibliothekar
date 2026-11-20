"""Full adoption regression for multiple physical copies of one canonical content.

All data are synthetic and remain in isolated test folders.
"""
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
import sqlite3
from zipfile import ZipFile

import pytest

from app import main
from app.database import database_connection
from app.legacy_adoption_catalogue import catalogue_job_id
from app.legacy_adoption_dataset import prove as kernel_dataset_proof
from tests.backend.test_legacy_adoption_integration import fresh_main, _onboard, _adopt, _json
from tests.backend.test_legacy_adoption_inventory import synthetic_dataset


@pytest.mark.parametrize("fresh_main", [True], indirect=True, ids=["native-when-available"])
def test_two_identical_archived_occurrences_are_both_named_and_registered(
    fresh_main, monkeypatch, synthetic_dataset,
):
    _, database, registry, archive = fresh_main
    source = archive.parent / "independent-source-folders"
    originals = [
        source / "private-photos" / "DSCF2922.JPG",
        source / "old-backups" / "deeply" / "nested" / "DSCF2922.JPG",
    ]
    payload = b"byte-identical synthetic JPEG camera original"
    for file in originals:
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes(payload)

    if os.environ.get("ADOPTION_ZFS_ROOT"):
        monkeypatch.setattr("app.legacy_adoption_dataset.prove", kernel_dataset_proof)
    monkeypatch.setattr(main, "NAS_SOURCE_ROOT", source)
    monkeypatch.setattr(
        "app.legacy_adoption_inventory.read_bound_metadata",
        lambda descriptors, _cancel: {
            fd: {"EXIF:ExifIFD:DateTimeOriginal": "2026:07:21 12:00:00"}
            for fd in descriptors
        },
    )
    client = _onboard(fresh_main)
    _adopt(client)
    route = "/api/legacy-adoption/jobs"
    job = route + "/" + _json(client, "POST", route, status=201, json={"root": "nas"})["id"]
    _json(client, "POST", job + "/scan", status=202)
    state = _json(client, "GET", job)
    assert state["state"] == "inventoried"
    assert state["duplicate_files"] == 0  # Neither physical occurrence is excluded.

    draft = {"events": [{"name": "Duplikate", "start_date": "2026-07-21",
                         "end_date": "2026-07-21"}]}
    revision = _json(client, "PUT", job + "/draft", json={**draft, "revision": 0})["revision"]
    plan = _json(client, "POST", job + "/plan", json={"revision": revision})
    assert plan["move_files"] == 2
    assert plan["move_families"] == 2
    assert plan["rename_files"] == 2
    planned = _json(client, "GET", job + "/moves")
    assert len(planned) == 2
    assert {Path(item["target"]).name for item in planned} == {
        "DSCF2922_Duplicate_001.JPG", "DSCF2922_Duplicate_002.JPG",
    }

    _json(client, "POST", job + "/documents")
    command = {"plan_id": plan["id"]}
    _json(client, "POST", job + "/confirm",
          json={**command, "method": "manual", "acknowledged": True})
    bundle = client.get(job + "/download/manual-setup")
    assert bundle.status_code == 200
    with ZipFile(BytesIO(bundle.content)) as packaged:
        packaged.extractall(archive)
    for row in planned:
        src, target = Path(row["source"]), Path(row["target"])
        target.parent.mkdir(parents=True, exist_ok=True)
        src.rename(target)

    assert _json(client, "POST", job + "/verify", json=command)["state"] == "verified"
    assert _json(client, "POST", job + "/finalize", json=command)["state"] == "completed"
    assert all(not path.exists() for path in originals)
    assert all(Path(row["target"]).read_bytes() == payload for row in planned)

    digest = sha256(payload).hexdigest()
    with database_connection(database) as connection:
        assert connection.execute(
            "SELECT count(*) FROM files WHERE job_id=?", (catalogue_job_id(plan),)
        ).fetchone()[0] == 2
        assert connection.execute(
            "SELECT count(DISTINCT family_id) FROM files WHERE job_id=?", (catalogue_job_id(plan),)
        ).fetchone()[0] == 2
    with sqlite3.connect(registry) as connection:
        assert connection.execute(
            "SELECT count(*) FROM source_media WHERE sha256=?", (digest,)
        ).fetchone()[0] == 2
        assert connection.execute(
            """SELECT count(DISTINCT canonical_family_id) FROM source_families
               WHERE backup_id = ?""", ("main:" + catalogue_job_id(plan),)
        ).fetchone()[0] == 1
        assert connection.execute("SELECT count(*) FROM family_claims").fetchone()[0] == 1
        origins = [json.loads(row[0]) for row in connection.execute(
            "SELECT metadata_json FROM source_families")]
        assert len(origins) == 2
        assert all(origin["occurrence_event_id"] == plan["events"][0]["id"]
                   for origin in origins)
