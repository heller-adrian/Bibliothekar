"""Read-only stack diagnostics for bounded concurrency regression tests.

All output stays in the isolated synthetic AUDIT_OUTPUT. No locks, original
media, application state or running jobs are changed by this observer.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import sys
import threading
import time
import traceback


def snapshot(label: str, threads, **details) -> dict:
    frames = sys._current_frames()
    entries = []
    for thread in threads:
        frame = frames.get(thread.ident)
        entries.append({
            "name": thread.name,
            "ident": thread.ident,
            "alive": thread.is_alive(),
            "stack": traceback.format_stack(frame, limit=40) if frame else [],
        })
    record = {
        "label": label,
        "monotonic_ns": time.monotonic_ns(),
        "threads": entries,
        "details": details,
    }
    folder = os.environ.get("AUDIT_OUTPUT")
    if folder:
        root = Path(folder).resolve()
        if root.is_dir() and label.replace("-", "").replace("_", "").isalnum():
            (root / ("thread-" + label + ".json")).write_text(
                json.dumps(record, indent=2, ensure_ascii=False, default=str),
                encoding="utf-8",
            )
    return record
