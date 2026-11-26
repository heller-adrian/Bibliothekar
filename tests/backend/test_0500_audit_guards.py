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
    workflows = Path(__file__).resolve().parents[2] / ".github" / "workflows"
    entry = (workflows / "publish-container.yml").read_text(encoding="utf-8")
    stable = (workflows / "publish-qualified-stable.yml").read_text(encoding="utf-8")
    assert "uses: ./.github/workflows/publish-qualified-stable.yml" in entry
    assert "type=raw,value=latest" not in entry
    assert 'git tag -f' not in stable and ' --force' not in stable
    assert 'test -z "$tag_ref" || test "$tag_ref" = "$RELEASE_SOURCE"' in stable
    assert "docker build" not in stable
    assert stable.index("releases/latest", stable.index("name: Advance latest")) < stable.index("promote_stable_manifest.py latest")


@pytest.fixture
def stable_registry(monkeypatch, tmp_path):
    import io
    from contextlib import contextmanager
    from urllib.error import HTTPError

    from qa.release import promote_stable_manifest as publisher

    source = "1" * 40
    qualified = "sha256:" + "2" * 64
    old = "sha256:" + "3" * 64
    for key, value in {
        "TAG": "v1.1.2", "RELEASE_SOURCE": source, "RELEASE_DIGEST": qualified,
        "CANDIDATE_TAG": "v1.1.2-rc.9", "PREVIOUS_TAG": "v1.1.1", "PREVIOUS_DIGEST": old,
        "RELEASE_EVIDENCE": str(tmp_path),
        "GITHUB_ACTOR": "test-actor", "GH_TOKEN": "unused-test-value",
        "GITHUB_SHA": "4" * 40, "RELEASE_QA_RUN": "1", "QUALIFIED_IMAGE_RUN": "2", "GITHUB_RUN_ID": "3",
    }.items():
        monkeypatch.setenv(key, value)
    registry = {qualified: qualified, f"patch-1.1.2-{source}": qualified, "v1.1.2-rc.9": qualified,
                "v1.1.1": old, "1.1.1": old, "latest": old}
    media_type = "application/vnd.oci.image.index.v1+json"
    writes = []

    def read(ref, _bearer):
        if ref not in registry:
            raise HTTPError("https://ghcr.io", 404, "missing", None,
                            io.BytesIO(b'{"errors":[{"code":"MANIFEST_UNKNOWN"}]}'))
        return registry[ref], media_type, b"unchanged OCI index"

    @contextmanager
    def write(tag, bearer, *, data, media_type, create_only):
        from types import SimpleNamespace
        assert bearer == "pull,push"
        assert data == b"unchanged OCI index" and media_type == "application/vnd.oci.image.index.v1+json"
        assert create_only == (tag != "latest")
        if create_only:
            assert tag not in registry
        writes.append(tag)
        registry[tag] = qualified
        yield SimpleNamespace(status=201, headers={"Docker-Content-Digest": qualified})

    monkeypatch.setattr(publisher, "token", lambda scope, *_: scope)
    monkeypatch.setattr(publisher, "read", read)
    monkeypatch.setattr(publisher, "manifest", write)
    return publisher.main, registry, writes, qualified, old


@pytest.mark.parametrize(("tag", "message"), [
    ("v1.1.2", "Version tag v1.1.2 already has a different digest"),
    ("v1.1.2-rc.9", "release candidate"),
    ("v1.1.1", "previous stable version"),
    ("latest", "stable channel advanced"),
])
def test_stable_preflight_refuses_conflicting_tags(stable_registry, tag, message):
    promote, registry, writes, _, _ = stable_registry
    registry[tag] = "sha256:" + "9" * 64
    with pytest.raises(AssertionError, match=message):
        promote("check")
    assert not writes


def test_stable_refuses_an_advanced_latest_after_preflight(stable_registry):
    promote, registry, writes, _, _ = stable_registry
    promote("check")
    promote("version")
    registry["latest"] = "sha256:" + "8" * 64
    with pytest.raises(AssertionError, match="stable channel advanced"):
        promote("latest")
    assert writes == ["1.1.2", "v1.1.2"]


def test_stable_promotes_the_same_manifest_and_advances_latest_last(stable_registry, tmp_path):
    import json

    promote, registry, writes, qualified, old = stable_registry
    promote("check")
    with pytest.raises(AssertionError, match="Both version tags"):
        promote("latest")
    assert not writes
    promote("version")
    assert writes == ["1.1.2", "v1.1.2"] and registry["latest"] == old
    promote("latest")
    assert writes[-1] == "latest"
    evidence = json.loads((tmp_path / "promotion.json").read_text())
    assert evidence["before"]["latest"] == old
    assert all(evidence["after"][tag] == qualified for tag in ("1.1.2", "v1.1.2", "latest", "v1.1.2-rc.9"))
    assert registry["v1.1.1"] == registry["1.1.1"] == old
    promote("check")
    promote("version")
    promote("latest")
    assert len(writes) == 3


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
