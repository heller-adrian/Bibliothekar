import pytest

from app.free_time import FreeTimeError, free_ranges, free_ranges_for_day


def test_free_ranges_for_day_keeps_only_real_gaps():
    result = free_ranges_for_day(
        "2026-07-15",
        [
            ("2026-07-15T08:00:00", "2026-07-15T10:59:59"),
            ("2026-07-15T13:00:00", "2026-07-15T15:59:59"),
        ],
    )
    assert result == [
        {
            "day_key": "2026-07-15",
            "start_time": "00:00",
            "end_time": "07:59",
            "start_datetime": "2026-07-15T00:00:00",
            "end_datetime": "2026-07-15T07:59:59",
        },
        {
            "day_key": "2026-07-15",
            "start_time": "11:00",
            "end_time": "12:59",
            "start_datetime": "2026-07-15T11:00:00",
            "end_datetime": "2026-07-15T12:59:59",
        },
        {
            "day_key": "2026-07-15",
            "start_time": "16:00",
            "end_time": "23:59",
            "start_datetime": "2026-07-15T16:00:00",
            "end_datetime": "2026-07-15T23:59:59",
        },
    ]


def test_free_ranges_merge_adjacent_and_overlapping_occupied_ranges():
    result = free_ranges(
        "2026-07-15T08:00:00",
        "2026-07-15T18:00:00",
        [
            ("2026-07-15T09:00:00", "2026-07-15T10:00:00"),
            ("2026-07-15T10:00:01", "2026-07-15T11:00:00"),
            ("2026-07-15T10:30:00", "2026-07-15T12:00:00"),
        ],
    )
    assert [
        (item["start_datetime"], item["end_datetime"])
        for item in result
    ] == [
        ("2026-07-15T08:00:00", "2026-07-15T08:59:59"),
        ("2026-07-15T12:00:01", "2026-07-15T18:00:00"),
    ]


def test_free_ranges_clip_occupied_ranges_to_requested_interval():
    result = free_ranges(
        "2026-07-15T08:00:00",
        "2026-07-15T12:00:00",
        [
            ("2026-07-15T06:00:00", "2026-07-15T08:59:59"),
            ("2026-07-15T11:00:00", "2026-07-15T14:00:00"),
        ],
    )
    assert len(result) == 1
    assert result[0]["start_datetime"] == "2026-07-15T09:00:00"
    assert result[0]["end_datetime"] == "2026-07-15T10:59:59"


def test_free_ranges_return_empty_when_interval_is_fully_occupied():
    assert free_ranges_for_day(
        "2026-07-15",
        [("2026-07-15T00:00:00", "2026-07-15T23:59:59")],
    ) == []


def test_free_ranges_reject_invalid_intervals():
    with pytest.raises(FreeTimeError):
        free_ranges(
            "2026-07-15T12:00:00",
            "2026-07-15T08:00:00",
            [],
        )
