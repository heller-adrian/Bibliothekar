from __future__ import annotations

from typing import Any
from datetime import date, time

from app.event_naming import (
    DEFAULT_EVENT_NAMING,
    naming_snapshot_for_new_event,
    normalize_event_naming,
    render_event_folder_name,
    render_no_event_folder_name,
)


class EventPreviewError(ValueError):
    pass


def assigned_day_keys_by_event(connection: Any, event_id: str) -> dict[str, list[str]]:
    """Return actual capture days per physical event branch.

    Parent and child assignments are deliberately kept separate.  This is the
    read-only counterpart of the sort planner's branch_days map and prevents
    inspectors from copying every parent day into every subevent.
    """
    rows = connection.execute(
        """
        SELECT assigned.id AS assigned_event_id,
               COALESCE(ff.selected_capture_time, direct_ff.selected_capture_time)
                   AS selected_capture_time
        FROM event_assignments AS ea
        JOIN events AS assigned ON assigned.id = ea.event_id
        LEFT JOIN file_families AS ff ON ff.id = ea.family_id
        LEFT JOIN files AS direct_file ON direct_file.id = ea.file_id
        LEFT JOIN file_families AS direct_ff ON direct_ff.id = direct_file.family_id
        WHERE COALESCE(assigned.parent_event_id, assigned.id) = ?
        """,
        (event_id,),
    ).fetchall()

    days: dict[str, set[str]] = {}
    for row in rows:
        capture = str(row["selected_capture_time"] or "")
        day_key = capture[:10]
        if len(day_key) != 10:
            continue
        days.setdefault(str(row["assigned_event_id"]), set()).add(day_key)

    return {
        assigned_event_id: sorted(day_keys)
        for assigned_event_id, day_keys in days.items()
    }


def _clean_name(
    value: Any,
    field_name: str,
) -> str:
    name = str(value or "").strip()

    if not name:
        raise EventPreviewError(
            f"{field_name} fehlt."
        )

    # Validate new planning input only. Persisted historical folder names are
    # never rewritten by this check.
    forbidden = set('<>:"/\\|?*')

    if (any(character in name for character in forbidden)
        or any(ord(character) < 32 or ord(character) == 127 for character in name)
        or name.endswith('.')
        or name.split('.')[0].upper() in {'CON', 'PRN', 'AUX', 'NUL',
            *(f'COM{i}' for i in range(1, 10)), *(f'LPT{i}' for i in range(1, 10))}):
        raise EventPreviewError(
            f"{field_name} enthält ein "
            'für SMB unzulässiges Zeichen oder einen reservierten Ordnernamen. '
            'Bitte <>:"/\\|?*, Steuerzeichen und abschließende Punkte vermeiden.'
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

    try:
        date.fromisoformat(date_value)
    except ValueError as error:
        raise EventPreviewError(
            f"{field_name} ist ungültig."
        ) from error

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

    try:
        time.fromisoformat(time_value)
    except ValueError as error:
        raise EventPreviewError(f"{field_name} ist ungültig.") from error

    return time_value


def continuous_event_bounds(start_date, end_date, start_time=None, end_time=None):
    """Resolve the inclusive bounds of one continuous event."""
    start_day = _validate_date(start_date, "Beginn")
    end_day = _validate_date(end_date, "Ende")
    first = _validate_time(start_time, "Startzeit") if start_time is not None else "00:00"
    last = _validate_time(end_time, "Endzeit") if end_time is not None else "23:59"
    start, end = f"{start_day}T{first}:00", f"{end_day}T{last}:59"
    if end < start:
        raise EventPreviewError("Das Ende muss nach dem Beginn liegen.")
    return start, end


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


def _layout_state(payload: dict[str, Any]) -> dict[str, Any]:
    from app.event_layout import DEFAULT_LAYOUT, normalize_layout, validate_input_path
    raw = payload.get("folder_layout")
    if not isinstance(raw, dict):
        raw = {
            "structure_enabled": True,
            "input_path": "Alle",
            "layout": DEFAULT_LAYOUT,
        }
    layout = normalize_layout(raw.get("layout") or DEFAULT_LAYOUT)
    enabled = bool(
        payload.get(
            "create_subfolders",
            raw.get("structure_enabled", True),
        )
    )
    input_path = validate_input_path(
        layout,
        raw.get("input_path", "Alle"),
        structure_enabled=enabled,
    )
    return {
        "structure_enabled": enabled,
        "input_path": input_path,
        "layout": layout,
    }


def _build_no_event_preview(
    payload: dict[str, Any],
    available_families: list[dict[str, Any]],
) -> dict[str, Any]:
    if payload.get("subevents") or payload.get("child_segments"):
        raise EventPreviewError("„Ohne Ereignis“ besitzt keine semantischen Unterereignisse.")
    from app.event_timeline import normalize_no_event_segments, EventTimelineError
    try:
        segments = normalize_no_event_segments(payload.get("no_event_segments") or [])
    except EventTimelineError as exc:
        raise EventPreviewError(str(exc)) from exc

    months = {str(segment["day_key"])[:7] for segment in segments}
    if len(months) != 1:
        raise EventPreviewError(
            "„Ohne Ereignis“ darf nur Tage und Zeitsegmente innerhalb eines Kalendermonats enthalten. "
            "Bitte für jeden Monat eine eigene Sammlung anlegen."
        )
    month_key = next(iter(months))
    raw_naming = payload.get("folder_naming") or normalize_event_naming({})
    naming = (
        dict(raw_naming)
        if isinstance(raw_naming, dict) and str(raw_naming.get("mode") or "") == "locked"
        else naming_snapshot_for_new_event(raw_naming)
    )

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
    if str(naming.get("mode") or "") == "locked":
        parent_folder = str(naming.get("locked_folder_name") or "").strip()
        if not parent_folder:
            parent_folder = render_no_event_folder_name(month_key, normalize_event_naming({}))
        no_event_label = str(payload.get("event_name") or "Ohne Ereignis").strip() or "Ohne Ereignis"
    else:
        parent_folder = render_no_event_folder_name(month_key, naming)
        no_event_label = normalize_event_naming(naming)["no_event_label"]

    preserve_day_folders = bool(payload.get("preserve_day_folders"))
    folder_layout = _layout_state(payload)

    from app.structure_view import render_structure
    segment_days = []
    for segment in segments:
        day = segment["day_key"]
        if day not in segment_days:
            segment_days.append(day)
    lines = render_structure(
        start_date[:4],
        parent_folder,
        segment_days,
        (),
        preserve_day_folders,
        layout_state=folder_layout,
    )
    lines.extend(["", "Zeitsegmente:"])
    for segment in segments:
        lines.append(f"{segment['day_key']} · {segment['start_time']}–{segment['end_time']}")
    lines.extend(["", f"Auswahl: {selected_file_count} Dateien, {len(selected_family_ids)} Familien"])

    return {
        "event_kind": "no_event",
        "event_name": parent_folder,
        "parent_folder": parent_folder,
        "child_folder": None,
        "child_event_name": None,
        "uses_time_range": False,
        "preserve_day_folders": preserve_day_folders,
        "folder_layout": folder_layout,
        "folder_naming": naming,
        "create_subfolders": bool(folder_layout["structure_enabled"]),
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
    # Seit 0.43.0 definieren Tageskarten keine Belegungssegmente mehr.
    # Ein normales Ereignis ist ausschließlich der durchgehende Beginn-/Ende-
    # Zeitraum des Formulars. Fotofreie Kalendertage und nicht angehakte
    # Tageskarten innerhalb dieses Bereichs sind deshalb keine „Lücken“.
    # Nur Erweiterungen bestehender Ereignisse verwenden selected_intervals
    # weiterhin als expliziten neu hinzukommenden Bereich.
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
    folder_layout = _layout_state(payload)

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

        start_second, end_second = continuous_event_bounds(
            start_date, end_date, payload.get("start_time") or "", payload.get("end_time") or "",
        )
        start_time, end_time = start_second[11:16], end_second[11:16]

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

    raw_naming = payload.get("folder_naming") or normalize_event_naming({})
    naming = (
        dict(raw_naming)
        if isinstance(raw_naming, dict) and str(raw_naming.get("mode") or "") == "locked"
        else naming_snapshot_for_new_event(raw_naming)
    )
    if "subevent_prefix_enabled" in payload:
        naming = dict(naming)
        naming["subevent_prefix_enabled"] = bool(payload.get("subevent_prefix_enabled"))

    from app.event_layout import resolve_layout_choice
    from app.subevents import normalize_subevents
    try:
        subevents = normalize_subevents(
            payload.get('subevents') or [],
            f"{start_date}T{start_time or '00:00'}:00",
            f"{end_date}T{end_time or '23:59'}:59",
            naming=naming,
        )
        for child in subevents:
            if child.get('folder_layout') is not None:
                shape = resolve_layout_choice(child['folder_layout'], folder_layout, payload.get('default_folder_layout'))
                if child['folder_layout'].get('mode') != 'inherit':
                    child['folder_layout'] = shape
        folders = [child['folder_name'].casefold() for child in subevents if child['folder_name']]
        if len(set(folders)) != len(folders):
            raise EventPreviewError('Mehrere Unterereignisse beanspruchen denselben Zielordner.')
    except ValueError as error:
        raise EventPreviewError(str(error)) from error
    requested_family_ids = {
        int(value)
        for value in (payload.get("selected_family_ids") or [])
    }

    if requested_family_ids:
        # Die sichtbare Tages-/Segmentauswahl definiert den Quellbestand,
        # nicht eine Pflicht, jede angeklickte Familie in den später enger
        # eingetragenen Zeitraum zu zwingen. Familien außerhalb des konkret
        # gewählten Zeitfensters bleiben einfach frei. Blockiert wird nur,
        # wenn eine explizit angeklickte Familie tatsächlich nicht mehr zum
        # verfügbaren Quellbestand gehört.
        available_requested_ids = {
            int(family["family_id"])
            for family in available_dated_families
        }
        unavailable_ids = sorted(
            requested_family_ids - available_requested_ids
        )
        if unavailable_ids:
            raise EventPreviewError(
                "Die Auswahl ist nicht mehr aktuell. Mindestens eine "
                "Dateifamilie ist nicht mehr verfügbar."
            )

        candidate_families = [
            family for family in candidate_families
            if int(family["family_id"]) in requested_family_ids
        ]

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

    structure_subevents = []
    empty_subevents = []
    empty_subevent_days = []
    child_family_ids = set()

    for subevent in subevents:
        matching = [
            family for family in candidate_families
            if subevent["start_datetime"]
            <= _capture_second(family["selected_capture_time"])
            <= subevent["end_datetime"]
        ]
        matching_day_keys = sorted({
            str(family["day_key"])
            for family in matching
            if family.get("day_key")
        })
        child_family_ids.update(
            int(family["family_id"]) for family in matching
        )
        child_layout = resolve_layout_choice(subevent.get("folder_layout"), folder_layout)
        structure_subevents.append({
            **subevent,
            "folder_layout": child_layout,
            "day_keys": matching_day_keys,
        })

        if not matching:
            empty_subevents.append({
                "name": subevent["name"],
                "start_datetime": subevent["start_datetime"],
                "end_datetime": subevent["end_datetime"],
                "folder_name": subevent["folder_name"],
            })
            continue

        # Fotofreie Kalendertage innerhalb eines definierten Unterereignisses
        # sind keine strukturellen Lücken.  Tagesordner entstehen nur dort,
        # wo tatsächlich Aufnahmen vorhanden sind.

    if subevents:
        parent_structure_day_keys = sorted({
            str(family["day_key"])
            for family in candidate_families
            if family.get("day_key")
            and int(family["family_id"]) not in child_family_ids
        })
    else:
        parent_structure_day_keys = selected_day_keys

    if event_kind == "no_event":
        if str(naming.get("mode") or "") == "locked":
            parent_name = str(payload.get("event_name") or "Ohne Ereignis").strip() or "Ohne Ereignis"
            parent_folder = str(naming.get("locked_folder_name") or "").strip()
            if not parent_folder:
                parent_folder = render_no_event_folder_name(start_date[:7], normalize_event_naming({}))
        else:
            parent_name = normalize_event_naming(naming)["no_event_label"]
            parent_folder = render_no_event_folder_name(start_date[:7], naming)
    else:
        parent_name = _clean_name(
            payload.get("event_name"),
            "Ereignisname",
        )
        parent_folder = render_event_folder_name(
            event_name=parent_name,
            start_date=start_date,
            end_date=end_date,
            start_time=start_time,
            end_time=end_time,
            uses_time_range=uses_time_range,
            naming=naming,
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
    lines = render_structure(
        start_date[:4],
        parent_folder,
        parent_structure_day_keys,
        structure_subevents
        or ([{"folder_name": child_folder, "day_keys": selected_day_keys}] if child_folder else []),
        preserve_day_folders,
        layout_state=folder_layout,
    )
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
        "folder_layout": folder_layout,
        "folder_naming": naming,
        "create_subfolders": bool(folder_layout["structure_enabled"]),
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
        "empty_subevent_days": empty_subevent_days,
        "selected_intervals": selected_intervals,
        "existing_parent_event_id": str(payload.get("existing_parent_event_id") or "").strip() or None,
        "structure_lines": lines,
        "structure_text": "\n".join(lines),
    }
