"""One isolated gate before the complete Linux matrix."""
import json,os,subprocess,sys
from pathlib import Path
names=['test_pre_metadata.py','test_pre_archive.py','test_pre_cache.py','test_pre_ui.py','test_0331_patch.py','test_0336_patch.py','test_0500_metadata_swap_recovery.py','test_0452_cache_history_ui.py','test_0504_english_ui_completion.py','test_rc14_import.py','test_rc14_lifecycle.py','test_rc13_provenance.py','test_rc12_storage.py']
files=['tests/backend/'+n for n in names if (Path('tests/backend')/n).exists()]
p=Path(os.environ['RUNNER_TEMP'])/'pre-targets.json';p.write_text(json.dumps(files))
raise SystemExit(subprocess.call([sys.executable,'qa/f14/linux/run_linux.py',str(Path.cwd()),'targets',str(p)]))
