from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def replace_once(path, old, new):
    p=ROOT/path
    s=p.read_text(encoding='utf-8')
    if new in s:
        return
    if old not in s:
        raise SystemExit(f'missing anchor in {path}: {old[:140]!r}')
    p.write_text(s.replace(old,new,1),encoding='utf-8')

# ---------------------------------------------------------------------------
# Simple normal (including archived) -> multiple child segments in ONE edit.
# The simple controls remain as an alternative; adding a segment switches the
# submitted structure to child_segments without needing an intermediate save.
# ---------------------------------------------------------------------------
replace_once('app/events_ui.py', '''${childEvents.length ? `<div class="edit-field full"><div style="display:flex;justify-content:space-between;align-items:center;gap:10px"><span>Zeitsegmente / Unterereignisse</span>${structural ? `<button id="add-normal-segment" type="button">＋ Zeitsegment hinzufügen</button>` : ""}</div><div id="normal-event-segments" style="display:grid;gap:6px;margin-top:6px">${normalSegmentHtml}</div><p class="muted">Zeitsegmente können geändert, ergänzt oder vollständig entfernt werden. Die Dateizugehörigkeit wird danach ausschließlich aus Datum und Uhrzeit neu berechnet.</p></div>` : `<label class="edit-field"><span>Unterereignis / Uhrzeit</span><select id="edit-time-enabled" ${structural ? "" : "disabled"}><option value="0" selected>Ganzer Zeitraum</option><option value="1">Zeitbereich verwenden</option></select></label><label class="edit-field"><span>Bezeichnung Zeitbereich</span><input id="edit-child-name" value="${escapeHtml(event.name || "")}" disabled></label><label class="edit-field"><span>Startzeit</span><input id="edit-start-time" type="time" value="00:00" disabled></label><label class="edit-field"><span>Endzeit</span><input id="edit-end-time" type="time" value="23:59" disabled></label>`}`}
''', '''${childEvents.length ? `<div class="edit-field full"><div style="display:flex;justify-content:space-between;align-items:center;gap:10px"><span>Zeitsegmente / Unterereignisse</span>${structural ? `<button id="add-normal-segment" type="button">＋ Zeitsegment hinzufügen</button>` : ""}</div><div id="normal-event-segments" style="display:grid;gap:6px;margin-top:6px">${normalSegmentHtml}</div><p class="muted">Zeitsegmente können geändert, ergänzt oder vollständig entfernt werden. Die Dateizugehörigkeit wird danach ausschließlich aus Datum und Uhrzeit neu berechnet.</p></div>` : `<label class="edit-field"><span>Unterereignis / Uhrzeit</span><select id="edit-time-enabled" ${structural ? "" : "disabled"}><option value="0" selected>Ganzer Zeitraum</option><option value="1">Ein Zeitbereich</option></select></label><label class="edit-field"><span>Bezeichnung Zeitbereich</span><input id="edit-child-name" value="${escapeHtml(event.name || "")}" disabled></label><label class="edit-field"><span>Startzeit</span><input id="edit-start-time" type="time" value="00:00" disabled></label><label class="edit-field"><span>Endzeit</span><input id="edit-end-time" type="time" value="23:59" disabled></label>${structural ? `<div class="edit-field full"><div style="display:flex;justify-content:space-between;align-items:center;gap:10px"><span>Mehrere Unterereignisse</span><button id="add-normal-segment" type="button">＋ Zeitsegment hinzufügen</button></div><div id="normal-event-segments" style="display:grid;gap:6px;margin-top:6px"></div><p class="muted">Sobald hier Zeitsegmente angelegt sind, bilden sie gemeinsam die neue Ereignisstruktur. Das funktioniert auch bei einem bisher einfachen archivierten Ereignis in einem einzigen Änderungsauftrag.</p></div>` : ""}`}`}
''')

# ---------------------------------------------------------------------------
# Archive reassignment: list archived normal parents and their existing child
# events as explicit manual targets, while retaining no-event targets.
# ---------------------------------------------------------------------------
replace_once('app/archive_reassignment.py', '''        targets=[]
        if months:
            ph=','.join('?' for _ in months)
            for r in c.execute(f"""SELECT id,name,folder_name,status,start_datetime,event_kind FROM events
                                    WHERE parent_event_id IS NULL AND event_kind='no_event' AND status='archived'
                                      AND substr(start_datetime,1,7) IN ({ph}) ORDER BY start_datetime""",months).fetchall():
                targets.append(dict(r))
    return {'change_request_id':cr_id,'job_id':str(cr['job_id']),'families':[dict(r) for r in rows],'family_count':len(rows),'targets':targets}
''', '''        targets=[]
        if months:
            ph=','.join('?' for _ in months)
            for r in c.execute(f"""SELECT id,name,folder_name,status,start_datetime,end_datetime,event_kind,preserve_day_folders
                                    FROM events
                                    WHERE parent_event_id IS NULL AND status='archived'
                                      AND (event_kind!='no_event' OR substr(start_datetime,1,7) IN ({ph}))
                                    ORDER BY start_datetime,id""",months).fetchall():
                item=dict(r); item['children']=[]
                if str(r['event_kind'])=='event':
                    item['children']=[dict(x) for x in c.execute(
                        "SELECT id,name,folder_name,start_datetime,end_datetime FROM events WHERE parent_event_id=? AND status='archived' ORDER BY start_datetime,id",
                        (r['id'],),
                    ).fetchall()]
                targets.append(item)
    return {'change_request_id':cr_id,'job_id':str(cr['job_id']),'families':[dict(r) for r in rows],'family_count':len(rows),'targets':targets}
''')

# signature receives explicit child time fields
replace_once('app/archive_reassignment.py', '''def assign_archive_reassignments(database_path:Path,cr_id:str,family_ids:list[int],*,target_mode:str,new_event_name:str|None=None,target_event_id:str|None=None,workspace_path:Path|None=None)->dict[str,Any]:
''', '''def assign_archive_reassignments(database_path:Path,cr_id:str,family_ids:list[int],*,target_mode:str,new_event_name:str|None=None,target_event_id:str|None=None,target_child_event_id:str|None=None,new_child_start:str|None=None,new_child_end:str|None=None,workspace_path:Path|None=None)->dict[str,Any]:
''')

# target modes: existing archived event/child + explicit new child under archived parent
replace_once('app/archive_reassignment.py', '''        elif target_mode=='existing_no_event':
            t=c.execute("SELECT * FROM events WHERE id=? AND parent_event_id IS NULL",(target_event_id,)).fetchone()
            if t is None or str(t['status'])!='archived' or str(t['event_kind'])!='no_event': raise ArchiveReassignmentError('Als bestehendes Archivziel ist nur eine archivierte „Ohne Ereignis“-Sammlung zulässig.')
            target={'kind':'existing_no_event','event_id':str(t['id']),'name':'Ohne Ereignis','folder':str(t['folder_name']),'start':str(t['start_datetime']),'end':str(t['end_datetime']),'uses':0,'child_name':None,'child_folder':None,'preserve':int(bool(t['preserve_day_folders']))}
        else: raise ArchiveReassignmentError('Unbekanntes Ziel.')
        overlaps = continuous_event_overlaps(
            c, str(cr['job_id']), str(target['start'])[:19], str(target['end'])[:19],
            exclude_event_id=str(cr['event_id']),
        )
''', '''        elif target_mode=='existing_no_event':
            t=c.execute("SELECT * FROM events WHERE id=? AND parent_event_id IS NULL",(target_event_id,)).fetchone()
            if t is None or str(t['status'])!='archived' or str(t['event_kind'])!='no_event': raise ArchiveReassignmentError('Die archivierte „Ohne Ereignis“-Sammlung ist nicht verfügbar.')
            target={'kind':'existing_no_event','event_id':str(t['id']),'name':'Ohne Ereignis','folder':str(t['folder_name']),'start':str(t['start_datetime']),'end':str(t['end_datetime']),'uses':0,'child_name':None,'child_folder':None,'preserve':int(bool(t['preserve_day_folders']))}
        elif target_mode=='existing_event':
            t=c.execute("SELECT * FROM events WHERE id=? AND parent_event_id IS NULL",(target_event_id,)).fetchone()
            if t is None or str(t['status'])!='archived' or str(t['event_kind'])!='event': raise ArchiveReassignmentError('Das archivierte Zielereignis ist nicht verfügbar.')
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
            if t is None or str(t['status'])!='archived' or str(t['event_kind'])!='event': raise ArchiveReassignmentError('Das archivierte Oberereignis ist nicht verfügbar.')
            clean=str(new_event_name or '').strip(); st=str(new_child_start or '').strip(); et=str(new_child_end or '').strip()
            if not clean: raise ArchiveReassignmentError('Name des neuen Unterereignisses fehlt.')
            if len(st)!=5 or len(et)!=5 or st>=et: raise ArchiveReassignmentError('Start- und Endzeit des neuen Unterereignisses sind ungültig.')
            phf=','.join('?' for _ in fids); caps=c.execute(f"SELECT selected_capture_time FROM file_families WHERE id IN ({phf})",fids).fetchall()
            days={str(x['selected_capture_time'] or '')[:10] for x in caps}
            if len(days)!=1: raise ArchiveReassignmentError('Ein neues Unterereignis wird aus genau einem Tag angelegt.')
            day=next(iter(days)); start=f'{day}T{st}:00'; end=f'{day}T{et}:59'
            if not all(start <= str(x['selected_capture_time'] or '')[:19] <= end for x in caps): raise ArchiveReassignmentError('Nicht alle ausgewählten Familien liegen im eingegebenen Zeitbereich.')
            overlap=c.execute("SELECT 1 FROM events WHERE parent_event_id=? AND start_datetime<=? AND end_datetime>=? LIMIT 1",(t['id'],end,start)).fetchone()
            if overlap: raise ArchiveReassignmentError('Der neue Zeitbereich überschneidet sich mit einem vorhandenen Unterereignis.')
            child_folder=f"{st.replace(':','-')} - {et.replace(':','-')} - {clean}"
            target={'kind':'new_child','event_id':str(t['id']),'child_event_id':None,'name':str(t['name']),'folder':str(t['folder_name']),
                    'start':start,'end':end,'uses':1,'child_name':clean,'child_folder':child_folder,'preserve':int(bool(t['preserve_day_folders']))}
        else: raise ArchiveReassignmentError('Unbekanntes Ziel.')
        overlaps = continuous_event_overlaps(
            c, str(cr['job_id']), str(target['start'])[:19], str(target['end'])[:19],
            exclude_event_id=str(target.get('event_id') or cr['event_id']) if target['kind'] in {'existing_event','new_child'} else str(cr['event_id']),
        )
''')

# Store child event id for existing_event in target_kind encoding; schema has no dedicated child id.
replace_once('app/archive_reassignment.py', '''            c.execute("""INSERT OR REPLACE INTO event_change_reassignments(change_request_id,family_id,target_kind,target_event_id,target_name,target_folder_name,target_start_datetime,target_end_datetime,target_uses_time_range,target_child_name,target_child_folder,target_preserve_day_folders,created_at)
                         VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",(cr_id,fid,target['kind'],target['event_id'],target['name'],target['folder'],target['start'],target['end'],target['uses'],target['child_name'],target['child_folder'],target['preserve'],now))
''', '''            stored_kind = target['kind'] + (':' + str(target.get('child_event_id')) if target['kind']=='existing_event' and target.get('child_event_id') else '')
            c.execute("""INSERT OR REPLACE INTO event_change_reassignments(change_request_id,family_id,target_kind,target_event_id,target_name,target_folder_name,target_start_datetime,target_end_datetime,target_uses_time_range,target_child_name,target_child_folder,target_preserve_day_folders,created_at)
                         VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",(cr_id,fid,stored_kind,target['event_id'],target['name'],target['folder'],target['start'],target['end'],target['uses'],target['child_name'],target['child_folder'],target['preserve'],now))
''')

# Apply existing archived event / existing child / new child instead of creating a duplicate parent.
replace_once('app/archive_reassignment.py', '''        if kind=='existing_no_event':
            eid=target_id
''', '''        if kind.startswith('existing_event'):
            eid=target_id
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
''')

# Main forwards archive target details.
replace_once('app/main.py', '''            target_event_id=body.get("target_event_id"),
            workspace_path=WORKSPACE_PATH,
        )
''', '''            target_event_id=body.get("target_event_id"),
            target_child_event_id=body.get("target_child_event_id"),
            new_child_start=body.get("new_child_start"),
            new_child_end=body.get("new_child_end"),
            workspace_path=WORKSPACE_PATH,
        )
''')

# Archive UI target options now include archived normal events, their child events, and new child option.
replace_once('app/events_ui.py', '''          const targetOptions = (archiveReassignData.targets||[]).map(t =>
            `<option value="existing:${escapeHtml(t.id)}">Bestehend · ${escapeHtml(t.folder_name||t.name||t.id)}</option>`
          ).join("");
''', '''          const targetOptions = (archiveReassignData.targets||[]).map(t => {
            if (t.event_kind === "no_event") return `<option value="existing-no-event:${escapeHtml(t.id)}">Bestehend · ${escapeHtml(t.folder_name||t.name||t.id)}</option>`;
            const parent=`<option value="existing-event:${escapeHtml(t.id)}">Bestehendes Ereignis · ${escapeHtml(t.name||t.folder_name||t.id)}</option>`;
            const child=(t.children||[]).map(c=>`<option value="existing-child:${escapeHtml(t.id)}:${escapeHtml(c.id)}">Bestehendes Unterereignis · ${escapeHtml(t.name)} / ${escapeHtml(c.name)}</option>`).join("");
            const newChild=`<option value="new-child:${escapeHtml(t.id)}">Neues Unterereignis in · ${escapeHtml(t.name)}</option>`;
            return parent+child+newChild;
          }).join("");
''')

replace_once('app/events_ui.py', '''          html += `<label id="archive-reassign-name-row" class="edit-field"><span>Name des neuen Ereignisses</span><input id="archive-reassign-name" type="text" placeholder="Ereignisname"></label>`;
''', '''          html += `<label id="archive-reassign-name-row" class="edit-field"><span>Name des neuen Ereignisses / Unterereignisses</span><input id="archive-reassign-name" type="text" placeholder="Name"></label>`;
          html += `<div id="archive-reassign-time-row" class="edit-grid" hidden><label class="edit-field"><span>Startzeit</span><input id="archive-reassign-start" type="time"></label><label class="edit-field"><span>Endzeit</span><input id="archive-reassign-end" type="time"></label></div>`;
''')
replace_once('app/events_ui.py', '''        if (archiveTarget && archiveNameRow) {
          const syncArchiveName = () => { archiveNameRow.hidden = archiveTarget.value !== "new"; };
          archiveTarget.addEventListener("change", syncArchiveName); syncArchiveName();
        }
''', '''        if (archiveTarget && archiveNameRow) {
          const archiveTimeRow=changeRequestBody.querySelector("#archive-reassign-time-row");
          const syncArchiveName = () => {
            const isNew=archiveTarget.value === "new";
            const isChild=archiveTarget.value.startsWith("new-child:");
            archiveNameRow.hidden = !(isNew || isChild);
            if (archiveTimeRow) archiveTimeRow.hidden = !isChild;
          };
          archiveTarget.addEventListener("change", syncArchiveName); syncArchiveName();
        }
''')
replace_once('app/events_ui.py', '''          const value = archiveTarget.value;
          const body = { family_ids: familyIds, target_mode: value === "new" ? "new_event" : (value === "new-no-event" ? "new_no_event" : "existing_no_event"), target_event_id: value.startsWith("existing:") ? value.slice(9) : null, new_event_name: value === "new" ? changeRequestBody.querySelector("#archive-reassign-name").value : null };
''', '''          const value = archiveTarget.value;
          let targetMode="new_event", targetEventId=null, targetChildEventId=null;
          if (value === "new-no-event") targetMode="new_no_event";
          else if (value.startsWith("existing-no-event:")) { targetMode="existing_no_event"; targetEventId=value.slice(18); }
          else if (value.startsWith("existing-event:")) { targetMode="existing_event"; targetEventId=value.slice(15); }
          else if (value.startsWith("existing-child:")) { const bits=value.split(":"); targetMode="existing_event"; targetEventId=bits[1]; targetChildEventId=bits[2]; }
          else if (value.startsWith("new-child:")) { targetMode="new_child"; targetEventId=value.slice(10); }
          const isNamed = value === "new" || targetMode === "new_child";
          const body = { family_ids: familyIds, target_mode: targetMode, target_event_id: targetEventId, target_child_event_id: targetChildEventId, new_event_name: isNamed ? changeRequestBody.querySelector("#archive-reassign-name").value : null, new_child_start: targetMode === "new_child" ? changeRequestBody.querySelector("#archive-reassign-start").value : null, new_child_end: targetMode === "new_child" ? changeRequestBody.querySelector("#archive-reassign-end").value : null };
''')

print('archive structure materialized')
