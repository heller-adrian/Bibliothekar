"""Canonical time extraction from ordinary and millisecond-named exports."""
from app.event_inventory import _filename_schema_capture_time

def test_ordinary_export_unchanged():
    assert _filename_schema_capture_time("20260719_171137_Fuji-X-E5.JPG") == "2026-07-19T17:11:37"

def test_millisecond_export_is_temporally_recoverable():
    assert _filename_schema_capture_time("20260719_171137425_Fuji-X-E5.JPG") == "2026-07-19T17:11:37.425000"

def test_burst_number_fallback_is_not_mistaken_for_milliseconds():
    assert _filename_schema_capture_time("20260719_171137_Fuji-X-E5_Burst_001.JPG") == "2026-07-19T17:11:37"

def test_long_time_digits_are_not_truncated():
    assert _filename_schema_capture_time("20260719_1711374250_Fuji-X-E5.JPG") is None
