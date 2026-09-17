from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = ROOT / "qa" / "evidence_snapshot.py"
DELTA = ROOT / "qa" / "evidence_delta.py"
EXPORT = ROOT / "qa" / "build_verified_export.py"


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def make_db(path: Path, *, files: int = 0, jobs: list[tuple[str, str]] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        conn.executescript(
            """
            CREATE TABLE schema_versions(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);
            INSERT INTO schema_versions(version, applied_at) VALUES (1, 'x'), (2, 'x');
            CREATE TABLE files(id INTEGER PRIMARY KEY);
            CREATE TABLE jobs(id TEXT PRIMARY KEY, kind TEXT NOT NULL, state TEXT NOT NULL);
            CREATE TABLE imported_source_files(id INTEGER PRIMARY KEY);
            """
        )
        conn.executemany("INSERT INTO files(id) VALUES (?)", [(i + 1,) for i in range(files)])
        if jobs:
            conn.executemany("INSERT INTO jobs(id, kind, state) VALUES (?, ?, ?)", [(str(i), kind, state) for i, (kind, state) in enumerate(jobs)])
        conn.commit()
    finally:
        conn.close()


def snapshot(qa_root: Path, db: Path, fixture: Path, out: Path, test_id: str = "T004") -> dict:
    proc = run(
        str(SNAPSHOT),
        "--qa-root", str(qa_root),
        "--database", str(db),
        "--fixture-root", str(fixture),
        "--test-id", test_id,
        "--phase", "A",
        "--executor-task-id", "t_exec",
        "--executor-run-id", "32",
        "--output", str(out),
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    return json.loads(out.read_text())


def test_snapshot_and_delta_are_deterministic_and_read_only(tmp_path: Path) -> None:
    qa_root = tmp_path / "qa"
    db = qa_root / "run" / "database" / "kamera.sqlite3"
    fixture = qa_root / "run" / "removable-sources" / "QA_SD_T004"
    fixture.mkdir(parents=True)
    (fixture / "A.JPG").write_bytes(b"aaa")
    make_db(db, files=1, jobs=[("folder_import", "completed")])

    before_path = qa_root / "evidence" / "before.json"
    before = snapshot(qa_root, db, fixture, before_path)
    assert before["database"]["table_counts"]["files"] == 1
    assert before["database"]["integrity_check"] == ["ok"]
    assert before["fixture"]["file_count"] == 1

    (fixture / "B.JPG").write_bytes(b"bbb")
    conn = sqlite3.connect(db)
    try:
        conn.execute("INSERT INTO files(id) VALUES (2)")
        conn.execute("INSERT INTO imported_source_files(id) VALUES (1)")
        conn.commit()
    finally:
        conn.close()

    after_path = qa_root / "evidence" / "after.json"
    snapshot(qa_root, db, fixture, after_path)
    delta_path = qa_root / "evidence" / "delta.json"
    proc = run(str(DELTA), "--before", str(before_path), "--after", str(after_path), "--output", str(delta_path))
    assert proc.returncode == 0, proc.stderr + proc.stdout
    delta = json.loads(delta_path.read_text())
    assert delta["database"]["table_count_delta"]["files"] == 1
    assert delta["database"]["table_count_delta"]["imported_source_files"] == 1
    assert [x["relative_path"] for x in delta["fixture"]["added"]] == ["B.JPG"]


def test_verified_export_requires_completed_matching_thinker_review(tmp_path: Path) -> None:
    evidence = tmp_path / "delta.json"
    evidence.write_text(json.dumps({
        "schema": "bibliothekar.qa.evidence.delta.v1",
        "test_id": "T004",
        "phase": "A",
        "executor": {"task_id": "t_exec", "run_id": "32"},
        "database": {
            "table_count_delta": {"files": 3},
            "jobs_by_state_delta": {"completed": 1},
            "jobs_by_kind_delta": {"folder_import": 1},
            "integrity_before": ["ok"],
            "integrity_after": ["ok"],
            "schema_versions_equal": True,
        },
        "fixture": {"added": [], "removed": [], "changed": []},
    }))

    review = tmp_path / "review.json"
    review.write_text(json.dumps({
        "task_id": "t_review",
        "run_id": "33",
        "profile": "qa-thinker",
        "mode": "REVIEW",
        "completed": True,
        "verdict": "ACCEPT_PASS",
        "reason": "Contract satisfied by deterministic evidence.",
        "test_id": "T004",
        "executor_task_id": "t_exec",
        "executor_run_id": "32",
    }))
    out = tmp_path / "verified.json"
    proc = run(
        str(EXPORT),
        "--evidence", str(evidence),
        "--review", str(review),
        "--product-commit", "627c5515e533e167e45354ccaa71f988f104ae08",
        "--qa-commit", "abc123",
        "--output", str(out),
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    data = json.loads(out.read_text())
    assert data["review"]["verdict"] == "ACCEPT_PASS"
    assert data["evidence"]["database"]["table_count_delta"]["files"] == 3

    bad_review = json.loads(review.read_text())
    bad_review["completed"] = False
    review.write_text(json.dumps(bad_review))
    proc = run(
        str(EXPORT),
        "--evidence", str(evidence),
        "--review", str(review),
        "--product-commit", "p",
        "--qa-commit", "q",
        "--output", str(out),
    )
    assert proc.returncode != 0
    assert "review is not completed" in (proc.stderr + proc.stdout)


def test_verified_export_rejects_nas_paths_or_secret_like_text(tmp_path: Path) -> None:
    evidence = tmp_path / "delta.json"
    evidence.write_text(json.dumps({
        "schema": "bibliothekar.qa.evidence.delta.v1",
        "test_id": "T004",
        "phase": "A",
        "executor": {"task_id": "t_exec", "run_id": "32"},
        "database": {},
        "fixture": {"added": [], "removed": [], "changed": []},
    }))
    review = tmp_path / "review.json"
    review.write_text(json.dumps({
        "task_id": "t_review",
        "run_id": "33",
        "profile": "qa-thinker",
        "mode": "REVIEW",
        "completed": True,
        "verdict": "RETEST_REQUIRED",
        "reason": "See /mnt/storage/private/path",
        "test_id": "T004",
        "executor_task_id": "t_exec",
        "executor_run_id": "32",
    }))
    out = tmp_path / "verified.json"
    proc = run(
        str(EXPORT),
        "--evidence", str(evidence),
        "--review", str(review),
        "--product-commit", "p",
        "--qa-commit", "q",
        "--output", str(out),
    )
    assert proc.returncode != 0
    assert "forbidden" in (proc.stderr + proc.stdout).lower()
