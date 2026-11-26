"""Full adoption regression for multiple physical copies of one canonical content.

All data are synthetic and remain in isolated test folders.
"""
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
import sqlite3
import sys
from zipfile import ZipFile

import pytest

from app import legacy_adoption_host as host, legacy_adoption_package as package, main
from app.database import database_connection
from app.legacy_adoption_catalogue import catalogue_job_id
from app.legacy_adoption_dataset import prove as kernel_dataset_proof
from tests.backend.test_legacy_adoption_host import _macos_rename
from tests.backend.test_legacy_adoption_integration import fresh_main, _onboard, _adopt, _json
from tests.backend.test_legacy_adoption_inventory import synthetic_dataset


@pytest.mark.parametrize("fresh_main", [True], indirect=True, ids=["native-when-available"])
@pytest.mark.parametrize(("method", "kind"), [
    ("manual", "full-copies"), ("manual", "shared-jpeg"),
    ("manual", "bound-sidecar"), ("script", "bound-sidecar"),
])
def test_two_archived_occurrences_are_both_named_and_registered(
    fresh_main, monkeypatch, synthetic_dataset, method, kind,
):
    distinct_raw = kind != "full-copies"
    bound_sidecar = kind == "bound-sidecar"
    _, database, registry, archive = fresh_main
    source = archive.parent / "independent-source-folders"
    originals = [
        source / "private-photos" / "DSCF2922.JPG",
        source / "old-backups" / "deeply" / "nested" / "DSCF2922.JPG",
    ]
    payload = b"byte-identical synthetic JPEG camera original"
    xmp_bytes = (
        b'<x:xmpmeta xmlns:x="adobe:ns:meta/">'
        b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
        b'<rdf:Description xmlns:crs="http://ns.adobe.com/camera-raw-settings/1.0/"'
        b' crs:RawFileName="DSCF2922.RAF"/>'
        b'</rdf:RDF></x:xmpmeta>'
    )
    expected = {}
    for index, file in enumerate(originals):
        file.parent.mkdir(parents=True, exist_ok=True)
        expected[file] = payload
        if distinct_raw:
            expected[file.with_suffix(".RAF")] = f"distinct RAW original {index}".encode()
        if bound_sidecar:
            expected[file.with_suffix(".xmp")] = xmp_bytes
    for file, content in expected.items():
        file.write_bytes(content)

    if os.environ.get("ADOPTION_ZFS_ROOT"):
        monkeypatch.setattr("app.legacy_adoption_dataset.prove", kernel_dataset_proof)
    monkeypatch.setattr(main, "NAS_SOURCE_ROOT", source)

    def metadata(descriptors, _cancel):
        result = {}
        for fd in descriptors:
            tags = {"EXIF:ExifIFD:DateTimeOriginal": "2026:07:21 12:00:00"}
            if os.pread(fd, 10, 0).startswith(b"<x:xmpmeta"):
                tags = {"XMP:XMP-exif:DateTimeOriginal": "2026:07:21 12:00:00",
                        "XMP:XMP-crs:RawFileName": "DSCF2922.RAF"}
            result[fd] = tags
        return result

    monkeypatch.setattr("app.legacy_adoption_inventory.read_bound_metadata", metadata)
    client = _onboard(fresh_main)
    _adopt(client)
    route = "/api/legacy-adoption/jobs"
    job = route + "/" + _json(client, "POST", route, status=201, json={"root": "nas"})["id"]
    _json(client, "POST", job + "/scan", status=202)
    state = _json(client, "GET", job)
    assert state["state"] == "inventoried"
    assert state["duplicate_files"] == 0  # Neither physical occurrence is excluded.

    if kind == "shared-jpeg":
        event = {"event_kind": "no_event", "segments": [{"day_key": "2026-07-21"}]}
    else:
        event = {"name": "Duplikate", "start_date": "2026-07-21", "end_date": "2026-07-21"}
    draft = {"events": [event]}
    revision = _json(client, "PUT", job + "/draft", json={**draft, "revision": 0})["revision"]
    plan = _json(client, "POST", job + "/plan", json={"revision": revision, "filename_method": method})
    assert plan["move_files"] == len(expected)
    assert plan["move_families"] == 2
    planned = _json(client, "GET", job + "/moves")
    assert len(planned) == len(expected)
    endings = {file.suffix for file in expected}
    if method == "manual" and bound_sidecar:
        assert plan["rename_files"] == 0
        directories = set(_json(client, "GET", job + "/directories"))
        targets = {Path(row["target_path"]) for row in planned}
        assert {target.parent.name for target in targets} == {
            "DSCF2922_Duplicate_001", "DSCF2922_Duplicate_002",
        }
        assert all(str(target.parent) in directories for target in targets)
        assert all(Path(row["target"]).name == Path(row["source"]).name for row in planned)
    elif method == "manual":
        assert plan["rename_files"] == len(expected)
        assert {Path(row["target"]).name for row in planned} == {
            f"DSCF2922_Duplicate_{index:03d}{ending}" for index in (1, 2) for ending in endings
        }
    else:
        assert plan["rename_files"] == len(expected)
        assert {Path(row["target"]).stem.rsplit("_", 1)[1] for row in planned} == {"001", "002"}
        assert all("_Duplicate_" in Path(row["target"]).stem for row in planned)

    _json(client, "POST", job + "/documents")
    command = {"plan_id": plan["id"]}
    if method == "manual":
        _json(client, "POST", job + "/confirm",
              json={**command, "method": "manual", "acknowledged": True})
        bundle = client.get(job + "/download/manual-setup")
        assert bundle.status_code == 200
        with ZipFile(BytesIO(bundle.content)) as packaged:
            packaged.extractall(archive)
        for row in planned:
            src, target = Path(row["source"]), Path(row["target"])
            assert target.parent.is_dir()
            src.rename(target)
        assert _json(client, "POST", job + "/verify", json=command)["state"] == "verified"
    else:
        appdata = database.parent / "duplicate-script-appdata"
        appdata.mkdir()
        monkeypatch.setattr(package, "appdata_root", lambda: appdata)
        if sys.platform == "darwin":
            monkeypatch.setattr(host, "mount_id", lambda _fd: 1)
            monkeypatch.setattr(host, "rename_noreplace", _macos_rename)
        probe = _json(client, "POST", job + "/script/probe", json={
            **command, "appdata": str(appdata), "source": str(source), "archive": str(archive),
        })
        package_path = Path(probe["host"]["package"])
        device, inode = host.inode(package_path.stat())
        args = ["--package", str(package_path), "--source", str(source), "--archive", str(archive),
                "--package-device", str(device), "--package-inode", str(inode)]
        assert host.main(["probe", *args, "--sha256", probe["sha256"]]) == 0
        _json(client, "POST", job + "/confirm", status=202, json={
            **command, "acknowledged": True, "method": "script", "probe_sha256": probe["sha256"],
        })
        _json(client, "POST", job + "/script/release", json=command)
        release = json.loads((package_path / "permission.json").read_bytes())
        assert host.main(["apply", *args, "--sha256", release["manifest"]]) == 0
        for row in planned:
            if row["relative_path"].endswith(".xmp"):
                src = Path(row["source"])
                expected[src] = xmp_bytes.replace(
                    b'DSCF2922.RAF', row["xmp_new_raw_name"].encode(),
                )
                assert sha256(expected[src]).hexdigest() == row["current_sha256"]
    assert _json(client, "POST", job + "/finalize", json=command)["state"] == "completed"
    assert all(not path.exists() for path in expected)
    assert all(Path(row["target"]).read_bytes() == expected[Path(row["source"])] for row in planned)

    digest = sha256(payload).hexdigest()
    with database_connection(database) as connection:
        assert connection.execute(
            "SELECT count(*) FROM files WHERE job_id=?", (catalogue_job_id(plan),)
        ).fetchone()[0] == len(expected)
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
        ).fetchone()[0] == (2 if distinct_raw else 1)
        assert connection.execute("SELECT count(*) FROM family_claims").fetchone()[0] == (2 if distinct_raw else 1)
        origins = [json.loads(row[0]) for row in connection.execute(
            "SELECT metadata_json FROM source_families")]
        assert len(origins) == 2
        assert all(origin["occurrence_event_id"] == plan["events"][0]["id"]
                   for origin in origins)
