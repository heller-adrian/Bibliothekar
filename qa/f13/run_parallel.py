"""Reuse unchanged phase-4 assertions for SSD/root and SSD/inventory overlap."""
from pathlib import Path
from run_original import run

root=Path(__file__).resolve().parent/'original'
raise SystemExit(run([str(root/'test_final_combinations.py')+'::test_rename_after_ssd_unlink',
                      str(root/'test_completion.py')+'::test_inventory_during_ssd_release']))
