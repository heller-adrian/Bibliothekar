METADATA_CORRECTION_HTML = r"""<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Metadatenkorrektur</title>
<style>
main{width:min(1180px,100%);margin:0 auto;padding:18px 30px 70px}
.muted{color:var(--bk-muted,#738091)}
.meta-actions{display:flex;gap:8px;flex-wrap:wrap}
.meta-actions button,.meta-card button{min-height:40px;border:1px solid var(--bk-line,#ccd2d8);border-radius:11px;padding:8px 13px;background:var(--bk-surface,#fff);color:inherit}
.primary{background:var(--bk-blue,#1976d2)!important;color:#fff!important;border-color:var(--bk-blue,#1976d2)!important}
.meta-grid{display:grid;grid-template-columns:minmax(0,1.4fr) minmax(330px,.8fr);gap:16px;align-items:start}
.meta-card{border:1px solid var(--bk-line,#ccd2d8);border-radius:15px;background:var(--bk-surface,#fff);padding:16px}
.meta-overview{margin-bottom:16px}
.meta-paths{display:grid;gap:5px;font-size:.9rem;margin:9px 0 0}
.meta-groups{display:grid;gap:14px;margin-top:14px}
.meta-library-group{border:1px solid var(--bk-line,#ccd2d8);border-radius:13px;padding:12px;background:var(--bk-surface-2,#f5f5f5)}
.meta-library-group-head{display:flex;justify-content:space-between;gap:10px;align-items:baseline;margin-bottom:9px}
.meta-files{display:grid;gap:8px}
.meta-file{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:10px;text-align:left;width:100%;border:1px solid var(--bk-line,#ccd2d8);border-radius:12px;padding:11px 13px;background:var(--bk-surface,#fff);color:inherit}
.meta-file.active{outline:2px solid var(--bk-blue,#1976d2)}
.meta-file strong,.meta-file small{display:block}
.badge{display:inline-flex;align-items:center;border:1px solid currentColor;border-radius:999px;padding:3px 8px;font-size:.8rem;white-space:nowrap}
.good{color:#149b61}.warn{color:#c88700}.danger{color:#d53d48}
.meta-form{display:grid;gap:12px}
.meta-form label{display:grid;gap:5px}
.meta-form input{min-height:40px;border:1px solid var(--bk-line,#ccd2d8);border-radius:10px;padding:8px 10px;background:var(--bk-surface-2,#fff);color:inherit}
.meta-kv{display:grid;grid-template-columns:130px minmax(0,1fr);gap:6px 10px;font-size:.9rem}
.meta-task{border-top:1px solid var(--bk-line,#ccd2d8);padding-top:12px;margin-top:12px}
.meta-placeholder{padding:28px 18px;text-align:center}
@media(max-width:820px){main{padding:14px 14px 60px}.meta-grid{grid-template-columns:1fr}.meta-kv{grid-template-columns:105px minmax(0,1fr)}}
</style>
</head>
<body>
<main>
  <section class="meta-card meta-overview">
    <div style="display:flex;justify-content:space-between;gap:12px;align-items:flex-start;flex-wrap:wrap">
      <div>
        <strong id="meta-area-title">Bibliothek</strong>
        <div id="meta-area-help" class="muted" style="margin-top:4px"></div>
      </div>
      <div class="meta-actions">
        <button id="meta-scan" type="button" class="primary">Bestand prüfen</button>
      </div>
    </div>
    <div id="meta-paths" class="meta-paths"></div>
    <div id="meta-status" class="muted" style="margin-top:10px"></div>
  </section>

  <div id="meta-workspace" class="meta-grid">
    <section class="meta-card">
      <div style="display:flex;justify-content:space-between;gap:8px;align-items:center">
        <strong id="meta-list-title">Dateien</strong>
        <span id="meta-summary" class="muted">Noch nicht geprüft</span>
      </div>
      <div id="meta-files" class="meta-groups"><div class="muted">Prüfung starten.</div></div>
    </section>

    <aside class="meta-card">
      <strong>Datei prüfen</strong>
      <div id="meta-details" class="muted" style="margin-top:12px">Links eine Datei auswählen.</div>
      <div id="meta-open-tasks" class="meta-task"></div>
    </aside>
  </div>

  <section id="meta-multiple-placeholder" class="meta-card meta-placeholder" hidden>
    <strong>Mehrfachkorrektur · vorgesehen für 0.34.0</strong>
    <p class="muted">Hier wird eine Referenzaufnahme mit dem korrekten Datum und der korrekten Uhrzeit versehen. Bibliothekar überträgt anschließend denselben Zeitversatz auf die zusammengehörigen Kameraaufnahmen, ohne deren zeitliche Abstände zu verändern.</p>
    <p class="muted">Der vorgesehene verwaltete Ordner ist <code id="meta-multiple-path">/workspace/Metadatenkorrektur/Mehrfachkorrektur</code>. Er wird erst mit der Funktion in 0.34.0 aktiviert.</p>
  </section>
</main>
<script>
(()=>{
  const params=new URLSearchParams(location.search);
  const requested=String(params.get("area")||"library");
  const state={area:["library","general","multiple"].includes(requested)?requested:"library",scan:null,selected:null,tasks:[],areas:null};
  const $=id=>document.getElementById(id);
  const esc=v=>String(v??"").replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;");
  async function json(url,options={}){
    const response=await fetch(url,options);
    const raw=await response.text(); let data={};
    try{data=raw?JSON.parse(raw):{};}catch(_){}
    if(!response.ok)throw new Error(typeof data.detail==="string"?data.detail:(raw||("HTTP "+response.status)));
    return data;
  }
  function setStatus(message,error=false){
    $("meta-status").textContent=message||"";
    $("meta-status").style.color=error?"var(--bk-danger,#d53d48)":"";
  }
  function bestSuggestion(file){return file.preferred_suggestion||file.filename_suggestion||null;}
  function splitSuggestion(hint){
    const dt=String(hint?.datetime||"");
    return {date:hint?.date||dt.slice(0,10)||"",time:(hint?.time||dt.slice(11,19)||"").slice(0,5)};
  }
  function configureArea(){
    const library=state.area==="library", general=state.area==="general", multiple=state.area==="multiple";
    $("meta-area-title").textContent=library?"Bibliothek":general?"Allgemein":"Mehrfachkorrektur";
    $("meta-area-help").textContent=library
      ?"Alle freien Kamera-Familien ohne belastbares Aufnahmedatum – nach Herkunftsbibliothek gruppiert."
      : general
        ?"Unabhängige Dateien direkt im verwalteten Ordner Allgemein korrigieren."
        :"Zeitlich zusammengehörige Kameraaufnahmen gemeinsam verschieben.";
    $("meta-scan").hidden=multiple;
    $("meta-workspace").hidden=multiple;
    $("meta-multiple-placeholder").hidden=!multiple;
    $("meta-list-title").textContent=library?"Ohne-Datum-Bestand":"Dateien im Ordner Allgemein";
  }
  async function loadAreas(){
    try{
      state.areas=(await json("/api/metadata-correction/areas")).areas||{};
      const area=state.areas[state.area]||{};
      if(state.area==="library"){
        $("meta-paths").innerHTML='<span>Quelle: <code>'+esc(area.source_root||"Ohne_Datum")+'</code></span><span class="muted">Nach erfolgreicher Korrektur wird die Familie direkt in den normalen freien Tagesbestand zurückgeführt.</span>';
      }else if(state.area==="general"){
        $("meta-paths").innerHTML='<span>Ordner: <code>'+esc(area.root||"")+'</code></span><span class="muted">Kein Eingang/Ausgang: die geprüfte Datei wird nach erfolgreicher Verifikation atomar am selben Ort ersetzt.</span>';
      }else{
        $("meta-paths").innerHTML="";
        $("meta-multiple-path").textContent=area.root||"/workspace/Metadatenkorrektur/Mehrfachkorrektur";
      }
    }catch(error){setStatus(error.message,true);}
  }
  function fileBadge(file){
    const hint=bestSuggestion(file);
    if(file.capture_time_confidence==="high")return ["Metadaten sicher","good"];
    if(hint)return ["Vorschlag vorhanden","warn"];
    return ["Prüfung nötig","danger"];
  }
  function fileButton(file,index){
    const [badge,cls]=fileBadge(file);
    const memberText=Number(file.member_count||0)>1 ? " · "+Number(file.member_count)+" Dateien" : "";
    return '<button class="meta-file '+(state.selected===index?"active":"")+'" data-meta-file="'+index+'" type="button">'
      +'<span><strong>'+esc(file.filename)+'</strong><small class="muted">'+esc(file.relative_path||"")+memberText+'</small>'
      +'<small class="muted">Aktuell: '+esc(file.selected_capture_time||"kein belastbares Datum")+'</small></span>'
      +'<span class="badge '+cls+'">'+esc(badge)+'</span></button>';
  }
  function renderFiles(){
    const files=state.scan?.files||[];
    const fileCount=Number(state.scan?.summary?.file_count ?? files.length);
    const familyCount=Number(state.scan?.summary?.family_count ?? files.length);
    $("meta-summary").textContent=state.area==="library"
      ? familyCount+" Familien · "+fileCount+" Dateien"
      : files.length+" Datei"+(files.length===1?"":"en");
    if(!files.length){
      $("meta-files").innerHTML='<div class="muted">'+(state.area==="library"?"Keine Ohne-Datum-Familien vorhanden.":"Der Ordner ist leer.")+'</div>';return;
    }
    if(state.area==="library"){
      let offset=0;
      $("meta-files").innerHTML=(state.scan.groups||[]).map(group=>{
        const groupFiles=group.files||[];
        const start=offset; offset+=groupFiles.length;
        return '<section class="meta-library-group"><div class="meta-library-group-head"><strong>'+esc(group.library_name||group.library_id||"Bibliothek")+'</strong>'
          +'<span class="muted">'+groupFiles.length+' Familien</span></div><div class="meta-files">'
          +groupFiles.map((file,i)=>fileButton(file,start+i)).join("")+'</div></section>';
      }).join("");
    }else{
      $("meta-files").innerHTML='<div class="meta-files">'+files.map((file,i)=>fileButton(file,i)).join("")+'</div>';
    }
    document.querySelectorAll("[data-meta-file]").forEach(button=>button.addEventListener("click",()=>{
      state.selected=Number(button.dataset.metaFile);renderFiles();renderDetails();
    }));
  }
  function renderDetails(){
    const file=(state.scan?.files||[])[state.selected];
    if(!file){$("meta-details").innerHTML='<div class="muted">Links eine Datei auswählen.</div>';return;}
    const hint=bestSuggestion(file), suggested=splitSuggestion(hint), filename=file.filename_suggestion;
    const familyLine=state.area==="library"
      ? '<span>Familie</span><span>'+esc(file.member_count||1)+' Dateien · '+esc(file.library_name||file.library_id||"")+'</span>'
      :"";
    $("meta-details").innerHTML='<div class="meta-form"><div class="meta-kv">'
      +'<span>Datei</span><strong>'+esc(file.filename)+'</strong>'+familyLine
      +'<span>Metadaten</span><span>'+esc(file.selected_capture_time||"kein belastbares Datum")+' · '+esc(file.capture_time_confidence||"")+'</span>'
      +'<span>Dateiname</span><span>'+(filename?(esc(filename.date)+(filename.time?" "+esc(filename.time):" · Uhrzeit fehlt")):"kein Datum erkannt")+'</span></div>'
      +'<label><span>Datum</span><input id="meta-date" type="date" value="'+esc(suggested.date)+'"></label>'
      +'<label><span>Uhrzeit</span><input id="meta-time" type="time" step="1" value="'+esc(suggested.time)+'"></label>'
      +'<button id="meta-prepare" type="button" class="primary">Änderung vorbereiten</button>'
      +'<div class="muted">'+(state.area==="library"
        ?"Die vollständige Familie wird eingefroren. Erst nach Schreiben, Metadatenprüfung und Zielprüfung wird sie aus Ohne_Datum in den normalen Tagesbestand übernommen."
        :"Beim Vorbereiten werden Pfad, Größe und SHA-256 eingefroren. Die Originaldatei bleibt bis zur bestätigten Schreibprüfung unverändert.")+'</div></div>';
    $("meta-prepare").addEventListener("click",()=>prepare(file));
  }
  async function prepare(file){
    const date=$("meta-date").value,time=$("meta-time").value;
    if(!date||!time){setStatus("Datum und Uhrzeit müssen vollständig angegeben werden.",true);return;}
    setStatus("Metadatenauftrag wird vorbereitet …");
    try{
      const payload={area:state.area,relative_path:file.relative_path,proposed_datetime:date+"T"+time};
      if(state.area==="library"){payload.library_id=file.library_id;payload.family_id=file.family_id;}
      await json("/api/metadata-correction/tasks",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
      setStatus("Vorbereitet. Physisch wurde noch nichts verändert.");
      await loadTasks();renderDetails();
    }catch(error){setStatus(error.message,true);}
  }
  async function loadTasks(){
    try{
      const data=await json("/api/metadata-correction/tasks");
      state.tasks=data.tasks||[];
      renderTasks();
    }catch(error){setStatus(error.message,true);}
  }
  function renderTasks(){
    const host=$("meta-open-tasks");
    const tasks=(state.tasks||[]).filter(t=>String(t.area)===state.area);
    if(!tasks.length){host.innerHTML='<div class="muted">Keine offenen Metadatenaufträge.</div>';return;}
    host.innerHTML='<strong>Offene Aufgaben</strong>'+tasks.map(t=>'<div class="meta-task">'
      +'<div><strong>'+esc(t.source_filename)+'</strong></div>'
      +(state.area==="library"?'<div class="muted">'+esc(t.library_name||t.library_id||"")+'</div>':"")
      +'<div class="muted">'+esc(t.proposed_datetime||"")+'</div>'
      +(t.error_message?'<div class="danger">'+esc(t.error_message)+'</div>':'')
      +'<div class="meta-actions" style="margin-top:8px"><button class="primary" data-meta-apply="'+esc(t.id)+'">Schreiben & prüfen</button>'
      +'<button data-meta-cancel="'+esc(t.id)+'">Verwerfen</button></div></div>').join("");
    host.querySelectorAll("[data-meta-apply]").forEach(b=>b.addEventListener("click",()=>applyTask(b.dataset.metaApply)));
    host.querySelectorAll("[data-meta-cancel]").forEach(b=>b.addEventListener("click",()=>cancelTask(b.dataset.metaCancel)));
  }
  async function applyTask(id){
    const question=state.area==="library"
      ?"Metadaten familienweise schreiben, vollständig prüfen und danach in den normalen Tagesbestand zurückführen?"
      :"Metadaten in einer Arbeitskopie schreiben, prüfen und die Datei danach atomar ersetzen?";
    if(!confirm(question))return;
    setStatus("Korrektur wird geschrieben und vollständig geprüft …");
    try{
      await json("/api/metadata-correction/tasks/"+encodeURIComponent(id)+"/apply",{method:"POST"});
      setStatus(state.area==="library"?"Korrektur geprüft und in den Arbeitsbestand zurückgeführt.":"Korrektur vollständig geschrieben und geprüft.");
      await scan();await loadTasks();
    }catch(error){setStatus(error.message,true);await loadTasks();}
  }
  async function cancelTask(id){
    try{await json("/api/metadata-correction/tasks/"+encodeURIComponent(id)+"/cancel",{method:"POST"});await loadTasks();}
    catch(error){setStatus(error.message,true);}
  }
  async function scan(){
    if(state.area==="multiple")return;
    setStatus(state.area==="library"?"Ohne-Datum-Bestand wird gelesen …":"Ordner und Metadaten werden gelesen …");
    try{
      state.scan=await json("/api/metadata-correction/scan?area="+encodeURIComponent(state.area));
      state.selected=null;renderFiles();renderDetails();
      setStatus("Prüfung abgeschlossen. Es wurde noch nichts verändert.");
    }catch(error){setStatus(error.message,true);}
  }
  $("meta-scan").addEventListener("click",scan);
  configureArea();
  loadAreas();
  loadTasks();
})();
</script>
</body>
</html>"""
