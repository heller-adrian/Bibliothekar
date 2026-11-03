"""pre.6.1: actual Exif milliseconds, not frame numbers, only on collisions."""
from pathlib import Path
from app.metadata import build_candidates
from app.folder_import import build_folder_import_plan


def fixture(files):
    entries = []
    records = []
    families = []
    for name, instant, kind in files:
        stem = Path(name).stem
        family = f"DCIM/{stem}"
        records.append({
            "family_key": family, "relative_path": f"DCIM/{name}",
            "filename": name, "media_type": kind,
            "selected_capture_time": instant, "capture_time_confidence": "high",
            "camera_make": "FUJIFILM", "camera_model": "X-E5",
        })
        entries.append({
            "relative_path": f"DCIM/{name}", "size_bytes": 100 + len(name),
            "sha256": stem.ljust(64, "0")[:64],
        })
        if family not in [f["family_key"] for f in families]:
            families.append({
                "family_key": family, "selected_capture_time": instant,
                "capture_time_confidence": "high",
            })
    return entries, {"files": records, "families": families}


def names(tmp_path, files):
    entries, analysis = fixture(files)
    plan, _, _ = build_folder_import_plan(entries, analysis, tmp_path)
    return sorted(Path(row["destination_relative_path"]).name for row in plan)


def test_isolated_name_unchanged(tmp_path):
    result = names(tmp_path, [("DSCF001.JPG", "2026-07-19T17:11:37.024+03:00", "jpeg")])
    assert result == ["20260719_171137_Fuji-X-E5.JPG"]


def test_forty_distinct_families_get_real_three_digit_milliseconds(tmp_path):
    files = [
        (f"DSCF{i:04d}.JPG", f"2026-07-19T17:11:37.{i*25:03d}+03:00", "jpeg")
        for i in range(40)
    ]
    observed = names(tmp_path, files)
    expected = sorted(
        f"20260719_171137{i*25:03d}_Fuji-X-E5.JPG"
        for i in range(40)
    )
    assert observed == expected


def test_raw_and_jpeg_share_one_family_name(tmp_path):
    files = [
        ("DSCF001.RAF", "2026-07-19T17:11:37.010+03:00", "raw"),
        ("DSCF001.JPG", "2026-07-19T17:11:37.010+03:00", "jpeg"),
        ("DSCF002.RAF", "2026-07-19T17:11:37.035+03:00", "raw"),
        ("DSCF002.JPG", "2026-07-19T17:11:37.035+03:00", "jpeg"),
    ]
    assert names(tmp_path, files) == sorted([
        "20260719_171137010_Fuji-X-E5.JPG",
        "20260719_171137010_Fuji-X-E5.RAF",
        "20260719_171137035_Fuji-X-E5.JPG",
        "20260719_171137035_Fuji-X-E5.RAF",
    ])


def test_prior_filename_does_not_get_overwritten(tmp_path):
    day = tmp_path / "2026/2026-07-19"
    day.mkdir(parents=True)
    existing = day / "20260719_171137_Fuji-X-E5.JPG"
    existing.write_bytes(b"original")
    assert names(tmp_path, [
        ("DSCF002.JPG", "2026-07-19T17:11:37.250+03:00", "jpeg")
    ]) == ["20260719_171137250_Fuji-X-E5.JPG"]
    assert existing.read_bytes() == b"original"


def test_no_subseconds_never_invents_milliseconds(tmp_path):
    assert names(tmp_path, [
        ("DSCF001.JPG", "2026-07-19T17:11:37+03:00", "jpeg"),
        ("DSCF002.JPG", "2026-07-19T17:11:37+03:00", "jpeg"),
    ]) == [
        "20260719_171137_Fuji-X-E5_001.JPG",
        "20260719_171137_Fuji-X-E5_002.JPG",
    ]


def test_exif_subsec_is_merged_before_offset():
    candidates = build_candidates({
        "EXIF:ExifIFD:DateTimeOriginal": "2026:07:19 17:11:37",
        "EXIF:ExifIFD:SubSecTimeOriginal": "025",
        "EXIF:ExifIFD:OffsetTimeOriginal": "+03:00",
    }, "raw")
    assert candidates[0]["normalized_datetime"] == "2026-07-19T17:11:37.025000+03:00"


def test_exif_zero_milliseconds_are_not_lost():
    candidates = build_candidates({
        "EXIF:ExifIFD:DateTimeOriginal": "2026:07:19 17:11:37",
        "EXIF:ExifIFD:SubSecTimeOriginal": "000",
        "EXIF:ExifIFD:OffsetTimeOriginal": "+03:00",
    }, "raw")
    assert candidates[0]["normalized_datetime"] == "2026-07-19T17:11:37.000000+03:00"


def test_raw_jpeg_mixed_precision_is_one_capture_family(tmp_path, monkeypatch):
    from app import metadata
    raf = tmp_path / "DSCF0001.RAF"
    jpeg = tmp_path / "DSCF0001.JPG"
    raf.write_bytes(b"synthetic-raf")
    jpeg.write_bytes(b"synthetic-jpeg")
    def exif_response(_source_root, **_kwargs):
        return [
            {
                "SourceFile": str(raf),
                "EXIF:ExifIFD:DateTimeOriginal": "2026:07:19 17:11:37",
                "EXIF:ExifIFD:SubSecTimeOriginal": "025",
                "EXIF:ExifIFD:OffsetTimeOriginal": "+03:00",
            },
            {
                "SourceFile": str(jpeg),
                "EXIF:ExifIFD:DateTimeOriginal": "2026:07:19 17:11:37",
                "EXIF:ExifIFD:OffsetTimeOriginal": "+03:00",
            },
        ]
    monkeypatch.setattr(metadata, "run_exiftool", exif_response)
    analysis = metadata.analyze_tree(tmp_path)
    assert len(analysis["families"]) == 1
    assert analysis["families"][0]["selected_capture_time"] == (
        "2026-07-19T17:11:37.025000+03:00"
    )
    assert analysis["families"][0]["capture_time_confidence"] == "high"
