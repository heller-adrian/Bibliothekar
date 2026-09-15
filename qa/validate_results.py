#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

VALID_STATUSES = {"PASS", "FAIL", "BLOCKED", "SKIPPED"}
ARCHIVE_IDS = {f"T{i:03d}" for i in range(80, 89)}
ARCHIVE_PLAN_IDS = {f"T{i:03d}" for i in range(82, 88)}
EXPECTED_REVISION = "627c5515e533e167e45354ccaa71f988f104ae08"
EXPECTED_ARCHIVE_ROOT = "/mnt/storage/ki-workspace/hermes/bibliothekar-qa/archive-test-library"
PRODUCTION_ARCHIVE = "/mnt/storage/fotos/Kamerabibliothek"
PRODUCTION_DATABASE_PREFIX = "/mnt/apps/appdata/kamera-automatisierung/database"
EVIDENCE_EMPTY_FIELDS = (
    "missing_files",
    "unexpected_files",
    "missing_directories",
    "unexpected_directories",
    "size_mismatches",
    "sha256_mismatches",
    "duplicate_sha256",
    "split_families",
    "symlinks",
    "errors",
)


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


def resolve_evidence_path(run_root: Path, value: object, label: str, test_id: str) -> Path:
    text = str(value or "").strip()
    if not text:
        fail(f"{test_id}: filesystem_check benötigt {label}")
    path = Path(text)
    if not path.is_absolute():
        path = run_root / path
    path = path.resolve()
    try:
        path.relative_to(run_root.resolve())
    except ValueError:
        fail(f"{test_id}: {label} liegt außerhalb des QA-Laufordners: {path}")
    if not path.is_file():
        fail(f"{test_id}: {label} fehlt: {path}")
    return path


def validate_one_filesystem_check(test_id: str, check: dict, run_root: Path, require_plan: bool) -> None:
    step = str(check.get("step") or "").strip()
    if not step:
        fail(f"{test_id}: filesystem_check ohne step")
    status = str(check.get("status") or "").upper()
    if status not in {"PASS", "FAIL"}:
        fail(f"{test_id}/{step}: filesystem_check braucht PASS oder FAIL")

    expected_path = resolve_evidence_path(run_root, check.get("expected"), "expected", test_id)
    evidence_path = resolve_evidence_path(run_root, check.get("evidence"), "evidence", test_id)
    if require_plan:
        resolve_evidence_path(run_root, check.get("plan"), "plan", test_id)

    expected = json.loads(expected_path.read_text(encoding="utf-8"))
    if expected.get("archive_root") not in {None, EXPECTED_ARCHIVE_ROOT}:
        fail(f"{test_id}/{step}: SOLL-Manifest verwendet falsches QA-Archiv")

    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    if evidence.get("archive_root") != EXPECTED_ARCHIVE_ROOT:
        fail(f"{test_id}/{step}: Dateisystemnachweis stammt nicht aus dem freigegebenen QA-Archiv")
    if evidence.get("status") != status:
        fail(
            f"{test_id}/{step}: Status in results.json ({status}) und Evidence "
            f"({evidence.get('status')!r}) widersprechen sich"
        )

    required_fields = {
        "expected_file_count",
        "actual_file_count",
        "expected_directory_count",
        "actual_directory_count",
        *EVIDENCE_EMPTY_FIELDS,
    }
    missing_fields = sorted(field for field in required_fields if field not in evidence)
    if missing_fields:
        fail(f"{test_id}/{step}: Evidence unvollständig: {', '.join(missing_fields)}")

    if status == "PASS":
        if int(evidence["expected_file_count"]) != int(evidence["actual_file_count"]):
            fail(f"{test_id}/{step}: PASS trotz unterschiedlicher Dateianzahl")
        if int(evidence["expected_directory_count"]) != int(evidence["actual_directory_count"]):
            fail(f"{test_id}/{step}: PASS trotz unterschiedlicher Ordneranzahl")
        for field in EVIDENCE_EMPTY_FIELDS:
            if evidence.get(field):
                fail(f"{test_id}/{step}: PASS trotz nichtleerem Evidence-Feld {field}")


def validate_archive_filesystem_evidence(results: dict[str, dict], results_path: Path) -> None:
    run_root = results_path.resolve().parent
    for test_id in sorted(ARCHIVE_IDS):
        record = results.get(test_id)
        if not record:
            continue
        status = record["status"]
        checks = record.get("filesystem_checks")

        if status == "PASS":
            if not isinstance(checks, list) or not checks:
                fail(
                    f"{test_id}: PASS ist ohne mindestens einen realen Dateisystem-Abgleich "
                    "gegen den erwarteten IST→SOLL-Zustand unzulässig"
                )
        elif checks is None:
            continue

        if checks is not None and not isinstance(checks, list):
            fail(f"{test_id}: filesystem_checks muss eine Liste sein")

        for check in checks or []:
            if not isinstance(check, dict):
                fail(f"{test_id}: filesystem_checks enthält keinen Objekteintrag")
            validate_one_filesystem_check(
                test_id,
                check,
                run_root,
                require_plan=test_id in ARCHIVE_PLAN_IDS,
            )

        if status == "PASS":
            failed_checks = [
                str(check.get("step") or "?")
                for check in checks
                if str(check.get("status") or "").upper() != "PASS"
            ]
            if failed_checks:
                fail(
                    f"{test_id}: PASS trotz fehlgeschlagener Dateisystemprüfung(en): "
                    + ", ".join(failed_checks)
                )


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
    validate_archive_filesystem_evidence(results, args.results)

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
