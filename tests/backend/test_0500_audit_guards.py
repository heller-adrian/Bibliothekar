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


def test_stable_release_workflow_never_force_retags(monkeypatch) -> None:
    from urllib.error import HTTPError

    from qa.release import promote_stable_manifest as publisher

    workflows = Path(__file__).resolve().parents[2] / ".github" / "workflows"
    entry = (workflows / "publish-container.yml").read_text(encoding="utf-8")
    stable = (workflows / "publish-qualified-stable.yml").read_text(encoding="utf-8")
    assert "uses: ./.github/workflows/publish-qualified-stable.yml" in entry
    assert "type=raw,value=latest" not in entry
    assert 'git tag -f' not in stable and ' --force' not in stable
    assert 'test -z "$tag_ref" || test "$tag_ref" = "$RELEASE_SOURCE"' in stable

    source = "1" * 40
    qualified = "sha256:" + "2" * 64
    old = "sha256:" + "3" * 64
    for key, value in {
        "TAG": "v1.1.0", "RELEASE_SOURCE": source, "RELEASE_DIGEST": qualified,
        "GITHUB_ACTOR": "test-actor", "GH_TOKEN": "unused-test-value",
    }.items():
        monkeypatch.setenv(key, value)

    def read(ref, _bearer):
        if ref == "1.1.0":
            raise HTTPError("https://ghcr.io", 404, "missing", None, None)
        digest = qualified if ref in (qualified, f"patch-1.1.0-{source}") else old
        return digest, "application/vnd.oci.image.index.v1+json", b"manifest"

    def unexpected_write(*args, **kwargs):
        pytest.fail("Registry must remain unchanged when a version tag already differs")

    monkeypatch.setattr(publisher, "token", lambda *args: "unused-test-token")
    monkeypatch.setattr(publisher, "read", read)
    monkeypatch.setattr(publisher, "manifest", unexpected_write)
    with pytest.raises(AssertionError, match="Version tag v1.1.0 already has a different digest"):
        publisher.main("version")


def test_storage_rename_error_path_restores_confirmed_job_prefixes() -> None:
    # Historical rename/rollback contract is preserved in the QA package.
    # Its replacement must have no filesystem or SQL mutation path at all.
    import ast
    code=(Path(__file__).resolve().parents[2]/"app"/"main.py").read_text()
    tree=ast.parse(code)
    function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=="_set_storage_paths")
    assert len(function.body)==1 and isinstance(function.body[0],ast.Raise)
    assert "410" in ast.unparse(function.body[0])
    assert "path_rollback_errors: list[str] = []" not in code
    assert "renamed_backup_root," not in code


def test_reconciliation_commits_applied_state_with_paths() -> None:
    code = (Path(__file__).resolve().parents[2] / "app" / "workspace_reconcile.py").read_text(
        encoding="utf-8"
    )
    # The first commit must include the applied marker and mutation finish.
    assert code.index("mark_job_mutation_completed(c, job_id)") < code.index(
        "database_finalized = True"
    )
    assert "if database_finalized:\n            raise" in code
