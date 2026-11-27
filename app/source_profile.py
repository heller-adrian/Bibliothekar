"""Process-wide capability shared by the web app and container supervisor."""
import json
import os
from pathlib import Path

SOURCE_HELPER_ENABLED = os.environ.get("KAMERA_SOURCE_HELPER_ENABLED", "false").strip().lower() in {
    "1", "true", "yes", "on",
}

DISABLED_MESSAGE = "Der Wechselmedienzugriff ist in dieser Installation deaktiviert."


def removable_job(operation, trigger, device, source, result, removable_root):
    if operation not in {"folder_import", "sd_recheck", "sd_import"}:
        return False
    if isinstance(result, str):
        try:
            result = json.loads(result or "{}")
        except ValueError:
            return True
    if result is not None and not isinstance(result, dict):
        return True
    result = result or {}
    return bool(
        device or trigger in {"approved_sd", "usb_key"}
        or result.get("source_root_key") == "removable"
        or result.get("source_mode") in {"sd_card", "drive"}
        or (operation == "sd_recheck" and not result.get("source_root_key"))
        or (source and Path(source).is_relative_to(removable_root))
    )
