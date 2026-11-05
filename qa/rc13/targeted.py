"""Reproduce failed CI contracts before spending a full acceptance run."""
import json
import os
from pathlib import Path
import subprocess
import sys

source = Path(__file__).resolve().parents[2]
tests = [
    'test_root_atomic_publication.py', 'test_descriptor_filesystem.py',
    'test_rc13_provenance.py', 'test_rc13_ui.py', 'test_rc13_partition.py',
    'test_0504_english_ui_completion.py', 'test_0508_regression.py',
    'test_0509_english_workflows.py',
    'test_f14_o2_policy.py::test_f14_o2_sigkill_and_three_real_lifecycle_starts_preserve_state',
    'test_f14_continuation.py::test_f14_finished_receipt_survives_repeated_sigkill',
    'test_f14_continuation.py::test_f14_orphan_shared_reservation_blocks_other_library_after_sigkill',
    'test_rc1_b01.py::test_b01_live_inventory_conflict_is_bounded_and_visible',
    'test_f14_runtime.py::test_f14_real_worker_rejects_rename_then_allows_completion[reconcile-reconcile.move1]',
    'test_wave2_integration.py',
    'test_f11_trash_reservation.py::test_f11_reservation_wins[full]',
    'test_0562_process_recovery.py::test_trash_sigkill[trash.db1]',
    'test_0562_process_recovery.py::test_sort_recovery_sigkill',
    'test_f16_f20_stock_consistency.py::test_unchanged_original[f20]',
    'test_rc4_practice.py::test_sd_activity_only_in_dock_and_local_notice',
    'test_0562_recovery_guards.py::test_startup_recovers_registered_databases_only',
    'test_rc1_b01.py', 'test_rc1_package_c.py',
    'test_0562_process_recovery.py::test_ssd_repeat_retry_counterprobe',
    'test_metadata_consistency_f15_f17_f18.py::test_metadata_safety_contract[f15_active]',
    'test_metadata_consistency_f15_f17_f18.py::test_metadata_safety_contract[f15_pending]',
]
selection = Path(os.environ['RUNNER_TEMP'])/'rc13-targeted.json'
selection.write_text(json.dumps(['tests/backend/'+name for name in tests]))
raise SystemExit(subprocess.call([sys.executable, str(source/'qa/f14/linux/run_linux.py'),
                                 str(source), 'targets', str(selection)]))
