from __future__ import annotations

from typing import Any
import re


DEFAULT_NO_EVENT_LABEL = "Ohne Ereignis"

DEFAULT_EVENT_NAMING = {
    "no_event_label": DEFAULT_NO_EVENT_LABEL,
    # Normal events: start date by default; range/year/time are opt-in.
    "date_mode": "start",
    "include_year": False,
    "include_time": False,
    # Monthly collection folders have no coherent start/end time range.
    # They may optionally include the year before the month.
    "no_event_include_year": False,
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
        raw.get("no_event_label", DEFAULT_NO_EVENT_LABEL),
        field="Bezeichnung für Ohne Ereignis",
    )

    date_mode = str(raw.get("date_mode") or "start").strip().lower()
    if date_mode not in {"start", "range"}:
        raise EventNamingError(
            "Datumsdarstellung muss „start“ oder „range“ sein."
        )

    return {
        "no_event_label": no_event_label,
        "date_mode": date_mode,
        "include_year": bool(raw.get("include_year", False)),
        "include_time": bool(raw.get("include_time", False)),
        "no_event_include_year": bool(raw.get("no_event_include_year", False)),
    }


def naming_from_library_settings(settings: Any) -> dict[str, Any]:
    raw = settings if isinstance(settings, dict) else {}
    return normalize_event_naming(raw.get("event_naming") or {})


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

    start = _date_token(start_date, include_year=normalized["include_year"])
    end = _date_token(end_date, include_year=normalized["include_year"])

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
    """Return the pre-0.33 naming policy for an existing event.

    Existing 0.32.x events must not suddenly adopt a newly configured 0.33
    naming template. They must, however, keep the old behaviour when the user
    intentionally edits name/date: legacy normal events still use MM-DD -
    Name, and legacy no-event collections keep their historical label.
    """
    if str(event_kind or "event") != "no_event":
        return normalize_event_naming({})

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

    return normalize_event_naming({
        "no_event_label": label,
        "no_event_include_year": include_year,
    })


def naming_snapshot_for_new_event(naming: Any) -> dict[str, Any]:
    """Return a stable per-event snapshot.

    The snapshot is persisted with the event. Settings changes only influence
    events created afterwards.
    """
    return normalize_event_naming(naming)
