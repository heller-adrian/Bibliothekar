"""Baseline-Check: alle App-Module kompilieren und importieren (read-only)."""
import compileall
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

ok = compileall.compile_dir(str(ROOT / "app"), quiet=1)
print("COMPILE_OK" if ok else "COMPILE_FELGER")

import app.main  # noqa: E402

print("IMPORT_OK", app.main.APP_VERSION)
