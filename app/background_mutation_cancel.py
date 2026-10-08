"""0.44.3: persistente, browserunabhängige Rücknahme von Applied-Änderungen.

SQLite führt die Queue pro Bibliothek. Der vorhandene Server-Worker arbeitet
Aufträge seriell ab, und unvollständige Aufträge werden beim Neustart erneut
vorgelegt. Die Dateirücknahme ist für diese Wiederaufnahme idempotent.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any
import sqlite3
import uuid

from app.database import database_connection

STATES_ACTIVE = ("queued", "running")
STATES_TERMINAL = ("completed", "failed")


def _public(row: Any) -> dict[str, Any]:
    return {key: row[key] for key in (
        "id", "job_id", "mutation_id", "status", "error_message",
        "created_at", "updated_at", "started_at", "completed_at",
    )}


def enqueue(database_path: Path, job_id: str, mutation_id: str) -> dict[str, Any]:
    """Atomar aufnehmen; Doppel-Klicks und Wiederholungen erzeugen keinen Doppelauftrag."""
    with database_connection(database_path) as db:
        db.execute("BEGIN IMMEDIATE")
        old = db.execute(
            "SELECT * FROM background_mutation_cancellations WHERE job_id=? AND mutation_id=?",
            (job_id, mutation_id),
        ).fetchone()
        if old is not None:
            if old["status"] == "failed":
                # Ein bereits rückgenommener Mutationskern wird beim Retry
                # nicht erneut verändert; lediglich zentrale Claims werden erneut synchronisiert.
                db.execute(
                    """UPDATE background_mutation_cancellations
                       SET status='queued',error_message=NULL,updated_at=datetime('now'),
                           started_at=NULL,completed_at=NULL WHERE id=?""",
                    (old["id"],),
                )
            return _public(db.execute(
                "SELECT * FROM background_mutation_cancellations WHERE id=?",
                (old["id"],),
            ).fetchone())
        mutation = db.execute(
            "SELECT status FROM event_mutations WHERE id=? AND job_id=?",
            (mutation_id, job_id),
        ).fetchone()
        if mutation is None:
            raise ValueError("Ereignisänderung wurde nicht gefunden.")
        if str(mutation["status"]) not in {
            "pending_reassignment", "pending_apply", "manual_archive"
        }:
            raise ValueError("Diese Ereignisänderung kann nicht mehr verworfen werden.")
        row_id = str(uuid.uuid4())
        db.execute(
            """INSERT INTO background_mutation_cancellations(id,job_id,mutation_id)
               VALUES (?,?,?)""",
            (row_id, job_id, mutation_id),
        )
        return _public(db.execute(
            "SELECT * FROM background_mutation_cancellations WHERE id=?",
            (row_id,),
        ).fetchone())


def recover_interrupted(database_path: Path) -> int:
    """Ein einzelner TrueNAS-App-Prozess darf nach dem Neustart Jobs zurückstellen."""
    with database_connection(database_path) as db:
        return db.execute(
            """UPDATE background_mutation_cancellations
               SET status='queued',error_message=NULL,updated_at=datetime('now')
               WHERE status='running'"""
        ).rowcount


def claim_next(database_path: Path) -> dict[str, Any] | None:
    with database_connection(database_path) as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute(
            """SELECT * FROM background_mutation_cancellations
               WHERE status='queued' ORDER BY created_at,id LIMIT 1"""
        ).fetchone()
        if row is None:
            return None
        db.execute(
            """UPDATE background_mutation_cancellations
               SET status='running',started_at=datetime('now'),updated_at=datetime('now')
               WHERE id=? AND status='queued'""",
            (row["id"],),
        )
        return _public(db.execute(
            "SELECT * FROM background_mutation_cancellations WHERE id=?",
            (row["id"],),
        ).fetchone())


def finish(database_path: Path, operation_id: str, *, error: str | None = None) -> None:
    with database_connection(database_path) as db:
        db.execute(
            """UPDATE background_mutation_cancellations
               SET status=?, error_message=?,updated_at=datetime('now'),
                   completed_at=datetime('now')
               WHERE id=? AND status='running'""",
            ("failed" if error else "completed", error, operation_id),
        )


def get(database_path: Path, operation_id: str) -> dict[str, Any] | None:
    with database_connection(database_path) as db:
        row = db.execute(
            "SELECT * FROM background_mutation_cancellations WHERE id=?",
            (operation_id,),
        ).fetchone()
        return _public(row) if row is not None else None


def list_visible(database_path: Path, *, limit: int = 5) -> list[dict[str, Any]]:
    with database_connection(database_path) as db:
        rows = db.execute(
            """SELECT * FROM background_mutation_cancellations
               WHERE status IN ('queued','running','failed')
                  OR completed_at >= datetime('now','-30 seconds')
               ORDER BY created_at DESC,id DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [_public(row) for row in rows]


def mutation_already_cancelled(db: sqlite3.Connection, mutation_id: str, job_id: str) -> bool:
    row = db.execute(
        "SELECT status FROM event_mutations WHERE id=? AND job_id=?",
        (mutation_id, job_id),
    ).fetchone()
    if row is None:
        raise ValueError("Die gespeicherte Ereignisänderung fehlt.")
    return str(row["status"]) == "cancelled"
