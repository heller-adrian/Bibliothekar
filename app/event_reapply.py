"""Nachsortierung (re-apply) nach einer strukturellen Ereignis-Edition.

Wenn ein bereits angewendetes Ereignis bearbeitet wurde, beschreibt der
Index (SQLite + event.json) ab sofort die *gewünschte* Struktur, während
die Dateien im Arbeitsbereich (noch) in der alten Struktur liegen. Die
Nachsortierung richtet die Dateien wieder neu – ausschließlich innerhalb
des gemeinsamen Arbeitsbereichs:

- Quell- und Zielpfade liegen niemals außerhalb des Arbeitsbereichs,
- Dateien werden mit dem bewährten, prüfsummensicheren
  Link-Verschiebe-Verfahren bewegt (gleiche Dateisystemvoraussetzung wie
  der 0.14.0-Anwendelauf),
- ein Rollback setzt bei Fehlern die Ausgangslage wieder her,
- die Kamerabibliothek, Backups, SD-Karten und die Sicherung bleiben
  berührungslos.

Der Lauf wird als ``sort_runs``-Eintrag mit ``run_kind = 'reapply'``
geführt und braucht – wie der initiale Anwenden-Lauf – einen tagesaktuellen
Plan-Token und eine explizite Bestätigung.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
import uuid

from app.database import database_connection
from app.sort_apply import (
    CONFIRMATION_PHRASE,
    SortApplyError,
    _json_details,
    _now,
)
from app.sort_plan import build_event_sort_plan
from app.job_readiness import job_sort_readiness


ACTIVE_RUN_STATUSES = (
    "queued",
    "verifying",
    "moving",
    "finalizing",
    "rolling_back",
    "interrupted",
)


def active_sort_run_exists(
    connection: Any,
    event_id: str,
) -> bool:
    row = connection.execute(
        """
        SELECT id
        FROM sort_runs
        WHERE event_id = ?
          AND status IN (?, ?, ?, ?, ?, ?)
        LIMIT 1
        """,
        (event_id, *ACTIVE_RUN_STATUSES),
    ).fetchone()
    return row is not None


def prepare_reapply_sort_run(
    database_path: Path,
    job_id: str,
    event_id: str,
    workspace_path: Path,
    *,
    expected_plan_token: str,
    confirmation_phrase: str,
) -> dict[str, Any]:
    """Ein Nachsortierlauf aufsetzen (rein vorbereitend, keine Dateien).

    Das Ereignis muss angewendet, nicht archiviert und frei von aktiven
    Sortierläufen sein. Der übergebene Plan-Token muss zu einem
    soeben berechneten, reapply-fähigen Sortierplan passen.
    """

    if confirmation_phrase != CONFIRMATION_PHRASE:
        raise SortApplyError(
            "Die ausdrückliche Bestätigung für die Nachsortierung fehlt."
        )

    plan = build_event_sort_plan(
        database_path,
        job_id,
        event_id,
        workspace_path,
        verify_sha256=False,
        allow_reapply=True,
    )

    if not bool(plan["summary"]["ready"]):
        raise SortApplyError(
            "Der Nachsortierplan besitzt Blocker und darf nicht "
            "angewendet werden."
        )

    if str(plan["plan_token"]) != str(expected_plan_token):
        raise SortApplyError(
            "Der Nachsortierplan ist nicht mehr aktuell. Bitte erneut prüfen."
        )

    job_ready, job_blocker = job_sort_readiness(plan["job"])
    if not job_ready:
        raise SortApplyError(job_blocker)

    run_id = "RSORT_" + uuid.uuid4().hex.upper()
    now = _now()
    summary = plan["summary"]

    with database_connection(database_path) as connection:
        connection.execute("BEGIN IMMEDIATE")

        event = connection.execute(
            """
            SELECT status, applied_at, archived_at, event_level
            FROM events
            WHERE id = ? AND job_id = ?
            """,
            (event_id, job_id),
        ).fetchone()

        if event is None:
            raise SortApplyError("Ereignis wurde nicht gefunden.")

        if str(event["event_level"]) != "parent":
            raise SortApplyError(
                "Eine Nachsortierung kann nur für ein Hauptereignis "
                "angefordert werden."
            )

        if (
            str(event["status"]) != "applied"
            or event["applied_at"] is None
            or event["archived_at"] is not None
        ):
            raise SortApplyError(
                "Für dieses Ereignis ist keine Nachsortierung möglich: "
                "Es ist nicht angewendet oder bereits archiviert."
            )

        if active_sort_run_exists(connection, event_id):
            raise SortApplyError(
                "Für dieses Ereignis existiert bereits ein aktiver oder "
                "unterbrochener Sortierlauf. Bitte zuerst klären."
            )

        connection.execute(
            """
            INSERT INTO sort_runs (
                id, job_id, event_id, plan_token, status, phase,
                source_root, target_root, file_count, verified_file_count,
                move_count, moved_file_count, directory_count,
                created_directory_count, total_size_bytes, verified_bytes,
                moved_bytes, error_message, details_json,
                created_at, started_at, updated_at, completed_at, run_kind
            )
            VALUES (
                ?, ?, ?, ?, 'queued',
                'Wartet auf vollständig erneute SHA-256-Prüfung',
                ?, ?, ?, 0, ?, 0, ?, 0, ?, 0, 0,
                NULL, ?, ?, NULL, ?, NULL, 'reapply'
            )
            """,
            (
                run_id,
                job_id,
                event_id,
                str(plan["plan_token"]),
                str(plan["source_root"]),
                str(plan["target_root"]),
                int(summary["file_count"]),
                int(summary["move_count"]),
                int(summary["directory_count"]),
                int(summary["total_size_bytes"]),
                _json_details({
                    "event_name": str(plan["event"]["name"]),
                    "structure_text": str(plan["structure_text"]),
                    "planned_directories": [
                        str(row["relative_path"])
                        for row in plan["directories"]
                    ],
                    "created_directories": [],
                    "removed_empty_source_directories": [],
                }),
                now,
                now,
            ),
        )

        operations = []
        for sequence, entry in enumerate(plan["files"], start=1):
            status_value = (
                "already_at_target"
                if entry["status"] == "already_at_target"
                else "planned"
            )
            operations.append((
                run_id,
                sequence,
                int(entry["file_id"]),
                str(entry["source_relative_path"]),
                str(entry["destination_relative_path"]),
                int(entry["expected_size_bytes"]),
                str(entry["stored_sha256"]),
                status_value,
            ))

        connection.executemany(
            """
            INSERT INTO sort_operations (
                sort_run_id, sequence_number, file_id,
                source_relative_path, destination_relative_path,
                expected_size_bytes, expected_sha256, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            operations,
        )

        connection.execute(
            """
            INSERT INTO audit_log (
                job_id, action, entity_type, entity_id, details_json, created_at
            )
            VALUES (?, 'event_reapply_run_queued', 'sort_run', ?, ?, ?)
            """,
            (
                job_id,
                run_id,
                _json_details({
                    "event_id": event_id,
                    "plan_token": str(plan["plan_token"]),
                    "file_count": int(summary["file_count"]),
                    "move_count": int(summary["move_count"]),
                    "run_kind": "reapply",
                }),
                now,
            ),
        )

        connection.commit()

    from app.sort_apply import get_sort_run

    run = get_sort_run(database_path, job_id, run_id)

    if run is None:
        raise SortApplyError("Der Nachsortierlauf konnte nicht angelegt werden.")

    run["run_kind"] = "reapply"
    return run
