from __future__ import annotations
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import uuid

from app.database import database_connection
from app.event_structure import build_event_preview
from app.event_timeline import continuous_event_overlaps
from app.archive_reassignment_segments import (
    ArchiveSegmentError,
    build_archive_reassignment_segments,
    selected_bounds,
    validate_atomic_segment_selection,
)

class ArchiveReassignmentError(ValueError): pass

def _now(): return datetime.now(timezone.utc).isoformat()

def list_archive_reassignments(database_path:Path,cr_id:str)->dict[str,Any]:
    with database_connection(database_path) as c:
        cr_row=c.execute("SELECT * FROM event_change_requests WHERE id=?",(cr_id,)).fetchone()
        if cr_row is None: raise ArchiveReassignmentError('Änderungsauftrag wurde nicht gefunden.')
        cr=dict(cr_row)
        rows=[dict(r) for r in c.execute("""SELECT r.family_id,ff.family_key,ff.original_stem,ff.selected_capture_time,COUNT(DISTINCT f.id) file_count
                          FROM event_change_file_reviews r JOIN file_families ff ON ff.id=r.family_id
                          LEFT JOIN files f ON f.family_id=ff.id
                          WHERE r.change_request_id=? AND r.action='delete' AND r.new_path=''
                          GROUP BY r.family_id ORDER BY ff.selected_capture_time,ff.id""",(cr_id,)).fetchall()]
        try:
            reassignment_segments=build_archive_reassignment_segments(c,cr,rows)
        except ArchiveSegmentError as exc:
            raise ArchiveReassignmentError(str(exc)) from exc
        months=sorted({str(seg['day_key'])[:7] for seg in reassignment_segments if seg.get('day_key')})
        occupied_no_event_months=[]
        if months:
            ph_months=','.join('?' for _ in months)
            occupied_no_event_months=[
                str(r['month'])
                for r in c.execute(
                    f"""SELECT DISTINCT substr(start_datetime,1,7) AS month
                        FROM events
                        WHERE parent_event_id IS NULL
                          AND event_kind='no_event'
                          AND status IN ('planned','applied','archived')
                          AND substr(start_datetime,1,7) IN ({ph_months})
                        ORDER BY month""",
                    months,
                ).fetchall()
            ]
        clauses=["(event_kind!='no_event' AND job_id=?)"]
        params:list[Any]=[str(cr['job_id'])]
        if months:
            ph=','.join('?' for _ in months)
            clauses.append(f"(event_kind='no_event' AND substr(start_datetime,1,7) IN ({ph}))")
            params.extend(months)
        targets=[]
        for r in c.execute(f"""SELECT id,job_id,name,folder_name,status,start_datetime,end_datetime,event_kind,preserve_day_folders
                                FROM events
                                WHERE parent_event_id IS NULL AND status='archived'
                                  AND id<>?
                                  AND ({' OR '.join(clauses)})
                                ORDER BY start_datetime,id""",[str(cr['event_id']),*params]).fetchall():
            item=dict(r); item['children']=[]
            if str(r['event_kind'])=='event':
                item['children']=[dict(x) for x in c.execute(
                    "SELECT id,name,folder_name,start_datetime,end_datetime FROM events WHERE parent_event_id=? AND status='archived' ORDER BY start_datetime,id",
                    (r['id'],),
                ).fetchall()]
            targets.append(item)
    return {
        'change_request_id':cr_id,
        'job_id':str(cr['job_id']),
        'families':rows,
        'family_count':len(rows),
        'reassignment_segments':reassignment_segments,
        'targets':targets,
        'occupied_no_event_months':occupied_no_event_months,
    }

def _target_for_new_event(c,job_id:str,fids:list[int],name:str,range_start:str,range_end:str)->dict[str,Any]:
    clean=str(name or '').strip()
    if not clean: raise ArchiveReassignmentError('Name des neuen Ereignisses fehlt.')
    ph=','.join('?' for _ in fids)
    rows=c.execute(f"SELECT id,selected_capture_time,family_key FROM file_families WHERE job_id=? AND id IN ({ph}) ORDER BY selected_capture_time",(job_id,*fids)).fetchall()
    if len(rows)!=len(fids) or any(not r['selected_capture_time'] for r in rows): raise ArchiveReassignmentError('Aufnahmedaten der Familien sind unvollständig.')
    available=[{'family_id':int(r['id']),'family_key':r['family_key'],'selected_capture_time':r['selected_capture_time'],'capture_time_confidence':'high','day_key':str(r['selected_capture_time'])[:10],'has_date':True,'file_count':0,'total_size_bytes':0,'review_required_count':0} for r in rows]
    preview=build_event_preview({'event_kind':'event','event_name':clean,'start_date':range_start[:10],'end_date':range_end[:10],'uses_time_range':False,'child_event_name':'','start_time':'00:00','end_time':'23:59','preserve_day_folders':False,'selected_family_ids':fids,'selected_day_keys':[]},available)
    return {'kind':'new_event','event_id':None,'name':clean,'folder':preview['parent_folder'],'start':range_start,'end':range_end,'uses':0,'child_name':None,'child_folder':None,'preserve':0}

def _target_for_new_no_event(c,job_id:str,fids:list[int],range_start:str,range_end:str)->dict[str,Any]:
    ph=','.join('?' for _ in fids)
    rows=c.execute(f"SELECT id,selected_capture_time FROM file_families WHERE job_id=? AND id IN ({ph})",(job_id,*fids)).fetchall()
    if len(rows)!=len(fids) or any(not r['selected_capture_time'] for r in rows): raise ArchiveReassignmentError('Aufnahmedaten der Familien sind unvollständig.')
    months={range_start[:7],range_end[:7]}
    if len(months)!=1: raise ArchiveReassignmentError('Eine neue „Ohne Ereignis“-Sammlung muss in einem Monat liegen.')
    month=next(iter(months))
    existing=c.execute(
        """SELECT id FROM events
           WHERE parent_event_id IS NULL
             AND event_kind='no_event'
             AND status IN ('planned','applied','archived')
             AND substr(start_datetime,1,7)=?
           LIMIT 1""",
        (month,),
    ).fetchone()
    if existing is not None:
        raise ArchiveReassignmentError(
            'Für diesen Monat existiert bereits eine „Ohne Ereignis“-Sammlung. '
            'Bitte diese bestehende Sammlung als Ziel wählen.'
        )
    folder=f"{month[5:7]} - Ohne Ereignis"
    return {'kind':'new_no_event','event_id':None,'name':'Ohne Ereignis','folder':folder,'start':range_start,'end':range_end,'uses':0,'child_name':None,'child_folder':None,'preserve':0}

def assign_archive_reassignments(database_path:Path,cr_id:str,family_ids:list[int],*,target_mode:str,new_event_name:str|None=None,target_event_id:str|None=None,target_child_event_id:str|None=None,new_child_start:str|None=None,new_child_end:str|None=None,workspace_path:Path|None=None)->dict[str,Any]:
    fids=sorted({int(x) for x in family_ids})
    if not fids: raise ArchiveReassignmentError('Keine Tages-/Zeitsegmente ausgewählt.')
    now=_now()
    with database_connection(database_path) as c:
        c.execute('BEGIN IMMEDIATE')
        cr_row=c.execute("SELECT * FROM event_change_requests WHERE id=?",(cr_id,)).fetchone()
        if cr_row is None or str(cr_row['status']) not in {'aenderbar_vorschlagen','aenderbar_bestaetigt'}: raise ArchiveReassignmentError('Änderungsauftrag ist nicht mehr offen.')
        cr=dict(cr_row)
        pending_rows=[dict(r) for r in c.execute("""SELECT r.family_id,ff.family_key,ff.original_stem,ff.selected_capture_time,COUNT(DISTINCT f.id) file_count
                          FROM event_change_file_reviews r JOIN file_families ff ON ff.id=r.family_id
                          LEFT JOIN files f ON f.family_id=ff.id
                          WHERE r.change_request_id=? AND r.action='delete' AND r.new_path=''
                          GROUP BY r.family_id ORDER BY ff.selected_capture_time,ff.id""",(cr_id,)).fetchall()]
        pending={int(r['family_id']) for r in pending_rows}
        if not set(fids)<=pending: raise ArchiveReassignmentError('Mindestens eine Auswahl ist nicht mehr offen.')
        try:
            all_segments=build_archive_reassignment_segments(c,cr,pending_rows)
            selected_segments=validate_atomic_segment_selection(all_segments,fids)
            released_start,released_end=selected_bounds(selected_segments)
        except ArchiveSegmentError as exc:
            raise ArchiveReassignmentError(str(exc)) from exc

        from app.released_ranges import merge_intervals
        selected_ranges=merge_intervals((s['start_datetime'],s['end_datetime']) for s in selected_segments)
        if target_mode=='new_event' and len(selected_ranges)!=1:
            raise ArchiveReassignmentError('Ein normales Ereignis benötigt einen durchgehenden Zeitraum.')
        if target_mode=='new_event': target=_target_for_new_event(c,str(cr['job_id']),fids,str(new_event_name or ''),released_start,released_end)
        elif target_mode=='new_no_event': target=_target_for_new_no_event(c,str(cr['job_id']),fids,released_start,released_end)
        elif target_mode=='existing_no_event':
            t=c.execute("SELECT * FROM events WHERE id=? AND parent_event_id IS NULL",(target_event_id,)).fetchone()
            if t is None or str(t['status'])!='archived' or str(t['event_kind'])!='no_event': raise ArchiveReassignmentError('Die archivierte „Ohne Ereignis“-Sammlung ist nicht verfügbar.')
            target={'kind':'existing_no_event','event_id':str(t['id']),'name':'Ohne Ereignis','folder':str(t['folder_name']),'start':released_start,'end':released_end,'uses':0,'child_name':None,'child_folder':None,'preserve':int(bool(t['preserve_day_folders']))}
        elif target_mode=='existing_event':
            t=c.execute("SELECT * FROM events WHERE id=? AND parent_event_id IS NULL",(target_event_id,)).fetchone()
            if t is None or str(t['job_id'])!=str(cr['job_id']) or str(t['status'])!='archived' or str(t['event_kind'])!='event': raise ArchiveReassignmentError('Das archivierte Zielereignis ist nicht verfügbar.')
            child=None
            if target_child_event_id:
                child=c.execute("SELECT * FROM events WHERE id=? AND parent_event_id=? AND status='archived'",(target_child_event_id,t['id'])).fetchone()
                if child is None: raise ArchiveReassignmentError('Das archivierte Unterereignis ist nicht verfügbar.')
            target={'kind':'existing_event','event_id':str(t['id']),'child_event_id':str(child['id']) if child else None,
                    'name':str(t['name']),'folder':str(t['folder_name']),
                    'start':str(child['start_datetime'] if child else t['start_datetime']),'end':str(child['end_datetime'] if child else t['end_datetime']),
                    'uses':1 if child else 0,'child_name':str(child['name']) if child else None,
                    'child_folder':str(child['folder_name']) if child else None,'preserve':int(bool(t['preserve_day_folders']))}
        elif target_mode=='new_child':
            t=c.execute("SELECT * FROM events WHERE id=? AND parent_event_id IS NULL",(target_event_id,)).fetchone()
            if t is None or str(t['job_id'])!=str(cr['job_id']) or str(t['status'])!='archived' or str(t['event_kind'])!='event': raise ArchiveReassignmentError('Das archivierte Oberereignis ist nicht verfügbar.')
            clean=str(new_event_name or '').strip(); st=str(new_child_start or '').strip(); et=str(new_child_end or '').strip()
            if not clean: raise ArchiveReassignmentError('Name des neuen Unterereignisses fehlt.')
            if len(st)!=5 or len(et)!=5 or st>=et: raise ArchiveReassignmentError('Start- und Endzeit des neuen Unterereignisses sind ungültig.')
            phf=','.join('?' for _ in fids); caps=c.execute(f"SELECT selected_capture_time FROM file_families WHERE id IN ({phf})",fids).fetchall()
            days={str(x['selected_capture_time'] or '')[:10] for x in caps}
            if len(days)!=1: raise ArchiveReassignmentError('Ein neues Unterereignis wird aus genau einem Tag angelegt.')
            day=next(iter(days)); start=f'{day}T{st}:00'; end=f'{day}T{et}:59'
            if not (str(t['start_datetime'])[:19] <= start <= end <= str(t['end_datetime'])[:19]):
                raise ArchiveReassignmentError('Das neue Unterereignis muss vollständig im Zeitraum des Oberereignisses liegen.')
            if not all(start <= str(x['selected_capture_time'] or '')[:19] <= end for x in caps): raise ArchiveReassignmentError('Nicht alle ausgewählten Familien liegen im eingegebenen Zeitbereich.')
            overlap=c.execute("SELECT 1 FROM events WHERE parent_event_id=? AND start_datetime<=? AND end_datetime>=? LIMIT 1",(t['id'],end,start)).fetchone()
            if overlap: raise ArchiveReassignmentError('Der neue Zeitbereich überschneidet sich mit einem vorhandenen Unterereignis.')
            child_folder=f"{st.replace(':','-')} - {et.replace(':','-')} - {clean}"
            target={'kind':'new_child','event_id':str(t['id']),'child_event_id':None,'name':str(t['name']),'folder':str(t['folder_name']),
                    'start':start,'end':end,'uses':1,'child_name':clean,'child_folder':child_folder,'preserve':int(bool(t['preserve_day_folders']))}
        else: raise ArchiveReassignmentError('Unbekanntes Ziel.')

        captures={int(r['family_id']):str(r['selected_capture_time'] or '')[:19] for r in pending_rows if int(r['family_id']) in set(fids)}
        from app.released_ranges import merge_intervals
        if target['kind']=='existing_event':
            union=merge_intervals([(target['start'],target['end'])]+selected_ranges)
            if len(union)!=1:
                raise ArchiveReassignmentError('Der freie Bereich grenzt nicht unmittelbar an das Zielereignis an.')
            target['start'],target['end']=union[0]
        from app.event_timeline import no_event_segment_overlaps
        check_ranges=selected_ranges if target['kind'] in {'new_no_event','existing_no_event'} else [(target['start'],target['end'])]
        for a,b in check_ranges:
            conflicts=continuous_event_overlaps(c,str(cr['job_id']),a,b,exclude_event_id=str(cr['event_id']))
            conflicts=[x for x in conflicts if x['id']!=target.get('event_id')]
            segments=no_event_segment_overlaps(c,str(cr['job_id']),a,b,exclude_event_id=str(cr['event_id']))
            segments=[x for x in segments if x['event_id']!=target.get('event_id')]
            if conflicts or segments:
                raise ArchiveReassignmentError('Dieses Ziel überschneidet sich mit einem anderen Ereignis.')

        ph=','.join('?' for _ in fids)
        for fid in fids:
            stored_kind = target['kind'] + (':' + str(target.get('child_event_id')) if target['kind']=='existing_event' and target.get('child_event_id') else '')
            c.execute("""INSERT OR REPLACE INTO event_change_reassignments(change_request_id,family_id,target_kind,target_event_id,target_name,target_folder_name,target_start_datetime,target_end_datetime,target_uses_time_range,target_child_name,target_child_folder,target_preserve_day_folders,created_at)
                         VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",(cr_id,fid,stored_kind,target['event_id'],target['name'],target['folder'],target['start'],target['end'],target['uses'],target['child_name'],target['child_folder'],target['preserve'],now))
            reviews=c.execute(
                "SELECT id,old_path FROM event_change_file_reviews WHERE change_request_id=? AND family_id=?",
                (cr_id,fid),
            ).fetchall()
            for rv in reviews:
                filename=Path(str(rv['old_path'])).name
                source_parts=[part for part in Path(str(rv['old_path'])).parts if part]
                branch=next((part for part in source_parts if part in {'Alle','Sortiert','Export'}),'Alle')
                parts=[str(target['start'])[:4],target['folder']]
                if target['child_folder']: parts.append(target['child_folder'])
                if target['preserve']: parts.append(captures[fid][:10])
                parts += [branch,filename]
                new='/'.join(parts)
                c.execute(
                    "UPDATE event_change_file_reviews SET new_path=?,action='move',updated_at=? WHERE id=?",
                    (new,now,int(rv['id'])),
                )

            asset_reviews=c.execute(
                """SELECT id,old_path,asset_kind
                   FROM event_change_asset_reviews
                   WHERE change_request_id=? AND family_id=?""",
                (cr_id,fid),
            ).fetchall()
            for rv in asset_reviews:
                filename=Path(str(rv['old_path'])).name
                source_parts=[part for part in Path(str(rv['old_path'])).parts if part]
                branch=next(
                    (part for part in source_parts if part in {'Alle','Sortiert','Export'}),
                    'Export' if str(rv['asset_kind'])=='export' else 'Alle',
                )
                parts=[str(target['start'])[:4],target['folder']]
                if target['child_folder']: parts.append(target['child_folder'])
                if target['preserve']: parts.append(captures[fid][:10])
                parts += [branch,filename]
                new='/'.join(parts)
                c.execute(
                    """UPDATE event_change_asset_reviews
                       SET new_path=?,action='move',updated_at=? WHERE id=?""",
                    (new,now,int(rv['id'])),
                )
        c.commit()
    prepared=None
    if workspace_path is not None:
        root=Path(workspace_path)/'Arbeitsbereich'/'Später zuordnen'/str(target['start'])[:4]/target['folder']
        if target['child_folder']: root/=target['child_folder']
        if target['preserve']:
            days=sorted({captures[fid][:10] for fid in fids})
            for day in days:
                for branch in ('Alle','Sortiert','Export'): (root/day/branch).mkdir(parents=True,exist_ok=True)
        else:
            for branch in ('Alle','Sortiert','Export'): (root/branch).mkdir(parents=True,exist_ok=True)
        prepared=str(root)
    return {'status':'assigned','family_ids':fids,'reassignment_segments':selected_segments,'target':target,'prepared_structure':prepared}

def apply_archive_reassignment_targets(connection,cr:dict[str,Any],now:str)->list[str]:
    def _exact_segments_for(fids):
        if not fids: return []
        ph=' ,'.join('?' for _ in fids).replace(' ','')
        pending=[dict(r) for r in connection.execute(f"SELECT ff.id family_id,ff.selected_capture_time,COUNT(DISTINCT f.id) file_count FROM file_families ff LEFT JOIN files f ON f.family_id=ff.id WHERE ff.id IN ({ph}) GROUP BY ff.id",fids).fetchall()]
        try:
            return build_archive_reassignment_segments(connection,cr,pending)
        except ArchiveSegmentError as exc:
            raise ArchiveReassignmentError(str(exc)) from exc
    rows=connection.execute("SELECT * FROM event_change_reassignments WHERE change_request_id=? ORDER BY target_folder_name,family_id",(cr['id'],)).fetchall()
    groups=defaultdict(list)
    for r in rows: groups[(str(r['target_kind']),str(r['target_event_id'] or ''),str(r['target_name']),str(r['target_folder_name']),str(r['target_start_datetime']),str(r['target_end_datetime']),int(r['target_uses_time_range']),str(r['target_child_name'] or ''),str(r['target_child_folder'] or ''),int(r['target_preserve_day_folders']))].append(int(r['family_id']))
    created=[]
    for key,fids in groups.items():
        kind,target_id,name,folder,start,end,uses,child_name,child_folder,preserve=key
        if kind.startswith('existing_event'):
            eid=target_id
            connection.execute("UPDATE events SET start_datetime=?,end_datetime=?,time_model_version=2,updated_at=?,revision=revision+1 WHERE id=?",(start,end,now,eid))
            child_id = kind.split(':',1)[1] if ':' in kind else None
            assign_id=child_id or eid
            connection.executemany("INSERT OR IGNORE INTO event_assignments(event_id,family_id,file_id,assignment_source,created_at) VALUES (?,?,NULL,'manual',?)",[(assign_id,f,now) for f in fids])
            continue
        if kind=='new_child':
            eid=target_id
            cid='EVENT_'+uuid.uuid4().hex.upper()
            connection.execute("""INSERT INTO events(id,job_id,parent_event_id,event_level,name,start_datetime,end_datetime,uses_time_range,folder_name,status,created_at,updated_at,event_kind,preserve_day_folders,revision,applied_at,archived_at,timeline_model)
                VALUES (?,?,?,'child',?,?,?,1,?,'archived',?,?,'event',?,1,?,?, 'continuous')""",(cid,cr['job_id'],eid,child_name,start,end,child_folder,now,now,preserve,now,now))
            connection.executemany("INSERT INTO event_assignments(event_id,family_id,file_id,assignment_source,created_at) VALUES (?,?,NULL,'manual',?)",[(cid,f,now) for f in fids])
            continue
        if kind=='existing_no_event':
            eid=target_id
            connection.executemany("INSERT OR IGNORE INTO event_assignments(event_id,family_id,file_id,assignment_source,created_at) VALUES (?,?,NULL,'manual',?)",[(eid,f,now) for f in fids])
            target_event=connection.execute("SELECT job_id FROM events WHERE id=?",(eid,)).fetchone()
            target_job=str(target_event['job_id']) if target_event is not None else str(cr['job_id'])
            for segment in _exact_segments_for(fids):
                exists=connection.execute("SELECT 1 FROM event_time_segments WHERE event_id=? AND start_datetime=? AND end_datetime=? LIMIT 1",(eid,segment['start_datetime'],segment['end_datetime'])).fetchone()
                if exists is None:
                    connection.execute("INSERT INTO event_time_segments(event_id,job_id,day_key,start_time,end_time,start_datetime,end_datetime,source,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",(eid,target_job,segment['day_key'],segment['start_time'],segment['end_time'],segment['start_datetime'],segment['end_datetime'],'reassignment',now,now))
            bounds=connection.execute("SELECT MIN(start_datetime) a,MAX(end_datetime) b FROM event_time_segments WHERE event_id=?",(eid,)).fetchone()
            if bounds and bounds['a'] and bounds['b']: connection.execute("UPDATE events SET start_datetime=?,end_datetime=?,updated_at=? WHERE id=?",(bounds['a'],bounds['b'],now,eid))
            continue
        eid='EVENT_'+uuid.uuid4().hex.upper(); event_kind='no_event' if kind=='new_no_event' else 'event'
        parent_start = start
        parent_end = end
        connection.execute("""INSERT INTO events(id,job_id,parent_event_id,event_level,name,start_datetime,end_datetime,uses_time_range,folder_name,status,created_at,updated_at,event_kind,preserve_day_folders,revision,applied_at,archived_at,timeline_model)
                             VALUES (?,?,NULL,'parent',?,?,?,0,?,'archived',?,?,?, ?,1,?,?,?)""",(eid,cr['job_id'],name,parent_start,parent_end,folder,now,now,event_kind,preserve,now,now,'segments' if event_kind=='no_event' else 'continuous'))
        assign_id=eid
        if uses:
            cid='EVENT_'+uuid.uuid4().hex.upper(); connection.execute("""INSERT INTO events(id,job_id,parent_event_id,event_level,name,start_datetime,end_datetime,uses_time_range,folder_name,status,created_at,updated_at,event_kind,preserve_day_folders,revision,applied_at,archived_at,timeline_model)
                VALUES (?,?,?,'child',?,?,?,1,?,'archived',?,?,'event',?,1,?,?, 'continuous')""",(cid,cr['job_id'],eid,child_name or name,start,end,child_folder,now,now,preserve,now,now)); assign_id=cid
        connection.executemany("INSERT INTO event_assignments(event_id,family_id,file_id,assignment_source,created_at) VALUES (?,?,NULL,'manual',?)",[(assign_id,f,now) for f in fids])
        if event_kind=='no_event':
            exact_segments=_exact_segments_for(fids)
            for segment in exact_segments:
                connection.execute("INSERT INTO event_time_segments(event_id,job_id,day_key,start_time,end_time,start_datetime,end_datetime,source,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",(eid,cr['job_id'],segment['day_key'],segment['start_time'],segment['end_time'],segment['start_datetime'],segment['end_datetime'],'reassignment',now,now))
            if exact_segments:
                connection.execute("UPDATE events SET start_datetime=?,end_datetime=?,updated_at=? WHERE id=?",(min(s['start_datetime'] for s in exact_segments),max(s['end_datetime'] for s in exact_segments),now,eid))
        created.append(eid)
    return created
