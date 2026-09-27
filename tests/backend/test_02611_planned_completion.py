from pathlib import Path

from app.database import (
    database_connection,
    delete_planned_event,
    get_event_edit_context,
    initialize_database,
    list_global_tasks,
    update_event_definition,
)
from app.main import APP_VERSION, _event_edit_payload_within_new_range
from tests.backend.test_0262_logic_hardening import (
    NOW,
    assign,
    seed_event,
    seed_family_file,
    seed_job,
)


def _planned_fixture(tmp_path: Path):
    db = tmp_path / "db.sqlite3"
    initialize_database(db)
    with database_connection(db) as connection:
        seed_job(connection, "j")
        seed_event(
            connection,
            event_id="e",
            job_id="j",
            status="planned",
            start="2026-07-22T00:00:00",
            end="2026-07-22T23:59:59",
            folder="07-22 - Test",
            name="Test",
        )
        early, _ = seed_family_file(
            connection,
            job_id="j",
            family_key="EARLY",
            capture="2026-07-22T12:00:00",
            current_path="2026/2026-07-22/EARLY.JPG",
            content=b"early",
        )
        late, _ = seed_family_file(
            connection,
            job_id="j",
            family_key="LATE",
            capture="2026-07-22T23:30:00",
            current_path="2026/2026-07-22/LATE.JPG",
            content=b"late",
        )
        assign(connection, "e", early)
        assign(connection, "e", late)
    return db, early, late


def _preview(family_ids, *, end_time: str):
    return {
        "selected_family_ids": list(family_ids),
        "start_date": "2026-07-22",
        "end_date": "2026-07-22",
        "start_time": "00:00",
        "end_time": end_time,
        "uses_time_range": True,
        "parent_folder": "07-22 - Test",
        "child_folder": "",
        "child_event_name": "",
        "subevents": [],
        "event_kind": "event",
        "preserve_day_folders": False,
    }


def test_02611_version():
    assert APP_VERSION == "0.26.11"


def test_02611_planned_shrink_is_complete_and_can_expand_again(tmp_path: Path):
    db, early, late = _planned_fixture(tmp_path)

    result = update_event_definition(
        db,
        "j",
        "e",
        _preview([early], end_time="23:00"),
        event_name="Test",
        notes="",
        expected_revision=1,
    )
    assert result["reassignment_required"] is False
    assert result["removed_family_ids"] == [late]

    with database_connection(db) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM event_reapply_removed_families WHERE event_id='e'"
        ).fetchone()[0] == 0
        marker = connection.execute(
            """SELECT released_start_datetime,released_end_datetime
               FROM released_free_families WHERE job_id='j' AND family_id=?""",
            (late,),
        ).fetchone()
        assigned = {
            int(row[0])
            for row in connection.execute(
                """SELECT ea.family_id FROM event_assignments ea
                   JOIN events e ON e.id=ea.event_id
                   WHERE COALESCE(e.parent_event_id,e.id)='e'"""
            )
        }
    assert assigned == {early}
    assert marker is not None
    assert tuple(marker) == ("2026-07-22T23:01:00", "2026-07-22T23:59:59")

    tasks = list_global_tasks(db)
    assert not any(item["kind"] == "reassignment" for item in tasks)
    assert not any(item["kind"] == "unassigned_families" for item in tasks)
    assert any(item["kind"] == "planned_apply" and item["event_id"] == "e" for item in tasks)

    # The family that just became free remains an eligible family in the editor,
    # so extending the planned interval can absorb it again immediately.
    context = get_event_edit_context(db, "j", "e")
    payload = _event_edit_payload_within_new_range(
        {
            "event_kind": "event",
            "start_date": "2026-07-22",
            "end_date": "2026-07-22",
            "start_time": "00:00",
            "end_time": "23:59",
            "uses_time_range": True,
        },
        context["families"],
    )
    assert payload["selected_family_ids"] == [early, late]

    expanded = update_event_definition(
        db,
        "j",
        "e",
        _preview([early, late], end_time="23:59"),
        event_name="Test",
        notes="",
        expected_revision=2,
    )
    assert expanded["reassignment_required"] is False
    assert expanded["removed_family_ids"] == []

    with database_connection(db) as connection:
        assigned = {
            int(row[0])
            for row in connection.execute(
                """SELECT ea.family_id FROM event_assignments ea
                   JOIN events e ON e.id=ea.event_id
                   WHERE COALESCE(e.parent_event_id,e.id)='e'"""
            )
        }
        marker_count = connection.execute(
            "SELECT COUNT(*) FROM released_free_families WHERE job_id='j' AND family_id=?",
            (late,),
        ).fetchone()[0]
        queue_count = connection.execute(
            "SELECT COUNT(*) FROM event_reapply_removed_families WHERE event_id='e'"
        ).fetchone()[0]
    assert assigned == {early, late}
    assert marker_count == 0
    assert queue_count == 0


def test_02611_planned_delete_releases_without_reassignment_task(tmp_path: Path):
    db, early, late = _planned_fixture(tmp_path)
    result = delete_planned_event(db, "j", "e")
    assert result["reassignment_required"] is False
    assert result["pending_delete"] is False

    with database_connection(db) as connection:
        assert connection.execute("SELECT COUNT(*) FROM events WHERE id='e'").fetchone()[0] == 0
        assert connection.execute(
            "SELECT COUNT(*) FROM event_reapply_removed_families WHERE job_id='j'"
        ).fetchone()[0] == 0
        markers = {
            int(row[0])
            for row in connection.execute(
                "SELECT family_id FROM released_free_families WHERE job_id='j'"
            )
        }
    assert markers == {early, late}
    tasks = list_global_tasks(db)
    assert not any(item["kind"] in {"reassignment", "unassigned_families"} for item in tasks)


def test_02611_legacy_planned_queue_is_converted_before_next_edit(tmp_path: Path):
    db, early, late = _planned_fixture(tmp_path)
    with database_connection(db) as connection:
        connection.execute(
            "DELETE FROM event_assignments WHERE family_id=?",
            (late,),
        )
        connection.execute(
            """INSERT INTO event_reapply_removed_families(
                   event_id,job_id,family_id,created_at,
                   released_start_datetime,released_end_datetime)
               VALUES ('e','j',?,?, '2026-07-22T23:01:00','2026-07-22T23:59:59')""",
            (late, NOW),
        )

    # Old 0.26.10 durable state must no longer throw "Neu-Zuordnung abschließen".
    result = update_event_definition(
        db,
        "j",
        "e",
        _preview([early, late], end_time="23:59"),
        event_name="Test",
        notes="",
        expected_revision=1,
    )
    assert result["reassignment_required"] is False
    with database_connection(db) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM event_reapply_removed_families WHERE event_id='e'"
        ).fetchone()[0] == 0
        assert connection.execute(
            "SELECT COUNT(*) FROM released_free_families WHERE job_id='j' AND family_id=?",
            (late,),
        ).fetchone()[0] == 0
