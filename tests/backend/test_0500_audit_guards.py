"""Regression guards for the 0.50.0 audit hardening.

All database tests use disposable SQLite files; no NAS datasets are touched.
"""
from pathlib import Path
import sqlite3

import pytest

from app.database import DatabaseError, initialize_database


def test_future_schema_version_is_rejected_before_migrations(tmp_path: Path) -> None:
    database = tmp_path / "future.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE schema_versions(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
        )
        connection.execute(
            "INSERT INTO schema_versions VALUES (999, '2026-10-10')"
        )
    with pytest.raises(DatabaseError, match="nicht unterstützte"):
        initialize_database(database)
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT version FROM schema_versions").fetchall() == [(999,)]
        assert connection.execute(
            "SELECT name FROM sqlite_master WHERE name='jobs'"
        ).fetchone() is None


@pytest.mark.parametrize("filename", ["events_ui.py", "workspace_ui.py"])
def test_global_task_panel_escapes_untrusted_text(filename: str) -> None:
    code = (Path(__file__).resolve().parents[2] / "app" / filename).read_text(
        encoding="utf-8"
    )
    assert "escapeHtml(String(task.title||'Aufgabe'))" in code
    assert "escapeHtml(String(task.detail||''))" in code
    assert "escapeHtml(safeHref)" in code
    assert "${String(task.detail||'')}" not in code


def test_stable_release_workflow_never_force_retags() -> None:
    code = (Path(__file__).resolve().parents[2] / ".github" / "workflows" / "publish-container.yml").read_text(
        encoding="utf-8"
    )
    assert 'git tag -f' not in code
    assert 'refs/tags/${TAG}" --force' not in code
    assert 'Reject an existing stable version tag' in code


def test_storage_rename_error_path_restores_confirmed_job_prefixes() -> None:
    code = (Path(__file__).resolve().parents[2] / "app" / "main.py").read_text(
        encoding="utf-8"
    )
    assert "path_rollback_errors: list[str] = []" in code
    assert "renamed_backup_root," in code
    assert "original_backup_root," in code
    assert "Datenbank-Pfadrückbau nicht vollständig" in code


def test_reconciliation_commits_applied_state_with_paths() -> None:
    code = (Path(__file__).resolve().parents[2] / "app" / "workspace_reconcile.py").read_text(
        encoding="utf-8"
    )
    # The first commit must include the applied marker and mutation finish.
    assert code.index("mark_job_mutation_completed(c, job_id)") < code.index(
        "database_finalized = True"
    )
    assert "if database_finalized:\n            raise" in code
