"""Browser wizard for planning and checking a legacy adoption."""
from html import escape
import re

from app.legacy_adoption_i18n import TRANSLATIONS, PATTERNS
from app.ui_i18n import i18n_ui_js
from app.ui_shell import apply_shell

_I18N_JS = i18n_ui_js(TRANSLATIONS, PATTERNS)


def wizard_html(library_id: str) -> str:
    html = apply_shell(_PAGE, active_area="assistant", subarea="adoption", localization_js=_I18N_JS)
    return re.sub(r'(<body\b[^>]*)(>)',
                  lambda match: match[1] + ' data-library="' + escape(library_id, quote=True) + '"' + match[2],
                  html, count=1)


_PAGE = r"""<!doctype html>
<html lang="de">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Bestandsübernahme · Bibliothekar</title>
<style>
.legacy-adoption{width:100%;max-width:1600px;margin:auto;padding:24px;box-sizing:border-box;color:var(--bk-ink)}
.legacy-adoption :is(section,fieldset){min-width:0;background:var(--bk-surface);border:1px solid var(--bk-line);border-radius:var(--bk-radius);padding:24px;margin:18px 0;box-shadow:var(--bk-shadow)}
.legacy-adoption fieldset{margin:12px 0;box-shadow:none}
.legacy-adoption legend{font-weight:700;padding:0 8px;max-width:100%;box-sizing:border-box}
.legacy-adoption h1{font-size:clamp(1.5rem,3vw,2.25rem);margin:12px 0 24px}
.legacy-adoption :is(h2,h3){margin:0 0 16px}
.legacy-adoption label{display:flex;flex-direction:column;gap:7px;min-width:0}
.legacy-adoption label:has(input[type=checkbox]){flex-direction:row;align-items:center;gap:9px;cursor:pointer}
.legacy-adoption input[type=checkbox]{width:auto;margin:0;order:-1}
.legacy-adoption :is(input,select,textarea){box-sizing:border-box;max-width:100%;min-width:0}
.legacy-adoption .inline{display:flex;gap:12px;align-items:end;flex-wrap:wrap}
.legacy-adoption .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,22rem),1fr));gap:24px}
.legacy-adoption .stack{display:grid;gap:12px}
.legacy-adoption .row{border-top:1px solid var(--bk-line);padding:12px 0}
.legacy-adoption :is(code,.paths){overflow-wrap:anywhere}
.legacy-adoption :is(small,.subtle){color:var(--bk-muted)}
.legacy-adoption :is(#message,#safety){border-left:4px solid var(--bk-yellow);padding:12px 16px;background:var(--bk-surface-2);border-radius:8px}
.legacy-adoption #message:empty{display:none}
.legacy-adoption #dirty{color:var(--bk-danger);font-weight:600}
.legacy-adoption [hidden]{display:none!important}
.legacy-adoption summary{cursor:pointer;padding:8px 0}
.legacy-adoption textarea{min-height:5rem;width:100%}
.legacy-adoption :focus-visible{outline:3px solid var(--bk-blue);outline-offset:3px}
@media(max-width:640px){.legacy-adoption{padding:12px}.legacy-adoption :is(section,fieldset){padding:16px}.legacy-adoption .inline>*{max-width:100%}}
.adoption-heading{display:flex;justify-content:space-between;align-items:start;gap:16px}
.adoption-stepper{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:20px}
.legacy-adoption :is(button:not(.day-card),summary.adoption-control){min-height:40px;padding:8px 14px;font:inherit;font-weight:650}
.legacy-adoption summary.adoption-control{display:inline-flex;align-items:center;border-radius:11px}
.legacy-adoption button:disabled{opacity:.45;cursor:not-allowed}
.adoption-planning{grid-template-columns:minmax(0,1.5fr) minmax(19rem,1fr)!important}
.legacy-adoption .adoption-month{padding:12px;box-shadow:none;margin:14px 0}
.adoption-day-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:10px;max-height:clamp(280px,62vh,640px);overflow:auto;padding:3px}
.legacy-adoption .day-card{display:grid;grid-template-columns:auto minmax(0,1fr);text-align:left;padding:14px;gap:8px;border:1px solid var(--bk-line);border-radius:15px;background:var(--bk-surface);color:var(--bk-ink);user-select:none}
.day-card .subtle{grid-column:2}
.legacy-adoption .day-card.selected{border-color:var(--bk-blue);background:color-mix(in srgb,var(--bk-blue) 16%,var(--bk-surface))}
.adoption-event-card{border:1px solid var(--bk-line);border-radius:var(--bk-radius);padding:14px;margin-bottom:12px}
.adoption-event-card summary{display:grid;gap:6px}
@media(max-width:900px){.adoption-planning{grid-template-columns:minmax(0,1fr)!important}.adoption-heading{flex-wrap:wrap}}
</style>
</head>
<body>
<main class="bk-page legacy-adoption">
<header class="adoption-heading"><div><a id="back" href="/">Zur Bibliothek</a><h1>Bestehende Fotosammlung übernehmen</h1></div><div id="top-actions"></div></header>
<nav id="wizard-steps" class="adoption-stepper" aria-label="Übernahmeschritte"></nav>
<details id="introduction" open><summary>Sicherheit und Zeitbedarf</summary>
  <p>Die Übernahme einer bestehenden Fotosammlung ist ein umfangreicher Vorgang und kann längere Zeit dauern. Abhängig von der Anzahl und Größe der Dateien können Inventur, Planung und Sicherheitsprüfung mehrere Stunden benötigen. Bitte plane ausreichend Zeit ein und führe die Übernahme möglichst ohne Zeitdruck durch.</p>
  <p>Die alte Fotosammlung und das neue Zielarchiv müssen sich auf demselben ZFS-Dataset befinden. Unterschiedliche Ordner innerhalb desselben Datasets sind zulässig. Unterschiedliche Datasets werden nicht unterstützt, auch wenn sie auf demselben ZFS-Pool liegen.</p>
  <p>Liegt deine Fotosammlung auf einem anderen Dataset, kopiere sie vor der Bestandsübernahme eigenständig auf das Dataset des Zielarchivs.</p>
</details>
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
<div id="work"></div><nav id="wizard-navigation" class="inline" aria-label="Schrittnavigation"></nav>
</main>
<script>
"use strict";
const $ = id => document.getElementById(id);
let library = document.body.dataset.library;
const currentUrl = new URL(location.href);
let jobId = currentUrl.searchParams.get("job") || "";
let job = null, draft = {}, draftRevision = 0, year = "", day = null;
let familyCursor = "", moveCursor = "", reviewCursor = "", directoryCursor = "", timer = 0, scriptTimer = 0;
let selectedSource = null;
let viewStep=currentUrl.searchParams.get("step") || "";
let selectedDays=new Set(), dayRows=[], selectionAnchor="", dayPage=60, selectedDaysJob="", draftStats=[], previewRevision=-1;
const steps=[["setup","Einrichten"],["inventory","Inventur"],["plan","Ereignisse planen"],["review","Plan prüfen"],["execution","Methode wählen"],["execute","Durchführen"],["verify","Prüfen und abschließen"]];
function allowedSteps(){
  if(!job || job.state==="discarded")return ["setup"];
  if(!job.plan.id)return job.state==="inventoried" ? ["inventory","plan"] : ["inventory"];
  if(!job.plan.execution)return ["inventory","review","execution"];
  return job.plan.state==="completed" ? ["review","verify"] : ["review","execute","verify"];
}
function rememberView(step,push=false){
  viewStep=step;
  const url=new URL(location.href);url.searchParams.set("step",step);
  history[push?"pushState":"replaceState"](null,"",url);
}
async function goStep(step){
  requireSaved();
  if(step==="plan" && job.plan.id && !job.plan.execution)await mutate("/reopen");
  if(!allowedSteps().includes(step))return;
  rememberView(step,true);await refresh();
  document.querySelector(".adoption-heading").scrollIntoView({block:"start"});
}
function navigation(){
  const allowed=allowedSteps();
  if(!allowed.includes(viewStep))rememberView(allowed.at(-1));
  $("wizard-steps").replaceChildren(...steps.map(([id,title],index)=>{
    const button=action((index+1)+". "+t(title),()=>goStep(id),id===viewStep);
    button.disabled=!allowed.includes(id);
    button.setAttribute("aria-current",id===viewStep?"step":"false");
    return button;
  }));
  const nav=$("wizard-navigation");nav.replaceChildren();
  if(!job)return;
  const previous={plan:"inventory",review:job.plan.execution?null:"plan",execution:"review",verify:job.plan.state==="completed"?null:"execute"}[viewStep];
  if(previous)nav.append(action("Zurück",()=>goStep(previous)));
  if(viewStep==="inventory" && job.state==="inventoried")nav.append(action("Weiter: Ereignisse planen",()=>goStep("plan"),true));
  if(viewStep==="plan")nav.append(action("Weiter: Plan prüfen",()=>mutate("/plan","POST",{revision:draftRevision}),true));
  if(viewStep==="review" && !job.plan.execution)nav.append(action("Weiter: Methode wählen",async()=>{
    if(!job.plan.documents_at)await mutate("/documents");
    await goStep("execution");
  },true));
  if(viewStep==="execute")nav.append(action("Weiter: Archiv prüfen",()=>goStep("verify"),true));
}
window.addEventListener("popstate",()=>{
  if(dirty.size){rememberView(viewStep);report("Speichere deine Eingaben zuerst.");return;}
  viewStep=new URL(location.href).searchParams.get("step")||"";
  refresh().catch(error=>report(error.message));
});
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
  if(selectedDaysJob!==jobId){
    selectedDaysJob=jobId;
    try{selectedDays=new Set(JSON.parse(sessionStorage.getItem("bk-adoption-days:"+jobId)||"[]").filter(day=>/^\d{4}-\d{2}-\d{2}$/.test(day)).slice(0,10000));}catch{selectedDays=new Set();}
    previewRevision=-1;
  }
  draftRevision=state.draft_revision;
  draft={events:[],capture_overrides:{},exclude_families:[],target_stems:{},...state.draft};
  let checked=null;
  if(job.state==="inventoried" && !job.plan.id && previewRevision!==draftRevision){
    checked=await api(jobPath("/draft/check"),"POST",draft);
    draftStats=checked.events;previewRevision=draftRevision;
  }
  render();
  if(checked && !checked.valid && $("event-editor"))showConflicts(checked,draft);
  if (job.scan_running) {
    timer=setTimeout(()=>refresh().catch(error=>report(error.message)),2000);
  } else if (!job.plan.id && job.state==="inventoried" && viewStep==="plan") {
    await chronology();
  } else if (job.plan.id) {
    if($("moves"))await showMoves(true);
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
    const target={"/plan":"review","/confirm":"execute","/verify":"verify","/finalize":"verify","/reopen":"plan","/scan":"inventory"}[path];
    if(target)rememberView(target);
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
  navigation();
  $("introduction").hidden=false;$("introduction").open=viewStep==="setup";
  $("setup").hidden=viewStep!=="setup";
  $("top-actions").replaceChildren();
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
  else if (!job.plan.id) buttons.append(action(job.state==="ready"?"Inventur starten":"Inventur erneut starten",async()=>{
    if(job.state!=="ready" && !confirm(t("Inventur neu starten? Der bisherige Entwurf wird verworfen. Originaldateien bleiben unverändert.")))return;
    await mutate("/scan");
  },true));
  if (!terminal && !job.plan.execution && !job.scan_running) { const discard=action("Änderungen verwerfen",async()=>{
    if (!confirm("Auftrag und Entwurf verwerfen? Originaldateien bleiben erhalten.")) return;
    await api(jobPath(),"DELETE");
    dirty.clear();
    location.href=$("back").href;
  });discard.classList.add("danger-button");$("top-actions").append(discard);}
  if (job.errors) buttons.append(action("Pfadfehler anzeigen", async()=>{
    const rows=await api(jobPath("/errors"));
    $("inventory-errors").replaceChildren(...rows.map(row=>line(row.relative_path+" · "+t(row.error))));
  }));
  status.append(buttons,slot("inventory-errors"));
  host.replaceChildren();
  if(viewStep==="inventory")host.append(status);
  else if(job.plan.id)renderPlan(host);
  else if(viewStep==="plan" && !job.scan_running && job.state==="inventoried")renderDraft(host);
}
function renderDraft(host) {
  const panel=section("Ereignisse planen");
  panel.append(line("Wähle Aufnahmetage wie im Arbeitsbereich. Klick und Strg/Cmd wählen einzelne Tage, Umschalt wählt einen Bereich. Mit Plus kannst du auch ohne Auswahl ein Ereignis anlegen."));
  const toolbar=node("div",undefined,"inline adoption-toolbar");
  const plus=node("details");plus.append(node("summary","＋ "+t("Neu"),"primary adoption-control"));
  const menu=node("div",undefined,"stack");
  const startEditor=kind=>{
    const days=[...selectedDays].sort();
    const index=kind==="child" ? draft.events.findIndex(event=>!event.existing_id && event.event_kind!=="no_event") : undefined;
    eventEditor(index===-1?undefined:index,days[0]||"",kind);
    plus.open=false;$("event-editor").scrollIntoView({block:"nearest"});
  };
  menu.append(action("Neues Ereignis",()=>startEditor("event")),action("Neues Unterereignis",()=>startEditor("child")),action("Sammelordner ohne Ereignis",()=>startEditor("no_event")));plus.append(menu);
  toolbar.append(plus,action("Alle auswählen",()=>{for(const row of dayRows)selectedDays.add(row.period);renderDays();}),action("Auswahl aufheben",()=>{selectedDays.clear();renderDays();}),slot("selection-count","span"));
  panel.append(toolbar,slot("periods"));
  const grid=node("div",undefined,"grid adoption-planning");
  const chronologyPane=node("div");chronologyPane.append(slot("days"),slot("matches"));
  const diagnostic=node("details");diagnostic.id="family-diagnostics";
  diagnostic.append(node("summary","Dateifamilien und Aufnahmezeiten prüfen"),slot("families"));
  diagnostic.addEventListener("toggle",()=>{if(diagnostic.open && !$("families").childElementCount)showFamilies().catch(error=>report(error.message));});
  chronologyPane.append(diagnostic);
  const formPane=node("div");formPane.append(node("h3","Gespeicherte Ereignisse"),slot("draft-events"),slot("event-editor"));
  grid.append(chronologyPane,formPane);panel.append(grid);host.append(panel);
  $("event-editor").hidden=true;showDraftEvents();
}
async function chronology() {
  requireSaved($("families"));
  const periods=await api(jobPath("/chronology"));
  if(!periods.some(period=>period.period===year))year=periods.find(period=>period.period)?.period || "";
  const buttons=node("div",undefined,"inline");
  for(const period of periods){
    const button=action((period.period||t("Ohne gesichertes Datum"))+" ("+period.families+")",async()=>{
      year=period.period||"";day=period.period?null:"";dayPage=60;await chronology();
    });
    button.setAttribute("aria-pressed",String(period.period===year));buttons.append(button);
  }
  $("periods").replaceChildren(buttons);$("matches").replaceChildren();$("families").replaceChildren();
  dayRows=year ? await api(jobPath("/chronology?"+new URLSearchParams({year}))) : [];
  renderDays();
  if(day!==null)await showDay();
}
function renderDays(){
  const host=$("days");if(!host)return;
  host.replaceChildren();
  const months=new Map();
  for(const item of dayRows.slice(0,dayPage)){
    const month=item.period.slice(0,7);
    if(!months.has(month)){
      const group=node("section",undefined,"adoption-month");group.append(node("h3",month));
      const cards=node("div",undefined,"adoption-day-grid");group.append(cards);months.set(month,cards);host.append(group);
    }
    const card=node("button",undefined,"day-card"+(selectedDays.has(item.period)?" selected":""));
    card.type="button";card.dataset.day=item.period;card.setAttribute("role","checkbox");
    card.setAttribute("aria-checked",String(selectedDays.has(item.period)));
    card.append(node("span",selectedDays.has(item.period)?"☑":"□"),node("strong",item.period),node("span",item.families+" "+t("Familien"),"subtle"));
    function choose(event){
      requireSaved($("families"));
      if(event.shiftKey && selectionAnchor){
        const keys=dayRows.map(row=>row.period),a=keys.indexOf(selectionAnchor),b=keys.indexOf(item.period);
        if(a>=0 && b>=0)for(const key of keys.slice(Math.min(a,b),Math.max(a,b)+1))selectedDays.add(key);
      }else if(selectedDays.has(item.period))selectedDays.delete(item.period);
      else selectedDays.add(item.period);
      selectionAnchor=item.period;day=item.period;
      renderDays();showDay().catch(error=>report(error.message));
      $("days").querySelector('[data-day="'+item.period+'"]')?.focus();
    }
    card.addEventListener("mousedown",event=>{if(event.shiftKey)event.preventDefault();});
    card.addEventListener("click",event=>{try{choose(event);}catch(error){report(error.message);}});
    card.addEventListener("keydown",event=>{
      if(!["ArrowLeft","ArrowRight","ArrowUp","ArrowDown"].includes(event.key))return;
      event.preventDefault();const cards=[...host.querySelectorAll("[data-day]")],at=cards.indexOf(card);
      const next=cards[at+(["ArrowLeft","ArrowUp"].includes(event.key)?-1:1)];
      if(next){next.focus();if(event.shiftKey)next.dispatchEvent(new MouseEvent("click",{bubbles:true,shiftKey:true}));}
    });
    months.get(month).append(card);
  }
  if(dayRows.length>dayPage)host.append(action("Weitere Tage",()=>{dayPage+=60;renderDays();}));
  sessionStorage.setItem("bk-adoption-days:"+jobId,JSON.stringify([...selectedDays]));
  $("selection-count").textContent=selectedDays.size+" "+t("Tage ausgewählt");
  showDraftEvents();
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
  if($("family-diagnostics")?.open)await showFamilies();
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
  const checked=await api(jobPath("/draft/check"),"POST",value);
  if(!checked.valid){showConflicts(checked,value,editor);throw new Error("Zeitkonflikt: Korrigiere die markierte Planung. Gespeicherte Entwürfe bleiben erhalten.");}
  const result=await api(jobPath("/draft"),"PUT",{...value,revision:draftRevision});
  draftStats=checked.events;previewRevision=result.revision;
  draft=value;
  draftRevision=result.revision;
  savedEditor(editor);
  showDraftEvents();
}
function showConflicts(checked,candidate,editor){
  $("planning-conflicts")?.remove();
  const panel=node("section");panel.id="planning-conflicts";panel.setAttribute("role","alert");
  panel.append(node("h3","Zeitkonflikte lösen"),line("Gespeicherte Entwürfe bleiben erhalten. Korrigiere den betroffenen Zeitraum oder ergänze das vorhandene Archivereignis."));
  for(const conflict of checked.conflicts){
    const proposed=candidate.events[conflict.index];
    const row=node("div",undefined,"row");
    const title=node("strong",(proposed.name||t("Sammelordner ohne Ereignis"))+" ↔ "+conflict.name);title.dataset.bkPreserveLanguage="";
    row.append(title,line(conflict.start.slice(0,10)+" → "+conflict.end.slice(0,10)));
    if(conflict.kind==="archive")row.append(action("Vorhandenes Ereignis ergänzen",async()=>{
      const events=candidate.events.filter((item,index)=>index!==conflict.index && item.existing_id!==conflict.existing_id);
      events.push({existing_id:conflict.existing_id,name:conflict.name});
      await setDraft({...candidate,events},editor);panel.remove();
      $("event-editor").replaceChildren();$("event-editor").hidden=true;
      report("Archivereignis im Entwurf gespeichert.");
    }));
    row.append(action("Zeitraum ändern",()=>{
      if(editor?.isConnected)editor.querySelector('input[type="date"],textarea')?.focus();
      else eventEditor(conflict.index);
    }));panel.append(row);
  }
  if($("event-editor"))$("event-editor").before(panel);
  else $("work").prepend(panel);
}
function showDraftEvents() {
  const el=$("draft-events");if(!el)return;
  el.replaceChildren();
  if(!draft.events.length)el.append(line("Noch keine Ereignisse geplant. Wähle Plus, um zu beginnen."));
  draft.events.forEach((item,index)=>{
    const row=node("details",undefined,"adoption-event-card");
    const kind=item.existing_id?"Archivereignis ergänzen":item.event_kind==="no_event"?"Sammelordner ohne Ereignis":"Neues Ereignis";
    const dates=item.event_kind==="no_event"?(item.segments||[]).map(segment=>segment.day_key):[item.start_date,item.end_date].filter(Boolean);
    const summary=node("summary");const title=node("strong",item.name||t(kind));title.dataset.bkPreserveLanguage="";
    summary.append(title,node("span",t(kind),"subtle"),node("span",[...new Set(dates)].join(" → "),"subtle"));
    row.append(summary);
    const matches=dayRows.filter(day=>item.event_kind==="no_event"?dates.includes(day.period):day.period>=item.start_date && day.period<=item.end_date);
    const stats=draftStats[index];
    row.append(line((stats?.days??matches.length)+" "+t("Tage")+" · "+(stats?.families??matches.reduce((sum,day)=>sum+day.families,0))+" "+t("Familien")));
    if(stats && !dates.length)row.append(line(stats.start.slice(0,10)+" → "+stats.end.slice(0,10)));
    const controls=node("div",undefined,"inline");
    if(!item.existing_id)controls.append(action("Bearbeiten",()=>eventEditor(index)));
    controls.append(action("Entfernen",async()=>{await setDraft({...draft,events:draft.events.filter((_,at)=>at!==index)});report("Entwurf entfernt.");}));
    row.append(controls);el.append(row);
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
  const state=structuredClone(saved?.layout ? saved : job.layout_default || {structure_enabled:true,input_path:"",layout:{version:2,nodes:[]}});
  state.layout=state.layout || {version:2,nodes:[]};
  const tree=node("div",undefined,"stack");
  const exported=node("select");
  const exportWrap=node("label","Exportordner");exportWrap.append(exported);
  const radioName="adoption-folder-"+crypto.randomUUID();
  function renderFolders(){
    window.BibliothekarFolderLayout.render({state,host:tree,exportSelect:exported,radioName,
      onChange:()=>{if(panel.isConnected)panel.dispatchEvent(new Event("input",{bubbles:true}));}});
  }
  custom.append(tree,action("Ordner hinzufügen",()=>{
    state.layout.nodes.push({id:window.BibliothekarFolderLayout.nodeId(),name:t("Neuer Ordner"),children:[]});
    renderFolders();
  }),exportWrap);
  function update(){custom.hidden=type.value!=="custom";if(!custom.hidden)renderFolders();}
  type.addEventListener("change",update);update();
  panel.append(select,custom);
  function value(){
    if(type.value==="inherit")return undefined;
    if(type.value==="default")return {mode:"default"};
    if(type.value==="disabled")return {structure_enabled:false,input_path:""};
    return {...structuredClone(state),structure_enabled:true};
  }
  return [panel,value];
}
function eventEditor(index, selectedDay="",newKind="event") {
  requireSaved($("event-editor"));
  const item=draft.events[index] || {};
  const form=node("fieldset");
  watchDraft(form);
  form.append(node("legend",index===undefined?"Neues Ereignis oder Sammelordner":"Entwurf bearbeiten"));
  const type=node("select");
  for (const [value,title] of [["event","Normales Ereignis"],["no_event","Sammelordner ohne Ereignis"]]) {
    const option=node("option",title);option.value=value;type.append(option);
  }
  type.value=item.event_kind || (newKind==="no_event"?"no_event":"event");
  const [nameWrap,name]=field("Ereignisname","text",item.name);
  const [startWrap,start]=field("Erster Tag","date",item.start_date || selectedDay);
  const [endWrap,end]=field("Letzter Tag","date",item.end_date || [...selectedDays].sort().at(-1) || selectedDay);
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
  if(newKind==="child")addChild();
  continuous.append(nameWrap,dates);
  if(selectedDay && selectedDays.size>1)continuous.append(line("Das Ereignis umfasst alle Aufnahmetage zwischen dem ersten und letzten Datum. Prüfe die Datumsspanne vor dem Speichern."));
  continuous.append(children,action("Unterereignis hinzufügen",()=>{addChild();markDirty(form);}));
  const segments=node("label","Ein Zeitabschnitt pro Zeile, zum Beispiel 2026-07-21 12:00 17:30. Für einen ganzen Tag reicht das Datum.");
  const text=node("textarea");
  text.value=(item.segments || []).map(segment=>[segment.day_key,segment.start_time,segment.end_time].filter(Boolean).join(" ")).join("\n");
  if (!text.value && selectedDay) text.value=([...selectedDays].sort().length?[...selectedDays].sort():[selectedDay]).join("\n");
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
      $("event-editor").replaceChildren();$("event-editor").hidden=true;
      report("Entwurf gespeichert.");
    }));
  $("event-editor").hidden=false;$("event-editor").replaceChildren(form);
}
function renderPlan(host) {
  const plan=job.plan;
  const panel=section(steps.find(([id])=>id===viewStep)?.[1]||"Durchführung und Prüfung");
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
    if (plan.documents_at && viewStep==="execution") {
      renderConfirmation(panel,command);
    }
  }
  const scripted=plan.execution?.method==="script";
  if (scripted && !completed && phase!=="rolled_back") panel.append(slot("script-state"));
  if (viewStep==="verify" && !scripted && ["manual","verifying","repair"].includes(phase)) {
    controls.append(action("Archiv prüfen",()=>run("/verify"),true));
  }
  if (phase==="repair" && !scripted) controls.append(action("Manuelle Schritte fortsetzen",()=>run("/resume")));
  if (viewStep==="verify" && ["registration_pending","registering"].includes(phase)) {
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
  const moves=node("details");moves.append(node("summary","Verschiebeplan anzeigen"),slot("moves"));
  panel.append(controls,slot("issues"),moves);
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
  try {
    if(!jobId)navigation();else $("setup").hidden=true;
    await lists(); if (jobId) await refresh();
  }
  catch(error) { report(error.message); }
})();
</script>
</body></html>"""
