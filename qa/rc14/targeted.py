import json,os,subprocess,sys
from pathlib import Path
p=Path(os.environ['RUNNER_TEMP'])/'rc14-targeted.json'
p.write_text(json.dumps(['tests/backend/'+s for s in ['test_rc14_import.py','test_rc14_lifecycle.py','test_rc14_ui.py','test_rc13_provenance.py','test_rc13_ui.py','test_0310_multi_library.py','test_0311_global_stock.py','test_0400_import_backup_controls.py','test_0455_import_safety.py','test_0562_recovery_guards.py',
    # Onboarding/first-library regressions must pass before the 8 expensive
    # backend partitions are allowed to run.
    'test_0329_patch.py',
    'test_rc5_practice_followup.py::test_fresh_real_startup_and_actual_onboarding',
    'test_rc6_legacy_setup.py::test_historical_missing_intent_offers_confirmed_setup',
    'test_rc7_reset_states.py::test_two_independent_states_complete_real_onboarding',
    'test_rc7_reset_states.py::test_real_onboarding_read_does_not_turn_empty_registry_into_a_blocker']]))
raise SystemExit(subprocess.call([sys.executable,'qa/f14/linux/run_linux.py',str(Path.cwd()),'targets',str(p)]))
