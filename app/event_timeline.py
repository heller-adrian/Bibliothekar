from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from app.database import database_connection


class EventTimelineError(ValueError):
    pass


def _date(value: Any) -> str:
    raw = str(value or '').strip()
    try:
        datetime.strptime(raw, '%Y-%m-%d')
    except ValueError as exc:
        raise EventTimelineError(f'Ungueltiges Datum: {raw or "—"}.') from exc
    return raw


def _time(value: Any) -> str:
    raw = str(value or '').strip()
    try:
        datetime.strptime(raw, '%H:%M')
    except ValueError as exc:
        raise EventTimelineError(f'Ungueltige Uhrzeit: {raw or "—"}.') from exc
    return raw


def normalize_no_event_segments(values: Any) -> list[dict[str, str]]:
    """Validate and normalize per-day no-event time segments."""
    if not isinstance(values, list) or not values:
        raise EventTimelineError('Fuer „Ohne Ereignis“ muss mindestens ein Tag ausgewaehlt werden.')
    result: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in values:
        if not isinstance(item, dict):
            raise EventTimelineError('Ein „Ohne Ereignis“-Zeitsegment ist ungueltig.')
        day = _date(item.get('day_key'))
        start = _time(item.get('start_time') or '00:00')
        end = _time(item.get('end_time') or '23:59')
        start_dt = f'{day}T{start}:00'
        end_dt = f'{day}T{end}:59'
        if end_dt < start_dt:
            raise EventTimelineError(f'Am {day} liegt das Ende vor dem Beginn.')
        key = (day, start, end)
        if key in seen:
            continue
        seen.add(key)
        result.append({
            'day_key': day,
            'start_time': start,
            'end_time': end,
            'start_datetime': start_dt,
            'end_datetime': end_dt,
        })
    result.sort(key=lambda x: (x['day_key'], x['start_time'], x['end_time']))
    # Segments of the same no-event collection must not overlap each other.
    previous: dict[str, str] = {}
    for segment in result:
        prev_end = previous.get(segment['day_key'])
        if prev_end and segment['start_datetime'] <= prev_end:
            raise EventTimelineError(
                f'Die „Ohne Ereignis“-Zeitsegmente am {segment["day_key"]} ueberlappen sich.'
            )
        previous[segment['day_key']] = segment['end_datetime']
    return result


def list_event_segments(database_path: Path, event_id: str) -> list[dict[str, Any]]:
    with database_connection(database_path) as connection:
        rows = connection.execute(
            """SELECT * FROM event_time_segments WHERE event_id = ?
               ORDER BY start_datetime, id""", (event_id,)
        ).fetchall()
    return [dict(row) for row in rows]


def replace_event_segments(
    connection,
    *,
    event_id: str,
    job_id: str,
    segments: list[dict[str, str]],
    now: str,
    source: str = 'user',
) -> None:
    connection.execute('DELETE FROM event_time_segments WHERE event_id = ?', (event_id,))
    connection.executemany(
        """INSERT INTO event_time_segments(
               event_id,job_id,day_key,start_time,end_time,start_datetime,end_datetime,
               source,created_at,updated_at
           ) VALUES (?,?,?,?,?,?,?,?,?,?)""",
        [(
            event_id, job_id, s['day_key'], s['start_time'], s['end_time'],
            s['start_datetime'], s['end_datetime'], source, now, now,
        ) for s in segments],
    )


def family_ids_for_segments(connection, job_id: str, segments: list[dict[str, str]]) -> list[int]:
    rows = connection.execute(
        """SELECT id, selected_capture_time FROM file_families
           WHERE job_id = ? AND selected_capture_time IS NOT NULL
           ORDER BY selected_capture_time, id""", (job_id,)
    ).fetchall()
    selected: list[int] = []
    for row in rows:
        capture = str(row['selected_capture_time'] or '')[:19]
        if any(s['start_datetime'] <= capture <= s['end_datetime'] for s in segments):
            selected.append(int(row['id']))
    return selected


def family_ids_for_continuous_range(
    connection, job_id: str, start_datetime: str, end_datetime: str
) -> list[int]:
    rows = connection.execute(
        """SELECT id FROM file_families
           WHERE job_id = ? AND selected_capture_time IS NOT NULL
             AND substr(selected_capture_time,1,19) BETWEEN ? AND ?
           ORDER BY selected_capture_time, id""",
        (job_id, start_datetime, end_datetime),
    ).fetchall()
    return [int(r['id']) for r in rows]


def no_event_segment_overlaps(
    connection, job_id: str, start_datetime: str, end_datetime: str, *, exclude_event_id: str | None = None
) -> list[dict[str, Any]]:
    sql = """SELECT s.*, e.name, e.status, e.folder_name
             FROM event_time_segments s JOIN events e ON e.id=s.event_id
             WHERE s.job_id=? AND e.event_kind='no_event'
               AND s.start_datetime <= ? AND s.end_datetime >= ?"""
    params: list[Any] = [job_id, end_datetime, start_datetime]
    if exclude_event_id:
        sql += ' AND s.event_id != ?'
        params.append(exclude_event_id)
    sql += ' ORDER BY s.start_datetime'
    return [dict(r) for r in connection.execute(sql, params).fetchall()]


def continuous_event_overlaps(
    connection, job_id: str, start_datetime: str, end_datetime: str, *, exclude_event_id: str | None = None
) -> list[dict[str, Any]]:
    """Return normal root events whose effective interval overlaps.

    For a parent with a child time range, the child interval is authoritative.
    """
    sql = """SELECT e.*,
                    COALESCE((SELECT MIN(c.start_datetime) FROM events c WHERE c.parent_event_id=e.id), e.start_datetime) AS effective_start,
                    COALESCE((SELECT MAX(c.end_datetime) FROM events c WHERE c.parent_event_id=e.id), e.end_datetime) AS effective_end
             FROM events e
             WHERE e.job_id=? AND e.event_level='parent' AND e.event_kind='event'
               AND e.status IN ('draft','planned','applied','archived')
               AND COALESCE((SELECT MIN(c.start_datetime) FROM events c WHERE c.parent_event_id=e.id), e.start_datetime) <= ?
               AND COALESCE((SELECT MAX(c.end_datetime) FROM events c WHERE c.parent_event_id=e.id), e.end_datetime) >= ?"""
    params: list[Any] = [job_id, end_datetime, start_datetime]
    if exclude_event_id:
        sql += ' AND e.id != ?'
        params.append(exclude_event_id)
    sql += ' ORDER BY effective_start, e.id'
    return [dict(r) for r in connection.execute(sql, params).fetchall()]


def effective_event_interval(connection, event_id: str) -> tuple[str, str] | None:
    row=connection.execute(
        """SELECT e.start_datetime,e.end_datetime,
                  COALESCE((SELECT MIN(c.start_datetime) FROM events c WHERE c.parent_event_id=e.id),e.start_datetime) AS effective_start,
                  COALESCE((SELECT MAX(c.end_datetime) FROM events c WHERE c.parent_event_id=e.id),e.end_datetime) AS effective_end
           FROM events e WHERE e.id=?""",(event_id,)
    ).fetchone()
    return (str(row['effective_start'])[:19],str(row['effective_end'])[:19]) if row else None


def trim_no_event_segments_for_range(
    connection, job_id: str, start_datetime: str, end_datetime: str, *, now: str,
    exclude_event_ids: set[str] | None = None,
) -> list[str]:
    """Remove an occupied normal-event range from no-event segments.

    A segment can be shortened or split. Returns affected no-event event ids.
    """
    overlaps = no_event_segment_overlaps(connection, job_id, start_datetime, end_datetime)
    excluded = {str(v) for v in (exclude_event_ids or set())}
    affected: set[str] = set()
    for row in overlaps:
        if str(row['event_id']) in excluded:
            continue
        affected.add(str(row['event_id']))
        original_start = str(row['start_datetime'])
        original_end = str(row['end_datetime'])
        connection.execute('DELETE FROM event_time_segments WHERE id=?', (row['id'],))
        pieces: list[tuple[str, str]] = []
        if original_start < start_datetime:
            left_end = (datetime.fromisoformat(start_datetime) - timedelta(seconds=1)).isoformat(timespec='seconds')
            if original_start <= left_end:
                pieces.append((original_start, left_end))
        if original_end > end_datetime:
            right_start = (datetime.fromisoformat(end_datetime) + timedelta(seconds=1)).isoformat(timespec='seconds')
            if right_start <= original_end:
                pieces.append((right_start, original_end))
        for a, b in pieces:
            connection.execute(
                """INSERT INTO event_time_segments(event_id,job_id,day_key,start_time,end_time,
                   start_datetime,end_datetime,source,created_at,updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (row['event_id'], job_id, a[:10], a[11:16], b[11:16], a, b, 'cascade', now, now),
            )
    return sorted(affected)


def cascade_preview_for_interval(
    connection,
    job_id: str,
    event_id: str,
    start_datetime: str,
    end_datetime: str,
) -> dict[str, Any]:
    normal = continuous_event_overlaps(
        connection, job_id, start_datetime, end_datetime, exclude_event_id=event_id
    )
    no_event = no_event_segment_overlaps(
        connection, job_id, start_datetime, end_datetime, exclude_event_id=event_id
    )
    items: list[dict[str, Any]] = []
    can_apply = True
    for row in normal:
        a = str(row['effective_start'])[:19]
        b = str(row['effective_end'])[:19]
        if a < start_datetime <= b <= end_datetime:
            action='trim_end'; proposed_end=(datetime.fromisoformat(start_datetime)-timedelta(seconds=1)).isoformat(timespec='seconds'); proposed_start=a
        elif start_datetime <= a <= end_datetime < b:
            action='trim_start'; proposed_start=(datetime.fromisoformat(end_datetime)+timedelta(seconds=1)).isoformat(timespec='seconds'); proposed_end=b
        elif start_datetime <= a and b <= end_datetime:
            action='fully_covered'; proposed_start=None; proposed_end=None; can_apply=False
        else:
            action='split_required'; proposed_start=None; proposed_end=None; can_apply=False
        if str(row['status']) == 'archived':
            can_apply=False
        items.append({
            'kind':'event','event_id':str(row['id']),'name':str(row['name']),
            'status':str(row['status']),'current_start':a,'current_end':b,
            'action':action,'proposed_start':proposed_start,'proposed_end':proposed_end,
            'automatic': action in {'trim_end','trim_start'} and str(row['status']) != 'archived',
        })
    seen_segments=set()
    for row in no_event:
        key=(str(row['event_id']),int(row['id']))
        if key in seen_segments: continue
        seen_segments.add(key)
        if str(row['status']) == 'archived': can_apply=False
        items.append({
            'kind':'no_event','event_id':str(row['event_id']),'name':'Ohne Ereignis',
            'status':str(row['status']),'current_start':str(row['start_datetime']),
            'current_end':str(row['end_datetime']),'action':'trim_or_split_segment',
            'automatic': str(row['status']) != 'archived',
        })
    return {'has_conflicts':bool(items),'can_apply_automatically':can_apply,'items':items}


def _set_continuous_event_interval(connection, event_id: str, new_start: str, new_end: str, now: str) -> list[int]:
    """Set one normal event interval and rebuild its membership from capture time.

    0.17.1 deliberately does *not* derive the new membership from the event's
    previous assignment rows.  Those rows may already have been trimmed by an
    earlier coordinated edit.  The current date/time definition is canonical.
    """
    event=connection.execute('SELECT * FROM events WHERE id=?',(event_id,)).fetchone()
    if event is None: return []
    children=connection.execute('SELECT * FROM events WHERE parent_event_id=? ORDER BY start_datetime',(event_id,)).fetchall()
    full_start=new_start[11:19]=='00:00:00'
    full_end=new_end[11:19]=='23:59:59'
    parent_start=f'{new_start[:10]}T00:00:00'
    parent_end=f'{new_end[:10]}T23:59:59'
    connection.execute('UPDATE events SET start_datetime=?,end_datetime=?,updated_at=?,revision=revision+1 WHERE id=?',(parent_start,parent_end,now,event_id))
    if full_start and full_end:
        if children:
            connection.execute('DELETE FROM events WHERE parent_event_id=?',(event_id,))
        assignment_event_id=event_id
    else:
        child=children[0] if children else None
        if child is None:
            import uuid
            child_id='EVENT_'+uuid.uuid4().hex.upper()
            child_name=str(event['name'])
            folder=f'{new_start[11:16].replace(":","-")} - {new_end[11:16].replace(":","-")} - {child_name}'
            connection.execute(
                """INSERT INTO events(id,job_id,parent_event_id,event_level,name,start_datetime,end_datetime,
                   uses_time_range,folder_name,status,created_at,updated_at,event_kind,preserve_day_folders,
                   revision,applied_at,archived_at,notes,timeline_model)
                   VALUES (?,?,?,'child',?,?,?,1,?,?,?,?,'event',?,1,?,NULL,'','continuous')""",
                (child_id,event['job_id'],event_id,child_name,new_start,new_end,folder,event['status'],now,now,
                 int(event['preserve_day_folders'] or 0),event['applied_at']),
            )
            assignment_event_id=child_id
        else:
            assignment_event_id=str(child['id'])
            child_name=str(child['name'] or event['name'])
            folder=f'{new_start[11:16].replace(":","-")} - {new_end[11:16].replace(":","-")} - {child_name}'
            connection.execute(
                'UPDATE events SET start_datetime=?,end_datetime=?,folder_name=?,updated_at=?,revision=revision+1 WHERE id=?',
                (new_start,new_end,folder,now,assignment_event_id),
            )

    old_rows=connection.execute(
        """SELECT DISTINCT ea.family_id
           FROM event_assignments ea JOIN events e ON e.id=ea.event_id
           WHERE COALESCE(e.parent_event_id,e.id)=? AND ea.family_id IS NOT NULL""",
        (event_id,),
    ).fetchall()
    old_ids={int(row['family_id']) for row in old_rows}

    # Canonical membership = every family in this import whose selected capture
    # time lies inside the new effective interval.  Exclude only families that
    # are still owned by another active event after the coordinated trims.
    candidates=family_ids_for_continuous_range(connection, str(event['job_id']), new_start, new_end)
    keep=[]
    for fid in candidates:
        conflict=connection.execute(
            """SELECT 1
               FROM event_assignments ea JOIN events e ON e.id=ea.event_id
               WHERE ea.family_id=?
                 AND COALESCE(e.parent_event_id,e.id) != ?
                 AND e.status IN ('draft','planned','applied','archived')
               LIMIT 1""",
            (fid,event_id),
        ).fetchone()
        if conflict is None:
            keep.append(int(fid))

    connection.execute('DELETE FROM event_assignments WHERE event_id=? OR event_id IN (SELECT id FROM events WHERE parent_event_id=?)',(event_id,event_id))
    if keep:
        connection.executemany(
            "INSERT INTO event_assignments(event_id,family_id,file_id,assignment_source,created_at) VALUES (?,?,NULL,'date_time_range',?)",
            [(assignment_event_id,fid,now) for fid in keep],
        )
    return sorted(old_ids-set(keep))


def apply_cascade_for_interval(
    connection,
    job_id: str,
    event_id: str,
    start_datetime: str,
    end_datetime: str,
    *,
    now: str,
    allow_archived_manual: bool = False,
) -> dict[str, Any]:
    preview=cascade_preview_for_interval(connection,job_id,event_id,start_datetime,end_datetime)
    archived_items=[item for item in preview['items'] if str(item.get('status')) == 'archived']
    hard_items=[item for item in preview['items'] if str(item.get('status')) != 'archived' and not bool(item.get('automatic'))]
    if hard_items or (archived_items and not allow_archived_manual):
        raise EventTimelineError(
            'Die Zeitänderung betrifft ein archiviertes Ereignis oder würde ein anderes Ereignis vollständig teilen/überdecken. '
            'Dieser Fall muss über einen gemeinsamen manuellen Änderungsauftrag bearbeitet werden.'
        )
    affected=[]
    removed_by_event: dict[str,list[int]] = {}
    for item in preview['items']:
        if item['kind']=='no_event' or str(item.get('status')) == 'archived':
            continue
        removed = _set_continuous_event_interval(connection,item['event_id'],item['proposed_start'],item['proposed_end'],now)
        removed_by_event[item['event_id']] = removed
        if item['status']=='applied':
            connection.execute('UPDATE events SET resort_required=1 WHERE id=?',(item['event_id'],))
        affected.append(item['event_id'])
    archived_no_event_ids={str(item['event_id']) for item in archived_items if item.get('kind')=='no_event'}
    no_events=trim_no_event_segments_for_range(
        connection,job_id,start_datetime,end_datetime,now=now,exclude_event_ids=archived_no_event_ids
    )
    for eid in no_events:
        ev=connection.execute('SELECT status FROM events WHERE id=?',(eid,)).fetchone()
        if ev and str(ev['status'])=='applied':
            connection.execute('UPDATE events SET resort_required=1,updated_at=? WHERE id=?',(now,eid))
        # Remove assignments now covered by the edited normal event.
        rows=connection.execute(
            """SELECT ea.id,ea.family_id,ff.selected_capture_time FROM event_assignments ea
               JOIN file_families ff ON ff.id=ea.family_id
               WHERE ea.event_id=? AND ea.family_id IS NOT NULL""",(eid,)
        ).fetchall()
        removed=[int(r['family_id']) for r in rows if start_datetime <= str(r['selected_capture_time'] or '')[:19] <= end_datetime]
        connection.executemany('DELETE FROM event_assignments WHERE id=?',[(int(r['id']),) for r in rows if int(r['family_id']) in set(removed)])
        removed_by_event[eid]=removed
        affected.append(eid)
    return {
        'preview':preview,'affected_event_ids':sorted(set(affected)),
        'removed_by_event':removed_by_event,'archived_manual_items':archived_items,
    }
