"""Partition the complete acceptance matrix across isolated runners."""
import json,os,subprocess,sys
from pathlib import Path
source=Path(__file__).resolve().parents[2]
group=sys.argv[1]
all_targets=json.loads((source/'qa/rc11/targets.json').read_text())
partitions={'baseline':all_targets[:6],
 'bootstrap':['tests/backend/test_rc11_bootstrap.py'],
 'retention':['tests/backend/test_rc4_private_retention.py'],
 'history':['tests/backend/test_f14_root_operations.py','tests/backend/test_rc5_practice_followup.py']}
flat=[x for rows in partitions.values() for x in rows]
assert len(flat)==len(set(flat)) and set(flat)==set(all_targets)
selection=Path(os.environ['RUNNER_TEMP'])/('rc11-'+group+'-targets.json')
selection.write_text(json.dumps(partitions[group]))
raise SystemExit(subprocess.call([sys.executable,str(source/'qa/f14/linux/run_linux.py'),str(source),'targets',str(selection)],cwd=source))
