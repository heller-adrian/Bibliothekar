"""Browser wizard for planning and checking a legacy adoption."""
from html import escape

from app.legacy_adoption_i18n import TRANSLATIONS, PATTERNS
from app.security import _client_code
from app.ui_i18n import i18n_ui_js

_I18N_JS = i18n_ui_js(TRANSLATIONS, PATTERNS)


def wizard_html(library_id: str) -> str:
    return (_PAGE.replace("__LIBRARY__", escape(library_id, quote=True))
            .replace("__SECURITY__", _client_code()).replace("__I18N__", _I18N_JS))


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
#safety{position:sticky;top:0;z-index:1;border-left:.25rem solid #c27b24;padding:.55rem .75rem;background:Canvas}
#dirty:not(:empty){color:#a45616;font-weight:600}
[hidden]{display:none!important}
summary{cursor:pointer}textarea{min-height:4rem;width:min(100%,35rem);box-sizing:border-box}
</style>
</head>
<body data-library="__LIBRARY__">
<main>
<nav class="inline"><a id="back" href="/">Bibliothekar</a></nav>
<h1>Bestehende Fotosammlung übernehmen</h1>
<section id="introduction">
  <p>Die Übernahme einer bestehenden Fotosammlung ist ein umfangreicher Vorgang und kann längere Zeit dauern. Abhängig von der Anzahl und Größe der Dateien können Inventur, Planung und Sicherheitsprüfung mehrere Stunden benötigen. Bitte plane ausreichend Zeit ein und führe die Übernahme möglichst ohne Zeitdruck durch.</p>
  <p>Die alte Fotosammlung und das neue Zielarchiv müssen sich auf demselben ZFS-Dataset befinden. Unterschiedliche Ordner innerhalb desselben Datasets sind zulässig. Unterschiedliche Datasets werden nicht unterstützt, auch wenn sie auf demselben ZFS-Pool liegen.</p>
  <p>Liegt deine Fotosammlung auf einem anderen Dataset, kopiere sie vor der Bestandsübernahme eigenständig auf das Dataset des Zielarchivs.</p>
</section>
<p id="safety" role="status">Bitte keine manuellen Änderungen an der alten Fotosammlung oder am Zielarchiv vornehmen. Andernfalls kann der gespeicherte Übernahmeplan ungültig werden.</p>
<div id="message" role="status" aria-live="polite"></div>
<div id="dirty" role="status" aria-live="polite"></div>
<section id="setup">
  <h2>1. Bestehende Fotosammlung auswählen</h2>
  <div class="inline">
    <label>Quellenbereich <select id="source-root"><option value="nas">NAS-Quelle</option><option value="saved">Eingebundene Sicherungen</option></select></label>
    <button type="button" id="browse">Ordner anzeigen</button>
  </div>
  <div id="source" class="stack"></div>
  <fieldset id="choose-library" hidden>
    <legend>2. Zielbibliothek auswählen oder anlegen</legend>
    <p id="chosen-source"></p>
    <div class="inline">
      <label>Zielbibliothek <select id="library"></select></label>
      <button type="button" id="start">Dataset prüfen und Inventur starten</button>
    </div>
    <details>
      <summary>Neue Bibliothek anlegen</summary>
      <label>Anzeigename <input id="new-name" type="text"></label>
      <label>Archivpfad im Container <input id="new-archive" type="text"></label>
      <label>Arbeitsordner im Container, optional <input id="new-work" type="text"></label>
      <button type="button" id="create-library">Bibliothek anlegen</button>
    </details>
  </fieldset>
  <h3 style="margin-top:1rem">Gespeicherte Aufträge</h3><div id="jobs" class="stack"></div>
</section>
<div id="work"></div>
</main>
<script>__SECURITY__</script>
<script>__I18N__</script>
<script>
"use strict";
const $ = id => document.getElementById(id);
let library = document.body.dataset.library;
const currentUrl = new URL(location.href);
let jobId = currentUrl.searchParams.get("job") || "";
let job = null, draft = {}, draftRevision = 0, year = "", day = null;
let familyCursor = "", moveCursor = "", reviewCursor = "", directoryCursor = "", timer = 0, scriptTimer = 0;
let selectedSource = null;
const base = "/api/legacy-adoption";
const dirty = new Set();
function watchDraft(editor) {
  editor.addEventListener("input", () => markDirty(editor));
}
function markDirty(editor) {
  dirty.add(editor);
  $("dirty").textContent = "Du hast ungespeicherte Eingaben.";
}
function savedEditor(editor) {
  dirty.delete(editor);
  if (!dirty.size) $("dirty").textContent = "";
}
function requireSaved(scope, except) {
  if ([...dirty].some(editor => editor !== except && (!scope || scope.contains(editor)))) {
    throw new Error("Speichere deine Eingaben zuerst.");
  }
}
window.addEventListener("beforeunload", event => {
  if (dirty.size) {
    event.preventDefault();
    event.returnValue = "";
  }
});
const labels = {
 ready:"Bereit", scanning:"Inventur", inventoried:"Inventur abgeschlossen", prepared:"Plan vorbereitet",
 manual:"Manuelle Verschiebung", verifying:"Archivprüfung läuft", repair:"Fehlerbehebung erforderlich",
 script_prepared:"Skript bereitgestellt", script_running:"Skript wird extern ausgeführt",
 script_interrupted:"Skriptausführung unterbrochen", operations_done:"Dateioperationen abgeschlossen",
 attention_required:"Fehlerbehebung erforderlich",
 registration_pending:"Registrierung ausstehend", registering:"Registrierung läuft",
 rolling_back:"Wiederherstellung läuft", rolled_back:"Wiederherstellung geprüft",
 media_verified:"Medien geprüft", verified:"Medien und Ereignisdokumente geprüft", completed:"Registriert",
 pending:"Ausstehend", duplicate:"Bereits registriert", missing:"Zieldatei fehlt", unsafe:"Unsicherer Pfad",
 size_mismatch:"Dateigröße weicht ab", sha256_mismatch:"Prüfsumme weicht ab", source_present:"Datei auch an der Quelle",
 identity_mismatch:"Die Zieldatei hat eine andere Dateiidentität als das Original"
};
function label(value) { return labels[value] || value; }
function t(value) { return window.BibliothekarI18n.t(value); }
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
  if (value?.errors?.length) return value.errors.map(item=>window.BibliothekarI18n.t(item)).join("\n");
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
    option.dataset.bkPreserveLanguage="";
    option.selected=item.library_id===library;
    return option;
  }));
  const jobs = await api(base+"/jobs");
  $("jobs").replaceChildren(...jobs.map(item => {
    const row=node("div",undefined,"inline");
    row.append(node("span",item.source_root+" · "+t(label(item.plan_state || item.state)),"paths"),
      action("Auftrag öffnen", async () => { await openJob(item.id); }));
    return row;
  }));
  if (!jobs.length) $("jobs").append(line("In dieser Bibliothek ist noch kein Auftrag gespeichert."));
}
async function browse(relative) {
  const root=$("source-root").value;
  const data=await api(base+"/source?"+new URLSearchParams({root,relative}));
  const host=$("source");
  const bar=node("div",undefined,"inline");
  bar.append(node("code",data.path));
  if (data.parent!==null) bar.append(action("Übergeordneter Ordner",()=>browse(data.parent)));
  bar.append(action("Diesen Quellordner wählen",()=>{
    selectedSource={root,relative:data.relative};
    $("chosen-source").textContent=data.path;
    $("choose-library").hidden=false;
    $("library").focus();
  },true));
  const children=node("div",undefined,"inline");
  for (const name of data.folders) {
    const folder=action(name,()=>browse([data.relative,name].filter(Boolean).join("/")));
    folder.dataset.bkPreserveLanguage="";
    children.append(folder);
  }
  host.replaceChildren(bar,children);
}
async function openJob(id) {
  requireSaved();
  jobId=id;
  year="";day=null;familyCursor="";moveCursor="";reviewCursor="";
  const url=new URL(location.href);url.searchParams.set("job",id);
  history.replaceState(null,"",url);
  await refresh();
}
async function refresh() {
  clearTimeout(timer);
  clearTimeout(scriptTimer);
  if (!jobId) return;
  const requested=jobId;
  const state=await api(jobPath());
  if (requested!==jobId) return;
  requireSaved();
  job=state;
  draftRevision=state.draft_revision;
  draft={events:[],capture_overrides:{},exclude_families:[],target_stems:{},...state.draft};
  render();
  if (job.scan_running) {
    timer=setTimeout(()=>refresh().catch(error=>report(error.message)),2000);
  } else if (!job.plan.id && job.state==="inventoried") {
    await chronology();
  } else if (job.plan.id) {
    await showMoves(true);
    if (job.plan.execution?.method==="script" && !["completed","rolled_back"].includes(job.plan.execution.phase)) {
      await pollScript();
    }
  }
}
async function mutate(path, method="POST", body) {
  requireSaved();
  report("Bibliothekar verarbeitet den Auftrag …");
  const checking=path==="/verify" || path==="/finalize";
  if (checking) $("safety").textContent="Bitte keine Dateien mehr verändern. Bibliothekar prüft und registriert gerade den übernommenen Archivbestand.";
  try {
    const result=await api(jobPath(path),method,body);
    await refresh();
    report();
    return result;
  } catch (error) {
    if (checking) await refresh().catch(()=>{});
    throw error;
  }
}
function render() {
  const phase=job.plan.execution?.phase;
  const terminal=job.state==="discarded" || job.plan.state==="completed";
  $("setup").hidden=!terminal;
  $("back").hidden=!terminal;
  $("safety").hidden=terminal;
  const warnings={
    manual:"Jetzt sind ausschließlich die im freigegebenen Plan beschriebenen manuellen Verschiebungen erlaubt.",
    rolling_back:"Führe nur die im Wiederherstellungsplan beschriebenen Rückschritte aus.",
    repair:"Bitte keine Dateien verändern. Prüfe die Abweichungen und wähle einen Weg zur Fortsetzung.",
    script:"Bitte keine zusätzlichen manuellen Dateioperationen ausführen. Das Übernahmeskript arbeitet mit dem verbindlich geprüften Plan.",
    checking:"Bitte keine Dateien mehr verändern. Bibliothekar prüft und registriert gerade den übernommenen Archivbestand."
  };
  const runningScript=job.plan.execution?.method==="script" &&
    ["script_prepared","rolling_back","repair"].includes(phase);
  $("safety").textContent=runningScript ? warnings.script : warnings[phase] || (
    ["operations_done","verifying","registration_pending","registering"].includes(phase) ? warnings.checking :
    "Bitte keine manuellen Änderungen an der alten Fotosammlung oder am Zielarchiv vornehmen. Andernfalls kann der gespeicherte Übernahmeplan ungültig werden."
  );
  const host=$("work");
  const status=section("3. Lesende Inventur");
  status.append(line(job.source_root),
    line([t(label(job.state)),job.files+" "+t("Dateien"),job.families+" "+t("Familien"),
      job.errors+" "+t("Pfadfehler")].join(" · ")));
  if (job.scan_error) status.append(line(job.scan_error));
  if (job.review_count) {
    status.append(action(job.review_count+" Prüffälle – Überprüfung erforderlich",async()=>{
      const target=$("review-cases");
      target.hidden=!target.hidden;
      if (!target.hidden) await showReview(true);
    },true));
    const cases=slot("review-cases");
    cases.hidden=true;
    status.append(cases);
  }
  const buttons=node("div",undefined,"inline");
  if (job.scan_running) buttons.append(action("Inventur pausieren",()=>mutate("/pause")));
  else if (!job.plan.id) buttons.append(action(job.state==="ready"?"Inventur starten":"Inventur erneut starten",()=>mutate("/scan")));
  if (!job.plan.execution && !job.scan_running) buttons.append(action("Änderungen verwerfen",async()=>{
    if (!confirm("Auftrag und Entwurf verwerfen? Originaldateien bleiben erhalten.")) return;
    await api(jobPath(),"DELETE");
    dirty.clear();
    location.href=$("back").href;
  }));
  if (job.errors) buttons.append(action("Pfadfehler anzeigen", async()=>{
    const rows=await api(jobPath("/errors"));
    $("inventory-errors").replaceChildren(...rows.map(row=>line(row.relative_path+" · "+t(row.error))));
  }));
  status.append(buttons,slot("inventory-errors"));
  host.replaceChildren(status);
  if (job.plan.id) renderPlan(host);
  else if (!job.scan_running && job.state==="inventoried") renderDraft(host);
}
function renderDraft(host) {
  const panel=section("4. Aufnahmezeiten und Ereignisse planen");
  panel.append(line("Wähle ein Jahr und einen Tag. Die Ereigniszeiträume bestimmen, welche bestätigten Familien in diesen Auftrag eingehen."));
  const grid=node("div",undefined,"grid");
  const chronologyPane=node("div");
  chronologyPane.append(slot("periods"),slot("days"),slot("matches"),slot("families"));
  const formPane=node("div");
  formPane.append(node("h3","Entwurf"),slot("draft-events"),slot("event-editor"));
  formPane.append(action("Verschiebeplan erstellen",()=>mutate("/plan","POST",{revision:draftRevision}),true));
  grid.append(chronologyPane,formPane);
  panel.append(grid);host.append(panel);
  showDraftEvents();eventEditor();
}
async function chronology() {
  requireSaved($("families"));
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
  requireSaved($("families"));
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
const reviewReasons={
  missing_capture_time:"Aufnahmezeit fehlt",
  conflicting_capture_time:"Aufnahmezeiten widersprechen sich",
  damaged_metadata:"Metadaten sind beschädigt",
  unreadable_member:"Mindestens eine Datei der Familie ist nicht vollständig lesbar",
  unassigned_event:"Kein geplantes Ereignis enthält die Aufnahmezeit",
  uncertain_capture_time:"Die Aufnahmezeit ist nicht ausreichend belegt"
};
const reviewStates={
  open:"Von der Archivübernahme ausgenommen",
  excluded:"Ausdrücklich ausgenommen",
  confirmed:"Aufnahmezeit im Entwurf bestätigt",
  copying:"Arbeitskopie kann fortgesetzt werden",
  copied:"Für die Metadatenkorrektur in General bereit"
};
async function showReview(reset=false) {
  const target=$("review-cases");
  if (reset) {
    reviewCursor="";
    target.replaceChildren(node("h3","Prüffälle"),line(
      "Ungeklärte Familien bleiben bei der Archivübernahme ausgenommen. Arbeitskopien in General benötigen zusätzlichen Speicherplatz und bleiben auch nach dem Verwerfen der Planung erhalten."
    ));
  }
  target.querySelector(".more")?.remove();
  const rows=await api(jobPath("/review?"+new URLSearchParams({after:reviewCursor})));
  for (const item of rows) {
    const row=node("details",undefined,"row");
    row.append(node("summary",item.family_key+" · "+t(reviewStates[item.state])));
    for (const reason of item.reasons) row.append(line(reviewReasons[reason] || reason));
    for (const file of item.files) {
      row.append(node("strong",file.relative_path.split("/").at(-1)),
        line(job.source_root+"/"+file.relative_path));
      if (file.error) row.append(line(file.error));
      if (file.metadata?.selected_capture_time) row.append(line(file.metadata.selected_capture_time));
      for (const candidate of file.metadata?.metadata_candidates || []) {
        row.append(line([candidate.technical_tag,candidate.normalized_datetime || candidate.raw_value].filter(Boolean).join(" · ")));
      }
    }
    if (item.target_relative) row.append(line("Arbeitsordner in General · "+item.target_relative));
    if (item.can_copy) row.append(action("Zur Metadatenkorrektur kopieren",async()=>{
      if (!confirm("Die vollständige Dateifamilie benötigt zusätzlichen Speicherplatz im Workspace. Jetzt nach General kopieren?")) return;
      await api(jobPath("/review/copy"),"POST",{family_key:item.family_key});
      await showReview(true);
    }));
    target.append(row);
  }
  if (rows.length===60) {
    reviewCursor=rows.at(-1).family_key;
    const more=action("Weitere Prüffälle",()=>showReview());
    more.className="more";
    target.append(more);
  }
}
async function showFamilies() {
  const target=$("families");
  target.querySelector(".more")?.remove();
  const rows=await api(jobPath("/families?"+new URLSearchParams({day,after:familyCursor})));
  for (const family of rows) {
    const row=node("details",undefined,"row");
    watchDraft(row);
    const capture=draft.capture_overrides[family.family_key] || family.selected_capture_time || "Aufnahmezeit offen";
    const excluded=draft.exclude_families.includes(family.family_key);
    const summary=node("summary",family.family_key+" · "+t(capture)+(excluded?" · "+t("Ausgeschlossen"):family.status==="review_required"?" · "+t("Prüfen"):""));
    row.append(summary);
    for (const file of family.files) {
      row.append(line(file.filename+" · "+file.media_type+" · "+file.size_bytes+" Bytes"));
      for (const candidate of file.metadata_candidates.filter(item=>item.usable)) {
        row.append(node("small",candidate.technical_tag+" · "+candidate.normalized_datetime),node("br"));
      }
    }
    for (const error of family.errors) row.append(line(error.relative_path+" · "+t(error.message)));
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
      await setDraft({...draft,capture_overrides,target_stems,exclude_families},row);
      if (![...dirty].some(editor=>$("families").contains(editor))) await showDay();
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
async function setDraft(value, editor) {
  const result=await api(jobPath("/draft"),"PUT",{...value,revision:draftRevision});
  draft=value;
  draftRevision=result.revision;
  savedEditor(editor);
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
function layoutRows(layout) {
  const result=[];
  function collect(nodes,prefix="") {
    for (const node of nodes || []) {
      const path=prefix+node.name;
      result.push({path,role:node.role});
      collect(node.children,path+"/");
    }
  }
  collect(layout?.nodes);
  return result;
}
function layoutEditor(title,saved,inherit=false) {
  const panel=node("fieldset");
  panel.append(node("legend",title));
  const type=node("select");
  const modes=[["default","Bibliotheksstandard"],["custom","Eigene Ordnerstruktur"],["disabled","Ohne zusätzliche Ordner"]];
  if (inherit) modes.unshift(["inherit","Struktur des Ereignisses übernehmen"]);
  for (const [value,text] of modes) {
    const option=node("option",text);
    option.value=value;
    type.append(option);
  }
  type.value=saved?.mode==="default" ? "default" : saved?.structure_enabled===false ? "disabled" :
    saved?.layout ? "custom" : inherit ? "inherit" : "default";
  const select=node("label","Struktur");
  select.append(type);
  const custom=node("div",undefined,"stack");
  const paths=node("textarea");
  const rows=layoutRows(saved?.layout || job.layout_default?.layout);
  paths.value=rows.map(item=>item.path).join("\n");
  const label=node("label","Ein Ordnerpfad pro Zeile, zum Beispiel Auswahl/Favoriten");
  label.append(paths);
  const [inputWrap,input]=field("Ordner für Originale, leer für das Ereignisblatt","text",
    saved?.input_path ?? job.layout_default?.input_path ?? "");
  const [exportWrap,exported]=field("Ordner für Exporte, optional","text",
    rows.find(item=>item.role==="export")?.path || "");
  custom.append(label,inputWrap,exportWrap);
  function update() { custom.hidden=type.value!=="custom"; }
  type.addEventListener("change",update);
  update();
  panel.append(select,custom);

  function value() {
    if (type.value==="inherit") return undefined;
    if (type.value==="default") return {mode:"default"};
    if (type.value==="disabled") return {structure_enabled:false,input_path:""};
    const nodes=[];
    const byPath=new Map();
    const declared=new Set();
    for (const line of paths.value.split(/\n/)) {
      const path=line.trim();
      if (!path) continue;
      if (declared.has(path)) throw new Error("Ein Ordnerpfad wurde doppelt angegeben.");
      declared.add(path);
      let parent=nodes;
      let key="";
      for (const name of path.split("/")) {
        key=key ? key+"/"+name : name;
        if (!byPath.has(key)) {
          const folder={id:"custom-"+byPath.size,name,children:[]};
          parent.push(folder);
          byPath.set(key,folder);
        }
        parent=byPath.get(key).children;
      }
    }
    const exportPath=exported.value.trim();
    if (exportPath) {
      if (!byPath.has(exportPath)) throw new Error("Der Exportordner muss in der Ordnerliste vorkommen.");
      byPath.get(exportPath).role="export";
    }
    return {structure_enabled:true,input_path:input.value.trim(),layout:{version:2,nodes}};
  }
  return [panel,value];
}
function eventEditor(index, selectedDay="") {
  requireSaved($("event-editor"));
  const item=draft.events[index] || {};
  const form=node("fieldset");
  watchDraft(form);
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
  const [folders,folderLayout]=layoutEditor("Ordnerstruktur für dieses Ereignis oder diesen Sammelordner",item.folder_layout);
  const continuous=node("div",undefined,"stack");
  const dates=node("div",undefined,"inline");dates.append(startWrap,endWrap);
  const children=node("div");
  function addChild(child={}) {
    const row=node("div",undefined,"row");
    const [nWrap,n]=field("Name des Unterereignisses","text",child.name);
    const [aWrap,a]=field("Beginn","datetime-local",child.start_datetime?.slice(0,16));
    const [bWrap,b]=field("Ende","datetime-local",child.end_datetime?.slice(0,16));
    const [folders,folderLayout]=layoutEditor("Ordnerstruktur für dieses Unterereignis",child.folder_layout,true);
    row.childValues=()=>({name:n.value,start_datetime:a.value,end_datetime:b.value,folder_layout:folderLayout()});
    const pair=node("div",undefined,"inline");pair.append(aWrap,bWrap);
    row.append(nWrap,pair,folders,action("Unterereignis entfernen",()=>{row.remove();markDirty(form);}));
    children.append(row);
  }
  for (const child of item.children || []) addChild(child);
  continuous.append(nameWrap,dates,children,action("Unterereignis hinzufügen",()=>{addChild();markDirty(form);}));
  const segments=node("label","Ein Zeitabschnitt pro Zeile, zum Beispiel 2026-07-21 12:00 17:30. Für einen ganzen Tag reicht das Datum.");
  const text=node("textarea");
  text.value=(item.segments || []).map(segment=>[segment.day_key,segment.start_time,segment.end_time].filter(Boolean).join(" ")).join("\n");
  if (!text.value && selectedDay) text.value=selectedDay;
  segments.append(text);
  function switchKind() { continuous.hidden=type.value!=="event"; segments.hidden=type.value==="event"; }
  type.addEventListener("change",switchKind);switchKind();
  form.append(type,continuous,segments,keepWrap,folders,
    action("Im Entwurf speichern",async()=>{
      const value={event_kind:type.value,preserve_day_folders:keep.checked,folder_layout:folderLayout()};
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
      await setDraft({...draft,events},form);
      eventEditor();
    }));
  $("event-editor").replaceChildren(form);
}
function renderPlan(host) {
  const plan=job.plan;
  const panel=section("5. Durchführung und Prüfung");
  const phase=plan.execution?.phase;
  const command={plan_id:plan.id};
  const run=path=>mutate(path,"POST",command);
  const completed=plan.state==="completed";
  panel.append(line(label(phase || plan.state)));
  panel.append(line([plan.dataset?.dataset, plan.move_files+" Dateien", plan.move_bytes+" Bytes"].filter(Boolean).join(" · ")));
  panel.append(node("code",plan.source_root+" → "+plan.archive_root));
  for (const [state,count] of Object.entries(plan.counts)) panel.append(node("span",t(label(state))+": "+count+"  "));
  if (!completed && phase!=="rolled_back") panel.append(line(
    "Vor größeren Dateiänderungen empfehlen wir, einen ZFS-Snapshot oder eine andere geeignete Sicherung anzulegen. Diese zusätzliche Sicherheitsmaßnahme ist freiwillig."
  ));
  const files=node("div",undefined,"inline");
  files.append(link("Verschiebeplan mit Rückwegen",jobPath("/download/manifest")));
  if (phase==="manual") {
    panel.append(line("Stelle die Ordner im Archiv über SMB bereit und verschiebe nur die aufgeführten Dateien. Sichere frühere Ereignisdokumente vor dem Ersetzen."));
    files.append(link("Leeres Ordnergerüst",jobPath("/download/folders")),
      link("Ereignisdokumente",jobPath("/download/documents")));
  }
  if (["manual","rolling_back","repair"].includes(phase)) {
    files.append(link("Frühere Ereignisdokumente",jobPath("/download/original-documents")));
  }
  panel.append(files);
  const directoryPreview=node("details");
  directoryPreview.append(node("summary","Vorschau der Zielordner"),slot("planned-directories"));
  directoryPreview.addEventListener("toggle",()=>{
    if (directoryPreview.open && !$("planned-directories").childElementCount) {
      showDirectories(true).catch(error=>report(error.message));
    }
  });
  panel.append(directoryPreview);
  if (plan.folder_moves.length && phase==="manual") {
    const groups=node("details");
    groups.append(node("summary","Tagesordner im Ganzen verschieben"));
    groups.append(line("Diese Vorschläge sind Alternativen zu den Einzeloperationen. Lasse den jeweiligen Zielordner beim Bereitstellen des Gerüsts frei. Nutze die Sammelanweisung nur, wenn sich der Quellordner seit der Inventur nicht verändert hat."));
    for (const move of plan.folder_moves) groups.append(line(
      plan.source_root+"/"+move.source_path+" → "+plan.archive_root+"/"+move.target_path+" · "+move.file_count+" Dateien"
    ));
    panel.append(groups);
  }
  const controls=node("div",undefined,"inline");
  if (!phase && !completed) {
    controls.append(
      action(plan.documents_at?"Ereignisdokumente neu vorbereiten":"Ereignisdokumente vorbereiten",()=>mutate("/documents")),
      action("Plan zur Bearbeitung öffnen",()=>mutate("/reopen")));
    if (plan.documents_at) {
      renderConfirmation(panel,command);
    }
  }
  const scripted=plan.execution?.method==="script";
  if (scripted && !completed && phase!=="rolled_back") panel.append(slot("script-state"));
  if (!scripted && ["manual","verifying","repair"].includes(phase)) {
    controls.append(action("Archiv prüfen",()=>run("/verify"),true));
  }
  if (phase==="repair" && !scripted) controls.append(action("Manuelle Schritte fortsetzen",()=>run("/resume")));
  if (["registration_pending","registering"].includes(phase)) {
    controls.append(action("Übernahme registrieren",()=>run("/finalize"),true));
  }
  if (["manual","script_prepared","operations_done","verifying","repair","registration_pending"].includes(phase)) {
    controls.append(action("Kontrollierte Wiederherstellung starten",async()=>{
      if (confirm("Möchtest du die Übernahme anhand des gespeicherten Plans rückgängig machen?")) {
        await run("/rollback/start");
      }
    }));
  }
  if (phase==="rolling_back") {
    if (!scripted) panel.append(line("Bringe verschobene Dateien über SMB an ihre ursprünglichen Pfade zurück. Stelle frühere Ereignisdokumente wieder her und entferne ausschließlich die für diesen Auftrag neu bereitgestellten Ereignisdokumente."));
    else controls.append(action("Befehl für die Skriptrücknahme bereitstellen",()=>run("/rollback/start")));
    controls.append(action("Wiederherstellung prüfen und Auftrag beenden",()=>run("/rollback/check"),true));
  }
  if (phase==="rolled_back" || completed) controls.append(link("Zur Bibliothek", $("back").href));
  if (plan.issues) controls.append(action("Prüfprobleme anzeigen",async()=>{
    const issues=await api(jobPath("/issues"));
    $("issues").replaceChildren(...issues.map(item=>line([item.relative_path,t(item.issue)].filter(Boolean).join(" · "))));
  }));
  panel.append(controls,slot("issues"),slot("moves"));
  host.append(panel);
}

function commandBox(command) {
  const area=node("textarea");
  area.readOnly=true;
  area.value=command;
  const host=node("div",undefined,"stack");
  host.append(area,action("Befehl kopieren",async()=>{
    area.select();
    if (navigator.clipboard && window.isSecureContext) await navigator.clipboard.writeText(command);
    else document.execCommand("copy");
  }));
  return host;
}
function renderConfirmation(panel,command) {
  const confirmation=node("fieldset");
  const method=node("select");
  for (const [value,title] of [["manual","Manuelle Durchführung über SMB"],["script","Skriptgestützte Durchführung auf TrueNAS"]]) {
    const option=node("option",title);
    option.value=value;
    method.append(option);
  }
  const choice=node("label","Durchführungsmethode");
  choice.append(method);
  const scripts=node("div",undefined,"stack");
  scripts.hidden=true;
  const [appWrap,appdata]=field("AppData auf dem TrueNAS-Host","text");
  const [sourceWrap,source]=field("Quellordner auf dem TrueNAS-Host","text");
  const [archiveWrap,archive]=field("Archivordner auf dem TrueNAS-Host","text");
  const proofState=node("div");
  let probe=null;
  function showProbe(result) {
    probe=result;
    proofState.replaceChildren();
    if (result.command) {
      appdata.value=result.host.package.split("/").slice(0,-2).join("/");
      source.value=result.host.source;
      archive.value=result.host.archive;
      proofState.append(line(result.verified?"Die Hostpfade sind bestätigt.":
        "Führe diesen reinen Prüfungsbefehl in der TrueNAS-Shell aus und lies danach den Nachweis ein."),
        commandBox(result.command));
    }
  }
  async function readProbe() { showProbe(await api(jobPath("/script/probe"))); }
  for (const input of [appdata,source,archive]) input.addEventListener("input",()=>{
    probe=null;
    proofState.replaceChildren();
  });
  scripts.append(
    line("Bibliothekar erstellt ein Python-Skript, das die geplanten Dateiverschiebungen auf deinem TrueNAS-System durchführen kann. Du startest dieses Skript eigenverantwortlich über die TrueNAS-Shell."),
    line("Du kannst das Skript vor der Ausführung einsehen, seinen Inhalt prüfen und es bei Bedarf mit Sicherheitssoftware untersuchen lassen. Eine automatische Sicherheitsprüfung ersetzt keine Kontrolle der tatsächlich vorgesehenen Dateioperationen."),
    line("Das Skript darf ausschließlich die zuvor bestätigten Verschiebungen innerhalb desselben ZFS-Datasets durchführen. Vorhandene Dateien dürfen nicht unkontrolliert überschrieben oder gelöscht werden."),
    link("Python-Skript ansehen",jobPath("/script/source/legacy_adoption_host.py")),
    link("Code für die Dataset-Prüfung ansehen",jobPath("/script/source/legacy_adoption_dataset.py")),
    appWrap,sourceWrap,archiveWrap,
    action("Hostpfadprüfung vorbereiten",async()=>{
      showProbe(await api(jobPath("/script/probe"),"POST",{
        ...command,appdata:appdata.value,source:source.value,archive:archive.value
      }));
    }),
    action("Hostnachweis einlesen",readProbe),
    proofState);
  method.addEventListener("change",()=>{
    scripts.hidden=method.value!=="script";
    ack.checked=false;
    if (!scripts.hidden && !probe) readProbe().catch(error=>report(error.message));
  });
  confirmation.append(node("legend","Verbindliche Sicherheitsbestätigung"),choice,scripts,
    line("Du bist dabei, die geplante Bestandsübernahme verbindlich zu starten."),
    line("Nach dieser Bestätigung kann der Übernahmeauftrag nicht mehr einfach verworfen werden. Die vorgesehenen Verschiebungen müssen abgeschlossen, überprüft oder gegebenenfalls über den vorgesehenen Wiederherstellungsweg rückgängig gemacht werden."),
    line("Bitte vergewissere dich, dass Quelle und Ziel auf demselben ZFS-Dataset liegen und während der Durchführung keine weiteren Änderungen am Archiv vorgenommen werden."),
    line("Möchtest du fortfahren?"));
  const [wrap,ack]=field("Ich bestätige die Sicherheitsbedingungen und den angezeigten Plan.","checkbox");
  confirmation.append(wrap,action("Durchführung verbindlich starten",()=>{
    if (!ack.checked) throw new Error("Bitte bestätige zuerst die Sicherheitsbedingungen.");
    if (method.value==="script" && !probe?.verified) throw new Error("Prüfe zuerst die drei tatsächlichen Hostpfade.");
    return mutate("/confirm","POST",{...command,method:method.value,acknowledged:true,probe_sha256:probe?.sha256});
  },true));
  panel.append(confirmation);
}
async function pollScript() {
  const target=$("script-state");
  const plan=job.plan;
  if (!target) return;
  const phase=plan.execution.phase;
  const run=path=>mutate(path,"POST",{plan_id:plan.id});
  try {
    const result=await api(jobPath("/script"));
    if (target!==$("script-state")) return;
    const status=result.status;
    const state=result.running ? "script_running" :
      status?.state==="running" ? "script_interrupted" :
      status?.state==="completed" ? "operations_done" : status?.state || phase;
    const nodes=[line(t(label(state))+(status?" · "+status.processed+" / "+status.total:""))];
    if (status?.error) nodes.push(line(status.error));
    if (result.command && target.dataset.command!==result.command) {
      target.dataset.command=result.command;
      target.replaceChildren(commandBox(result.command),slot("script-progress"));
    } else if (!result.command && target.dataset.command) {
      delete target.dataset.command;
      target.replaceChildren();
    }
    if (!result.running && ["script_prepared","repair"].includes(phase) && !result.command) {
      nodes.push(action("Skriptbefehl bereitstellen",()=>run("/script/release"),true));
    }
    if (!result.running && status?.state==="completed" && status.mode==="apply" &&
        ["script_prepared","operations_done","verifying","repair"].includes(phase)) {
      nodes.push(action("Archiv unabhängig prüfen",()=>run("/verify"),true));
    }
    if (!$("script-progress")) target.append(slot("script-progress"));
    $("script-progress").replaceChildren(...nodes);
  } catch (error) {
    report(error.message);
  }
  if (target===$("script-state")) scriptTimer=setTimeout(pollScript,3000);
}
async function showDirectories(reset=false) {
  const target=$("planned-directories");
  if (reset) {
    directoryCursor="";
    target.replaceChildren();
  }
  target.querySelector(".more")?.remove();
  const rows=await api(jobPath("/directories?"+new URLSearchParams({after:directoryCursor})));
  for (const path of rows) {
    const item=node("div");
    item.append(node("code",path));
    target.append(item);
  }
  if (rows.length===100) {
    directoryCursor=rows.at(-1);
    const more=action("Weitere Zielordner",()=>showDirectories());
    more.className="more";
    target.append(more);
  }
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
function selectLibrary(identifier) {
  library=identifier;
  $("back").href="/?library="+encodeURIComponent(library);
  const url=new URL(location.href);
  url.searchParams.set("library",library);
  history.replaceState(null,"",url);
}
selectLibrary(library);
$("library").addEventListener("change",()=>{
  selectLibrary($("library").value);
  lists().catch(error=>report(error.message));
});
$("browse").addEventListener("click",()=>browse("").catch(error=>report(error.message)));
$("source-root").addEventListener("change",()=>{
  selectedSource=null;
  $("choose-library").hidden=true;
  $("source").replaceChildren();
});
$("start").addEventListener("click",async()=>{
  if (!selectedSource) return;
  const button=$("start");
  button.disabled=true;
  try {
    const created=await api(base+"/jobs","POST",selectedSource);
    await openJob(created.id);
    await mutate("/scan");
  } catch (error) {
    report(error.message);
  } finally {
    button.disabled=false;
  }
});
$("create-library").addEventListener("click",async()=>{
  const button=$("create-library");
  button.disabled=true;
  try {
    const created=await api("/api/libraries","POST",{
      display_name:$("new-name").value,archive_root:$("new-archive").value,work_root:$("new-work").value
    });
    selectLibrary(created.library.library_id);
    await lists();
    $("new-name").value="";
    $("new-archive").value="";
    $("new-work").value="";
    report("Zielbibliothek angelegt.");
  } catch (error) {
    report(error.message);
  } finally {
    button.disabled=false;
  }
});
(async()=>{
  try { await lists(); if (jobId) await refresh(); }
  catch(error) { report(error.message); }
})();
</script>
</body></html>"""
