"""Build and persist manual legacy moves without changing the archive catalogue."""
from collections import Counter
from contextlib import closing, ExitStack
from datetime import date, datetime
from functools import lru_cache
from itertools import combinations, groupby
import json
import os
from pathlib import Path, PurePosixPath
import sqlite3
import stat
from uuid import uuid4

from app import legacy_adoption_dataset as dataset
from app.database import database_connection
from app.event_inventory import event_root_relative
from app.event_layout import ensure_event_layout_snapshot, get_global_default, layout_paths, normalize_layout, validate_input_path
from app.event_leaf_layouts import stored_leaf_layouts
from app.event_naming import (
    naming_from_library_settings, naming_snapshot_for_new_event,
    render_event_folder_name, render_no_event_folder_name,
)
from app.event_timeline import continuous_event_overlaps, no_event_segment_overlaps, normalize_no_event_segments, normal_event_ranges
from app.legacy_adoption_inventory import _job
from app.legacy_adoption_mode import require_no_managed_data
from app.legacy_adoption_paths import (
    AdoptionError, bound_directory, bound_file, relative_parent,
    target_key, validate_target,
)
from app.metadata import LOCAL_TIMEZONE
from app.operation_health import read_session
from app.subevents import assignment_target, normalize_subevents


def _event_id():
    return "EVENT_" + uuid4().hex.upper()


def _local_capture(value):
    result = datetime.fromisoformat(value)
    if result.year <= 1904 or len(value) < 16:
        raise AdoptionError("Die bestätigte Aufnahmezeit benötigt Datum und Uhrzeit.")
    if result.tzinfo is None:
        result = result.replace(tzinfo=LOCAL_TIMEZONE)
    return result.isoformat()


def _range(start, end):
    if not isinstance(start, str) or not isinstance(end, str):
        raise AdoptionError("Das Ereignis benötigt ein Anfangs- und Enddatum.")
    if date.fromisoformat(start).isoformat() != start or date.fromisoformat(end).isoformat() != end or end < start:
        raise AdoptionError("Der Ereigniszeitraum ist ungültig.")
    return (start + "T00:00:00", end + "T23:59:59")


def _layout(definition, defaults, inherited=None):
    values = definition.get("folder_layout")
    if values is None:
        return inherited or defaults
    if values.get("mode") == "default":
        return defaults
    layout = normalize_layout(values.get("layout") or defaults["layout"])
    for path in layout_paths(layout):
        validate_target(path)
    enabled = bool(values.get("structure_enabled", defaults["structure_enabled"]))
    return {"structure_enabled": enabled, "layout": layout,
            "input_path": validate_input_path(layout, values.get("input_path", defaults["input_path"]),
                                              structure_enabled=enabled)}


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
        "leaf_layouts": stored_leaf_layouts(connection, event_id),
    }


def _draft_event(definition, naming, defaults):
    if "existing_id" in definition:
        raise AdoptionError("Vorhandene Archivereignisse können bei der Ersteinrichtung nicht ergänzt werden.")
    kind = definition.get("event_kind", "event")
    parent_layout = _layout(definition, defaults)
    if kind == "event":
        start, end = _range(definition.get("start_date"), definition.get("end_date"))
        segments = []
        ranges = [(start, end)]
        name = str(definition.get("name") or "").strip()
        folder = render_event_folder_name(
            event_name=name, start_date=start[:10], end_date=end[:10],
            start_time=None, end_time=None, uses_time_range=False, naming=naming,
        )
        definitions = definition.get("children") or []
        normalized = normalize_subevents(
            [{**item, "id": str(index)} for index, item in enumerate(definitions)], start, end, naming=naming,
        )
        children = [
            {**child, "id": _event_id(),
             "folder_layout": _layout(definitions[int(child["id"])], defaults, inherited=parent_layout)}
            for child in normalized
        ]
        child_names = {target_key(child["folder_name"]) for child in children}
        if len(child_names) != len(children):
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


def _assert_timeline(connection, job_id, events):
    for event in events:
        for start, end in event["ranges"]:
            normal = continuous_event_overlaps(connection, job_id, start, end, exclude_event_id=event["id"])
            free = no_event_segment_overlaps(connection, job_id, start, end, exclude_event_id=event["id"])
            if normal or free:
                conflict = (normal or free)[0]
                raise AdoptionError("Zeitüberschneidung mit „" + conflict["name"] + "“. "
                                    "Prüfe den gespeicherten Zeitraum.")
    for first, second in combinations(events, 2):
        if first["id"] == second["id"] or any(
            a <= d and c <= b for a, b in first["ranges"] for c, d in second["ranges"]
        ):
            raise AdoptionError("Die im Auftrag gewählten Ereignisse überschneiden sich.")


def preview_draft(library, job_id, draft):
    """Read-only planning feedback, never a move/registration authority."""
    from bisect import bisect_right
    with database_connection(library.database_path) as connection:
        connection.execute('BEGIN')
        require_no_managed_data(connection)
        job = _job(connection, library.library_id, job_id)
        if job['state'] != 'inventoried':
            raise AdoptionError('Die Inventur muss zuerst abgeschlossen werden.')
        definitions = draft.get('events') or []
        if not definitions:
            return {'valid': True, 'conflicts': [], 'events': []}
        naming = naming_snapshot_for_new_event(naming_from_library_settings(library.settings))
        defaults = get_global_default(connection)
        events = [_draft_event(definition, naming, defaults) for definition in definitions]
        conflicts = []
        for (first_index, first), (second_index, second) in combinations(enumerate(events), 2):
            if first['id'] == second['id'] or any(a <= d and c <= b for a, b in first['ranges'] for c, d in second['ranges']):
                conflicts.append({'index': first_index, 'other_index': second_index, 'kind': 'draft',
                                  'name': second['name'], 'start': first['start_datetime'], 'end': first['end_datetime']})
        if conflicts:
            return {'valid': False, 'conflicts': conflicts, 'events': []}
        # Keep the final plan's existing timeline and folder collision gate.
        _assert_timeline(connection, job_id, events)
        prefixes = [target_key(str(event_root_relative(event))) for event in events]
        if len(set(prefixes)) != len(prefixes):
            raise AdoptionError('Mehrere Ereignisse beanspruchen denselben Zielordner.')
        intervals = sorted((start, end, index) for index, event in enumerate(events) for start, end in event['ranges'])
        starts = [item[0] for item in intervals]
        counts = [{'families': 0, 'days': set()} for _ in events]
        overrides = {key: _local_capture(value) for key, value in draft.get('capture_overrides', {}).items()}
        exclusions = set(draft.get('exclude_families') or [])
        for row in connection.execute(
            '''SELECT families.family_key,families.capture_time,families.review_required,copy.state AS review_copy
               FROM legacy_adoption_families families
               LEFT JOIN legacy_adoption_review_copies copy USING(job_id,family_key)
               WHERE families.job_id=?''', (job_id,),
        ):
            key = row['family_key']
            if key in exclusions or row['review_copy'] or (row['review_required'] and key not in overrides):
                continue
            capture = overrides.get(key, row['capture_time'])
            if not capture:
                continue
            at = bisect_right(starts, capture[:19]) - 1
            if at >= 0 and capture[:19] <= intervals[at][1]:
                count = counts[intervals[at][2]]
                count['families'] += 1
                count['days'].add(capture[:10])
        return {'valid': True, 'conflicts': [], 'events': [
            {'name': event['name'], 'start': event['start_datetime'], 'end': event['end_datetime'],
             'families': count['families'], 'days': len(count['days'])}
            for event, count in zip(events, counts)
        ]}


def _target_leaf(event, capture):
    prefix = event_root_relative(event)
    assigned = assignment_target(event["id"], event["children"], capture[:19])
    child = next((item for item in event["children"] if item["id"] == assigned), None)
    if child is not None:
        prefix /= child["folder_name"]
    leaf_key = assigned
    if event["preserve_day_folders"]:
        prefix /= capture[:10]
        leaf_key += "@" + capture[:10]
    layouts = event["leaf_layouts"]
    layout = layouts.get(leaf_key) or layouts.get(assigned) or (
        child.get("folder_layout") if child is not None else None
    ) or event["folder_layout"]
    return assigned, prefix, leaf_key, layout


def _plan_directories(connection, plan_id, leaf, layout, archive_entry):
    directories = [leaf]
    if layout["structure_enabled"]:
        directories.extend(leaf / part for part in layout_paths(layout["layout"]))
    for directory in directories:
        for parent in (directory, *directory.parents):
            if not parent.parts:
                continue
            value = str(parent)
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


def _plan_moves(connection, registry, job, plan_id, events, draft, source_fd, archive_fd):
    archive_entry = _archive_probe(archive_fd)
    for event in events:
        prefix = event_root_relative(event)
        validate_target(str(prefix))
        if archive_entry(str(prefix)) is not None:
            raise AdoptionError("Der neue Ereignisordner existiert bereits: " + str(prefix))

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
        eligible = [event for event in events if any(a <= capture[:19] <= b for a, b in event["ranges"])]
        if not eligible:
            continue
        if len(eligible) != 1:
            raise AdoptionError("Die Aufnahmezeit trifft mehrere Ereignisse: " + key)
        event = eligible[0]
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
            _store_leaf(event, leaf_key, leaf, layout)
            _plan_directories(connection, plan_id, leaf, layout, archive_entry)
            planned_directories.add((event["id"], leaf_key))
    for event in events:
        planned_leaves = {key.split("@", 1)[0] for key in event["leaf_layouts"]}
        for child in event["children"]:
            if child["id"] not in planned_leaves:
                path = event_root_relative(event) / child["folder_name"]
                _store_leaf(event, child["id"], path, child["folder_layout"])
                _plan_directories(connection, plan_id, path, child["folder_layout"], archive_entry)
    _check_planned_collisions(connection, plan_id)
    if (overrides.keys() | exclusions | target_stems.keys()) - seen_draft_keys:
        raise AdoptionError("Mindestens eine Dateifamilie aus dem Entwurf fehlt in der Inventur.")
    if not added:
        raise AdoptionError("Die Auswahl enthält keine neuen, vollständig datierten Dateifamilien.")
    if any(event["id"] not in added for event in events):
        raise AdoptionError("Mindestens ein gewähltes Ereignis erhält keine neuen Dateifamilien.")
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


def create_plan(library, registry_path: Path, job_id: str, draft=None, *, draft_revision=None) -> dict:
    plan_id = uuid4().hex
    with database_connection(library.database_path) as connection, closing(sqlite3.connect(
        registry_path.absolute().as_uri() + "?mode=ro", uri=True,
    )) as registry:
        connection.execute("BEGIN IMMEDIATE")
        registry.execute("BEGIN")
        require_no_managed_data(connection)
        job = _job(connection, library.library_id, job_id)
        if draft_revision is not None:
            if job["draft_revision"] != draft_revision:
                raise AdoptionError("Der Entwurf wurde in einer anderen Sitzung geändert. Lade ihn erneut.")
            draft = json.loads(job["draft_json"])
        definitions = (draft or {}).get("events")
        if not isinstance(definitions, list) or not 1 <= len(definitions) <= 200:
            raise AdoptionError("Wähle mindestens ein Ereignis und höchstens 200 Ereignisse.")
        if job["state"] != "inventoried":
            raise AdoptionError("Die Inventur muss zuerst abgeschlossen werden.")
        if connection.execute("SELECT 1 FROM legacy_adoption_plans WHERE job_id = ?", (job_id,)).fetchone():
            raise AdoptionError("Ein Verschiebeplan ist bereits gespeichert.")
        naming = naming_snapshot_for_new_event(naming_from_library_settings(library.settings))
        defaults = get_global_default(connection)
        events = [_draft_event(definition, naming, defaults) for definition in definitions]
        prefixes = [target_key(str(event_root_relative(event))) for event in events]
        if len(set(prefixes)) != len(prefixes):
            raise AdoptionError("Mehrere Ereignisse beanspruchen denselben Zielordner.")
        _assert_timeline(connection, job_id, events)
        connection.execute(
            """INSERT INTO legacy_adoption_plans (job_id, id, state, draft_json, events_json)
               VALUES (?, ?, 'prepared', ?, ?)""",
            (job_id, plan_id, json.dumps(draft), json.dumps(events)),
        )
        with ExitStack() as stack:
            source, archive = _roots(stack, library, job)
            _plan_moves(connection, registry, job, plan_id, events, draft, source, archive)
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
            """SELECT count(*), coalesce(sum(inventory.size_bytes), 0)
                 FROM legacy_adoption_moves AS move JOIN legacy_adoption_inventory AS inventory
                   ON inventory.job_id = ? AND inventory.relative_path = move.relative_path
                WHERE move.plan_id = ? AND move.target_path IS NOT NULL""",
            (job_id, plan["id"]),
        ).fetchone()
        return {
            "id": plan["id"], "state": plan["state"], "counts": counts,
            "execution": dict(execution) if execution else None,
            "move_files": volume[0], "move_bytes": volume[1],
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
