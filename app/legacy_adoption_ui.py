"""Browser wizard for planning and checking a legacy adoption."""
from html import escape
import re

from app.legacy_adoption_i18n import TRANSLATIONS, PATTERNS
from app.ui_i18n import i18n_ui_js
from app.ui_shell import apply_setup_shell

_I18N_JS = i18n_ui_js(TRANSLATIONS, PATTERNS)


def setup_choice_html(decision: str) -> str:
    primary = (
        '<a class="primary" href="/legacy-adoption">Bestandsübernahme fortsetzen</a>'
        if decision == "adopting"
        else '<button class="primary" type="button" data-decision="adopting">Bestehende Sammlung übernehmen</button>'
    )
    return apply_setup_shell(_CHOICE.replace("{{primary}}", primary), localization_js=_I18N_JS)


def wizard_html(library_id: str, *, later: bool = False, recovery_only: bool = False) -> str:
    html = apply_setup_shell(_PAGE, localization_js=_I18N_JS)
    return re.sub(r'(<body\b[^>]*)(>)',
                  lambda match: (match[1] + ' data-library="' + escape(library_id, quote=True) + '"'
                                 + (' data-recovery-only="true"' if recovery_only else '')
                                 + (' data-later="true"' if later else '') + match[2]),
                  html, count=1)


_CHOICE = """<!doctype html>
<html lang="de">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Ersteinrichtung · Bibliothekar</title></head>
<body>
<main class="bk-setup-choice">
<section>
<p>Hauptbibliothek einrichten</p>
<h1>Hast du eine bestehende Fotosammlung?</h1>
<p>Wenn du eine bestehende Sammlung übernehmen möchtest, lege sie vorab in einem gemeinsamen Quellordner ab. Bibliothekar erfasst auch verschachtelte Ordner und gruppiert die Aufnahmen nach Datum.</p>
<div class="bk-setup-choice-actions">
{{primary}}
<button type="button" data-decision="skipped">Mit einer leeren Bibliothek beginnen</button>
</div>
<p id="setup-status" role="status"></p>
</section>
</main>
<script>
document.querySelectorAll("[data-decision]").forEach(button=>button.addEventListener("click",async()=>{
  const buttons=document.querySelectorAll("[data-decision]");
  buttons.forEach(item=>item.disabled=true);
  try {
    const response=await fetch("/api/setup/adoption",{method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify({decision:button.dataset.decision})});
    const result=await response.json();
    if(!response.ok)throw new Error(result.detail);
    location.replace(result.next);
  } catch (error) {
    document.getElementById("setup-status").textContent=error.message;
    buttons.forEach(item=>item.disabled=false);
  }
}));
</script>
</body></html>"""


_PAGE = r"""<!doctype html>
<html lang="de">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Bestandsübernahme · Bibliothekar</title>
<style>
.legacy-adoption{width:100%;max-width:1600px;margin:auto;padding:24px;box-sizing:border-box;color:var(--bk-ink)}
.legacy-adoption section{min-width:0;background:var(--bk-surface);border:1px solid var(--bk-line);border-radius:var(--bk-radius);padding:24px;margin:18px 0;box-shadow:var(--bk-shadow)}
.legacy-adoption .adoption-card{min-width:0;border:1px solid var(--bk-line);border-radius:var(--bk-radius);padding:clamp(12px,2vw,22px);margin:12px 0}
.legacy-adoption .adoption-card>:first-child{margin-top:0}
.adoption-card h4{font-size:1rem;margin:0 0 12px}
.adoption-card .adoption-ack{align-items:start;gap:10px;margin:16px 0}
.adoption-card .adoption-ack input{flex:none;margin-top:.25em}
.adoption-proof{overflow-wrap:anywhere}
.adoption-plan-facts{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,8.5rem),1fr));gap:12px;margin:18px 0}
.adoption-plan-facts div{padding:10px 12px;background:var(--bk-surface-2);border-radius:10px;overflow-wrap:anywhere}
.adoption-plan-facts dt{font-size:.875rem;color:var(--bk-muted)}
.adoption-plan-facts dd{font-weight:650;margin:3px 0 0}
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
@media(max-width:640px){.legacy-adoption{padding:12px}.legacy-adoption section{padding:16px}.legacy-adoption .inline>*{max-width:100%}}
.adoption-heading{display:flex;justify-content:space-between;align-items:start;gap:16px}
.adoption-back{display:inline-flex;align-items:center;min-height:36px;padding:6px 12px;border:1px solid var(--bk-line);border-radius:8px;background:var(--bk-surface-2);color:var(--bk-ink);font-weight:650;text-decoration:none}
.adoption-back:hover{border-color:var(--bk-blue)}
#source-notice:empty{display:none}
.adoption-stepper{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:20px}
.legacy-adoption :is(button:not(.day-card),summary.adoption-control){min-height:40px;padding:8px 14px;font:inherit;font-weight:650}
.legacy-adoption .adoption-toolbar{align-items:center}
.legacy-adoption .adoption-toolbar :is(button,summary.adoption-control){box-sizing:border-box;min-height:36px;padding:6px 12px;font-size:.875rem;font-weight:600}
.legacy-adoption summary.adoption-control{display:inline-flex;align-items:center;border-radius:11px}
#periods:not(:empty){display:flex;flex-wrap:wrap;gap:8px;margin:16px 0 10px}
.legacy-adoption :is(input:not([type=checkbox],[type=radio]),select,textarea){min-height:38px;padding:7px 10px;background:var(--bk-surface-2);color:var(--bk-ink);border:1px solid var(--bk-line);border-radius:8px;font:inherit}
.legacy-adoption input[type=checkbox]{accent-color:var(--bk-blue)}
.legacy-adoption .adoption-command{width:100%;font: .85rem/1.4 ui-monospace,monospace;overflow-wrap:anywhere}
.legacy-adoption button:disabled{opacity:.45;cursor:not-allowed}
.adoption-planning{grid-template-columns:minmax(0,1.5fr) minmax(19rem,1fr)!important}
.legacy-adoption .adoption-month{padding:12px;box-shadow:none;margin:14px 0}
.adoption-day-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:10px;max-height:clamp(280px,62vh,640px);overflow:auto;padding:3px}
.legacy-adoption .day-card{display:grid;grid-template-columns:auto minmax(0,1fr);text-align:left;padding:14px;gap:8px;border:1px solid var(--bk-line);border-radius:15px;background:var(--bk-surface);color:var(--bk-ink);user-select:none}
.day-card .subtle{grid-column:2}
.legacy-adoption .day-card.selected{border-color:var(--bk-blue);background:color-mix(in srgb,var(--bk-blue) 16%,var(--bk-surface))}
.adoption-event-card{border:1px solid var(--bk-line);border-radius:var(--bk-radius);padding:14px;margin-bottom:12px}
.adoption-event-card summary{display:grid;gap:6px}
.legacy-adoption dialog{width:min(760px,calc(100% - 24px));max-height:calc(100% - 24px);box-sizing:border-box;padding:clamp(16px,3vw,28px);border:1px solid var(--bk-line);border-radius:var(--bk-radius);background:var(--bk-surface);color:var(--bk-ink);box-shadow:var(--bk-shadow)}
.legacy-adoption dialog::backdrop{background:rgb(5 12 18 / .65)}
.legacy-adoption dialog .inline>label{flex:1 1 10rem}
.legacy-adoption dialog [role=alert]{color:var(--bk-danger);white-space:pre-wrap}
.legacy-adoption dialog [role=alert]:empty{display:none}
.legacy-adoption dialog .editor-actions{justify-content:flex-end}
@media(max-width:900px){.adoption-planning{grid-template-columns:minmax(0,1fr)!important}.adoption-heading{flex-wrap:wrap;margin-bottom:12px}}
</style>
</head>
<body>
<main class="bk-page legacy-adoption">
<header class="adoption-heading"><div><a id="choice" class="adoption-back" href="/setup/adoption">Zur Einrichtungsentscheidung</a><h1>Bestehende Fotosammlung übernehmen</h1></div><div id="top-actions"></div></header>
<nav id="wizard-steps" class="adoption-stepper" aria-label="Übernahmeschritte"></nav>
<details id="introduction"><summary>Sicherheit und Zeitbedarf</summary>
  <p>Die Übernahme einer bestehenden Fotosammlung ist ein umfangreicher Vorgang und kann längere Zeit dauern. Abhängig von der Anzahl und Größe der Dateien können Inventur, Planung und Sicherheitsprüfung mehrere Stunden benötigen. Bitte plane ausreichend Zeit ein und führe die Übernahme möglichst ohne Zeitdruck durch.</p>
  <p>Die alte Fotosammlung und das neue Zielarchiv müssen sich auf demselben ZFS-Dataset befinden. Unterschiedliche Ordner innerhalb desselben Datasets sind zulässig. Unterschiedliche Datasets werden nicht unterstützt, auch wenn sie auf demselben ZFS-Pool liegen.</p>
  <p>Liegt deine Fotosammlung auf einem anderen Dataset, kopiere sie vor der Bestandsübernahme eigenständig auf das Dataset des Zielarchivs.</p>
</details>
<p id="safety" role="status">Bitte keine manuellen Änderungen an der alten Fotosammlung oder am Zielarchiv vornehmen. Andernfalls kann der gespeicherte Übernahmeplan ungültig werden.</p>
<div id="message" role="status" aria-live="polite"></div>
<div id="dirty" role="status" aria-live="polite"></div>
<section id="setup">
  <h2>Gemeinsamen Quellordner auswählen</h2>
  <p>Lege alle Fotos, die du übernehmen möchtest, unter einem gemeinsamen Quellordner ab. Die Inventur durchsucht seine Unterordner und gruppiert Aufnahmen anhand der Aufnahmezeit.</p>
  <div class="inline" id="source-actions" hidden>
    <label id="source-root-label" hidden>Quellenbereich <select id="source-root"></select></label>
    <button type="button" id="browse">Ordner anzeigen</button>
    <button type="button" id="pick-source" class="primary" disabled>Diesen Quellordner wählen</button>
  </div>
  <p id="source-notice" role="status"></p>
  <div id="source" class="stack"></div>
  <div id="selected-source" class="inline" hidden>
    <p id="chosen-source"></p>
    <button type="button" id="start" class="primary">Dataset prüfen und Inventur starten</button>
  </div>
</section>
<div id="work"></div><nav id="wizard-navigation" class="inline" aria-label="Schrittnavigation"></nav>
</main>
<script>
"use strict";
const $ = id => document.getElementById(id);
const library = document.body.dataset.library;
const recoveryOnly = document.body.dataset.recoveryOnly === "true";
const later = document.body.dataset.later === "true";
const librarySettings = "/?"+new URLSearchParams({library,settings:"libraries"});
const afterDiscard = later ? librarySettings : recoveryOnly ? "/" : "/setup/adoption";
const currentUrl = new URL(location.href);
let jobId = currentUrl.searchParams.get("job") || "";
$("choice").hidden = Boolean(jobId);
if(later) {
  $("choice").textContent="Zurück zu den Bibliotheken";
  $("choice").href=librarySettings;
}
let job = null, draft = {}, draftRevision = 0, year = "", day = null;
let familyCursor = "", moveCursor = "", reviewCursor = "", directoryCursor = "", timer = 0, scriptTimer = 0;
let selectedSource = null, browsedSource = null, browseVersion = 0;
let draftPage = 40;
let layoutGroup = 0;
let inventoryStarting = false;
let viewStep=currentUrl.searchParams.get("step") || "";
let selectedDays=new Set(), dayRows=[], selectionAnchor="", dayPage=60, selectedDaysJob="", draftStats=[], draftCoverage=null, previewRevision=-1;
const steps=[["setup","Einrichten"],["inventory","Inventur"],["plan","Ereignisse planen"],["review","Plan prüfen"],["execution","Methode wählen"],["execute","Durchführen"],["verify","Prüfen und abschließen"]];
function allowedSteps(){
  if(!job || job.state==="discarded")return ["setup"];
  if(recoveryOnly){
    if(!job.plan.id)return ["inventory"];
    if(!job.plan.execution)return ["inventory","review"];
    return ["review",job.plan.execution.phase==="registering"?"verify":"execute"];
  }
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
  if(step==="plan" && job?.plan.id && !job.plan.execution)await mutate("/reopen");
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
  if(!job || recoveryOnly)return;
  const previous={plan:"inventory",review:job.plan.execution?null:"plan",execution:"review",verify:job.plan.state==="completed"?null:"execute"}[viewStep];
  if(previous)nav.append(action("Zurück",()=>goStep(previous)));
  if(viewStep==="inventory" && job.state==="inventoried")nav.append(action("Weiter: Ereignisse planen",()=>goStep("plan"),true));
  if(viewStep==="plan")nav.append(action("Weiter: Plan prüfen",()=>{
    if(!draft.events.length)throw new Error("Lege mindestens ein Ereignis oder einen Sammelordner an.");
    return mutate("/plan","POST",{revision:draftRevision});
  },true));
  if(viewStep==="review" && !job.plan.execution)nav.append(action("Weiter: Methode wählen",async()=>{
    if(!job.plan.documents_at)await mutate("/documents");
    await goStep("execution");
  },true));
  if(viewStep==="execute")nav.append(action("Weiter: Archiv prüfen",()=>goStep("verify"),true));
}
window.addEventListener("bk-language-changed",()=>{
  navigation();
  if($("days"))renderDays();
  if($("draft-events"))showDraftEvents();
  if($("inventory-counts"))$("inventory-counts").textContent=inventoryCounts();
  document.querySelectorAll(".adoption-command").forEach(area=>area.setAttribute("aria-label",t("TrueNAS-Shell-Befehl")));
});
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
 pending:"Ausstehend", duplicate:"Duplikat bleibt an der Quelle", missing:"Zieldatei fehlt", unsafe:"Unsicherer Pfad",
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
function report(message="") {
  const editorMessage=document.querySelector("#event-editor[open] #editor-message");
  (editorMessage || $("message")).textContent=message;
}
function detail(value) {
  if (typeof value === "string") return value;
  if (Array.isArray(value)) return value.map(item=>{
    if(item.type==="too_long" && item.loc?.at(-1)==="events")
      return "Pro Auftrag sind bis zu "+item.ctx.max_length+" Planobjekte möglich.";
    return item.msg || "";
  }).join("\n");
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
async function setupSourceBrowser(){
  const query=later?"?mode=library":"";
  const choices=await api(base+"/sources"+query);
  const select=$("source-root");
  for(const {key} of choices.roots){
    const option=node("option",key==="nas"?"NAS-Quelle":"Eingebundene Sicherungen");
    option.value=key;select.append(option);
  }
  if(!choices.preferred){
    $("source-notice").textContent="Binde einen NAS-Quellordner auf dem Dataset des Zielarchivs schreibgeschützt ein.";
    return;
  }
  select.value=choices.preferred;
  $("source-root-label").hidden=choices.roots.length<2;
  $("source-actions").hidden=false;
  await browse("");
}
async function browse(relative) {
  const version=++browseVersion;
  const root=$("source-root").value;
  const query=new URLSearchParams({root,relative});
  if(later)query.set("mode","library");
  browsedSource=null;selectedSource=null;
  $("selected-source").hidden=true;
  $("pick-source").disabled=true;
  const data=await api(base+"/source?"+query);
  if(version!==browseVersion)return;
  browsedSource={root,...data};
  $("pick-source").disabled=!data.dataset;
  $("source-notice").textContent=data.reason || (data.read_only?"":"Die Quell-Einbindung ist nicht schreibgeschützt.");
  const bar=node("div",undefined,"inline");
  const path=node("code",data.path);path.dataset.bkPreserveLanguage="";bar.append(path);
  if(data.dataset){
    const dataset=node("span",data.dataset,"subtle");dataset.dataset.bkPreserveLanguage="";
    bar.append(node("strong","ZFS-Dataset"),dataset);
  }
  if(data.parent!==null)bar.append(action("Übergeordneter Ordner",()=>browse(data.parent)));
  const children=node("div",undefined,"inline");
  for(const name of data.folders){
    const folder=action(name,()=>browse([data.relative,name].filter(Boolean).join("/")));
    folder.dataset.bkPreserveLanguage="";
    children.append(folder);
  }
  $("source").replaceChildren(bar,children);
}
function openJob(id) {
  requireSaved();
  jobId=id;
  year="";day=null;familyCursor="";moveCursor="";reviewCursor="";draftPage=40;
  const url=new URL(location.href);
  url.searchParams.set("job",id);
  url.searchParams.set("library",library);
  history.replaceState(null,"",url);
}
function inventoryProgress(){
  const status=node("p","Fotosammlung wird gelesen …","bk-loading-status");
  status.setAttribute("role","status");
  return status;
}
async function startInventory(){
  if(inventoryStarting)return;
  inventoryStarting=true;
  rememberView("inventory");
  if(job)render();
  else{
    $("setup").hidden=true;
    $("choice").hidden=true;
    $("work").replaceChildren(inventoryProgress());
  }
  try{await api(jobPath("/scan"),"POST");}
  finally{inventoryStarting=false;await refresh();}
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
    draftCoverage=null;previewRevision=-1;
  }
  draftRevision=state.draft_revision;
  draft={events:[],capture_overrides:{},exclude_families:[],target_stems:{},...state.draft};
  let checked=null;
  if(!recoveryOnly && job.state==="inventoried" && !job.plan.id && previewRevision!==draftRevision){
    checked=await api(jobPath("/draft/check"),"POST",draft);
    draftStats=checked.events;draftCoverage=checked.coverage;previewRevision=draftRevision;
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
    if(path==="/finalize" && result.state==="completed") {
      location.replace("/?"+new URLSearchParams({library}));
      return result;
    }
    if(path==="/rollback/check" && result.execution?.phase==="rolled_back") {
      location.replace(afterDiscard);
      return result;
    }
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
function reviewControls(){
  const details=node("details");
  const cases=slot("review-cases");
  details.append(node("summary",job.review_count+" Prüffälle – Überprüfung erforderlich"),cases);
  details.addEventListener("toggle",()=>{
    if(details.open && !cases.childElementCount)showReview(true).catch(error=>report(error.message));
  });
  return details;
}
function inventoryCounts() {
  const phase=job.state==="scanning" && !job.scan_running && !inventoryStarting?"Inventur unterbrochen":label(job.state);
  return [t(phase),job.files+" "+t("Dateien"),job.families+" "+t("Familien"),
    job.errors+" "+t("Pfadfehler")].join(" · ");
}
function render() {
  const phase=job.plan.execution?.phase;
  const terminal=job.state==="discarded" || job.plan.state==="completed";
  navigation();
  $("introduction").hidden=false;
  $("setup").hidden=viewStep!=="setup";
  $("top-actions").replaceChildren();
  $("choice").hidden=true;
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
  if(recoveryOnly)$("safety").textContent="Dieser Auftrag stammt aus einer älteren Version. Prüfe den gespeicherten Stand und verwirf den Entwurf oder verwende die angezeigte Wiederherstellung.";
  const host=$("work");
  const status=section("Lesende Inventur");
  const counts=line(inventoryCounts());
  counts.id="inventory-counts";
  status.append(line(job.source_root));
  if(job.scan_running || inventoryStarting)status.append(inventoryProgress());
  counts.setAttribute("aria-live","polite");
  status.append(counts);
  if (job.scan_error) status.append(line(job.scan_error));
  if(job.review_count)status.append(reviewControls());
  const buttons=node("div",undefined,"inline");
  if (!recoveryOnly && job.scan_running) buttons.append(action("Inventur pausieren",()=>mutate("/pause")));
  else if (!recoveryOnly && !terminal && !job.plan.id && !inventoryStarting) {
    const labels={ready:"Inventur starten",scanning:"Inventur fortsetzen",inventoried:"Inventur erneut starten"};
    buttons.append(action(labels[job.state],async()=>{
      if(job.state==="inventoried" && !confirm(t("Inventur neu starten? Der bisherige Entwurf wird verworfen. Originaldateien bleiben unverändert.")))return;
      await startInventory();
    },true));
  }
  if (!terminal && !job.plan.execution && !job.scan_running && !inventoryStarting) { const discard=action("Änderungen verwerfen",async()=>{
    if (!confirm("Auftrag und Entwurf verwerfen? Originaldateien bleiben erhalten.")) return;
    await api(jobPath(),"DELETE");
    dirty.clear();
    location.replace(afterDiscard);
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
  panel.append(line("Wähle Aufnahmetage wie im Arbeitsbereich. Klick und Strg/Cmd wählen einzelne Tage, Umschalt wählt einen Bereich. Du kannst auch ohne ausgewählte Tage planen."));
  const toolbar=node("div",undefined,"inline adoption-toolbar");
  toolbar.append(
    action("+ Ereignis",()=>eventEditor(undefined,"event"),true),
    action("+ Sammelordner ohne Ereignis",()=>eventEditor(undefined,"no_event")),
    action("Alle auswählen",()=>{for(const row of dayRows)selectedDays.add(row.period);renderDays();}),
    action("Auswahl aufheben",()=>{selectedDays.clear();renderDays();}),
    slot("selection-count","span"));
  panel.append(toolbar,slot("periods"));
  const grid=node("div",undefined,"grid adoption-planning");
  const chronologyPane=node("div");chronologyPane.append(slot("days"),slot("matches"));
  const diagnostic=node("details");diagnostic.id="family-diagnostics";
  diagnostic.append(node("summary","Dateifamilien und Aufnahmezeiten prüfen"),slot("families"));
  diagnostic.addEventListener("toggle",()=>{if(diagnostic.open && !$("families").childElementCount)showFamilies().catch(error=>report(error.message));});
  chronologyPane.append(diagnostic);
  const formPane=node("div");
  formPane.append(node("h3","Gespeicherte Planobjekte"),slot("draft-coverage"),slot("draft-events"));
  const editor=slot("event-editor","dialog");
  editor.setAttribute("aria-labelledby","event-editor-title");
  grid.append(chronologyPane,formPane);panel.append(grid,editor);host.append(panel);
  showDraftEvents();
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
    card.append(node("span",selectedDays.has(item.period)?"☑":"□"),node("strong",item.period),node("span",item.families+" "+t(item.families===1?"Dateifamilie":"Familien"),"subtle"));
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
  $("selection-count").textContent=selectedDays.size+" "+t(selectedDays.size===1?"Tag ausgewählt":"Tage ausgewählt");
}
async function showDay() {
  requireSaved($("families"));
  $("matches").replaceChildren();
  $("families").replaceChildren();
  familyCursor="";
  if (day) {
    const requestedDay=day;
    if(later) {
      const matches=await api(jobPath("/events?"+new URLSearchParams({day:requestedDay})));
      if(day!==requestedDay || !$("matches"))return;
      for(const item of matches) {
        const card=node("div",undefined,"row");
        const title=node("strong",item.name);title.dataset.bkPreserveLanguage="";
        card.append(title,line(item.start_datetime.slice(0,10)+" → "+item.end_datetime.slice(0,10)),
          action("Zu bestehendem Ereignis hinzufügen",()=>addExisting(item)));
        $("matches").append(card);
      }
    }
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
    if (!recoveryOnly && item.can_copy) row.append(action("Zur Metadatenkorrektur kopieren",async()=>{
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
  draftStats=checked.events;draftCoverage=checked.coverage;previewRevision=result.revision;
  draft=value;
  draftRevision=result.revision;
  savedEditor(editor);
  showDraftEvents();
}
async function addExisting(item, candidate=draft, replaceAt=null, editor=null) {
  const events=candidate.events.filter((event,index)=>event.existing_id!==item.id && index!==replaceAt);
  events.push({existing_id:item.id,name:item.name});
  await setDraft({...candidate,events},editor);
  $("planning-conflicts")?.remove();
  if(editor) $("event-editor").close();
  report("Aufnahmen innerhalb des gespeicherten Zeitraums zugeordnet.");
}
function showConflicts(checked,candidate,editor){
  $("planning-conflicts")?.remove();
  const panel=node("section");panel.id="planning-conflicts";panel.setAttribute("role","alert");
  panel.append(node("h3","Zeitkonflikte lösen"),line("Gespeicherte Entwürfe bleiben erhalten. Korrigiere den betroffenen Zeitraum."));
  for(const conflict of checked.conflicts){
    const proposed=candidate.events[conflict.index];
    const row=node("div",undefined,"row");
    const title=node("strong",(proposed.name||t("Sammelordner ohne Ereignis"))+" ↔ "+conflict.name);title.dataset.bkPreserveLanguage="";
    row.append(title,line(conflict.start.slice(0,10)+" → "+conflict.end.slice(0,10)));
    if(later && conflict.kind==="archive")row.append(action("Zu bestehendem Ereignis hinzufügen",()=>addExisting({
      id:conflict.existing_id,name:conflict.name,
    },candidate,conflict.index,editor)));
    row.append(action("Zeitraum ändern",()=>{
      if(editor?.isConnected)editor.querySelector('input[type="date"],textarea')?.focus();
      else eventEditor(conflict.index);
    }));panel.append(row);
  }
  if(editor?.isConnected) editor.prepend(panel);
  else if($("event-editor")) $("event-editor").before(panel);
  else $("work").prepend(panel);
}
function showDraftEvents() {
  const el=$("draft-events");if(!el)return;
  el.replaceChildren();
  const coverage=$("draft-coverage");
  coverage.replaceChildren();
  if(draft.events.length)coverage.append(line("Alle gespeicherten Planobjekte fließen in den Verschiebeplan ein."));
  if(draftCoverage?.unassigned){
    const message=draftCoverage.unassigned===1?"Eine Dateifamilie ist noch nicht zugeordnet.":
      draftCoverage.unassigned+" Dateifamilien sind noch nicht zugeordnet.";
    const hint=node("p",message,"subtle");
    coverage.append(hint,line("Ordne diese Aufnahmen zu oder prüfe sie im nächsten Schritt. Ohne Zuordnung bleiben sie an der Quelle."));
    if(draftCoverage.unassigned_days.length)coverage.append(node("p",draftCoverage.unassigned_days.join(" · "),"subtle"));
  }
  if(!draft.events.length)el.append(line("Lege mindestens ein Ereignis oder einen Sammelordner an."));
  draft.events.slice(0,draftPage).forEach((item,index)=>{
    const row=node("details",undefined,"adoption-event-card");
    const kind=item.existing_id?"Archivereignis ergänzen":item.event_kind==="no_event"?"Sammelordner ohne Ereignis":"Neues Ereignis";
    const dates=item.event_kind==="no_event"?(item.segments||[]).map(segment=>segment.day_key):[item.start_date,item.end_date].filter(Boolean);
    const summary=node("summary");const title=node("strong",item.name||kind);
    if(item.name)title.dataset.bkPreserveLanguage="";
    summary.append(title);
    if(item.name)summary.append(node("span",kind,"subtle"));
    if(dates.length)summary.append(node("span",[...new Set(dates)].join(" → "),"subtle"));
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
  if(draftPage<draft.events.length)el.append(action("Weitere Planobjekte",()=>{draftPage+=40;showDraftEvents();}));
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
  const panel=node("div",undefined,"adoption-card");
  panel.append(node("h4",title));
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
  // Radio groups only need to be unique within this page, including over LAN HTTP.
  const radioName="adoption-folder-"+(++layoutGroup);
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
function eventEditor(index, newKind="event") {
  requireSaved($("event-editor"));
  const dialog=$("event-editor");
  const item=draft.events[index] || {};
  const kind=item.event_kind || newKind;
  const isEvent=kind==="event";
  const days=index===undefined?[...selectedDays].sort():[];
  const form=node("div",undefined,"stack");
  watchDraft(form);
  const title=node("h3",index===undefined?(isEvent?"Neues Ereignis":"Sammelordner ohne Ereignis"):"Entwurf bearbeiten");
  title.id="event-editor-title";
  const message=node("p");message.id="editor-message";message.setAttribute("role","alert");
  form.append(title,message);
  const [keepWrap,keep]=field("Tagesordner erhalten","checkbox");
  keep.checked=Boolean(item.preserve_day_folders);
  const [folders,folderLayout]=layoutEditor("Ordnerstruktur",item.folder_layout);
  let firstInput, fields;

  if(isEvent){
    const [nameWrap,name]=field("Ereignisname","text",item.name);
    const [startWrap,start]=field("Erster Tag","date",item.start_date || days[0]);
    const [endWrap,end]=field("Letzter Tag","date",item.end_date || days.at(-1));
    const dates=node("div",undefined,"inline");dates.append(startWrap,endWrap);
    form.append(nameWrap,dates);
    firstInput=name;
    if(days.length>1)form.append(line("Das Ereignis umfasst alle Aufnahmetage zwischen dem ersten und letzten Datum. Prüfe die Datumsspanne vor dem Speichern."));
    const children=node("div");
    function addChild(child={}) {
      const row=node("div",undefined,"adoption-card stack");
      const [nWrap,n]=field("Name des Unterereignisses","text",child.name);
      const [aWrap,a]=field("Beginn","datetime-local",child.start_datetime?.slice(0,16));
      const [bWrap,b]=field("Ende","datetime-local",child.end_datetime?.slice(0,16));
      const [childFolders,childLayout]=layoutEditor("Ordnerstruktur für dieses Unterereignis",child.folder_layout,true);
      row.childValues=()=>({name:n.value,start_datetime:a.value,end_datetime:b.value,folder_layout:childLayout()});
      const pair=node("div",undefined,"inline");pair.append(aWrap,bWrap);
      row.append(nWrap,pair,childFolders,action("Unterereignis entfernen",()=>{row.remove();markDirty(form);}));
      children.append(row);
      return n;
    }
    for(const child of item.children || [])addChild(child);
    form.append(children,action("Unterereignis hinzufügen",()=>{addChild().focus();markDirty(form);}));
    fields=()=>{
      if(!name.value.trim() || !start.value || !end.value)throw new Error("Name, Beginn und Ende fehlen.");
      return {name:name.value.trim(),start_date:start.value,end_date:end.value,
        children:[...children.children].map(row=>row.childValues())};
    };
  }else{
    const segments=node("div",undefined,"stack");
    function addSegment(segment={}) {
      const row=node("div",undefined,"inline");
      const [dayWrap,day]=field("Aufnahmetag","date",segment.day_key);
      const [fromWrap,from]=field("Von","time",segment.start_time);
      const [toWrap,to]=field("Bis","time",segment.end_time);
      row.segmentValue=()=>{
        if(!day.value || Boolean(from.value)!==Boolean(to.value))throw new Error("Gib ein Datum und entweder beide Uhrzeiten oder keine Uhrzeit an.");
        return {day_key:day.value,...(from.value?{start_time:from.value,end_time:to.value}:{})};
      };
      row.append(dayWrap,fromWrap,toWrap,action("Entfernen",()=>{row.remove();markDirty(form);}));
      segments.append(row);
      return day;
    }
    const initial=item.segments || days.map(day_key=>({day_key}));
    for(const segment of initial.length?initial:[{}]){
      const input=addSegment(segment);
      firstInput ??= input;
    }
    form.append(line("Lasse beide Uhrzeiten leer, um den ganzen Tag zu übernehmen."));
    if(index===undefined)form.append(line("Für jeden Monat mit ausgewählten Tagen wird ein Sammelordner angelegt."));
    form.append(segments,action("Tag oder Zeitabschnitt hinzufügen",()=>{addSegment().focus();markDirty(form);}));
    fields=()=>{
      if(!segments.children.length)throw new Error("Mindestens ein Zeitabschnitt fehlt.");
      return {segments:[...segments.children].map(row=>row.segmentValue())};
    };
  }
  const controls=node("div",undefined,"inline editor-actions");
  function cancel(){
    if(dirty.has(form) && !confirm(t("Ungespeicherte Änderungen an diesem Planobjekt verwerfen?")))return;
    dialog.close();
  }
  dialog.oncancel=event=>{event.preventDefault();cancel();};
  dialog.onclose=()=>{savedEditor(form);dialog.replaceChildren();};
  controls.append(action("Abbrechen",cancel),action("Im Entwurf speichern",async()=>{
    const value={event_kind:kind,preserve_day_folders:keep.checked,folder_layout:folderLayout(),...fields()};
    const events=[...draft.events];
    if(index!==undefined)events[index]=value;
    else if(isEvent)events.push(value);
    else {
      const months=new Map();
      for(const segment of value.segments){
        const month=segment.day_key.slice(0,7);
        if(!months.has(month))months.set(month,[]);
        months.get(month).push(segment);
      }
      for(const segments of months.values())events.push({...value,segments});
    }
    await setDraft({...draft,events},form);
    dialog.close();
    report("Entwurf gespeichert.");
  },true));
  form.append(keepWrap,folders,controls);
  dialog.replaceChildren(form);
  dialog.showModal();
  firstInput?.focus();
}
function renderPlan(host) {
  const plan=job.plan;
  const panel=section(steps.find(([id])=>id===viewStep)?.[1]||"Durchführung und Prüfung");
  const phase=plan.execution?.phase;
  const command={plan_id:plan.id};
  const run=path=>mutate(path,"POST",command);
  const completed=plan.state==="completed";
  panel.append(line(label(phase || plan.state)));
  const locale=window.BibliothekarI18n.getLocale();
  const format=new Intl.NumberFormat(locale);
  const unit=["B","KiB","MiB","GiB","TiB"];
  const power=Math.min(unit.length-1,Math.floor(Math.log(Math.max(1,plan.move_bytes))/Math.log(1024)));
  const facts=node("dl",undefined,"adoption-plan-facts");
  for (const [title,value] of [
    ["Zu übernehmende Dateien",format.format(plan.move_files)],
    ["Dateifamilien im Verschiebeplan",format.format(plan.move_families)],
    ["Datenvolumen",format.format(plan.move_bytes / 1024**power)+" "+unit[power]],
    ["Zielbibliothek",plan.library_name],
    ["Neue Ereignisse und Sammelordner",format.format(plan.events.filter(event=>!event.existing).length)],
    ["Zu ergänzende Archivereignisse",format.format(plan.events.filter(event=>event.existing).length)],
    ["Offene Prüffälle",format.format(job.review_count)],
    ["Duplikate bleiben an der Quelle",format.format(plan.counts.duplicate || 0)],
  ]) {
    const fact=node("div");fact.append(node("dt",title),node("dd",value));facts.append(fact);
  }
  panel.append(facts);
  if (plan.counts.duplicate) panel.append(line("Duplikate sind bereits registriert oder in diesem Plan mit identischem Inhalt enthalten."));
  if (job.review_count) panel.append(line("Dateifamilien ohne Zuordnung und ausgenommene Prüffälle bleiben an der Quelle. Prüfe sie in der Liste der Prüffälle."),reviewControls());
  const diagnostics=node("details",undefined,"adoption-proof");
  diagnostics.append(node("summary","Technische Plandetails"),
    line("ZFS-Dataset: "+(plan.dataset?.dataset || "—")),
    node("code",plan.source_root+" → "+plan.archive_root),
    line(Object.entries(plan.counts).map(([state,count])=>t(label(state))+": "+count).join(" · ")));
  panel.append(diagnostics);
  if (!completed && phase!=="rolled_back") panel.append(line(
    "Vor größeren Dateiänderungen empfehlen wir, einen ZFS-Snapshot oder eine andere geeignete Sicherung anzulegen. Diese zusätzliche Sicherheitsmaßnahme ist freiwillig."
  ));
  const files=node("div",undefined,"inline");
  const manifest=link("Verschiebeplan mit Rückwegen",jobPath("/download/manifest"));
  if(phase && plan.execution?.method==="manual") files.append(manifest);
  else diagnostics.append(line(""),manifest);
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
  if (!recoveryOnly && !phase && !completed) {
    controls.append(
      action(plan.documents_at?"Ereignisdokumente neu vorbereiten":"Ereignisdokumente vorbereiten",()=>mutate("/documents")),
      action("Plan zur Bearbeitung öffnen",()=>mutate("/reopen")));
    if (plan.documents_at && viewStep==="execution") {
      renderConfirmation(panel,command);
    }
  }
  const scripted=plan.execution?.method==="script";
  if (scripted && !completed && phase!=="rolled_back") {
    panel.append(slot("script-state"));
    const details=node("details");
    details.append(node("summary","Erweiterte Details zu Skript und Prüfung"),scriptLinks(true));
    panel.append(details);
  }
  if (!recoveryOnly && viewStep==="verify" && !scripted && ["manual","verifying","repair"].includes(phase)) {
    controls.append(action("Archiv prüfen",()=>run("/verify"),true));
  }
  if (!recoveryOnly && phase==="repair" && !scripted) controls.append(action("Manuelle Schritte fortsetzen",()=>run("/resume")));
  if (viewStep==="verify" && (phase==="registering" || (!recoveryOnly && phase==="registration_pending"))) {
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
  if (plan.issues) controls.append(action("Prüfprobleme anzeigen",async()=>{
    const issues=await api(jobPath("/issues"));
    $("issues").replaceChildren(...issues.map(item=>line([item.relative_path,t(item.issue)].filter(Boolean).join(" · "))));
  }));
  const moves=node("details");moves.append(node("summary","Verschiebeplan anzeigen"),slot("moves"));
  panel.append(controls,slot("issues"),moves);
  host.append(panel);
}

function commandBox(command) {
  const area=node("textarea",undefined,"adoption-command");
  area.setAttribute("aria-label",t("TrueNAS-Shell-Befehl"));
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
function scriptLinks(confirmed=false) {
  const links=node("div",undefined,"stack");
  links.append(link("Python-Skript ansehen",jobPath("/script/source/legacy_adoption_host.py")),
    link("Code für die Dataset-Prüfung ansehen",jobPath("/script/source/legacy_adoption_dataset.py")),
    confirmed ? link("Bestätigtes Skriptmanifest",jobPath("/script/manifest")) :
      link("Verschiebeplan mit Rückwegen",jobPath("/download/manifest")));
  return links;
}
function renderConfirmation(panel,command) {
  const confirmation=node("div",undefined,"adoption-card");
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
  const proofState=node("div",undefined,"adoption-proof");
  proofState.setAttribute("role","status");
  const [appWrap,appdata]=field("AppData auf dem TrueNAS-Host","text");
  const [sourceWrap,source]=field("Quellordner auf dem TrueNAS-Host","text");
  const [archiveWrap,archive]=field("Archivordner auf dem TrueNAS-Host","text");
  const [wrap,ack]=field("Ich bestätige die Sicherheitsbedingungen und den angezeigten Plan.","checkbox");
  wrap.classList.add("adoption-ack");
  let probe=null;
  function showProbe(result) {
    if (probe?.sha256!==result.sha256) ack.checked=false;
    probe=result;
    proofState.replaceChildren();
    if (!result.command) return;
    if (result.verified) {
      const paths=node("details");
      paths.append(node("summary","Bestätigte Hostpfade"),node("code",result.host.source+" → "+result.host.archive));
      proofState.append(line("Hostpfade und gemeinsames ZFS-Dataset bestätigt."),line(result.dataset),paths);
      return;
    }
    proofState.append(line("Führe den Prüfbefehl in der TrueNAS-Shell aus und lies den Nachweis anschließend ein. Die Prüfung verschiebt keine Dateien."),
      commandBox(result.command));
  }
  async function readProbe() {
    const result=await api(jobPath("/script/probe"));
    showProbe(result);
    if (!result.verified) report("Der Hostnachweis fehlt. Prüfe die Ausgabe in der TrueNAS-Shell oder verwende die technische Pfadzuordnung.");
  }
  const fallback=node("details",undefined,"adoption-card");
  fallback.append(node("summary","Technischer Ausnahmeweg: Hostpfade manuell zuordnen"),
    line("Verwende diesen Weg, wenn Docker die Hostpfade nicht eindeutig ermitteln kann."),
    appWrap,sourceWrap,archiveWrap,
    action("Manuelle Hostpfadprüfung vorbereiten",async()=>{
      showProbe(await api(jobPath("/script/probe"),"POST",{
        ...command,appdata:appdata.value,source:source.value,archive:archive.value
      }));
    }));
  const advanced=node("details");
  advanced.append(node("summary","Erweiterte Details zu Skript und Prüfung"),
    scriptLinks(),fallback);
  const actions=node("div",undefined,"inline");
  actions.append(action("Skript vorbereiten",async()=>{
    showProbe(await api(jobPath("/script/probe"),"POST",command));
  }), action("Hostnachweis einlesen",readProbe));
  scripts.append(line("Starte den Prüfbefehl selbst in der TrueNAS-Shell. Bibliothekar verwendet die bereits ausgewählte Quelle und das Zielarchiv."),
    actions,proofState,advanced);
  method.addEventListener("change",()=>{
    scripts.hidden=method.value!=="script";
    ack.checked=false;
    if (!scripts.hidden && !probe) api(jobPath("/script/probe")).then(showProbe).catch(error=>report(error.message));
  });
  confirmation.append(node("h3","Verbindliche Sicherheitsbestätigung"),choice,scripts,
    line("Nach dieser Bestätigung müssen die geplanten Verschiebungen abgeschlossen, überprüft oder kontrolliert rückgängig gemacht werden."),
    line("Quelle und Ziel müssen auf demselben ZFS-Dataset liegen. Führe währenddessen keine weiteren Änderungen am Archiv durch."),
    wrap,action("Durchführung verbindlich starten",()=>{
      if (!ack.checked) throw new Error("Bitte bestätige zuerst die Sicherheitsbedingungen.");
      if (method.value==="script" && !probe?.verified) throw new Error("Führe zuerst die Host- und Dataset-Prüfung durch.");
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
    if (!recoveryOnly && !result.running && ["script_prepared","repair"].includes(phase) && !result.command) {
      nodes.push(action("Skriptbefehl bereitstellen",()=>run("/script/release"),true));
    }
    if (!recoveryOnly && !result.running && status?.state==="completed" && status.mode==="apply" &&
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
$("browse").addEventListener("click",()=>browse("").catch(error=>report(error.message)));
$("source-root").addEventListener("change",()=>browse("").catch(error=>report(error.message)));
$("pick-source").addEventListener("click",()=>{
  if(!browsedSource?.dataset)return;
  selectedSource={root:browsedSource.root,relative:browsedSource.relative};
  $("chosen-source").textContent=browsedSource.path;
  $("chosen-source").dataset.bkPreserveLanguage="";
  $("selected-source").hidden=false;
  $("start").focus();
});
$("start").addEventListener("click",async()=>{
  if (!selectedSource) return;
  const button=$("start");
  button.disabled=true;
  $("pick-source").disabled=true;
  $("browse").disabled=true;
  $("source-root").disabled=true;
  $("source-notice").textContent="Quelle und Ziel werden geprüft …";
  try {
    const created=await api(base+"/jobs"+(later?"?mode=library":""),"POST",selectedSource);
    openJob(created.id);
    await startInventory();
  } catch (error) {
    report(error.message);
  } finally {
    $("source-notice").textContent="";
    button.disabled=false;
    $("pick-source").disabled=!browsedSource?.dataset;
    $("browse").disabled=false;
    $("source-root").disabled=false;
  }
});
(async()=>{
  try {
    if(!jobId){navigation();await setupSourceBrowser();}
    else{$("setup").hidden=true;await refresh();}
  }
  catch(error) { report(error.message); }
})();
</script>
</body></html>"""
