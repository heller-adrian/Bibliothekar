"""Build and persist manual legacy moves without changing the archive catalogue."""
from bisect import bisect_left, bisect_right
from collections import Counter, defaultdict
from contextlib import closing, ExitStack
from datetime import datetime
from functools import lru_cache
from itertools import groupby
import json
import os
import sqlite3
from pathlib import Path, PurePosixPath
import stat
from uuid import uuid4

from app import legacy_adoption_dataset as dataset
from app.large_xmp import large_xmp_proof, MAX_STREAM_BYTES
from app.xmp_raw_filename import XmpReferenceError
from app.database import database_connection
from app.event_inventory import event_root_relative
from app.event_layout import ensure_event_layout_snapshot, get_global_default, layout_paths, resolve_layout_choice
from app.event_leaf_layouts import effective_leaf_layouts
from app.event_naming import (
    naming_from_library_settings, naming_snapshot_for_new_event,
    render_event_folder_name, render_no_event_folder_name,
)
from app.event_structure import continuous_event_bounds
from app.filename_collisions import capture_stem, has_capture_fraction, numbered_stem
from app.folder_import import normalize_device_name
from app.free_time import free_ranges_for_day
from app.event_timeline import continuous_event_overlaps, no_event_segment_overlaps, normalize_no_event_segments, normal_event_ranges
from app.legacy_adoption_inventory import _job, _legacy_family_key, registered_content
from app.legacy_adoption_mode import require_no_managed_data
from app.legacy_adoption_xmp_plan import MAX_XMP_BYTES, RAW_EXTENSIONS, XmpPlanError, planned_edit, raw_name_pair
from app.legacy_adoption_paths import (
    AdoptionError, bound_directory, bound_file, bound_sha256, file_identity, relative_parent,
    target_key, validate_target, verify_inventory_identity, walk_bound_files,
)
from app.media_family_identity import IDENTITY_VERSION
from app.metadata import LOCAL_TIMEZONE, family_member_ending
from app.operation_health import read_session
from app.released_ranges import merge_intervals
from app.subevents import assignment_target, normalize_subevents


MAX_PLAN_ITEMS = 2000
MAX_DRAFT_CONFLICTS = 50


class ManualXmpRenameConflict(AdoptionError):
    pass


def file_issue_summary(items):
    files = list(items)
    return {"total": len(files),
            "reasons": dict(Counter(item["reason"] for item in files)),
            "examples": [{key: item[key] for key in ("path", "reason")} for item in files[:10]]}


class PlanFileIssues(AdoptionError):
    def __init__(self, items):
        self.items = items
        super().__init__("Einige Dateien können nicht sicher in diesen Plan aufgenommen werden.")


def _event_id():
    return "EVENT_" + uuid4().hex.upper()


def _local_capture(value):
    result = datetime.fromisoformat(value)
    if result.year <= 1904 or len(value) < 16:
        raise AdoptionError("Die bestätigte Aufnahmezeit benötigt Datum und Uhrzeit.")
    if result.tzinfo is None:
        result = result.replace(tzinfo=LOCAL_TIMEZONE)
    return result.isoformat(timespec="microseconds" if has_capture_fraction(value) else "auto")


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


def preview_draft(library, job_id, draft, *, allow_existing=False, validate_only=False):
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
        if validate_only:
            return {'valid': True, 'conflicts': []}
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
                      (SELECT count(*) FROM legacy_adoption_inventory AS member INDEXED BY legacy_adoption_inventory_family
                       WHERE member.job_id=families.job_id AND member.family_key=families.family_key
                         AND member.disposition = 'candidate') AS files
               FROM legacy_adoption_candidate_families families
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
            """SELECT family_key, capture_time, review_required FROM legacy_adoption_candidate_families AS family
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


def _archive_probe(root_fd, *, registered=None):
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
        parts = PurePosixPath(relative).parts
        for index, part in enumerate(parts):
            aliases = names(str(prefix)).get(target_key(part), [])
            if aliases and aliases != [part]:
                if (registered is None or index != len(parts) - 1 or len(aliases) != 1
                        or str(prefix / aliases[0]) not in registered):
                    raise AdoptionError("Zielkollision durch Schreibweise: " + str(prefix / part))
                part = aliases[0]
            prefix /= part
        try:
            with relative_parent(root_fd, str(prefix)) as (directory, name):
                return os.stat(name, dir_fd=directory, follow_symlinks=False)
        except FileNotFoundError:
            return None

    lookup.names = names
    return lookup


def _family_duplicate_conflict(checksums, already_known):
    """Explain a blocked historic family without weakening content ownership.

    An identical checksum *within* a candidate family and a partial match to
    already-owned material are different situations. Neither may silently be
    turned into a second canonical media registration.
    """
    if len(checksums) != len(already_known):
        raise ValueError("Checksum and registration lists must have equal length")
    if len(set(checksums)) != len(checksums):
        return "Mehrere Mitglieder dieser Familie besitzen denselben SHA-256-Inhalt"
    if any(already_known) and not all(already_known):
        return "Nur ein Teil der Familienmitglieder ist bereits registriert oder im Plan enthalten"
    return None


def _known_content(connection, registry, plan_id, checksum):
    # Same-plan occurrences are intentional physical copies. Only an already
    # registered prior import is excluded from this new adoption plan.
    return bool(registered_content(connection, registry, checksum))


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


def _registered_archive_paths(connection, plan_id, event_id):
    return {row[0] for row in connection.execute(
        """SELECT baseline.relative_path FROM legacy_adoption_baseline baseline
              JOIN event_inventory_files inventory ON inventory.relative_path = baseline.relative_path
               AND inventory.sha256 = baseline.sha256 AND inventory.size_bytes = baseline.size_bytes
              JOIN files ON files.id = inventory.known_file_id
               AND files.current_relative_path = baseline.relative_path
               AND files.sha256_current = baseline.sha256 AND files.size_bytes = baseline.size_bytes
             WHERE baseline.plan_id = ? AND inventory.event_id = ?
               AND inventory.root_kind = 'camera_archive' AND files.current_root_kind = 'camera_archive'""",
        (plan_id, event_id),
    )}


def _versioned_members(family, member_name):
    """Reserve distinct names for sidecars without replacing an edit version."""
    names = [member_name(member["relative_path"]) for member in family]
    bases = defaultdict(list)
    for index, name in enumerate(names):
        bases[target_key(name)].append(index)
    reserved = set(bases)
    for indexes in bases.values():
        if len(indexes) < 2:
            continue
        if any(not names[index].casefold().endswith(".xmp") for index in indexes):
            raise AdoptionError("Mehrere Aufnahmen beanspruchen dieselbe Zieldatei: " + family[indexes[0]]["relative_path"])
        # Keep the sidecar beside the matching master as the default version.
        def order(index):
            member = family[index]
            path = PurePosixPath(member["relative_path"])
            metadata = json.loads(member["metadata_json"] or "{}")
            hint = (metadata.get("capture_identity") or {}).get("sidecar_raw")
            colocated = any(
                PurePosixPath(item["relative_path"]).parent == path.parent
                and PurePosixPath(item["relative_path"]).name.casefold() == hint
                for item in family
            )
            return not colocated, path.as_posix()

        for index in sorted(indexes, key=order)[1:]:
            name = names[index]
            number = 2
            while True:
                tail = f".XMP_{number:03d}" + name[-4:]
                stem = name[:-4].encode("utf-8")[:255 - len(tail.encode("utf-8"))].decode("utf-8", errors="ignore")
                alternate = stem + tail
                if target_key(alternate) not in reserved:
                    names[index] = alternate
                    reserved.add(target_key(alternate))
                    break
                number += 1
    return names


def _family_targets(folder, key, family, override, archive_entry, registered, used, sequences,
                    *, duplicate_index=None, collision_index=None, occupied_paths=None, sibling_names=()):
    """Retain original names unless a *real target path* is already reserved.

    A byte-identical source occurrence always gets a _Duplicate_NNN label,
    including the first one. Two different physical occurrences contending
    for the same full target name both get _001, _002, etc. Different formats
    may share their unchanged stem without creating a false collision.
    """
    original = PurePosixPath(key).name
    stem = override if override is not None else original
    if override is not None:
        if "/" in stem:
            raise AdoptionError("Der Zielname muss ein einzelner Dateiname ohne Endung sein.")
        validate_target(stem)
    if override is not None and (duplicate_index is not None or collision_index is not None):
        raise AdoptionError("Expliziter Zielname kollidiert mit einer weiteren Aufnahme: " + stem)

    endings = _versioned_members(family, family_member_ending)

    reserved = used if occupied_paths is None else occupied_paths
    number = duplicate_index if duplicate_index is not None else (collision_index or 0)
    while True:
        if number > 999999:
            raise AdoptionError("Zu viele gleichnamige Dateien im Zielordner: " + stem)
        suffix = (f"_Duplicate_{number:03d}" if duplicate_index is not None
                  else f"_{number:03d}" if number else "")
        max_stem_bytes = 255 - len(suffix.encode("utf-8")) - max(
            len(ending.encode("utf-8")) for ending in endings
        )
        if max_stem_bytes <= 0:
            raise AdoptionError("Dateiname ist zu lang: " + stem)
        safe_stem = stem.encode("utf-8")[:max_stem_bytes].decode("utf-8", errors="ignore") + suffix
        targets = [str(folder / (safe_stem + ending)) for ending in endings]
        for path in targets:
            validate_target(path)
        if all(target_key(path) not in reserved
               and target_key(PurePosixPath(path).name) not in sibling_names
               and archive_entry(path) is None for path in targets):
            for path in targets:
                reserved.add(target_key(path))
            used.add(target_key(str(folder / safe_stem)))
            sequences[target_key(str(folder / stem))] = number
            return targets
        if override is not None:
            raise AdoptionError("Zieldatei existiert bereits: " + targets[0])
        number += 1


def _occurrence_components(buckets):
    """Return connected sets for numbering, without changing any family identity."""
    parent = {}

    def root(key):
        parent.setdefault(key, key)
        while key != parent[key]:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key

    for bucket in buckets:
        if len(bucket) > 1:
            ordered = sorted(bucket)
            first = root(ordered[0])
            for key in ordered[1:]:
                parent[root(key)] = first
    components = defaultdict(list)
    for key in sorted(parent):
        components[root(key)].append(key)
    return components.values()


def _adoption_occurrence_sequences(selections, target_stems):
    """Number physical file copies and name conflicts independently."""
    by_hash, by_target = defaultdict(set), defaultdict(set)
    media_hashes, raw_hashes = {}, {}
    for key, members, _capture, _event, (_assigned, leaf, _leaf_key, layout) in selections:
        folder = _destination_folder(leaf, layout)
        stem = target_stems.get(key, PurePosixPath(key).name)
        media_hashes[key], raw_hashes[key] = set(), set()
        for member in members:
            ending = family_member_ending(member["relative_path"])
            by_target[target_key(str(folder / (stem + ending)))].add(key)
            media_type = json.loads(member["metadata_json"] or "{}").get("media_type")
            checksum = member["sha256"]
            if media_type != "xmp":
                by_hash[checksum].add(key)
                media_hashes[key].add(checksum)
            if media_type == "raw":
                raw_hashes[key].add(checksum)

    duplicates, cohorts = {}, {}
    for component in _occurrence_components(by_hash.values()):
        masters = {frozenset(raw_hashes[key]) for key in component if raw_hashes[key]}
        unambiguous = len(masters) <= 1 and all(
            len(by_hash[checksum]) in {1, len(component)}
            for key in component for checksum in media_hashes[key]
        )
        # A shared companion proves copies of that file. Burst numbering may
        # group captures only when their masters or complete media agree.
        capture_groups = defaultdict(list)
        for number, key in enumerate(component, 1):
            duplicates[key] = number
            if unambiguous:
                signature = None
            elif raw_hashes[key]:
                signature = ("raw", frozenset(raw_hashes[key]))
            else:
                signature = ("media", frozenset(media_hashes[key]))
            capture_groups[signature].append(key)
        for group in capture_groups.values():
            cohort = frozenset(group)
            cohorts.update(dict.fromkeys(group, cohort))

    collisions = {
        key: number
        for component in _occurrence_components(by_target.values())
        for number, key in enumerate(component, 1)
    }
    return duplicates, collisions, cohorts


def _exact_script_collisions(selections, camera_tokens, burst_counts):
    """Only same generated millisecond name needs _001 from the first family."""
    candidates = Counter()
    for key, members, capture, _event, (_assigned, leaf, _leaf_key, layout) in selections:
        camera, group = camera_tokens[key]
        base, index, _ = capture_stem(
            capture, camera, set(), same_second=burst_counts[group] > 1,
        )
        if index == 0:
            candidates[(target_key(str(_destination_folder(leaf, layout))), base.casefold())] += 1
    return candidates


def _assigned_families(rows, draft, events, intervals, seen):
    starts = [item[0] for item in intervals]
    overrides = {key: _local_capture(value) for key, value in (draft.get("capture_overrides") or {}).items()}
    exclusions = set(draft.get("exclude_families") or [])
    file_exclusions = draft.get("file_exclusions") or {}
    for key, group in groupby(rows, key=lambda row: row["family_key"]):
        members = []
        for member in group:
            proof = file_exclusions.get(member["relative_path"])
            if proof:
                if proof["sha256"] != member["sha256"]:
                    raise AdoptionError("Eine ausgeschlossene Datei hat sich geändert. Prüfe die Inventur erneut.")
                continue
            if member["disposition"] == "candidate":
                members.append(member)
        seen.add(key)
        if not members or key in exclusions or members[0]["review_copy"]:
            continue
        capture = overrides.get(key, members[0]["capture_time"])
        if not capture or (key not in overrides and members[0]["review_required"]):
            continue
        index = _assigned_index(intervals, starts, capture)
        if index is not None:
            yield key, members, capture, events[index], _target_leaf(events[index], capture)


def _destination_folder(leaf, layout):
    return leaf / (layout["input_path"] if layout["structure_enabled"] else "")


def _camera_tokens(families):
    tokens, groups = {}, Counter()
    for key, members, capture, _, (_, leaf, _, layout) in families:
        metadata = (json.loads(member["metadata_json"] or "{}") for member in members)
        camera = next((item for item in metadata if item.get("camera_make") or item.get("camera_model")), {})
        _, token = normalize_device_name(camera.get("camera_make"), camera.get("camera_model"))
        group = (target_key(str(_destination_folder(leaf, layout))), capture[:19], token.casefold())
        tokens[key] = (token, group)
        groups[group] += 1
    return tokens, groups


def _script_capture_ordinals(selections, cameras, cohorts):
    """Assign burst positions to distinct captures, sharing an ordinal only for proven copies."""
    unique_by_group = defaultdict(set)
    no_subsec_by_group = defaultdict(set)
    for key, _members, capture, *_ in selections:
        group = cameras[key][1]
        cohort = cohorts.get(key, frozenset({key}))
        unique_by_group[group].add(cohort)
        if capture[19:20] != ".":
            no_subsec_by_group[group].add(cohort)
    distinct = {group: len(cohorts) for group, cohorts in unique_by_group.items()}

    def order(cohort):
        return min((PurePosixPath(key).name.casefold(), key) for key in cohort)

    burst_ordinals = {}
    for group, captures in no_subsec_by_group.items():
        for index, cohort in enumerate(sorted(captures, key=order), 1):
            for key in cohort:
                burst_ordinals[key] = index
    return distinct, burst_ordinals


def _has_bound_raw_reference(family):
    originals = [member["relative_path"] for member in family]
    for member in family:
        metadata = json.loads(member["metadata_json"] or "{}")
        hint = (metadata.get("capture_identity") or {}).get("sidecar_raw")
        if metadata.get("media_type") == "xmp" and hint and raw_name_pair(family, originals, hint):
            return True
    return False


def _manual_linked_targets(folder, key, family, duplicate_index, archive_entry, reserved, layout_paths):
    """Preserve the RAW basename required by a bound sidecar."""
    stem = PurePosixPath(key).name
    siblings = archive_entry.names(str(folder))
    layout_keys = {target_key(path) for path in layout_paths}
    names = _versioned_members(family, lambda path: PurePosixPath(path).name)
    targets = [str(folder / name) for name in names]
    if duplicate_index is None and all(
        target_key(path) not in reserved and target_key(path) not in layout_keys
        and target_key(PurePosixPath(path).name) not in siblings for path in targets
    ):
        for path in targets:
            validate_target(path)
        reserved.update(target_key(path) for path in targets)
        return folder, targets
    number = duplicate_index or 1
    while number <= 999999:
        suffix = f"_Duplicate_{number:03d}" if duplicate_index is not None else f"_{number:03d}"
        prefix = stem.encode("utf-8")[:255 - len(suffix)].decode("utf-8", errors="ignore")
        name = prefix + suffix
        directory = folder / name
        normalized = target_key(str(directory))
        if normalized not in reserved and normalized not in layout_keys and target_key(name) not in siblings:
            targets = [str(directory / filename) for filename in names]
            for target in targets:
                validate_target(target)
            reserved.add(normalized)
            reserved.update(target_key(target) for target in targets)
            return directory, targets
        number += 1
    raise AdoptionError("Zu viele gleichnamige Dateien im Zielordner: " + stem)


def _automatic_family_targets(folder, key, family, capture, camera, same_second, names, stems, used,
                              *, duplicate_index=None, number_all=False, burst_ordinal=None):
    endings = _versioned_members(family, family_member_ending)
    # Reuse exactly the same real-EXIF-millisecond Burst implementation as the
    # normal folder import. Neither invented subseconds nor directory patterns.
    base, index, _ = capture_stem(capture, camera, stems, same_second=same_second)
    if index > 0 and base.endswith("_Burst") and burst_ordinal is not None:
        base += f"_{burst_ordinal:03d}"
        index = 0
    if duplicate_index is not None:
        base += "_Duplicate"
        index = duplicate_index
    elif number_all and index == 0:
        index = 1
    while True:
        suffix = numbered_stem("", index)
        max_bytes = 255 - len(suffix.encode("utf-8")) - max(
            len(ending.encode("utf-8")) for ending in endings
        )
        if max_bytes <= 0:
            raise AdoptionError("Dateiname ist zu lang: " + key)
        stem = base.encode("utf-8")[:max_bytes].decode("utf-8", errors="ignore") + suffix
        prefix = target_key(str(folder / stem))
        targets = [str(folder / (stem + ending)) for ending in endings]
        if prefix not in used and all(target_key(PurePosixPath(path).name) not in names for path in targets):
            used.add(prefix)
            for path in targets:
                validate_target(path)
            return targets
        index += 1


def _retain_xmp_companions(connection, plan_id, job_id, issues, anchors, selections, exclusions):
    """Refuse to move a source master away from a retained companion."""
    paths = {item["path"] for item in issues}
    anchors = {path: (raw, key) for path, raw, key in anchors}
    source_sidecars = connection.execute(
        """SELECT inventory.relative_path, inventory.family_key, inventory.sha256,
                  json_extract(inventory.metadata_json, '$.capture_identity.sidecar_raw') AS raw_name
             FROM legacy_adoption_inventory AS inventory
             LEFT JOIN legacy_adoption_moves AS move
               ON move.plan_id = ? AND move.relative_path = inventory.relative_path AND move.target_path IS NOT NULL
            WHERE inventory.job_id = ? AND inventory.disposition = 'candidate' AND move.relative_path IS NULL
              AND json_extract(inventory.metadata_json, '$.media_type') = 'xmp'
              AND json_extract(inventory.metadata_json, '$.capture_identity.sidecar_raw') <> ''""",
        (plan_id, job_id),
    )
    documents = {row["relative_path"]: row for row in source_sidecars}
    anchors.update((path, (row["raw_name"], row["family_key"])) for path, row in documents.items())
    if not anchors:
        return
    groups = {key: members for key, members, *_ in selections}
    folders, adjacent = defaultdict(set), defaultdict(set)
    names = {target_key(raw) for raw, _ in anchors.values()}
    for key, members in groups.items():
        for member in members:
            path = PurePosixPath(member["relative_path"])
            name = target_key(path.name)
            if path.suffix.casefold() in RAW_EXTENSIONS and name in names:
                folders[path.parent, name].add(key)
                adjacent[path.parent.parent, name].add(key)
    protected = set()
    for sidecar, (raw, key) in anchors.items():
        directory = PurePosixPath(sidecar).parent
        name = target_key(raw)
        companions = set(folders.get((directory, name), ()))
        if directory.parent != PurePosixPath("."):
            companions.update(adjacent.get((directory.parent, name), ()))
        if key in groups and any(member["relative_path"] != sidecar for member in groups[key]):
            companions.add(key)
        if companions and sidecar not in paths and sidecar not in exclusions:
            paths.add(sidecar)
            issues.append({
                "path": sidecar, "sha256": documents[sidecar]["sha256"],
                "reason": "Für ein an der Quelle verbleibendes XMP ist ein möglicher RAW-Partner eingeplant.",
                "identity_version": IDENTITY_VERSION,
            })
        protected.update(companions)
    for key in sorted(protected):
        for member in groups.get(key, ()):
            if member["relative_path"] not in paths:
                paths.add(member["relative_path"])
                issues.append({
                    "path": member["relative_path"], "sha256": member["sha256"],
                    "reason": "Datei bleibt mit einem nicht sicher übernehmbaren XMP an der Quelle.",
                    "identity_version": IDENTITY_VERSION,
                })



def _plan_moves(connection, registry, job, plan_id, events, intervals, draft, source_fd, archive_fd,
                filename_method):
    registered = set()
    archive_entry = _archive_probe(archive_fd, registered=registered)
    for event in events:
        prefix = event_root_relative(event)
        validate_target(str(prefix))
        if event["existing"]:
            _snapshot_existing_event(connection, plan_id, archive_fd, prefix, event["id"])
            registered.update(_registered_archive_paths(connection, plan_id, event["id"]))
        elif archive_entry(str(prefix)) is not None:
            raise AdoptionError("Der neue Ereignisordner existiert bereits: " + str(prefix))

    target_stems = draft.get("target_stems") or {}
    seen_draft_keys = set()
    added = set()
    candidates = {}
    target_counts = Counter()
    planned_directories = set()
    file_issues = []
    xmp_anchors = []
    used_stems = {target_key(_legacy_family_key(Path(), path)) for path in registered}
    registered_keys = {target_key(path) for path in registered}
    filename_sequences = Counter()
    rows = connection.execute(
        """SELECT inventory.*, families.capture_time, families.review_required, copy.state AS review_copy
             FROM legacy_adoption_inventory inventory
             JOIN legacy_adoption_families families USING (job_id, family_key)
             LEFT JOIN legacy_adoption_review_copies copy USING (job_id, family_key)
            WHERE inventory.job_id = ? ORDER BY family_key, relative_path""",
        (job["id"],),
    )
    selections = list(_assigned_families(rows, draft, events, intervals, seen_draft_keys))
    # Existing global media are skipped entirely, not participants in a new
    # destination collision or duplicate numbering set. Only physical copies
    # which will actually be newly moved can require an indexed target name.
    # Do not discard partially registered families here: the existing
    # _family_duplicate_conflict guard must still reject their unsafe merge.
    new_selections = [
        selected for selected in selections
        if not all(registered_content(connection, registry, member["sha256"])
                   for member in selected[1])
    ]
    duplicate_indices, collision_indices, cohorts = _adoption_occurrence_sequences(new_selections, target_stems)
    occupied_targets = set()
    if filename_method == "script":
        cameras, bursts = _camera_tokens(selections)
        distinct, burst_ordinals = _script_capture_ordinals(new_selections, cameras, cohorts)
        exact_collisions = _exact_script_collisions(new_selections, cameras, bursts)
    @lru_cache(maxsize=128)
    def existing_names(folder):
        names = archive_entry.names(folder)
        stems = {PurePosixPath(_legacy_family_key(Path(), name)).name.casefold() for name in names}
        return names, stems

    for key, family, capture, event, (assigned, leaf, leaf_key, layout) in selections:
        if key.strip() != key:
            raise AdoptionError("Der Familienname ist für die globale Registry ungeeignet: " + key)
        if any(not member["sha256"] for member in family):
            raise AdoptionError("Die Familie konnte nicht vollständig inventarisiert werden: " + key)

        checksums = [member["sha256"] for member in family]
        duplicate = [_known_content(connection, registry, plan_id, checksum) for checksum in checksums]
        conflict = _family_duplicate_conflict(checksums, duplicate)
        if conflict:
            raise AdoptionError("Einzelne Mitglieder einer Dateifamilie sind bereits registriert "
                                "oder haben identischen Inhalt: " + key + " (" + conflict + ")")

        new_family = not all(duplicate)
        folder = _destination_folder(leaf, layout)
        if not new_family:
            targets = [None] * len(family)
        elif filename_method == "script" and key not in target_stems:
            camera, burst_group = cameras[key]
            same_second = (distinct[burst_group] > 1 or
                           (bursts[burst_group] > 1 and has_capture_fraction(capture)))
            generated_stem, generated_index, _ = capture_stem(
                capture, camera, set(), same_second=same_second,
            )
            number_all = generated_index == 0 and exact_collisions[
                (target_key(str(folder)), generated_stem.casefold())
            ] > 1
            targets = _automatic_family_targets(
                folder, key, family, capture, camera, same_second,
                *existing_names(str(folder)), used_stems,
                duplicate_index=duplicate_indices.get(key), number_all=number_all,
                burst_ordinal=burst_ordinals.get(key),
            )
        elif filename_method == "manual" and key not in target_stems and _has_bound_raw_reference(family):
            directory, targets = _manual_linked_targets(
                folder, key, family, duplicate_indices.get(key), archive_entry, occupied_targets,
                _leaf_directories(leaf, layout),
            )
            _plan_directories(connection, plan_id, directory, {"structure_enabled": False}, archive_entry)
        else:
            targets = _family_targets(
                folder, key, family, target_stems.get(key), archive_entry, registered_keys,
                used_stems, filename_sequences,
                duplicate_index=duplicate_indices.get(key),
                collision_index=collision_indices.get(key),
                occupied_paths=occupied_targets,
                sibling_names=archive_entry.names(str(folder)) if key in duplicate_indices else (),
            )
        for member, target in zip(family, targets, strict=True):
            source = member["relative_path"]
            if source.strip() != source or "\\" in source:
                raise AdoptionError("Der Quellpfad ist für die globale Registry ungeeignet: " + source)
            xmp_edit = None
            with relative_parent(source_fd, source) as (directory, name):
                with bound_file(directory, name) as (fd, info):
                    verify_inventory_identity(fd, info, json.loads(member["identity"]), member["sha256"])
                    metadata = json.loads(member["metadata_json"] or "{}")
                    raw_hint = (metadata.get("capture_identity") or {}).get("sidecar_raw")
                    if target is not None and metadata.get("media_type") == "xmp" and (
                        raw_hint or metadata.get("metadata_error")
                    ):
                        owner = raw_name_pair(family, targets, raw_hint) if raw_hint else None
                        reason = None
                        if metadata.get("metadata_error"):
                            reason = "XMP-Metadaten konnten nicht gelesen werden."
                        elif not owner:
                            reason = "Der referenzierte RAW-Master ist nicht eindeutig zugeordnet."
                        elif info.st_size > MAX_STREAM_BYTES:
                            reason = "Die XMP-Datei überschreitet die sichere Prüfgröße."
                        else:
                            try:
                                if info.st_size > MAX_XMP_BYTES:
                                    proof = large_xmp_proof(fd, info.st_size, raw_hint, owner[1])
                                    if proof.pop("original_sha256") != member["sha256"]:
                                        raise AdoptionError("XMP-Datei wurde während der Planung verändert: " + source)
                                    xmp_edit = proof or None
                                else:
                                    payload = os.pread(fd, info.st_size, 0)
                                    if len(payload) != info.st_size:
                                        raise AdoptionError("XMP-Datei wurde während der Planung verändert: " + source)
                                    xmp_edit = planned_edit(family, targets, payload, inventory_hint=raw_hint)
                            except (XmpPlanError, XmpReferenceError):
                                reason = "Der eingebettete RAW-Verweis konnte nicht sicher geprüft oder angepasst werden."
                            if filename_method == "manual" and xmp_edit is not None:
                                raise ManualXmpRenameConflict(
                                    "Die RAW-Umbenennung würde einen gebundenen XMP-Verweis ungültig machen. "
                                    "Plane mit unverändertem RAW-Namen oder wähle das TrueNAS-Skript. " + source
                                )
                        if reason:
                            file_issues.append({
                                "path": source, "reason": reason, "sha256": member["sha256"],
                                "identity_version": IDENTITY_VERSION,
                            })
                            if raw_hint:
                                xmp_anchors.append((source, raw_hint, key))
                            continue
            if target is not None:
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
            if xmp_edit is not None:
                connection.execute(
                    """UPDATE legacy_adoption_moves
                          SET current_sha256=?, current_size_bytes=?,
                              xmp_old_raw_name=?, xmp_new_raw_name=?
                        WHERE plan_id=? AND relative_path=?""",
                    (xmp_edit["current_sha256"], xmp_edit["current_size_bytes"],
                     xmp_edit["xmp_old_raw_name"], xmp_edit["xmp_new_raw_name"],
                     plan_id, source),
                )
        if not new_family:
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
    _retain_xmp_companions(connection, plan_id, job["id"], file_issues, xmp_anchors, new_selections,
                           draft.get("file_exclusions", {}))
    if file_issues:
        raise PlanFileIssues(file_issues)
    _check_planned_collisions(connection, plan_id)
    if (set(draft.get("capture_overrides") or {}) | set(draft.get("exclude_families") or [])
            | target_stems.keys()) - seen_draft_keys:
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


def _manual_method_blocker(connection, job_id, plan, draft):
    """Identify known bound RAW names that a manual plan could not preserve."""
    if plan["filename_method"] != "script":
        return None
    rows = connection.execute(
        """SELECT inventory.family_key, move.relative_path, move.target_path, move.xmp_old_raw_name
             FROM legacy_adoption_moves move
             JOIN legacy_adoption_inventory inventory
               ON inventory.job_id = ? AND inventory.relative_path = move.relative_path
            WHERE move.plan_id = ? AND move.target_path IS NOT NULL
            ORDER BY move.relative_path""",
        (job_id, plan["id"]),
    )
    raw_names, references = {}, []
    for row in rows:
        name = PurePosixPath(row["relative_path"]).name
        if row["xmp_old_raw_name"]:
            references.append(row)
        elif PurePosixPath(name).suffix.casefold() in RAW_EXTENSIONS:
            raw_names.setdefault((row["family_key"], name.casefold()), []).append(row)
    target_stems = draft.get("target_stems") or {}
    for sidecar in references:
        family, old_name = sidecar["family_key"], sidecar["xmp_old_raw_name"]
        owners = raw_names.get((family, old_name.casefold()), ())
        if len(owners) != 1:
            continue
        raw = owners[0]
        # Only make an early decision when manual collision handling keeps
        # the physical RAW name. Overrides still need normal plan validation.
        if family in target_stems:
            continue
        manual_name = PurePosixPath(raw["relative_path"]).name
        if manual_name != old_name:
            return {"path": sidecar["relative_path"], "raw_reference": old_name, "raw_name": manual_name}
    return None


def create_plan(library, registry_path: Path, job_id: str, draft=None, *, draft_revision=None,
                allow_existing=False, filename_method="manual", replace_plan_id=None) -> dict:
    if filename_method not in {"manual", "script"}:
        raise AdoptionError("Wähle eine verfügbare Durchführungsmethode.")
    plan_id = uuid4().hex
    with database_connection(library.database_path) as connection, closing(sqlite3.connect(
        registry_path.absolute().as_uri() + "?mode=ro", uri=True,
    )) as registry:
        connection.execute("BEGIN IMMEDIATE")
        registry.execute("BEGIN")
        if not allow_existing:
            require_no_managed_data(connection)
        job = _job(connection, library.library_id, job_id)
        if replace_plan_id is not None:
            from app.legacy_adoption_verify import _plan, assert_original_layout

            previous = _plan(connection, job_id)
            if (previous["id"] != replace_plan_id or previous["state"] != "prepared"
                    or connection.execute(
                        "SELECT 1 FROM legacy_adoption_execution WHERE plan_id = ?", (replace_plan_id,),
                    ).fetchone()):
                raise AdoptionError("Der bestätigte Verschiebeplan ist eingefroren.")
            draft = json.loads(previous["draft_json"])
            if filename_method == "manual" and (blocker := _manual_method_blocker(connection, job_id, previous, draft)):
                raise ManualXmpRenameConflict(
                    "Die manuelle Methode kann den gebundenen XMP-Verweis nicht anpassen. " + blocker["path"]
                )
            assert_original_layout(connection, library, job, previous)
            connection.execute("DELETE FROM legacy_adoption_plans WHERE id = ?", (replace_plan_id,))
        if draft_revision is not None:
            if job["draft_revision"] != draft_revision:
                raise AdoptionError("Der Entwurf wurde in einer anderen Sitzung geändert. Lade ihn erneut.")
            draft = json.loads(job["draft_json"])
        draft = {key: value for key, value in (draft or {}).items() if key != "planning_attempt"}
        definitions = draft.get("events")
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
            """INSERT INTO legacy_adoption_plans (job_id, id, state, draft_json, events_json, filename_method)
               VALUES (?, ?, 'prepared', ?, ?, ?)""",
            (job_id, plan_id, json.dumps(draft), json.dumps(events), filename_method),
        )
        with ExitStack() as stack:
            source, archive = _roots(stack, library, job)
            _plan_moves(connection, registry, job, plan_id, events, intervals, draft, source, archive, filename_method)
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
        renamed = connection.execute(
            """SELECT count(*), count(DISTINCT inventory.family_key)
                 FROM legacy_adoption_moves move
                 JOIN legacy_adoption_inventory inventory
                   ON inventory.job_id = ? AND inventory.relative_path = move.relative_path
                WHERE move.plan_id = ? AND move.target_path IS NOT NULL
                  AND substr(move.target_path, -1 - length(json_extract(inventory.metadata_json, '$.filename')))
                      != '/' || json_extract(inventory.metadata_json, '$.filename')""",
            (job_id, plan["id"]),
        ).fetchone()
        draft = json.loads(plan["draft_json"])
        return {
            "rename_files": renamed[0], "rename_families": renamed[1],
            "excluded_files": file_issue_summary((draft.get("file_exclusions") or {}).values()),
            "manual_blocker": _manual_method_blocker(connection, job_id, plan, draft) if execution is None else None,
            "id": plan["id"], "state": plan["state"], "counts": counts, "filename_method": plan["filename_method"],
            "execution": dict(execution) if execution else None,
            "inventory_duplicates": connection.execute(
                "SELECT count(*) FROM legacy_adoption_inventory WHERE job_id = ? AND disposition = 'duplicate'",
                (job_id,),
            ).fetchone()[0],
            "move_files": volume[0], "move_bytes": volume[1], "move_families": volume[2],
            "library_name": library.display_name,
            "documents_at": plan["documents_at"],
            "folder_moves": [dict(row) for row in connection.execute(
                """SELECT source_path, target_path, file_count FROM legacy_adoption_folder_moves
                    WHERE plan_id = ? ORDER BY source_path LIMIT 100""", (plan["id"],),
            )],
            "source_root": job["source_root"], "archive_root": job["archive_root"],
            "draft": draft, "events": json.loads(plan["events_json"]),
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


def plan_moves(library, job_id: str, *, after: str = "", limit: int = 100, renamed: bool = False):
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
                  AND (NOT ? OR substr(move.target_path, -1 - length(json_extract(inventory.metadata_json, '$.filename')))
                      != '/' || json_extract(inventory.metadata_json, '$.filename'))
                ORDER BY move.relative_path LIMIT ?""",
            (job_id, after, renamed, max(1, min(limit, 200))),
        )
        return [{
            **dict(row), "source": str(Path(job["source_root"]) / row["relative_path"]),
            "target": str(Path(job["archive_root"]) / row["target_path"]) if row["target_path"] else None,
        } for row in rows]
