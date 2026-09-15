from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: str, old: str, new: str) -> None:
    p = ROOT / path
    text = p.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise SystemExit(f"Zielstelle fehlt in {path}: {old[:120]!r}")
    text = text.replace(old, new, 1)
    p.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# 0.21.2 version + SD reuse UX: only camera/media files participate in the
# incremental new/changed counters. Camera management companions are ignored.
# ---------------------------------------------------------------------------
replace_once("app/main.py", 'APP_VERSION = "0.21.1"', 'APP_VERSION = "0.21.2"')

replace_once(
    "app/main.py",
    '''    already_imported_fast = 0
    new_fast = 0
    changed_fast = 0
    history_paths = {str(row["relative_path"]) for row in history_rows}
    for item in path.rglob("*"):
        if item.is_symlink() or not item.is_file():
            continue
        try:
            stat = item.stat()
            size = stat.st_size
        except OSError:
            continue
        file_count += 1
        total_size += size
        relative_item = item.relative_to(path).as_posix()
        if (relative_item, int(size), int(stat.st_mtime_ns)) in fast_history:
            already_imported_fast += 1
        elif relative_item in history_paths:
            changed_fast += 1
        else:
            new_fast += 1
        if item.suffix.lower() in MEDIA_SOURCE_EXTENSIONS:
            media_count += 1
''',
    '''    already_imported_fast = 0
    new_fast = 0
    changed_fast = 0
    ignored_fast = 0
    history_paths = {str(row["relative_path"]) for row in history_rows}
    for item in path.rglob("*"):
        if item.is_symlink() or not item.is_file():
            continue
        try:
            stat = item.stat()
            size = stat.st_size
        except OSError:
            continue
        file_count += 1
        total_size += size
        relative_item = item.relative_to(path).as_posix()
        if item.suffix.lower() not in MEDIA_SOURCE_EXTENSIONS:
            ignored_fast += 1
            continue
        media_count += 1
        if (relative_item, int(size), int(stat.st_mtime_ns)) in fast_history:
            already_imported_fast += 1
        elif relative_item in history_paths:
            changed_fast += 1
        else:
            new_fast += 1
''',
)

replace_once(
    "app/main.py",
    '''    import_status = "available"
    if duplicate is not None:
        import_status = "already_imported" if duplicate.get("state") == "completed" else "import_running"
    return {
''',
    '''    import_status = "available"
    if duplicate is not None:
        import_status = "already_imported" if duplicate.get("state") == "completed" else "import_running"
    elif source_device_id and history_rows and new_fast == 0 and changed_fast == 0:
        # Reused SD card with no new/changed camera media is a normal idle state,
        # not an import error. Non-media camera management files do not keep the
        # source artificially "new".
        import_status = "no_changes"
    return {
''',
)

replace_once(
    "app/main.py",
    '''        "changed_file_count": changed_fast,
        "import_status": import_status,
''',
    '''        "changed_file_count": changed_fast,
        "ignored_file_count": ignored_fast,
        "import_status": import_status,
''',
)

replace_once(
    "app/main.py",
    '''      const changed = Number(source.changed_file_count || 0);
      sdSourceDetail.textContent = `${source.file_count} Dateien insgesamt · `
        + `${source.media_file_count} Medien · `
        + `${formatBytes(source.total_size_bytes)} · `
        + `${Number(source.already_imported_file_count || 0)} bereits gesichert · `
        + `${Number(source.new_file_count || 0)} neu`
        + (changed ? ` · ${changed} verändert/zu prüfen` : "");
''',
    '''      const changed = Number(source.changed_file_count || 0);
      const ignored = Number(source.ignored_file_count || 0);
      sdSourceDetail.textContent = `${source.file_count} Dateien insgesamt · `
        + `${source.media_file_count} Medien · `
        + `${formatBytes(source.total_size_bytes)} · `
        + `${Number(source.already_imported_file_count || 0)} bereits gesichert · `
        + `${Number(source.new_file_count || 0)} neu`
        + (changed ? ` · ${changed} verändert/zu prüfen` : "")
        + (ignored ? ` · ${ignored} Verwaltungsdateien ignoriert` : "")
        + (source.import_status === "no_changes" ? " · Keine neuen Dateien" : "");
''',
)

replace_once(
    "app/main.py",
    '''      const blocked = source.import_status !== "available";
      importButton.disabled = blocked;
      importButton.textContent = source.import_status === "already_imported"
        ? "Bereits importiert"
        : source.import_status === "import_running"
          ? "Import läuft"
          : "Quelle importieren";
      const incremental = source.source_device_id
        ? ` · ${source.already_imported_file_count || 0} bereits gesichert · ${source.new_file_count || 0} neu`
          + ((source.changed_file_count || 0) ? ` · ${source.changed_file_count} verändert/zu prüfen` : "")
        : "";
''',
    '''      const blocked = source.import_status !== "available";
      importButton.disabled = blocked;
      importButton.textContent = source.import_status === "no_changes"
        ? "Keine neuen Dateien"
        : source.import_status === "already_imported"
          ? "Bereits importiert"
          : source.import_status === "import_running"
            ? "Import läuft"
            : "Quelle importieren";
      const incremental = source.source_device_id
        ? ` · ${source.already_imported_file_count || 0} bereits gesichert · ${source.new_file_count || 0} neu`
          + ((source.changed_file_count || 0) ? ` · ${source.changed_file_count} verändert/zu prüfen` : "")
          + ((source.ignored_file_count || 0) ? ` · ${source.ignored_file_count} Verwaltungsdateien ignoriert` : "")
        : "";
''',
)

# ---------------------------------------------------------------------------
# Normal event child segments: add/remove rows in the editor. Existing IDs are
# retained; new rows intentionally have no ID and are materialized by backend.
# ---------------------------------------------------------------------------
replace_once(
    "app/events_ui.py",
    '''          <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:8px;margin-top:8px">
            <label class="edit-field"><span>Bezeichnung</span><input data-child-name value="${escapeHtml(segment.name||"")}" ${structural ? "" : "disabled"}></label>
            <label class="edit-field"><span>Startzeit</span><input data-child-start type="time" value="${escapeHtml(start)}" ${structural ? "" : "disabled"}></label>
            <label class="edit-field"><span>Endzeit</span><input data-child-end type="time" value="${escapeHtml(end)}" ${structural ? "" : "disabled"}></label>
          </div>
''',
    '''          <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:8px;margin-top:8px">
            <label class="edit-field"><span>Bezeichnung</span><input data-child-name value="${escapeHtml(segment.name||"")}" ${structural ? "" : "disabled"}></label>
            <label class="edit-field"><span>Startzeit</span><input data-child-start type="time" value="${escapeHtml(start)}" ${structural ? "" : "disabled"}></label>
            <label class="edit-field"><span>Endzeit</span><input data-child-end type="time" value="${escapeHtml(end)}" ${structural ? "" : "disabled"}></label>
            ${structural ? `<button type="button" data-remove-child-segment class="danger-button">Zeitsegment entfernen</button>` : ""}
          </div>
''',
)

replace_once(
    "app/events_ui.py",
    '''          ${childEvents.length ? `<div class="edit-field full"><span>Zeitsegmente / Unterereignisse</span><div style="display:grid;gap:6px;margin-top:6px">${normalSegmentHtml}</div><p class="muted">Jedes vorhandene Zeitsegment wird vollständig angezeigt. Änderungen der Uhrzeit bestimmen automatisch, welche Familien im Ereignis verbleiben.</p></div>` : `<label class="edit-field"><span>Unterereignis / Uhrzeit</span><select id="edit-time-enabled" ${structural ? "" : "disabled"}><option value="0" selected>Ganzer Zeitraum</option><option value="1">Zeitbereich verwenden</option></select></label><label class="edit-field"><span>Bezeichnung Zeitbereich</span><input id="edit-child-name" value="${escapeHtml(event.name || "")}" disabled></label><label class="edit-field"><span>Startzeit</span><input id="edit-start-time" type="time" value="00:00" disabled></label><label class="edit-field"><span>Endzeit</span><input id="edit-end-time" type="time" value="23:59" disabled></label>`}`}
''',
    '''          ${childEvents.length ? `<div class="edit-field full"><div style="display:flex;justify-content:space-between;align-items:center;gap:10px"><span>Zeitsegmente / Unterereignisse</span>${structural ? `<button id="add-normal-segment" type="button">＋ Zeitsegment hinzufügen</button>` : ""}</div><div id="normal-event-segments" style="display:grid;gap:6px;margin-top:6px">${normalSegmentHtml}</div><p class="muted">Zeitsegmente können geändert, ergänzt oder vollständig entfernt werden. Die Dateizugehörigkeit wird danach ausschließlich aus Datum und Uhrzeit neu berechnet.</p></div>` : `<label class="edit-field"><span>Unterereignis / Uhrzeit</span><select id="edit-time-enabled" ${structural ? "" : "disabled"}><option value="0" selected>Ganzer Zeitraum</option><option value="1">Zeitbereich verwenden</option></select></label><label class="edit-field"><span>Bezeichnung Zeitbereich</span><input id="edit-child-name" value="${escapeHtml(event.name || "")}" disabled></label><label class="edit-field"><span>Startzeit</span><input id="edit-start-time" type="time" value="00:00" disabled></label><label class="edit-field"><span>Endzeit</span><input id="edit-end-time" type="time" value="23:59" disabled></label>`}`}
''',
)

replace_once(
    "app/events_ui.py",
    '''      if (!noEvent) {
        const timeEnabled = document.getElementById("edit-time-enabled");
''',
    '''      if (!noEvent) {
        const normalContainer = document.getElementById("normal-event-segments");
        const bindNormalRemove = () => normalContainer?.querySelectorAll("[data-remove-child-segment]").forEach(button => {
          button.onclick = () => button.closest("[data-child-segment]")?.remove();
        });
        bindNormalRemove();
        document.getElementById("add-normal-segment")?.addEventListener("click", () => {
          if (!normalContainer) return;
          const row=document.createElement("details");
          row.className="card"; row.dataset.childSegment="1"; row.open=true;
          row.style.cssText="padding:8px 10px;margin:6px 0";
          row.innerHTML=`<summary style="cursor:pointer"><strong>Neues Zeitsegment</strong></summary><div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:8px;margin-top:8px"><label class="edit-field"><span>Bezeichnung</span><input data-child-name value="${escapeHtml(event.name||"")}"></label><label class="edit-field"><span>Startzeit</span><input data-child-start type="time" value="00:00"></label><label class="edit-field"><span>Endzeit</span><input data-child-end type="time" value="23:59"></label><button type="button" data-remove-child-segment class="danger-button">Zeitsegment entfernen</button></div>`;
          normalContainer.appendChild(row); bindNormalRemove();
        });
        const timeEnabled = document.getElementById("edit-time-enabled");
''',
)

replace_once(
    "app/events_ui.py",
    '''              child_segments: segmentRows.map(row=>({
                id: row.dataset.childId,
                name: row.querySelector("[data-child-name]").value,
''',
    '''              child_segments: segmentRows.map(row=>({
                id: row.dataset.childId || null,
                name: row.querySelector("[data-child-name]").value,
''',
)

# ---------------------------------------------------------------------------
# Reassignment is a day/time-segment decision, never a family checkbox UI.
# The selected day rows carry their family IDs internally for the existing API.
# ---------------------------------------------------------------------------
replace_once(
    "app/events_ui.py",
    '<h2>Herausfallende Familien neu zuordnen</h2>',
    '<h2>Herausfallende Tages-/Zeitsegmente neu zuordnen</h2>',
)
replace_once(
    "app/events_ui.py",
    '''      reassignmentSubtitle.textContent = `${families.length} ${families.length === 1 ? "Familie benötigt" : "Familien benötigen"} noch ein Ziel.`;
''',
    '''      reassignmentSubtitle.textContent = `${families.length} ${families.length === 1 ? "Dateifamilie liegt" : "Dateifamilien liegen"} in noch neu zuzuordnenden Tages-/Zeitsegmenten.`;
''',
)
replace_once(
    "app/events_ui.py",
    '''        return `<details class="card" style="padding:7px 9px"><summary style="display:flex;align-items:center;gap:8px;cursor:pointer;min-height:28px"><strong style="flex:0 0 auto">${escapeHtml(germanDay(day))}</strong><span class="muted" style="flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${items.length} Familien · ${files} Dateien${escapeHtml(timeText)}</span><input type="checkbox" data-reassign-day checked onclick="event.stopPropagation()" style="width:16px;height:16px;margin-left:auto;flex:0 0 auto"></summary><div style="display:grid;gap:4px;margin-top:6px">${items.map(f=>`<label style="display:flex;gap:8px;align-items:center;padding:4px 0"><input type="checkbox" name="reassignment_family" value="${Number(f.family_id)}" checked style="width:15px;height:15px"><span><strong>${escapeHtml(f.original_stem || f.family_key || `Familie ${f.family_id}`)}</strong> <span class="muted">· ${Number(f.file_count||0)} Dateien</span></span></label>`).join("")}</div></details>`;
''',
    '''        const ids=items.map(f=>Number(f.family_id)).join(",");
        return `<label class="card" style="display:flex;align-items:center;gap:10px;padding:10px 12px"><input type="checkbox" data-reassign-day data-family-ids="${escapeHtml(ids)}" data-day="${escapeHtml(day)}" checked style="width:18px;height:18px;flex:0 0 auto"><span style="min-width:0"><strong>${escapeHtml(germanDay(day))}${escapeHtml(timeText)}</strong><br><span class="muted">${items.length} Familien · ${files} Dateien · nur gemeinsam zuordenbar</span></span></label>`;
''',
)
replace_once(
    "app/events_ui.py",
    '''        <div class="edit-warning">Wähle die Tagessegmente bzw. Familien, die gemeinsam dasselbe Ziel bekommen. Du kannst den Vorgang wiederholen und so auf mehrere Ziele verteilen.</div>
''',
    '''        <div class="edit-warning">Wähle ganze Tages-/Zeitsegmente, die gemeinsam dasselbe Ziel bekommen. Einzelne Familien oder Dateien können hier bewusst nicht herausgepickt werden.</div>
''',
)
replace_once(
    "app/events_ui.py",
    '''      reassignmentBody.querySelectorAll('[data-reassign-day]').forEach(dayBox=>{
        const details=dayBox.closest('details');
        dayBox.onchange=()=>details?.querySelectorAll('input[name="reassignment_family"]').forEach(box=>box.checked=dayBox.checked);
        details?.querySelectorAll('input[name="reassignment_family"]').forEach(box=>box.onchange=()=>{ const all=[...details.querySelectorAll('input[name="reassignment_family"]')]; dayBox.checked=all.every(x=>x.checked); dayBox.indeterminate=!dayBox.checked&&all.some(x=>x.checked); });
      });
''',
    '''      // 0.21.2: day/time rows are atomic. No family-level controls exist.
''',
)
replace_once(
    "app/events_ui.py",
    '''        const selectedIds = [...reassignmentBody.querySelectorAll('input[name="reassignment_family"]:checked')].map(i => Number(i.value));
        if (!selectedIds.length) { document.getElementById("reassignment-message").textContent = "Bitte mindestens eine Familie auswählen."; return; }
''',
    '''        const selectedDays=[...reassignmentBody.querySelectorAll('[data-reassign-day]:checked')];
        const selectedIds=[...new Set(selectedDays.flatMap(i=>String(i.dataset.familyIds||"").split(",").filter(Boolean).map(Number)))];
        if (!selectedIds.length) { document.getElementById("reassignment-message").textContent = "Bitte mindestens ein Tages-/Zeitsegment auswählen."; return; }
''',
)

replace_once(
    "app/events_ui.py",
    '''        const options = targets.map(t => {
        const kind = t.event_kind === "no_event" ? "Ohne Ereignis" : "Ereignis";
        return `<option value="${escapeHtml(t.event_id)}" data-kind="${escapeHtml(t.event_kind)}">${escapeHtml(kind)} · ${escapeHtml(t.name)} · ${escapeHtml(t.status)}</option>`;
      }).join("");
''',
    '''      const options = targets.map(t => {
        const kind = t.event_kind === "no_event" ? "Ohne Ereignis" : "Ereignis";
        const existing=`<option value="${escapeHtml(t.event_id)}" data-kind="${escapeHtml(t.event_kind)}">${escapeHtml(kind)} · ${escapeHtml(t.name)} · ${escapeHtml(t.status)}</option>`;
        const child=t.event_kind === "event" && t.status !== "archived" ? `<option value="__child__:${escapeHtml(t.event_id)}" data-kind="new_child" data-parent-id="${escapeHtml(t.event_id)}">Neues Unterereignis in · ${escapeHtml(t.name)}</option>` : "";
        return existing+child;
      }).join("");
''',
)
replace_once(
    "app/events_ui.py",
    '''      const updateNew = () => { newWrap.hidden = target.value !== "__new__"; };
''',
    '''      const updateNew = () => { newWrap.hidden = !(target.value === "__new__" || target.selectedOptions[0]?.dataset.kind === "new_child"); };
''',
)
replace_once(
    "app/events_ui.py",
    '''        const targetMode = isNew ? "new_event" : (isNewNoEvent ? "new_no_event" : (opt.dataset.kind === "no_event" ? "existing_no_event" : "existing_event"));
''',
    '''        const isNewChild = opt.dataset.kind === "new_child";
        const targetMode = isNew ? "new_event" : (isNewNoEvent ? "new_no_event" : (isNewChild ? "new_child" : (opt.dataset.kind === "no_event" ? "existing_no_event" : "existing_event")));
''',
)
replace_once(
    "app/events_ui.py",
    '''            body:JSON.stringify({family_ids:selectedIds, target_mode:targetMode, target_event_id:(isNew||isNewNoEvent) ? null : target.value, new_event_name:isNew ? document.getElementById("reassignment-new-name").value : null})
''',
    '''            body:JSON.stringify({family_ids:selectedIds, target_mode:targetMode, target_event_id:(isNew||isNewNoEvent) ? null : (isNewChild ? opt.dataset.parentId : target.value), new_event_name:(isNew||isNewChild) ? document.getElementById("reassignment-new-name").value : null})
''',
)

# clearer durable pending state
replace_once(
    "app/events_ui.py",
    '''          <div class="reassignment-resume"><span><strong>Änderung wird abgeschlossen</strong><br><span class="muted">Die Neu-Zuordnung ist vollständig; die Nachsortierung steht noch aus.</span></span><button type="button" class="danger-button" data-cancel-mutation="${escapeHtml(event.mutation_id)}" data-job-id="${escapeHtml(event._job_id||event.job_id||"")}">Änderung verwerfen</button></div>` : "";
''',
    '''          <div class="reassignment-resume"><span><strong>⚠ Änderung noch nicht angewendet</strong><br><span class="muted">Die Neu-Zuordnung ist vollständig. Die neue Struktur ist gespeichert, aber die verifizierte Nachsortierung auf der SSD steht noch aus.</span></span><button type="button" class="danger-button" data-cancel-mutation="${escapeHtml(event.mutation_id)}" data-job-id="${escapeHtml(event._job_id||event.job_id||"")}">Änderung verwerfen</button></div>` : "";
''',
)

# ---------------------------------------------------------------------------
# Backend child-segment editing: omitted old children are deletion, missing IDs
# are new children. Retained children keep their stable IDs.
# ---------------------------------------------------------------------------
replace_once(
    "app/database.py",
    '''            current_by_id = {str(row["id"]): row for row in children}
            requested_ids_set = {str(seg.get("id") or "") for seg in multi_segments}
            if not requested_ids_set or "" in requested_ids_set or requested_ids_set != set(current_by_id):
                connection.rollback()
                raise ValueError("Die Zeitsegmente haben sich zwischenzeitlich geändert. Bitte den Editor neu öffnen.")
            normalized_segments = []
            for seg in multi_segments:
                sid = str(seg["id"])
''',
    '''            current_by_id = {str(row["id"]): row for row in children}
            supplied_ids = [str(seg.get("id") or "") for seg in multi_segments if str(seg.get("id") or "")]
            if len(supplied_ids) != len(set(supplied_ids)) or any(sid not in current_by_id for sid in supplied_ids):
                connection.rollback()
                raise ValueError("Die Zeitsegmente haben sich zwischenzeitlich geändert. Bitte den Editor neu öffnen.")
            normalized_segments = []
            for seg in multi_segments:
                sid = str(seg.get("id") or "") or ("EVENT_" + uuid.uuid4().hex.upper())
''',
)
replace_once(
    "app/database.py",
    '''            for sid,name,st,et,seg_start,seg_end,folder in normalized_segments:
                connection.execute(
                    """UPDATE events SET name=?,start_datetime=?,end_datetime=?,folder_name=?,uses_time_range=1,
                       preserve_day_folders=?,revision=revision+1,updated_at=?,edited_at=? WHERE id=? AND parent_event_id=?""",
                    (name,seg_start,seg_end,folder,int(bool(preview["preserve_day_folders"])),now,now,sid,event_id),
                )
''',
    '''            requested_segment_ids={seg[0] for seg in normalized_segments}
            for old_child in children:
                if str(old_child["id"]) not in requested_segment_ids:
                    connection.execute("DELETE FROM events WHERE id=? AND parent_event_id=?", (old_child["id"], event_id))
            for sid,name,st,et,seg_start,seg_end,folder in normalized_segments:
                if sid in current_by_id:
                    connection.execute(
                        """UPDATE events SET name=?,start_datetime=?,end_datetime=?,folder_name=?,uses_time_range=1,
                           preserve_day_folders=?,revision=revision+1,updated_at=?,edited_at=? WHERE id=? AND parent_event_id=?""",
                        (name,seg_start,seg_end,folder,int(bool(preview["preserve_day_folders"])),now,now,sid,event_id),
                    )
                else:
                    connection.execute(
                        """INSERT INTO events(id,job_id,parent_event_id,event_level,name,start_datetime,end_datetime,
                           uses_time_range,folder_name,status,created_at,updated_at,event_kind,preserve_day_folders,
                           revision,applied_at,archived_at,notes,edited_at,timeline_model)
                           VALUES (?,?,?,'child',?,?,?,1,?,?,?,?,'event',?,1,?,NULL,'',?,'continuous')""",
                        (sid,job_id,event_id,name,seg_start,seg_end,folder,
                         'applied' if is_applied else 'planned',now,now,int(bool(preview["preserve_day_folders"])),
                         now if is_applied else None,now),
                    )
''',
)

# ---------------------------------------------------------------------------
# Reassignment backend: expose exact source day/time ranges, include normal
# targets, and support existing normal events plus new child under a parent.
# ---------------------------------------------------------------------------
replace_once(
    "app/event_reassignment.py",
    '''                  AND event_kind = 'no_event'
                  AND status IN ('planned','applied','archived')
                  AND substr(start_datetime,1,7) IN ({placeholders})
''',
    '''                  AND status IN ('planned','applied','archived')
                  AND (event_kind != 'no_event' OR substr(start_datetime,1,7) IN ({placeholders}))
''',
)
replace_once(
    "app/event_reassignment.py",
    '''    target_list = []
    seen_months: set[str] = set()
    for target in target_rows:
        month_key = str(target["month_key"] or "")
        if not month_key or month_key in seen_months:
            continue
        seen_months.add(month_key)
        target_list.append({
''',
    '''    target_list = []
    seen_months: set[str] = set()
    for target in target_rows:
        month_key = str(target["month_key"] or "")
        if str(target["event_kind"]) == "no_event":
            if not month_key or month_key in seen_months:
                continue
            seen_months.add(month_key)
        target_list.append({
''',
)
replace_once(
    "app/event_reassignment.py",
    '''    return {
        "source_event": {
''',
    '''    # Canonical released ranges come from the source definition, never
    # from family min/max capture times. This is especially important after
    # deleting or shortening a timed event.
    pending_days = sorted({str(r["selected_capture_time"] or "")[:10] for r in rows if r["selected_capture_time"]})
    reassignment_time_ranges: dict[str, dict[str, str]] = {}
    with database_connection(database_path) as connection:
        if str(source["event_kind"]) == "no_event":
            defined = connection.execute(
                "SELECT day_key,start_time,end_time FROM event_time_segments WHERE event_id=? ORDER BY start_datetime,id",
                (event_id,),
            ).fetchall()
            for seg in defined:
                day=str(seg["day_key"] or "")
                if day in pending_days:
                    reassignment_time_ranges[day]={"start_time":str(seg["start_time"]),"end_time":str(seg["end_time"])}
        else:
            children = connection.execute(
                "SELECT start_datetime,end_datetime FROM events WHERE parent_event_id=? ORDER BY start_datetime,id",
                (event_id,),
            ).fetchall()
            definitions = list(children) if children else [source]
            for day in pending_days:
                day_start=f"{day}T00:00:00"; day_end=f"{day}T23:59:59"
                pieces=[]
                for definition in definitions:
                    a=max(day_start,str(definition["start_datetime"] or "")[:19])
                    b=min(day_end,str(definition["end_datetime"] or "")[:19])
                    if a <= b:
                        pieces.append((a,b))
                if pieces:
                    reassignment_time_ranges[day]={"start_time":min(a for a,_ in pieces)[11:16],"end_time":max(b for _,b in pieces)[11:16]}

    return {
        "source_event": {
''',
)
replace_once(
    "app/event_reassignment.py",
    '''        "pending_months": pending_months,
    }
''',
    '''        "pending_months": pending_months,
        "reassignment_time_ranges": reassignment_time_ranges,
    }
''',
)

# Insert helper for new child before assign_event_reassignments.
replace_once(
    "app/event_reassignment.py",
    '''def assign_event_reassignments(
''',
    '''def _create_child_in_existing_event(connection, job_id: str, target, family_ids: list[int], name: str, now: str) -> dict[str, Any]:
    clean_name=str(name or "").strip()
    if not clean_name:
        raise EventReassignmentError("Für das neue Unterereignis fehlt ein Name.")
    if str(target["job_id"]) != job_id or str(target["status"]) not in {"planned","applied"} or str(target["event_kind"]) != "event":
        raise EventReassignmentError("Dieses Ereignis kann kein neues Unterereignis aufnehmen.")
    rows=_selected_capture_rows(connection,job_id,family_ids)
    captures=[str(r["selected_capture_time"])[:19] for r in rows]
    day_keys={c[:10] for c in captures}
    if len(day_keys) != 1:
        raise EventReassignmentError("Ein neues Unterereignis wird aus genau einem Tages-/Zeitsegment erzeugt.")
    start=min(captures); end=max(captures)
    overlaps=connection.execute(
        "SELECT name,start_datetime,end_datetime FROM events WHERE parent_event_id=? AND start_datetime<=? AND end_datetime>=? ORDER BY start_datetime",
        (target["id"],end,start),
    ).fetchall()
    if overlaps:
        raise EventReassignmentError("Der Zeitbereich überschneidet sich mit einem vorhandenen Unterereignis.")
    child_id="EVENT_"+uuid.uuid4().hex.upper()
    folder=f"{start[11:16].replace(':','-')} - {end[11:16].replace(':','-')} - {clean_name}"
    connection.execute(
        """INSERT INTO events(id,job_id,parent_event_id,event_level,name,start_datetime,end_datetime,uses_time_range,
           folder_name,status,created_at,updated_at,event_kind,preserve_day_folders,revision,applied_at,archived_at,notes,timeline_model)
           VALUES (?,?,?,'child',?,?,?,1,?,?,?,?, 'event',?,1,?,NULL,'','continuous')""",
        (child_id,job_id,target["id"],clean_name,start,end,folder,target["status"],now,now,
         int(target["preserve_day_folders"] or 0), now if str(target["status"])=='applied' else None),
    )
    connection.executemany(
        "INSERT INTO event_assignments(event_id,family_id,file_id,assignment_source,created_at) VALUES (?,?,NULL,'date_time_range',?)",
        [(child_id,fid,now) for fid in family_ids],
    )
    if str(target["status"]) == "applied":
        connection.execute("UPDATE events SET resort_required=1,updated_at=? WHERE id=?",(now,target["id"]))
    return {"event_id":str(target["id"]),"child_event_id":child_id,"name":str(target["name"]),"status":str(target["status"]),
            "folder_name":str(target["folder_name"]),"preserve_day_folders":bool(target["preserve_day_folders"]),
            "linkage_kind":str(target["linkage_kind"] or ""),"linked_target_status":str(target["status"])}


def assign_event_reassignments(
''',
)

replace_once(
    "app/event_reassignment.py",
    '''    elif target_mode == "existing_event":
        raise EventReassignmentError(
            "Normale bestehende Ereignisse sind kein Ziel für eine Neu-Zuordnung. "
            "Passe stattdessen deren Zeitraum an oder erstelle ein neues Ereignis."
        )
    else:
''',
    '''    elif target_mode == "existing_event":
        if not target_event_id:
            raise EventReassignmentError("Das Zielereignis fehlt.")
        with database_connection(database_path) as connection:
            target=_root_event(connection,target_event_id)
            if target is None or str(target["job_id"]) != job_id or str(target["event_kind"]) != "event" or str(target["status"]) not in {"planned","applied"}:
                raise EventReassignmentError("Das Zielereignis ist nicht mehr verfügbar.")
            capture_rows=_selected_capture_rows(connection,job_id,selected)
            assignments=[]
            for row in capture_rows:
                cap=str(row["selected_capture_time"] or "")[:19]
                assignment_id=_assignment_event_id(connection,target,cap)
                if assignment_id == str(target["id"]):
                    children=connection.execute("SELECT COUNT(*) FROM events WHERE parent_event_id=?",(target["id"],)).fetchone()[0]
                    if int(children or 0):
                        raise EventReassignmentError("Mindestens eine Familie passt in kein vorhandenes Unterereignis. Wähle dafür „Neues Unterereignis“.")
                assignments.append((assignment_id,int(row["id"]),now))
            connection.executemany(
                "INSERT INTO event_assignments(event_id,family_id,file_id,assignment_source,created_at) VALUES (?,?,NULL,'date_time_range',?)",
                assignments,
            )
            if str(target["status"]) == "applied":
                connection.execute("UPDATE events SET resort_required=1,updated_at=? WHERE id=?",(now,target["id"]))
            target_info={"event_id":str(target["id"]),"name":str(target["name"]),"status":str(target["status"]),
                         "folder_name":str(target["folder_name"]),"preserve_day_folders":bool(target["preserve_day_folders"]),
                         "linkage_kind":str(target["linkage_kind"] or ""),"linked_target_status":str(target["status"])}
            connection.commit()
    elif target_mode == "new_child":
        if not target_event_id:
            raise EventReassignmentError("Das Oberereignis fehlt.")
        with database_connection(database_path) as connection:
            target=_root_event(connection,target_event_id)
            if target is None:
                raise EventReassignmentError("Das Oberereignis ist nicht mehr verfügbar.")
            target_info=_create_child_in_existing_event(connection,job_id,target,selected,str(new_event_name or ""),now)
            connection.commit()
    else:
''',
)

# ---------------------------------------------------------------------------
# Archived multi-child structure: store child segments in change request,
# route each file to its actual selected child folder, and rebuild children on
# completion. No time folder is invented if no child segment was requested.
# ---------------------------------------------------------------------------
replace_once(
    "app/event_change_request.py",
    '''    child_folder = str(preview.get("child_folder") or "").strip()
    preserve_day_folders = bool(preview.get("preserve_day_folders"))
''',
    '''    child_folder = str(preview.get("child_folder") or "").strip()
    child_segments = list(preview.get("child_segments") or [])
    normalized_child_segments=[]
    for segment in child_segments:
        name=str(segment.get("name") or "").strip()
        start=str(segment.get("start_time") or "")
        end=str(segment.get("end_time") or "")
        if not name or len(start)!=5 or len(end)!=5 or start>=end:
            raise EventChangeRequestError("Mindestens ein Unterereignis ist unvollständig oder ungültig.")
        normalized_child_segments.append({"id":segment.get("id"),"name":name,"start_time":start,"end_time":end,
            "folder":f"{start.replace(':','-')} - {end.replace(':','-')} - {name}"})
    normalized_child_segments.sort(key=lambda s:(s["start_time"],s["end_time"],s["name"]))
    for left,right in zip(normalized_child_segments,normalized_child_segments[1:]):
        if left["end_time"] >= right["start_time"]:
            raise EventChangeRequestError("Unterereignisse dürfen sich zeitlich nicht überschneiden.")
    preserve_day_folders = bool(preview.get("preserve_day_folders"))
''',
)
replace_once(
    "app/event_change_request.py",
    '''            parts = [year, parent_folder]
            if child_folder:
                parts.append(child_folder)
            day_key = str(row["selected_capture_time"] or "")[:10]
''',
    '''            parts = [year, parent_folder]
            capture=str(row["selected_capture_time"] or "")[:19]
            if normalized_child_segments:
                matching=[s for s in normalized_child_segments if f"{start_date}T{s['start_time']}:00" <= capture <= f"{str(preview.get('end_date') or start_date)}T{s['end_time']}:59"]
                if len(matching) != 1:
                    raise EventChangeRequestError(f"Familie {family_id} passt in kein eindeutiges Unterereignis.")
                parts.append(matching[0]["folder"])
            elif child_folder:
                parts.append(child_folder)
            day_key = str(row["selected_capture_time"] or "")[:10]
''',
)
replace_once(
    "app/event_change_request.py",
    '''    if child_folder:
        lines.append(f"    └── {child_folder}")
''',
    '''    if normalized_child_segments:
        for index,segment in enumerate(normalized_child_segments):
            connector="└──" if index == len(normalized_child_segments)-1 else "├──"
            lines.append(f"    {connector} {segment['folder']}")
    elif child_folder:
        lines.append(f"    └── {child_folder}")
''',
)
replace_once(
    "app/event_change_request.py",
    '''                no_event_segments,
                status, version, proposed_at,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
''',
    '''                no_event_segments, child_segments_json,
                status, version, proposed_at,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
''',
)
replace_once(
    "app/event_change_request.py",
    '''                json.dumps(preview.get("no_event_segments", []), ensure_ascii=False),
                "aenderbar_vorschlagen",
''',
    '''                json.dumps(preview.get("no_event_segments", []), ensure_ascii=False),
                json.dumps(normalized_child_segments, ensure_ascii=False),
                "aenderbar_vorschlagen",
''',
)

# event_change_apply: decode child segments and rebuild archived child graph.
replace_once(
    "app/event_change_apply.py",
    '''    uses_time_range = bool(cr["uses_time_range"]) if event_kind != "no_event" else False
    start_time = str(cr["start_time"] or "00:00")
''',
    '''    uses_time_range = bool(cr["uses_time_range"]) if event_kind != "no_event" else False
    try:
        child_segments = json.loads(cr.get("child_segments_json") or "[]") if event_kind == "event" else []
    except Exception as exc:
        raise EventChangeApplyError("Die gespeicherten Unterereignisse sind ungültig.") from exc
    start_time = str(cr["start_time"] or "00:00")
''',
)
replace_once(
    "app/event_change_apply.py",
    '''        elif uses_time_range:
            child_name = str(cr.get("child_event_name") or "Unterereignis")
''',
    '''        elif child_segments:
            connection.execute("DELETE FROM event_assignments WHERE event_id IN (SELECT id FROM events WHERE parent_event_id=?)",(cr["event_id"],))
            connection.execute("DELETE FROM events WHERE parent_event_id=?",(cr["event_id"],))
            created_children=[]
            for segment in child_segments:
                import uuid
                child_id="EVENT_"+uuid.uuid4().hex.upper()
                seg_start=f"{start_date}T{segment['start_time']}:00"; seg_end=f"{end_date}T{segment['end_time']}:59"
                folder=str(segment.get("folder") or f"{segment['start_time'].replace(':','-')} - {segment['end_time'].replace(':','-')} - {segment['name']}")
                connection.execute(
                    """INSERT INTO events(id,job_id,parent_event_id,event_level,name,start_datetime,end_datetime,uses_time_range,folder_name,status,created_at,updated_at,event_kind,preserve_day_folders,revision,applied_at,archived_at,notes,edited_at,timeline_model)
                       VALUES (?,?,?,'child',?,?,?,1,?,'archived',?,?,'event',?,1,?,?,'',?,'continuous')""",
                    (child_id,cr["job_id"],cr["event_id"],segment["name"],seg_start,seg_end,folder,now,now,
                     int(bool(cr["preserve_day_folders"])),event["applied_at"],event["archived_at"],now),
                )
                created_children.append((child_id,seg_start,seg_end))
            assignment_event_id=None
        elif uses_time_range:
            child_name = str(cr.get("child_event_name") or "Unterereignis")
''',
)
# Replace later assignment rebuild to support child_segments. Anchor occurs once after child selection.
replace_once(
    "app/event_change_apply.py",
    '''        connection.execute(
            "DELETE FROM event_assignments WHERE event_id = ? OR event_id IN (SELECT id FROM events WHERE parent_event_id = ?)",
            (cr["event_id"], cr["event_id"]),
        )
        connection.executemany(
            "INSERT INTO event_assignments(event_id, family_id, file_id, assignment_source, created_at) VALUES (?, ?, NULL, 'date_time_range', ?)",
            [(assignment_event_id, family_id, now) for family_id in selected_ids],
        )
''',
    '''        connection.execute(
            "DELETE FROM event_assignments WHERE event_id = ? OR event_id IN (SELECT id FROM events WHERE parent_event_id = ?)",
            (cr["event_id"], cr["event_id"]),
        )
        if child_segments:
            family_rows=connection.execute(
                "SELECT id,selected_capture_time FROM file_families WHERE job_id=? AND id IN (" + ",".join("?" for _ in selected_ids) + ")",
                (cr["job_id"],*selected_ids),
            ).fetchall()
            assignments=[]
            for family in family_rows:
                capture=str(family["selected_capture_time"] or "")[:19]
                matches=[child_id for child_id,a,b in created_children if a <= capture <= b]
                if len(matches) != 1:
                    connection.rollback(); raise EventChangeApplyError("Eine archivierte Familie passt in kein eindeutiges Unterereignis.")
                assignments.append((matches[0],int(family["id"]),now))
            connection.executemany(
                "INSERT INTO event_assignments(event_id,family_id,file_id,assignment_source,created_at) VALUES (?,?,NULL,'date_time_range',?)",
                assignments,
            )
        else:
            connection.executemany(
                "INSERT INTO event_assignments(event_id, family_id, file_id, assignment_source, created_at) VALUES (?, ?, NULL, 'date_time_range', ?)",
                [(assignment_event_id, family_id, now) for family_id in selected_ids],
            )
''',
)

# Changelog: make the patch scope explicit as implemented/in-progress baseline.
replace_once(
    "CHANGELOG.md",
    '''## [Unreleased]

### Geplant / offen
''',
    '''## [Unreleased]

### 0.21.2 – Patch in Arbeit

- normale Zeitsegmente können ergänzt und vollständig entfernt werden
- Neu-Zuordnung arbeitet auf Tages-/Zeitsegmentebene statt Familien-Drilldown
- bestehende Ereignisse und neue Unterereignisse sind Neu-Zuordnungsziele
- gespeicherte „Ohne Ereignis“-Segmente bleiben kanonische Zeitdefinition
- pending/Nachsortierung wird deutlich als noch nicht angewendet markiert
- freie Restzeiten werden sekundengenau berechnet
- archivierte Ereignisse können mehrere Unterereignisse im manuellen IST→SOLL-Auftrag abbilden
- SD-Wiederverwendung ignoriert Verwaltungsdateien und zeigt 0 neu / 0 verändert als normalen Zustand
- Archiv-E2E-Tests verwenden eine getrennte beschreibbare QA-Testbibliothek

### Weiter geplant / offen
''',
)

print("0.21.2 source patch materialized successfully")
