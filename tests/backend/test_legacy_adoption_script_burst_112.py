"""Legacy-adoption script must reuse the unchanged pre.6.1 Burst naming rules."""
import os
from pathlib import Path

import pytest

from app.legacy_adoption_plan import create_plan, plan_moves
from tests.backend.test_legacy_adoption_plan import inventory, _draft, _scan


@pytest.mark.parametrize("scenario,expected", [
    ("distinct_milliseconds", {
        "20260721_120000125_Fuji-X-E5.JPG",
        "20260721_120000875_Fuji-X-E5.JPG",
    }),
    ("identical_millisecond_different_bytes", {
        "20260721_120000425_Fuji-X-E5_001.JPG",
        "20260721_120000425_Fuji-X-E5_002.JPG",
    }),
    ("byte_identical_copies", {
        "20260721_120000425_Fuji-X-E5_Duplicate_001.JPG",
        "20260721_120000425_Fuji-X-E5_Duplicate_002.JPG",
    }),
    ("missing_milliseconds", {
        "20260721_120000_Fuji-X-E5_Burst_001.JPG",
        "20260721_120000_Fuji-X-E5_Burst_002.JPG",
    }),
])
def test_script_adoption_precise_burst_vs_real_duplicates(
    inventory, monkeypatch, scenario, expected,
):
    context, source, registry = inventory
    a = source / "anywhere-A" / "FIRST0001.JPG"
    b = source / "different" / "nested" / "SECOND0001.JPG"
    for path in (a, b):
        path.parent.mkdir(parents=True, exist_ok=True)
    a.write_bytes(b"photo-one")
    b.write_bytes(b"photo-one" if scenario == "byte_identical_copies" else b"photo-two")

    def metadata(descriptors, _cancel):
        result = {}
        for fd in descriptors:
            content = os.pread(fd, 32, 0)
            row = {
                "EXIF:IFD0:Make": "FUJIFILM",
                "EXIF:IFD0:Model": "X-E5",
                "EXIF:ExifIFD:DateTimeOriginal": "2026:07:21 12:00:00",
            }
            if scenario != "missing_milliseconds":
                row["EXIF:ExifIFD:SubSecTimeOriginal"] = (
                    "125" if scenario == "distinct_milliseconds" and content == b"photo-one"
                    else "875" if scenario == "distinct_milliseconds" else "425"
                )
            result[fd] = row
        return result

    monkeypatch.setattr("app.legacy_adoption_inventory.read_bound_metadata", metadata)
    job = _scan(context, source)
    plan = create_plan(context, registry, job, _draft(), filename_method="script")
    assert plan["move_files"] == 2
    assert {Path(item["target"]).name for item in plan_moves(context, job)} == expected
