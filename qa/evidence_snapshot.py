#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_QA_ROOT = Path("/mnt/storage/ki-workspace/hermes/bibliothekar-qa")
FORBIDDEN_PREFIXES = (
    Path("/mnt/storage/fotos/Kamerabibliothek"),
    Path("/mnt/apps/appdata/kamera-automatisierung/database"),
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def is_within(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def require_qa_path(path: Path, qa_root: Path) -> Path:
    resolved = path.resolve()
    if not is_within(resolved, qa_root):
        raise SystemExit(f"BLOCKED: path outside QA root: {resolved}")
    for forbidden in FORBIDDEN_PREFIXES:
        if is_within(resolved, forbidden) or is_within(forbidden, resolved):
            raise SystemExit(f"BLOCKED: path intersects forbidden production path: {resolved}")
    return resolved


def table_names(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    return [str(row[0]) for row in rows]


def scalar(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> Any:
    row = conn.execute(sql, params).fetchone()
    return None if row is None else row[0]


def collect_database(db_path: Path) -> dict[str, Any]:
    uri = f"file:{db_path.as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        tables = table_names(conn)
        counts: dict[str, int] = {}
        for table in tables:
            safe = table.replace('"', '""')
            counts[table] = int(scalar(conn, f'SELECT COUNT(*) FROM "{safe}"') or 0)

        integrity = [str(row[0]) for row in conn.execute("PRAGMA integrity_check").fetchall()]

        schema_versions: list[int] = []
        if "schema_versions" in tables:
            schema_versions = [int(row[0]) for row in conn.execute("SELECT version FROM schema_versions ORDER BY version")]

        jobs_by_state: dict[str, int] = {}
        jobs_by_kind: dict[str, int] = {}
        if "jobs" in tables:
            jobs_by_state = {
                str(state): int(count)
                for state, count in conn.execute("SELECT state, COUNT(*) FROM jobs GROUP BY state ORDER BY state")
            }
            jobs_by_kind = {
                str(kind): int(count)
                for kind, count in conn.execute("SELECT kind, COUNT(*) FROM jobs GROUP BY kind ORDER BY kind")
            }

        return {
            "sha256": sha256_file(db_path),
            "integrity_check": integrity,
            "schema_versions": schema_versions,
            "table_counts": counts,
            "jobs_by_state": jobs_by_state,
            "jobs_by_kind": jobs_by_kind,
        }
    finally:
        conn.close()


def collect_files(root: Path) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    if root.exists():
        for path in sorted((p for p in root.rglob("*") if p.is_file()), key=lambda p: p.as_posix()):
            rel = path.relative_to(root).as_posix()
            st = path.stat()
            files.append(
                {
                    "relative_path": rel,
                    "size_bytes": int(st.st_size),
                    "sha256": sha256_file(path),
                }
            )
    return {
        "file_count": len(files),
        "total_size_bytes": sum(item["size_bytes"] for item in files),
        "files": files,
    }


def main() -> int:
    p = argparse.ArgumentParser(description="Deterministic read-only QA evidence snapshot")
    p.add_argument("--database", required=True)
    p.add_argument("--test-id", required=True)
    p.add_argument("--phase", required=True)
    p.add_argument("--executor-task-id")
    p.add_argument("--executor-run-id")
    p.add_argument("--fixture-root")
    p.add_argument("--qa-root", default=str(DEFAULT_QA_ROOT))
    p.add_argument("--output", required=True)
    args = p.parse_args()

    qa_root = Path(args.qa_root).resolve()
    db_path = require_qa_path(Path(args.database), qa_root)
    output = require_qa_path(Path(args.output), qa_root)
    fixture_root = require_qa_path(Path(args.fixture_root), qa_root) if args.fixture_root else None

    if not db_path.is_file():
        raise SystemExit(f"BLOCKED: QA database not found: {db_path}")
    if fixture_root and not fixture_root.exists():
        raise SystemExit(f"BLOCKED: fixture root not found: {fixture_root}")

    payload: dict[str, Any] = {
        "schema": "bibliothekar.qa.evidence.snapshot.v1",
        "generated_at": utc_now(),
        "test_id": args.test_id,
        "phase": args.phase,
        "executor": {
            "task_id": args.executor_task_id,
            "run_id": args.executor_run_id,
        },
        "database": collect_database(db_path),
    }
    if fixture_root:
        payload["fixture"] = collect_files(fixture_root)

    output.parent.mkdir(parents=True, exist_ok=True)
    tmp = output.with_suffix(output.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, output)
    print(json.dumps({"status": "PASS", "output": str(output), "test_id": args.test_id}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
