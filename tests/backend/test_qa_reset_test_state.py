from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import subprocess
import sys


SCRIPT = Path(__file__).resolve().parents[2] / "qa" / "reset_test_state.py"


def _make_db(path: Path, *, active_state: str | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    try:
        connection.executescript(
            """
            CREATE TABLE schema_versions (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL
            );
            INSERT INTO schema_versions(version, applied_at)
            VALUES (1, 'now'), (2, 'now');

            CREATE TABLE jobs (
                id TEXT PRIMARY KEY,
                state TEXT NOT NULL,
                stage TEXT,
                operation TEXT,
                created_at TEXT,
                updated_at TEXT
            );

            CREATE TABLE files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT,
                name TEXT
            );
            """
        )
        if active_state is None:
            connection.execute(
                "INSERT INTO jobs(id, state, stage, operation, created_at, updated_at) "
                "VALUES ('DONE', 'completed', 'done', 'folder_import', 'now', 'now')"
            )
        else:
            connection.execute(
                "INSERT INTO jobs(id, state, stage, operation, created_at, updated_at) "
                "VALUES ('ACTIVE', ?, 'running', 'folder_import', 'now', 'now')",
                (active_state,),
            )
        connection.execute("INSERT INTO files(job_id, name) VALUES ('DONE', 'x.jpg')")
        connection.commit()
    finally:
        connection.close()


def _prepare(tmp_path: Path, *, active_state: str | None = None) -> tuple[Path, Path, Path]:
    qa_root = tmp_path / "qa-root"
    run_root = qa_root / "runs" / "RUN-1"
    archive_root = qa_root / "archive-test-library"

    _make_db(run_root / "database" / "kamera.sqlite3", active_state=active_state)

    for relative in (
        "workspace/old/work.jpg",
        "logs/backups/old/status.json",
        "import-sources/DEEPTEST_SD_02/DCIM/base.jpg",
        "import-sources/OLD_MUTABLE/old.jpg",
        "removable-sources/QA_SD_OLD/file.jpg",
        "nas-sources/old/file.jpg",
        "pool-probe/old.tmp",
        "evidence/existing.json",
        "config/settings.json",
    ):
        path = run_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture", encoding="utf-8")

    archive_file = archive_root / "2026" / "old.jpg"
    archive_file.parent.mkdir(parents=True, exist_ok=True)
    archive_file.write_text("archive", encoding="utf-8")
    return qa_root, run_root, archive_root


def _run(qa_root: Path, run_root: Path, archive_root: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--qa-root",
            str(qa_root),
            "--run-root",
            str(run_root),
            "--archive-root",
            str(archive_root),
            *extra,
        ],
        text=True,
        capture_output=True,
        check=False,
    )


def test_clean_slate_clears_mutable_state_and_preserves_evidence(tmp_path: Path) -> None:
    qa_root, run_root, archive_root = _prepare(tmp_path)

    result = _run(qa_root, run_root, archive_root)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "PASS"

    connection = sqlite3.connect(run_root / "database" / "kamera.sqlite3")
    try:
        assert connection.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM files").fetchone()[0] == 0
        assert [row[0] for row in connection.execute(
            "SELECT version FROM schema_versions ORDER BY version"
        )] == [1, 2]
    finally:
        connection.close()

    assert not any((run_root / "workspace").iterdir())
    assert not any((run_root / "logs").iterdir())
    assert not any((run_root / "removable-sources").iterdir())
    assert not any((run_root / "nas-sources").iterdir())
    assert not any((run_root / "pool-probe").iterdir())
    assert not any(archive_root.iterdir())

    assert (run_root / "import-sources" / "DEEPTEST_SD_02" / "DCIM" / "base.jpg").is_file()
    assert not (run_root / "import-sources" / "OLD_MUTABLE").exists()
    assert (run_root / "evidence" / "existing.json").is_file()
    assert (run_root / "config" / "settings.json").is_file()
    reset_evidence = list((run_root / "evidence" / "resets").glob("reset-*.json"))
    assert len(reset_evidence) == 1


def test_active_job_blocks_without_changes(tmp_path: Path) -> None:
    qa_root, run_root, archive_root = _prepare(tmp_path, active_state="copying")
    result = _run(qa_root, run_root, archive_root)
    assert result.returncode == 20
    payload = json.loads(result.stderr)
    assert payload["status"] == "BLOCKED"
    assert "nicht-terminale QA-Jobs" in payload["error"]

    connection = sqlite3.connect(run_root / "database" / "kamera.sqlite3")
    try:
        assert connection.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM files").fetchone()[0] == 1
    finally:
        connection.close()
    assert (run_root / "workspace" / "old" / "work.jpg").is_file()
    assert (archive_root / "2026" / "old.jpg").is_file()


def test_dry_run_does_not_modify_state(tmp_path: Path) -> None:
    qa_root, run_root, archive_root = _prepare(tmp_path)
    result = _run(qa_root, run_root, archive_root, "--dry-run")
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["mode"] == "dry-run"
    assert (run_root / "workspace" / "old" / "work.jpg").is_file()
    assert (run_root / "removable-sources" / "QA_SD_OLD" / "file.jpg").is_file()
    assert (archive_root / "2026" / "old.jpg").is_file()
    assert not (run_root / "evidence" / "resets").exists()


def test_keep_archive_preserves_archive_only(tmp_path: Path) -> None:
    qa_root, run_root, archive_root = _prepare(tmp_path)
    result = _run(qa_root, run_root, archive_root, "--keep-archive")
    assert result.returncode == 0, result.stderr
    assert (archive_root / "2026" / "old.jpg").is_file()
    assert not any((run_root / "workspace").iterdir())


def test_run_root_outside_runs_tree_is_blocked(tmp_path: Path) -> None:
    qa_root, _, archive_root = _prepare(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    result = _run(qa_root, outside, archive_root)
    assert result.returncode == 20
    payload = json.loads(result.stderr)
    assert "ausserhalb des erlaubten Bereichs" in payload["error"]
