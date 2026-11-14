"""Durable application-wide reservation for one active adoption."""
from contextlib import closing, contextmanager
from pathlib import Path
import sqlite3

from app.legacy_adoption_paths import AdoptionError
from app.library_registry import MAIN_LIBRARY_ID, source_registry_transaction
from app.root_operations import _lock


def _read(path):
    path = Path(path).absolute()
    connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=2)
    connection.row_factory = sqlite3.Row
    return connection


def adoption_reservation(registry_path):
    if not Path(registry_path).exists():
        return None
    with closing(_read(registry_path)) as registry:
        if registry.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='legacy_adoption_active'"
        ).fetchone() is None:
            return None
        reservation = registry.execute(
            """SELECT a.*, l.database_path
                 FROM legacy_adoption_active a LEFT JOIN libraries l USING (library_id)
                WHERE a.singleton = 1""",
        ).fetchone()
    if reservation is None:
        return None
    if reservation["database_path"] is None:
        raise AdoptionError("Die Bibliothek des aktiven Übernahmeauftrags fehlt.")
    with closing(_read(reservation["database_path"])) as catalogue:
        job = catalogue.execute(
            """SELECT j.state, p.id AS plan_id, p.state AS plan_state, e.phase
                 FROM legacy_adoption_jobs j LEFT JOIN legacy_adoption_plans p ON p.job_id = j.id
                 LEFT JOIN legacy_adoption_execution e ON e.plan_id = p.id
                WHERE j.id = ? AND j.library_id = ?""",
            (reservation["job_id"], reservation["library_id"]),
        ).fetchone()
    if job is None:
        raise AdoptionError("Der aktive Übernahmeauftrag ist in der Bibliotheksdatenbank nicht verfügbar.")
    return {
        "job_id": reservation["job_id"], "library_id": reservation["library_id"],
        "access_kind": dict(reservation).get("access_kind", "legacy"), **dict(job),
    }


def active_adoption(registry_path):
    job = adoption_reservation(registry_path)
    if job is None or job["state"] == "discarded" or job["plan_state"] == "completed":
        return None
    return job


def pending_initial_setup(registry_path):
    """An existing installation has no setup row. Only first registration creates one."""
    if not Path(registry_path).exists():
        return None
    with closing(_read(registry_path)) as registry:
        if not registry.execute(
            "SELECT 1 FROM sqlite_master WHERE name = 'initial_library_setup' AND type = 'table'",
        ).fetchone():
            return None
        setup = registry.execute("SELECT * FROM initial_library_setup").fetchone()
        if setup is None or setup["decision"] == "skipped":
            return None
        if setup["decision"] == "adopting":
            completed = dict(setup).get("completed_plan_id")
            if completed is None:
                reservation = adoption_reservation(registry_path)
                if (reservation and reservation["access_kind"] != "library"
                        and reservation["library_id"] == setup["library_id"]
                        and reservation["plan_state"] == "completed"):
                    completed = reservation["plan_id"]
            if completed:
                if not registry.execute(
                    "SELECT 1 FROM legacy_adoption_receipts WHERE plan_id = ? AND library_id = ?",
                    (completed, setup["library_id"]),
                ).fetchone():
                    raise AdoptionError("Der Abschlussnachweis der Ersteinrichtung fehlt.")
                return None
        return {"library_id": setup["library_id"], "decision": setup["decision"]}


def require_no_managed_data(connection):
    for table in ("events", "jobs", "files", "file_families"):
        if connection.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchone():
            raise AdoptionError("Die Hauptbibliothek enthält bereits verwaltete Daten.")


def require_empty_catalogue(library):
    if library.library_id != MAIN_LIBRARY_ID or not library.is_main:
        raise AdoptionError("Die Bestandsübernahme ist der leeren Hauptbibliothek vorbehalten.")
    with closing(_read(library.database_path)) as connection:
        require_no_managed_data(connection)


def require_initial_adoption(registry_path, library):
    setup = pending_initial_setup(registry_path)
    if setup != {"library_id": library.library_id, "decision": "adopting"}:
        raise AdoptionError("Die Bestandsübernahme ist nur während der Ersteinrichtung verfügbar.")
    require_empty_catalogue(library)


def choose_initial_setup(registry_path, library, decision):
    """Caller holds the exclusive adoption lock across the decision."""
    setup = pending_initial_setup(registry_path)
    if not setup or setup["library_id"] != library.library_id or active_adoption(registry_path):
        raise AdoptionError("Die Einrichtungsentscheidung ist in diesem Zustand gesperrt.")
    if decision == "adopting":
        require_empty_catalogue(library)
    with source_registry_transaction(registry_path) as registry:
        registry.execute(
            "UPDATE initial_library_setup SET decision = ? WHERE singleton = 1 AND library_id = ?",
            (decision, library.library_id),
        )


@contextmanager
def adoption_access(registry_path, *, exclusive=False):
    path = Path(registry_path)
    if not path.parent.is_dir():
        yield active_adoption(path)
        return
    with _lock(path.with_name(path.name + ".adoption.lock"), exclusive=exclusive):
        yield active_adoption(path)


def reserve_adoption(registry_path, library_id, job_id, *, access_kind="legacy"):
    """Caller holds the exclusive access lock through job creation and reservation."""
    previous = adoption_reservation(registry_path)
    if previous and previous["state"] != "discarded" and previous["plan_state"] != "completed":
        raise AdoptionError("Es ist bereits eine Bestandsübernahme aktiv.")
    with source_registry_transaction(registry_path) as registry:
        if (access_kind == "library" and previous and previous["access_kind"] != "library"
                and previous["plan_state"] == "completed"):
            # Seal a pre-upgrade setup receipt before replacing the singleton.
            registry.execute(
                """UPDATE initial_library_setup SET completed_plan_id = ?
                   WHERE library_id = ? AND decision = 'adopting' AND completed_plan_id IS NULL""",
                (previous["plan_id"], previous["library_id"]),
            )
        registry.execute(
            """INSERT INTO legacy_adoption_active (singleton, library_id, job_id, access_kind)
               VALUES (1, ?, ?, ?) ON CONFLICT(singleton) DO UPDATE SET
                 library_id = excluded.library_id, job_id = excluded.job_id, access_kind = excluded.access_kind""",
            (library_id, job_id, access_kind),
        )


def later_adoption_blockers(library):
    """The request gate owns the application-wide lock during actual job creation."""
    from app.operation_health import inspect
    from app.root_operations import RootOperationError, assert_no_pending

    messages = []
    health = inspect(library.workspace_root)
    if health["reservations"] or not health["writes_allowed"]:
        messages.append("Schließe laufende Vorgänge oder offene Wiederherstellungen ab.")
    with closing(_read(library.database_path)) as connection:
        events = connection.execute(
            """SELECT name FROM events WHERE status != 'archived' OR pending_delete != 0
               ORDER BY name LIMIT 5"""
        ).fetchall()
        if events:
            messages.append("Noch nicht vollständig archivierte Ereignisse: " + ", ".join(row["name"] for row in events))
        if connection.execute(
            """SELECT 1 FROM event_change_requests
               WHERE status NOT IN ('aenderbar_archiviert', 'aenderbar_abgebrochen') LIMIT 1"""
        ).fetchone():
            messages.append("Schließe offene Archivänderungen ab.")
        if connection.execute(
            """SELECT 1 FROM jobs
               WHERE state IN ('queued', 'copying', 'verifying', 'analyzing', 'analyzing_metadata',
                               'organizing', 'moving', 'running', 'interrupted') LIMIT 1"""
        ).fetchone():
            messages.append("Schließe offene Import- und Hintergrundaufträge ab.")
    if not messages:
        try:
            assert_no_pending(library.workspace_root, [library.database_path], library_id=library.library_id)
        except RootOperationError as error:
            messages.append("Schließe laufende Vorgänge oder offene Wiederherstellungen ab.")
            messages.append(str(error))
    return messages


def require_later_adoption(library):
    blockers = later_adoption_blockers(library)
    if blockers:
        raise AdoptionError("\n".join(blockers))


def adoption_execution_access(registry_path):
    path = Path(registry_path)
    return _lock(path.with_name(path.name + ".adoption-execution.lock"), exclusive=True)
