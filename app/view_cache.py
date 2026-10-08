"""Read-only UI snapshots: the database and physical checks remain authoritative."""
from __future__ import annotations

from collections import OrderedDict
from copy import deepcopy
from pathlib import Path
from threading import RLock
import time
from typing import Any

_LOCK = RLock()
_ITEMS: OrderedDict[tuple[Any, ...], tuple[tuple[Any, ...], float, Any]] = OrderedDict()
_VERIFIED: set[str] = set()
_MAX_ITEMS = 24
_MAX_AGE_SECONDS = 600


def database_stamp(path: Path) -> tuple[Any, ...]:
    """Observe the SQLite database and its WAL, not just the main database mtime."""
    values: list[Any] = []
    for name in (str(path), str(path) + "-wal"):
        try:
            st = Path(name).stat()
            values.extend((st.st_mtime_ns, st.st_size))
        except OSError:
            values.extend((None, None))
    return tuple(values)


def get_snapshot(path: Path, group: str, *args: Any, max_age_seconds: int | None = None) -> Any | None:
    key = (str(path.resolve(strict=False)), group, *args)
    with _LOCK:
        row = _ITEMS.get(key)
        if row is None:
            return None
        stamp, born, value = row
        ttl = min(_MAX_AGE_SECONDS, max_age_seconds) if max_age_seconds is not None else _MAX_AGE_SECONDS
        if time.monotonic() - born > ttl or stamp != database_stamp(path):
            _ITEMS.pop(key, None)
            return None
        _ITEMS.move_to_end(key)
        return deepcopy(value)


def put_snapshot(path: Path, group: str, value: Any, *args: Any) -> None:
    key = (str(path.resolve(strict=False)), group, *args)
    with _LOCK:
        _ITEMS[key] = (database_stamp(path), time.monotonic(), deepcopy(value))
        _ITEMS.move_to_end(key)
        while len(_ITEMS) > _MAX_ITEMS:
            _ITEMS.popitem(last=False)


def needs_first_physical_check(path: Path) -> bool:
    with _LOCK:
        return str(path.resolve(strict=False)) not in _VERIFIED


def mark_physical_checked(path: Path) -> None:
    with _LOCK:
        _VERIFIED.add(str(path.resolve(strict=False)))


def invalidate(path: Path) -> None:
    prefix = str(path.resolve(strict=False))
    with _LOCK:
        for key in list(_ITEMS):
            if key[0] == prefix:
                _ITEMS.pop(key, None)
