"""Pre6.1: EXIF subsecond precision in a mixed RAF/JPEG/XMP camera family."""
from app.metadata import analyze_tree

def test_raf_subsecond_and_jpeg_whole_second_are_one_family(tmp_path, monkeypatch):
    records = []
    for name, frac in (("DSCF0001.RAF", "425"), ("DSCF0001.JPG", None), ("DSCF0001.xmp", None)):
        p = tmp_path / name
        p.write_bytes(b"fixture")
        row = {"SourceFile": str(p), "EXIF:ExifIFD:DateTimeOriginal": "2026:07:19 17:11:37",
               "EXIF:IFD0:Make": "FUJIFILM", "EXIF:IFD0:Model": "X-E5"}
        if frac is not None:
            row["EXIF:ExifIFD:SubSecTimeOriginal"] = frac
        records.append(row)
    monkeypatch.setattr("app.metadata.run_exiftool", lambda *args, **kwargs: records)
    actual = analyze_tree(tmp_path, include_other=False)
    assert len(actual["families"]) == 1
    f = actual["families"][0]
    assert f["selected_capture_time"].startswith("2026-07-19T17:11:37.425")
    assert f["capture_time_confidence"] == "high"

def test_two_different_precise_values_remain_a_conflict(tmp_path, monkeypatch):
    records = []
    for name, frac in (("DSCF0002.RAF", "125"), ("DSCF0002.JPG", "875")):
        p = tmp_path / name
        p.write_bytes(b"fixture")
        records.append({"SourceFile":str(p),"EXIF:ExifIFD:DateTimeOriginal":"2026:07:19 17:11:37",
                        "EXIF:ExifIFD:SubSecTimeOriginal":frac})
    monkeypatch.setattr("app.metadata.run_exiftool", lambda *args, **kwargs: records)
    actual = analyze_tree(tmp_path, include_other=False)
    assert actual["families"][0]["capture_time_confidence"] == "conflict"
