from __future__ import annotations

from typing import Any
import os
import re


DEFAULT_NO_EVENT_LABEL = "No Event"


def _default_no_event_label() -> str:
    # Physical names for newly planned events do not follow the UI language.
    # Saved naming snapshots retain their original labels unchanged.
    return DEFAULT_NO_EVENT_LABEL

# 0.43.0 stored one exclusive mode. Keep those values readable so existing
# event snapshots never change their physical folder naming after the patch.
SUBEVENT_PREFIX_MODES = {
    "date",
    "date_range",
    "time",
    "year",
    "none",
    "legacy_datetime_range",
}

DEFAULT_EVENT_NAMING = {
    "no_event_label": DEFAULT_NO_EVENT_LABEL,
    # Normal events: start date by default; range/year/time are opt-in.
    "date_mode": "start",
    "include_year": False,
    "include_time": False,
    # Monthly collection folders have no coherent start/end time range.
    # They may optionally include the year before the month.
    "no_event_include_year": False,
    # 0.43.1: semantic child folders use the same combinable controls as
    # normal events instead of one mutually exclusive mode.
    "subevent_date_mode": "start",
    "subevent_include_year": False,
    "subevent_include_time": False,
    "subevent_prefix_enabled": True,
}


class EventNamingError(ValueError):
    pass


def _clean_component(value: Any, *, field: str) -> str:
    text = " ".join(str(value or "").split()).strip()
    if (
        not text
        or text in {".", ".."}
        or "/" in text
        or "\\" in text
        or "\x00" in text
    ):
        raise EventNamingError(
            f"{field} muss ein sicherer einzelner Ordnername sein."
        )
    return text


def normalize_event_naming(value: Any) -> dict[str, Any]:
    raw = value if isinstance(value, dict) else {}

    no_event_label = _clean_component(
        raw.get("no_event_label", _default_no_event_label()),
        field="Bezeichnung für Ohne Ereignis",
    )

    date_mode = str(raw.get("date_mode") or "start").strip().lower()
    if date_mode not in {"start", "range"}:
        raise EventNamingError(
            "Datumsdarstellung muss „start“ oder „range“ sein."
        )

    legacy_subevent_mode = str(raw.get("subevent_prefix_mode") or "").strip().lower()
    if legacy_subevent_mode and legacy_subevent_mode not in SUBEVENT_PREFIX_MODES:
        raise EventNamingError("Unbekannter Namenspräfix für Unterereignisse.")

    has_composite_subevent_naming = any(
        key in raw
        for key in (
            "subevent_date_mode",
            "subevent_include_year",
            "subevent_include_time",
        )
    )

    if has_composite_subevent_naming:
        subevent_date_mode = str(
            raw.get("subevent_date_mode")
            or DEFAULT_EVENT_NAMING["subevent_date_mode"]
        ).strip().lower()
        subevent_include_year = bool(raw.get("subevent_include_year", False))
        subevent_include_time = bool(raw.get("subevent_include_time", False))
    else:
        # Migrate the 0.43.0 settings surface into the combinable 0.43.1
        # controls. Existing event snapshots still keep the old mode key and
        # are rendered below with their exact old semantics.
        mapping = {
            "date": ("start", False, False),
            "date_range": ("range", False, False),
            "time": ("start", False, True),
            "year": ("start", True, False),
            "none": ("start", False, False),
            "legacy_datetime_range": ("range", False, True),
        }
        (
            subevent_date_mode,
            subevent_include_year,
            subevent_include_time,
        ) = mapping.get(
            legacy_subevent_mode,
            (
                DEFAULT_EVENT_NAMING["subevent_date_mode"],
                DEFAULT_EVENT_NAMING["subevent_include_year"],
                DEFAULT_EVENT_NAMING["subevent_include_time"],
            ),
        )

    if subevent_date_mode not in {"start", "range"}:
        raise EventNamingError(
            "Datumsdarstellung für Unterereignisse muss „start“ oder „range“ sein."
        )

    prefix_default = (
        False
        if legacy_subevent_mode == "none" and "subevent_prefix_enabled" not in raw
        else DEFAULT_EVENT_NAMING["subevent_prefix_enabled"]
    )

    result = {
        "no_event_label": no_event_label,
        "date_mode": date_mode,
        "include_year": bool(raw.get("include_year", False)),
        "include_time": bool(raw.get("include_time", False)),
        "no_event_include_year": bool(raw.get("no_event_include_year", False)),
        "subevent_date_mode": subevent_date_mode,
        "subevent_include_year": subevent_include_year,
        "subevent_include_time": subevent_include_time,
        "subevent_prefix_enabled": bool(
            raw.get("subevent_prefix_enabled", prefix_default)
        ),
    }

    # Preserve the old key only when it already exists. This freezes 0.43.0
    # event snapshots while new settings/snapshots use the composite model.
    if legacy_subevent_mode:
        result["subevent_prefix_mode"] = legacy_subevent_mode

    return result


def naming_from_library_settings(settings: Any) -> dict[str, Any]:
    raw = settings if isinstance(settings, dict) else {}
    result = normalize_event_naming(raw.get("event_naming") or {})
    # Library settings are migrated into the new combinable model immediately.
    # Existing per-event snapshots are handled separately and stay frozen.
    result.pop("subevent_prefix_mode", None)
    return result


def _date_token(value: str, *, include_year: bool) -> str:
    text = str(value or "").strip()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        raise EventNamingError("Ungültiges Datum für Ereignisordner.")
    return text if include_year else text[5:]


def _time_token(value: str | None) -> str:
    text = str(value or "").strip()
    if not re.fullmatch(r"\d{2}:\d{2}", text):
        raise EventNamingError("Ungültige Uhrzeit für Ereignisordner.")
    return text.replace(":", "-")


def render_event_folder_name(
    *,
    event_name: str,
    start_date: str,
    end_date: str,
    start_time: str | None,
    end_time: str | None,
    uses_time_range: bool,
    naming: Any,
) -> str:
    raw = naming if isinstance(naming, dict) else {}

    # Existing 0.32.x events that do not yet have a naming snapshot are
    # deliberately locked to their already persisted folder. A later settings
    # change must never rename an existing physical event implicitly.
    if str(raw.get("mode") or "") == "locked":
        locked = _clean_component(
            raw.get("locked_folder_name"),
            field="Bestehender Ereignisordner",
        )
        return locked

    normalized = normalize_event_naming(raw)
    name = _clean_component(event_name, field="Ereignisname")

    # Even if years are normally omitted, a year-spanning event must remain
    # unambiguous. The event continues to live below its start-year root.
    cross_year = str(start_date)[:4] != str(end_date)[:4]
    include_year = normalized["include_year"] or cross_year
    start = _date_token(start_date, include_year=include_year)
    end = _date_token(end_date, include_year=include_year)

    if normalized["date_mode"] == "range" and end_date != start_date:
        date_part = f"{start}–{end}"
    else:
        date_part = start

    if normalized["include_time"] and uses_time_range:
        start_clock = _time_token(start_time)
        end_clock = _time_token(end_time)
        if normalized["date_mode"] == "range" and end_date != start_date:
            date_part = f"{start} {start_clock}–{end} {end_clock}"
        else:
            date_part = f"{date_part} · {start_clock}–{end_clock}"

    return f"{date_part} - {name}"


def _render_legacy_subevent_prefix(
    *,
    mode: str,
    start: str,
    end: str,
    name: str,
    prefix_enabled: bool,
    include_year: bool,
) -> str:
    if not prefix_enabled or mode == "none":
        return name
    if mode == "legacy_datetime_range":
        return (
            f"{start[5:16].replace('T', ' ').replace(':', '-')} - "
            f"{end[5:16].replace('T', ' ').replace(':', '-')} - {name}"
        )

    start_date = _date_token(start[:10], include_year=include_year)
    end_date = _date_token(end[:10], include_year=include_year)
    if mode == "date":
        prefix = start_date
    elif mode == "date_range":
        prefix = start_date if start[:10] == end[:10] else f"{start_date}–{end_date}"
    elif mode == "time":
        prefix = f"{_time_token(start[11:16])}–{_time_token(end[11:16])}"
    elif mode == "year":
        prefix = start[:4] if start[:4] == end[:4] else f"{start[:4]}–{end[:4]}"
    else:
        prefix = ""
    return f"{prefix} - {name}" if prefix else name


def render_subevent_folder_name(
    *,
    event_name: str,
    start_datetime: str,
    end_datetime: str,
    naming: Any,
    parent_start_datetime: str | None = None,
    parent_end_datetime: str | None = None,
) -> str:
    """Render one semantic child-event folder.

    New 0.43.1 snapshots combine year/time/range independently. A persisted
    0.43.0 exclusive mode remains byte-for-byte compatible.
    """
    raw = naming if isinstance(naming, dict) else {}
    normalized = normalize_event_naming(raw)
    name = _clean_component(event_name, field="Unterereignisname")
    start = str(start_datetime or "")[:19]
    end = str(end_datetime or "")[:19]
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", start):
        raise EventNamingError("Ungültiger Beginn für Unterereignis.")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", end):
        raise EventNamingError("Ungültiges Ende für Unterereignis.")

    parent_start = str(parent_start_datetime or start)[:19]
    parent_end = str(parent_end_datetime or end)[:19]
    cross_year = (
        start[:4] != end[:4]
        or parent_start[:4] != parent_end[:4]
    )

    legacy_mode = str(raw.get("subevent_prefix_mode") or "").strip().lower()
    if legacy_mode:
        return _render_legacy_subevent_prefix(
            mode=legacy_mode,
            start=start,
            end=end,
            name=name,
            prefix_enabled=normalized["subevent_prefix_enabled"],
            include_year=cross_year,
        )

    if not normalized["subevent_prefix_enabled"]:
        return name

    include_year = normalized["subevent_include_year"] or cross_year
    start_date = _date_token(start[:10], include_year=include_year)
    end_date = _date_token(end[:10], include_year=include_year)

    if (
        normalized["subevent_date_mode"] == "range"
        and start[:10] != end[:10]
    ):
        date_part = f"{start_date}–{end_date}"
    else:
        date_part = start_date

    if normalized["subevent_include_time"]:
        start_clock = _time_token(start[11:16])
        end_clock = _time_token(end[11:16])
        if (
            normalized["subevent_date_mode"] == "range"
            and start[:10] != end[:10]
        ):
            date_part = f"{start_date} {start_clock}–{end_date} {end_clock}"
        else:
            date_part = f"{date_part} · {start_clock}–{end_clock}"

    return f"{date_part} - {name}"


def render_no_event_folder_name(month_key: str, naming: Any) -> str:
    normalized = normalize_event_naming(naming)
    month = str(month_key or "").strip()
    if not re.fullmatch(r"\d{4}-\d{2}", month):
        raise EventNamingError("Ungültiger Monat für Sammelordner.")
    date_part = month if normalized["no_event_include_year"] else month[5:7]
    return f"{date_part} - {normalized['no_event_label']}"


def legacy_naming_for_existing_event(
    *,
    event_kind: Any,
    folder_name: Any,
    event_name: Any,
) -> dict[str, Any]:
    """Return the pre-0.33 naming policy for an existing event."""
    if str(event_kind or "event") != "no_event":
        naming = normalize_event_naming({})
        naming["subevent_prefix_mode"] = "legacy_datetime_range"
        naming["subevent_prefix_enabled"] = True
        return naming

    folder = str(folder_name or "").strip()
    name = str(event_name or "").strip()
    include_year = False
    match = re.match(r"^(\d{4}-)?\d{2}\s*-\s*(.+)$", folder)
    if match and match.group(2).strip():
        include_year = bool(match.group(1))
        label = match.group(2).strip()
    else:
        match = re.match(r"^(\d{4}-)?\d{2}\s*-\s*(.+)$", name)
        if match and match.group(2).strip():
            include_year = bool(match.group(1))
            label = match.group(2).strip()
        else:
            label = name or DEFAULT_NO_EVENT_LABEL

    naming = normalize_event_naming({
        "no_event_label": label,
        "no_event_include_year": include_year,
    })
    naming["subevent_prefix_mode"] = "legacy_datetime_range"
    naming["subevent_prefix_enabled"] = True
    return naming


def protect_existing_no_event_folder(
    *,
    folder_name: Any,
    month_key: str,
    naming: Any,
) -> dict[str, Any]:
    """Preserve the confirmed physical name of an existing No Event collection.

    A manual root rename updates events.folder_name independently of its
    historical per-event naming template. If that template would regenerate a
    different folder, it is stale for this existing event. Never interpret
    changing time segments as an implicit request to rename its archive.
    New collections still use the configured library naming template.
    """
    folder = _clean_component(folder_name, field="Bestehender Ereignisordner")
    snapshot = dict(naming) if isinstance(naming, dict) else {}
    if snapshot.get("mode") == "locked":
        # The physical DB name is authoritative even if an old lock differs.
        return {**snapshot, "mode": "locked", "locked_folder_name": folder}
    try:
        matches = render_no_event_folder_name(month_key, snapshot) == folder
    except EventNamingError:
        matches = False
    if matches:
        return snapshot
    # Preserve the exact user-confirmed name; do not try to infer locale,
    # punctuation, date prefix, or an implicit month-dependent rename.
    return {**snapshot, "mode": "locked", "locked_folder_name": folder}


def naming_snapshot_for_new_event(naming: Any) -> dict[str, Any]:
    """Return a stable per-event snapshot.

    The snapshot is persisted with the event. Settings changes only influence
    events created afterwards.
    """
    return normalize_event_naming(naming)
