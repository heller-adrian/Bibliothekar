"""Build portable instructions and directory scaffolding for manual transfer."""
from contextlib import contextmanager
import json
from pathlib import Path
from tempfile import SpooledTemporaryFile
from zipfile import ZipFile

from app.database import database_connection
from app.legacy_adoption_inventory import _job
from app.legacy_adoption_paths import AdoptionError
from app.legacy_adoption_verify import _plan


@contextmanager
def directory_scaffold(library, job_id: str):
    with (
        SpooledTemporaryFile(max_size=2 * 1024 * 1024) as output,
        database_connection(library.database_path) as connection,
    ):
        connection.execute("BEGIN")
        _job(connection, library.library_id, job_id)
        plan = _plan(connection, job_id)
        with ZipFile(output, "w") as archive:
            for row in connection.execute(
                "SELECT relative_path FROM legacy_adoption_directories WHERE plan_id = ? ORDER BY relative_path",
                (plan["id"],),
            ):
                archive.mkdir(row["relative_path"] + "/")
        output.seek(0)
        yield output


def manual_manifest(library, job_id: str):
    with database_connection(library.database_path) as connection:
        connection.execute("BEGIN")
        job = _job(connection, library.library_id, job_id)
        plan = _plan(connection, job_id)
        yield json.dumps({
            "plan": plan["id"], "library": library.library_id,
            "source_root": job["source_root"], "archive_root": job["archive_root"],
            "format": 1,
        }, ensure_ascii=False) + "\n"
        for row in connection.execute(
            """SELECT move.*, inventory.identity, inventory.size_bytes, inventory.family_key
               FROM legacy_adoption_moves move JOIN legacy_adoption_inventory inventory
               ON inventory.job_id = ? AND inventory.relative_path = move.relative_path
               WHERE move.plan_id = ? ORDER BY move.relative_path""",
            (job_id, plan["id"]),
        ):
            source = str(Path(job["source_root"]) / row["relative_path"])
            target = str(Path(job["archive_root"]) / row["target_path"]) if row["target_path"] else None
            yield json.dumps({
                "source": source, "target": target, "size_bytes": row["size_bytes"],
                "sha256": row["sha256"], "source_identity": json.loads(row["identity"]),
                "family": row["family_key"], "event": row["parent_event_id"],
                "assigned_event": row["assigned_event_id"],
                "action": "move" if target else "skip_duplicate",
                "undo": {"from": target, "to": source} if target else None,
            }, ensure_ascii=False) + "\n"


@contextmanager
def event_documents(library, job_id: str, *, originals: bool = False):
    with (
        SpooledTemporaryFile(max_size=2 * 1024 * 1024) as output,
        database_connection(library.database_path) as connection,
    ):
        connection.execute("BEGIN")
        _job(connection, library.library_id, job_id)
        plan = _plan(connection, job_id)
        if plan["documents_at"] is None:
            raise AdoptionError("Die Ereignisdokumente müssen zuerst vorbereitet werden.")
        query = (
            """SELECT relative_path, document FROM legacy_adoption_baseline
               WHERE plan_id = ? AND document IS NOT NULL ORDER BY relative_path"""
            if originals else
            """SELECT relative_path, content FROM legacy_adoption_documents
               WHERE plan_id = ? ORDER BY relative_path"""
        )
        with ZipFile(output, "w") as archive:
            for path, content in connection.execute(query, (plan["id"],)):
                archive.writestr(path, content)
        output.seek(0)
        yield output
