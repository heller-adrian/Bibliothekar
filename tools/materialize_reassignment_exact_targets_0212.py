from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def replace_once(path, old, new):
    p=ROOT/path
    s=p.read_text(encoding='utf-8')
    if new in s:
        return
    if old not in s:
        raise SystemExit(f'missing anchor in {path}: {old[:120]!r}')
    p.write_text(s.replace(old,new,1),encoding='utf-8')

# UI renders exact atomic segments from backend and posts those exact boundaries.
replace_once('app/events_ui.py', '''      const byDay=new Map();
      for (const f of families) {
        const day=String(f.selected_capture_time||"").slice(0,10)||"Ohne Datum";
        if (!byDay.has(day)) byDay.set(day,[]);
        byDay.get(day).push(f);
      }
      const dayGroups=[...byDay.entries()].map(([day,items])=>{
        const files=items.reduce((n,f)=>n+Number(f.file_count||0),0);
        const explicitRange=(data.reassignment_time_ranges||{})[day] || null;
        const timeText=explicitRange ? ` · ${explicitRange.start_time}–${explicitRange.end_time}` : "";
        const ids=items.map(f=>Number(f.family_id)).join(",");
        return `<label class="card" style="display:flex;align-items:center;gap:10px;padding:10px 12px"><input type="checkbox" data-reassign-day data-family-ids="${escapeHtml(ids)}" data-day="${escapeHtml(day)}" checked style="width:18px;height:18px;flex:0 0 auto"><span style="min-width:0"><strong>${escapeHtml(germanDay(day))}${escapeHtml(timeText)}</strong><br><span class="muted">${items.length} Familien · ${files} Dateien · nur gemeinsam zuordenbar</span></span></label>`;
      }).join("");
''', '''      const exactSegments=data.reassignment_segments || [];
      const dayGroups=exactSegments.map(segment=>{
        const ids=(segment.family_ids||[]).map(Number).join(",");
        const day=segment.day_key || String(segment.start_datetime||"").slice(0,10);
        const fallback=segment.fallback ? " · Legacy-Zeitraum aus Aufnahmen" : "";
        return `<label class="card" style="display:flex;align-items:center;gap:10px;padding:10px 12px"><input type="checkbox" data-reassign-day data-family-ids="${escapeHtml(ids)}" data-day="${escapeHtml(day)}" data-start="${escapeHtml(segment.start_datetime||"")}" data-end="${escapeHtml(segment.end_datetime||"")}" checked style="width:18px;height:18px;flex:0 0 auto"><span style="min-width:0"><strong>${escapeHtml(germanDay(day))} · ${escapeHtml(segment.start_time||"")}–${escapeHtml(segment.end_time||"")}</strong><br><span class="muted">${Number(segment.family_count||0)} Familien · ${Number(segment.file_count||0)} Dateien · nur gemeinsam zuordenbar${escapeHtml(fallback)}</span></span></label>`;
      }).join("");
''')
replace_once('app/events_ui.py', '''        const selectedIds=[...new Set(selectedDays.flatMap(i=>String(i.dataset.familyIds||"").split(",").filter(Boolean).map(Number)))];
        if (!selectedIds.length) { document.getElementById("reassignment-message").textContent = "Bitte mindestens ein Tages-/Zeitsegment auswählen."; return; }
''', '''        const selectedIds=[...new Set(selectedDays.flatMap(i=>String(i.dataset.familyIds||"").split(",").filter(Boolean).map(Number)))];
        const selectedSegments=selectedDays.map(i=>({start_datetime:i.dataset.start,end_datetime:i.dataset.end,day_key:i.dataset.day}));
        if (!selectedIds.length) { document.getElementById("reassignment-message").textContent = "Bitte mindestens ein Tages-/Zeitsegment auswählen."; return; }
''')
replace_once('app/events_ui.py', '''            body:JSON.stringify({family_ids:selectedIds, target_mode:targetMode, target_event_id:(isNew||isNewNoEvent) ? null : (isNewChild ? opt.dataset.parentId : target.value), new_event_name:(isNew||isNewChild) ? document.getElementById("reassignment-new-name").value : null})
''', '''            body:JSON.stringify({family_ids:selectedIds, segments:selectedSegments, target_mode:targetMode, target_event_id:(isNew||isNewNoEvent) ? null : (isNewChild ? opt.dataset.parentId : target.value), new_event_name:(isNew||isNewChild) ? document.getElementById("reassignment-new-name").value : null})
''')

# Main API forwards exact segments.
replace_once('app/main.py', '''            target_event_id=body.get("target_event_id"),
            new_event_name=body.get("new_event_name"),
        )
''', '''            target_event_id=body.get("target_event_id"),
            new_event_name=body.get("new_event_name"),
            segments=body.get("segments") or [],
        )
''')

# Reassignment helpers + validation.
replace_once('app/event_reassignment.py', '''def _normalize_ids(values: Iterable[Any]) -> list[int]:
    result = sorted({int(v) for v in values if int(v) > 0})
    if not result:
        raise EventReassignmentError("Es wurden keine herausfallenden Familien ausgewählt.")
    return result


def _root_event(connection, event_id: str):
''', '''def _normalize_ids(values: Iterable[Any]) -> list[int]:
    result = sorted({int(v) for v in values if int(v) > 0})
    if not result:
        raise EventReassignmentError("Es wurden keine herausfallenden Familien ausgewählt.")
    return result


def _normalize_reassignment_segments(values: Iterable[Any] | None) -> list[dict[str,str]]:
    result=[]
    seen=set()
    for value in values or []:
        if not isinstance(value,dict):
            raise EventReassignmentError("Ein Tages-/Zeitsegment ist ungültig.")
        start=str(value.get("start_datetime") or "")[:19]
        end=str(value.get("end_datetime") or "")[:19]
        if len(start)!=19 or len(end)!=19 or start>end or start[:10] != end[:10]:
            raise EventReassignmentError("Ein Tages-/Zeitsegment besitzt ungültige Grenzen.")
        key=(start,end)
        if key in seen:
            continue
        seen.add(key)
        result.append({"day_key":start[:10],"start_datetime":start,"end_datetime":end,
                       "start_time":start[11:16],"end_time":end[11:16]})
    result.sort(key=lambda x:(x["start_datetime"],x["end_datetime"]))
    return result


def _root_event(connection, event_id: str):
''')

# Do not expose archived normal events as impossible direct targets.
replace_once('app/event_reassignment.py', '''    for target in target_rows:
        month_key = str(target["month_key"] or "")
        if str(target["event_kind"]) == "no_event":
''', '''    for target in target_rows:
        month_key = str(target["month_key"] or "")
        if str(target["event_kind"]) != "no_event" and str(target["status"]) == "archived":
            continue
        if str(target["event_kind"]) == "no_event":
''')
replace_once('app/event_reassignment.py', '''        "new_no_event_supported": not bool(target_list),
''', '''        "new_no_event_supported": not any(str(item.get("event_kind")) == "no_event" for item in target_list),
''')

# New no-event uses persisted exact segments when available.
replace_once('app/event_reassignment.py', '''def _create_new_no_event(
    database_path: Path, job_id: str, family_ids: list[int],
    *, ignore_event_ids: set[str] | None = None,
) -> dict[str, Any]:
''', '''def _create_new_no_event(
    database_path: Path, job_id: str, family_ids: list[int],
    *, ignore_event_ids: set[str] | None = None, segments: list[dict[str,str]] | None = None,
) -> dict[str, Any]:
''')
replace_once('app/event_reassignment.py', '''        "no_event_segments": _no_event_segments_for_rows(rows),
        "selected_family_ids": family_ids,
''', '''        "no_event_segments": (segments or _no_event_segments_for_rows(rows)),
        "selected_family_ids": family_ids,
''')

# Cross-job no-event exact segments.
replace_once('app/event_reassignment.py', '''def _create_cross_job_no_event_extension(connection, job_id: str, target, family_ids: list[int], now: str) -> dict[str, Any]:
''', '''def _create_cross_job_no_event_extension(connection, job_id: str, target, family_ids: list[int], now: str, segments: list[dict[str,str]] | None = None) -> dict[str, Any]:
''')
replace_once('app/event_reassignment.py', '''    for seg in _no_event_segments_for_rows(rows):
        day=seg["day_key"]; start=f"{day}T{seg['start_time']}:00"; end=f"{day}T{seg['end_time']}:59"
''', '''    for seg in (segments or _no_event_segments_for_rows(rows)):
        day=seg["day_key"]
        start=seg.get("start_datetime") or f"{day}T{seg['start_time']}:00"
        end=seg.get("end_datetime") or f"{day}T{seg['end_time']}:59"
''')

# New child exact range.
replace_once('app/event_reassignment.py', '''def _create_child_in_existing_event(connection, job_id: str, target, family_ids: list[int], name: str, now: str) -> dict[str, Any]:
''', '''def _create_child_in_existing_event(connection, job_id: str, target, family_ids: list[int], name: str, now: str, segments: list[dict[str,str]] | None = None) -> dict[str, Any]:
''')
replace_once('app/event_reassignment.py', '''    start=min(captures); end=max(captures)
    overlaps=connection.execute(
''', '''    if segments:
        if len(segments) != 1:
            raise EventReassignmentError("Ein neues Unterereignis übernimmt genau ein Tages-/Zeitsegment. Weitere Segmente danach separat zuordnen.")
        start=segments[0]["start_datetime"]; end=segments[0]["end_datetime"]
        if not all(start <= capture <= end for capture in captures):
            raise EventReassignmentError("Die ausgewählten Familien passen nicht vollständig in das Tages-/Zeitsegment.")
    else:
        start=min(captures); end=max(captures)
    overlaps=connection.execute(
''')

# Reassignment signature and durable validation.
replace_once('app/event_reassignment.py', '''def assign_event_reassignments(
    database_path: Path, job_id: str, event_id: str, family_ids: Iterable[Any],
    *, target_mode: str, target_event_id: str | None = None, new_event_name: str | None = None,
) -> dict[str, Any]:
    selected = _normalize_ids(family_ids)
    now = _now()
''', '''def assign_event_reassignments(
    database_path: Path, job_id: str, event_id: str, family_ids: Iterable[Any],
    *, target_mode: str, target_event_id: str | None = None, new_event_name: str | None = None,
    segments: Iterable[Any] | None = None,
) -> dict[str, Any]:
    selected = _normalize_ids(family_ids)
    exact_segments = _normalize_reassignment_segments(segments)
    now = _now()
''')
replace_once('app/event_reassignment.py', '''        pending = connection.execute(
            f"SELECT family_id FROM event_reapply_removed_families WHERE job_id=? AND event_id=? AND family_id IN ({placeholders})",
            (job_id, event_id, *selected),
        ).fetchall()
        if {int(r["family_id"]) for r in pending} != set(selected):
            raise EventReassignmentError("Mindestens eine Familie ist nicht mehr zur Neu-Zuordnung offen.")
''', '''        pending = connection.execute(
            f"SELECT family_id,released_start_datetime,released_end_datetime FROM event_reapply_removed_families WHERE job_id=? AND event_id=? AND family_id IN ({placeholders})",
            (job_id, event_id, *selected),
        ).fetchall()
        if {int(r["family_id"]) for r in pending} != set(selected):
            raise EventReassignmentError("Mindestens eine Familie ist nicht mehr zur Neu-Zuordnung offen.")
        expected_ranges={
            (str(r["released_start_datetime"])[:19],str(r["released_end_datetime"])[:19])
            for r in pending if r["released_start_datetime"] and r["released_end_datetime"]
        }
        provided_ranges={(seg["start_datetime"],seg["end_datetime"]) for seg in exact_segments}
        if expected_ranges and provided_ranges != expected_ranges:
            raise EventReassignmentError("Die ausgewählten Tages-/Zeitsegmente sind nicht mehr aktuell. Bitte die Neu-Zuordnung neu öffnen.")
        if exact_segments:
            capture_rows=_selected_capture_rows(connection,job_id,selected)
            for row in capture_rows:
                cap=str(row["selected_capture_time"] or "")[:19]
                if not any(seg["start_datetime"] <= cap <= seg["end_datetime"] for seg in exact_segments):
                    raise EventReassignmentError("Mindestens eine Familie liegt außerhalb der ausgewählten Tages-/Zeitsegmente.")
''')

# New event: preserve one exact segment. Multiple same-target segments are intentionally
# handled one reassignment action at a time until general multi-day child semantics are explicit.
replace_once('app/event_reassignment.py', '''    if target_mode == "new_event":
        target_info = _create_new_event(
            database_path, job_id, selected, str(new_event_name or ""),
            ignore_event_ids=ignored_for_target,
        )
    elif target_mode == "new_no_event":
        target_info = _create_new_no_event(
            database_path, job_id, selected, ignore_event_ids=ignored_for_target,
        )
''', '''    if target_mode == "new_event":
        if len(exact_segments) > 1:
            raise EventReassignmentError("Ein neues normales Ereignis übernimmt pro Schritt genau ein Tages-/Zeitsegment. Ordne weitere Segmente anschließend demselben Ereignis oder weiteren Zielen zu.")
        target_info = _create_new_event(
            database_path, job_id, selected, str(new_event_name or ""),
            ignore_event_ids=ignored_for_target,
            segment=exact_segments[0] if exact_segments else None,
        )
    elif target_mode == "new_no_event":
        target_info = _create_new_no_event(
            database_path, job_id, selected, ignore_event_ids=ignored_for_target, segments=exact_segments,
        )
''')

# _create_new_event accepts exact range.
replace_once('app/event_reassignment.py', '''def _create_new_event(
    database_path: Path, job_id: str, family_ids: list[int], name: str,
    *, ignore_event_ids: set[str] | None = None,
) -> dict[str, Any]:
''', '''def _create_new_event(
    database_path: Path, job_id: str, family_ids: list[int], name: str,
    *, ignore_event_ids: set[str] | None = None, segment: dict[str,str] | None = None,
) -> dict[str, Any]:
''')
replace_once('app/event_reassignment.py', '''    start_date = min(captures)[:10]
    end_date = max(captures)[:10]
''', '''    start_date = (segment["start_datetime"] if segment else min(captures))[:10]
    end_date = (segment["end_datetime"] if segment else max(captures))[:10]
''')
replace_once('app/event_reassignment.py', '''        "start_time": min(captures)[11:16] if same_day else "00:00",
        "end_time": max(captures)[11:16] if same_day else "23:59",
''', '''        "start_time": (segment["start_time"] if segment else min(captures)[11:16]) if same_day else "00:00",
        "end_time": (segment["end_time"] if segment else max(captures)[11:16]) if same_day else "23:59",
''')

# Existing no-event direct extension uses exact selected boundaries.
replace_once('app/event_reassignment.py', '''            if str(target["job_id"]) != job_id:
                target_info = _create_cross_job_no_event_extension(connection, job_id, target, selected, now)
''', '''            if str(target["job_id"]) != job_id:
                target_info = _create_cross_job_no_event_extension(connection, job_id, target, selected, now, exact_segments)
''')
replace_once('app/event_reassignment.py', '''                by_day: dict[str, list[str]] = {}
                for row in captures:
                    cap = str(row["selected_capture_time"])[:19]
                    by_day.setdefault(cap[:10], []).append(cap)
                    connection.execute(
''', '''                by_day: dict[str, list[str]] = {}
                for row in captures:
                    cap = str(row["selected_capture_time"])[:19]
                    by_day.setdefault(cap[:10], []).append(cap)
                    connection.execute(
''')
# Replace loop source only; exact segments if present otherwise legacy min/max.
replace_once('app/event_reassignment.py', '''                for day, values in by_day.items():
                    a, b = min(values), max(values)
                    existing = connection.execute(
''', '''                segment_values = exact_segments or [
                    {"day_key":day,"start_datetime":min(values),"end_datetime":max(values),
                     "start_time":min(values)[11:16],"end_time":max(values)[11:16]}
                    for day,values in by_day.items()
                ]
                for selected_segment in segment_values:
                    day=selected_segment["day_key"]
                    a=selected_segment["start_datetime"]; b=selected_segment["end_datetime"]
                    existing = connection.execute(
''')

# New child call gets exact segment.
replace_once('app/event_reassignment.py', '''            target_info=_create_child_in_existing_event(connection,job_id,target,selected,str(new_event_name or ""),now)
''', '''            target_info=_create_child_in_existing_event(connection,job_id,target,selected,str(new_event_name or ""),now,exact_segments)
''')

print('exact target reassignment patch materialized')
