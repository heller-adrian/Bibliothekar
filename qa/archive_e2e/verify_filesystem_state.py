#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections import defaultdict
from pathlib import Path, PurePosixPath
from typing import Any

DEFAULT_ARCHIVE_ROOT = Path("/mnt/storage/ki-workspace/hermes/bibliothekar-qa/archive-test-library")
IGNORED_EXACT_NAMES = {"event.json", ".DS_Store"}
IGNORED_PREFIXES = ("._",)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_relative(value: str) -> str:
    path = PurePosixPath(str(value).replace("\\", "/"))
    if path.is_absolute() or ".." in path.parts or str(path) in {"", "."}:
        raise ValueError(f"Ungültiger relativer Archivpfad: {value!r}")
    return str(path)


def is_ignored_metadata(path: Path) -> bool:
    return path.name in IGNORED_EXACT_NAMES or path.name.startswith(IGNORED_PREFIXES)


def expected_directories(files: list[dict[str, Any]], explicit: list[str]) -> set[str]:
    result = {safe_relative(value) for value in explicit}
    for record in files:
        rel = PurePosixPath(safe_relative(record["path"]))
        parent = rel.parent
        while str(parent) not in {"", "."}:
            result.add(str(parent))
            parent = parent.parent
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Vergleicht den tatsächlichen Zustand der isolierten QA-Archivbibliothek exakt "
            "mit einem erwarteten IST→SOLL-Dateisystemmanifest."
        )
    )
    parser.add_argument("manifest", type=Path, help="JSON-Manifest des erwarteten SOLL-Zustands")
    parser.add_argument(
        "--archive-root",
        type=Path,
        default=DEFAULT_ARCHIVE_ROOT,
        help="Beschreibbare QA-Archivwurzel",
    )
    parser.add_argument(
        "--evidence",
        type=Path,
        required=True,
        help="JSON-Datei für den maschinenlesbaren Dateisystem-Nachweis",
    )
    args = parser.parse_args()

    root = args.archive_root.resolve()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    manifest_root = manifest.get("archive_root")
    if manifest_root and Path(manifest_root).resolve() != root:
        raise SystemExit(f"FAIL: Manifest gilt für andere Archivwurzel: {manifest_root}")
    if not root.is_dir():
        raise SystemExit(f"FAIL: QA-Archivwurzel fehlt: {root}")

    expected_files = list(manifest.get("files") or [])
    if not isinstance(expected_files, list):
        raise SystemExit("FAIL: Manifestfeld 'files' muss eine Liste sein")

    expected_by_path: dict[str, dict[str, Any]] = {}
    family_paths: dict[str, list[str]] = defaultdict(list)
    manifest_errors: list[str] = []
    for record in expected_files:
        if not isinstance(record, dict) or not record.get("path"):
            manifest_errors.append("Jeder erwartete Dateieintrag benötigt 'path'.")
            continue
        try:
            rel = safe_relative(str(record["path"]))
        except ValueError as exc:
            manifest_errors.append(str(exc))
            continue
        if rel in expected_by_path:
            manifest_errors.append(f"Doppelter SOLL-Pfad im Manifest: {rel}")
            continue
        expected_by_path[rel] = record
        family_id = str(record.get("family_id") or record.get("family_key") or "").strip()
        if not family_id:
            manifest_errors.append(f"Datei {rel} hat keine family_id/family_key.")
        else:
            family_paths[family_id].append(rel)

    split_families: dict[str, list[str]] = {}
    for family_id, paths in family_paths.items():
        parents = sorted({str(PurePosixPath(path).parent) for path in paths})
        if len(parents) != 1:
            split_families[family_id] = parents

    explicit_dirs = list(manifest.get("directories") or [])
    expected_dirs = expected_directories(expected_files, explicit_dirs)

    actual_files: dict[str, dict[str, Any]] = {}
    actual_dirs: set[str] = set()
    ignored_metadata: list[str] = []
    symlinks: list[str] = []

    for current, dirs, files in os.walk(root, followlinks=False):
        current_path = Path(current)
        for dirname in list(dirs):
            full = current_path / dirname
            rel = full.relative_to(root).as_posix()
            if full.is_symlink():
                symlinks.append(rel)
                dirs.remove(dirname)
                continue
            actual_dirs.add(rel)
        for filename in files:
            full = current_path / filename
            rel = full.relative_to(root).as_posix()
            if full.is_symlink():
                symlinks.append(rel)
                continue
            if is_ignored_metadata(full):
                ignored_metadata.append(rel)
                continue
            stat = full.stat()
            actual_files[rel] = {
                "size_bytes": stat.st_size,
                "sha256": sha256_file(full),
            }

    expected_paths = set(expected_by_path)
    actual_paths = set(actual_files)
    missing_files = sorted(expected_paths - actual_paths)
    unexpected_files = sorted(actual_paths - expected_paths)
    missing_dirs = sorted(expected_dirs - actual_dirs)
    unexpected_dirs = sorted(actual_dirs - expected_dirs)

    size_mismatches: list[dict[str, Any]] = []
    hash_mismatches: list[dict[str, Any]] = []
    for rel in sorted(expected_paths & actual_paths):
        expected = expected_by_path[rel]
        actual = actual_files[rel]
        if expected.get("size_bytes") is not None and int(expected["size_bytes"]) != int(actual["size_bytes"]):
            size_mismatches.append(
                {"path": rel, "expected": int(expected["size_bytes"]), "actual": int(actual["size_bytes"])}
            )
        expected_sha = str(expected.get("sha256") or "").strip().lower()
        if expected_sha and expected_sha != str(actual["sha256"]).lower():
            hash_mismatches.append(
                {"path": rel, "expected": expected_sha, "actual": actual["sha256"]}
            )

    hashes: dict[str, list[str]] = defaultdict(list)
    for rel, record in actual_files.items():
        hashes[str(record["sha256"])].append(rel)
    allowed_duplicate_hashes = {str(value).lower() for value in manifest.get("allow_duplicate_sha256", [])}
    duplicate_sha256 = {
        digest: sorted(paths)
        for digest, paths in sorted(hashes.items())
        if len(paths) > 1 and digest.lower() not in allowed_duplicate_hashes
    }

    errors: list[str] = []
    errors.extend(manifest_errors)
    if missing_files:
        errors.append(f"{len(missing_files)} erwartete Datei(en) fehlen")
    if unexpected_files:
        errors.append(f"{len(unexpected_files)} unerwartete/verbliebene Datei(en) vorhanden")
    if missing_dirs:
        errors.append(f"{len(missing_dirs)} erwartete Ordner fehlen")
    if unexpected_dirs:
        errors.append(f"{len(unexpected_dirs)} unerwartete/verbliebene Ordner vorhanden")
    if size_mismatches:
        errors.append(f"{len(size_mismatches)} Größenabweichung(en)")
    if hash_mismatches:
        errors.append(f"{len(hash_mismatches)} SHA-256-Abweichung(en)")
    if duplicate_sha256:
        errors.append(f"{len(duplicate_sha256)} duplizierte Dateiinhalte an mehreren Pfaden")
    if split_families:
        errors.append(f"{len(split_families)} Dateifamilie(n) auf mehrere Zielordner aufgeteilt")
    if symlinks:
        errors.append(f"{len(symlinks)} Symlink(s) im QA-Archiv")

    evidence = {
        "status": "PASS" if not errors else "FAIL",
        "archive_root": str(root),
        "manifest": str(args.manifest.resolve()),
        "expected_file_count": len(expected_paths),
        "actual_file_count": len(actual_paths),
        "expected_directory_count": len(expected_dirs),
        "actual_directory_count": len(actual_dirs),
        "missing_files": missing_files,
        "unexpected_files": unexpected_files,
        "missing_directories": missing_dirs,
        "unexpected_directories": unexpected_dirs,
        "size_mismatches": size_mismatches,
        "sha256_mismatches": hash_mismatches,
        "duplicate_sha256": duplicate_sha256,
        "split_families": split_families,
        "symlinks": sorted(symlinks),
        "ignored_metadata": sorted(ignored_metadata),
        "errors": errors,
        "actual_files": actual_files,
    }
    args.evidence.parent.mkdir(parents=True, exist_ok=True)
    args.evidence.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if errors:
        print("FAIL: Dateisystemzustand weicht vom erwarteten IST→SOLL-Zustand ab", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(
        "PASS: QA-Archiv entspricht exakt dem erwarteten IST→SOLL-Zustand; "
        f"Dateien={len(actual_paths)}, Ordner={len(actual_dirs)}, Familien={len(family_paths)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
