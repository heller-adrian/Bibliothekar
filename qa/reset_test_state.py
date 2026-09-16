#!/usr/bin/env python3
"""Deterministischer Clean-Slate-Reset fuer die isolierte Bibliothekar-QA.

Der Reset ist absichtlich radikal, aber hart auf den Hermes-QA-Bereich begrenzt:
- SQLite-Schema/Migrationsstand bleibt erhalten, alle Testdaten werden geloescht.
- Mutable QA-Verzeichnisse werden geleert.
- Die kanonische, unveraenderliche Testkopie DEEPTEST_SD_02 kann erhalten bleiben.
- Evidence/Reports ausserhalb der explizit mutablen Verzeichnisse bleiben unangetastet.

Das Skript ist fuer einen laufenden, aber IDLEN isolierten QA-Container gedacht.
Es verweigert den Reset, solange ein nicht-terminaler Job in der QA-DB existiert.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from typing import Any


DEFAULT_QA_ROOT = Path("/mnt/storage/ki-workspace/hermes/bibliothekar-qa")
PRODUCTION_ARCHIVE = Path("/mnt/storage/fotos/Kamerabibliothek")
PRODUCTION_DATABASE = Path("/mnt/apps/appdata/kamera-automatisierung/database")
TERMINAL_JOB_STATES = {"completed", "failed", "interrupted"}
PRESERVED_DB_TABLES = {"schema_versions"}
DEFAULT_PRESERVED_IMPORT_SOURCES = ("DEEPTEST_SD_02",)


class ResetError(RuntimeError):
    pass


def canon(path: Path) -> Path:
    return Path(os.path.realpath(os.fspath(path)))


def is_within(path: Path, parent: Path) -> bool:
    path = canon(path)
    parent = canon(parent)
    return path == parent or parent in path.parents


def require_within(path: Path, parent: Path, label: str) -> Path:
    resolved = canon(path)
    if not is_within(resolved, parent):
        raise ResetError(f"{label} liegt ausserhalb des erlaubten Bereichs: {resolved}")
    return resolved


def reject_production_overlap(path: Path, label: str) -> None:
    resolved = canon(path)
    for forbidden, name in (
        (canon(PRODUCTION_ARCHIVE), "reale Kamerabibliothek"),
        (canon(PRODUCTION_DATABASE), "Produktiv-DB"),
    ):
        if is_within(resolved, forbidden) or is_within(forbidden, resolved):
            raise ResetError(f"{label} kollidiert mit {name}: {resolved}")


def quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sqlite_tables(connection: sqlite3.Connection) -> list[str]:
    return [
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
    ]


def table_counts(connection: sqlite3.Connection, tables: list[str]) -> dict[str, int]:
    result: dict[str, int] = {}
    for table in tables:
        value = connection.execute(
            f"SELECT COUNT(*) FROM {quote_identifier(table)}"
        ).fetchone()[0]
        result[table] = int(value)
    return result


def schema_versions(connection: sqlite3.Connection) -> list[int]:
    return [
        int(row[0])
        for row in connection.execute(
            "SELECT version FROM schema_versions ORDER BY version"
        )
    ]


def active_jobs(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    tables = set(sqlite_tables(connection))
    if "jobs" not in tables:
        return []
    rows = connection.execute(
        "SELECT id, state, stage, operation, updated_at FROM jobs ORDER BY created_at"
    ).fetchall()
    active: list[dict[str, Any]] = []
    for row in rows:
        state = str(row[1])
        if state not in TERMINAL_JOB_STATES:
            active.append(
                {
                    "id": str(row[0]),
                    "state": state,
                    "stage": row[2],
                    "operation": row[3],
                    "updated_at": row[4],
                }
            )
    return active


def inspect_database(database: Path) -> dict[str, Any]:
    if not database.is_file() or database.is_symlink():
        raise ResetError(f"QA-Datenbank fehlt oder ist kein regulaeres File: {database}")
    connection = sqlite3.connect(database, timeout=5.0)
    try:
        connection.execute("PRAGMA busy_timeout=5000")
        tables = sqlite_tables(connection)
        if "schema_versions" not in tables:
            raise ResetError("QA-Datenbank enthaelt keine schema_versions-Tabelle")
        mutable_tables = [name for name in tables if name not in PRESERVED_DB_TABLES]
        return {
            "tables": tables,
            "mutable_tables": mutable_tables,
            "schema_versions": schema_versions(connection),
            "counts": table_counts(connection, mutable_tables),
            "active_jobs": active_jobs(connection),
            "sha256": sha256_file(database),
        }
    finally:
        connection.close()


def reset_database(database: Path, *, dry_run: bool) -> dict[str, Any]:
    before = inspect_database(database)
    if before["active_jobs"]:
        ids = ", ".join(
            f"{item['id']}:{item['state']}" for item in before["active_jobs"]
        )
        raise ResetError(
            "Clean-Slate verweigert: nicht-terminale QA-Jobs vorhanden: " + ids
        )

    if dry_run:
        return {"before": before, "after": before, "dry_run": True}

    connection = sqlite3.connect(database, timeout=10.0)
    try:
        connection.execute("PRAGMA busy_timeout=10000")
        connection.execute("PRAGMA foreign_keys=OFF")
        connection.execute("BEGIN IMMEDIATE")
        try:
            tables = sqlite_tables(connection)
            if "schema_versions" not in tables:
                raise ResetError("QA-Datenbank enthaelt keine schema_versions-Tabelle")
            versions_before = schema_versions(connection)
            for table in tables:
                if table in PRESERVED_DB_TABLES:
                    continue
                connection.execute(f"DELETE FROM {quote_identifier(table)}")
            has_sequence = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='sqlite_sequence'"
            ).fetchone()
            if has_sequence:
                connection.execute("DELETE FROM sqlite_sequence")
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.execute("PRAGMA foreign_keys=ON")

        foreign_key_violations = connection.execute("PRAGMA foreign_key_check").fetchall()
        integrity = str(connection.execute("PRAGMA integrity_check").fetchone()[0])
        versions_after = schema_versions(connection)
        if versions_after != versions_before:
            raise ResetError(
                "Schema-Versionen wurden beim Reset veraendert: "
                f"vorher={versions_before}, nachher={versions_after}"
            )
        if foreign_key_violations:
            raise ResetError(
                f"Foreign-Key-Check nach Reset fehlgeschlagen: {foreign_key_violations[:5]}"
            )
        if integrity.lower() != "ok":
            raise ResetError(f"SQLite integrity_check nach Reset fehlgeschlagen: {integrity}")
        try:
            connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        except sqlite3.DatabaseError:
            pass
    finally:
        connection.close()

    after = inspect_database(database)
    non_zero = {
        name: count for name, count in after["counts"].items() if int(count) != 0
    }
    if non_zero:
        raise ResetError(f"QA-Datenbank ist nach Reset nicht leer: {non_zero}")
    return {"before": before, "after": after, "dry_run": False}


def count_files(root: Path) -> int:
    if not root.exists():
        return 0
    return sum(1 for path in root.rglob("*") if path.is_file() or path.is_symlink())


def clear_directory(
    root: Path,
    *,
    preserve_top_level: set[str] | None = None,
    dry_run: bool,
) -> dict[str, Any]:
    preserve_top_level = preserve_top_level or set()
    if root.exists() and root.is_symlink():
        raise ResetError(f"Mutable QA-Wurzel darf kein Symlink sein: {root}")
    root.mkdir(parents=True, exist_ok=True)

    before = count_files(root)
    removed_entries: list[str] = []
    preserved_entries: list[str] = []

    for child in sorted(root.iterdir(), key=lambda item: item.name):
        if child.name in preserve_top_level:
            preserved_entries.append(child.name)
            continue
        if os.path.ismount(child):
            raise ResetError(f"Reset verweigert: Mountpoint innerhalb QA-State: {child}")
        removed_entries.append(child.name)
        if dry_run:
            continue
        if child.is_symlink() or child.is_file():
            child.unlink()
        elif child.is_dir():
            shutil.rmtree(child)
        else:
            raise ResetError(f"Unbekannter Dateityp im QA-State: {child}")

    after = before if dry_run else count_files(root)
    return {
        "path": str(root),
        "files_before": before,
        "files_after": after,
        "removed_top_level": removed_entries,
        "preserved_top_level": preserved_entries,
        "dry_run": dry_run,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Setzt einen isolierten Bibliothekar-QA-Lauf deterministisch auf Clean Slate."
    )
    parser.add_argument("--run-root", required=True, type=Path)
    parser.add_argument("--qa-root", type=Path, default=DEFAULT_QA_ROOT)
    parser.add_argument("--archive-root", type=Path)
    parser.add_argument(
        "--preserve-import-source",
        action="append",
        default=None,
        help="Top-Level-Name unter import-sources, der erhalten bleiben soll; wiederholbar.",
    )
    parser.add_argument(
        "--keep-archive",
        action="store_true",
        help="QA-Archiv nicht leeren (nur fuer explizite Persistenz-Szenarien).",
    )
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    qa_root = canon(args.qa_root)
    run_root = require_within(args.run_root, qa_root / "runs", "Run-Root")
    if run_root == canon(qa_root / "runs"):
        raise ResetError("Run-Root darf nicht die runs-Wurzel selbst sein")
    reject_production_overlap(run_root, "Run-Root")

    database = require_within(
        run_root / "database" / "kamera.sqlite3",
        run_root,
        "QA-Datenbank",
    )
    workspace = require_within(run_root / "workspace", run_root, "QA-Workspace")
    logs = require_within(run_root / "logs", run_root, "QA-Logs")
    imports = require_within(run_root / "import-sources", run_root, "QA-Importquellen")
    removable = require_within(
        run_root / "removable-sources", run_root, "QA-Removable-Quellen"
    )
    nas_sources = require_within(run_root / "nas-sources", run_root, "QA-NAS-Quellen")
    pool_probe = require_within(run_root / "pool-probe", run_root, "QA-Pool-Probe")
    archive_root = canon(args.archive_root or (qa_root / "archive-test-library"))
    archive_root = require_within(archive_root, qa_root, "QA-Archiv")
    reject_production_overlap(archive_root, "QA-Archiv")

    for path, label in (
        (database, "QA-Datenbank"),
        (workspace, "QA-Workspace"),
        (logs, "QA-Logs"),
        (imports, "QA-Importquellen"),
        (removable, "QA-Removable-Quellen"),
        (nas_sources, "QA-NAS-Quellen"),
        (pool_probe, "QA-Pool-Probe"),
    ):
        reject_production_overlap(path, label)

    preserve_import = set(
        args.preserve_import_source
        if args.preserve_import_source is not None
        else DEFAULT_PRESERVED_IMPORT_SOURCES
    )
    if any("/" in value or value in {"", ".", ".."} for value in preserve_import):
        raise ResetError("--preserve-import-source akzeptiert nur einfache Top-Level-Namen")

    started_at = datetime.now(timezone.utc).isoformat()
    database_result = reset_database(database, dry_run=args.dry_run)
    filesystem_result = {
        "workspace": clear_directory(workspace, dry_run=args.dry_run),
        "logs": clear_directory(logs, dry_run=args.dry_run),
        "import_sources": clear_directory(
            imports,
            preserve_top_level=preserve_import,
            dry_run=args.dry_run,
        ),
        "removable_sources": clear_directory(removable, dry_run=args.dry_run),
        "nas_sources": clear_directory(nas_sources, dry_run=args.dry_run),
        "pool_probe": clear_directory(pool_probe, dry_run=args.dry_run),
    }
    if args.keep_archive:
        filesystem_result["archive"] = {
            "path": str(archive_root),
            "kept": True,
            "files": count_files(archive_root),
        }
    else:
        filesystem_result["archive"] = clear_directory(
            archive_root,
            dry_run=args.dry_run,
        )

    result = {
        "schema_version": 1,
        "status": "PASS",
        "mode": "dry-run" if args.dry_run else "reset",
        "started_at": started_at,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "qa_root": str(qa_root),
        "run_root": str(run_root),
        "database": str(database),
        "archive_root": str(archive_root),
        "preserved_import_sources": sorted(preserve_import),
        "keep_archive": bool(args.keep_archive),
        "database_reset": database_result,
        "filesystem_reset": filesystem_result,
        "guarantees": {
            "production_database_touched": False,
            "production_archive_touched": False,
            "schema_versions_preserved": True,
            "evidence_outside_mutable_roots_preserved": True,
            "active_jobs_required_zero": True,
        },
    }

    evidence_dir = run_root / "evidence" / "resets"
    if not args.dry_run:
        evidence_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        evidence_path = evidence_dir / f"reset-{timestamp}.json"
        evidence_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        result["evidence_file"] = str(evidence_path)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ResetError as error:
        print(
            json.dumps(
                {"status": "BLOCKED", "error": str(error)},
                ensure_ascii=False,
                indent=2,
            ),
            file=sys.stderr,
        )
        raise SystemExit(20)
