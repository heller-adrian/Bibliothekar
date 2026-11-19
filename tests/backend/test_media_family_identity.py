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
    assert result["summary"]["family_count"] == 14
    families = {family["family_key"]: set(family["members"]) for family in result["families"]}
    complete = {entry["relative_path"] for entry in entries[:5]}
    assert families["day/RAW/DSCF7545"] == complete
    assert families["day/RAW/twin"] == {"day/RAW/twin.NEF", "day/JPEG/twin.JPG"}
    assert families["day/RAW/coarse"] == {"day/RAW/coarse.RAF", "day/JPEG/coarse.JPG"}
    assert families["day/RAW/no-serial"] == {"day/RAW/no-serial.RAF", "day/JPEG/no-serial.JPG"}
    assert all(len(family) == 1 for key, family in families.items()
               if key not in {"day/RAW/twin", "day/RAW/DSCF7545",
                              "day/RAW/coarse", "day/RAW/no-serial"})

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
    """An XMP without own capture metadata can identify its exact RAF by name."""
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
        row = {"SourceFile": str(path)}
        if path.suffix.lower() != ".xmp":
            row.update({
                "EXIF:IFD0:Make": "FUJIFILM",
                "EXIF:IFD0:Model": "X-H2S",
                "EXIF:ExifIFD:DateTimeOriginal": "2025:01:28 17:11:52",
            })
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
    })
    unsafe = analyze_import_tree(source)
    assert unsafe["summary"]["family_count"] == 4
