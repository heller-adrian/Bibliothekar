"""Collect every backend test; disjoint nodes balance long crash-test files."""
import json
import os
from pathlib import Path
import subprocess
import sys
source=Path(__file__).resolve().parents[2]
partition=int(sys.argv[1]);assert 0<=partition<8
files=sorted(str(p.relative_to(source)) for p in (source/'tests/backend').rglob('test_*.py'))
assert files
path=Path(os.environ['RUNNER_TEMP'])/'rc13-targets.json'
path.write_text(json.dumps(files))
raise SystemExit(subprocess.call([sys.executable,str(source/'qa/f14/linux/run_linux.py'),str(source),'targets',str(path)],
                                env=dict(os.environ,RC13_PARTITION=str(partition))))
