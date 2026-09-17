#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

ALLOWED_SNAPSHOT_SCHEMA = "bibliothekar.qa.evidence.snapshot.v1"


def load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != ALLOWED_SNAPSHOT_SCHEMA:
        raise SystemExit(f"BLOCKED: unsupported snapshot schema in {path}")
    return data


def numeric_delta(before: dict[str, Any], after: dict[str, Any]) -> dict[str, int]:
    keys = sorted(set(before) | set(after))
    out: dict[str, int] = {}
    for key in keys:
        a = before.get(key, 0)
        b = after.get(key, 0)
        if isinstance(a, int) and isinstance(b, int):
            out[key] = b - a
    return out


def file_index(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    fixture = snapshot.get("fixture") or {}
    files = fixture.get("files") or []
    return {str(item["relative_path"]): item for item in files}


def fixture_delta(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    a = file_index(before)
    b = file_index(after)
    added = sorted(set(b) - set(a))
    removed = sorted(set(a) - set(b))
    changed = sorted(
        path for path in set(a) & set(b)
        if a[path].get("sha256") != b[path].get("sha256") or a[path].get("size_bytes") != b[path].get("size_bytes")
    )
    return {
        "added": [b[path] for path in added],
        "removed": [a[path] for path in removed],
        "changed": [
            {"relative_path": path, "before": a[path], "after": b[path]}
            for path in changed
        ],
    }


def main() -> int:
    p = argparse.ArgumentParser(description="Build deterministic delta from two QA evidence snapshots")
    p.add_argument("--before", required=True)
    p.add_argument("--after", required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args()

    before_path = Path(args.before)
    after_path = Path(args.after)
    output = Path(args.output)
    before = load(before_path)
    after = load(after_path)

    if before.get("test_id") != after.get("test_id"):
        raise SystemExit("BLOCKED: test_id mismatch")
    if before.get("phase") != after.get("phase"):
        raise SystemExit("BLOCKED: phase mismatch")

    before_db = before.get("database") or {}
    after_db = after.get("database") or {}
    payload = {
        "schema": "bibliothekar.qa.evidence.delta.v1",
        "test_id": before.get("test_id"),
        "phase": before.get("phase"),
        "executor": after.get("executor") or before.get("executor") or {},
        "database": {
            "table_count_delta": numeric_delta(
                before_db.get("table_counts") or {},
                after_db.get("table_counts") or {},
            ),
            "jobs_by_state_delta": numeric_delta(
                before_db.get("jobs_by_state") or {},
                after_db.get("jobs_by_state") or {},
            ),
            "jobs_by_kind_delta": numeric_delta(
                before_db.get("jobs_by_kind") or {},
                after_db.get("jobs_by_kind") or {},
            ),
            "integrity_before": before_db.get("integrity_check") or [],
            "integrity_after": after_db.get("integrity_check") or [],
            "schema_versions_equal": before_db.get("schema_versions") == after_db.get("schema_versions"),
        },
        "fixture": fixture_delta(before, after),
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    tmp = output.with_suffix(output.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, output)
    print(json.dumps({"status": "PASS", "output": str(output), "test_id": payload["test_id"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
