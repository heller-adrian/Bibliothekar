"""0.28.0: reassignment queue stays event-centric across backup provenance."""
from __future__ import annotations

from pathlib import Path
import json

from app.database import (
    database_connection,
    initialize_database,
    list_global_tasks,
    list_job_events,
)
from app.event_reassignment import assign_event_reassignments
from tests.backend.test_0262_logic_hardening import (
    NOW,
    seed_event,
    seed_family_file,
    seed_job,
)


def test_0280_cross_backup_reassignment_queue_uses_event_identity(tmp_path: Path):
    db = tmp_path / "db.sqlite3"
    initialize_database(db)
    with database_connection(db) as connection:
        seed_job(connection, "a")
        seed_job(connection, "b")
        seed_event(
            connection,
            event_id="source",
            job_id="a",
            status="applied",
            start="2026-07-23T00:00:00",
            end="2026-07-23T12:00:59",
            folder="07-23 - Source",
            name="Source",
        )
        seed_event(
            connection,
            event_id="target",
            job_id="a",
            status="planned",
            start="2026-07-23T12:01:00",
            end="2026-07-23T23:59:59",
            folder="07-23 - Target",
            name="Target",
        )
        family_id, _file_id = seed_family_file(
            connection,
            job_id="b",
            family_key="B",
            capture="2026-07-23T13:00:00",
            current_path="2026/07-23 - Source/Alle/B.JPG",
            content=b"camera-b",
        )
        connection.execute(
            """INSERT INTO event_reapply_removed_families(
                   event_id,job_id,family_id,created_at
               ) VALUES ('source','b',?,?)""",
            (family_id, NOW),
        )
        connection.execute(
            """INSERT INTO event_mutations(
                   id,job_id,anchor_event_id,mutation_kind,status,
                   affected_event_ids_json,original_state_json,target_state_json,
                   created_at,updated_at
               ) VALUES (
                   'mut','a','source','edit','pending_reassignment',
                   ?, '{}', '{}', ?, ?
               )""",
            (json.dumps(["source"]), NOW, NOW),
        )

    event_rows = list_job_events(db, "a")
    source_row = next(row for row in event_rows if row["id"] == "source")
    assert source_row["pending_reassignment_count"] == 1

    # The B-provenance queue row belongs to an active A-anchor mutation and
    # must not surface as a second independent global task.
    assert not any(
        task["kind"] == "reassignment" and task["event_id"] == "source"
        for task in list_global_tasks(db)
    )

    result = assign_event_reassignments(
        db,
        "a",
        "source",
        [family_id],
        target_mode="existing_event",
        target_event_id="target",
    )
    assert result["pending_family_count"] == 0
    assert result["target"]["event_id"] == "target"

    with database_connection(db) as connection:
        queue = connection.execute(
            """SELECT job_id,target_event_id,target_status,target_kind
               FROM event_reapply_removed_families
               WHERE event_id='source' AND family_id=?""",
            (family_id,),
        ).fetchone()
        mutation = connection.execute(
            "SELECT status FROM event_mutations WHERE id='mut'"
        ).fetchone()
        assignment = connection.execute(
            "SELECT event_id FROM event_assignments WHERE family_id=?",
            (family_id,),
        ).fetchone()

    assert tuple(queue) == ("b", "target", "planned", "existing_event")
    assert mutation["status"] == "pending_apply"
    assert assignment["event_id"] == "target"


def test_0280_cross_backup_reassignment_can_create_new_event(tmp_path: Path):
    db = tmp_path / "db.sqlite3"
    initialize_database(db)
    with database_connection(db) as connection:
        seed_job(connection, "a")
        seed_job(connection, "b")
        seed_event(
            connection,
            event_id="source",
            job_id="a",
            status="applied",
            start="2026-07-23T00:00:00",
            end="2026-07-23T12:00:59",
            folder="07-23 - Source",
            name="Source",
        )
        family_id, _file_id = seed_family_file(
            connection,
            job_id="b",
            family_key="B",
            capture="2026-07-23T13:00:00",
            current_path="2026/07-23 - Source/Alle/B.JPG",
            content=b"camera-b",
        )
        connection.execute(
            """INSERT INTO event_reapply_removed_families(
                   event_id,job_id,family_id,created_at
               ) VALUES ('source','b',?,?)""",
            (family_id, NOW),
        )

    result = assign_event_reassignments(
        db,
        "a",
        "source",
        [family_id],
        target_mode="new_event",
        new_event_name="Neu",
    )
    target_id = result["target"]["event_id"]
    assert target_id != "source"

    with database_connection(db) as connection:
        target = connection.execute(
            "SELECT job_id,linkage_kind,status FROM events WHERE id=?",
            (target_id,),
        ).fetchone()
        assignment = connection.execute(
            "SELECT event_id FROM event_assignments WHERE family_id=?",
            (family_id,),
        ).fetchone()
        sources = connection.execute(
            "SELECT job_id FROM event_source_jobs WHERE event_id=? ORDER BY job_id",
            (target_id,),
        ).fetchall()

    assert tuple(target) == ("a", None, "planned")
    assert assignment["event_id"] == target_id
    assert [row["job_id"] for row in sources] == ["a", "b"]
