"""Disjoint partitions covering every backend test file; no deselection."""
import json
import os
from pathlib import Path
import subprocess
import sys
source=Path(__file__).resolve().parents[2]
partition=int(sys.argv[1]);assert 0<=partition<8
files=sorted(str(p.relative_to(source)) for p in (source/'tests/backend').rglob('test_*.py'))
selected=files[partition::8];assert selected
path=Path(os.environ['RUNNER_TEMP'])/'rc13-targets.json'
path.write_text(json.dumps(selected))
(Path(os.environ['RUNNER_TEMP'])/'rc13-partition.json').write_text(json.dumps({'partition':partition,'partitions':8,'all_files':files,'selected':selected},indent=2))
raise SystemExit(subprocess.call([sys.executable,str(source/'qa/f14/linux/run_linux.py'),str(source),'targets',str(path)]))
