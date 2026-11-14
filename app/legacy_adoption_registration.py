"""Publish verified archives to the catalogue and the global ownership registry."""
from contextlib import closing
import hashlib
from itertools import groupby
import json
import sqlite3

from app.database import database_connection
from app.global_library_inventory import backup_key, family_content_fingerprint, occurrence_key
from app.legacy_adoption_catalogue import (
    _inventory_rows, adoption_source_signature, catalogue_documents, catalogue_job_id, write_catalogue,
)
from app.legacy_adoption_execution import execution_row, set_phase
from app.legacy_adoption_inventory import _job
from app.legacy_adoption_paths import AdoptionError
from app.legacy_adoption_plan import plan_status
from app.legacy_adoption_verify import assert_verification_stamps, verify_locked
from app.library_registry import (
    MAIN_LIBRARY_ID, claim_source_family, register_source_backup, register_source_family,
    register_source_family_members, register_source_media, source_registry_transaction,
)
from app.root_operations import protect, validate_active_roots


class _RegistrationConflict(AdoptionError):
    pass


def _fingerprint(connection, plan):
    digest = hashlib.sha256()
    for value in (plan["id"], plan["job_id"], plan["draft_json"], plan["events_json"], plan["documents_at"]):
        digest.update(json.dumps(value).encode("utf-8") + b"\n")
    for query in (
        """SELECT relative_path, target_path, parent_event_id, assigned_event_id, capture_time, sha256
             FROM legacy_adoption_moves WHERE plan_id = ? ORDER BY relative_path""",
        "SELECT relative_path, sha256 FROM legacy_adoption_documents WHERE plan_id = ? ORDER BY relative_path",
    ):
        for row in connection.execute(query, (plan["id"],)):
            digest.update(json.dumps(tuple(row)).encode("utf-8") + b"\n")
    return digest.hexdigest()


def _receipt(connection, plan):
    return connection.execute(
        "SELECT library_id, catalogue_job_id, plan_fingerprint FROM legacy_adoption_receipts WHERE plan_id = ?",
        (plan["id"],),
    ).fetchone()


def _assert_receipt(receipt, library, plan, fingerprint):
    if tuple(receipt) != (library.library_id, catalogue_job_id(plan), fingerprint):
        raise AdoptionError("Die globale Abschlussquittung widerspricht dem Bibliotheksauftrag.")


def _register_global(connection, registry, registry_path, library, job, plan, fingerprint):
    job_id = catalogue_job_id(plan)
    backup = backup_key(library.library_id, job_id)
    signature = adoption_source_signature(plan)
    main = library.library_id == MAIN_LIBRARY_ID
    identity = signature if main else f"{library.library_id}:{signature}"
    metadata = {"library_id": library.library_id, "job_id": job_id, "legacy_adoption": True}
    args = {"_transaction_connection": registry}
    register_source_backup(
        registry_path, backup_id=backup, source_kind="import" if main else "existing_library",
        source_identity=identity, backup_path=job["source_root"],
        metadata={**metadata, "physical_source_identity": signature}, **args,
    )
    for key, group in groupby(_inventory_rows(connection, plan, job), key=lambda row: row["family_key"]):
        rows = list(group)
        members = [{
            "relative_path": row["relative_path"], "sha256": row["sha256"], "size_bytes": row["size_bytes"],
            "media_type": json.loads(row["metadata_json"])["media_type"],
        } for row in rows]
        for member in members:
            sha = member["sha256"]
            if registry.execute("SELECT 1 FROM source_media WHERE sha256 = ? LIMIT 1", (sha,)).fetchone():
                raise _RegistrationConflict("Die Prüfsumme wurde seit der Planung global registriert: " +
                                            member["relative_path"])
        content_fingerprint = family_content_fingerprint(members)
        if registry.execute(
            """SELECT 1 FROM canonical_families canonical JOIN family_claims claim USING (canonical_family_id)
                WHERE canonical.content_fingerprint = ? LIMIT 1""", (content_fingerprint,),
        ).fetchone():
            raise _RegistrationConflict("Die Dateifamilie besitzt bereits eine globale Zuordnung: " + key)
        source_family = occurrence_key(library.library_id, job_id, key)
        register_source_family(
            registry_path, source_family_key=source_family, backup_id=backup, family_key=key,
            content_fingerprint=content_fingerprint, metadata=metadata, **args,
        )
        media_ids = [register_source_media(registry_path, backup_id=backup, **member, **args)["media_id"]
                     for member in members]
        register_source_family_members(registry_path, source_family_key=source_family, media_ids=media_ids, **args)
        claim_source_family(
            registry_path, source_family_key=source_family, library_id=library.library_id,
            event_id=rows[0]["parent_event_id"], claim_state="owned", **args,
        )
    registry.execute(
        "INSERT INTO legacy_adoption_receipts VALUES (?, ?, ?, ?, ?)",
        (plan["id"], library.library_id, job_id, fingerprint, plan["documents_at"]),
    )


def _assert_catalogue_duplicates(connection, plan):
    row = connection.execute(
        """SELECT relative_path FROM legacy_adoption_moves move
            WHERE plan_id = ? AND target_path IS NOT NULL AND (
                EXISTS (SELECT 1 FROM files WHERE sha256_original = move.sha256) OR
                EXISTS (SELECT 1 FROM files WHERE sha256_current = move.sha256)
            ) LIMIT 1""", (plan["id"],),
    ).fetchone()
    if row:
        raise _RegistrationConflict("Die Prüfsumme wurde seit der Planung in der Bibliothek registriert: " +
                                    row["relative_path"])


def _assert_document_projection(connection, library, plan, events):
    expected = {row["relative_path"]: row["sha256"] for row in connection.execute(
        "SELECT relative_path, sha256 FROM legacy_adoption_documents WHERE plan_id = ?", (plan["id"],),
    )}
    actual = {path: checksum for path, _, checksum in catalogue_documents(
        connection, library, plan, events, plan["documents_at"],
    )}
    if expected != actual:
        raise _RegistrationConflict("Der Bibliotheksindex hat sich geändert. "
                                    "Prüfe die Änderungen und nutze gegebenenfalls den vorgesehenen Wiederherstellungsweg.")


@protect(kind="archive", error_type=AdoptionError)
def finalize_adoption(library_context, registry_path, job_id, operation_id):
    """Hold the existing durable archive lease across both database commits.

    Registry inventory and its receipt commit together. The library commits
    the regular catalogue and completed plan together. An interrupted lease
    must replay from the exact plan and receipt before other catalogue writes.
    """
    library = library_context
    with database_connection(library.database_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        job = _job(connection, library.library_id, job_id)
        plan = connection.execute("SELECT * FROM legacy_adoption_plans WHERE job_id = ?", (job_id,)).fetchone()
        if plan is None or plan["id"] != operation_id or plan["documents_at"] is None:
            return {"state": "unavailable", "error": "Bereite den aktuellen Verschiebeplan und seine Ereignisdokumente vor."}
        fingerprint = _fingerprint(connection, plan)
        with closing(sqlite3.connect(registry_path.absolute().as_uri() + "?mode=ro", uri=True)) as registry:
            receipt = _receipt(registry, plan)
        if receipt is not None:
            _assert_receipt(receipt, library, plan, fingerprint)
        if plan["state"] == "completed":
            if receipt is None:
                raise AdoptionError("Die globale Abschlussquittung fehlt.")
        else:
            execution = execution_row(connection, plan["id"])
            if execution is None or execution["phase"] != "registering":
                raise AdoptionError("Der bestätigte Auftrag ist noch nicht zur Registrierung bereit.")
            state = verify_locked(connection, library, job, plan, keep_stamps=True)
            if state != "verified":
                if receipt is not None:
                    raise AdoptionError("Archivnachweis seit Beginn der Registrierung verändert.")
                set_phase(connection, plan["id"], "repair")
            else:
                _complete_verified(connection, registry_path, library, job, plan, fingerprint, receipt)
        validate_active_roots()
    return plan_status(library, job_id)


def _complete_verified(connection, registry_path, library, job, plan, fingerprint, receipt):
    events = json.loads(plan["events_json"])
    connection.execute("SAVEPOINT adopt_catalogue")
    try:
        _assert_catalogue_duplicates(connection, plan)
        write_catalogue(connection, library, job, plan, events, plan["documents_at"])
        _assert_document_projection(connection, library, plan, events)
        with source_registry_transaction(registry_path) as registry:
            current_receipt = _receipt(registry, plan)
            if current_receipt is None:
                if receipt is not None:
                    raise AdoptionError("Die globale Abschlussquittung wurde entfernt.")
                _register_global(connection, registry, registry_path, library, job, plan, fingerprint)
            else:
                _assert_receipt(current_receipt, library, plan, fingerprint)
            try:
                assert_verification_stamps(connection, library, job, plan)
            except (OSError, AdoptionError) as error:
                if current_receipt is not None:
                    raise
                raise _RegistrationConflict(str(error)) from error
            validate_active_roots()
        assert_verification_stamps(connection, library, job, plan)
        connection.execute(
            "UPDATE legacy_adoption_plans SET state = 'completed' WHERE id = ?", (plan["id"],),
        )
        set_phase(connection, plan["id"], "completed")
    except _RegistrationConflict as error:
        if receipt is not None:
            raise
        connection.execute("ROLLBACK TO adopt_catalogue")
        set_phase(connection, plan["id"], "repair")
        connection.execute("UPDATE legacy_adoption_plans SET state = 'prepared' WHERE id = ?", (plan["id"],))
        connection.execute(
            "INSERT OR IGNORE INTO legacy_adoption_issues VALUES (?, '', ?)", (plan["id"], str(error)),
        )
    connection.execute("RELEASE adopt_catalogue")
