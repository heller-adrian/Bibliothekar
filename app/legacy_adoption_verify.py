"""Compare manually moved originals with the persisted plan through read-only descriptors."""
from contextlib import ExitStack
import json
import os
import stat

from app.database import database_connection
from app.event_inventory import event_root_relative
from app.legacy_adoption_inventory import _job
from app.legacy_adoption_paths import AdoptionError, bound_file, bound_sha256, file_identity, relative_parent, target_key, walk_bound_files
from app.legacy_adoption_plan import _assert_timeline, _existing_event, _roots, plan_status


def _plan(connection, job_id):
    plan = connection.execute("SELECT * FROM legacy_adoption_plans WHERE job_id = ?", (job_id,)).fetchone()
    if plan is None:
        raise AdoptionError("Kein Verschiebeplan vorhanden.")
    return plan


def _entry(root, relative):
    try:
        with relative_parent(root, relative) as (directory, name):
            return os.stat(name, dir_fd=directory, follow_symlinks=False)
    except FileNotFoundError:
        return None


def _verify_move(source, archive, row):
    try:
        original = _entry(source, row["relative_path"])
        with relative_parent(archive, row["target_path"]) as (directory, name):
            with bound_file(directory, name) as (descriptor, info):
                if info.st_dev != os.fstat(archive).st_dev:
                    return "unsafe"
                if info.st_size != row["size_bytes"]:
                    return "size_mismatch"
                if bound_sha256(descriptor) != row["sha256"]:
                    return "sha256_mismatch"
        return "source_present" if original is not None else "verified"
    except FileNotFoundError:
        return "missing"
    except (OSError, AdoptionError):
        return "unsafe"


def _catalogue_unchanged(connection, job_id, events):
    _assert_timeline(connection, job_id, events)
    for event in events:
        if event["existing"] and json.loads(json.dumps(_existing_event(connection, event["id"]))) != event:
            raise AdoptionError("Das bestehende Ereignis hat sich seit der Planung geändert: " + event["name"])


def verify_media(library, job_id: str) -> dict:
    with database_connection(library.database_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        job = _job(connection, library.library_id, job_id)
        plan = _plan(connection, job_id)
        if plan["state"] not in {"prepared", "media_verified", "verified"}:
            raise AdoptionError("Der Verschiebeplan kann in diesem Zustand nicht erneut geprüft werden.")
        verify_locked(connection, library, job, plan)
    return plan_status(library, job_id)


def verify_locked(connection, library, job, plan):
    job_id = job["id"]
    events = json.loads(plan["events_json"])
    plan_id = plan["id"]
    documents = {
        row["relative_path"]: (row["size_bytes"], row["sha256"]) for row in connection.execute(
            """SELECT relative_path, length(content) AS size_bytes, sha256 FROM legacy_adoption_documents
                WHERE plan_id = ?""", (plan_id,),
        )
    }
    connection.execute("DELETE FROM legacy_adoption_issues WHERE plan_id = ?", (plan_id,))

    def issue(path, message):
        connection.execute(
            "INSERT OR IGNORE INTO legacy_adoption_issues VALUES (?, ?, ?)", (plan_id, path, message),
        )

    try:
        _catalogue_unchanged(connection, job_id, events)
    except AdoptionError as error:
        issue("", str(error))

    with ExitStack() as stack:
        source, archive = _roots(stack, library, job)
        moves = connection.execute(
            """SELECT move.*, inventory.size_bytes FROM legacy_adoption_moves move
               JOIN legacy_adoption_inventory inventory ON inventory.job_id = ? AND
                    inventory.relative_path = move.relative_path
               WHERE move.plan_id = ? AND target_path IS NOT NULL ORDER BY move.relative_path""",
            (job_id, plan_id),
        )
        for row in moves:
            status = _verify_move(source, archive, row)
            connection.execute(
                "UPDATE legacy_adoption_moves SET status = ? WHERE plan_id = ? AND relative_path = ?",
                (status, plan_id, row["relative_path"]),
            )

        for directory in connection.execute(
            "SELECT relative_path FROM legacy_adoption_directories WHERE plan_id = ?", (plan_id,),
        ):
            path = directory["relative_path"]
            try:
                info = _entry(archive, path)
                if info is None or not stat.S_ISDIR(info.st_mode) or info.st_dev != os.fstat(archive).st_dev:
                    issue(path, "Benötigter Archivordner fehlt oder ist unsicher.")
            except (OSError, AdoptionError) as error:
                issue(path, str(error))

        for event in events:
            prefix = event_root_relative(event)
            try:
                for path, _, _, _ in walk_bound_files(archive, prefix):
                    expected = connection.execute(
                        """SELECT 1 FROM legacy_adoption_baseline WHERE plan_id = ? AND relative_path = ?
                           UNION ALL
                           SELECT 1 FROM legacy_adoption_moves WHERE plan_id = ? AND target_key = ?
                               AND target_path = ?""",
                        (plan_id, path, plan_id, target_key(path), path),
                    ).fetchone()
                    if expected is None and path not in documents:
                        issue(path, "Zusätzliche Datei im betroffenen Ereignisordner.")
            except (OSError, AdoptionError) as error:
                issue(str(prefix), str(error))

        for row in connection.execute(
            "SELECT * FROM legacy_adoption_baseline WHERE plan_id = ?", (plan_id,),
        ):
            path = row["relative_path"]
            if path in documents:
                continue
            try:
                with relative_parent(archive, path) as (directory, name):
                    with bound_file(directory, name) as (descriptor, info):
                        if info.st_size != row["size_bytes"] or bound_sha256(descriptor) != row["sha256"]:
                            issue(path, "Bereits vorhandene Archivdatei wurde verändert.")
            except (OSError, AdoptionError) as error:
                issue(path, str(error))

        for path, proof in documents.items():
            if not _matches(archive, path, *proof):
                issue(path, "Das vorbereitete Ereignisdokument fehlt oder stimmt nicht überein.")

    pending = connection.execute(
        """SELECT 1 FROM legacy_adoption_issues WHERE plan_id = ?
           UNION ALL SELECT 1 FROM legacy_adoption_moves WHERE plan_id = ?
               AND status NOT IN ('verified', 'duplicate') LIMIT 1""",
        (plan_id, plan_id),
    ).fetchone()
    state = "prepared" if pending else "verified" if documents else "media_verified"
    connection.execute("UPDATE legacy_adoption_plans SET state = ? WHERE id = ?", (state, plan_id))
    return state


def _matches(root, path, size, checksum):
    try:
        with relative_parent(root, path) as (directory, name):
            with bound_file(directory, name) as (descriptor, info):
                return (info.st_dev == os.fstat(root).st_dev and info.st_size == size
                        and bound_sha256(descriptor) == checksum)
    except (OSError, AdoptionError):
        return False


def reopen_plan(library, job_id: str) -> None:
    """Forget a plan after independently confirming the original file layout."""
    with database_connection(library.database_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        job = _job(connection, library.library_id, job_id)
        plan = _plan(connection, job_id)
        if plan["state"] not in {"prepared", "media_verified", "verified"}:
            raise AdoptionError("Der Verschiebeplan kann in diesem Zustand nicht zurückgenommen werden.")
        with ExitStack() as stack:
            source, archive = _roots(stack, library, job)
            for row in connection.execute(
                """SELECT * FROM legacy_adoption_moves WHERE plan_id = ? AND target_path IS NOT NULL""",
                (plan["id"],),
            ):
                if _entry(archive, row["target_path"]) is not None:
                    raise AdoptionError("Vor der Rücknahme die Datei manuell zurückbringen: " + row["target_path"])
                try:
                    with relative_parent(source, row["relative_path"]) as (directory, name):
                        with bound_file(directory, name) as (descriptor, _):
                            if bound_sha256(descriptor) != row["sha256"]:
                                raise AdoptionError("Die Datei an der Quelle stimmt nicht mit dem Plan überein.")
                except FileNotFoundError as error:
                    raise AdoptionError("Quelldatei fehlt: " + row["relative_path"]) from error
            for row in connection.execute(
                """SELECT doc.relative_path, base.size_bytes, base.sha256 FROM legacy_adoption_documents doc
                     LEFT JOIN legacy_adoption_baseline base USING (plan_id, relative_path)
                    WHERE doc.plan_id = ?""", (plan["id"],),
            ):
                path = row["relative_path"]
                if row["sha256"] is not None:
                    if not _matches(archive, path, row["size_bytes"], row["sha256"]):
                        raise AdoptionError("Vor der Rücknahme das frühere Ereignisdokument wiederherstellen: " + path)
                elif _entry(archive, path) is not None:
                    raise AdoptionError("Vor der Rücknahme das neue Ereignisdokument manuell entfernen: " + path)
        connection.execute("DELETE FROM legacy_adoption_plans WHERE id = ?", (plan["id"],))


def plan_issues(library, job_id: str, *, limit: int = 200):
    with database_connection(library.database_path) as connection:
        _job(connection, library.library_id, job_id)
        plan = _plan(connection, job_id)
        return [dict(row) for row in connection.execute(
            """SELECT relative_path, issue FROM legacy_adoption_issues
               WHERE plan_id = ? ORDER BY relative_path LIMIT ?""",
            (plan["id"], max(1, min(limit, 200))),
        )]
