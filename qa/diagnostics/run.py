"""Run only the known failed pytest nodes on the inherited disposable F14 runner.

This diagnostic never grants release approval. It always records exact node
identity, JUnit statistics and failures, including when a test stays red.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from xml.etree import ElementTree as ET

SOURCE = Path(__file__).resolve().parents[2]
ROOT = Path(os.environ["RUNNER_TEMP"]).resolve()
GROUPS = json.loads((SOURCE / "qa/diagnostics/groups.json").read_text(encoding="utf-8"))["groups"]
name = sys.argv[1] if len(sys.argv) == 2 else ""
if name not in GROUPS:
    raise SystemExit("Unknown diagnostic group: " + name)
nodes = GROUPS[name]
assert nodes and len(nodes) == len(set(nodes)), "Empty or duplicated selection"
assert all(node.startswith("tests/backend/") and ".." not in node.split("::")[0].split("/") for node in nodes)

selected_path = ROOT / "targeted-nodes.json"
files_path = ROOT / "targeted-files.json"
selected_path.write_text(json.dumps(nodes, indent=2), encoding="utf-8")
files_path.write_text(json.dumps(sorted({node.split("::")[0] for node in nodes}), indent=2), encoding="utf-8")

environment = dict(os.environ, AUDIT_DIAGNOSTIC_NODES_FILE=str(selected_path))
argv = [
    sys.executable, str(SOURCE / "qa/f14/linux/run_linux.py"),
    str(SOURCE), "targets", str(files_path),
]
try:
    completed = subprocess.run(argv, cwd=SOURCE, env=environment, timeout=1800)
    code = completed.returncode
except subprocess.TimeoutExpired:
    code = 124

output = ROOT / "f14-qa/targets/results"
selection = output / "diagnostic-selection.json"
junit = output / "result.xml"
stats = {}
actually_selected = []
if selection.is_file():
    recorded = json.loads(selection.read_text(encoding="utf-8"))
    actually_selected = recorded["selected"]
if junit.is_file():
    xml = ET.parse(junit).getroot()
    stats = {
        key: sum(int(suite.get(key, 0)) for suite in xml.iter("testsuite"))
        for key in ("tests", "failures", "errors", "skipped")
    }

ok_selection = (len(actually_selected) == len(nodes) and
                set(actually_selected) == set(nodes))
status = "PASS" if (
    code == 0 and ok_selection and
    stats.get("tests") == len(nodes) and
    all(stats.get(key, 1) == 0 for key in ("failures", "errors", "skipped"))
) else "FAIL"
report = {
    "group": name,
    "source": os.environ["GITHUB_SHA"],
    "expected_node_ids": nodes,
    "selected_node_ids": actually_selected,
    "selection_valid": ok_selection,
    "returncode": code,
    "junit": stats,
    "status": status,
    "qualification": "DIAGNOSTIC_ONLY_NOT_FULL_1_0_0_RELEASE_APPROVAL",
}
(ROOT / "diagnostic-summary.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report, indent=2), flush=True)
raise SystemExit(0 if status == "PASS" else 1)
