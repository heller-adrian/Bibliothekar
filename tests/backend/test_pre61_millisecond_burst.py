"""Pre.6.1: real EXIF milliseconds, burst naming, unchanged ordinary names."""
from pathlib import Path

from app.folder_import import build_folder_import_plan
from app.metadata import build_candidates


def _make(count, *, fractional=True, start=0):
    entries, files, families = [], [], []
    for i in range(start, start + count):
        filename = f"DSCF{i:04d}.JPG"
        capture = "2026-07-19T17:11:37"
        if fractional:
            capture += f".{(i * 25) % 1000:03d}"
        capture += "+03:00"
        item = {
            "relative_path": filename, "filename": filename,
            "family_key": filename[:-4], "media_type": "jpeg",
            "selected_capture_time": capture,
            "capture_time_confidence": "high",
            "camera_make": "FUJIFILM", "camera_model": "X-E5",
        }
        entries.append({"relative_path": filename, "size_bytes": 10+i, "sha256": "x"+str(i)})
        files.append(item)
        families.append({
            "family_key": item["family_key"], "selected_capture_time": capture,
            "capture_time_confidence": "high",
        })
    return entries, {"files": files, "families": families}


def test_normal_single_capture_keeps_exact_legacy_filename(tmp_path):
    entries, analysis = _make(1)
    plan, _, summary = build_folder_import_plan(entries, analysis, tmp_path)
    assert plan[0]["destination_relative_path"] == (
        "2026/2026-07-19/20260719_171137_Fuji-X-E5.JPG"
    )
    assert summary["burst_family_count"] == 0


def test_forty_distinct_millisecond_captures_have_correct_three_digits(tmp_path):
    entries, analysis = _make(40)
    plan, _, summary = build_folder_import_plan(entries, analysis, tmp_path)
    names = {Path(item["destination_relative_path"]).name for item in plan}
    assert len(names) == 40
    assert summary["burst_family_count"] == 40
    for i in range(40):
        assert f"20260719_171137{i * 25:03d}_Fuji-X-E5.JPG" in names
    assert "20260719_171137_Fuji-X-E5.JPG" not in names


def test_existing_unsuffixed_second_requires_milliseconds_on_new_capture(tmp_path):
    day = tmp_path / "2026" / "2026-07-19"
    day.mkdir(parents=True)
    existing = day / "20260719_171137_Fuji-X-E5.JPG"
    existing.write_bytes(b"historical")
    entries, analysis = _make(1, start=12)
    plan, _, summary = build_folder_import_plan(entries, analysis, tmp_path)
    assert Path(plan[0]["destination_relative_path"]).name == (
        "20260719_171137300_Fuji-X-E5.JPG"
    )
    assert summary["burst_family_count"] == 1
    assert existing.read_bytes() == b"historical"


def test_unknown_fraction_uses_explicit_sequence_not_fake_milliseconds(tmp_path):
    entries, analysis = _make(2, fractional=False)
    plan, _, summary = build_folder_import_plan(entries, analysis, tmp_path)
    names = [Path(item["destination_relative_path"]).name for item in plan]
    assert names == [
        "20260719_171137_Fuji-X-E5_Burst_001.JPG",
        "20260719_171137_Fuji-X-E5_Burst_002.JPG",
    ]
    assert summary["burst_without_subseconds_count"] == 2


def test_same_exact_millisecond_never_overwrites_another_family(tmp_path):
    entries, analysis = _make(2)
    analysis["families"][1]["selected_capture_time"] = "2026-07-19T17:11:37.000+03:00"
    analysis["files"][1]["selected_capture_time"] = "2026-07-19T17:11:37.000+03:00"
    plan, _, _ = build_folder_import_plan(entries, analysis, tmp_path)
    assert sorted(Path(item["destination_relative_path"]).stem for item in plan) == [
        "20260719_171137000_Fuji-X-E5",
        "20260719_171137000_Fuji-X-E5_001",
    ]


def test_metadata_uses_real_exif_subsectime_original_with_offset():
    candidates = build_candidates({
        "EXIF:ExifIFD:DateTimeOriginal": "2026:07:19 17:11:37",
        "EXIF:ExifIFD:SubSecTimeOriginal": "425",
        "EXIF:ExifIFD:OffsetTimeOriginal": "+03:00",
    }, "raw")
    original = next(c for c in candidates if c["tag_name"] == "EXIF:ExifIFD:DateTimeOriginal")
    assert original["normalized_datetime"] == "2026-07-19T17:11:37.425000+03:00"


def test_metadata_does_not_fabricate_missing_milliseconds():
    candidates = build_candidates({
        "EXIF:ExifIFD:DateTimeOriginal": "2026:07:19 17:11:37",
        "EXIF:ExifIFD:OffsetTimeOriginal": "+03:00",
    }, "jpeg")
    original = next(c for c in candidates if c["tag_name"] == "EXIF:ExifIFD:DateTimeOriginal")
    assert original["normalized_datetime"] == "2026-07-19T17:11:37+03:00"
