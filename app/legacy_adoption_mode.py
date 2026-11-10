"""Durable application-wide reservation for one active adoption."""
from contextlib import closing, contextmanager
from pathlib import Path
import sqlite3

from app.legacy_adoption_paths import AdoptionError
from app.library_registry import source_registry_transaction
from app.root_operations import _lock


def _read(path):
    path = Path(path).absolute()
    connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=2)
    connection.row_factory = sqlite3.Row
    return connection


def active_adoption(registry_path):
    if not Path(registry_path).exists():
        return None
    with closing(_read(registry_path)) as registry:
        if registry.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='legacy_adoption_active'"
        ).fetchone() is None:
            return None
        reservation = registry.execute(
            """SELECT a.job_id, a.library_id, l.database_path
                 FROM legacy_adoption_active a LEFT JOIN libraries l USING (library_id)
                WHERE a.singleton = 1""",
        ).fetchone()
    if reservation is None:
        return None
    if reservation["database_path"] is None:
        raise AdoptionError("Die Bibliothek des aktiven Übernahmeauftrags fehlt.")
    with closing(_read(reservation["database_path"])) as catalogue:
        job = catalogue.execute(
            """SELECT j.state, p.state AS plan_state
                 FROM legacy_adoption_jobs j LEFT JOIN legacy_adoption_plans p ON p.job_id = j.id
                WHERE j.id = ? AND j.library_id = ?""",
            (reservation["job_id"], reservation["library_id"]),
        ).fetchone()
    if job is None:
        raise AdoptionError("Der aktive Übernahmeauftrag ist in der Bibliotheksdatenbank nicht verfügbar.")
    if job["state"] == "discarded" or job["plan_state"] == "completed":
        return None
    return {"job_id": reservation["job_id"], "library_id": reservation["library_id"]}


@contextmanager
def adoption_access(registry_path, *, exclusive=False):
    path = Path(registry_path)
    if not path.parent.is_dir():
        yield active_adoption(path)
        return
    with _lock(path.with_name(path.name + ".adoption.lock"), exclusive=exclusive):
        yield active_adoption(path)


def reserve_adoption(registry_path, library_id, job_id):
    """Caller holds the exclusive access lock through job creation and reservation."""
    if active_adoption(registry_path) is not None:
        raise AdoptionError("Es ist bereits eine Bestandsübernahme aktiv.")
    with source_registry_transaction(registry_path) as registry:
        registry.execute(
            """INSERT INTO legacy_adoption_active (singleton, library_id, job_id)
               VALUES (1, ?, ?)
               ON CONFLICT(singleton) DO UPDATE SET library_id = excluded.library_id, job_id = excluded.job_id""",
            (library_id, job_id),
        )
