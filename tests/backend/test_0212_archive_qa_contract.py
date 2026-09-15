from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from qa.validate_results import validate_archive_filesystem_evidence


VERIFIER = Path(__file__).resolve().parents[2] / "qa" / "archive_e2e" / "verify_filesystem_state.py"


def _write_manifest(path: Path, root: Path, files: list[dict]) -> None:
    path.write_text(
        json.dumps(
            {
                "archive_root": str(root),
                "files": files,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def test_archive_filesystem_verifier_accepts_exact_family_manifest(tmp_path: Path) -> None:
    root = tmp_path / "archive-test-library"
    target = root / "2026" / "07.15 - Beispiel" / "08-00 - 12-00 - Vormittag" / "Alle"
    target.mkdir(parents=True)
    raf = target / "20260715_091500_Kamera.RAF"
    jpg = target / "20260715_091500_Kamera.JPG"
    raf.write_bytes(b"raf-family-member")
    jpg.write_bytes(b"jpg-family-member")

    import hashlib

    manifest = tmp_path / "expected.json"
    evidence = tmp_path / "evidence.json"
    _write_manifest(
        manifest,
        root,
        [
            {
                "path": raf.relative_to(root).as_posix(),
                "family_id": "42",
                "size_bytes": raf.stat().st_size,
                "sha256": hashlib.sha256(raf.read_bytes()).hexdigest(),
            },
            {
                "path": jpg.relative_to(root).as_posix(),
                "family_id": "42",
                "size_bytes": jpg.stat().st_size,
                "sha256": hashlib.sha256(jpg.read_bytes()).hexdigest(),
            },
        ],
    )

    result = subprocess.run(
        [
            sys.executable,
            str(VERIFIER),
            str(manifest),
            "--archive-root",
            str(root),
            "--evidence",
            str(evidence),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    proof = json.loads(evidence.read_text(encoding="utf-8"))
    assert proof["status"] == "PASS"
    assert proof["expected_file_count"] == 2
    assert proof["actual_file_count"] == 2
    assert proof["split_families"] == {}
    assert proof["unexpected_files"] == []
    assert proof["duplicate_sha256"] == {}


def test_archive_filesystem_verifier_rejects_leftover_duplicate(tmp_path: Path) -> None:
    root = tmp_path / "archive-test-library"
    target = root / "2026" / "07.15 - Beispiel" / "Alle"
    stale = root / "2026" / "07.15 - Alt" / "Alle"
    target.mkdir(parents=True)
    stale.mkdir(parents=True)
    expected_file = target / "20260715_091500_Kamera.JPG"
    leftover = stale / "20260715_091500_Kamera.JPG"
    expected_file.write_bytes(b"same-content")
    leftover.write_bytes(b"same-content")

    manifest = tmp_path / "expected.json"
    evidence = tmp_path / "evidence.json"
    _write_manifest(
        manifest,
        root,
        [
            {
                "path": expected_file.relative_to(root).as_posix(),
                "family_id": "7",
                "size_bytes": expected_file.stat().st_size,
            }
        ],
    )

    result = subprocess.run(
        [
            sys.executable,
            str(VERIFIER),
            str(manifest),
            "--archive-root",
            str(root),
            "--evidence",
            str(evidence),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    proof = json.loads(evidence.read_text(encoding="utf-8"))
    assert proof["status"] == "FAIL"
    assert leftover.relative_to(root).as_posix() in proof["unexpected_files"]
    assert proof["unexpected_directories"]
    assert proof["duplicate_sha256"]


def test_archive_pass_requires_real_filesystem_checks(tmp_path: Path) -> None:
    results_path = tmp_path / "results.json"
    results_path.write_text("{}", encoding="utf-8")

    with pytest.raises(SystemExit):
        validate_archive_filesystem_evidence(
            {"T080": {"status": "PASS"}},
            results_path,
        )
