"""One isolated gate before the complete Linux matrix."""
import json,os,subprocess,sys
from pathlib import Path
names=['test_0264_inspector_ui.py','test_0291_guided_custom_app.py','test_0402_mobile_no_event_range.py','test_0421_hotfix.py','test_0422_metadata_autoscan.py','test_pre_metadata.py','test_pre_metadata_retry.py','test_pre_archive.py','test_pre_cache.py','test_pre_ui.py','test_0331_patch.py','test_0336_patch.py','test_0500_metadata_swap_recovery.py','test_0452_cache_history_ui.py','test_0504_english_ui_completion.py','test_rc14_import.py','test_rc14_lifecycle.py','test_rc13_provenance.py','test_rc12_storage.py']
files=['tests/backend/'+n for n in names]
assert all(Path(p).is_file() for p in files), 'Missing mandatory targeted test'
p=Path(os.environ['RUNNER_TEMP'])/'pre-targets.json';p.write_text(json.dumps(files))
raise SystemExit(subprocess.call([sys.executable,'qa/f14/linux/run_linux.py',str(Path.cwd()),'targets',str(p)]))
