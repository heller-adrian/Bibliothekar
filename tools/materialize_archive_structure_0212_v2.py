from pathlib import Path

p = Path(__file__).resolve().parents[1] / "app" / "archive_reassignment.py"
s = p.read_text(encoding="utf-8")

old_child = """            day=next(iter(days)); start=f'{day}T{st}:00'; end=f'{day}T{et}:59'\n            if not all(start <= str(x['selected_capture_time'] or '')[:19] <= end for x in caps): raise ArchiveReassignmentError('Nicht alle ausgewählten Familien liegen im eingegebenen Zeitbereich.')\n            overlap=c.execute(\"SELECT 1 FROM events WHERE parent_event_id=? AND start_datetime<=? AND end_datetime>=? LIMIT 1\",(t['id'],end,start)).fetchone()\n"""
new_child = """            day=next(iter(days)); start=f'{day}T{st}:00'; end=f'{day}T{et}:59'\n            if not (str(t['start_datetime'])[:19] <= start <= end <= str(t['end_datetime'])[:19]):\n                raise ArchiveReassignmentError('Das neue Unterereignis muss vollständig im Zeitraum des Oberereignisses liegen.')\n            if not all(start <= str(x['selected_capture_time'] or '')[:19] <= end for x in caps): raise ArchiveReassignmentError('Nicht alle ausgewählten Familien liegen im eingegebenen Zeitbereich.')\n            overlap=c.execute(\"SELECT 1 FROM events WHERE parent_event_id=? AND start_datetime<=? AND end_datetime>=? LIMIT 1\",(t['id'],end,start)).fetchone()\n"""
if old_child in s:
    s = s.replace(old_child, new_child, 1)
elif "Das neue Unterereignis muss vollständig im Zeitraum des Oberereignisses liegen." not in s:
    raise SystemExit("new-child bounds anchor missing")

old_overlap = """        overlaps = continuous_event_overlaps(\n            c, str(cr['job_id']), str(target['start'])[:19], str(target['end'])[:19],\n            exclude_event_id=str(target.get('event_id') or cr['event_id']) if target['kind'] in {'existing_event','new_child'} else str(cr['event_id']),\n        )\n        if overlaps and target['kind'] not in {'existing_no_event'}:\n            names = sorted({str(r['name']) for r in overlaps})\n            raise ArchiveReassignmentError('Dieses Ziel würde sich mit einem anderen Ereignis überschneiden: ' + ', '.join(names))\n"""
new_overlap = """        # Existing archived targets already own their timeline interval. Adding\n        # families or a child inside that parent must not be rejected because\n        # the still-unmodified source event overlaps until the change request\n        # is finished. Only newly created root targets extend the timeline.\n        if target['kind'] in {'new_event','new_no_event'}:\n            overlaps = continuous_event_overlaps(\n                c, str(cr['job_id']), str(target['start'])[:19], str(target['end'])[:19],\n                exclude_event_id=str(cr['event_id']),\n            )\n            if overlaps:\n                names = sorted({str(r['name']) for r in overlaps})\n                raise ArchiveReassignmentError('Dieses Ziel würde sich mit einem anderen Ereignis überschneiden: ' + ', '.join(names))\n"""
if old_overlap in s:
    s = s.replace(old_overlap, new_overlap, 1)
elif "Only newly created root targets extend the timeline." not in s:
    raise SystemExit("archive overlap anchor missing")

p.write_text(s, encoding="utf-8")
