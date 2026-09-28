"""Manueller Archivanteil einer ereignisübergreifenden Zeitänderung."""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from app.database import database_connection, get_event_edit_context
from app.event_structure import build_event_preview
from app.event_change_request import propose_event_change, propose_archived_event_deletion, EventChangeRequestError


def _safe_parts(path: str) -> list[str]:
    return [p for p in str(path or '').replace('\\','/').split('/') if p not in {'','.','..'}]


def _source_target_relative(source_preview: dict[str,Any], capture: str, filename: str) -> str:
    year=str(source_preview.get('start_date') or capture[:10])[:4]
    parts=[year,str(source_preview.get('parent_folder') or 'Neues Ereignis')]
    child=str(source_preview.get('child_folder') or '').strip()
    if child: parts.append(child)
    if bool(source_preview.get('preserve_day_folders')) and len(capture)>=10:
        parts.append(capture[:10])
    parts.extend(['Alle',filename])
    return '/'.join(_safe_parts('/'.join(parts)))


def _prepare_empty_structure(workspace_path:Path, source_preview:dict[str,Any])->str:
    year=str(source_preview.get('start_date') or '')[:4] or 'Unbekannt'
    root=Path(workspace_path)/'Arbeitsbereich'/'Später zuordnen'/year/str(source_preview.get('parent_folder') or 'Neues Ereignis')
    child=str(source_preview.get('child_folder') or '').strip()
    if child: root=root/child
    for branch in ('Alle','Sortiert','Export'):
        (root/branch).mkdir(parents=True,exist_ok=True)
    return str(root)


def _subtract_segment(seg_start:str,seg_end:str,cut_start:str,cut_end:str)->list[tuple[str,str]]:
    if seg_end < cut_start or seg_start > cut_end: return [(seg_start,seg_end)]
    out=[]
    if seg_start < cut_start:
        a=seg_start; b=(datetime.fromisoformat(cut_start)-timedelta(seconds=1)).isoformat(timespec='seconds')
        if a<=b: out.append((a,b))
    if seg_end > cut_end:
        a=(datetime.fromisoformat(cut_end)+timedelta(seconds=1)).isoformat(timespec='seconds'); b=seg_end
        if a<=b: out.append((a,b))
    return out


def _retarget_removed_reviews(database_path:Path,cr_id:str,job_id:str,source_preview:dict[str,Any],source_family_ids:set[int])->int:
    changed=0
    with database_connection(database_path) as c:
        rows=c.execute("""SELECT r.id,r.family_id,r.file_id,f.current_relative_path,f.original_relative_path,ff.selected_capture_time
                          FROM event_change_file_reviews r
                          JOIN files f ON f.id=r.file_id
                          JOIN file_families ff ON ff.id=r.family_id
                          WHERE r.change_request_id=?""",(cr_id,)).fetchall()
        for row in rows:
            if int(row['family_id']) not in source_family_ids: continue
            old=str(row['current_relative_path'] or row['original_relative_path'] or '')
            filename=Path(old).name; capture=str(row['selected_capture_time'] or '')[:19]
            new=_source_target_relative(source_preview,capture,filename)
            c.execute("UPDATE event_change_file_reviews SET new_path=?,action='move',updated_at=datetime('now') WHERE id=?",(new,int(row['id'])))
            changed+=1
        c.commit()
    return changed


def prepare_archived_cascade_impacts(database_path:Path,job_id:str,source_event_id:str,source_preview:dict[str,Any],cascade_preview:dict[str,Any],workspace_path:Path)->dict[str,Any]:
    """Create manual CRs for archived items; never touch archive files."""
    archived=[x for x in cascade_preview.get('items',[]) if str(x.get('status'))=='archived']
    if not archived: return {'change_request_ids':[],'prepared_structures':[],'archived_events':[]}
    source_ids={int(v) for v in source_preview.get('selected_family_ids',[])}
    cut_start=(f"{source_preview['start_date']}T{source_preview.get('start_time') or '00:00'}:00" if source_preview.get('uses_time_range') else f"{source_preview['start_date']}T00:00:00")
    cut_end=(f"{source_preview['end_date']}T{source_preview.get('end_time') or '23:59'}:59" if source_preview.get('uses_time_range') else f"{source_preview['end_date']}T23:59:59")
    cr_ids=[]; prepared=[]; archived_events=[]
    for item in archived:
        eid=str(item['event_id']); ctx=get_event_edit_context(database_path,job_id,eid); ev=ctx['event']
        action=str(item.get('action') or '')
        if item.get('kind')=='event' and action=='split_required':
            raise EventChangeRequestError(
                f"Das ARCHIVIERTE Ereignis „{item.get('name')}“ würde in zwei getrennte Zeitbereiche geteilt. "
                "Dieser seltene Split muss zuerst über zwei eindeutige Zielereignisse aufgelöst werden."
            )
        if item.get('kind')=='event' and action=='fully_covered':
            res=propose_archived_event_deletion(database_path,job_id,eid); cr_id=str(res['change_request_id'])
        else:
            families=[{
                'family_id':int(f['family_id']),'family_key':f['family_key'],'selected_capture_time':f['selected_capture_time'],
                'capture_time_confidence':f['capture_time_confidence'],'day_key':f['day_key'],'has_date':f['has_date'],
                'file_count':int(f['file_count']),'total_size_bytes':int(f['total_size_bytes']),'review_required_count':int(f['review_required_count']),
            } for f in ctx['families']]
            if str(ev.get('event_kind') or 'event')=='no_event':
                segments=[]
                for seg in ctx.get('time_segments',[]):
                    for a,b in _subtract_segment(str(seg['start_datetime'])[:19],str(seg['end_datetime'])[:19],cut_start,cut_end):
                        segments.append({'day_key':a[:10],'start_time':a[11:16],'end_time':b[11:16]})
                retained={int(f['family_id']) for f in families if any(
                    f.get('selected_capture_time') and a['day_key']<=str(f['selected_capture_time'])[:10]<=a['day_key'] and
                    f"{a['day_key']}T{a['start_time']}:00" <= str(f['selected_capture_time'])[:19] <= f"{a['day_key']}T{a['end_time']}:59"
                    for a in segments
                )}
                preview={'event_kind':'no_event','event_name':'Ohne Ereignis','parent_folder':str(ev['folder_name']),
                         'preserve_day_folders':False,'uses_time_range':False,'no_event_segments':segments,
                         'start_date':segments[0]['day_key'] if segments else str(ev['start_datetime'])[:10],
                         'end_date':segments[-1]['day_key'] if segments else str(ev['end_datetime'])[:10],
                         'selected_family_ids':sorted(retained)}
            else:
                new_start=str(item.get('proposed_start') or item.get('current_start'))[:19]
                new_end=str(item.get('proposed_end') or item.get('current_end'))[:19]
                uses=not (new_start[11:19]=='00:00:00' and new_end[11:19]=='23:59:59')
                raw={'event_kind':'event','event_name':str(ev['name']),'start_date':new_start[:10],'end_date':new_end[:10],
                     'uses_time_range':uses,'child_event_name':str((ctx.get('child_event') or {}).get('name') or ev['name']),
                     'start_time':new_start[11:16],'end_time':new_end[11:16],
                     'preserve_day_folders':bool(ev.get('preserve_day_folders')),'selected_day_keys':[]}
                preview=build_event_preview(raw,families)
            res=propose_event_change(
                database_path,job_id,eid,preview,
                event_name=str(ev['name']),
                notes=str(ev.get('notes') or ''),
                workspace_path=workspace_path,
            ); cr_id=str(res['change_request_id'])
        _retarget_removed_reviews(database_path,cr_id,job_id,source_preview,source_ids)
        cr_ids.append(cr_id); archived_events.append({'event_id':eid,'name':str(ev['name']),'status':'archived','change_request_id':cr_id})
    return {'change_request_ids':cr_ids,'prepared_structures':sorted(set(prepared)),'archived_events':archived_events,'archive_read_only':True}
