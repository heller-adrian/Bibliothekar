from pathlib import Path
from app.events_ui import EVENTS_HTML

from app.database import database_connection, initialize_database
from app.free_time import free_ranges_for_day


def test_0212_free_remainder_is_exact():
    ranges = free_ranges_for_day(
        "2026-07-15",
        [
            ("2026-07-15T08:00:00", "2026-07-15T10:59:59"),
            ("2026-07-15T12:00:00", "2026-07-15T14:59:59"),
        ],
    )
    assert [(r["start_time"], r["end_time"]) for r in ranges] == [
        ("00:00", "07:59"),
        ("11:00", "11:59"),
        ("15:00", "23:59"),
    ]


def test_0212_schema_stores_archived_child_segments(tmp_path: Path):
    db = tmp_path / "qa.sqlite3"
    result = initialize_database(db)
    assert 23 in result["applied_versions"]
    assert 31 in result["applied_versions"]
    with database_connection(db) as connection:
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(event_change_requests)")}
    assert "child_segments_json" in columns


def test_0212_event_ui_has_atomic_reassignment_and_segment_delete():
    # 0.25 removes the target selector: assignment happens through workspace cards.
    assert 'In Aufnahmen öffnen' in EVENTS_HTML
    assert 'id="reassignment-target"' not in EVENTS_HTML
    assert 'id="reassignment-apply"' not in EVENTS_HTML
    assert 'segment.start_time' in EVENTS_HTML and 'segment.end_time' in EVENTS_HTML
    assert 'segment.family_count' in EVENTS_HTML and 'segment.file_count' in EVENTS_HTML


def test_0212_version_and_sd_idle_copy():
    from app.main import APP_VERSION, index

    assert APP_VERSION == "0.27.3"
    html = index().body.decode() if hasattr(index(), "body") else str(index())
    assert "Keine neuen Dateien" in html
    assert "Verwaltungsdateien ignoriert" in html


def test_0212_direct_archived_reassignment_endpoint_is_disabled():
    source = Path("app/main.py").read_text()
    start = source.index("def api_change_request_reassignments_assign")
    end = source.index("@app.post(\"/api/change-requests/{cr_id}/confirm\")", start)
    endpoint = source[start:end]

    assert "Direkte Neu-Zuordnung innerhalb einer Archivänderung ist deaktiviert." in endpoint
    assert "Freigewordene Archivdateien" in endpoint
    assert "assign_archive_reassignments(" not in endpoint
