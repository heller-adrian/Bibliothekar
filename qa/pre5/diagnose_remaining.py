"""Bounded, read-only-to-repository Linux diagnosis; all app writes stay in synthetic scratch.

Run: python qa/pre5/diagnose_remaining.py
The child executes the real unchanged F14 pytest harness, retains complete XML/stdout
for each independent group and continues past failing tests. Never a release gate.
"""
from collections import Counter
from pathlib import Path
import json
import os
import shutil
import signal
import subprocess
import sys
import xml.etree.ElementTree as ET

source = Path.cwd().resolve()
work = Path(os.environ["QA_WORK"]).resolve()
work.mkdir(parents=True, exist_ok=True)
evidence = work / "diagnostics-evidence"
runs = work / "diagnostics-runs"
evidence.mkdir(exist_ok=True)
runs.mkdir(exist_ok=True)
definition = json.loads((source / "qa/pre5/diagnostic_selection.json").read_text())
groups = definition["groups"]
assert len(groups) == 3 and sum(map(len, groups.values())) == 24
assert len(set(node for nodes in groups.values() for node in nodes)) == 24
summary = {"source":os.environ["GITHUB_SHA"],"classification":"DIAGNOSTIC_ONLY_NOT_RELEASE_ACCEPTANCE",
           "baseline_run":definition["source_baseline"],
           "unretested_run":definition["unretested_previous_run"],"groups":[],
           "selected":24,"passed":0,"failed":0,"errors":0,"skipped":0,
           "unmatched_or_missing":0,"status":"IN_PROGRESS"}
(evidence / "selection.json").write_text(json.dumps(definition,indent=2)+"\n")

for name, nodes in groups.items():
    assert name.replace("_","").isalnum() and nodes
    target = runs / name
    target.mkdir()
    selection_file = target / "selection.json"
    selection_file.write_text(json.dumps(nodes,indent=2)+"\n")
    args = [sys.executable,"qa/f14/linux/run_linux.py",str(source),"targets",str(selection_file)]
    env = dict(os.environ,RUNNER_TEMP=str(target))
    timed_out = False
    with (evidence / (name+"-launcher.log")).open("w") as log:
        process = subprocess.Popen(args,cwd=source,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        try:
            result = process.wait(timeout=840)
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(process.pid,signal.SIGKILL)
            result = process.wait()
    root = target / "f14-qa/targets/results"
    for filename in ("result.xml","stdout.log","bootstrap.log","command.json","exit.json","execution-deadlines.json"):
        path = root / filename
        if path.is_file():
            shutil.copy2(path,evidence/(name+"-"+filename))
    path = evidence/(name+"-result.xml")
    cases = list(ET.parse(path).iter("testcase")) if path.is_file() else []
    counts = Counter()
    findings = []
    for case in cases:
        problem = case.find("failure")
        error = case.find("error")
        skip = case.find("skipped")
        status = "FAIL" if problem is not None else "ERROR" if error is not None else "SKIP" if skip is not None else "PASS"
        counts[status] += 1
        if status != "PASS":
            element = problem if problem is not None else error if error is not None else skip
            findings.append({"classname":case.get("classname"),"case":case.get("name"),
                             "status":status,"duration_seconds":case.get("time"),
                             "message":(element.get("message") or "")[:1500],
                             "trace_excerpt":(element.text or "")[-2500:]})
    group_info = {"name":name,"requested":len(nodes),"recorded":len(cases),
                  "exit_code":result,"timeout":timed_out,
                  "passed":counts["PASS"],"failed":counts["FAIL"],
                  "errors":counts["ERROR"],"skipped":counts["SKIP"],
                  "findings":findings}
    summary["groups"].append(group_info)
    for k in ("passed","failed","errors","skipped"):
        summary[k] += group_info[k]
    if len(cases) != len(nodes) or timed_out:
        summary["unmatched_or_missing"] += abs(len(cases)-len(nodes)) or 1
    (evidence/"summary.json").write_text(json.dumps(summary,indent=2)+"\n")
    print(json.dumps({k:v for k,v in group_info.items() if k!="findings"}),flush=True)

summary["status"]="PASS" if summary["passed"]==24 and not summary["unmatched_or_missing"] and all(g["exit_code"]==0 for g in summary["groups"]) else "FAIL"
(evidence/"summary.json").write_text(json.dumps(summary,indent=2)+"\n")
print(json.dumps({"status":summary["status"],"passed":summary["passed"],"failed":summary["failed"],
                  "errors":summary["errors"],"skipped":summary["skipped"],
                  "unmatched_or_missing":summary["unmatched_or_missing"]}),flush=True)
raise SystemExit(0 if summary["status"]=="PASS" else 1)
