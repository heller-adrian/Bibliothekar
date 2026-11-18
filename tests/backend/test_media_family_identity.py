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
    assert all(len(family) == 1 for key, family in families.items() if key not in {"day/RAW/twin", "day/RAW/DSCF7545"})

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
