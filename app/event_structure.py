from __future__ import annotations

from typing import Any


class EventPreviewError(ValueError):
    pass


def _clean_name(
    value: Any,
    field_name: str,
) -> str:
    name = str(value or "").strip()

    if not name:
        raise EventPreviewError(
            f"{field_name} fehlt."
        )

    forbidden = {
        "/",
        "\\",
        "\0",
    }

    if any(
        character in name
        for character in forbidden
    ):
        raise EventPreviewError(
            f"{field_name} enthält ein "
            "unzulässiges Zeichen."
        )

    return name


def _validate_date(
    value: Any,
    field_name: str,
) -> str:
    date_value = str(value or "").strip()

    if len(date_value) != 10:
        raise EventPreviewError(
            f"{field_name} ist ungültig."
        )

    if (
        date_value[4] != "-"
        or date_value[7] != "-"
    ):
        raise EventPreviewError(
            f"{field_name} ist ungültig."
        )

    return date_value


def _validate_time(
    value: Any,
    field_name: str,
) -> str:
    time_value = str(value or "").strip()

    if len(time_value) != 5:
        raise EventPreviewError(
            f"{field_name} ist ungültig."
        )

    if time_value[2] != ":":
        raise EventPreviewError(
            f"{field_name} ist ungültig."
        )

    return time_value


def _folder_triplet(
    indentation: str,
) -> list[str]:
    return [
        f"{indentation}├── Alle",
        f"{indentation}├── Sortiert",
        f"{indentation}└── Export",
    ]


def _capture_second(value: Any) -> str:
    return str(value or "")[:19]




def _build_no_event_preview(
    payload: dict[str, Any],
    available_families: list[dict[str, Any]],
) -> dict[str, Any]:
    from app.event_timeline import normalize_no_event_segments, EventTimelineError
    try:
        segments = normalize_no_event_segments(payload.get("no_event_segments") or [])
    except EventTimelineError as exc:
        raise EventPreviewError(str(exc)) from exc

    candidate_families = []
    for family in available_families:
        capture = _capture_second(family.get("selected_capture_time"))
        if not capture:
            continue
        if any(seg["start_datetime"] <= capture <= seg["end_datetime"] for seg in segments):
            candidate_families.append(family)

    if not candidate_families:
        raise EventPreviewError(
            "In den gewählten „Ohne Ereignis“-Zeitsegmenten wurden keine freien Dateifamilien gefunden."
        )

    selected_family_ids = sorted({int(f["family_id"]) for f in candidate_families})
    selected_day_keys = sorted({str(f.get("day_key") or _capture_second(f.get("selected_capture_time"))[:10]) for f in candidate_families})
    selected_file_count = sum(int(f.get("file_count", 0)) for f in candidate_families)
    start_date = segments[0]["day_key"]
    end_date = segments[-1]["day_key"]
    parent_folder = f"{start_date[5:7]} - Ohne Ereignis"

    preserve_day_folders = bool(payload.get("preserve_day_folders"))

    lines = [start_date[:4], f"└── {parent_folder}"]
    if preserve_day_folders:
        segment_days = []
        for segment in segments:
            day = segment["day_key"]
            if day not in segment_days:
                segment_days.append(day)
        for index, day in enumerate(segment_days):
            connector = "└──" if index == len(segment_days) - 1 else "├──"
            lines.append(f"    {connector} {day}")
            indent = "        " if index == len(segment_days) - 1 else "    │   "
            lines.extend(_folder_triplet(indent))
    else:
        lines.extend(["    ├── Alle", "    ├── Sortiert", "    └── Export"])

    lines.extend(["", "Zeitsegmente:"])
    for segment in segments:
        lines.append(f"{segment['day_key']} · {segment['start_time']}–{segment['end_time']}")
    lines.extend(["", f"Auswahl: {selected_file_count} Dateien, {len(selected_family_ids)} Familien"])

    return {
        "event_kind": "no_event",
        "event_name": "Ohne Ereignis",
        "parent_folder": parent_folder,
        "child_folder": None,
        "child_event_name": None,
        "uses_time_range": False,
        "preserve_day_folders": preserve_day_folders,
        # Legacy bounding values: canonical no-event time data is no_event_segments.
        "start_date": start_date,
        "end_date": end_date,
        "start_time": None,
        "end_time": None,
        "no_event_segments": segments,
        "selected_day_keys": selected_day_keys,
        "selected_family_ids": selected_family_ids,
        "selected_file_count": selected_file_count,
        "selected_family_count": len(selected_family_ids),
        "structure_lines": lines,
        "structure_text": "\n".join(lines),
    }

def build_event_preview(
    payload: dict[str, Any],
    available_families: list[dict[str, Any]],
) -> dict[str, Any]:
    if payload.get("child_segments"):
        raise EventPreviewError("Normale Ereignisse benötigen einen durchgehenden Beginn und ein Ende. Getrennte Belegungssegmente sind nicht zulässig.")
    selected_intervals = payload.get("selected_intervals") or []
    if selected_intervals and payload.get("event_kind", "event") == "event":
        from app.released_ranges import merge_intervals
        ranges = merge_intervals((v['start_datetime'], v['end_datetime']) for v in selected_intervals)
        if len(ranges) != 1 and not payload.get("existing_parent_event_id"):
            raise EventPreviewError("Die Auswahl ist nicht durchgehend. Bitte getrennte Ereignisse oder „Ohne Ereignis“ verwenden.")
    event_kind = str(
        payload.get(
            "event_kind",
            "event",
        )
    )

    if event_kind not in {
        "event",
        "no_event",
    }:
        raise EventPreviewError(
            "Unbekannte Ereignisart."
        )

    if event_kind == "no_event" and payload.get("no_event_segments"):
        return _build_no_event_preview(payload, available_families)

    start_date = _validate_date(
        payload.get("start_date"),
        "Beginn",
    )

    end_date = _validate_date(
        payload.get("end_date"),
        "Ende",
    )

    if end_date < start_date:
        raise EventPreviewError(
            "Das Enddatum liegt vor dem Beginn."
        )

    uses_time_range = bool(
        payload.get("uses_time_range")
    )

    preserve_day_folders = bool(
        payload.get("preserve_day_folders")
    )

    if event_kind == "no_event":
        preserve_day_folders = False
        uses_time_range = False

    requested_day_keys = []

    for value in (
        payload.get("selected_day_keys")
        or []
    ):
        day_key = str(value or "").strip()

        if day_key and day_key not in requested_day_keys:
            requested_day_keys.append(day_key)

    available_dated_families = [
        family
        for family in available_families
        if family.get("has_date")
        and family.get("day_key")
        and family.get("selected_capture_time")
    ]

    available_day_keys = {
        str(family["day_key"])
        for family in available_dated_families
    }

    # 0.18.0: Die Tagesauswahl ist nur ein Komfort-Startwert für das Formular.
    # Führend ist bei normalen Ereignissen immer der aktuell eingetragene
    # Datum-/Zeitbereich. Dadurch aktualisiert sich auch „Tagesordner behalten“
    # korrekt, wenn Beginn oder Ende nachträglich erweitert werden.
    candidate_families = [
        family
        for family in available_dated_families
        if start_date <= str(family["day_key"]) <= end_date
    ]

    start_time = None
    end_time = None
    child_name = None
    child_folder = None

    if uses_time_range:
        if str(payload.get("child_event_name") or "").strip():
            child_name = _clean_name(payload["child_event_name"], "Unterereignisname")

        start_time = _validate_time(
            payload.get("start_time"),
            "Startzeit",
        )

        end_time = _validate_time(
            payload.get("end_time"),
            "Endzeit",
        )

        start_second = (
            f"{start_date}T{start_time}:00"
        )
        end_second = (
            f"{end_date}T{end_time}:59"
        )

        if end_second < start_second or (
            start_date == end_date and end_time < start_time
        ):
            raise EventPreviewError(
                "Das Ende muss nach dem Beginn liegen."
            )

        candidate_families = [
            family
            for family in candidate_families
            if start_second
            <= _capture_second(
                family["selected_capture_time"]
            )
            <= end_second
        ]

        child_folder = (
            start_time.replace(":", "-")
            + " - "
            + end_time.replace(":", "-")
            + " - "
            + child_name
        ) if child_name else None

    from app.subevents import normalize_subevents
    try:
        subevents = normalize_subevents(payload.get('subevents') or [],
            f"{start_date}T{start_time or '00:00'}:00",f"{end_date}T{end_time or '23:59'}:59")
    except ValueError as error:
        raise EventPreviewError(str(error)) from error
    empty_subevents = []
    for subevent in subevents:
        matching = [
            family for family in candidate_families
            if subevent["start_datetime"]
            <= _capture_second(family["selected_capture_time"])
            <= subevent["end_datetime"]
        ]
        if not matching:
            empty_subevents.append({
                "name": subevent["name"],
                "start_datetime": subevent["start_datetime"],
                "end_datetime": subevent["end_datetime"],
                "folder_name": subevent["folder_name"],
            })

    requested_family_ids = {
        int(value)
        for value in (payload.get("selected_family_ids") or [])
    }

    if requested_family_ids:
        candidate_families = [
            family for family in candidate_families
            if int(family["family_id"]) in requested_family_ids
        ]

        found_ids = {int(family["family_id"]) for family in candidate_families}
        missing_ids = sorted(requested_family_ids - found_ids)
        if missing_ids:
            raise EventPreviewError(
                "Die ausgewählten Familien passen nicht vollständig "
                "zum Zeitraum oder sind nicht mehr verfügbar."
            )

    if not candidate_families:
        raise EventPreviewError(
            "Im gewählten freien Zeitraum wurden "
            "keine Dateifamilien gefunden."
        )

    selected_family_ids = sorted({
        int(family["family_id"])
        for family in candidate_families
    })

    selected_day_keys = sorted({
        str(family["day_key"])
        for family in candidate_families
        if family.get("day_key")
    })

    selected_file_count = sum(
        int(family.get("file_count", 0))
        for family in candidate_families
    )

    selected_family_count = len(
        selected_family_ids
    )

    if event_kind == "no_event":
        parent_name = "Ohne Ereignis"
        parent_folder = (
            f"{start_date[5:7]}"
            " - Ohne Ereignis"
        )
    else:
        parent_name = _clean_name(
            payload.get("event_name"),
            "Ereignisname",
        )

        parent_folder = (
            f"{start_date[5:]}"
            f" - {parent_name}"
        )

    lines = [
        start_date[:4],
        f"└── {parent_folder}",
    ]

    content_indentation = "    "

    if child_folder:
        lines.append(
            f"    └── {child_folder}"
        )

        content_indentation = "        "

    if (
        preserve_day_folders
        and selected_day_keys
    ):
        for index, day_key in enumerate(
            selected_day_keys
        ):
            is_last_day = (
                index
                == len(selected_day_keys) - 1
            )

            day_connector = (
                "└──"
                if is_last_day
                else "├──"
            )

            lines.append(
                f"{content_indentation}"
                f"{day_connector} "
                f"{day_key}"
            )

            child_indentation = (
                content_indentation
                + (
                    "    "
                    if is_last_day
                    else "│   "
                )
            )

            lines.extend(
                _folder_triplet(
                    child_indentation
                )
            )
    else:
        lines.extend(
            _folder_triplet(
                content_indentation
            )
        )

    from app.structure_view import render_structure
    lines = render_structure(start_date[:4],parent_folder,selected_day_keys,
        subevents or ([{'folder_name':child_folder}] if child_folder else []),preserve_day_folders)
    lines.extend([
        "",
        "Zeitraum:",
        (
            f"{start_date} {start_time}"
            if start_time
            else start_date
        ),
        (
            "bis "
            + (
                f"{end_date} {end_time}"
                if end_time
                else end_date
            )
        ),
        "",
        (
            f"Auswahl: {selected_file_count} Dateien, "
            f"{selected_family_count} Familien"
        ),
    ])

    return {
        "event_kind": event_kind,
        "event_name": parent_name,
        "parent_folder": parent_folder,
        "child_folder": child_folder,
        "child_event_name": child_name,
        "uses_time_range": uses_time_range,
        "preserve_day_folders": (
            preserve_day_folders
        ),
        "start_date": start_date,
        "end_date": end_date,
        "start_time": start_time,
        "end_time": end_time,
        "selected_day_keys": selected_day_keys,
        "selected_family_ids": selected_family_ids,
        "selected_file_count": selected_file_count,
        "selected_family_count": (
            selected_family_count
        ),
        "subevents": subevents,
        "empty_subevents": empty_subevents,
        "selected_intervals": selected_intervals,
        "existing_parent_event_id": str(payload.get("existing_parent_event_id") or "").strip() or None,
        "structure_lines": lines,
        "structure_text": "\n".join(lines),
    }

