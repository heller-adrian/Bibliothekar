<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Metadatenkorrektur</title>
<style>
main{width:min(1180px,100%);margin:0 auto;padding:26px 30px 70px}
.meta-head{display:flex;justify-content:space-between;gap:18px;align-items:flex-end;margin-bottom:20px}
.meta-head h1{margin:0 0 6px;font-size:clamp(1.8rem,3vw,2.7rem)}
.muted{color:var(--bk-muted,#738091)}
.meta-tabs,.meta-actions{display:flex;gap:8px;flex-wrap:wrap}
.meta-tabs button,.meta-actions button,.meta-card button{min-height:42px;border:1px solid var(--bk-border,#ccd2d8);border-radius:11px;padding:9px 14px;background:var(--bk-surface,#fff);color:inherit}
.meta-tabs button.active,.primary{background:#1976d2!important;color:#fff!important;border-color:#1976d2!important}
.meta-grid{display:grid;grid-template-columns:minmax(0,1.4fr) minmax(330px,.8fr);gap:16px;align-items:start}
.meta-card{border:1px solid var(--bk-border,#ccd2d8);border-radius:15px;background:var(--bk-surface,#fff);padding:16px}
.meta-paths{display:grid;gap:5px;font-size:.9rem;margin:8px 0 14px}
.meta-files{display:grid;gap:8px;margin-top:14px}
.meta-file{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:10px;text-align:left;width:100%;border:1px solid var(--bk-border,#ccd2d8);border-radius:12px;padding:11px 13px;background:transparent;color:inherit}
.meta-file.active{outline:2px solid #1976d2}
.meta-file strong,.meta-file small{display:block}
.badge{display:inline-flex;align-items:center;border:1px solid currentColor;border-radius:999px;padding:3px 8px;font-size:.8rem;white-space:nowrap}
.good{color:#149b61}.warn{color:#c88700}.danger{color:#d53d48}
.meta-form{display:grid;gap:12px}
.meta-form label{display:grid;gap:5px}
.meta-form input{min-height:42px;border:1px solid var(--bk-border,#ccd2d8);border-radius:10px;padding:8px 10px;background:var(--bk-input,#fff);color:inherit}
.meta-kv{display:grid;grid-template-columns:130px 1fr;gap:6px 10px;font-size:.9rem}
.meta-task{border-top:1px solid var(--bk-border,#ccd2d8);padding-top:12px;margin-top:12px}
#meta-general-settings{margin-top:12px;padding-top:12px;border-top:1px solid var(--bk-border,#ccd2d8)}
@media(max-width:820px){main{padding:18px 14px 60px}.meta-grid{grid-template-columns:1fr}.meta-head{align-items:flex-start;flex-direction:column}}
</style>
</head>
<body class="bibliothekar-redesign">
<main>
  <div class="meta-head">
    <div>
      <h1>Metadatenkorrektur</h1>
      <div class="muted">Problemdateien analysieren, Aufnahmezeit aus Metadaten oder Dateinamen ableiten und erst nach Bestätigung sicher schreiben.</div>
    </div>
    <div class="meta-tabs">
      <button id="meta-tab-library" type="button" class="active">Bibliothek</button>
      <button id="meta-tab-general" type="button">Allgemein</button>
    </div>
  </div>

  <section class="meta-card" style="margin-bottom:16px">
    <div style="display:flex;justify-content:space-between;gap:12px;align-items:flex-start;flex-wrap:wrap">
      <div>
        <strong id="meta-area-title">Bibliothek</strong>
        <div id="meta-area-help" class="muted" style="margin-top:4px">Dateien werden im bibliotheksspezifischen Metadaten-Eingang bearbeitet.</div>
      </div>
      <div class="meta-actions">
        <button id="meta-scan" type="button" class="primary">Eingang prüfen</button>
      </div>
    </div>
    <div class="meta-paths">
      <span>Eingang: <code id="meta-input-path">–</code></span>
      <span>Ausgang: <code id="meta-output-path">–</code></span>
    </div>
    <div id="meta-general-settings" hidden>
      <div class="muted">„Allgemein“ verwendet einen eigenen in TrueNAS gemounteten RW-Host-Path. Konfiguriert wird er unter Einstellungen → Pfade.</div>
    </div>
    <div id="meta-status" class="muted"></div>
  </section>

  <div class="meta-grid">
    <section class="meta-card">
      <div style="display:flex;justify-content:space-between;gap:8px;align-items:center">
        <strong>Dateien im Eingang</strong>
        <span id="meta-summary" class="muted">Noch nicht geprüft</span>
      </div>
      <div id="meta-files" class="meta-files"><div class="muted">„Eingang prüfen“ starten.</div></div>
    </section>

    <aside class="meta-card">
      <strong>Datei prüfen</strong>
      <div id="meta-details" class="muted" style="margin-top:12px">Links eine Datei auswählen.</div>
      <div id="meta-open-tasks" class="meta-task"></div>
    </aside>
  </div>
</main>
<script>
(()=>{
  const state={area:"library",scan:null,selected:null,tasks:[]};
  const $=id=>document.getElementById(id);
  const esc=v=>String(v??"").replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;");
  async function json(url,options={}){
    const response=await fetch(url,options);
    const raw=await response.text(); let data={};
    try{data=raw?JSON.parse(raw):{};}catch(_){}
    if(!response.ok)throw new Error(data.detail||raw||("HTTP "+response.status));
    return data;
  }
  function setStatus(message,error=false){
    $("meta-status").textContent=message||"";
    $("meta-status").style.color=error?"var(--bk-danger,#d53d48)":"";
  }
  function setArea(area){
    state.area=area;
    $("meta-tab-library").classList.toggle("active",area==="library");
    $("meta-tab-general").classList.toggle("active",area==="general");
    $("meta-area-title").textContent=area==="library"?"Bibliothek":"Allgemein";
    $("meta-area-help").textContent=area==="library"
      ?"Eigener Eingang dieser Bibliothek unter dem gemeinsamen Metadatenkorrektur-Stamm."
      :"Unabhängige Dateien im separaten TrueNAS-Host-Path.";
    $("meta-general-settings").hidden=area!=="general";
    state.scan=null;state.selected=null;
    $("meta-files").innerHTML='<div class="muted">„Eingang prüfen“ starten.</div>';
    $("meta-details").innerHTML='<div class="muted">Links eine Datei auswählen.</div>';
    loadAreaPaths();
  }
  async function loadAreaPaths(){
    try{
      const data=await json("/api/metadata-correction/areas");
      const area=data.areas?.[state.area]||{};
      $("meta-input-path").textContent=area.input_root||"nicht verfügbar";
      $("meta-output-path").textContent=area.output_root||"nicht verfügbar";
      if(area.error)setStatus(area.error,true); else setStatus("");
    }catch(error){setStatus(error.message,true);}
  }
  function bestSuggestion(file){
    return file.preferred_suggestion||file.filename_suggestion||null;
  }
  function renderFiles(){
    const files=state.scan?.files||[];
    $("meta-summary").textContent=files.length+" Datei"+(files.length===1?"":"en");
    if(!files.length){
      $("meta-files").innerHTML='<div class="muted">Der Eingang ist leer.</div>';return;
    }
    $("meta-files").innerHTML=files.map((file,index)=>{
      const hint=bestSuggestion(file);
      const badge=file.capture_time_confidence==="high"?"Metadaten sicher":hint?"Vorschlag vorhanden":"Prüfung nötig";
      const cls=file.capture_time_confidence==="high"?"good":hint?"warn":"danger";
      return '<button class="meta-file '+(state.selected===index?"active":"")+'" data-meta-file="'+index+'" type="button">'
        +'<span><strong>'+esc(file.filename)+'</strong><small class="muted">'+esc(file.relative_path)+'</small>'
        +'<small class="muted">Aktuell: '+esc(file.selected_capture_time||"kein belastbares Datum")+'</small></span>'
        +'<span class="badge '+cls+'">'+esc(badge)+'</span></button>';
    }).join("");
    document.querySelectorAll("[data-meta-file]").forEach(button=>button.addEventListener("click",()=>{
      state.selected=Number(button.dataset.metaFile);renderFiles();renderDetails();
    }));
  }
  function splitSuggestion(hint){
    const dt=String(hint?.datetime||"");
    return {date:hint?.date||dt.slice(0,10)||"",time:(hint?.time||dt.slice(11,19)||"").slice(0,5)};
  }
  function renderDetails(){
    const file=(state.scan?.files||[])[state.selected];
    if(!file){$("meta-details").innerHTML='<div class="muted">Links eine Datei auswählen.</div>';return;}
    const hint=bestSuggestion(file); const suggested=splitSuggestion(hint);
    const filename=file.filename_suggestion;
    $("meta-details").innerHTML='<div class="meta-form">'
      +'<div class="meta-kv"><span>Datei</span><strong>'+esc(file.filename)+'</strong>'
      +'<span>Metadaten</span><span>'+esc(file.selected_capture_time||"kein belastbares Datum")+' · '+esc(file.capture_time_confidence||"")+'</span>'
      +'<span>Dateiname</span><span>'+(filename?(esc(filename.date)+(filename.time?" "+esc(filename.time):" · Uhrzeit fehlt")):"kein Datum erkannt")+'</span></div>'
      +'<label><span>Datum</span><input id="meta-date" type="date" value="'+esc(suggested.date)+'"></label>'
      +'<label><span>Uhrzeit</span><input id="meta-time" type="time" step="1" value="'+esc(suggested.time)+'"></label>'
      +'<button id="meta-prepare" type="button" class="primary">Änderung vorbereiten</button>'
      +'<div class="muted">Beim Vorbereiten werden Pfad, Größe und SHA-256 eingefroren. Geschrieben wird erst im nächsten Schritt.</div>'
      +'</div>';
    $("meta-prepare").addEventListener("click",()=>prepare(file));
  }
  async function prepare(file){
    const date=$("meta-date").value; const time=$("meta-time").value;
    if(!date||!time){setStatus("Datum und Uhrzeit müssen vollständig angegeben werden.",true);return;}
    setStatus("Metadatenauftrag wird vorbereitet …");
    try{
      const result=await json("/api/metadata-correction/tasks",{
        method:"POST",headers:{"Content-Type":"application/json"},
        body:JSON.stringify({area:state.area,relative_path:file.relative_path,proposed_datetime:date+"T"+time})
      });
      setStatus("Vorbereitet. Die Eingangsdatei wurde noch nicht verändert.");
      await loadTasks(); renderDetails(); renderTasks();
    }catch(error){setStatus(error.message,true);}
  }
  async function loadTasks(){
    try{const data=await json("/api/metadata-correction/tasks");state.tasks=data.tasks||[];renderTasks();}
    catch(error){setStatus(error.message,true);}
  }
  function renderTasks(){
    const host=$("meta-open-tasks"); const tasks=(state.tasks||[]).filter(t=>t.area===state.area);
    if(!tasks.length){host.innerHTML='<div class="muted">Keine offenen Metadatenaufträge.</div>';return;}
    host.innerHTML='<strong>Offene Aufgaben</strong>'+tasks.map(t=>'<div class="meta-task">'
      +'<div><strong>'+esc(t.source_filename)+'</strong></div><div class="muted">'+esc(t.proposed_datetime||"")+'</div>'
      +(t.error_message?'<div class="danger">'+esc(t.error_message)+'</div>':'')
      +'<div class="meta-actions" style="margin-top:8px"><button class="primary" data-meta-apply="'+esc(t.id)+'">Schreiben & prüfen</button>'
      +'<button data-meta-cancel="'+esc(t.id)+'">Verwerfen</button></div></div>').join("");
    host.querySelectorAll("[data-meta-apply]").forEach(b=>b.addEventListener("click",()=>applyTask(b.dataset.metaApply)));
    host.querySelectorAll("[data-meta-cancel]").forEach(b=>b.addEventListener("click",()=>cancelTask(b.dataset.metaCancel)));
  }
  async function applyTask(id){
    if(!confirm("Metadaten in eine geprüfte Ausgangskopie schreiben? Die Eingangsdatei wird erst nach erfolgreicher Prüfung entfernt."))return;
    setStatus("Ausgangskopie wird geschrieben und geprüft …");
    try{
      await json("/api/metadata-correction/tasks/"+encodeURIComponent(id)+"/apply",{method:"POST"});
      setStatus("Korrektur vollständig geschrieben und geprüft.");
      await scan(); await loadTasks();
    }catch(error){setStatus(error.message,true);await loadTasks();}
  }
  async function cancelTask(id){
    try{await json("/api/metadata-correction/tasks/"+encodeURIComponent(id)+"/cancel",{method:"POST"});await loadTasks();}
    catch(error){setStatus(error.message,true);}
  }
  async function scan(){
    setStatus("Eingang und Metadaten werden gelesen …");
    try{
      state.scan=await json("/api/metadata-correction/scan?area="+encodeURIComponent(state.area));
      state.selected=null;renderFiles();
      const p=state.scan.paths||{};$("meta-input-path").textContent=p.input_root||"–";$("meta-output-path").textContent=p.output_root||"–";
      setStatus("Prüfung abgeschlossen. Es wurde noch nichts verändert.");
    }catch(error){setStatus(error.message,true);}
  }
  $("meta-tab-library").addEventListener("click",()=>setArea("library"));
  $("meta-tab-general").addEventListener("click",()=>setArea("general"));
  $("meta-scan").addEventListener("click",scan);
  loadAreaPaths();loadTasks();
})();
</script>
</body>
</html>