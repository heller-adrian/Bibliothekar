"""First-library setup editor backed by the normal library settings APIs."""
from html import escape

from app.legacy_adoption_i18n import PATTERNS, TRANSLATIONS
from app.ui_i18n import i18n_ui_js
from app.ui_shell import apply_setup_shell


def preferences_html(library_name: str) -> str:
    return apply_setup_shell(
        _PAGE.replace("{{LIBRARY}}", escape(library_name, quote=True)),
        localization_js=i18n_ui_js(TRANSLATIONS, PATTERNS),
    )


_PAGE = r"""<!doctype html>
<html lang="de">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Bibliothekseinstellungen · Bibliothekar</title>
<style>
#first-library-preferences{max-width:950px;margin:26px auto;padding:16px}
#first-library-preferences section{border:1px solid var(--bk-line);background:var(--bk-surface);border-radius:15px;margin:12px 0;padding:18px}
#first-library-preferences h1{font-size:clamp(1.5rem,4vw,2.3rem);margin:4px 0}
#first-library-preferences h2{font-size:1.12rem;margin:0 0 15px}
#first-library-preferences p{color:var(--bk-muted);line-height:1.5}
#first-library-preferences label{display:inline-flex;align-items:center;gap:8px;margin:5px 12px 5px 0}
#first-library-preferences label.vertical{display:grid;gap:6px;justify-items:start}
#first-library-preferences input:not([type=checkbox]):not([type=radio]),#first-library-preferences select{box-sizing:border-box;max-width:100%;padding:8px;background:var(--bk-paper);color:var(--bk-ink);border:1px solid var(--bk-line);border-radius:9px}
#first-library-preferences button{background:var(--bk-surface-2);color:var(--bk-ink);border:1px solid var(--bk-line);border-radius:10px;padding:9px 15px;cursor:pointer}
#first-library-preferences #first-library-next{background:var(--bk-blue);color:white}
#first-library-preferences button:disabled{opacity:.55}
#first-library-preferences .actions{position:sticky;bottom:0;border-top:1px solid var(--bk-line);background:var(--bk-paper);padding:15px 0}
#first-library-status{white-space:pre-wrap;margin-top:10px}
#first-library-status[data-error=true]{color:var(--bk-danger)}
#first-library-preview{white-space:pre-wrap;background:var(--bk-surface-2);border-radius:10px;padding:14px;font-family:Menlo,monospace;font-size:.85rem}
</style>
</head>
<body>
<main id="first-library-preferences">
<p>Ersteinrichtung · Schritt 2 von 3</p>
<h1>Ordnerstruktur und Benennung</h1>
<p>Diese Einstellungen gelten für <strong>{{LIBRARY}}</strong> und bleiben nach der Übernahme
für spätere Ereignisse und Importe erhalten. Du kannst die Standardwerte unverändert übernehmen.</p>
<section>
<h2>Ordnerstruktur</h2>
<label><input id="folder-enabled" type="checkbox"> Unterordner für neue Ereignisse anlegen</label>
<div id="folder-tree"></div>
<label class="vertical">Exportordner
<select id="folder-export"><option value="">Kein Exportordner</option></select></label>
<div><button type="button" id="folder-add">＋ Ordner</button></div>
</section>
<section><h2>Normale Ereignisse</h2>
<label><input id="event-year" type="checkbox"> Jahr einbeziehen</label>
<label><input id="event-time" type="checkbox"> Uhrzeit einbeziehen</label>
<label><input id="event-range" type="checkbox"> Von–bis im Namen</label>
</section>
<section><h2>Unterereignisse</h2>
<label><input id="child-year" type="checkbox"> Jahr einbeziehen</label>
<label><input id="child-time" type="checkbox"> Uhrzeit einbeziehen</label>
<label><input id="child-range" type="checkbox"> Von–bis im Namen</label>
<label><input id="child-enabled" type="checkbox"> Präfix standardmäßig verwenden</label>
</section>
<section><h2>Sammelordner</h2>
<label class="vertical">Bezeichnung für Sammelordner
<input id="collection-label" type="text" autocomplete="off"></label>
<label><input id="collection-year" type="checkbox"> Jahr einbeziehen</label>
</section>
<section><h2>Vorschau</h2><div id="first-library-preview"></div></section>
<div class="actions"><button id="first-library-next" type="button" disabled>Weiter · Übernahme auswählen</button>
<div id="first-library-status" role="status" aria-live="polite">Einstellungen werden geladen …</div></div>
</main>
<script>
(() => {
  "use strict";
  const el = id => document.getElementById(id);
  const next = el("first-library-next"), status = el("first-library-status");
  const {render, flatten, nodeId} = window.BibliothekarFolderLayout;
  let layout = null, naming = null, oldLayout = "", oldNaming = "", saving = false;
  const api = async (url, options = {}) => {
    const res = await fetch(url, {cache:"no-store", ...options});
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw Error(typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail || res.status));
    return data;
  };
  const opts = data => ({method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify(data)});
  const msg = (value, bad=false) => {status.textContent=value;status.dataset.error=String(bad);};
  function values() {
    return {
      no_event_label:el("collection-label").value,
      date_mode:el("event-range").checked?"range":"start",
      include_year:el("event-year").checked,
      include_time:el("event-time").checked,
      no_event_include_year:el("collection-year").checked,
      subevent_date_mode:el("child-range").checked?"range":"start",
      subevent_include_year:el("child-year").checked,
      subevent_include_time:el("child-time").checked,
      subevent_prefix_enabled:el("child-enabled").checked
    };
  }
  function setNaming(data) {
    naming=data;
    el("collection-label").value=data.no_event_label;
    el("event-range").checked=data.date_mode==="range";
    el("event-year").checked=!!data.include_year;
    el("event-time").checked=!!data.include_time;
    el("collection-year").checked=!!data.no_event_include_year;
    el("child-range").checked=data.subevent_date_mode==="range";
    el("child-year").checked=!!data.subevent_include_year;
    el("child-time").checked=!!data.subevent_include_time;
    el("child-enabled").checked=data.subevent_prefix_enabled!==false;
    oldNaming=JSON.stringify(values());
  }
  function preview() {
    if (!naming || !layout) return;
    const n=values();
    const event=(n.include_year?"2026-":"")+(n.date_mode==="range"?"07-01–07-05":"07-01")
      +(n.include_time?"_14-30":"")+" - Beispielereignis";
    const collection=(n.no_event_include_year?"2026-":"")+"07 - "+n.no_event_label;
    el("first-library-preview").textContent="Ereignis: "+event+"\nSammelordner: "+collection+
      "\nUnterordner: "+(layout.structure_enabled ? flatten(layout.layout?.nodes||[]).map(v=>v.path).join(", ") : "keine");
  }
  function redraw() {
    if (!layout) return;
    el("folder-enabled").checked=!!layout.structure_enabled;
    render({state:layout,host:el("folder-tree"),exportSelect:el("folder-export"),
      radioName:"first-library-input",manageExport:false,onChange:preview});
  }
  async function load() {
    const [n,l]=await Promise.all([api("/api/settings/event-naming"),api("/api/settings/event-folder-layout")]);
    setNaming(n);layout=l;oldLayout=JSON.stringify(layout);redraw();preview();
    next.disabled=false;msg("Einstellungen geladen. Ohne Änderung direkt mit Weiter fortfahren.");
  }
  for(const id of ["event-range","event-year","event-time","collection-year","child-range",
                   "child-year","child-time","child-enabled","collection-label"]) {
    el(id).addEventListener("input",preview);
    el(id).addEventListener("change",preview);
  }
  el("folder-enabled").addEventListener("change",e=>{layout.structure_enabled=!!e.target.checked;preview();});
  el("folder-export").addEventListener("change",e=>{
    const selected=e.target.value;
    for(const {node} of flatten(layout.layout?.nodes||[])) {
      if(node.role==="export")delete node.role;
      if(selected && node.id===selected)node.role="export";
    }
    preview();
  });
  el("folder-add").addEventListener("click",()=>{
    layout.layout.nodes.push({id:nodeId(),name:"Neuer Ordner",children:[]});redraw();preview();
  });
  next.addEventListener("click",async()=>{
    if(saving || !layout || !naming)return;
    saving=true;next.disabled=true;msg("Einstellungen werden gespeichert …");
    try{
      if(JSON.stringify(values())!==oldNaming){
        setNaming(await api("/api/settings/event-naming",opts(values())));
      }
      if(JSON.stringify(layout)!==oldLayout){
        layout=await api("/api/settings/event-folder-layout",opts(layout));
        oldLayout=JSON.stringify(layout);redraw();
      }
      // Re-read from the normal APIs: the preferences are not setup-only copies.
      const [n,l]=await Promise.all([api("/api/settings/event-naming"),api("/api/settings/event-folder-layout")]);
      if(n.no_event_label!==values().no_event_label || JSON.stringify(l)!==JSON.stringify(layout)){
        throw Error("Die gespeicherten Einstellungen stimmen nicht überein.");
      }
      const result=await api("/api/setup/preferences/continue",{method:"POST"});
      location.replace(result.next);
    }catch(e){msg(e.message||String(e),true);next.disabled=false;}
    finally{saving=false;}
  });
  load().catch(e=>msg(e.message||String(e),true));
})();
</script>
</body></html>"""
