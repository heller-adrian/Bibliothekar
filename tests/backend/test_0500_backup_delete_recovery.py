"""BA-02: durable deletion journal fault/abrupt process restart matrix.

Only synthetic SQLite databases and files inside pytest tmp_path are used.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from app.backup_management import (
    BackupDeletionError,
    _deletion_paths,
    delete_backup,
    recover_backup_deletions,
)
from app.database import database_connection, get_job
from app.workspace_layout import backup_root
from tests.backend.test_0400_import_backup_controls import (
    _completed_backup,
    _foundation,
)


def _seed(tmp_path):
    db, registry, workspace = _foundation(tmp_path)
    file, family_id = _completed_backup(db, workspace)
    return db, registry, backup_root(workspace), file, family_id


def _run_child(db, registry, root, script):
    result = subprocess.run(
        [sys.executable, "-c", script, str(db), str(registry), str(root)],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 42, (result.returncode, result.stdout, result.stderr)


def _journal(job_id, root):
    path, stage = _deletion_paths(root, job_id)
    assert path.is_file()
    return path, stage


def test_0500_staging_crash_before_main_commit_rolls_back(tmp_path):
    db, registry, root, original, _ = _seed(tmp_path)
    script = """
import os, sys
from pathlib import Path
import app.backup_management as m
m._delete_job_row = lambda *_a, **_kw: os._exit(42)
m.delete_backup(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), "IMPORT_0400")
"""
    _run_child(db, registry, root, script)
    journal, stage = _journal("IMPORT_0400", root)
    assert not original.exists()
    assert get_job(db, "IMPORT_0400") is not None
    result = recover_backup_deletions(db, registry, root)
    assert result == {"completed": 0, "rolled_back": 1, "blocked": 0, "errors": []}
    assert original.read_bytes() == b"bibliothekar-0.40.0-backup"
    assert not journal.exists()
    assert not stage.exists()
    assert get_job(db, "IMPORT_0400") is not None
    assert recover_backup_deletions(db, registry, root)["rolled_back"] == 0


def test_0500_after_main_commit_crash_completes_purge(tmp_path):
    db, registry, root, original, _ = _seed(tmp_path)
    script = """
import os, sys
from pathlib import Path
import app.backup_management as m
m._finish_deletion = lambda *_a, **_kw: os._exit(42)
m.delete_backup(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), "IMPORT_0400")
"""
    _run_child(db, registry, root, script)
    journal, stage = _journal("IMPORT_0400", root)
    assert stage.exists()
    assert not original.exists()
    assert get_job(db, "IMPORT_0400") is None
    result = recover_backup_deletions(db, registry, root)
    assert result == {"completed": 1, "rolled_back": 0, "blocked": 0, "errors": []}
    assert not journal.exists()
    assert not stage.exists()
    assert not original.exists()
    assert recover_backup_deletions(db, registry, root)["completed"] == 0


def test_0500_mid_purge_crash_recovery_is_idempotent(tmp_path):
    db, registry, root, original, _ = _seed(tmp_path)
    script = """
import os, sys
from pathlib import Path
import app.backup_management as m
def midway(path, **kwargs):
    files = sorted(p for p in path.rglob("*") if p.is_file())
    assert files
    files[0].unlink()
    os._exit(42)
m.shutil.rmtree = midway
m.delete_backup(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), "IMPORT_0400")
"""
    _run_child(db, registry, root, script)
    journal, stage = _journal("IMPORT_0400", root)
    assert journal.exists()
    assert stage.exists()
    assert get_job(db, "IMPORT_0400") is None
    assert recover_backup_deletions(db, registry, root)["completed"] == 1
    assert not stage.exists()
    assert not journal.exists()
    assert not original.exists()


def test_0500_interrupted_rollback_keeps_journal_and_bytes(tmp_path, monkeypatch):
    import app.backup_management as module

    db, registry, root, original, _ = _seed(tmp_path)
    original_replace = module.os.replace

    def inject(source, destination):
        # Permit the first stage move but refuse the restore.
        if str(source).find(".deleting/") >= 0:
            raise PermissionError("synthetic restore refused")
        return original_replace(source, destination)

    def stop_before_main(*args):
        raise RuntimeError("synthetic SQLite failure")

    with monkeypatch.context() as faults:
        faults.setattr(module.os, "replace", inject)
        faults.setattr(module, "_delete_job_row", stop_before_main)
        with pytest.raises(BackupDeletionError, match="Löschjournal bleibt"):
            delete_backup(db, registry, root, "IMPORT_0400")

    journal, stage = _journal("IMPORT_0400", root)
    assert not original.exists()
    assert (stage / "2026/2026-10-04/20261004_120000_Test.JPG").is_file()
    assert get_job(db, "IMPORT_0400") is not None
    assert recover_backup_deletions(db, registry, root)["rolled_back"] == 1
    assert original.exists()
    assert not journal.exists()


def test_0500_unknown_stage_file_blocks_destructive_purge(tmp_path):
    db, registry, root, original, _ = _seed(tmp_path)
    script = """
import os, sys
from pathlib import Path
import app.backup_management as m
m._finish_deletion = lambda *_a, **_kw: os._exit(42)
m.delete_backup(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), "IMPORT_0400")
"""
    _run_child(db, registry, root, script)
    journal, stage = _journal("IMPORT_0400", root)
    foreign = stage / "foreign.txt"
    foreign.write_text("retain unrelated bytes", encoding="utf-8")
    result = recover_backup_deletions(db, registry, root)
    assert result["blocked"] == 1
    assert foreign.read_text(encoding="utf-8") == "retain unrelated bytes"
    assert journal.exists()
    assert stage.exists()
    foreign.unlink()
    assert recover_backup_deletions(db, registry, root)["completed"] == 1
    assert not journal.exists()


def test_0500_deletion_journal_not_necessary_after_clean_success(tmp_path):
    db, registry, root, original, _ = _seed(tmp_path)
    result = delete_backup(db, registry, root, "IMPORT_0400")
    assert result["deleted_file_count"] == 1
    assert get_job(db, "IMPORT_0400") is None
    assert not original.exists()
    assert recover_backup_deletions(db, registry, root) == {
        "completed": 0, "rolled_back": 0, "blocked": 0, "errors": []
    }



def _with_second_library(tmp_path):
    from app.database import initialize_database
    from app.library_registry import ensure_library_identity, register_library
    from app.global_stock import project_import_job

    db, registry, root, original, _ = _seed(tmp_path)
    second_db = tmp_path / "second" / "kamera.sqlite3"
    second_workspace = tmp_path / "second-workspace"
    second_work_root = second_workspace / "Arbeitsbereich"
    second_archive = tmp_path / "second-archive"
    second_workspace.mkdir()
    second_work_root.mkdir()
    second_archive.mkdir()
    initialize_database(second_db)
    ensure_library_identity(second_db, "secondary")
    register_library(
        registry, library_id="secondary", display_name="Nebenbibliothek",
        database_path=second_db, workspace_root=second_workspace,
        work_root=second_work_root, archive_root=second_archive,
    )
    project_import_job(db, second_db, "IMPORT_0400")
    assert get_job(second_db, "IMPORT_0400") is not None
    return db, registry, root, original, second_db


def test_0500_multilibrary_crash_after_secondary_delete_restores_projection(tmp_path):
    db, registry, root, original, second = _with_second_library(tmp_path)
    script = """
import os, sys
from pathlib import Path
import app.backup_management as m
main = Path(sys.argv[1]).resolve()
actual = m._delete_job_row
def crash_after_secondary(db, job):
    if Path(db).resolve() == main:
        os._exit(42)
    return actual(db, job)
m._delete_job_row = crash_after_secondary
m.delete_backup(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), "IMPORT_0400")
"""
    _run_child(db, registry, root, script)
    assert get_job(db, "IMPORT_0400") is not None
    assert get_job(second, "IMPORT_0400") is None
    assert not original.exists()
    recovered = recover_backup_deletions(db, registry, root)
    assert recovered["rolled_back"] == 1, recovered
    assert original.read_bytes() == b"bibliothekar-0.40.0-backup"
    assert get_job(second, "IMPORT_0400") is not None
    with database_connection(second) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM files WHERE job_id='IMPORT_0400'"
        ).fetchone()[0] == 1
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


def test_0500_unknown_empty_subdirectory_blocks_deletion(tmp_path):
    db, registry, root, original, _ = _seed(tmp_path)
    script = """
import os, sys
from pathlib import Path
import app.backup_management as m
m._finish_deletion = lambda *_a, **_kw: os._exit(42)
m.delete_backup(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), "IMPORT_0400")
"""
    _run_child(db, registry, root, script)
    journal, stage = _journal("IMPORT_0400", root)
    unexpected = stage / "unrelated-empty"
    unexpected.mkdir()
    recovered = recover_backup_deletions(db, registry, root)
    assert recovered["blocked"] == 1
    assert unexpected.exists()
    assert journal.exists()
    unexpected.rmdir()
    assert recover_backup_deletions(db, registry, root)["completed"] == 1


def test_0500_tampered_staged_file_is_never_deleted(tmp_path):
    db, registry, root, original, _ = _seed(tmp_path)
    script = """
import os, sys
from pathlib import Path
import app.backup_management as m
m._finish_deletion = lambda *_a, **_kw: os._exit(42)
m.delete_backup(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), "IMPORT_0400")
"""
    _run_child(db, registry, root, script)
    journal, stage = _journal("IMPORT_0400", root)
    staged = stage / "2026/2026-10-04/20261004_120000_Test.JPG"
    expected = staged.read_bytes()
    staged.write_bytes(b"tampered")
    state = recover_backup_deletions(db, registry, root)
    assert state["blocked"] == 1, state
    assert staged.read_bytes() == b"tampered"
    assert journal.exists()
    staged.write_bytes(expected)
    assert recover_backup_deletions(db, registry, root)["completed"] == 1
