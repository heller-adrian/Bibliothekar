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
