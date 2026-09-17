#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ALLOWED_VERDICTS = {"ACCEPT_PASS", "ACCEPT_FAIL", "ACCEPT_BLOCKED", "RETEST_REQUIRED"}
ALLOWED_CHECK_RESULTS = {"PASS", "FAIL", "BLOCKED"}
FORBIDDEN_TEXT_PATTERNS = (
    re.compile(r"/mnt/"),
    re.compile(r"/home/"),
    re.compile(r"BEGIN [A-Z ]*PRIVATE KEY"),
    re.compile(r"(?i)(token|password|passwd|secret)\s*[:=]"),
)
MAX_CHECKS = 100
MAX_CHECK_ID_CHARS = 80
MAX_CHECK_METHOD_CHARS = 80
MAX_CHECK_TEXT_CHARS = 1000


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"BLOCKED: expected JSON object: {path}")
    return data


def reject_forbidden_text(value: Any, where: str = "root") -> None:
    if isinstance(value, str):
        for pattern in FORBIDDEN_TEXT_PATTERNS:
            if pattern.search(value):
                raise SystemExit(f"BLOCKED: forbidden sensitive/path-like text at {where}")
    elif isinstance(value, dict):
        for key, child in value.items():
            reject_forbidden_text(child, f"{where}.{key}")
    elif isinstance(value, list):
        for idx, child in enumerate(value):
            reject_forbidden_text(child, f"{where}[{idx}]")


def clean_text(value: Any, *, field: str, max_chars: int, required: bool = False) -> str | None:
    if value is None:
        if required:
            raise SystemExit(f"BLOCKED: check missing {field}")
        return None
    if not isinstance(value, str):
        raise SystemExit(f"BLOCKED: check {field} must be a string")
    text = value.strip()
    if required and not text:
        raise SystemExit(f"BLOCKED: check {field} is empty")
    if len(text) > max_chars:
        raise SystemExit(f"BLOCKED: check {field} exceeds {max_chars} chars")
    return text or None


def clean_checks(evidence: dict[str, Any]) -> list[dict[str, Any]]:
    raw = evidence.get("checks") or []
    if not isinstance(raw, list):
        raise SystemExit("BLOCKED: evidence.checks must be a list")
    if len(raw) > MAX_CHECKS:
        raise SystemExit(f"BLOCKED: evidence.checks exceeds {MAX_CHECKS} entries")

    out: list[dict[str, Any]] = []
    for idx, item in enumerate(raw):
        if not isinstance(item, dict):
            raise SystemExit(f"BLOCKED: evidence.checks[{idx}] must be an object")

        check_id = clean_text(item.get("id"), field="id", max_chars=MAX_CHECK_ID_CHARS, required=True)
        method = clean_text(item.get("method"), field="method", max_chars=MAX_CHECK_METHOD_CHARS, required=True)
        action = clean_text(item.get("action"), field="action", max_chars=MAX_CHECK_TEXT_CHARS, required=True)
        expected = clean_text(item.get("expected"), field="expected", max_chars=MAX_CHECK_TEXT_CHARS, required=True)
        actual = clean_text(item.get("actual"), field="actual", max_chars=MAX_CHECK_TEXT_CHARS, required=True)
        result = clean_text(item.get("result"), field="result", max_chars=20, required=True)
        if result not in ALLOWED_CHECK_RESULTS:
            raise SystemExit(f"BLOCKED: evidence.checks[{idx}].result invalid: {result}")

        status_code = item.get("status_code")
        if status_code is not None:
            if isinstance(status_code, bool) or not isinstance(status_code, int):
                raise SystemExit(f"BLOCKED: evidence.checks[{idx}].status_code must be an integer or null")
            if status_code < 100 or status_code > 599:
                raise SystemExit(f"BLOCKED: evidence.checks[{idx}].status_code outside HTTP range")

        error = clean_text(item.get("error"), field="error", max_chars=MAX_CHECK_TEXT_CHARS)

        cleaned: dict[str, Any] = {
            "id": check_id,
            "method": method,
            "action": action,
            "expected": expected,
            "actual": actual,
            "result": result,
        }
        if status_code is not None:
            cleaned["status_code"] = status_code
        if error is not None:
            cleaned["error"] = error
        out.append(cleaned)
    return out


def clean_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    db = evidence.get("database") or {}
    fixture = evidence.get("fixture") or {}
    return {
        "database": {
            "table_count_delta": db.get("table_count_delta") or {},
            "jobs_by_state_delta": db.get("jobs_by_state_delta") or {},
            "jobs_by_kind_delta": db.get("jobs_by_kind_delta") or {},
            "integrity_before": db.get("integrity_before") or [],
            "integrity_after": db.get("integrity_after") or [],
            "schema_versions_equal": bool(db.get("schema_versions_equal")),
        },
        "fixture": {
            "added": fixture.get("added") or [],
            "removed": fixture.get("removed") or [],
            "changed": fixture.get("changed") or [],
        },
        "checks": clean_checks(evidence),
    }


def main() -> int:
    p = argparse.ArgumentParser(description="Build sanitized Thinker-gated QA ledger export")
    p.add_argument("--evidence", required=True, help="Deterministic evidence delta JSON")
    p.add_argument("--review", required=True, help="Sanitized completed qa-thinker review JSON")
    p.add_argument("--product-commit", required=True)
    p.add_argument("--qa-commit", required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args()

    evidence = load_json(Path(args.evidence))
    review = load_json(Path(args.review))

    if evidence.get("schema") != "bibliothekar.qa.evidence.delta.v1":
        raise SystemExit("BLOCKED: unsupported evidence schema")
    if review.get("profile") != "qa-thinker":
        raise SystemExit("BLOCKED: review profile is not qa-thinker")
    if review.get("mode") != "REVIEW":
        raise SystemExit("BLOCKED: review mode is not REVIEW")
    if review.get("completed") is not True:
        raise SystemExit("BLOCKED: review is not completed")

    verdict = review.get("verdict")
    if verdict not in ALLOWED_VERDICTS:
        raise SystemExit("BLOCKED: invalid or missing Thinker verdict")

    test_id = str(evidence.get("test_id") or "")
    phase = str(evidence.get("phase") or "")
    executor = evidence.get("executor") or {}
    if not test_id or not phase:
        raise SystemExit("BLOCKED: evidence missing test_id/phase")
    if review.get("test_id") != test_id:
        raise SystemExit("BLOCKED: review/evidence test_id mismatch")
    if str(review.get("executor_task_id") or "") != str(executor.get("task_id") or ""):
        raise SystemExit("BLOCKED: review/evidence executor_task_id mismatch")
    if str(review.get("executor_run_id") or "") != str(executor.get("run_id") or ""):
        raise SystemExit("BLOCKED: review/evidence executor_run_id mismatch")

    reason = str(review.get("reason") or "").strip()
    if not reason:
        raise SystemExit("BLOCKED: review reason missing")

    payload = {
        "schema": "bibliothekar.qa.verified-result.v1",
        "exported_at": utc_now(),
        "test_id": test_id,
        "phase": phase,
        "product_commit": args.product_commit,
        "qa_commit": args.qa_commit,
        "executor": {
            "task_id": executor.get("task_id"),
            "run_id": executor.get("run_id"),
        },
        "review": {
            "task_id": review.get("task_id"),
            "run_id": review.get("run_id"),
            "profile": "qa-thinker",
            "mode": "REVIEW",
            "completed": True,
            "verdict": verdict,
            "reason": reason,
        },
        "evidence": clean_evidence(evidence),
    }

    reject_forbidden_text(payload)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    tmp = output.with_suffix(output.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, output)
    print(json.dumps({"status": "PASS", "output": str(output), "verdict": verdict, "test_id": test_id}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
