"""Run every backend node once in isolated Linux partitions and retain coverage."""
from pathlib import Path
import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET

root = Path(os.environ['RUNNER_TEMP']) / 'pre5-full-backend'
root.mkdir()
all_nodes = None
seen = set()
parts = []
failed = False
for index in range(8):
    scratch = root / str(index)
    scratch.mkdir()
    result = subprocess.run(
        [sys.executable, 'qa/rc13/regression.py', str(index)],
        env=dict(os.environ, RUNNER_TEMP=str(scratch)), timeout=2500)
    manifest_path = scratch / 'rc13-partition.json'
    part = {'partition': index, 'returncode': result.returncode}
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text())
        nodes = manifest['all_nodes']
        if all_nodes is None:
            all_nodes = nodes
        assert all_nodes == nodes, 'Collected nodes changed between partitions'
        selected = manifest['selected_nodes']
        assert not (seen & set(selected)), 'A node was executed more than once'
        seen.update(selected)
        part['selected'] = len(selected)
    else:
        failed = True
        part['coverage_error'] = 'Collection manifest missing'
    xml_path = scratch / 'f14-qa/targets/results/result.xml'
    if xml_path.is_file():
        suites = ET.parse(xml_path).getroot()
        part['results'] = {key: sum(int(s.get(key, 0)) for s in suites.iter('testsuite'))
                           for key in ('tests', 'failures', 'errors', 'skipped')}
        if part['results']['tests'] != part.get('selected'):
            failed = True
            part['coverage_error'] = 'JUnit result count differs from selected nodes'
        # Native-tool checks run on this fully equipped Linux runner. A
        # historical BLOCKED skip is an unresolved acceptance gap, not PASS.
        if any(part['results'][k] for k in ('failures', 'errors', 'skipped')):
            failed = True
    else:
        failed = True
        part['coverage_error'] = 'JUnit results missing'
    failed |= result.returncode != 0
    parts.append(part)
    (root / 'summary.json').write_text(json.dumps({
        'source': os.environ['GITHUB_SHA'], 'parts': parts,
        'collected': len(all_nodes or []), 'selected_once': len(seen),
        'complete': index == 7 and seen == set(all_nodes or [])
            and all(p.get('results', {}).get('tests') == p.get('selected')
                    and 'coverage_error' not in p for p in parts),
        'status': 'FAIL' if failed else 'IN_PROGRESS',
    }, indent=2))
    print(json.dumps(part), flush=True)
    if result.returncode not in (0, 1):
        # A collection/infrastructure failure invalidates this attempt. Do
        # not repeat the same failed collection for seven more partitions.
        raise SystemExit(result.returncode)
assert all_nodes and seen == set(all_nodes), 'Incomplete backend coverage'
summary = json.loads((root / 'summary.json').read_text())
summary['status'] = 'FAIL' if failed else 'PASS'
(root / 'summary.json').write_text(json.dumps(summary, indent=2))
raise SystemExit(1 if failed else 0)
