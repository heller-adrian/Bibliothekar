"""Verify downloaded exact-source pre CI artifacts before release; no application writes."""
import json, os, subprocess, xml.etree.ElementTree as ET
from pathlib import Path

BASE = Path(os.environ.get("EVIDENCE_DIR", str(Path(os.environ["RUNNER_TEMP"]) / "pre-accepted-evidence")))
OUT = Path(os.environ.get("ASSET_DIR", "release-assets"))
SHA = os.environ["ACCEPTED_SHA"]
RUN = int(os.environ["ACCEPTED_QA"])

def read_json(path):
    return json.loads(path.read_text())

def require_passed_xml(path):
    cases = list(ET.parse(path).iter("testcase"))
    assert cases, "empty test report: " + str(path)
    for case in cases:
        assert all(case.find(name) is None for name in ("failure", "error", "skipped")), (
            "failed, skipped or errored: " + ET.tostring(case, encoding="unicode")[:1000]
        )
    return len(cases)

run = read_json(OUT / "accepted-QA.json")
assert run["id"] == RUN and run["head_sha"] == SHA, "CI run identity mismatch"
assert run["path"] == ".github/workflows/qa-pre.yml"
assert run["status"] == "completed" and run["conclusion"] == "success", "CI not successful"
assert run["run_attempt"] == 1, "unexpected CI attempt: inspect before publishing"
repo = read_json(OUT / "repository-privacy.json")
assert repo["private"] is True and repo["full_name"] == "heller-adrian/Bibliothekar"
jobs = read_json(OUT / "accepted-jobs.json")["jobs"]
required = {"Targeted failure and security gate", "Chromium German English mobile desktop",
            "Real supervisor RC12 upgrade and crash acceptance"}
required |= {"Complete backend (" + str(i) + ")" for i in range(8)}
assert len(jobs) == len(required), "unexpected missing or additional jobs"
assert {j["name"] for j in jobs} == required, "job set mismatch"
assert all(j["status"] == "completed" and j["conclusion"] == "success" for j in jobs)
artifacts = read_json(OUT / "accepted-artifacts.json")["artifacts"]
required_artifacts = {"rc14-container", "pre-browser", "rc14-targeted"}
required_artifacts |= {"rc14-backend-" + str(i) for i in range(8)}
assert {a["name"] for a in artifacts} == required_artifacts, "artifact names mismatch"
assert all(not a["expired"] and a["size_in_bytes"] > 0 for a in artifacts)
for a in required_artifacts:
    assert (BASE / a).is_dir(), "artifact not downloaded: " + a

all_nodes = None
all_files = None
selected, executed = [], []
counts = {}
for partition in range(8):
    root = BASE / ("rc14-backend-" + str(partition))
    manifest = read_json(root / "rc13-partition.json")
    assert manifest["partition"] == partition and manifest["partitions"] == 8
    if all_nodes is None:
        all_nodes = manifest["all_nodes"]
        all_files = manifest["all_files"]
    assert manifest["all_nodes"] == all_nodes and manifest["all_files"] == all_files
    expected = all_nodes[partition::8]
    assert manifest["selected_nodes"] == expected
    results = root / "f14-qa" / "targets" / "results"
    assert read_json(results / "exit.json")["returncode"] == 0
    count = require_passed_xml(results / "result.xml")
    assert count == len(expected), "partition XML count mismatch"
    actual = []
    for path in results.glob("*incremental.jsonl"):
        for line in path.read_text().splitlines():
            record = json.loads(line)
            if record.get("phase") == "call":
                assert record["outcome"] == "passed", record
                actual.append(record["nodeid"])
    assert len(actual) == count and sorted(actual) == expected, "incremental mismatch"
    selected.extend(expected)
    executed.extend(actual)
    counts[str(partition)] = count
assert len(all_nodes) == 2269 and len(set(all_nodes)) == len(all_nodes)
assert sorted(selected) == all_nodes and sorted(executed) == all_nodes
source_files = sorted(str(p.relative_to(Path(os.environ.get("SOURCE_DIR", ".")))) for p in (Path(os.environ.get("SOURCE_DIR", ".")) / "tests/backend").rglob("test_*.py"))
assert source_files == all_files, "backend test file set changed since acceptance"
assert {x.split("::")[0] for x in all_nodes} == set(source_files)

targeted = BASE / "rc14-targeted"
assert read_json(targeted / "exit.json")["returncode"] == 0
assert require_passed_xml(targeted / "result.xml") == 177

browser_dir = BASE / "pre-browser"
browser = read_json(browser_dir / "rc14-browser" / "results.json")
legacy = read_json(browser_dir / "rc14-browser-legacy" / "results.json")
pre = read_json(browser_dir / "pre-browser" / "results.json")
for case_set, expected in ((browser, 147), (legacy, 44), (pre, 4)):
    assert case_set["status"] == "PASS" and len(case_set["cases"]) == expected
    assert all(c["status"] == "PASS" for c in case_set["cases"])

container_root = BASE / "rc14-container"
reports = {prefix: read_json(container_root / (prefix + "-evidence.json"))
           for prefix in ("rc14", "rc13", "rc12", "rc11")}
expected_counts = {"rc14": 2, "rc13": 2, "rc12": 25, "rc11": 19}
for prefix, report in reports.items():
    assert report["source"] == SHA, "container source mismatch: " + prefix
    assert len(report["cases"]) == expected_counts[prefix]
    assert all(c["status"] == "PASS" for c in report["cases"])
assert reports["rc14"]["native_truenas"] == reports["rc13"]["native_truenas"] == "NOT_RUN"
assert {c["boundary"] for c in reports["rc14"]["cases"]} == {"journal", "partial"}
for case in reports["rc14"]["cases"]:
    assert case["uid"] == 568 and case["real_rc13_upgrade"]
    assert all(case[key] for key in ("normal_archive_reimport", "two_restarts", "readonly_bytes_unchanged"))
    crash = case["import_crash"]
    assert crash["boundary"] == case["boundary"] and crash["uid"] == 568
    assert crash["event"] == "return" and crash["thread"] == "kamera-job-worker"
    assert crash["function"] == ("_atomic_json" if case["boundary"] == "journal" else "publish_import_file")
    if case["boundary"] == "journal":
        retirement = case["retirement_crash"]
        assert retirement["boundary"] == "retirement-registry-committed"
        assert retirement["uid"] == 568 and retirement["event"] == "c_return" and retirement["function"] == "remove.commit"
    else:
        assert case["retirement_crash"] is None
for case in reports["rc13"]["cases"]:
    assert all(case[key] for key in ("rc12_block_reproduced", "real_http_import",
        "source_members_preserved", "second_library_created", "unknown_restore_no_mutation",
        "protected_mutation_after_restart", "raw_identity_preserved", "readonly_bytes_preserved"))
assert reports["rc13"]["cases"][1]["crash"]["uid"] == 568
for case in reports["rc12"]["cases"]:
    assert all(case[key] for key in ("first_library_created", "following_mutation",
        "restarted", "repair_restored", "repair_replaced", "archives_unchanged"))
for case in reports["rc11"]["cases"]:
    assert all(case[key] for key in ("first_library_created", "following_mutation",
        "restarted", "archives_unchanged"))

pre_container = read_json(container_root / "pre-evidence.json")
assert pre_container["commit"] == SHA and pre_container["status"] == "PASS"
assert pre_container["corrected_files"] == 14
assert all(pre_container[k] for k in ("same_reservation_preserved_until_retry", "origin_preserved", "readonly_bytes_preserved"))
assert pre_container["native_truenas"] == "NOT_RUN"
assert pre_container["before"]["origin"] == pre_container["after"]["origin"]
assert pre_container["before"]["readonly"] == pre_container["final"]["readonly"]
expected_counts["pre"] = 1

summary = {"status": "PASS", "accepted_source_sha": SHA, "accepted_run": RUN,
    "backend_tests": len(all_nodes), "backend_partitions": counts, "targeted_tests": 177,
    "chromium_rc14": 147, "chromium_legacy": 44, "chromium_pre": 4,
    "containers": expected_counts, "containers_total": sum(expected_counts.values()),
    "native_truenas_acl": "NOT_RUN"}
(OUT / "verified-QA-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
print(json.dumps(summary, indent=2))
