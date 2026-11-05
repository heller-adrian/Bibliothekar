"""RC12 reruns historical guards and new architecture in isolated partitions."""
import json,os,subprocess,sys
from pathlib import Path
source=Path(__file__).resolve().parents[2];group=sys.argv[1]
if group != 'rc12':
    raise SystemExit(subprocess.call([sys.executable,str(source/'qa/rc11/regression.py'),group]))
selection=Path(os.environ['RUNNER_TEMP'])/'rc12-targets.json'
selection.write_text(json.dumps(['tests/backend/test_rc12_storage.py','tests/backend/test_device_safety.py',
                                 'tests/backend/test_0500_http_owner_auth.py','tests/backend/test_0310_multi_library.py']))
raise SystemExit(subprocess.call([sys.executable,str(source/'qa/f14/linux/run_linux.py'),str(source),'targets',str(selection)]))
