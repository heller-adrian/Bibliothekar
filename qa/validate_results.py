#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

VALID_STATUSES = {"PASS", "FAIL", "BLOCKED", "SKIPPED"}
ARCHIVE_IDS = {f"T{i:03d}" for i in range(80, 89)}
EXPECTED_REVISION = "627c5515e533e167e45354ccaa71f988f104ae08"
EXPECTED_ARCHIVE_ROOT = "/mnt/storage/ki-workspace/hermes/bibliothekar-qa/archive-test-library"
PRODUCTION_ARCHIVE = "/mnt/storage/fotos/Kamerabibliothek"
PRODUCTION_DATABASE_PREFIX = "/mnt/apps/appdata/kamera-automatisierung/database"


def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def matrix_ids(path: Path) -> list[str]:
    ids: list[str] = []
    pattern = re.compile(r"^\|\s*(T\d{3})\s*\|")
    for line in path.read_text(encoding="utf-8").splitlines():
        match = pattern.match(line)
        if match:
            ids.append(match.group(1))
    if not ids:
        fail(f"Keine Test-IDs in {path} gefunden")
    duplicates = sorted({test_id for test_id in ids if ids.count(test_id) > 1})
    if duplicates:
        fail(f"Doppelte Test-IDs in Testmatrix: {', '.join(duplicates)}")
    return ids


def result_map(path: Path) -> dict[str, dict]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict) and "results" in raw:
        raw = raw["results"]

    results: dict[str, dict] = {}
    if isinstance(raw, dict):
        for test_id, value in raw.items():
            if isinstance(value, str):
                record = {"status": value}
            elif isinstance(value, dict):
                record = dict(value)
            else:
                fail(f"Ungültiger Ergebniseintrag für {test_id}")
            record.setdefault("id", test_id)
            results[str(test_id)] = record
    elif isinstance(raw, list):
        for value in raw:
            if not isinstance(value, dict) or not value.get("id"):
                fail("Jeder Listeneintrag in results.json benötigt ein id-Feld")
            test_id = str(value["id"])
            if test_id in results:
                fail(f"Doppeltes Ergebnis für {test_id}")
            results[test_id] = dict(value)
    else:
        fail("results.json muss ein Objekt, eine Liste oder ein Objekt mit results-Liste/-Objekt sein")

    for test_id, record in results.items():
        status = str(record.get("status", "")).upper()
        if status not in VALID_STATUSES:
            fail(f"Ungültiger Status für {test_id}: {record.get('status')!r}")
        record["status"] = status
    return results


def validate_archive_isolation(results: dict[str, dict], isolation_path: Path | None) -> None:
    executed = [
        test_id
        for test_id in sorted(ARCHIVE_IDS)
        if test_id in results and results[test_id]["status"] in {"PASS", "FAIL"}
    ]
    if not executed:
        return
    if isolation_path is None:
        fail(
            "T080-T088 wurden als ausgeführt gemeldet, aber kein isolation.json wurde angegeben. "
            "Archiv-E2E darf nur nach bestandenem Isolations-Gate laufen."
        )
    if not isolation_path.is_file():
        fail(f"isolation.json fehlt: {isolation_path}")

    isolation = json.loads(isolation_path.read_text(encoding="utf-8"))
    if isolation.get("status") != "PASS":
        fail("Archiv-Isolations-Gate ist nicht PASS")
    if isolation.get("product_revision") != EXPECTED_REVISION:
        fail(
            "Archiv-E2E lief nicht gegen die freigegebene Produktrevision: "
            f"{isolation.get('product_revision')!r}"
        )
    if isolation.get("archive_root") != EXPECTED_ARCHIVE_ROOT:
        fail(f"Falscher Archiv-QA-Pfad: {isolation.get('archive_root')!r}")
    if isolation.get("production_archive_mounted") is not False:
        fail("isolation.json bestätigt nicht, dass die reale Kamerabibliothek ungemountet blieb")
    if isolation.get("production_database_mounted") is not False:
        fail("isolation.json bestätigt nicht, dass die Produktiv-DB ungemountet blieb")

    database = str(isolation.get("database", ""))
    if database.startswith(PRODUCTION_DATABASE_PREFIX):
        fail(f"Produktiv-DB wurde als QA-DB verwendet: {database}")
    if str(isolation.get("archive_root", "")) == PRODUCTION_ARCHIVE:
        fail("Reale Kamerabibliothek wurde als QA-Archiv verwendet")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prüft, dass ein Hermes-QA-Bericht den gesamten aktuellen TEST_MATRIX-Umfang abdeckt."
    )
    parser.add_argument("results", type=Path, help="results.json des QA-Laufs")
    parser.add_argument(
        "--matrix",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "TEST_MATRIX.md",
        help="Pfad zu TEST_MATRIX.md",
    )
    parser.add_argument(
        "--archive-isolation",
        type=Path,
        default=None,
        help="isolation.json des isolierten T080-T088-Laufs",
    )
    args = parser.parse_args()

    expected = matrix_ids(args.matrix)
    results = result_map(args.results)
    expected_set = set(expected)
    actual_set = set(results)

    missing = [test_id for test_id in expected if test_id not in actual_set]
    unknown = sorted(actual_set - expected_set)
    if missing:
        fail("QA-Bericht ist unvollständig; fehlende Test-IDs: " + ", ".join(missing))
    if unknown:
        fail("QA-Bericht enthält unbekannte Test-IDs: " + ", ".join(unknown))

    validate_archive_isolation(results, args.archive_isolation)

    counts = {status: 0 for status in sorted(VALID_STATUSES)}
    for test_id in expected:
        counts[results[test_id]["status"]] += 1

    print(
        "PASS: vollständiger QA-Matrixbericht; "
        + ", ".join(f"{status}={counts[status]}" for status in ("PASS", "FAIL", "BLOCKED", "SKIPPED"))
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
