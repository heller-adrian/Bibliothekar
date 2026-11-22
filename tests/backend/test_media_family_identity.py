from hashlib import sha256
from pathlib import Path

import pytest

from app.folder_import import build_folder_import_plan
from app.metadata import analyze_import_tree


def test_verified_capture_families_share_import_targets(tmp_path, monkeypatch):
    source = tmp_path / "source"
    entries, exif = [], []

    def add(relative, *, image_id=None, serial="TEST001", fraction="415", camera="X-T5",
            timestamp="2025:01:28 13:42:03+01:00", original_raw=None):
        path = source / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        data = relative.encode()
        path.write_bytes(data)
        entries.append(dict(relative_path=relative, sha256=sha256(data).hexdigest(), size_bytes=len(data)))
        metadata = {
            "SourceFile": str(path), "EXIF:IFD0:Make": "FUJIFILM", "EXIF:IFD0:Model": camera,
            "EXIF:ExifIFD:DateTimeOriginal": timestamp,
        }
        for key, value in {
            "EXIF:ExifIFD:ImageUniqueID": image_id, "EXIF:ExifIFD:BodySerialNumber": serial,
            "EXIF:ExifIFD:SubSecTimeOriginal": fraction, "EXIF:IFD0:OriginalRawFileName": original_raw,
        }.items():
            if value is not None:
                metadata[key] = value
        exif.append(metadata)

    uid = "00112233445566778899aabbccddeeff"
    add("day/RAW/DSCF7545.RAF", image_id=uid)
    add("day/JPEG/renamed.JPG", image_id=uid, fraction=None, timestamp="2025:01:28 12:42:03Z")
    add("day/DNG/DSCF7545.dng", original_raw="DSCF7545.RAF")
    add("day/Sidecar/DSCF7545.RAF.xmp", image_id=uid, serial=None)
    add("day/JPEG/renamed.JPG.xmp", image_id=None)
    add("day/RAW/twin.NEF")
    add("day/JPEG/twin.JPG")
    # Each pair below contains a contradiction or insufficient evidence.
    for name, raw, jpeg in [
        ("clock", {}, {"timestamp": "2025:01:28 13:42:04+01:00"}),
        ("burst", {}, {"fraction": "420"}),
        ("coarse", {"fraction": None}, {"fraction": None}),
        ("serial", {}, {"serial": "TEST002"}),
        ("no-serial", {"serial": None}, {"serial": None}),
        ("camera", {}, {"camera": "Other Camera"}),
        ("ids", {"image_id": "11112233445566778899aabbccddeeff"}, {"image_id": "22112233445566778899aabbccddeeff"}),
    ]:
        add(f"day/RAW/{name}.RAF", **raw)
        add(f"day/JPEG/{name}.JPG", **jpeg)

    monkeypatch.setattr("app.metadata.run_exiftool", lambda *_args, **_kwargs: exif)
    result = analyze_import_tree(source)
    assert result["summary"]["family_count"] == 16
    families = {family["family_key"]: set(family["members"]) for family in result["families"]}
    complete = {entry["relative_path"] for entry in entries[:5]}
    assert families["day/RAW/DSCF7545"] == complete
    assert families["day/RAW/twin"] == {"day/RAW/twin.NEF", "day/JPEG/twin.JPG"}
    assert all(len(family) == 1 for key, family in families.items()
               if key not in {"day/RAW/twin", "day/RAW/DSCF7545"})

    plan, excluded, _ = build_folder_import_plan(entries, result, tmp_path / "workspace")
    assert not excluded
    paths = {row["source_relative_path"]: Path(row["destination_relative_path"]) for row in plan}
    assert len(set(paths.values())) == len(entries)
    outputs = [paths[path].name for path in complete]
    stem = paths["day/RAW/DSCF7545.RAF"].stem
    assert set(outputs) == {stem + extension for extension in (".RAF", ".JPG", ".dng", ".RAF.xmp", ".JPG.xmp")}
    assert {row["source_relative_path"]: row["sha256"] for row in plan} == {
        item["relative_path"]: item["sha256"] for item in entries
    }


@pytest.mark.parametrize("role", ["RAW", "JPEG", "DNG"])
def test_ambiguous_identity_does_not_merge_any_subset(tmp_path, monkeypatch, role):
    files = ["day/RAW/a.RAF", "day/JPEG/a.JPG", "day/DNG/a.dng"]
    extension = dict(RAW=".RAF", JPEG=".JPG", DNG=".dng")[role]
    files.append(f"day/candidate/{role}/renamed{extension}")
    metadata = []
    for relative in files:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(relative)
        metadata.append({
            "SourceFile": str(path), "EXIF:IFD0:Make": "Synthetic", "EXIF:IFD0:Model": "Camera",
            "EXIF:ExifIFD:DateTimeOriginal": "2025:01:28 12:42:03",
            "EXIF:ExifIFD:ImageUniqueID": "00112233445566778899aabbccddeeff",
        })
    monkeypatch.setattr("app.metadata.run_exiftool", lambda *_args, **_kwargs: metadata)
    assert analyze_import_tree(tmp_path)["summary"]["family_count"] == 4


def test_fujifilm_xh2s_coarse_time_raw_jpeg_dng_and_import(tmp_path, monkeypatch):
    """Regression fixture based on the real X-H2S DSCF7545 metadata."""
    source = tmp_path / "source"
    day = "2025/01/28.01.2025"
    paths = [
        f"{day}/RAW/DSCF7545.RAF",
        f"{day}/JPEG/DSCF7545.JPG",
        f"{day}/DNG/DSCF7545.dng",
    ]
    rows, entries = [], []
    for relative in paths:
        path = source / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = relative.encode()
        path.write_bytes(payload)
        entries.append(dict(relative_path=relative, sha256=sha256(payload).hexdigest(),
                            size_bytes=len(payload)))
        metadata = {
            "SourceFile": str(path),
            "EXIF:IFD0:Make": "FUJIFILM",
            "EXIF:IFD0:Model": "X-H2S",
            "EXIF:ExifIFD:DateTimeOriginal": "2025:01:28 17:11:52",
            "EXIF:ExifIFD:ExposureTime": "1/250",
            "EXIF:ExifIFD:FNumber": "4",
            "EXIF:ExifIFD:ISO": "800",
        }
        if relative.endswith(".dng"):
            metadata["EXIF:IFD0:OriginalRawFileName"] = "DSCF7545.RAF"
        rows.append(metadata)

    monkeypatch.setattr("app.metadata.run_exiftool", lambda *_args, **_kwargs: rows)
    result = analyze_import_tree(source)
    assert result["summary"]["file_count"] == 3
    assert result["summary"]["family_count"] == 1
    [family] = result["families"]
    assert set(family["members"]) == set(paths)
    assert family["family_key"] == f"{day}/RAW/DSCF7545"
    assert all(record["family_key"] == family["family_key"] for record in result["files"])
    plan, excluded, _ = build_folder_import_plan(entries, result, tmp_path / "workspace")
    assert not excluded
    assert len(plan) == 3
    assert len({row["destination_relative_path"] for row in plan}) == 3
    assert {Path(row["destination_relative_path"]).suffix.lower() for row in plan} == {".raf", ".jpg", ".dng"}


@pytest.mark.parametrize("difference", [
    "other_camera",
    "other_second",
    "other_day",
    "different_exposure",
    "different_iso",
    "different_aperture",
    "conflicting_ids",
    "conflicting_serials",
    "different_subseconds",
    "fallback_date_only",
    "different_original_raw",
    "duplicate_raw_candidate",
])
def test_fujifilm_coarse_context_rejects_ambiguous_or_conflicting_match(
    tmp_path, monkeypatch, difference,
):
    source = tmp_path / "source"
    relative = ["2025/day/RAW/DSCF7545.RAF", "2025/day/JPEG/DSCF7545.JPG"]
    if difference == "other_day":
        relative[1] = "2025/another/JPEG/DSCF7545.JPG"
    if difference == "duplicate_raw_candidate":
        relative.append("2025/day/RAF/DSCF7545.RAF")
    if difference == "different_original_raw":
        relative.append("2025/day/DNG/DSCF7545.dng")
    rows = []
    for i, filename in enumerate(relative):
        path = source / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(filename.encode())
        metadata = {
            "SourceFile": str(path),
            "EXIF:IFD0:Make": "FUJIFILM",
            "EXIF:IFD0:Model": "X-H2S",
            "EXIF:ExifIFD:DateTimeOriginal": "2025:01:28 17:11:52",
            "EXIF:ExifIFD:ExposureTime": "1/250",
            "EXIF:ExifIFD:FNumber": "4",
            "EXIF:ExifIFD:ISO": "800",
        }
        if difference == "other_day" and i == 1:
            # Different EXIF capture date is a conflict; directory changes
            # alone must never block matching.
            metadata["EXIF:ExifIFD:DateTimeOriginal"] = "2025:01:29 17:11:52"
        if difference == "other_camera" and i == 1:
            metadata["EXIF:IFD0:Model"] = "X-T5"
        if difference == "other_second" and i == 1:
            metadata["EXIF:ExifIFD:DateTimeOriginal"] = "2025:01:28 17:11:53"
        if difference == "different_exposure" and i == 1:
            metadata["EXIF:ExifIFD:ExposureTime"] = "1/500"
        if difference == "different_iso" and i == 1:
            metadata["EXIF:ExifIFD:ISO"] = "1600"
        if difference == "different_aperture" and i == 1:
            metadata["EXIF:ExifIFD:FNumber"] = "5.6"
        if difference == "conflicting_ids":
            metadata["EXIF:ExifIFD:ImageUniqueID"] = ("00112233445566778899aabbccddeeff", "ffeeddccbbaa99887766554433221100")[i]
        if difference == "conflicting_serials":
            metadata["EXIF:ExifIFD:BodySerialNumber"] = "serial-a" if i == 0 else "serial-b"
        if difference == "different_subseconds":
            metadata["EXIF:ExifIFD:SubSecTimeOriginal"] = "125" if i == 0 else "875"
        if difference == "fallback_date_only" and i == 1:
            metadata["EXIF:ExifIFD:CreateDate"] = metadata.pop("EXIF:ExifIFD:DateTimeOriginal")
        if difference == "different_original_raw" and filename.endswith(".dng"):
            metadata["EXIF:IFD0:OriginalRawFileName"] = "DSCF9999.RAF"
        rows.append(metadata)
    monkeypatch.setattr("app.metadata.run_exiftool", lambda *_args, **_kwargs: rows)
    actual = analyze_import_tree(source)
    assert actual["summary"]["family_count"] == len(relative)


def test_separate_raf_sidecar_can_join_only_its_unique_original(tmp_path, monkeypatch):
    """A corroborated compound sidecar can bind to its exact RAW."""
    source = tmp_path / "photos"
    paths = [
        "2025/day/RAW/DSCF7545.RAF",
        "2025/day/JPEG/DSCF7545.JPG",
        "2025/day/XMP/DSCF7545.RAF.xmp",
    ]
    rows = []
    for path_name in paths:
        path = source / path_name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(path_name)
        row = {
            "SourceFile": str(path),
            "EXIF:IFD0:Make": "FUJIFILM",
            "EXIF:IFD0:Model": "X-H2S",
            "EXIF:ExifIFD:DateTimeOriginal": "2025:01:28 17:11:52",
            "EXIF:ExifIFD:ImageUniqueID": "00112233445566778899aabbccddeeff",
        }
        rows.append(row)
    monkeypatch.setattr("app.metadata.run_exiftool", lambda *_args, **_kwargs: rows)
    result = analyze_import_tree(source)
    assert result["summary"]["family_count"] == 1
    assert set(result["families"][0]["members"]) == set(paths)

    # A second RAW candidate under the same sibling scope makes ownership
    # ambiguous. The sidecar must never be assigned to one arbitrarily.
    other = "2025/day/RAF/DSCF7545.RAF"
    file = source / other
    file.parent.mkdir(parents=True)
    file.write_text(other)
    rows.append({
        "SourceFile": str(file),
        "EXIF:IFD0:Make": "FUJIFILM",
        "EXIF:IFD0:Model": "X-H2S",
        "EXIF:ExifIFD:DateTimeOriginal": "2025:01:28 17:11:52",
        "EXIF:ExifIFD:ImageUniqueID": "00112233445566778899aabbccddeeff",
    })
    unsafe = analyze_import_tree(source)
    assert unsafe["summary"]["family_count"] == 4


def test_historical_fujifilm_export_joins_primary_capture_without_swallowing_dng_variants(
    tmp_path, monkeypatch,
):
    source = tmp_path / "historical"
    base = "2024/12/17.12.2024"
    paths = (
        f"{base}/RAW/DSCF4762.RAF",
        f"{base}/DNG/DSCF4762.dng",
        f"{base}/Export/Foto-Export/DSCF4762.jpg",
        f"{base}/DNG/DSCF4762-2.dng",
        f"{base}/DNG/DSCF4762-Enhanced-NR.dng",
    )
    metadata = []
    for name in paths:
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(name.encode("utf-8"))
        tags = {
            "SourceFile": str(path),
            "EXIF:IFD0:Make": "FUJIFILM",
            "EXIF:IFD0:Model": "X-H2S",
            "EXIF:ExifIFD:DateTimeOriginal": "2024:12:17 17:36:43",
            "EXIF:ExifIFD:ExposureTime": "1/4",
            "EXIF:ExifIFD:FNumber": "4.0",
            "EXIF:ExifIFD:ISO": "1600",
        }
        if name.endswith(("-2.dng", "-Enhanced-NR.dng")):
            tags["EXIF:IFD0:OriginalRawFileName"] = "DSCF4762.RAF"
        metadata.append(tags)
    monkeypatch.setattr("app.metadata.run_exiftool", lambda *_args, **_kwargs: metadata)
    result = analyze_import_tree(source)
    families = {family["family_key"]: set(family["members"]) for family in result["families"]}
    assert families[f"{base}/RAW/DSCF4762"] == set(paths[:3])
    assert families[f"{base}/DNG/DSCF4762-2"] == {paths[3]}
    assert families[f"{base}/DNG/DSCF4762-Enhanced-NR"] == {paths[4]}
    assert result["summary"]["file_count"] == 5
    assert result["summary"]["family_count"] == 3


@pytest.mark.parametrize("different", ["time", "camera", "exposure"])
def test_historical_export_never_joins_contradictory_source(tmp_path, monkeypatch, different):
    source = tmp_path / "historic"
    day = "2024/12/17.12.2024"
    names = (f"{day}/RAW/DSCF4762.RAF", f"{day}/Export/Foto-Export/DSCF4762.jpg")
    exif = []
    for index, name in enumerate(names):
        file = source / name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes(name.encode())
        tags = {
            "SourceFile": str(file),
            "EXIF:IFD0:Make": "FUJIFILM",
            "EXIF:IFD0:Model": "X-H2S",
            "EXIF:ExifIFD:DateTimeOriginal": "2024:12:17 17:36:43",
            "EXIF:ExifIFD:ExposureTime": "1/4",
            "EXIF:ExifIFD:FNumber": "4.0",
            "EXIF:ExifIFD:ISO": "1600",
        }
        if index == 1:
            if different == "time":
                tags["EXIF:ExifIFD:DateTimeOriginal"] = "2024:12:17 17:36:44"
            elif different == "camera":
                tags["EXIF:IFD0:Model"] = "X-T5"
            else:
                tags["EXIF:ExifIFD:ExposureTime"] = "1/250"
        exif.append(tags)
    monkeypatch.setattr("app.metadata.run_exiftool", lambda *_args, **_kwargs: exif)
    result = analyze_import_tree(source)
    assert result["summary"]["family_count"] == 2


@pytest.mark.parametrize("raw_folder,jpeg_folder,dng_folder", [
    ("camera-originals", "finished-photos", "processing/converted"),
    ("random-folder/alpha", "another-collection/deep/nested", "third-place"),
    ("2024/collection-A", "2024/unrelated-name", "backup/unrecognised-folder"),
])
def test_capture_matching_is_independent_of_any_directory_names(
    tmp_path, monkeypatch, raw_folder, jpeg_folder, dng_folder,
):
    """Same file evidence must produce the same family in arbitrary layouts."""
    root = tmp_path / "source"
    cases = [
        (f"{raw_folder}/DSCF4762.RAF", "raw"),
        (f"{jpeg_folder}/DSCF4762.JPG", "jpeg"),
        (f"{dng_folder}/DSCF4762.dng", "dng"),
    ]
    exif = []
    for relative, kind in cases:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(relative.encode("utf-8"))
        row = {
            "SourceFile": str(path),
            "EXIF:IFD0:Make": "FUJIFILM",
            "EXIF:IFD0:Model": "X-H2S",
            "EXIF:ExifIFD:DateTimeOriginal": "2024:12:17 17:36:43",
            "EXIF:ExifIFD:ExposureTime": "1/4",
            "EXIF:ExifIFD:FNumber": "4.0",
            "EXIF:ExifIFD:ISO": "1600",
        }
        if kind == "dng":
            row["EXIF:IFD0:OriginalRawFileName"] = "DSCF4762.RAF"
        exif.append(row)
    monkeypatch.setattr("app.metadata.run_exiftool", lambda *_args, **_kwargs: exif)
    result = analyze_import_tree(root)
    assert result["summary"]["family_count"] == 1
    [family] = result["families"]
    assert set(family["members"]) == {name for name, _ in cases}


def test_reused_camera_name_with_incompatible_metadata_stays_separate_without_folder_hints(
    tmp_path, monkeypatch,
):
    root = tmp_path / "source"
    paths = [
        ("one-unknown-folder/DSCF1234.RAF", "2024:12:17 17:36:43", "1/4"),
        ("totally-different/DSCF1234.JPG", "2024:12:17 17:36:43", "1/250"),
    ]
    exif = []
    for relative, shot, exposure in paths:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(relative.encode())
        exif.append({
            "SourceFile": str(path),
            "EXIF:IFD0:Make": "FUJIFILM",
            "EXIF:IFD0:Model": "X-H2S",
            "EXIF:ExifIFD:DateTimeOriginal": shot,
            "EXIF:ExifIFD:ExposureTime": exposure,
            "EXIF:ExifIFD:FNumber": "4",
            "EXIF:ExifIFD:ISO": "1600",
        })
    monkeypatch.setattr("app.metadata.run_exiftool", lambda *_args, **_kwargs: exif)
    assert analyze_import_tree(root)["summary"]["family_count"] == 2
