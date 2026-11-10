"""Browser wizard for planning and checking a manual legacy adoption."""
from html import escape

from app.security import _client_code


def wizard_html(library_id: str) -> str:
    return _PAGE.replace("__LIBRARY__", escape(library_id, quote=True)).replace("__SECURITY__", _client_code())


_PAGE = r"""<!doctype html>
<html lang="de">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Bestandsübernahme · Bibliothekar</title>
<style>
:root{color-scheme:light dark;font:16px/1.5 system-ui,sans-serif;--line:color-mix(in srgb,CanvasText 22%,Canvas)}
body{margin:0;background:Canvas;color:CanvasText}
main{max-width:74rem;margin:auto;padding:1.4rem}
h1,h2,h3{line-height:1.2;margin:0 0 .65rem}p{margin:.5rem 0 .85rem}
section,fieldset{border:1px solid var(--line);border-radius:.8rem;margin:1rem 0;padding:1rem}
fieldset{margin:.6rem 0;min-width:0}
button,input,select,textarea{font:inherit;color:inherit;background:Canvas;border:1px solid var(--line);border-radius:.4rem;padding:.35rem .55rem}
button{cursor:pointer}button:disabled{cursor:wait;opacity:.55}
button.primary{background:#2359a5;color:white;border-color:#2359a5}
a{color:LinkText}label{display:flex;flex-direction:column;gap:.25rem;min-width:0}
.inline{display:flex;gap:.65rem;align-items:center;flex-wrap:wrap}
.inline label:has(input[type=checkbox]){flex-direction:row}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,19rem),1fr));gap:1rem}
.stack{display:grid;gap:.6rem}
.stack>div,.row{border-top:1px solid var(--line);padding:.55rem 0}
code,.paths{overflow-wrap:anywhere}
small,.subtle{opacity:.78}
#message:not(:empty){border-left:.25rem solid #c27b24;padding:.5rem .75rem;white-space:pre-wrap}
summary{cursor:pointer}textarea{min-height:4rem;width:min(100%,35rem);box-sizing:border-box}
</style>
</head>
<body data-library="__LIBRARY__">
<main>
<nav class="inline"><a id="back" href="/">Bibliothekar</a><a id="new-library" href="/?settings=libraries">Bibliothek einrichten</a></nav>
<h1>Bestehende Fotosammlung übernehmen</h1>
<p>Bibliothekar liest die Quelle und prüft das Archiv. Verschiebe die Originale und übertrage Ereignisdokumente anschließend selbst, etwa über SMB.</p>
<div id="message" role="status" aria-live="polite"></div>
<section>
  <h2>1. Zielbibliothek und Quelle</h2>
  <div class="inline">
    <label>Zielbibliothek <select id="library"></select></label>
    <label>Quellenbereich <select id="source-root"><option value="nas">NAS-Quelle</option><option value="saved">Eingebundene Sicherungen</option></select></label>
    <button type="button" id="browse">Ordner anzeigen</button>
  </div>
  <div id="source" class="stack"></div>
  <h3 style="margin-top:1rem">Gespeicherte Aufträge</h3><div id="jobs" class="stack"></div>
</section>
<div id="work"></div>
</main>
<script>__SECURITY__</script>
<script>
"use strict";
const $ = id => document.getElementById(id);
const library = document.body.dataset.library;
const currentUrl = new URL(location.href);
let jobId = currentUrl.searchParams.get("job") || "";
let job = null, draft = {}, year = "", day = null;
let familyCursor = "", moveCursor = "", sourceRelative = "", timer = 0;
const base = "/api/legacy-adoption";
const labels = {
 ready:"Bereit", scanning:"Inventur", inventoried:"Inventur abgeschlossen", prepared:"Manuelle Schritte offen",
 media_verified:"Medien geprüft", verified:"Medien und Ereignisdokumente geprüft", completed:"Registriert",
 pending:"Ausstehend", duplicate:"Bereits registriert", missing:"Zieldatei fehlt", unsafe:"Unsicherer Pfad",
 size_mismatch:"Dateigröße weicht ab", sha256_mismatch:"Prüfsumme weicht ab", source_present:"Datei auch an der Quelle"
};
function label(value) { return labels[value] || value; }
function node(tag, content, className) {
  const el = document.createElement(tag);
  if (content !== undefined) el.textContent = content;
  if (className) el.className = className;
  return el;
}
function report(message="") { $("message").textContent = message; }
function detail(value) {
  if (typeof value === "string") return value;
  if (Array.isArray(value)) return value.map(item=>item.msg || "").join("\n");
  return "Der Vorgang konnte nicht ausgeführt werden.";
}
async function api(path, method="GET", body) {
  const headers = {"X-Bibliothekar-Library":library};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const response = await fetch(path, {method,headers,cache:"no-store",
    body:body===undefined ? undefined : JSON.stringify(body)});
  const value = await response.json();
  if (!response.ok) throw new Error(detail(value.detail));
  return value;
}
function jobPath(path="") { return base+"/jobs/"+encodeURIComponent(jobId)+path; }
function action(text, handler, primary=false) {
  const button = node("button", text, primary ? "primary" : "");
  button.type = "button";
  button.addEventListener("click", async () => {
    button.disabled = true;
    report();
    try { await handler(); } catch (error) { report(error.message); }
    finally { button.disabled = false; }
  });
  return button;
}
function field(text, type, value="") {
  const wrap = node("label", text);
  const input = node("input");
  input.type = type;
  input.value = value;
  wrap.append(input);
  return [wrap,input];
}
function section(title) { const el=node("section"); el.append(node("h2",title)); return el; }
function line(text) { return node("p",text); }
function link(text, path) {
  const el=node("a",text);
  const url=new URL(path,location.href);
  url.searchParams.set("library",library);
  el.href=url.pathname+url.search;
  return el;
}
function slot(id, type="div") {const el=node(type);el.id=id;return el;}
async function lists() {
  const data = await api("/api/libraries");
  $("library").replaceChildren(...data.libraries.map(item => {
    const option=node("option",item.display_name);
    option.value=item.library_id;
    option.selected=item.library_id===library;
    return option;
  }));
  const jobs = await api(base+"/jobs");
  $("jobs").replaceChildren(...jobs.map(item => {
    const row=node("div",undefined,"inline");
    row.append(node("span",item.source_root+" · "+label(item.plan_state || item.state),"paths"),
      action("Auftrag öffnen", async () => { await openJob(item.id); }));
    return row;
  }));
  if (!jobs.length) $("jobs").append(line("In dieser Bibliothek ist noch kein Auftrag gespeichert."));
}
async function browse(relative) {
  const root=$("source-root").value;
  const data=await api(base+"/source?"+new URLSearchParams({root,relative}));
  sourceRelative=data.relative;
  const host=$("source");
  const bar=node("div",undefined,"inline");
  bar.append(node("code",data.path));
  if (data.parent!==null) bar.append(action("Übergeordneter Ordner",()=>browse(data.parent)));
  bar.append(action("Diesen Ordner inventarisieren",async()=>{
    const created=await api(base+"/jobs","POST",{root,relative:sourceRelative});
    await openJob(created.id);
    await mutate("/scan");
  },true));
  const children=node("div",undefined,"inline");
  for (const name of data.folders) children.append(action(name,()=>browse([data.relative,name].filter(Boolean).join("/"))));
  host.replaceChildren(bar,children);
}
async function openJob(id) {
  jobId=id;
  year="";day=null;familyCursor="";moveCursor="";
  const url=new URL(location.href);url.searchParams.set("job",id);
  history.replaceState(null,"",url);
  await refresh();
}
async function refresh() {
  clearTimeout(timer);
  if (!jobId) return;
  const requested=jobId;
  const state=await api(jobPath());
  if (requested!==jobId) return;
  job=state;
  draft={events:[],capture_overrides:{},exclude_families:[],target_stems:{},...state.draft};
  render();
  if (job.scan_running) {
    timer=setTimeout(()=>refresh().catch(error=>report(error.message)),2000);
  } else if (!job.plan.id && job.state==="inventoried") {
    await chronology();
  } else if (job.plan.id) {
    await showMoves(true);
  }
}
async function mutate(path, method="POST", body) {
  report("Bibliothekar verarbeitet den Auftrag …");
  const result=await api(jobPath(path),method,body);
  await refresh();
  report();
  return result;
}
function render() {
  const host=$("work");
  const status=section("2. Lesende Inventur");
  status.append(line(job.source_root),
    line(label(job.state)+" · "+job.files+" Dateien · "+job.families+" Familien · "+job.errors+" Pfadfehler"));
  if (job.scan_error) status.append(line(job.scan_error));
  const buttons=node("div",undefined,"inline");
  if (job.scan_running) buttons.append(action("Inventur pausieren",()=>mutate("/pause")));
  else if (!job.plan.id) buttons.append(action(job.state==="ready"?"Inventur starten":"Inventur erneut starten",()=>mutate("/scan")));
  if (!job.plan.id && !job.scan_running) buttons.append(action("Auftrag verwerfen",async()=>{
    if (!confirm("Auftrag und Entwurf verwerfen? Originaldateien bleiben erhalten.")) return;
    await api(jobPath(),"DELETE");
    jobId="";const url=new URL(location.href);url.searchParams.delete("job");history.replaceState(null,"",url);
    host.replaceChildren();await lists();
  }));
  if (job.errors) buttons.append(action("Pfadfehler anzeigen", async()=>{
    const rows=await api(jobPath("/errors"));
    $("inventory-errors").replaceChildren(...rows.map(row=>line(row.relative_path+" · "+row.error)));
  }));
  status.append(buttons,slot("inventory-errors"));
  host.replaceChildren(status);
  if (job.plan.id) renderPlan(host);
  else if (!job.scan_running && job.state==="inventoried") renderDraft(host);
}
function renderDraft(host) {
  const panel=section("3. Aufnahmezeiten und Ereignisse planen");
  panel.append(line("Wähle ein Jahr und einen Tag. Die Ereigniszeiträume bestimmen, welche bestätigten Familien in diesen Auftrag eingehen."));
  const grid=node("div",undefined,"grid");
  const chronologyPane=node("div");
  chronologyPane.append(slot("periods"),slot("days"),slot("matches"),slot("families"));
  const formPane=node("div");
  formPane.append(node("h3","Entwurf"),slot("draft-events"),slot("event-editor"));
  formPane.append(action("Verschiebeplan erstellen",()=>mutate("/plan","POST",draft),true));
  grid.append(chronologyPane,formPane);
  panel.append(grid);host.append(panel);
  showDraftEvents();eventEditor();
}
async function chronology() {
  const periods=await api(jobPath("/chronology"));
  const buttons=node("div",undefined,"inline");
  for (const period of periods) {
    const text=period.period || "Ohne gesichertes Datum";
    buttons.append(action(text+" ("+period.families+")",async()=>{
      year=period.period || "";day=period.period ? null : "";await chronology();
    }));
  }
  $("periods").replaceChildren(buttons);
  $("days").replaceChildren();
  $("matches").replaceChildren();
  $("families").replaceChildren();
  if (year) {
    const days=await api(jobPath("/chronology?"+new URLSearchParams({year})));
    const row=node("div",undefined,"inline");
    for (const item of days) row.append(action(item.period+" ("+item.families+")",async()=>{
      day=item.period;await showDay();
    }));
    $("days").append(row);
  }
  if (day!==null) await showDay();
}
async function showDay() {
  $("matches").replaceChildren();
  $("families").replaceChildren();
  familyCursor="";
  if (day) {
    const matches=await api(base+"/events?"+new URLSearchParams({day}));
    for (const item of matches) {
      const row=node("div",undefined,"row");
      row.append(line(item.name+" · "+item.start_datetime.slice(0,10)+" bis "+item.end_datetime.slice(0,10)),
        action("Vorhandenes Ereignis ergänzen",async()=>{
          if (draft.events.some(event=>event.existing_id===item.id)) return;
          await setDraft({...draft,events:[...draft.events,{existing_id:item.id,name:item.name}]});
          report("Archivereignis im Entwurf gespeichert.");
        }));
      $("matches").append(row);
    }
    $("matches").append(action("Diesen Tag im Formular verwenden",()=>eventEditor(undefined,day)));
  }
  await showFamilies();
}
async function showFamilies() {
  const target=$("families");
  target.querySelector(".more")?.remove();
  const rows=await api(jobPath("/families?"+new URLSearchParams({day,after:familyCursor})));
  for (const family of rows) {
    const row=node("details",undefined,"row");
    const capture=draft.capture_overrides[family.family_key] || family.selected_capture_time || "Aufnahmezeit offen";
    const excluded=draft.exclude_families.includes(family.family_key);
    const summary=node("summary",family.family_key+" · "+capture+(excluded?" · Ausgeschlossen":family.status==="review_required"?" · Prüfen":""));
    row.append(summary);
    for (const file of family.files) {
      row.append(line(file.filename+" · "+file.media_type+" · "+file.size_bytes+" Bytes"));
      for (const candidate of file.metadata_candidates.filter(item=>item.usable)) {
        row.append(node("small",candidate.technical_tag+" · "+candidate.normalized_datetime),node("br"));
      }
    }
    for (const error of family.errors) row.append(line(error.relative_path+" · "+error.message));
    const [wrap,input]=field("Bestätigte Aufnahmezeit mit optionalem UTC-Offset","text",capture==="Aufnahmezeit offen"?"":capture);
    input.placeholder="2026-07-21T12:00:00+02:00";
    const [stemWrap,stem]=field("Neuer Dateiname für alle Mitglieder, ohne Endung (optional)","text",draft.target_stems[family.family_key]);
    const [excludeWrap,exclude]=field("Familie aus dieser Übernahme auslassen","checkbox");
    exclude.checked=excluded;
    row.append(wrap,stemWrap,excludeWrap,action("Familie im Entwurf speichern",async()=>{
      const capture_overrides={...draft.capture_overrides};
      const target_stems={...draft.target_stems};
      const exclude_families=draft.exclude_families.filter(key=>key!==family.family_key);
      if (input.value.trim() && input.value.trim() !== family.selected_capture_time) capture_overrides[family.family_key]=input.value.trim();
      else if (!input.value.trim() || family.status!=="review_required") delete capture_overrides[family.family_key];
      else capture_overrides[family.family_key]=input.value.trim();
      if (stem.value.trim()) target_stems[family.family_key]=stem.value.trim();
      else delete target_stems[family.family_key];
      if (exclude.checked) exclude_families.push(family.family_key);
      await setDraft({...draft,capture_overrides,target_stems,exclude_families});
      await showDay();
      report("Familie im Entwurf gespeichert.");
    }));
    target.append(row);
  }
  if (rows.length===60) {
    familyCursor=rows[rows.length-1].family_key;
    const more=action("Weitere Familien",showFamilies);more.className="more";
    target.append(more);
  }
}
async function setDraft(value) {
  await api(jobPath("/draft"),"PUT",value);
  draft=value;
  showDraftEvents();
}
function showDraftEvents() {
  const el=$("draft-events");
  el.replaceChildren();
  draft.events.forEach((item,index)=>{
    const row=node("div",undefined,"row");
    const title=item.existing_id ? "Ergänzung · "+(item.name || item.existing_id)
      : item.event_kind==="no_event" ? "Sammelordner · "+item.segments.map(segment=>segment.day_key).join(", ")
      : item.name+" · "+item.start_date+" bis "+item.end_date;
    row.append(line(title));
    if (!item.existing_id) row.append(action("Bearbeiten",()=>eventEditor(index)));
    row.append(action("Entfernen",()=>setDraft({...draft,events:draft.events.filter((_,at)=>at!==index)})));
    el.append(row);
  });
}
function eventEditor(index, selectedDay="") {
  const item=draft.events[index] || {};
  const form=node("fieldset");
  form.append(node("legend",index===undefined?"Neues Ereignis oder Sammelordner":"Entwurf bearbeiten"));
  const type=node("select");
  for (const [value,title] of [["event","Normales Ereignis"],["no_event","Sammelordner ohne Ereignis"]]) {
    const option=node("option",title);option.value=value;type.append(option);
  }
  type.value=item.event_kind || "event";
  const [nameWrap,name]=field("Ereignisname","text",item.name);
  const [startWrap,start]=field("Erster Tag","date",item.start_date || selectedDay);
  const [endWrap,end]=field("Letzter Tag","date",item.end_date || selectedDay);
  const [keepWrap,keep]=field("Tagesordner erhalten","checkbox");
  keep.checked=Boolean(item.preserve_day_folders);
  const [flatWrap,flat]=field("Flache Ablage im Ereignisblatt","checkbox");
  flat.checked=item.folder_layout?.structure_enabled===false;
  const continuous=node("div",undefined,"stack");
  const dates=node("div",undefined,"inline");dates.append(startWrap,endWrap);
  const children=node("div");
  function addChild(child={}) {
    const row=node("div",undefined,"row");
    const [nWrap,n]=field("Name des Unterereignisses","text",child.name);
    const [aWrap,a]=field("Beginn","datetime-local",child.start_datetime?.slice(0,16));
    const [bWrap,b]=field("Ende","datetime-local",child.end_datetime?.slice(0,16));
    row.childValues=()=>({name:n.value,start_datetime:a.value,end_datetime:b.value});
    const pair=node("div",undefined,"inline");pair.append(aWrap,bWrap);
    row.append(nWrap,pair,action("Unterereignis entfernen",()=>row.remove()));
    children.append(row);
  }
  for (const child of item.children || []) addChild(child);
  continuous.append(nameWrap,dates,children,action("Unterereignis hinzufügen",()=>addChild()));
  const segments=node("label","Ein Zeitabschnitt pro Zeile, zum Beispiel 2026-07-21 12:00 17:30. Für einen ganzen Tag reicht das Datum.");
  const text=node("textarea");
  text.value=(item.segments || []).map(segment=>[segment.day_key,segment.start_time,segment.end_time].filter(Boolean).join(" ")).join("\n");
  if (!text.value && selectedDay) text.value=selectedDay;
  segments.append(text);
  function switchKind() { continuous.hidden=type.value!=="event"; segments.hidden=type.value==="event"; }
  type.addEventListener("change",switchKind);switchKind();
  form.append(type,continuous,segments,keepWrap,flatWrap,
    action("Im Entwurf speichern",async()=>{
      const value={event_kind:type.value,preserve_day_folders:keep.checked};
      if (flat.checked) value.folder_layout={structure_enabled:false,input_path:""};
      if (type.value==="event") {
        if (!name.value.trim() || !start.value || !end.value) throw new Error("Name, Beginn und Ende fehlen.");
        Object.assign(value,{name:name.value.trim(),start_date:start.value,end_date:end.value,
          children:[...children.children].map(row=>row.childValues())});
      } else {
        value.segments=text.value.trim().split(/\n+/).filter(Boolean).map(entry=>{
          const [day_key,start_time,end_time]=entry.trim().split(/\s+/);
          return {day_key,start_time,end_time};
        });
        if (!value.segments.length) throw new Error("Mindestens ein Zeitabschnitt fehlt.");
      }
      const events=[...draft.events];
      if (index===undefined) events.push(value);else events[index]=value;
      await setDraft({...draft,events});
      eventEditor();
    }));
  $("event-editor").replaceChildren(form);
}
function renderPlan(host) {
  const plan=job.plan;
  const panel=section("3. Manuelle Verschiebung und Prüfung");
  const completed=plan.state==="completed";
  panel.append(line(label(plan.state)));
  for (const [state,count] of Object.entries(plan.counts)) panel.append(node("span",label(state)+": "+count+"  "));
  if (!completed) {
    if (plan.filesystem_warning) panel.append(line(plan.filesystem_warning));
    panel.append(line(plan.snapshot_hint),
      line("Lade zuerst das leere Ordnergerüst und den Plan. Stelle die Ordner im Archiv bereit und verschiebe nur die aufgeführten Dateien. Sichere frühere Ereignisdokumente vor dem Ersetzen."));
  }
  const files=node("div",undefined,"inline");
  files.append(link("Leeres Ordnergerüst",jobPath("/download/folders")),
    link("Verschiebeplan mit Rückwegen",jobPath("/download/manifest")));
  if (plan.documents_at) files.append(link("Ereignisdokumente",jobPath("/download/documents")),
    link("Frühere Ereignisdokumente",jobPath("/download/original-documents")));
  panel.append(files);
  if (plan.folder_moves.length && !completed) {
    const groups=node("details");
    groups.append(node("summary","Tagesordner im Ganzen verschieben"));
    groups.append(line("Diese Vorschläge sind Alternativen zu den Einzeloperationen. Lasse den jeweiligen Zielordner beim Bereitstellen des Gerüsts frei. Nutze die Sammelanweisung nur, wenn sich der Quellordner seit der Inventur nicht verändert hat."));
    for (const move of plan.folder_moves) groups.append(line(
      plan.source_root+"/"+move.source_path+" → "+plan.archive_root+"/"+move.target_path+" · "+move.file_count+" Dateien"
    ));
    panel.append(groups);
  }
  const controls=node("div",undefined,"inline");
  if (!completed) {
    controls.append(
      action(plan.documents_at?"Ereignisdokumente neu vorbereiten":"Ereignisdokumente vorbereiten",()=>mutate("/documents")),
      action("Archiv prüfen",()=>mutate("/verify"),true),
      action("Übernahme registrieren",async()=>{
        if (plan.state!=="verified") throw new Error("Medien und Ereignisdokumente müssen vollständig geprüft sein.");
        if (confirm("Geprüfte Aufnahmen und Ereignisse in dieser Bibliothek registrieren?")) {
          await mutate("/finalize","POST",{plan_id:plan.id});
        }
      }),
      action("Plan zur Bearbeitung öffnen",async()=>{
        if (confirm("Falls bereits Dateien verschoben wurden, bringe sie zuerst manuell an ihren Ausgangsort zurück. Plan jetzt prüfen und öffnen?")) {
          await mutate("/reopen");
        }
      }));
  }
  if (plan.issues) controls.append(action("Prüfprobleme anzeigen",async()=>{
    const issues=await api(jobPath("/issues"));
    $("issues").replaceChildren(...issues.map(item=>line([item.relative_path,item.issue].filter(Boolean).join(" · "))));
  }));
  panel.append(controls,slot("issues"),slot("moves"));
  host.append(panel);
}
async function showMoves(reset=false) {
  const target=$("moves");
  if (reset) { target.replaceChildren();moveCursor=""; }
  target.querySelector(".more")?.remove();
  const rows=await api(jobPath("/moves?"+new URLSearchParams({after:moveCursor})));
  for (const move of rows) {
    const row=node("div",undefined,"row paths");
    row.append(node("strong",label(move.status)),node("br"),node("code",move.source));
    if (move.target) row.append(node("br"),node("code","→ "+move.target));
    target.append(row);
  }
  if (rows.length===100) {
    moveCursor=rows[rows.length-1].relative_path;
    const more=action("Weitere Verschiebungen",()=>showMoves());more.className="more";
    target.append(more);
  }
}
$("back").href="/?library="+encodeURIComponent(library);
$("new-library").href="/?settings=libraries&library="+encodeURIComponent(library);
$("library").addEventListener("change",()=>{
  location.href="/legacy-adoption?library="+encodeURIComponent($("library").value);
});
$("browse").addEventListener("click",()=>browse("").catch(error=>report(error.message)));
$("source-root").addEventListener("change",()=>{$("source").replaceChildren();});
(async()=>{
  try { await lists(); if (jobId) await refresh(); }
  catch(error) { report(error.message); }
})();
</script>
</body></html>"""
