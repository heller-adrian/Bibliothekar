"""Build and persist manual legacy moves without changing the archive catalogue."""
from bisect import bisect_left, bisect_right
from collections import Counter
from contextlib import closing, ExitStack
from datetime import datetime
from functools import lru_cache
from itertools import groupby
import json
import os
from pathlib import Path, PurePosixPath
import sqlite3
import stat
from uuid import uuid4

from app import legacy_adoption_dataset as dataset
from app.database import database_connection
from app.event_inventory import event_root_relative
from app.event_layout import ensure_event_layout_snapshot, get_global_default, layout_paths, resolve_layout_choice
from app.event_leaf_layouts import effective_leaf_layouts
from app.event_naming import (
    naming_from_library_settings, naming_snapshot_for_new_event,
    render_event_folder_name, render_no_event_folder_name,
)
from app.event_structure import continuous_event_bounds
from app.free_time import free_ranges_for_day
from app.event_timeline import continuous_event_overlaps, no_event_segment_overlaps, normalize_no_event_segments, normal_event_ranges
from app.legacy_adoption_inventory import _job
from app.legacy_adoption_mode import require_no_managed_data
from app.legacy_adoption_paths import (
    AdoptionError, bound_directory, bound_file, bound_sha256, file_identity, relative_parent,
    target_key, validate_target, walk_bound_files,
)
from app.metadata import LOCAL_TIMEZONE
from app.operation_health import read_session
from app.released_ranges import merge_intervals
from app.subevents import assignment_target, normalize_subevents


MAX_PLAN_ITEMS = 2000
MAX_DRAFT_CONFLICTS = 50


def _event_id():
    return "EVENT_" + uuid4().hex.upper()


def _local_capture(value):
    result = datetime.fromisoformat(value)
    if result.year <= 1904 or len(value) < 16:
        raise AdoptionError("Die bestätigte Aufnahmezeit benötigt Datum und Uhrzeit.")
    if result.tzinfo is None:
        result = result.replace(tzinfo=LOCAL_TIMEZONE)
    return result.isoformat()


def _layout(definition, defaults, inherited=None):
    layout = resolve_layout_choice(definition.get("folder_layout"), inherited or defaults, defaults)
    for path in layout_paths(layout["layout"]):
        validate_target(path)
    return layout


def _existing_event(connection, event_id):
    row = connection.execute(
        """SELECT * FROM events WHERE id = ? AND status = 'archived' AND parent_event_id IS NULL
              AND pending_delete = 0 AND coalesce(linkage_kind, '') = ''""", (event_id,),
    ).fetchone()
    if row is None:
        raise AdoptionError("Das ausgewählte Archivereignis ist nicht verfügbar.")
    event = dict(row)
    if connection.execute(
        """SELECT 1 FROM event_change_requests WHERE event_id = ?
            AND status IN ('aenderbar_vorschlagen', 'aenderbar_bestaetigt')""", (event_id,),
    ).fetchone():
        raise AdoptionError("Für das Archivereignis ist bereits ein Änderungsauftrag offen.")
    children = [dict(child) for child in connection.execute(
        "SELECT * FROM events WHERE parent_event_id = ? ORDER BY start_datetime, id", (event_id,),
    )]
    segments = [dict(segment) for segment in connection.execute(
        "SELECT * FROM event_time_segments WHERE event_id = ? ORDER BY start_datetime, id", (event_id,),
    )]
    ranges = ([(segment["start_datetime"], segment["end_datetime"]) for segment in segments]
              if row["event_kind"] == "no_event" else normal_event_ranges(connection, event_id))
    if not ranges:
        raise AdoptionError("Für das Archivereignis fehlen zuordenbare Zeitbereiche.")
    with read_session():
        layout = ensure_event_layout_snapshot(connection, event_id, now="")
    return {
        **event, "existing": True, "children": children, "segments": segments, "ranges": ranges,
        "folder_layout": layout,
        "leaf_layouts": effective_leaf_layouts(connection, event_id),
    }


def _draft_event(connection, definition, naming, defaults, *, allow_existing=False):
    if "existing_id" in definition:
        if not allow_existing:
            raise AdoptionError("Vorhandene Archivereignisse können bei der Ersteinrichtung nicht ergänzt werden.")
        return _existing_event(connection, definition["existing_id"])
    kind = definition.get("event_kind", "event")
    parent_layout = _layout(definition, defaults)
    if kind == "event":
        if definition.get("subevent_prefix_enabled") is not None:
            naming = {**naming, "subevent_prefix_enabled": definition["subevent_prefix_enabled"]}
        start_time, end_time = definition.get("start_time"), definition.get("end_time")
        explicit_time = start_time is not None or end_time is not None
        start, end = continuous_event_bounds(
            definition.get("start_date"), definition.get("end_date"),
            (start_time or "") if explicit_time else None,
            (end_time or "") if explicit_time else None,
        )
        uses_time_range = start[11:] != "00:00:00" or end[11:] != "23:59:59"
        segments = []
        ranges = [(start, end)]
        name = str(definition.get("name") or "").strip()
        folder = render_event_folder_name(
            event_name=name, start_date=start[:10], end_date=end[:10],
            start_time=start_time, end_time=end_time, uses_time_range=uses_time_range, naming=naming,
        )
        definitions = definition.get("children") or []
        normalized = normalize_subevents(
            [{**item, "id": str(index)} for index, item in enumerate(definitions)], start, end, naming=naming,
        )
        children = [
            {**child, "id": _event_id(),
             "folder_layout": _layout(definitions[int(child["id"])], defaults, inherited=parent_layout)
             if child["folder_name"] else parent_layout}
            for child in normalized
        ]
        child_folders = [child["folder_name"] for child in children if child["folder_name"]]
        child_names = {target_key(folder) for folder in child_folders}
        if len(child_names) != len(child_folders):
            raise AdoptionError("Mehrere Unterereignisse beanspruchen denselben Zielordner.")
        if parent_layout["structure_enabled"] and not definition.get("preserve_day_folders"):
            if child_names.intersection(target_key(node["name"]) for node in parent_layout["layout"]["nodes"]):
                raise AdoptionError("Unterereignis und Ordnerstruktur beanspruchen denselben Zielordner.")
    elif kind == "no_event":
        segments = normalize_no_event_segments(definition.get("segments"))
        if len({segment["day_key"][:7] for segment in segments}) != 1 or definition.get("children"):
            raise AdoptionError("Ein Sammelordner umfasst einen Monat und besitzt keine Unterereignisse.")
        ranges = [(segment["start_datetime"], segment["end_datetime"]) for segment in segments]
        start, end = ranges[0][0], ranges[-1][1]
        name = naming["no_event_label"]
        folder = render_no_event_folder_name(start[:7], naming)
        children = []
    else:
        raise AdoptionError("Unbekannte Ereignisart.")
    return {
        "id": _event_id(), "existing": False, "name": name, "folder_name": folder,
        "event_kind": kind, "start_datetime": start, "end_datetime": end, "ranges": ranges,
        "children": children, "segments": segments,
        "preserve_day_folders": bool(definition.get("preserve_day_folders")),
        "folder_layout": parent_layout, "leaf_layouts": {}, "naming": naming,
    }


def _draft_intervals(events):
    return sorted(
        (start, end, index)
        for index, event in enumerate(events)
        for start, end in merge_intervals(event["ranges"])
    )


def _draft_overlaps(intervals):
    """Yield a conflicting pair per overlapping interval, in chronological order."""
    furthest = None
    for current in intervals:
        if furthest is not None and current[0] <= furthest[1] and current[2] != furthest[2]:
            yield furthest, current
        if furthest is None or current[1] > furthest[1]:
            furthest = current


def _assert_timeline(connection, job_id, events):
    for event in events:
        for start, end in event["ranges"]:
            normal = continuous_event_overlaps(connection, job_id, start, end, exclude_event_id=event["id"])
            free = no_event_segment_overlaps(connection, job_id, start, end, exclude_event_id=event["id"])
            if normal or free:
                conflict = (normal or free)[0]
                raise AdoptionError("Zeitüberschneidung mit „" + conflict["name"] + "“. "
                                    "Prüfe den gespeicherten Zeitraum.")
    intervals = _draft_intervals(events)
    if len({event["id"] for event in events}) != len(events) or next(_draft_overlaps(intervals), None):
        raise AdoptionError("Die im Auftrag gewählten Ereignisse überschneiden sich.")
    return intervals


def _assigned_index(intervals, starts, capture):
    if not capture:
        return None
    time = capture[:19]
    at = bisect_right(starts, time) - 1
    return intervals[at][2] if at >= 0 and time <= intervals[at][1] else None


def preview_draft(library, job_id, draft, *, allow_existing=False):
    """Read-only planning feedback, never a move/registration authority."""
    with database_connection(library.database_path) as connection:
        connection.execute('BEGIN')
        if not allow_existing:
            require_no_managed_data(connection)
        job = _job(connection, library.library_id, job_id)
        if job['state'] != 'inventoried':
            raise AdoptionError('Die Inventur muss zuerst abgeschlossen werden.')
        definitions = draft.get('events') or []
        if len(definitions) > MAX_PLAN_ITEMS:
            raise AdoptionError(f"Pro Auftrag sind bis zu {MAX_PLAN_ITEMS} Planobjekte möglich.")
        naming = naming_snapshot_for_new_event(naming_from_library_settings(library.settings))
        defaults = get_global_default(connection)
        events = [
            _draft_event(connection, definition, naming, defaults, allow_existing=allow_existing)
            for definition in definitions
        ]
        intervals = _draft_intervals(events)
        conflicts = []
        for index, event in enumerate(events):
            for start, end in event['ranges']:
                existing = continuous_event_overlaps(connection, job_id, start, end, exclude_event_id=event['id'])
                existing += no_event_segment_overlaps(connection, job_id, start, end, exclude_event_id=event['id'])
                for other in existing[:MAX_DRAFT_CONFLICTS - len(conflicts)]:
                    conflicts.append({'index': index, 'kind': 'archive' if other['status'] == 'archived' else 'catalogue',
                                      'existing_id': other.get('event_id') or other['id'], 'name': other['name'],
                                      'start': max(start, other.get('effective_start', other['start_datetime'])),
                                      'end': min(end, other.get('effective_end', other['end_datetime']))})
                if len(conflicts) == MAX_DRAFT_CONFLICTS:
                    return {'valid': False, 'conflicts': conflicts, 'events': []}
        for first, second in _draft_overlaps(intervals):
            start, end, index = first
            other_start, other_end, other_index = second
            conflicts.append({'index': index, 'other_index': other_index, 'kind': 'draft',
                              'name': events[other_index]['name'], 'start': max(start, other_start),
                              'end': min(end, other_end)})
            if len(conflicts) == MAX_DRAFT_CONFLICTS:
                break
        if conflicts:
            return {'valid': False, 'conflicts': conflicts, 'events': []}
        prefixes = [target_key(str(event_root_relative(event))) for event in events]
        if len(set(prefixes)) != len(prefixes):
            raise AdoptionError('Mehrere Ereignisse beanspruchen denselben Zielordner.')
        starts = [item[0] for item in intervals]
        counts = [{'families': 0, 'files': 0, 'days': set()} for _ in events]
        overrides = {key: _local_capture(value) for key, value in draft.get('capture_overrides', {}).items()}
        exclusions = set(draft.get('exclude_families') or [])
        coverage = {'unassigned': 0, 'review': 0, 'excluded': 0}
        occupied = merge_intervals((start, end) for start, end, _ in intervals)
        occupied_ends = [end for _, end in occupied]
        free_by_day = {}
        archive_by_day = {}
        archive = _archive_occupations(connection, job_id) if allow_existing else []
        archive_ends = []
        for _, end, _ in archive:
            archive_ends.append(max(end, archive_ends[-1]) if archive_ends else end)
        for row in connection.execute(
            """SELECT families.family_key, families.capture_time, families.review_required, copy.state AS review_copy,
                      (SELECT count(*) FROM legacy_adoption_inventory AS member
                       WHERE member.job_id=families.job_id AND member.family_key=families.family_key) AS files
               FROM legacy_adoption_families families
               LEFT JOIN legacy_adoption_review_copies copy USING(job_id,family_key)
               WHERE families.job_id=?""", (job_id,),
        ):
            key = row['family_key']
            capture = overrides.get(key, row['capture_time'])
            if key in exclusions or row['review_copy']:
                coverage['excluded'] += 1
            elif not capture or (row['review_required'] and key not in overrides):
                coverage['review'] += 1
            elif (index := _assigned_index(intervals, starts, capture)) is None:
                coverage['unassigned'] += 1
                day = capture[:10]
                if day not in free_by_day:
                    first = bisect_left(occupied_ends, day + 'T00:00:00')
                    blocked = list(_day_occupations(occupied, first, day))
                    if archive:
                        archive_by_day[day] = _archive_segments(archive, archive_ends, day)
                        blocked.extend((part['start_datetime'], part['end_datetime']) for part in archive_by_day[day])
                    free_by_day[day] = [
                        {**part, 'families': 0, 'files': 0}
                        for part in free_ranges_for_day(day, blocked)
                    ]
                for part in (*free_by_day[day], *archive_by_day.get(day, ())):
                    if part['start_datetime'] <= capture[:19] <= part['end_datetime']:
                        part['families'] += 1
                        part['files'] += row['files']
                        break
            else:
                counts[index]['families'] += 1
                counts[index]['files'] += row['files']
                counts[index]['days'].add(capture[:10])
        return {
            'valid': True, 'conflicts': [],
            'coverage': {**coverage, 'unassigned_days': sorted(free_by_day)[:12]},
            'free_segments': [part for day in sorted(free_by_day) for part in free_by_day[day] if part['families']],
            'archive_segments': [part for day in sorted(archive_by_day) for part in archive_by_day[day] if part['families']],
            'events': [
                {'name': event['name'], 'folder_name': event['folder_name'],
                 'start': event['start_datetime'], 'end': event['end_datetime'],
                 'children': [{'name': child['name'], 'start': child['start_datetime'], 'end': child['end_datetime']}
                              for child in event['children']],
                 'segments': event['segments'],
                 'families': count['families'], 'files': count['files'], 'days': len(count['days'])}
                for event, count in zip(events, counts)
            ],
        }


def _day_occupations(occupied, first, day):
    for index in range(first, len(occupied)):
        start, end = occupied[index]
        if start[:10] > day:
            break
        yield start, end


def _archive_occupations(connection, job_id):
    first, last = '0001-01-01T00:00:00', '9999-12-31T23:59:59'
    normal = continuous_event_overlaps(connection, job_id, first, last)
    collections = no_event_segment_overlaps(connection, job_id, first, last)
    return sorted(
        (row.get('effective_start', row['start_datetime']), row.get('effective_end', row['end_datetime']), row['name'])
        for row in normal + collections
    )


def _archive_segments(archive, ends, day):
    first, last = day + 'T00:00:00', day + 'T23:59:59'
    result = []
    for index in range(bisect_left(ends, first), len(archive)):
        start, end, name = archive[index]
        if start > last:
            break
        if end >= first:
            start, end = max(first, start), min(last, end)
            result.append({'day_key': day, 'start_datetime': start, 'end_datetime': end,
                           'event_name': name, 'families': 0, 'files': 0})
    return result


def _target_leaf(event, capture):
    prefix = event_root_relative(event)
    assigned = assignment_target(event["id"], event["children"], capture[:19])
    child = next((item for item in event["children"] if item["id"] == assigned), None)
    separate = child is not None and bool(child["folder_name"])
    if separate:
        prefix /= child["folder_name"]
    owner = assigned if separate else event["id"]
    leaf_key = owner
    if event["preserve_day_folders"]:
        prefix /= capture[:10]
        leaf_key += "@" + capture[:10]
    layouts = event["leaf_layouts"]
    layout = layouts.get(leaf_key) or layouts.get(owner) or (
        child.get("folder_layout") if separate else None
    ) or event["folder_layout"]
    return assigned, prefix, leaf_key, layout


def _leaf_directories(leaf, layout):
    directories = [leaf]
    if layout["structure_enabled"]:
        directories.extend(leaf / part for part in layout_paths(layout["layout"]))
    return {str(parent) for path in directories for parent in (path, *path.parents) if parent.parts}


def _unpopulated_child_leaves(event, planned_keys):
    if event["existing"]:
        return
    populated = {key.split("@", 1)[0] for key in planned_keys}
    for child in event["children"]:
        if child["folder_name"] and child["id"] not in populated:
            yield child["id"], event_root_relative(event) / child["folder_name"], child["folder_layout"]


def preview_event_directories(library, job_id, draft, *, allow_existing=False):
    """Show planned folders without creating a plan or inspecting archive contents."""
    with database_connection(library.database_path) as connection:
        connection.execute("BEGIN")
        if _job(connection, library.library_id, job_id)["state"] != "inventoried":
            raise AdoptionError("Die Inventur muss zuerst abgeschlossen werden.")
        naming = naming_snapshot_for_new_event(naming_from_library_settings(library.settings))
        defaults = get_global_default(connection)
        events = [_draft_event(connection, definition, naming, defaults, allow_existing=allow_existing)
                  for definition in draft["events"]]
        directories = set()
        intervals = _draft_intervals(events)
        starts = [item[0] for item in intervals]
        overrides = {key: _local_capture(value) for key, value in draft["capture_overrides"].items()}
        exclusions = set(draft["exclude_families"])
        seen_leaves = [set() for _ in events]
        rows = connection.execute(
            """SELECT family_key, capture_time, review_required FROM legacy_adoption_families AS family
               WHERE job_id = ? AND NOT EXISTS (
                   SELECT 1 FROM legacy_adoption_review_copies AS copy
                   WHERE copy.job_id = family.job_id AND copy.family_key = family.family_key
               ) ORDER BY capture_time, family_key""", (job_id,),
        )
        for row in rows:
            key = row["family_key"]
            capture = overrides.get(key, row["capture_time"])
            if key in exclusions or not capture or (row["review_required"] and key not in overrides):
                continue
            index = _assigned_index(intervals, starts, capture)
            if index is not None:
                _, leaf, leaf_key, layout = _target_leaf(events[index], capture)
                if leaf_key not in seen_leaves[index]:
                    seen_leaves[index].add(leaf_key)
                    directories.update(_leaf_directories(leaf, layout))
        for event, keys in zip(events, seen_leaves, strict=True):
            directories.update(_leaf_directories(event_root_relative(event), {"structure_enabled": False}))
            for _, leaf, layout in _unpopulated_child_leaves(event, keys):
                directories.update(_leaf_directories(leaf, layout))
    return {"directories": sorted(directories)}


def _plan_directories(connection, plan_id, leaf, layout, archive_entry):
    for value in sorted(_leaf_directories(leaf, layout)):
        validate_target(value)
        info = archive_entry(value)
        if info is not None and not stat.S_ISDIR(info.st_mode):
            raise AdoptionError("Ein benötigter Ordnerpfad ist belegt: " + value)
        connection.execute(
            "INSERT OR IGNORE INTO legacy_adoption_directories VALUES (?, ?)", (plan_id, value),
        )


def _store_leaf(event, key, path, layout):
    relative = path.relative_to(event_root_relative(event))
    event["leaf_layouts"][key] = {
        **layout, "leaf_key": key, "leaf_prefix": relative.as_posix() if relative.parts else "",
    }


def _check_planned_collisions(connection, plan_id):
    paths = {}
    for (path,) in connection.execute(
        """SELECT relative_path FROM legacy_adoption_directories WHERE plan_id = ?
           UNION ALL SELECT target_path FROM legacy_adoption_moves WHERE plan_id = ? AND target_path IS NOT NULL""",
        (plan_id, plan_id),
    ):
        key = target_key(path)
        if key in paths:
            raise AdoptionError("Mehrere geplante Pfade kollidieren: " + paths[key] + " / " + path)
        paths[key] = path


def _snapshot_existing_event(connection, plan_id, root_fd, prefix, event_id):
    doc = str(prefix / "event.json")
    found = False
    for path, directory, name, observed in walk_bound_files(root_fd, prefix):
        document = None
        with bound_file(directory, name, file_identity(observed)) as (descriptor, info):
            digest = bound_sha256(descriptor)
            if path == doc:
                if info.st_size > 64 * 1024 * 1024:
                    raise AdoptionError("Das bestehende Ereignisdokument überschreitet das Leselimit.")
                with os.fdopen(os.dup(descriptor), "rb") as handle:
                    handle.seek(0)
                    document = handle.read()
                payload = json.loads(document)
                if not isinstance(payload, dict) or (payload.get("event") or {}).get("id") != event_id:
                    raise AdoptionError("Das vorhandene Ereignisdokument gehört zu einem anderen Ereignis.")
                found = True
        connection.execute(
            """INSERT INTO legacy_adoption_baseline
                  (plan_id, relative_path, size_bytes, sha256, document) VALUES (?, ?, ?, ?, ?)""",
            (plan_id, path, info.st_size, digest, document),
        )
    if not found:
        raise AdoptionError("Das bestehende Ereignisdokument fehlt: " + doc)


def _archive_probe(root_fd):
    @lru_cache(maxsize=32)
    def names(parent):
        try:
            with relative_parent(root_fd, str(PurePosixPath(parent) / ".probe")) as (directory, _):
                keys = {}
                for name in os.listdir(directory):
                    keys.setdefault(target_key(name), []).append(name)
                return keys
        except FileNotFoundError:
            return {}

    def lookup(relative):
        prefix = PurePosixPath()
        for part in PurePosixPath(relative).parts:
            aliases = names(str(prefix)).get(target_key(part), [])
            if aliases and aliases != [part]:
                raise AdoptionError("Zielkollision durch Schreibweise: " + str(prefix / part))
            prefix /= part
        try:
            with relative_parent(root_fd, relative) as (directory, name):
                return os.stat(name, dir_fd=directory, follow_symlinks=False)
        except FileNotFoundError:
            return None

    return lookup


def _known_content(connection, registry, plan_id, checksum):
    return bool(
        connection.execute("SELECT 1 FROM files WHERE sha256_original = ? OR sha256_current = ? LIMIT 1",
                           (checksum, checksum)).fetchone()
        or registry.execute("SELECT 1 FROM source_media WHERE sha256 = ? LIMIT 1", (checksum,)).fetchone()
        or connection.execute(
            "SELECT 1 FROM legacy_adoption_moves WHERE plan_id = ? AND sha256 = ? LIMIT 1",
            (plan_id, checksum),
        ).fetchone()
    )


def _suggest_folder_moves(connection, plan_id, source_fd, archive_entry, candidates, target_counts):
    for source, (target, count) in candidates.items():
        if not target or target_counts[target] != count or archive_entry(target) is not None:
            continue
        try:
            with relative_parent(source_fd, str(PurePosixPath(source) / ".binding")) as (directory, _):
                with os.scandir(directory) as entries:
                    actual = 0
                    for entry in entries:
                        relative = str(PurePosixPath(source) / entry.name)
                        if not entry.is_file(follow_symlinks=False) or connection.execute(
                            """SELECT 1 FROM legacy_adoption_moves
                               WHERE plan_id = ? AND relative_path = ? AND target_path = ?""",
                            (plan_id, relative, str(PurePosixPath(target) / entry.name)),
                        ).fetchone() is None:
                            break
                        actual += 1
                    else:
                        if actual == count:
                            connection.execute(
                                "INSERT INTO legacy_adoption_folder_moves VALUES (?, ?, ?, ?)",
                                (plan_id, source, target, count),
                            )
        except OSError:
            # The per-file move plan remains valid even when grouping is unavailable.
            continue


def _plan_moves(connection, registry, job, plan_id, events, intervals, draft, source_fd, archive_fd):
    archive_entry = _archive_probe(archive_fd)
    for event in events:
        prefix = event_root_relative(event)
        validate_target(str(prefix))
        if event["existing"]:
            _snapshot_existing_event(connection, plan_id, archive_fd, prefix, event["id"])
        elif archive_entry(str(prefix)) is not None:
            raise AdoptionError("Der neue Ereignisordner existiert bereits: " + str(prefix))

    starts = [item[0] for item in intervals]
    overrides = {key: _local_capture(value) for key, value in (draft.get("capture_overrides") or {}).items()}
    exclusions = set(draft.get("exclude_families") or [])
    target_stems = draft.get("target_stems") or {}
    seen_draft_keys = set()
    added = set()
    candidates = {}
    target_counts = Counter()
    planned_directories = set()
    rows = connection.execute(
        """SELECT inventory.*, families.capture_time, families.review_required, copy.state AS review_copy
             FROM legacy_adoption_inventory inventory
             JOIN legacy_adoption_families families USING (job_id, family_key)
             LEFT JOIN legacy_adoption_review_copies copy USING (job_id, family_key)
            WHERE inventory.job_id = ? ORDER BY family_key, relative_path""",
        (job["id"],),
    )
    for key, group in groupby(rows, key=lambda row: row["family_key"]):
        family = list(group)
        seen_draft_keys.add(key)
        if key in exclusions or family[0]["review_copy"]:
            continue
        capture = overrides.get(key, family[0]["capture_time"])
        if key not in overrides and family[0]["review_required"]:
            continue
        if not capture:
            continue
        index = _assigned_index(intervals, starts, capture)
        if index is None:
            continue
        event = events[index]
        if key.strip() != key:
            raise AdoptionError("Der Familienname ist für die globale Registry ungeeignet: " + key)
        assigned, leaf, leaf_key, layout = _target_leaf(event, capture)
        if any(not member["sha256"] for member in family):
            raise AdoptionError("Die Familie konnte nicht vollständig inventarisiert werden: " + key)

        checksums = [member["sha256"] for member in family]
        duplicate = [_known_content(connection, registry, plan_id, checksum) for checksum in checksums]
        if (any(duplicate) and not all(duplicate)) or len(set(checksums)) != len(checksums):
            raise AdoptionError("Einzelne Mitglieder einer Dateifamilie sind bereits registriert "
                                "oder haben identischen Inhalt: " + key)

        for member in family:
            source = member["relative_path"]
            if source.strip() != source or "\\" in source:
                raise AdoptionError("Der Quellpfad ist für die globale Registry ungeeignet: " + source)
            with relative_parent(source_fd, source) as (directory, name):
                with bound_file(directory, name, tuple(json.loads(member["identity"]))):
                    pass
            target = None
            if not all(duplicate):
                filename = PurePosixPath(source).name
                if key in target_stems:
                    stem = target_stems[key]
                    if "/" in stem:
                        raise AdoptionError("Der Zielname muss ein einzelner Dateiname ohne Endung sein.")
                    validate_target(stem)
                    original_stem = PurePosixPath(key).name
                    filename = stem + filename[len(original_stem):]
                input_path = layout["input_path"] if layout["structure_enabled"] else ""
                target = str(leaf / input_path / filename)
                validate_target(target)
                if archive_entry(target) is not None:
                    raise AdoptionError("Zieldatei existiert bereits: " + target)
                source_dir = PurePosixPath(source).parent
                target_dir = str(PurePosixPath(target).parent)
                target_counts[target_dir] += 1
                if source_dir.name == capture[:10]:
                    previous, count = candidates.get(str(source_dir), (target_dir, 0))
                    candidates[str(source_dir)] = (target_dir if previous == target_dir else None, count + 1)
                added.add(event["id"])
            try:
                connection.execute(
                    """INSERT INTO legacy_adoption_moves (
                           plan_id, relative_path, target_path, target_key, parent_event_id,
                           assigned_event_id, capture_time, sha256, status
                       ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (plan_id, source, target, target_key(target) if target else None, event["id"],
                     assigned, capture, member["sha256"], "pending" if target else "duplicate"),
                )
            except sqlite3.IntegrityError as error:
                raise AdoptionError("Mehrere Aufnahmen beanspruchen dieselbe Zieldatei: " + str(target)) from error
        if all(duplicate):
            continue
        if (event["id"], leaf_key) not in planned_directories:
            if not event["existing"]:
                _store_leaf(event, leaf_key, leaf, layout)
            _plan_directories(connection, plan_id, leaf, layout, archive_entry)
            planned_directories.add((event["id"], leaf_key))
    for event in events:
        for key, path, layout in _unpopulated_child_leaves(event, event["leaf_layouts"]):
            _store_leaf(event, key, path, layout)
            _plan_directories(connection, plan_id, path, layout, archive_entry)
    _check_planned_collisions(connection, plan_id)
    if (overrides.keys() | exclusions | target_stems.keys()) - seen_draft_keys:
        raise AdoptionError("Mindestens eine Dateifamilie aus dem Entwurf fehlt in der Inventur.")
    if not added:
        raise AdoptionError("Die Auswahl enthält keine neuen, vollständig datierten Dateifamilien.")
    if any(event["id"] not in added for event in events):
        raise AdoptionError("Mindestens ein gespeichertes Ereignis oder ein Sammelordner enthält keine neuen Dateifamilien.")
    _suggest_folder_moves(connection, plan_id, source_fd, archive_entry, candidates, target_counts)


def _roots(stack, library, job):
    if Path(job["archive_root"]) != library.archive_root:
        raise AdoptionError("Die Archivwurzel der Zielbibliothek hat sich geändert.")
    source = stack.enter_context(bound_directory(
        Path(job["source_root"]), (job["source_device"], job["source_inode"]),
    ))
    archive = stack.enter_context(bound_directory(
        library.archive_root, (job["archive_device"], job["archive_inode"]),
    ))
    dataset.revalidate(json.loads(job["dataset_json"] or "null"),
                       job["source_root"], library.archive_root, source, archive)
    return source, archive


def create_plan(library, registry_path: Path, job_id: str, draft=None, *, draft_revision=None,
                allow_existing=False) -> dict:
    plan_id = uuid4().hex
    with database_connection(library.database_path) as connection, closing(sqlite3.connect(
        registry_path.absolute().as_uri() + "?mode=ro", uri=True,
    )) as registry:
        connection.execute("BEGIN IMMEDIATE")
        registry.execute("BEGIN")
        if not allow_existing:
            require_no_managed_data(connection)
        job = _job(connection, library.library_id, job_id)
        if draft_revision is not None:
            if job["draft_revision"] != draft_revision:
                raise AdoptionError("Der Entwurf wurde in einer anderen Sitzung geändert. Lade ihn erneut.")
            draft = json.loads(job["draft_json"])
        definitions = (draft or {}).get("events")
        if not isinstance(definitions, list) or not definitions:
            raise AdoptionError("Lege mindestens ein Ereignis oder einen Sammelordner an.")
        if len(definitions) > MAX_PLAN_ITEMS:
            raise AdoptionError(f"Pro Auftrag sind bis zu {MAX_PLAN_ITEMS} Planobjekte möglich.")
        if job["state"] != "inventoried":
            raise AdoptionError("Die Inventur muss zuerst abgeschlossen werden.")
        if connection.execute("SELECT 1 FROM legacy_adoption_plans WHERE job_id = ?", (job_id,)).fetchone():
            raise AdoptionError("Ein Verschiebeplan ist bereits gespeichert.")
        naming = naming_snapshot_for_new_event(naming_from_library_settings(library.settings))
        defaults = get_global_default(connection)
        events = [
            _draft_event(connection, definition, naming, defaults, allow_existing=allow_existing)
            for definition in definitions
        ]
        prefixes = [target_key(str(event_root_relative(event))) for event in events]
        if len(set(prefixes)) != len(prefixes):
            raise AdoptionError("Mehrere Ereignisse beanspruchen denselben Zielordner.")
        intervals = _assert_timeline(connection, job_id, events)
        connection.execute(
            """INSERT INTO legacy_adoption_plans (job_id, id, state, draft_json, events_json)
               VALUES (?, ?, 'prepared', ?, ?)""",
            (job_id, plan_id, json.dumps(draft), json.dumps(events)),
        )
        with ExitStack() as stack:
            source, archive = _roots(stack, library, job)
            _plan_moves(connection, registry, job, plan_id, events, intervals, draft, source, archive)
        connection.execute("UPDATE legacy_adoption_plans SET events_json = ? WHERE id = ?", (json.dumps(events), plan_id))
    return plan_status(library, job_id)


def plan_status(library, job_id: str) -> dict:
    with database_connection(library.database_path) as connection:
        connection.execute("BEGIN")
        job = _job(connection, library.library_id, job_id)
        plan = connection.execute("SELECT * FROM legacy_adoption_plans WHERE job_id = ?", (job_id,)).fetchone()
        if plan is None:
            return {}
        counts = {row["status"]: row["count"] for row in connection.execute(
            "SELECT status, count(*) AS count FROM legacy_adoption_moves WHERE plan_id = ? GROUP BY status",
            (plan["id"],),
        )}
        execution = connection.execute(
            "SELECT method, phase, confirmed_at, updated_at FROM legacy_adoption_execution WHERE plan_id = ?",
            (plan["id"],),
        ).fetchone()
        volume = connection.execute(
            """SELECT count(*), coalesce(sum(inventory.size_bytes), 0), count(DISTINCT inventory.family_key)
                 FROM legacy_adoption_moves AS move JOIN legacy_adoption_inventory AS inventory
                   ON inventory.job_id = ? AND inventory.relative_path = move.relative_path
                WHERE move.plan_id = ? AND move.target_path IS NOT NULL""",
            (job_id, plan["id"]),
        ).fetchone()
        return {
            "id": plan["id"], "state": plan["state"], "counts": counts,
            "execution": dict(execution) if execution else None,
            "move_files": volume[0], "move_bytes": volume[1], "move_families": volume[2],
            "library_name": library.display_name,
            "documents_at": plan["documents_at"],
            "folder_moves": [dict(row) for row in connection.execute(
                """SELECT source_path, target_path, file_count FROM legacy_adoption_folder_moves
                    WHERE plan_id = ? ORDER BY source_path LIMIT 100""", (plan["id"],),
            )],
            "source_root": job["source_root"], "archive_root": job["archive_root"],
            "draft": json.loads(plan["draft_json"]), "events": json.loads(plan["events_json"]),
            "issues": connection.execute("SELECT count(*) FROM legacy_adoption_issues WHERE plan_id = ?",
                                         (plan["id"],)).fetchone()[0],
            "dataset": json.loads(job["dataset_json"] or "null"),
            "dataset_verified_at": job["dataset_verified_at"],
            "snapshot_hint": (
                "Vor größeren Dateiänderungen wird empfohlen, einen ZFS-Snapshot oder eine andere "
                "geeignete Sicherung anzulegen. Dies ist eine freiwillige zusätzliche Sicherheitsmaßnahme "
                "und keine Voraussetzung für die Übernahme."
            ),
        }


def plan_directories(library, job_id, *, after=""):
    with database_connection(library.database_path) as connection:
        _job(connection, library.library_id, job_id)
        return [row[0] for row in connection.execute(
            """SELECT directory.relative_path FROM legacy_adoption_directories directory
                 JOIN legacy_adoption_plans plan ON plan.id = directory.plan_id
                WHERE plan.job_id = ? AND directory.relative_path > ?
                ORDER BY directory.relative_path LIMIT 100""", (job_id, after),
        )]


def plan_moves(library, job_id: str, *, after: str = "", limit: int = 100):
    with database_connection(library.database_path) as connection:
        connection.execute("BEGIN")
        job = _job(connection, library.library_id, job_id)
        rows = connection.execute(
            """SELECT move.*, inventory.size_bytes, inventory.identity, inventory.family_key
                 FROM legacy_adoption_moves move
                 JOIN legacy_adoption_plans plan ON plan.id = move.plan_id
                 JOIN legacy_adoption_inventory inventory ON inventory.job_id = plan.job_id
                      AND inventory.relative_path = move.relative_path
                WHERE plan.job_id = ? AND move.relative_path > ?
                ORDER BY move.relative_path LIMIT ?""",
            (job_id, after, max(1, min(limit, 200))),
        )
        return [{
            **dict(row), "source": str(Path(job["source_root"]) / row["relative_path"]),
            "target": str(Path(job["archive_root"]) / row["target_path"]) if row["target_path"] else None,
        } for row in rows]
