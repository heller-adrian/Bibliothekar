from app.main import APP_VERSION, _event_edit_payload_within_new_range
from app.event_structure import build_event_preview
import inspect
import app.main as main_module


def _family(fid, capture):
    return {
        "family_id": fid,
        "family_key": f"F{fid}",
        "selected_capture_time": capture,
        "capture_time_confidence": "high",
        "day_key": capture[:10],
        "has_date": True,
        "file_count": 2,
        "total_size_bytes": 100,
        "review_required_count": 0,
    }


def test_version_0206():
    assert APP_VERSION == "0.22.1"


def test_multisegment_shrink_derives_union_without_requiring_old_membership():
    families = [
        _family(1, "2026-07-20T11:30:00"),
        _family(2, "2026-07-20T14:30:00"),
        _family(3, "2026-07-20T16:00:00"),
        _family(4, "2026-07-20T20:00:00"),
    ]
    payload = {
        "event_kind": "event",
        "event_name": "Test 20",
        "start_date": "2026-07-20",
        "end_date": "2026-07-20",
        "preserve_day_folders": False,
        "child_segments": [
            {"id": "c1", "name": "Mittag", "start_time": "11:00", "end_time": "14:00"},
            {"id": "c2", "name": "Nachmittag - Abend", "start_time": "15:01", "end_time": "23:59"},
        ],
    }
    normalized = _event_edit_payload_within_new_range(payload, families)
    assert normalized["selected_family_ids"] == [1, 3, 4]

    first = normalized["child_segments"][0]
    preview_payload = dict(normalized)
    preview_payload.pop("selected_family_ids", None)
    preview_payload.pop("selected_day_keys", None)
    preview_payload.update({
        "uses_time_range": True,
        "child_event_name": first["name"],
        "start_time": first["start_time"],
        "end_time": first["end_time"],
    })
    preview = build_event_preview(preview_payload, families)
    assert preview["selected_family_ids"] == [1]


def test_endpoint_multisegment_preview_does_not_pass_union_into_first_child_validator():
    source = inspect.getsource(main_module.api_update_event)
    assert 'preview_payload.pop("selected_family_ids", None)' in source
    assert 'preview["child_segments"] = child_segments' in source
