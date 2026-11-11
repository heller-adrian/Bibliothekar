"""Persist resumable legacy inventory in the selected library's catalogue."""
from contextlib import ExitStack
from itertools import groupby
import json
import os
from pathlib import Path
import stat
from uuid import uuid4

from app import legacy_adoption_dataset as dataset
from app.database import database_connection
from app.legacy_adoption_paths import (
    AdoptionError, absolute_root, bound_child_directory, bound_directory,
    bound_file, bound_sha256, directory_identity, file_identity,
)
from app.library_context import LibraryContext
from app.metadata import (
    analyze_file_metadata, classify_media, family_key, read_bound_metadata,
    summarize_file_metadata,
)
from app.source_filter import IGNORED_SOURCE_DIRECTORIES, should_ignore_source_relative


_BATCH_SIZE = 48
_MAX_DEPTH = 80


def _overlaps(left: Path, right: Path) -> bool:
    return left == right or left in right.parents or right in left.parents


def qualify_source(
    library: LibraryContext, source: Path, *, other_managed_roots: tuple[Path, ...] = (),
):
    source = absolute_root(source)
    archive = absolute_root(library.archive_root)
    managed = (archive, library.workspace_root, library.work_root,
               library.database_path.parent, *other_managed_roots)
    if any(_overlaps(source, absolute_root(root)) for root in managed):
        raise AdoptionError("Die Bestandsquelle muss von verwalteten Ordnern getrennt sein.")
    with bound_directory(source) as source_fd, bound_directory(archive) as archive_fd:
        source_identity = directory_identity(os.fstat(source_fd))
        archive_identity = directory_identity(os.fstat(archive_fd))
        if source_identity == archive_identity:
            raise AdoptionError("Bestandsquelle und Archiv bezeichnen denselben Ordner.")
        evidence = dataset.prove(source, archive, source_fd, archive_fd)
        read_only = bool(os.fstatvfs(source_fd).f_flag & os.ST_RDONLY)
    return source, archive, source_identity, archive_identity, evidence, read_only


def create_job(
    library: LibraryContext, source: Path, *, other_managed_roots: tuple[Path, ...] = (),
) -> str:
    source, archive, source_identity, archive_identity, evidence, _ = qualify_source(
        library, source, other_managed_roots=other_managed_roots,
    )
    job_id = uuid4().hex
    with database_connection(library.database_path) as connection:
        connection.execute(
            """INSERT INTO legacy_adoption_jobs (
                   id, library_id, source_root, source_device, source_inode,
                   archive_root, archive_device, archive_inode, state, dataset_json, dataset_verified_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'ready', ?, CURRENT_TIMESTAMP)""",
            (job_id, library.library_id, str(source), *source_identity,
             str(archive), *archive_identity, json.dumps(evidence)),
        )
    return job_id


def _job(connection, library_id: str, job_id: str):
    job = connection.execute(
        "SELECT * FROM legacy_adoption_jobs WHERE id = ? AND library_id = ?",
        (job_id, library_id),
    ).fetchone()
    if job is None:
        raise AdoptionError("Übernahmeauftrag wurde in dieser Bibliothek nicht gefunden.")
    return job


def inventory_status(library: LibraryContext, job_id: str) -> dict:
    with database_connection(library.database_path) as connection:
        connection.execute("BEGIN")
        job = dict(_job(connection, library.library_id, job_id))
        counts = connection.execute(
            """SELECT count(*) AS entries, count(sha256) AS files,
                      count(DISTINCT CASE WHEN sha256 IS NOT NULL THEN family_key END) AS families,
                      count(error) AS errors, coalesce(sum(CASE WHEN sha256 IS NOT NULL
                          THEN size_bytes ELSE 0 END), 0) AS bytes
                 FROM legacy_adoption_inventory WHERE job_id = ? AND seen_generation = ?""",
            (job_id, job["scan_generation"]),
        ).fetchone()
    return {
        "id": job["id"], "state": job["state"], "source_root": job["source_root"],
        "scan_error": job["scan_error"], "dataset": json.loads(job["dataset_json"] or "null"),
        "dataset_verified_at": job["dataset_verified_at"], **dict(counts),
    }


def _inventory_groups(rows, source):
    for key, group in groupby(rows, key=lambda row: row["family_key"]):
        members = [dict(row) for row in group]
        files = [json.loads(row["metadata_json"]) for row in members if row["metadata_json"]]
        family = {"family_key": key, "status": "review_required"}
        if files:
            family = summarize_file_metadata(source, files)["families"][0]
            if any(row["error"] for row in members) or any(row["review_required"] for row in files):
                family["status"] = "review_required"
        yield family, members, files


def inventory_chronology(library: LibraryContext, job_id: str, *, year: str = ""):
    if year and (len(year) != 4 or not year.isascii() or not year.isdigit()):
        raise AdoptionError("Ungültiges Jahr.")
    with database_connection(library.database_path) as connection:
        connection.execute("BEGIN")
        job = _job(connection, library.library_id, job_id)
        if job["state"] != "inventoried":
            raise AdoptionError("Die Inventur muss zuerst abgeschlossen werden.")
        counts = connection.execute(
            """SELECT substr(capture_time, 1, :length) AS period, count(*) AS families,
                      sum(review_required) AS review
                 FROM legacy_adoption_families
                WHERE job_id = :job AND (:year = '' OR capture_time LIKE :year || '-%')
                GROUP BY period ORDER BY period""",
            {"job": job_id, "length": 10 if year else 4, "year": year},
        )
        return [dict(row) for row in counts]


def inventory_families(
    library: LibraryContext, job_id: str, *, after: str = "", limit: int = 100,
    day: str | None = None,
) -> list[dict]:
    with database_connection(library.database_path) as connection:
        connection.execute("BEGIN")
        job = _job(connection, library.library_id, job_id)
        if job["state"] != "inventoried":
            raise AdoptionError("Die Inventur muss zuerst abgeschlossen werden.")
        rows = connection.execute(
            """WITH page AS (
                   SELECT family_key FROM legacy_adoption_families
                    WHERE job_id = :job AND family_key > :after
                      AND (:day IS NULL OR substr(capture_time, 1, 10) = :day
                           OR (:day = '' AND capture_time IS NULL))
                    ORDER BY family_key LIMIT :limit
               )
               SELECT inventory.* FROM legacy_adoption_inventory AS inventory
               JOIN page USING (family_key)
               WHERE job_id = :job ORDER BY family_key, relative_path""",
            {"job": job_id, "after": after, "limit": max(1, min(limit, 200)), "day": day},
        )
        result = []
        for family, members, files in _inventory_groups(rows, Path(job["source_root"])):
            errors = [row for row in members if row["error"]]
            result.append({
                **family,
                "files": files,
                "errors": [{"relative_path": row["relative_path"], "message": row["error"]}
                           for row in errors],
            })
    return result


def inventory_errors(library: LibraryContext, job_id: str, *, after: str = "", limit: int = 100):
    with database_connection(library.database_path) as connection:
        job = _job(connection, library.library_id, job_id)
        return [dict(row) for row in connection.execute(
            """SELECT relative_path, error FROM legacy_adoption_inventory
                WHERE job_id = ? AND seen_generation = ? AND error IS NOT NULL AND relative_path > ?
                ORDER BY relative_path LIMIT ?""",
            (job_id, job["scan_generation"], after, max(1, min(limit, 200))),
        )]


def discard_job(library: LibraryContext, job_id: str) -> None:
    with database_connection(library.database_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        job = _job(connection, library.library_id, job_id)
        if connection.execute(
            """SELECT 1 FROM legacy_adoption_plans AS plan
                 LEFT JOIN legacy_adoption_execution AS execution ON execution.plan_id = plan.id
                WHERE plan.job_id = ? AND (execution.plan_id IS NOT NULL OR plan.state != 'prepared')""",
            (job_id,),
        ).fetchone():
            raise AdoptionError("Der bestätigte Auftrag kann nur kontrolliert zurückgenommen werden.")
        connection.execute("DELETE FROM legacy_adoption_plans WHERE job_id = ?", (job_id,))
        connection.execute("DELETE FROM legacy_adoption_families WHERE job_id = ?", (job_id,))
        connection.execute("DELETE FROM legacy_adoption_inventory WHERE job_id = ?", (job_id,))
        connection.execute(
            """UPDATE legacy_adoption_jobs SET state = 'discarded', scan_error = NULL
                WHERE id = ?""",
            (job_id,),
        )


def _identity_json(info) -> str:
    return json.dumps(file_identity(info), separators=(",", ":"))


def _legacy_family_key(source, relative):
    path = source / relative
    if path.suffix.lower() == ".xmp" and classify_media(path.with_suffix("")) not in {"other", "xmp"}:
        path = path.with_suffix("")
    return family_key(source, path)


def _row(relative: Path, source: Path, info=None, *, media=False, error=None):
    return {
        "relative_path": relative.as_posix(),
        "family_key": _legacy_family_key(source, relative) if media else None,
        "identity": _identity_json(info) if info is not None else None,
        "size_bytes": info.st_size if info is not None else None,
        "sha256": None,
        "metadata_json": None,
        "error": error,
    }


def _directory_stamp(info):
    return (*directory_identity(info), info.st_mtime_ns, info.st_ctime_ns)


def _scan_tree(source_fd, source, consume, cancel):
    device = os.fstat(source_fd).st_dev

    def walk(directory, prefix, depth):
        before = _directory_stamp(os.fstat(directory))
        batch = []

        def queue(row):
            batch.append(row)
            if len(batch) == _BATCH_SIZE:
                consume(directory, batch)
                batch.clear()

        with os.scandir(directory) as entries:
            for entry in entries:
                cancel()
                relative = prefix / entry.name
                if any(0xD800 <= ord(char) <= 0xDFFF for char in entry.name):
                    raise AdoptionError("Nicht als UTF-8 lesbarer Dateiname: " + ascii(str(relative)))
                try:
                    info = entry.stat(follow_symlinks=False)
                except OSError as error:
                    queue(_row(relative, source, error=str(error)))
                    continue
                if stat.S_ISLNK(info.st_mode):
                    queue(_row(relative, source, error="Symbolische Links werden nicht verfolgt."))
                    continue
                if info.st_dev != device:
                    queue(_row(relative, source, error="Weitere Dateisysteme werden nicht durchsucht."))
                    continue
                if should_ignore_source_relative(relative):
                    continue
                if stat.S_ISDIR(info.st_mode):
                    if entry.name.casefold() in IGNORED_SOURCE_DIRECTORIES:
                        continue
                    if depth == _MAX_DEPTH:
                        queue(_row(relative, source, error="Die Verzeichnistiefe überschreitet das Limit."))
                        continue
                    try:
                        with bound_child_directory(directory, entry.name, directory_identity(info)) as child:
                            walk(child, relative, depth + 1)
                    except (OSError, AdoptionError) as error:
                        if not isinstance(error, PermissionError):
                            raise
                        queue(_row(relative, source, error=str(error)))
                elif stat.S_ISREG(info.st_mode):
                    queue(_row(relative, source, info, media=classify_media(relative) != "other"))
                else:
                    queue(_row(relative, source, error="Der Pfad bezeichnet keine reguläre Datei."))
        if batch:
            consume(directory, batch)
        if _directory_stamp(os.fstat(directory)) != before:
            raise AdoptionError("Der Quellordner wurde während der Inventur verändert: " + str(prefix))

    walk(source_fd, Path("."), 0)


def _read_batch(directory, source, rows, cached, cancel):
    pending = []
    with ExitStack() as files:
        for row in rows:
            if row["family_key"] is None:
                continue
            path = row["relative_path"]
            old = cached.get(path)
            bound = bound_file(directory, Path(path).name, tuple(json.loads(row["identity"])))
            try:
                if old is not None and old["identity"] == row["identity"] and old["sha256"]:
                    with bound:
                        record = json.loads(old["metadata_json"])
                        record["family_key"] = row["family_key"]
                        row.update(sha256=old["sha256"], metadata_json=json.dumps(record, ensure_ascii=False))
                    continue
                descriptor, _ = files.enter_context(bound)
            except (OSError, AdoptionError) as error:
                row.update(sha256=None, metadata_json=None, error=str(error))
                continue
            pending.append((descriptor, row))
        metadata = read_bound_metadata(tuple(fd for fd, _ in pending), cancel)
        for descriptor, row in pending:
            row["sha256"] = bound_sha256(descriptor, cancel)
            try:
                record = analyze_file_metadata(
                    source, source / row["relative_path"], row["size_bytes"], metadata.get(descriptor, {}),
                )
            except ValueError:
                record = analyze_file_metadata(source, source / row["relative_path"], row["size_bytes"], {})
                record["metadata_error"] = "Ungültiger Metadatenwert."
            reported_error = metadata.get(descriptor, {}).get("ExifTool:Error")
            if reported_error:
                record["metadata_error"] = str(reported_error)
                record["review_required"] = True
            record["family_key"] = row["family_key"]
            row["metadata_json"] = json.dumps(record, ensure_ascii=False)


def scan_inventory(library: LibraryContext, job_id: str, *, cancellation_callback=None) -> dict:
    def cancel():
        if cancellation_callback is not None:
            cancellation_callback()

    with database_connection(library.database_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        job = _job(connection, library.library_id, job_id)
        if job["state"] not in {"ready", "scanning", "inventoried"}:
            raise AdoptionError("Dieser Auftrag kann nicht inventarisiert werden.")
        if connection.execute("SELECT 1 FROM legacy_adoption_plans WHERE job_id = ?", (job_id,)).fetchone():
            raise AdoptionError("Der gespeicherte Verschiebeplan muss zuerst zurückgenommen werden.")
        if Path(job["archive_root"]) != library.archive_root:
            raise AdoptionError("Die Archivwurzel der Zielbibliothek hat sich geändert.")
        generation = job["scan_generation"] + 1
        connection.execute(
            """UPDATE legacy_adoption_jobs
                  SET scan_generation = ?, scan_error = NULL, state = 'scanning'
                WHERE id = ?""",
            (generation, job_id),
        )

    def check_current(connection):
        current = _job(connection, library.library_id, job_id)
        if current["state"] != "scanning" or current["scan_generation"] != generation:
            raise AdoptionError("Die Inventur wurde verworfen oder durch einen Neustart ersetzt.")

    def consume(directory, rows):
        paths = [row["relative_path"] for row in rows]
        with database_connection(library.database_path) as connection:
            check_current(connection)
            placeholders = ",".join("?" for _ in paths)
            cached = {row["relative_path"]: row for row in connection.execute(
                f"""SELECT relative_path, identity, sha256, metadata_json FROM legacy_adoption_inventory
                    WHERE job_id = ? AND relative_path IN ({placeholders})""",
                (job_id, *paths),
            )}
        _read_batch(directory, source, rows, cached, cancel)
        with database_connection(library.database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            check_current(connection)
            connection.executemany(
                """INSERT INTO legacy_adoption_inventory (
                       job_id, relative_path, family_key, size_bytes, identity, sha256,
                       metadata_json, error, seen_generation
                   ) VALUES (
                       :job, :relative_path, :family_key, :size_bytes, :identity, :sha256,
                       :metadata_json, :error, :generation
                   )
                   ON CONFLICT(job_id, relative_path) DO UPDATE SET
                       family_key = excluded.family_key, size_bytes = excluded.size_bytes,
                       identity = excluded.identity, sha256 = excluded.sha256,
                       metadata_json = excluded.metadata_json, error = excluded.error,
                       seen_generation = excluded.seen_generation""",
                [{**row, "job": job_id, "generation": generation} for row in rows],
            )

    source = Path(job["source_root"])
    archive = library.archive_root
    try:
        with (
            bound_directory(source, (job["source_device"], job["source_inode"])) as source_fd,
            bound_directory(archive, (job["archive_device"], job["archive_inode"])) as archive_fd,
        ):
            evidence = json.loads(job["dataset_json"] or "null")
            dataset.revalidate(evidence, source, archive, source_fd, archive_fd)
            _scan_tree(source_fd, source, consume, cancel)
            dataset.revalidate(evidence, source, archive, source_fd, archive_fd)
        cancel()
        with database_connection(library.database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            check_current(connection)
            connection.execute(
                "DELETE FROM legacy_adoption_inventory WHERE job_id = ? AND seen_generation != ?",
                (job_id, generation),
            )
            connection.execute("DELETE FROM legacy_adoption_families WHERE job_id = ?", (job_id,))
            rows = connection.execute(
                """SELECT * FROM legacy_adoption_inventory
                    WHERE job_id = ? AND family_key IS NOT NULL ORDER BY family_key, relative_path""",
                (job_id,),
            )
            connection.executemany(
                """INSERT INTO legacy_adoption_families (job_id, family_key, capture_time, review_required)
                   VALUES (?, ?, ?, ?)""",
                ((job_id, family["family_key"], family.get("selected_capture_time"),
                  family["status"] == "review_required")
                 for family, _, _ in _inventory_groups(rows, source)),
            )
            connection.execute("UPDATE legacy_adoption_jobs SET state = 'inventoried' WHERE id = ?", (job_id,))
    except Exception as error:
        with database_connection(library.database_path) as connection:
            connection.execute(
                """UPDATE legacy_adoption_jobs SET scan_error = ? WHERE id = ?
                    AND state = 'scanning' AND scan_generation = ?""",
                (str(error)[:2000], job_id, generation),
            )
        raise
    return inventory_status(library, job_id)
