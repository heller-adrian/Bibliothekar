"""Optional organizational children; they never define parent occupancy."""
from datetime import datetime
import uuid


def normalize_subevents(values, start, end):
    result=[]
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
        result.append({'id':value.get('id'),'name':name,'start_datetime':a,'end_datetime':b,
            'start_time':a[11:16],'end_time':b[11:16],
            'folder_name':f"{a[5:16].replace('T',' ').replace(':','-')} - {b[5:16].replace('T',' ').replace(':','-')} - {name}"})
    result.sort(key=lambda x:(x['start_datetime'],x['end_datetime']))
    if any(a['end_datetime']>=b['start_datetime'] for a,b in zip(result,result[1:])):
        raise ValueError('Organisatorische Unterereignisse dürfen sich nicht überschneiden.')
    return result


def store_subevents(connection,event_id,segments,now):
    parent=dict(connection.execute('SELECT * FROM events WHERE id=?',(event_id,)).fetchone())
    current={r['id'] for r in connection.execute('SELECT id FROM events WHERE parent_event_id=?',(event_id,))}
    supplied=[str(s['id']) for s in segments if s.get('id')]
    if len(supplied)!=len(set(supplied)) or not set(supplied)<=current:
        raise ValueError('Unterereignisse wurden zwischenzeitlich geändert. Bitte neu laden.')
    keep=set(supplied)
    for cid in current-keep:
        connection.execute('DELETE FROM events WHERE id=?',(cid,))
    result=[]
    for segment in segments:
        cid=str(segment.get('id') or 'EVENT_'+uuid.uuid4().hex.upper())
        if cid in current:
            connection.execute('UPDATE events SET name=?,start_datetime=?,end_datetime=?,folder_name=?,preserve_day_folders=?,updated_at=?,revision=revision+1 WHERE id=?',
                (segment['name'],segment['start_datetime'],segment['end_datetime'],segment['folder_name'],parent['preserve_day_folders'],now,cid))
        else:
            connection.execute("""INSERT INTO events(id,job_id,parent_event_id,event_level,name,start_datetime,end_datetime,uses_time_range,folder_name,status,created_at,updated_at,event_kind,preserve_day_folders,revision,applied_at,archived_at,time_model_version)
                VALUES (?,?,?,'child',?,?,?,1,?,?,?,?, 'event',?,1,?,?,2)""",
                (cid,parent['job_id'],event_id,segment['name'],segment['start_datetime'],segment['end_datetime'],segment['folder_name'],parent['status'],now,now,parent['preserve_day_folders'],parent['applied_at'],parent['archived_at']))
        result.append({**segment,'id':cid})
    return result


def assignment_target(event_id,children,capture):
    return next((s['id'] for s in children if s['start_datetime']<=capture<=s['end_datetime']),event_id)
