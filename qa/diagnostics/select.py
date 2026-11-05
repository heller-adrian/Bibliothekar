"""Exact-node selection and synthetic-only failure forensics.

No assertion is weakened: missing/renamed nodes are fatal, and the caller
must still validate every selected JUnit result. Never inspect any NAS path.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
import threading
import traceback

import pytest


def pytest_collection_modifyitems(config, items):
    path = Path(os.environ["AUDIT_DIAGNOSTIC_NODES_FILE"])
    expected = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(expected, list) and expected and len(expected) == len(set(expected))
    assert all(isinstance(node, str) and node.startswith("tests/backend/") for node in expected)
    actual = {item.nodeid: item for item in items}
    assert len(actual) == len(items), "Duplicate collected pytest node IDs"
    missing = sorted(set(expected) - set(actual))
    if missing:
        raise RuntimeError("Diagnostic tests not collected; refusal to pass: " + repr(missing))
    chosen = set(expected)
    excluded = [item for item in items if item.nodeid not in chosen]
    items[:] = [item for item in items if item.nodeid in chosen]
    config.hook.pytest_deselected(items=excluded)
    output = Path(os.environ["AUDIT_OUTPUT"])
    (output / "diagnostic-selection.json").write_text(json.dumps({
        "expected": expected, "selected": [item.nodeid for item in items],
        "deselected": len(excluded),
    }, indent=2))


def _inside_scratch(path):
    scratch = Path(os.environ["AUDIT_SCRATCH"]).resolve()
    candidate = Path(path).absolute()
    return candidate == scratch or scratch in candidate.parents


def _safe_file(path):
    if not isinstance(path, Path) or not _inside_scratch(path):
        return None
    result = {"path": str(path), "exists": path.is_file()}
    if path.is_file() and path.stat().st_size < 16 * 1024 * 1024:
        result["size"] = path.stat().st_size
        result["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def _failure_snapshot(item, call):
    evidence = {"nodeid": item.nodeid, "issue": "failure remains reproducible"}
    if "test_f11_trash_reservation.py" in item.nodeid:
        # Inspect only Python thread stacks; never change the lock/operation.
        frames = sys._current_frames()
        evidence["threads"] = [{
            "name": thread.name, "alive": thread.is_alive(),
            "stack": [str(line) for line in traceback.extract_stack(frames[thread.ident])[-14:]]
        } for thread in threading.enumerate()
          if thread is not threading.main_thread() and thread.ident in frames][:12]
    if any(key in item.nodeid for key in
           ("test_rc4_sd_recheck.py", "test_rc1_sd_reimport.py", "test_rc5_practice_followup.py")):
        # Read only the failing case's local synthetic fixture and child result.
        for trace in reversed(list(call.excinfo.traceback)):
            local = trace.frame.f_locals
            if any(k in local for k in ("target", "source", "child", "dbs")):
                for key in ("target", "source"):
                    observed = _safe_file(local.get(key))
                    if observed is not None:
                        evidence[key] = observed
                child = local.get("child")
                if isinstance(child, dict):
                    evidence["child"] = {
                        k: child.get(k) for k in ("id", "state", "operation", "error")
                    }
                    if isinstance(child.get("result"), dict):
                        evidence["child"]["result"] = {
                            k: child["result"].get(k)
                            for k in ("status", "organization", "source")
                        }
                if evidence.get("target") and evidence.get("source"):
                    break
        target = evidence.get("target")
        source = evidence.get("source")
        if target and source and source.get("sha256"):
            root = Path(os.environ["AUDIT_SCRATCH"])
            hits = []
            for candidate in root.glob("pytest/**/workspace/**/*.JPG"):
                if len(hits) >= 20:
                    break
                try:
                    if candidate.is_file() and candidate.stat().st_size == source.get("size"):
                        if hashlib.sha256(candidate.read_bytes()).hexdigest() == source["sha256"]:
                            hits.append(str(candidate))
                except OSError:
                    pass
            evidence["matching_synthetic_jpg_paths"] = hits
    return evidence


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if report.failed and report.when == "call":
        output = Path(os.environ["AUDIT_OUTPUT"])
        try:
            evidence = _failure_snapshot(item, call)
        except Exception as error:
            evidence = {"nodeid": item.nodeid, "diagnostic_error": str(error)}
        with (output / "diagnostic-failures.jsonl").open("a", encoding="utf-8") as file:
            file.write(json.dumps(evidence, ensure_ascii=False, default=str) + "\n")
