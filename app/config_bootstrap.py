"""Safe, one-time creation of a minimal application settings file.

Missing settings are normal on a first install / after an intentional clean
slate. A present configuration is never altered here, including malformed
JSON, because repairing it implicitly could discard the owner's choices.
"""
from __future__ import annotations

from pathlib import Path
import json
import os


def ensure_settings_file(config_path: Path) -> bool:
    """Create a valid UTF-8 JSON settings object if missing.

    Returns True if created, False if a file already exists. Only the
    configured target is written; sibling secrets (e.g. admin-password) and
    saved settings are never touched. Uses exclusive creation to avoid
    overwriting a file that appears between existence check and open.
    """
    path = Path(config_path)
    if path.exists() or path.is_symlink():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({}, ensure_ascii=False, indent=2) + "\n"
    try:
        descriptor = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        return False
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        # Only this process could have created the file with O_EXCL.
        # Don't leave a partial document to be mistaken for valid settings.
        try:
            path.unlink()
        except OSError:
            pass
        raise
    return True
