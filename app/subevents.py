"""Optional organizational children; they never define parent occupancy."""
from datetime import datetime
import uuid

from app.event_naming import normalize_event_naming, render_subevent_folder_name


def _legacy_subevent_naming():
    naming = normalize_event_naming({})
    naming["subevent_prefix_mode"] = "legacy_datetime_range"
    naming["subevent_prefix_enabled"] = True
    return naming


def normalize_subevents(values, start, end, naming=None):
    result=[]
    effective_naming = _legacy_subevent_naming() if naming is None else naming
    for value in values or []:
        name=str(value.get('name') or '').strip()
        if not name or any(x in name for x in ('/','\\','\0')):
            raise ValueError('Ein Unterereignis benötigt einen gültigen Namen.')
        a=str(value.get('start_datetime') or '')
        b=str(value.get('end_datetime') or '')
        if len(a)==16:a+=':00'
        if len(b)==16:b+=':59'
        datetime.fromisoformat(a);datetime.fromisoformat(b)
        if not start<=a<=b<=end:
            raise ValueError('Unterereignisse müssen innerhalb des durchgehenden Elternzeitraums liegen.')
        result.append({
            'id':value.get('id'),
            'name':name,
            'start_datetime':a,
            'end_datetime':b,
            'start_time':a[11:16],
            'end_time':b[11:16],
            'folder_name':render_subevent_folder_name(
                event_name=name,
                start_datetime=a,
                end_datetime=b,
                naming=effective_naming,
                parent_start_datetime=start,
                parent_end_datetime=end,
            ),
        })
    result.sort(key=lambda x:(x['start_datetime'],x['end_datetime']))
    if any(a['end_datetime']>=b['start_datetime'] for a,b in zip(result,result[1:])):
        raise ValueError('Organisatorische Unterereignisse dürfen sich nicht überschneiden.')
    return result


def store_subevents(connection,event_id,segments,now):
    parent=dict(connection.execute('SELECT * FROM events WHERE id=?',(event_id,)).fetchone())
    current_rows=connection.execute('SELECT * FROM events WHERE parent_event_id=?',(event_id,)).fetchall()
    current={str(r['id']):dict(r) for r in current_rows}
    supplied=[str(s['id']) for s in segments if s.get('id')]
    if len(supplied)!=len(set(supplied)) or not set(supplied)<=set(current):
        raise ValueError('Unterereignisse wurden zwischenzeitlich geändert. Bitte neu laden.')
    keep=set(supplied)
    for cid in set(current)-keep:
        connection.execute('DELETE FROM events WHERE id=?',(cid,))
    result=[]
    for segment in segments:
        cid=str(segment.get('id') or 'EVENT_'+uuid.uuid4().hex.upper())
        if cid in current:
            existing=current[cid]
            changed=any([
                str(existing.get('name') or '') != str(segment['name']),
                str(existing.get('start_datetime') or '')[:19] != str(segment['start_datetime'])[:19],
                str(existing.get('end_datetime') or '')[:19] != str(segment['end_datetime'])[:19],
                str(existing.get('folder_name') or '') != str(segment['folder_name']),
                bool(existing.get('preserve_day_folders')) != bool(parent['preserve_day_folders']),
            ])
            if changed:
                connection.execute('UPDATE events SET name=?,start_datetime=?,end_datetime=?,folder_name=?,preserve_day_folders=?,updated_at=?,revision=revision+1 WHERE id=?',
                    (segment['name'],segment['start_datetime'],segment['end_datetime'],segment['folder_name'],parent['preserve_day_folders'],now,cid))
        else:
            connection.execute("""INSERT INTO events(id,job_id,parent_event_id,event_level,name,start_datetime,end_datetime,uses_time_range,folder_name,status,created_at,updated_at,event_kind,preserve_day_folders,revision,applied_at,archived_at,time_model_version)
                VALUES (?,?,?,'child',?,?,?,1,?,?,?,?, 'event',?,1,?,?,2)""",
                (cid,parent['job_id'],event_id,segment['name'],segment['start_datetime'],segment['end_datetime'],segment['folder_name'],parent['status'],now,now,parent['preserve_day_folders'],parent['applied_at'],parent['archived_at']))
        result.append({**segment,'id':cid})
    return result


def append_extension_subevents(connection,event_id,segments,extension_start,extension_end,now,naming=None):
    """Append new child events only inside one newly added parent interval."""
    if not segments:
        return []
    parent_row=connection.execute('SELECT * FROM events WHERE id=?',(event_id,)).fetchone()
    if parent_row is None:
        raise ValueError('Ereignis wurde nicht gefunden.')
    parent=dict(parent_row)
    try:
        new_segments=normalize_subevents(
            segments,extension_start,extension_end,naming=naming
        )
    except ValueError as exc:
        if 'durchgehenden Elternzeitraums' in str(exc):
            raise ValueError(
                'Neue Unterereignisse dürfen nur innerhalb des neu hinzugefügten Erweiterungsbereichs liegen.'
            ) from exc
        raise
    existing=[dict(row) for row in connection.execute(
        'SELECT * FROM events WHERE parent_event_id=? ORDER BY start_datetime,id',(event_id,)
    ).fetchall()]
    # Validate overlap against the complete child-event model without rewriting
    # any existing child row.
    normalize_subevents([
        *[{
            'id':row['id'],'name':row['name'],
            'start_datetime':row['start_datetime'],'end_datetime':row['end_datetime']
        } for row in existing],
        *new_segments,
    ],str(parent['start_datetime'])[:19],str(parent['end_datetime'])[:19],naming=naming)
    result=[]
    for segment in new_segments:
        cid='EVENT_'+uuid.uuid4().hex.upper()
        connection.execute("""INSERT INTO events(id,job_id,parent_event_id,event_level,name,start_datetime,end_datetime,uses_time_range,folder_name,status,created_at,updated_at,event_kind,preserve_day_folders,revision,applied_at,archived_at,time_model_version)
            VALUES (?,?,?,'child',?,?,?,1,?,?,?,?, 'event',?,1,?,?,2)""",
            (cid,parent['job_id'],event_id,segment['name'],segment['start_datetime'],segment['end_datetime'],segment['folder_name'],parent['status'],now,now,parent['preserve_day_folders'],parent['applied_at'],parent['archived_at']))
        result.append({**segment,'id':cid})
    return result


def assignment_target(event_id,children,capture):
    return next((s['id'] for s in children if s['start_datetime']<=capture<=s['end_datetime']),event_id)
