"""Check current-source backend evidence and prove each collected test ran once."""
from collections import Counter
import json
import os
from pathlib import Path
import sys
from xml.etree import ElementTree

PARTITIONS = 8
READ_ONLY_TEST = "tests/backend/test_legacy_adoption_integration.py::test_adoption_reads_actual_read_only_archive"


def require(condition, message):
    if not condition:
        raise SystemExit(message)


def verify(root, source):
    collected = None
    tested = Counter()
    for index in range(PARTITIONS):
        directory = root / f"backend-qa-part-{index}"
        manifest = json.loads((directory / "rc13-partition.json").read_text())
        results = directory / "f14-qa/targets/results"
        result = json.loads((results / "exit.json").read_text())
        nodes = manifest["all_nodes"]
        selected = manifest["selected_nodes"]
        if collected is None:
            collected = nodes
        require(
            nodes == collected == sorted(set(nodes))
            and manifest["partition"] == index
            and manifest["partitions"] == PARTITIONS
            and bool(selected) and selected == nodes[index::PARTITIONS],
            f"Partition {index}: invalid or inconsistent collection",
        )
        require((directory / "source.txt").read_text().strip() == source,
                f"Partition {index}: source differs")
        require(result["returncode"] == 0 and not result.get("timed_out"),
                f"Partition {index}: no successful test process")
        rows = [json.loads(line) for line in (results / "targets-incremental.jsonl").read_text().splitlines()]
        calls = Counter(row["nodeid"] for row in rows if row["phase"] == "call" and row["outcome"] == "passed")
        require(len(rows) == len(selected) and calls == Counter(selected),
                f"Partition {index}: test outcomes differ from selection")
        cases = list(ElementTree.parse(results / "result.xml").iter("testcase"))
        require(len(cases) == len(selected) and not any(
            any(child.tag in {"failure", "error", "skipped"} for child in case) for case in cases
        ), f"Partition {index}: incomplete or unsuccessful JUnit report")
        tested.update(calls)
    require(tested == Counter(collected), "Missing or repeated backend cases")
    require(tested[READ_ONLY_TEST] == 1, "Missing successful kernel read-only mount test")
    return {"source": source, "collected": len(collected), "tested_once": len(tested),
            "partitions": PARTITIONS, "read_only_mount": "PASS", "status": "PASS"}


if __name__ == "__main__":
    report = verify(Path(sys.argv[1]), os.environ["QA_SOURCE"])
    Path(sys.argv[2]).write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))
