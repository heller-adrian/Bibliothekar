"""Persistent confirmation, execution and recovery of a frozen adoption plan."""
import json

from app.database import database_connection
from app.legacy_adoption_dataset import DatasetError
from app.legacy_adoption_inventory import _job
from app.legacy_adoption_paths import AdoptionError
from app.legacy_adoption_plan import plan_status
from app.legacy_adoption_verify import _catalogue_unchanged, _plan, assert_original_layout, verify_locked


def execution_row(connection, plan_id):
    return connection.execute(
        "SELECT * FROM legacy_adoption_execution WHERE plan_id = ?", (plan_id,),
    ).fetchone()


def set_phase(connection, plan_id, phase):
    connection.execute(
        """UPDATE legacy_adoption_execution SET phase = ?, updated_at = CURRENT_TIMESTAMP
            WHERE plan_id = ?""", (phase, plan_id),
    )


def confirm_plan(library, job_id, plan_id, method, *, acknowledged):
    if acknowledged is not True or method != "manual":
        raise AdoptionError("Bestätige die Sicherheitsbedingungen und wähle eine verfügbare Methode.")
    with database_connection(library.database_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        job = _job(connection, library.library_id, job_id)
        plan = _plan(connection, job_id)
        if (job["state"] != "inventoried" or plan["id"] != plan_id or
                plan["state"] != "prepared" or not plan["documents_at"]):
            raise AdoptionError("Der vollständige aktuelle Plan und seine Ereignisdokumente müssen vorliegen.")
        existing = execution_row(connection, plan_id)
        if existing is None:
            _catalogue_unchanged(connection, job_id, json.loads(plan["events_json"]))
            assert_original_layout(connection, library, job, plan)
            connection.execute(
                "INSERT INTO legacy_adoption_execution (plan_id, method, phase) VALUES (?, ?, 'manual')",
                (plan_id, method),
            )
        elif existing["method"] != method:
            raise AdoptionError("Die bestätigte Methode kann nicht geändert werden.")
    return plan_status(library, job_id)


def change_phase(library, job_id, plan_id, phase, *, from_phases):
    with database_connection(library.database_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        job = _job(connection, library.library_id, job_id)
        plan = _plan(connection, job_id)
        execution = execution_row(connection, plan["id"])
        if (job["state"] == "discarded" or plan["id"] != plan_id or execution is None or
                execution["phase"] not in from_phases):
            raise AdoptionError("Der Übernahmeauftrag ist für diesen Schritt nicht verfügbar.")
        set_phase(connection, plan_id, phase)


def verify_execution(library, job_id, plan_id):
    change_phase(library, job_id, plan_id, "verifying", from_phases={
        "manual", "operations_done", "verifying", "repair", "registration_pending",
    })
    try:
        with database_connection(library.database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            job = _job(connection, library.library_id, job_id)
            plan = _plan(connection, job_id)
            state = verify_locked(connection, library, job, plan)
            set_phase(connection, plan_id, "registration_pending" if state == "verified" else "repair")
    except (OSError, AdoptionError, DatasetError):
        change_phase(library, job_id, plan_id, "repair", from_phases={"verifying"})
        raise
    return plan_status(library, job_id)


def complete_rollback(library, job_id, plan_id):
    with database_connection(library.database_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        job = _job(connection, library.library_id, job_id)
        plan = _plan(connection, job_id)
        execution = execution_row(connection, plan["id"])
        if plan["id"] != plan_id or execution is None or execution["phase"] != "rolling_back":
            raise AdoptionError("Starte zuerst den vorgesehenen Wiederherstellungsweg.")
        _catalogue_unchanged(connection, job_id, json.loads(plan["events_json"]))
        assert_original_layout(connection, library, job, plan)
        set_phase(connection, plan_id, "rolled_back")
        connection.execute("UPDATE legacy_adoption_jobs SET state = 'discarded' WHERE id = ?", (job_id,))
    return plan_status(library, job_id)
