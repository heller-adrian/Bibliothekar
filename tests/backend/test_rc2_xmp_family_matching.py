"""RC2 regression tests for real-world cross-folder Adobe XMP sidecars.

Synthetic metadata and file bytes only. No production media are modified.
"""
from pathlib import Path

import pytest

from app.metadata import analyze_import_tree


def _analyse(tmp_path, monkeypatch, rows):
    root = tmp_path / "photos"
    metadata = []
    for relative, tags in rows:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(relative.encode("utf-8"))
        metadata.append({"SourceFile": str(path), **tags})
    monkeypatch.setattr("app.metadata.run_exiftool", lambda *_args, **_kwargs: metadata)
    result = analyze_import_tree(root)
    families = [set(family["members"]) for family in result["families"]]
    return families, result, root


def _camera(day="2025:04:16 19:37:26", *, exposure="1/50", camera="X-H2S"):
    return {
        "EXIF:IFD0:Make": "FUJIFILM",
        "EXIF:IFD0:Model": camera,
        "EXIF:ExifIFD:DateTimeOriginal": day,
        "EXIF:ExifIFD:ExposureTime": exposure,
        "EXIF:ExifIFD:FNumber": "5.6",
        "EXIF:ExifIFD:ISO": "3200",
    }


def _xmp(day="2025:04:16 19:37:26+02:00", *, raw_name="DSCF2915.RAF",
         exposure="1/100", camera="X-H2S"):
    result = {
        "XMP:XMP-tiff:Make": "FUJIFILM",
        "XMP:XMP-tiff:Model": camera,
        "XMP:XMP-exif:DateTimeOriginal": day,
        "XMP:XMP-exif:ExposureTime": exposure,
        "XMP:XMP-exif:FNumber": "5.6",
        "XMP:XMP-exif:ISO": "3200",
    }
    if raw_name is not None:
        result["XMP:XMP-crs:RawFileName"] = raw_name
    return result


def test_real_dscf2915_raf_jpeg_xmp_in_arbitrary_folders(tmp_path, monkeypatch):
    """Actual reported camera/time/path situation, with edited XMP exposure."""
    paths = {
        "2025/Sammlung/Rohformat/DSCF2915.RAF",
        "2025/Sammlung/Bilder/DSCF2915.JPG",
        "2025/Sammlung/Sonstiges/DSCF2915.xmp",
    }
    families, result, root = _analyse(tmp_path, monkeypatch, [
        ("2025/Sammlung/Rohformat/DSCF2915.RAF", _camera()),
        ("2025/Sammlung/Bilder/DSCF2915.JPG", _camera()),
        ("2025/Sammlung/Sonstiges/DSCF2915.xmp", _xmp()),
    ])
    assert families == [paths]
    assert result["summary"]["family_count"] == 1
    assert result["summary"]["file_count"] == 3
    assert (root / "2025/Sammlung/Sonstiges/DSCF2915.xmp").read_bytes().endswith(b".xmp")


def test_plain_xmp_without_rawfilename_needs_time_and_camera(tmp_path, monkeypatch):
    paths = {"other/DSCF2915.RAF", "anything/DSCF2915.JPG", "third/DSCF2915.xmp"}
    families, _, _ = _analyse(tmp_path, monkeypatch, [
        ("other/DSCF2915.RAF", _camera()),
        ("anything/DSCF2915.JPG", _camera()),
        ("third/DSCF2915.xmp", _xmp(raw_name=None, exposure="1/50")),
    ])
    assert families == [paths]


def test_xmp_with_rawfilename_rejects_reused_ambiguous_raw_name(tmp_path, monkeypatch):
    files = [
        "A/DSCF2915.RAF",
        "B/DSCF2915.RAF",
        "C/DSCF2915.xmp",
    ]
    families, _, _ = _analyse(tmp_path, monkeypatch, [
        (files[0], _camera()),
        (files[1], _camera()),
        (files[2], _xmp()),
    ])
    assert {files[2]} in families
    assert len(families) == 3


@pytest.mark.parametrize("reason", ["wrong_time", "wrong_camera", "wrong_raw_name"])
def test_xmp_reference_does_not_override_conflicting_identity(tmp_path, monkeypatch, reason):
    metadata = _xmp()
    if reason == "wrong_time":
        metadata["XMP:XMP-exif:DateTimeOriginal"] = "2025:04:16 19:37:27+02:00"
    elif reason == "wrong_camera":
        metadata["XMP:XMP-tiff:Model"] = "X-T5"
    else:
        metadata["XMP:XMP-crs:RawFileName"] = "OTHER.RAF"
    families, _, _ = _analyse(tmp_path, monkeypatch, [
        ("odd/a/DSCF2915.RAF", _camera()),
        ("odd/b/DSCF2915.xmp", metadata),
    ])
    assert {"odd/b/DSCF2915.xmp"} in families
    assert len(families) == 2


def test_compound_raw_xmp_legacy_matching_still_works(tmp_path, monkeypatch):
    paths = {"one/DSCF2915.RAF", "two/DSCF2915.RAF.xmp"}
    families, _, _ = _analyse(tmp_path, monkeypatch, [
        ("one/DSCF2915.RAF", _camera()),
        ("two/DSCF2915.RAF.xmp", {}),
    ])
    assert families == [paths]


def test_plain_xmp_without_proof_remains_unassigned(tmp_path, monkeypatch):
    families, _, _ = _analyse(tmp_path, monkeypatch, [
        ("one/DSCF2915.RAF", _camera()),
        ("two/DSCF2915.xmp", {}),
    ])
    assert len(families) == 2


def test_rawfilename_is_recorded_in_capture_identity():
    from app.media_family_identity import capture_identity
    result = capture_identity({"XMP:XMP-crs:RawFileName": "DSCF2915.RAF"})
    assert result["sidecar_raw"] == "dscf2915.raf"


def test_explicit_rawfilename_works_when_xmp_create_date_is_an_edit_timestamp(tmp_path, monkeypatch):
    """An XMP edit timestamp must not be compared to the camera shutter time."""
    files = {"raw/DSCF2915.RAF", "edit/DSCF2915.xmp"}
    sidecar = {
        "XMP:XMP-tiff:Make": "FUJIFILM",
        "XMP:XMP-tiff:Model": "X-H2S",
        "XMP:XMP-xmp:CreateDate": "2026:11:21 15:03:00+01:00",
        "XMP:XMP-crs:RawFileName": "DSCF2915.RAF",
    }
    families, _, _ = _analyse(tmp_path, monkeypatch, [
        ("raw/DSCF2915.RAF", _camera()),
        ("edit/DSCF2915.xmp", sidecar),
    ])
    assert families == [files]
