from pathlib import Path

import pytest

from app import archive_transfer, main, view_cache
from app.database import database_connection, initialize_database
from tests.backend.test_0263_event_inventory import seed_event, seed_job


@pytest.mark.parametrize("count", [0, 7, 10, 23])
def test_history_pages_use_the_catalogue_and_preserve_totals(
    tmp_path: Path, monkeypatch, count: int,
):
    db = tmp_path / "library.sqlite3"
    archive = tmp_path / "archive"
    archive.mkdir()
    initialize_database(db)
    with database_connection(db) as connection:
        seed_job(connection)
        seed_event(connection, event_id="open", status="applied")
        seed_event(connection, event_id="blocked", status="applied")
        connection.executemany(
            """INSERT INTO event_archive_verifications(
                 id, job_id, event_id, status, archive_root, created_at, updated_at
               ) VALUES (?, 'j', ?, ?, ?, '2026-09-24', '2026-09-24')""",
            [("v1", "open", "verified", str(archive)), ("v2", "blocked", "failed", str(archive))],
        )
        for index in range(count):
            seed_event(connection, event_id=f"event-{index:03}", status="archived")

    def unexpected_scan(*args, **kwargs):
        pytest.fail("a history request physically scanned an event")

    monkeypatch.setattr(archive_transfer, "scan_event_inventory", unexpected_scan)
    monkeypatch.setattr(main, "current_database_file", lambda: db)
    monkeypatch.setattr(main, "current_archive_root", lambda: archive)
    page = main.api_archive_summary(force_refresh=True)
    assert [item["event_id"] for item in page["candidates"] if not item["released"]] == ["open", "blocked"]

    cursor = None
    loaded = []
    while True:
        assert (page["candidate_count"], page["verified_count"], page["released_count"], page["blocked_count"]) == (
            2, 1, count, 1,
        )
        items = [item for item in page["candidates"] if item["released"]]
        assert len(items) == min(10, count - len(loaded))
        assert all(item["current_archive"]["available"] for item in items)
        loaded.extend(item["event_id"] for item in items)
        next_cursor = page["history_next_cursor"]
        if next_cursor is None:
            break
        assert next_cursor != cursor
        cursor = next_cursor
        view_cache.invalidate(db)
        page = main.api_archive_summary(**cursor)
        assert all(item["released"] for item in page["candidates"])

    assert loaded == [f"event-{index:03}" for index in reversed(range(count))]
