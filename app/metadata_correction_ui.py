METADATA_CORRECTION_HTML = r"""<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Metadatenkorrektur</title>
<style>
main{width:min(1180px,100%);margin:0 auto;padding:18px 30px 70px}
.muted{color:var(--bk-muted,#738091)}
.meta-actions{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
.meta-actions button,.meta-card button{min-height:40px;border:1px solid var(--bk-line,#ccd2d8);border-radius:11px;padding:8px 13px;background:var(--bk-surface,#fff);color:inherit}
.primary{background:var(--bk-blue,#1976d2)!important;color:#fff!important;border-color:var(--bk-blue,#1976d2)!important}
.meta-grid{display:grid;grid-template-columns:minmax(0,1.4fr) minmax(330px,.8fr);gap:16px;align-items:start}
.meta-card{border:1px solid var(--bk-line,#ccd2d8);border-radius:15px;background:var(--bk-surface,#fff);padding:16px}
.meta-overview{margin-bottom:16px}
.meta-paths{display:grid;gap:5px;font-size:.9rem;margin:9px 0 0}
.meta-groups{display:grid;gap:14px;margin-top:14px}
.meta-files{display:grid;gap:8px}
.meta-file{display:grid;grid-template-columns:auto minmax(0,1fr) auto;gap:10px;align-items:center;text-align:left;width:100%;box-sizing:border-box;border:1px solid var(--bk-line,#ccd2d8);border-radius:12px;padding:11px 13px;background:var(--bk-surface,#fff);color:inherit;cursor:pointer;user-select:none;-webkit-user-select:none}
.meta-file.active{border-color:var(--bk-blue,#1976d2);box-shadow:inset 0 0 0 1px var(--bk-blue,#1976d2)}
.meta-file.selected{border-color:var(--bk-blue,#1976d2);background:var(--bk-surface-2,#f5f5f5)}
.meta-file-check{width:19px;height:19px;min-height:auto;accent-color:var(--bk-blue,#1976d2)}
.meta-file strong,.meta-file small{display:block}
.badge{display:inline-flex;align-items:center;border:1px solid currentColor;border-radius:999px;padding:3px 8px;font-size:.8rem;white-space:nowrap}
.good{color:#149b61}.warn{color:#c88700}.danger{color:#d53d48}
.meta-form{display:grid;gap:12px}
.meta-form label{display:grid;gap:5px}
.meta-form input{min-height:40px;border:1px solid var(--bk-line,#ccd2d8);border-radius:10px;padding:8px 10px;background:var(--bk-surface-2,#fff);color:inherit}
.meta-kv{display:grid;grid-template-columns:130px minmax(0,1fr);gap:6px 10px;font-size:.9rem}
.meta-task{border-top:1px solid var(--bk-line,#ccd2d8);padding-top:12px;margin-top:12px}
.meta-placeholder{padding:28px 18px;text-align:center}
.meta-selection-note{font-size:.85rem;padding:8px 10px;border-radius:10px;background:var(--bk-surface-2,#f5f5f5)}
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
      <div style="display:flex;justify-content:space-between;gap:8px;align-items:center;flex-wrap:wrap">
        <strong id="meta-list-title">Dateien</strong>
        <div class="meta-actions">
          <span id="meta-summary" class="muted">Noch nicht geprüft</span>
          <button id="meta-select-all" type="button" title="Mehrere Einträge lassen sich auch mit Umschalt (Shift) auswählen.">Alle auswählen</button>
        </div>
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
    <strong>Mehrfachkorrektur · in Vorbereitung</strong>
    <p class="muted">Hier wird eine Referenzaufnahme mit dem korrekten Datum und der korrekten Uhrzeit versehen. Bibliothekar überträgt anschließend denselben Zeitversatz auf die zusammengehörigen Kameraaufnahmen, ohne deren zeitliche Abstände zu verändern.</p>
    <p class="muted">Der vorgesehene verwaltete Ordner ist <code id="meta-multiple-path">/workspace/Metadatenkorrektur/Mehrfachkorrektur</code>.</p>
  </section>
</main>
<script>
(()=>{
  const params=new URLSearchParams(location.search);
  const requested=String(params.get("area")||"library");
  const state={
    area:["library","general","multiple"].includes(requested)?requested:"library",
    scan:null,selected:null,selectedSet:new Set(),lastSelected:null,tasks:[],areas:null
  };
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
  function fileKey(file){
    return state.area==="library"
      ? String(file.library_id||"")+"::"+String(file.family_id||"")
      : String(file.relative_path||file.filename||"");
  }
  function bestSuggestion(file){
    if(state.area==="library"&&file.reintegration_ready&&file.selected_capture_time){
      const dt=String(file.selected_capture_time).slice(0,19);
      return {date:dt.slice(0,10),time:dt.slice(11,19),datetime:dt};
    }
    return file.preferred_suggestion||file.filename_suggestion||null;
  }
  function splitSuggestion(hint){
    const dt=String(hint?.datetime||"");
    return {date:hint?.date||dt.slice(0,10)||"",time:(hint?.time||dt.slice(11,19)||"").slice(0,8)};
  }
  function configureArea(){
    const library=state.area==="library", general=state.area==="general", multiple=state.area==="multiple";
    $("meta-area-title").textContent=library?"Bibliothek":general?"Allgemein":"Mehrfachkorrektur";
    $("meta-area-help").textContent=library
      ?"Gemeinsamer Ohne-Datum-Bestand aller Kamerasicherungen: erst Metadaten prüfen oder korrigieren, danach bewusst einsortieren."
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
        $("meta-paths").innerHTML='<span>Quelle: <code>'+esc(area.source_root||"Ohne_Datum")+'</code></span><span class="muted">Metadatenänderungen bleiben zunächst in Ohne_Datum. Erst „In Tagesbestand einsortieren“ verschiebt die geprüfte Familie in den kanonischen Tagesordner.</span>';
      }else if(state.area==="general"){
        $("meta-paths").innerHTML='<span>Ordner: <code>'+esc(area.root||"")+'</code></span><span class="muted">Kein Eingang/Ausgang: die geprüfte Datei wird nach erfolgreicher Verifikation atomar am selben Ort ersetzt.</span>';
      }else{
        $("meta-paths").innerHTML="";
        $("meta-multiple-path").textContent=area.root||"/workspace/Metadatenkorrektur/Mehrfachkorrektur";
      }
    }catch(error){setStatus(error.message,true);}
  }
  function fileBadge(file){
    if(state.area==="library"&&file.reintegration_ready)return ["Bereit zum Einsortieren","good"];
    const hint=bestSuggestion(file);
    if(file.capture_time_confidence==="high")return ["Metadaten sicher","good"];
    if(hint)return ["Vorschlag vorhanden","warn"];
    return ["Prüfung nötig","danger"];
  }
  function fileRow(file,index){
    const [badge,cls]=fileBadge(file);
    const memberText=Number(file.member_count||0)>1 ? " · "+Number(file.member_count)+" Dateien" : "";
    const checked=state.selectedSet.has(index);
    return '<div class="meta-file '+(state.selected===index?"active ":"")+(checked?"selected":"")+'" data-meta-file="'+index+'" role="button" tabindex="0">'
      +'<input class="meta-file-check" data-meta-check="'+index+'" type="checkbox" '+(checked?"checked":"")+' aria-label="Datei auswählen">'
      +'<span><strong>'+esc(file.filename)+'</strong><small class="muted">'+esc(file.relative_path||"")+memberText+'</small>'
      +'<small class="muted">Aktuell: '+esc(file.selected_capture_time||"kein belastbares Datum")+'</small></span>'
      +'<span class="badge '+cls+'">'+esc(badge)+'</span></div>';
  }
  function updateSelectAllButton(){
    const files=state.scan?.files||[];
    const all=files.length>0&&state.selectedSet.size===files.length;
    $("meta-select-all").textContent=all?"Auswahl aufheben":"Alle auswählen";
    $("meta-select-all").disabled=!files.length;
  }
  function selectRange(index,checked=true){
    const files=state.scan?.files||[];
    const anchor=Number.isInteger(state.lastSelected)?state.lastSelected:index;
    const lo=Math.max(0,Math.min(anchor,index));
    const hi=Math.min(files.length-1,Math.max(anchor,index));
    for(let i=lo;i<=hi;i++){
      if(checked)state.selectedSet.add(i);else state.selectedSet.delete(i);
    }
  }
  function renderFiles(){
    const files=state.scan?.files||[];
    for(const index of [...state.selectedSet])if(index<0||index>=files.length)state.selectedSet.delete(index);
    const fileCount=Number(state.scan?.summary?.file_count ?? files.length);
    const familyCount=Number(state.scan?.summary?.family_count ?? files.length);
    const chosen=state.selectedSet.size?(" · "+state.selectedSet.size+" ausgewählt"):"";
    $("meta-summary").textContent=state.area==="library"
      ? familyCount+" Familien · "+fileCount+" Dateien"+chosen
      : files.length+" Datei"+(files.length===1?"":"en")+chosen;
    if(!files.length){
      $("meta-files").innerHTML='<div class="muted">'+(state.area==="library"?"Keine Ohne-Datum-Familien vorhanden.":"Der Ordner ist leer.")+'</div>';
      updateSelectAllButton();return;
    }
    $("meta-files").innerHTML='<div class="meta-files">'+files.map(fileRow).join("")+'</div>';
    document.querySelectorAll("[data-meta-file]").forEach(row=>{
      const index=Number(row.dataset.metaFile);
      row.addEventListener("mousedown",event=>{
        if(event.shiftKey && !event.target.closest("input,button"))event.preventDefault();
      });
      row.addEventListener("click",event=>{
        if(event.target.closest("[data-meta-check]"))return;
        state.selected=index;
        if(event.shiftKey){
          selectRange(index,true);
        }else{
          state.selectedSet.add(index);
        }
        state.lastSelected=index;
        renderFiles();renderDetails();
      });
      row.addEventListener("keydown",event=>{
        if(event.key==="Enter"||event.key===" "){event.preventDefault();row.click();}
      });
    });
    document.querySelectorAll("[data-meta-check]").forEach(check=>{
      check.addEventListener("click",event=>{
        event.stopPropagation();
        const index=Number(check.dataset.metaCheck);
        state.selected=index;
        if(event.shiftKey){
          selectRange(index,check.checked);
        }else if(check.checked){
          state.selectedSet.add(index);
        }else{
          state.selectedSet.delete(index);
        }
        state.lastSelected=index;
        renderFiles();renderDetails();
      });
    });
    updateSelectAllButton();
  }
  function selectedFiles(){
    const files=state.scan?.files||[];
    const indices=state.selectedSet.size?[...state.selectedSet]:(Number.isInteger(state.selected)?[state.selected]:[]);
    return indices.map(index=>files[index]).filter(Boolean);
  }
  function selectedReadyFiles(){
    const files=selectedFiles();
    return files.length&&files.every(file=>file.reintegration_ready)?files:[];
  }
  function renderDetails(){
    const file=(state.scan?.files||[])[state.selected];
    if(!file){$("meta-details").innerHTML='<div class="muted">Links eine Datei auswählen.</div>';return;}
    const hint=bestSuggestion(file), suggested=splitSuggestion(hint), filename=file.filename_suggestion;
    const familyLine=state.area==="library"
      ? '<span>Familie</span><span>'+esc(file.member_count||1)+' Dateien</span>'
      :"";
    const selectionNote=state.selectedSet.size>1
      ? '<div class="meta-selection-note"><strong>'+state.selectedSet.size+' Einträge ausgewählt.</strong></div>'
      :"";
    const ready=state.area==="library"&&file.reintegration_ready;
    const chosenFiles=selectedFiles();
    const readyFiles=selectedReadyFiles();
    const correctionCount=chosenFiles.length||1;
    const sortButton=state.area==="library"&&readyFiles.length
      ? '<button id="meta-reintegrate" type="button" class="primary">In Tagesbestand einsortieren'+(readyFiles.length>1?" ("+readyFiles.length+")":"")+'</button>'
      :"";
    $("meta-details").innerHTML='<div class="meta-form">'+selectionNote+'<div class="meta-kv">'
      +'<span>Datei</span><strong>'+esc(file.filename)+'</strong>'+familyLine
      +'<span>Metadaten</span><span>'+esc(file.selected_capture_time||"kein belastbares Datum")+' · '+esc(file.capture_time_confidence||"")+'</span>'
      +'<span>Status</span><span>'+(ready?"korrigiert · wartet auf Einsortierung":"Prüfung/Korrektur erforderlich")+'</span>'
      +'<span>Dateiname</span><span>'+(filename?(esc(filename.date)+(filename.time?" "+esc(filename.time):" · Uhrzeit fehlt")):"kein Datum erkannt")+'</span></div>'
      +'<label><span>Datum</span><input id="meta-date" type="date" value="'+esc(suggested.date)+'"></label>'
      +'<label><span>Uhrzeit</span><input id="meta-time" type="time" step="1" value="'+esc(suggested.time)+'"></label>'
      +'<button id="meta-prepare" type="button" class="primary">'+(ready?"Metadaten erneut ändern":"Metadaten ändern")+(correctionCount>1?" ("+correctionCount+")":"")+'</button>'
      +sortButton+'</div>';
    $("meta-prepare").addEventListener("click",()=>correctSelected(file));
    if($("meta-reintegrate"))$("meta-reintegrate").addEventListener("click",reintegrateSelected);
  }
  function selectionKeys(){
    const files=state.scan?.files||[];
    return {
      keys:new Set([...state.selectedSet].map(index=>files[index]).filter(Boolean).map(fileKey)),
      primary:Number.isInteger(state.selected)&&files[state.selected]?fileKey(files[state.selected]):null,
      last:Number.isInteger(state.lastSelected)&&files[state.lastSelected]?fileKey(files[state.lastSelected]):null
    };
  }
  function restoreSelection(snapshot){
    const files=state.scan?.files||[];
    const byKey=new Map(files.map((file,index)=>[fileKey(file),index]));
    state.selectedSet=new Set([...snapshot.keys].map(key=>byKey.get(key)).filter(Number.isInteger));
    state.selected=snapshot.primary&&byKey.has(snapshot.primary)?byKey.get(snapshot.primary):null;
    state.lastSelected=snapshot.last&&byKey.has(snapshot.last)?byKey.get(snapshot.last):state.selected;
  }
  async function correctSelected(file){
    const date=$("meta-date").value,time=$("meta-time").value;
    if(!date||!time){setStatus("Datum und Uhrzeit müssen vollständig angegeben werden.",true);return;}
    const files=selectedFiles().length?selectedFiles():[file];
    const button=$("meta-prepare");
    if(button)button.disabled=true;
    setStatus(files.length===1?"Metadaten werden geändert …":files.length+" Einträge werden geändert …");
    let completed=0;
    try{
      for(const item of files){
        const payload={area:state.area,relative_path:item.relative_path,proposed_datetime:date+"T"+time};
        if(state.area==="library"){payload.library_id=item.library_id;payload.family_id=item.family_id;}
        await json("/api/metadata-correction/correct",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
        completed+=1;
      }
      await scan(false,true);
      await loadTasks(true);
      setStatus(files.length===1
        ?"Metadaten geändert. Bereit zum Einsortieren."
        :files.length+" Einträge geändert. Bereit zum Einsortieren.");
    }catch(error){
      await scan(false,true);
      await loadTasks(true);
      setStatus((completed?completed+" von "+files.length+" Einträgen geändert. ":"")+error.message,true);
    }finally{
      const current=$("meta-prepare");
      if(current)current.disabled=false;
    }
  }
  async function reintegrateSelected(){
    const files=selectedReadyFiles();
    if(!files.length){setStatus("Bitte zuerst alle ausgewählten Einträge korrigieren.",true);return;}
    const button=$("meta-reintegrate");
    if(button)button.disabled=true;
    setStatus(files.length===1?"Korrigierte Familie wird einsortiert …":files.length+" korrigierte Familien werden einsortiert …");
    try{
      await json("/api/metadata-correction/reintegrate",{
        method:"POST",headers:{"Content-Type":"application/json"},
        body:JSON.stringify({items:files.map(file=>({library_id:file.library_id,family_id:file.family_id}))})
      });
      state.selectedSet.clear();state.selected=null;state.lastSelected=null;
      await scan(false,false);
      await loadTasks(true);
      setStatus(files.length===1?"Familie wurde geprüft und in den Tagesbestand einsortiert.":files.length+" Familien wurden geprüft und in den Tagesbestand einsortiert.");
    }catch(error){
      setStatus(error.message,true);
      await loadTasks(true);
    }finally{
      const current=$("meta-reintegrate");
      if(current)current.disabled=false;
    }
  }
  async function loadTasks(quiet=false){
    try{
      const data=await json("/api/metadata-correction/tasks");
      state.tasks=data.tasks||[];
      renderTasks();
    }catch(error){if(!quiet)setStatus(error.message,true);}
  }
  function renderTasks(){
    const host=$("meta-open-tasks");
    const tasks=(state.tasks||[]).filter(t=>String(t.area)===state.area);
    if(!tasks.length){host.innerHTML='<div class="muted">Keine offenen Metadatenaufträge.</div>';return;}
    host.innerHTML='<details><summary><strong>Offene Korrekturen · '+tasks.length+'</strong></summary>'
      +tasks.map(t=>'<div class="meta-task">'
      +'<div><strong>'+esc(t.source_filename)+'</strong></div>'
      +'<div class="muted">'+esc(t.proposed_datetime||"")+'</div>'
      +(t.error_message?'<div class="danger">'+esc(t.error_message)+'</div>':'')
      +'<div class="meta-actions" style="margin-top:8px"><button class="primary" data-meta-apply="'+esc(t.id)+'">Jetzt ausführen</button>'
      +'<button data-meta-cancel="'+esc(t.id)+'">Verwerfen</button></div></div>').join("")
      +'</details>';
    host.querySelectorAll("[data-meta-apply]").forEach(b=>b.addEventListener("click",()=>applyTask(b.dataset.metaApply)));
    host.querySelectorAll("[data-meta-cancel]").forEach(b=>b.addEventListener("click",()=>cancelTask(b.dataset.metaCancel)));
  }
  async function applyTask(id){
    const question=state.area==="library"
      ?"Metadaten familienweise schreiben und vollständig prüfen? Die Familie bleibt danach in Ohne_Datum."
      :"Metadaten in einer Arbeitskopie schreiben, prüfen und die Datei danach atomar ersetzen?";
    if(!confirm(question))return;
    setStatus("Korrektur wird geschrieben und vollständig geprüft …");
    try{
      await json("/api/metadata-correction/tasks/"+encodeURIComponent(id)+"/apply",{method:"POST"});
      setStatus(state.area==="library"?"Korrektur geprüft. Die Familie kann jetzt separat einsortiert werden.":"Korrektur vollständig geschrieben und geprüft.");
      await scan(false,true);await loadTasks();
    }catch(error){setStatus(error.message,true);await loadTasks();}
  }
  async function cancelTask(id){
    try{await json("/api/metadata-correction/tasks/"+encodeURIComponent(id)+"/cancel",{method:"POST"});await loadTasks();}
    catch(error){setStatus(error.message,true);}
  }
  async function scan(announce=true,preserve=true){
    if(state.area==="multiple")return false;
    const snapshot=preserve?selectionKeys():{keys:new Set(),primary:null,last:null};
    if(announce)setStatus(state.area==="library"?"Ohne-Datum-Bestand wird gelesen …":"Ordner und Metadaten werden gelesen …");
    try{
      state.scan=await json("/api/metadata-correction/scan?area="+encodeURIComponent(state.area));
      restoreSelection(snapshot);
      renderFiles();renderDetails();
      if(announce)setStatus("Prüfung abgeschlossen. Es wurde noch nichts verändert.");
      return true;
    }catch(error){
      if(announce)setStatus(error.message,true);
      return false;
    }
  }
  $("meta-select-all").addEventListener("click",()=>{
    const files=state.scan?.files||[];
    if(files.length&&state.selectedSet.size===files.length){
      state.selectedSet.clear();
    }else{
      state.selectedSet=new Set(files.map((_,index)=>index));
      if(files.length&&state.selected===null)state.selected=0;
    }
    renderFiles();renderDetails();
  });
  $("meta-scan").addEventListener("click",()=>scan(true,true));
  configureArea();
  updateSelectAllButton();
  loadAreas();
  loadTasks();
})();
</script>
</body>
</html>"""
