import json,os,subprocess,sys
from pathlib import Path
p=Path(os.environ['RUNNER_TEMP'])/'rc14-targeted.json'
p.write_text(json.dumps(['tests/backend/'+s for s in ['test_rc14_import.py','test_rc14_lifecycle.py','test_rc13_provenance.py','test_rc13_ui.py','test_0310_multi_library.py','test_0311_global_stock.py','test_0400_import_backup_controls.py','test_0455_import_safety.py','test_0562_recovery_guards.py']]))
raise SystemExit(subprocess.call([sys.executable,'qa/f14/linux/run_linux.py',str(Path.cwd()),'targets',str(p)]))
