from app.event_structure import build_event_preview
from app.structure_view import render_structure


def _family(family_id, capture):
    return {
        "family_id": family_id,
        "selected_capture_time": capture,
        "day_key": capture[:10],
        "has_date": True,
        "file_count": 2,
    }


def test_02611_structure_renderer_uses_branch_specific_days():
    lines = render_structure(
        "2026",
        "07-20 - Test",
        ["2026-07-20", "2026-07-21"],
        [{
            "folder_name": "07-20–07-21 - Test 2",
            "day_keys": ["2026-07-20"],
        }],
        True,
    )
    text = "\n".join(lines)
    child = text.split("07-20–07-21 - Test 2", 1)[1]
    assert "2026-07-20" in child
    assert "2026-07-21" not in child


def test_02611_empty_child_has_direct_triplet_not_fake_day_folders():
    text = "\n".join(render_structure(
        "2026",
        "07-20 - Test",
        ["2026-07-20"],
        [{"folder_name": "Leer", "day_keys": []}],
        True,
    ))
    child = text.split("Leer", 1)[1]
    assert "2026-07-20" not in child
    assert "Alle" in child and "Sortiert" in child and "Export" in child


def test_02611_preview_reports_partial_empty_child_days_without_rendering_them():
    preview = build_event_preview(
        {
            "event_kind": "event",
            "event_name": "Test",
            "start_date": "2026-07-20",
            "end_date": "2026-07-21",
            "start_time": "00:00",
            "end_time": "23:59",
            "uses_time_range": True,
            "preserve_day_folders": True,
            "subevents": [{
                "name": "Test 2",
                "start_datetime": "2026-07-20T12:00:00",
                "end_datetime": "2026-07-21T17:00:59",
            }],
        },
        [
            _family(1, "2026-07-20T13:11:13"),
            _family(2, "2026-07-20T20:20:06"),
            _family(3, "2026-07-21T17:28:08"),
        ],
    )
    assert preview["empty_subevents"] == []
    # 0.43.0: Ein fotofreier Kalendertag innerhalb des definierten
    # Unterereigniszeitraums ist keine Lücke und braucht keine Bestätigung.
    assert preview["empty_subevent_days"] == []
    child = preview["structure_text"].split(
        "07-20–07-21 - Test 2", 1
    )[1].split("\n\nZeitraum:", 1)[0]
    assert "2026-07-20" in child
    assert "2026-07-21" not in child
