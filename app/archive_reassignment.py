from __future__ import annotations
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import uuid

from app.database import database_connection
from app.event_structure import build_event_preview
from app.event_timeline import continuous_event_overlaps

class ArchiveReassignmentError(ValueError): pass

def _now(): return datetime.now(timezone.utc).isoformat()

def list_archive_reassignments(database_path:Path,cr_id:str)->dict[str,Any]:
    with database_connection(database_path) as c:
        cr=c.execute("SELECT * FROM event_change_requests WHERE id=?",(cr_id,)).fetchone()
        if cr is None: raise ArchiveReassignmentError('Änderungsauftrag wurde nicht gefunden.')
        rows=c.execute("""SELECT r.family_id,ff.family_key,ff.original_stem,ff.selected_capture_time,COUNT(DISTINCT f.id) file_count
                          FROM event_change_file_reviews r JOIN file_families ff ON ff.id=r.family_id
                          LEFT JOIN files f ON f.family_id=ff.id
                          WHERE r.change_request_id=? AND r.action='delete' AND r.new_path=''
                          GROUP BY r.family_id ORDER BY ff.selected_capture_time,ff.id""",(cr_id,)).fetchall()
        months=sorted({str(r['selected_capture_time'] or '')[:7] for r in rows if r['selected_capture_time']})
        targets=[]
        if months:
            ph=','.join('?' for _ in months)
            for r in c.execute(f"""SELECT id,name,folder_name,status,start_datetime,event_kind FROM events
                                    WHERE parent_event_id IS NULL AND event_kind='no_event' AND status='archived'
                                      AND substr(start_datetime,1,7) IN ({ph}) ORDER BY start_datetime""",months).fetchall():
                targets.append(dict(r))
    return {'change_request_id':cr_id,'job_id':str(cr['job_id']),'families':[dict(r) for r in rows],'family_count':len(rows),'targets':targets}

def _target_for_new_event(c,job_id:str,fids:list[int],name:str)->dict[str,Any]:
    clean=str(name or '').strip()
    if not clean: raise ArchiveReassignmentError('Name des neuen Ereignisses fehlt.')
    ph=','.join('?' for _ in fids)
    rows=c.execute(f"SELECT id,selected_capture_time,family_key FROM file_families WHERE job_id=? AND id IN ({ph}) ORDER BY selected_capture_time",(job_id,*fids)).fetchall()
    if len(rows)!=len(fids) or any(not r['selected_capture_time'] for r in rows): raise ArchiveReassignmentError('Aufnahmedaten der Familien sind unvollständig.')
    captures=[str(r['selected_capture_time'])[:19] for r in rows]; start=min(captures); end=max(captures)
    # Archiv-Neuzuordnung: Ohne ausdrückliche Nutzereingabe für Uhrzeit/Unterereignis
    # darf aus den Aufnahmedaten kein künstlicher Zeit-Unterordner entstehen.
    # Der genaue Aufnahmebereich bleibt für Konfliktprüfung und DB-Zielzustand erhalten,
    # die vorbereitete Struktur ist jedoch direkt <Ereignis>/Alle|Sortiert|Export.
    available=[{'family_id':int(r['id']),'family_key':r['family_key'],'selected_capture_time':r['selected_capture_time'],'capture_time_confidence':'high','day_key':str(r['selected_capture_time'])[:10],'has_date':True,'file_count':0,'total_size_bytes':0,'review_required_count':0} for r in rows]
    preview=build_event_preview({'event_kind':'event','event_name':clean,'start_date':start[:10],'end_date':end[:10],'uses_time_range':False,'child_event_name':'','start_time':'00:00','end_time':'23:59','preserve_day_folders':False,'selected_family_ids':fids,'selected_day_keys':[]},available)
    return {'kind':'new_event','event_id':None,'name':clean,'folder':preview['parent_folder'],'start':start,'end':end,'uses':0,'child_name':None,'child_folder':None,'preserve':0}

def _target_for_new_no_event(c,job_id:str,fids:list[int])->dict[str,Any]:
    ph=','.join('?' for _ in fids); rows=c.execute(f"SELECT id,selected_capture_time FROM file_families WHERE job_id=? AND id IN ({ph})",(job_id,*fids)).fetchall()
    captures=[str(r['selected_capture_time'] or '')[:19] for r in rows]
    if len(rows)!=len(fids) or any(not x for x in captures): raise ArchiveReassignmentError('Aufnahmedaten der Familien sind unvollständig.')
    months={x[:7] for x in captures}
    if len(months)!=1: raise ArchiveReassignmentError('Eine neue „Ohne Ereignis“-Sammlung muss in einem Monat liegen.')
    month=next(iter(months)); folder=f"{month[5:7]} - Ohne Ereignis"
    return {'kind':'new_no_event','event_id':None,'name':'Ohne Ereignis','folder':folder,'start':min(captures),'end':max(captures),'uses':0,'child_name':None,'child_folder':None,'preserve':0}

def assign_archive_reassignments(database_path:Path,cr_id:str,family_ids:list[int],*,target_mode:str,new_event_name:str|None=None,target_event_id:str|None=None,workspace_path:Path|None=None)->dict[str,Any]:
    fids=sorted({int(x) for x in family_ids})
    if not fids: raise ArchiveReassignmentError('Keine Familien ausgewählt.')
    now=_now()
    with database_connection(database_path) as c:
        c.execute('BEGIN IMMEDIATE'); cr=c.execute("SELECT * FROM event_change_requests WHERE id=?",(cr_id,)).fetchone()
        if cr is None or str(cr['status']) not in {'aenderbar_vorschlagen','aenderbar_bestaetigt'}: raise ArchiveReassignmentError('Änderungsauftrag ist nicht mehr offen.')
        ph=','.join('?' for _ in fids)
        pending={int(r['family_id']) for r in c.execute(f"SELECT DISTINCT family_id FROM event_change_file_reviews WHERE change_request_id=? AND action='delete' AND new_path='' AND family_id IN ({ph})",(cr_id,*fids)).fetchall()}
        if pending!=set(fids): raise ArchiveReassignmentError('Mindestens eine Familie ist nicht mehr offen.')
        if target_mode=='new_event': target=_target_for_new_event(c,str(cr['job_id']),fids,str(new_event_name or ''))
        elif target_mode=='new_no_event': target=_target_for_new_no_event(c,str(cr['job_id']),fids)
        elif target_mode=='existing_no_event':
            t=c.execute("SELECT * FROM events WHERE id=? AND parent_event_id IS NULL",(target_event_id,)).fetchone()
            if t is None or str(t['status'])!='archived' or str(t['event_kind'])!='no_event': raise ArchiveReassignmentError('Als bestehendes Archivziel ist nur eine archivierte „Ohne Ereignis“-Sammlung zulässig.')
            target={'kind':'existing_no_event','event_id':str(t['id']),'name':'Ohne Ereignis','folder':str(t['folder_name']),'start':str(t['start_datetime']),'end':str(t['end_datetime']),'uses':0,'child_name':None,'child_folder':None,'preserve':int(bool(t['preserve_day_folders']))}
        else: raise ArchiveReassignmentError('Unbekanntes Ziel.')
        overlaps = continuous_event_overlaps(
            c, str(cr['job_id']), str(target['start'])[:19], str(target['end'])[:19],
            exclude_event_id=str(cr['event_id']),
        )
        if overlaps:
            names = sorted({str(r['name']) for r in overlaps})
            raise ArchiveReassignmentError(
                'Dieses Ziel würde sich mit einem anderen Ereignis überschneiden: ' + ', '.join(names)
            )
        rows=c.execute(f"SELECT id,selected_capture_time FROM file_families WHERE id IN ({ph})",fids).fetchall(); captures={int(r['id']):str(r['selected_capture_time'] or '')[:19] for r in rows}
        for fid in fids:
            c.execute("""INSERT OR REPLACE INTO event_change_reassignments(change_request_id,family_id,target_kind,target_event_id,target_name,target_folder_name,target_start_datetime,target_end_datetime,target_uses_time_range,target_child_name,target_child_folder,target_preserve_day_folders,created_at)
                         VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",(cr_id,fid,target['kind'],target['event_id'],target['name'],target['folder'],target['start'],target['end'],target['uses'],target['child_name'],target['child_folder'],target['preserve'],now))
            reviews=c.execute("SELECT id,old_path FROM event_change_file_reviews WHERE change_request_id=? AND family_id=?",(cr_id,fid)).fetchall()
            for rv in reviews:
                filename=Path(str(rv['old_path'])).name; parts=[str(target['start'])[:4],target['folder']]
                if target['child_folder']: parts.append(target['child_folder'])
                if target['preserve']: parts.append(captures[fid][:10])
                parts+=['Alle',filename]; new='/'.join(parts)
                c.execute("UPDATE event_change_file_reviews SET new_path=?,action='move',updated_at=? WHERE id=?",(new,now,int(rv['id'])))
        c.commit()
    prepared=None
    if workspace_path is not None:
        root=Path(workspace_path)/'Arbeitsbereich'/'Später zuordnen'/str(target['start'])[:4]/target['folder']
        if target['child_folder']: root/=target['child_folder']
        if target['preserve']:
            days=sorted({captures[fid][:10] for fid in fids})
            for day in days:
                for branch in ('Alle','Sortiert','Export'):
                    (root/day/branch).mkdir(parents=True,exist_ok=True)
        else:
            for branch in ('Alle','Sortiert','Export'): (root/branch).mkdir(parents=True,exist_ok=True)
        prepared=str(root)
    return {'status':'assigned','family_ids':fids,'target':target,'prepared_structure':prepared}

def apply_archive_reassignment_targets(connection,cr:dict[str,Any],now:str)->list[str]:
    rows=connection.execute("SELECT * FROM event_change_reassignments WHERE change_request_id=? ORDER BY target_folder_name,family_id",(cr['id'],)).fetchall()
    groups=defaultdict(list)
    for r in rows: groups[(str(r['target_kind']),str(r['target_event_id'] or ''),str(r['target_name']),str(r['target_folder_name']),str(r['target_start_datetime']),str(r['target_end_datetime']),int(r['target_uses_time_range']),str(r['target_child_name'] or ''),str(r['target_child_folder'] or ''),int(r['target_preserve_day_folders']))].append(int(r['family_id']))
    created=[]
    for key,fids in groups.items():
        kind,target_id,name,folder,start,end,uses,child_name,child_folder,preserve=key
        if kind=='existing_no_event':
            eid=target_id
            connection.executemany("INSERT OR IGNORE INTO event_assignments(event_id,family_id,file_id,assignment_source,created_at) VALUES (?,?,NULL,'manual',?)",[(eid,f,now) for f in fids])
            # append one segment per day from captures
            ph=','.join('?' for _ in fids)
            caps=connection.execute(f"SELECT selected_capture_time FROM file_families WHERE id IN ({ph})",fids).fetchall(); by=defaultdict(list)
            for r in caps:
                cap=str(r['selected_capture_time'])[:19]; by[cap[:10]].append(cap)
            for day,vals in by.items():
                connection.execute("INSERT INTO event_time_segments(event_id,job_id,day_key,start_time,end_time,start_datetime,end_datetime,source,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",(eid,cr['job_id'],day,min(vals)[11:16],max(vals)[11:16],min(vals),max(vals),'archive_reassignment',now,now))
            continue
        eid='EVENT_'+uuid.uuid4().hex.upper(); event_kind='no_event' if kind=='new_no_event' else 'event'
        parent_start = f"{start[:10]}T00:00:00" if uses else start
        parent_end = f"{end[:10]}T23:59:59" if uses else end
        connection.execute("""INSERT INTO events(id,job_id,parent_event_id,event_level,name,start_datetime,end_datetime,uses_time_range,folder_name,status,created_at,updated_at,event_kind,preserve_day_folders,revision,applied_at,archived_at,timeline_model)
                             VALUES (?,?,NULL,'parent',?,?,?,0,?,'archived',?,?,?, ?,1,?,?,?)""",(eid,cr['job_id'],name,parent_start,parent_end,folder,now,now,event_kind,preserve,now,now,'segments' if event_kind=='no_event' else 'continuous'))
        assign_id=eid
        if uses:
            cid='EVENT_'+uuid.uuid4().hex.upper(); connection.execute("""INSERT INTO events(id,job_id,parent_event_id,event_level,name,start_datetime,end_datetime,uses_time_range,folder_name,status,created_at,updated_at,event_kind,preserve_day_folders,revision,applied_at,archived_at,timeline_model)
                VALUES (?,?,?,'child',?,?,?,1,?,'archived',?,?,'event',?,1,?,?, 'continuous')""",(cid,cr['job_id'],eid,child_name or name,start,end,child_folder,now,now,preserve,now,now)); assign_id=cid
        connection.executemany("INSERT INTO event_assignments(event_id,family_id,file_id,assignment_source,created_at) VALUES (?,?,NULL,'manual',?)",[(assign_id,f,now) for f in fids])
        if event_kind=='no_event':
            ph=','.join('?' for _ in fids); caps=connection.execute(f"SELECT selected_capture_time FROM file_families WHERE id IN ({ph})",fids).fetchall(); by=defaultdict(list)
            for r in caps:
                cap=str(r['selected_capture_time'])[:19]; by[cap[:10]].append(cap)
            for day,vals in by.items(): connection.execute("INSERT INTO event_time_segments(event_id,job_id,day_key,start_time,end_time,start_datetime,end_datetime,source,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",(eid,cr['job_id'],day,min(vals)[11:16],max(vals)[11:16],min(vals),max(vals),'archive_reassignment',now,now))
        created.append(eid)
    return created
