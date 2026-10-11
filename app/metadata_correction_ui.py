METADATA_CORRECTION_HTML = r"""<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Metadatenkorrektur</title>
<style>
[hidden]{display:none!important}
main{width:min(1180px,100%);margin:0 auto;padding:18px 30px 70px}
.muted{color:var(--bk-muted,#738091)}
.meta-actions{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
.meta-actions button,.meta-card button{min-height:40px;border:1px solid var(--bk-line,#ccd2d8);border-radius:11px;padding:8px 13px;background:var(--bk-surface,#fff);color:inherit}
.primary{background:var(--bk-blue,#1976d2)!important;color:#fff!important;border-color:var(--bk-blue,#1976d2)!important}
.meta-grid{display:grid;grid-template-columns:minmax(0,1.4fr) minmax(330px,.8fr);gap:16px;align-items:start}
.meta-card{border:1px solid var(--bk-line,#ccd2d8);border-radius:15px;background:var(--bk-surface,#fff);padding:16px}
.meta-overview{margin-bottom:18px}
.meta-title-with-help{display:flex;align-items:center;gap:8px;min-width:0}
.meta-paths{display:grid;gap:5px;font-size:.86rem;margin:9px 0 0;min-width:0}
.meta-paths span,.meta-paths code{min-width:0;max-width:100%;white-space:normal;overflow-wrap:anywhere;word-break:break-word}
.meta-groups{display:grid;gap:14px;margin-top:14px}
.meta-files{display:grid;gap:8px}
.meta-file{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:10px;align-items:center;text-align:left;width:100%;box-sizing:border-box;border:1px solid var(--bk-line,#ccd2d8);border-radius:12px;padding:11px 13px;background:var(--bk-surface,#fff);color:inherit;cursor:pointer;user-select:none;-webkit-user-select:none}
.meta-file.selectable{grid-template-columns:auto minmax(0,1fr) auto}
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
.meta-candidate{border:1px solid var(--bk-line,#ccd2d8);border-radius:11px;padding:10px 11px;display:grid;gap:5px;background:var(--bk-surface-2,#f5f5f5)}
.meta-candidate-head{display:flex;justify-content:space-between;align-items:center;gap:8px}
.meta-candidate small{overflow-wrap:anywhere}
.meta-candidate button{min-height:30px!important;padding:4px 9px!important;font-size:.82rem}
.meta-candidate-list{display:grid;gap:8px}
.meta-form select{min-height:40px;border:1px solid var(--bk-line,#ccd2d8);border-radius:10px;padding:8px 10px;background:var(--bk-surface-2,#fff);color:inherit}
.multi-preview{display:grid;gap:8px;margin-top:12px}
.multi-preview-row{display:grid;grid-template-columns:minmax(0,1.2fr) minmax(130px,.8fr) auto minmax(130px,.8fr);gap:10px;align-items:center;border:1px solid var(--bk-line,#ccd2d8);border-radius:10px;padding:9px 11px}
.multi-offset{font-variant-numeric:tabular-nums}
@media(min-width:821px){
  #meta-detail-card,
  #multi-detail-card{
    position:sticky;
    top:calc(var(--bk-secondary-sticky-bottom,141px) + 12px);
    max-height:calc(100dvh - var(--bk-secondary-sticky-bottom,141px) - 24px);
    overflow:auto;
    overscroll-behavior:contain;
    scrollbar-gutter:stable;
  }
}
@media(max-width:820px){.multi-preview-row{grid-template-columns:1fr}.multi-preview-row .arrow{display:none}}
@media(max-width:820px){main{padding:14px 14px 60px}.meta-grid{grid-template-columns:1fr;gap:18px}.meta-kv{grid-template-columns:105px minmax(0,1fr)}.meta-card{padding:14px}.meta-paths{font-size:.78rem}}
</style>
</head>
<body>
<main>
  <section class="meta-card meta-overview">
    <div style="display:flex;justify-content:space-between;gap:12px;align-items:flex-start;flex-wrap:wrap">
      <div class="meta-title-with-help">
        <strong id="meta-area-title" class="bk-title-help" tabindex="0" role="button" aria-expanded="false" data-bk-title-help data-help="">Bibliothek</strong>
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
          <button id="meta-select-mode" type="button">Auswählen</button>
          <button id="meta-select-all" type="button" hidden title="Mehrere Einträge lassen sich auch mit Umschalt (Shift) auswählen.">Alle auswählen</button>
        </div>
      </div>
      <div id="meta-files" class="meta-groups"><div class="muted">Prüfung starten.</div></div>
    </section>

    <aside class="meta-card" id="meta-detail-card">
      <strong>Datei prüfen</strong>
      <div id="meta-details" class="muted" style="margin-top:12px">Links eine Datei auswählen.</div>
      <div id="meta-open-tasks" class="meta-task"></div>
    </aside>
  </div>

  <section id="meta-multiple-workspace" hidden>
    <div class="meta-grid">
      <section class="meta-card">
        <div style="display:flex;justify-content:space-between;gap:8px;align-items:center;flex-wrap:wrap">
          <strong>Dateien im Ordner Mehrfachkorrektur</strong>
          <div class="meta-actions">
            <span id="multi-summary" class="muted">Noch nicht geprüft</span>
            <button id="multi-select-mode" type="button">Auswählen</button>
            <button id="multi-select-all" type="button" hidden>Alle auswählen</button>
          </div>
        </div>
        <div id="multi-files" class="meta-groups"><div class="muted">Bestand prüfen.</div></div>
      </section>
      <aside class="meta-card" id="multi-detail-card">
        <strong>Referenzaufnahme</strong>
        <div id="multi-details" class="muted" style="margin-top:12px">Links die Aufnahme auswählen, deren tatsächliche Zeit bekannt ist.</div>
      </aside>
    </div>
    <section id="multi-preview-card" class="meta-card" style="margin-top:16px" hidden>
      <div style="display:flex;justify-content:space-between;gap:10px;align-items:center;flex-wrap:wrap">
        <div>
          <strong>Vorschau</strong>
          <div id="multi-offset" class="muted multi-offset" style="margin-top:4px"></div>
        </div>
        <div class="meta-actions">
          <button id="multi-apply" type="button">Anwenden</button>
          <button id="multi-apply-import" type="button" class="primary">Anwenden und in Tagesbestand übernehmen</button>
        </div>
      </div>
      <div id="multi-preview" class="multi-preview"></div>
    </section>
  </section>

  <dialog id="meta-mobile-dialog">
    <div class="meta-mobile-dialog-head">
      <strong id="meta-mobile-dialog-title">Datei prüfen</strong>
      <button id="meta-mobile-dialog-close" class="meta-mobile-dialog-close" type="button">Schließen</button>
    </div>
    <div id="meta-mobile-dialog-body" class="meta-mobile-dialog-body"></div>
  </dialog>
</main>
<script>
(()=>{
  const params=new URLSearchParams(location.search);
  const requested=String(params.get("area")||"library");
  const state={
    area:["library","general","multiple"].includes(requested)?requested:"library",
    scan:null,selected:null,selectedSet:new Set(),lastSelected:null,selectionMode:false,tasks:[],areas:null,
    multipleReference:null,multiplePreview:null,multipleSelectedSet:new Set(),multipleSelectionMode:false
  };
  const $=id=>document.getElementById(id);
  const isMobileWebApp=()=>(
    document.documentElement.dataset.bkDisplayMode==="standalone"
    && Boolean(window.matchMedia?.("(max-width: 820px)")?.matches)
  );
  const mobileDetail={node:null,parent:null,next:null,mode:null,kind:null};
  function clearMobileSelectionSheetClearance(){
    document.body?.classList.remove("bk-meta-selection-sheet-open");
    document.documentElement.style.removeProperty("--bk-meta-selection-sheet-height");
  }
  function updateMobileSelectionSheetClearance(){
    const dialog=$("meta-mobile-dialog");
    if(
      !isMobileWebApp()
      || !dialog?.open
      || !dialog.classList.contains("compact-selection")
    ){
      clearMobileSelectionSheetClearance();
      return;
    }
    document.body?.classList.add("bk-meta-selection-sheet-open");
    window.requestAnimationFrame(()=>{
      if(!dialog.open||!dialog.classList.contains("compact-selection"))return;
      const height=Math.ceil(dialog.getBoundingClientRect().height);
      document.documentElement.style.setProperty(
        "--bk-meta-selection-sheet-height",
        Math.max(0,height)+"px"
      );
    });
  }
  function closeMobileDetail(){
    const dialog=$("meta-mobile-dialog");
    if(dialog?.open)dialog.close();
    if(mobileDetail.node&&mobileDetail.parent){
      if(mobileDetail.next&&mobileDetail.next.parentNode===mobileDetail.parent){
        mobileDetail.parent.insertBefore(mobileDetail.node,mobileDetail.next);
      }else{
        mobileDetail.parent.appendChild(mobileDetail.node);
      }
    }
    mobileDetail.node=null;mobileDetail.parent=null;mobileDetail.next=null;
    mobileDetail.mode=null;mobileDetail.kind=null;
    dialog?.classList.remove("full-detail","compact-selection");
    clearMobileSelectionSheetClearance();
  }
  function openMobileDetail(kind,mode="full"){
    if(!isMobileWebApp())return;
    const dialog=$("meta-mobile-dialog");
    const body=$("meta-mobile-dialog-body");
    const node=$(kind==="multiple"?"multi-detail-card":"meta-detail-card");
    if(!dialog||!body||!node)return;
    const normalizedMode=mode==="compact"?"compact":"full";
    if(
      mobileDetail.node
      && (
        mobileDetail.node!==node
        || mobileDetail.mode!==normalizedMode
      )
    )closeMobileDetail();
    if(!mobileDetail.node){
      mobileDetail.node=node;
      mobileDetail.parent=node.parentNode;
      mobileDetail.next=node.nextSibling;
      mobileDetail.mode=normalizedMode;
      mobileDetail.kind=kind;
      body.appendChild(node);
    }
    dialog.classList.toggle("full-detail",normalizedMode==="full");
    dialog.classList.toggle("compact-selection",normalizedMode==="compact");
    $("meta-mobile-dialog-title").textContent=normalizedMode==="compact"
      ? (kind==="multiple"?"Auswahl · Referenzaufnahme":"Auswahl")
      : (kind==="multiple"?"Referenzaufnahme":"Datei prüfen");
    if(!dialog.open){
      if(normalizedMode==="compact")dialog.show();
      else dialog.showModal();
    }
    if(normalizedMode==="compact")updateMobileSelectionSheetClearance();
    else clearMobileSelectionSheetClearance();
  }
  function syncMobileSelectionDetail(kind,count){
    if(!isMobileWebApp())return;
    const dialog=$("meta-mobile-dialog");
    if(Number(count||0)>1){
      openMobileDetail(kind,"compact");
    }else if(dialog?.open&&dialog.classList.contains("compact-selection")){
      closeMobileDetail();
    }
  }
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
  function setScanBusy(busy){
    const button=$("meta-scan");
    const status=$("meta-status");
    if(button){
      button.disabled=Boolean(busy);
      button.classList.toggle("bk-busy",Boolean(busy));
      if(busy)button.setAttribute("aria-busy","true");
      else button.removeAttribute("aria-busy");
    }
    if(status)status.classList.toggle("bk-loading-status",Boolean(busy));
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
  function usableCandidates(file){
    return (file?.metadata_candidates||[])
      .filter(candidate=>candidate&&candidate.usable&&candidate.normalized_datetime)
      .sort((a,b)=>(Number(a.priority||999)-Number(b.priority||999))||String(a.tag_name||"").localeCompare(String(b.tag_name||"")));
  }
  function candidateSourceType(candidate){
    return String(candidate?.source_type||candidate?.tag_name||"").split(":").pop();
  }
  function candidateLabel(candidate){
    return String(candidate?.label_de||candidateSourceType(candidate)||"Metadaten");
  }
  function candidateForType(file,type){
    return usableCandidates(file).find(candidate=>candidateSourceType(candidate)===type)||null;
  }
  function preferredMetadataCandidate(file){
    const candidates=usableCandidates(file);
    return candidates.find(candidate=>candidate.is_selected)||candidates[0]||null;
  }
  function commonSourceTypes(files){
    if(!files.length)return [];
    const maps=files.map(file=>{
      const map=new Map();
      for(const candidate of usableCandidates(file)){
        const type=candidateSourceType(candidate);
        if(type&&!map.has(type))map.set(type,candidate);
      }
      return map;
    });
    return [...maps[0].keys()]
      .filter(type=>maps.every(map=>map.has(type)))
      .map(type=>maps[0].get(type))
      .sort((a,b)=>Number(a.priority||999)-Number(b.priority||999));
  }
  function formatCandidate(candidate){
    if(!candidate)return "";
    const trust=candidate.trust_label||candidate.confidence||"";
    return '<div class="meta-candidate"><div class="meta-candidate-head"><strong>'+esc(candidateLabel(candidate))+'</strong>'
      +'<button type="button" data-meta-use-candidate="'+esc(candidate.tag_name||"")+'">Übernehmen</button></div>'
      +'<span>'+esc(String(candidate.normalized_datetime||"").slice(0,19))+'</span>'
      +'<small class="muted">Vertrauen: '+esc(trust)+(candidate.trust_score!==undefined?" · "+esc(candidate.trust_score)+"/100":"")+'</small>'
      +'<small class="muted"><code>'+esc(candidate.technical_tag||candidate.tag_name||"")+'</code></small></div>';
  }
  function configureArea(){
    const library=state.area==="library", general=state.area==="general", multiple=state.area==="multiple";
    $("meta-area-title").textContent=library?"Bibliothek":general?"Allgemein":"Mehrfachkorrektur";
    const areaHelp=library
      ?"Gemeinsamer Ohne-Datum-Bestand aller Kamerasicherungen: erst Metadaten prüfen oder korrigieren, danach bewusst einsortieren."
      : general
        ?"Unabhängige Dateien direkt im verwalteten Ordner Allgemein korrigieren."
        :"Zeitlich zusammengehörige Kameraaufnahmen gemeinsam verschieben. Eine Referenzaufnahme festlegen, Vorschau prüfen und den Zeitversatz anschließend auf den gesamten Ordner anwenden.";
    $("meta-area-title").dataset.help=areaHelp;
    $("meta-area-title").setAttribute("aria-label","Hilfe zu "+(library?"Bibliothek":general?"Allgemein":"Mehrfachkorrektur"));
    $("meta-scan").hidden=false;
    $("meta-scan").textContent=multiple?"Bestand prüfen":"Bestand prüfen";
    $("meta-workspace").hidden=multiple;
    $("meta-multiple-workspace").hidden=!multiple;
    $("meta-list-title").textContent=library?"Ohne-Datum-Bestand":"Dateien im Ordner Allgemein";
  }
  async function loadAreas(){
    try{
      state.areas=(await json("/api/metadata-correction/areas")).areas||{};
      const area=state.areas[state.area]||{};
      if(state.area==="library"){
        $("meta-paths").innerHTML='<span>Quelle: <code>'+esc(area.source_root||"Ohne_Datum")+'</code></span>';
      }else if(state.area==="general"){
        $("meta-paths").innerHTML='<span>Ordner: <code>'+esc(area.root||"")+'</code></span>';
      }else{
        $("meta-paths").innerHTML='<span>Ordner: <code>'+esc(area.root||"/workspace/Metadatenkorrektur/Mehrfachkorrektur")+'</code></span>';
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
    const checkbox=state.selectionMode
      ? '<input class="meta-file-check" data-meta-check="'+index+'" type="checkbox" '+(checked?"checked":"")+' aria-label="Datei auswählen">'
      : "";
    return '<div class="meta-file '+(state.selectionMode?"selectable ":"")+(state.selected===index?"active ":"")+(checked?"selected":"")+'" data-meta-file="'+index+'" data-bk-pwa-select="metadata-file" data-bk-pwa-key="'+esc(fileKey(file))+'" role="button" tabindex="0">'
      +checkbox
      +'<span><strong>'+esc(file.filename)+'</strong><small class="muted">'+esc(file.relative_path||"")+memberText+'</small>'
      +'<small class="muted">Aktuell: '+esc(file.selected_capture_time||"kein belastbares Datum")+'</small></span>'
      +'<span class="badge '+cls+'">'+esc(badge)+'</span></div>';
  }
  function updateSelectionControls(){
    const files=state.scan?.files||[];
    const all=files.length>0&&state.selectedSet.size===files.length;
    $("meta-select-mode").textContent=state.selectionMode?"Auswahl beenden":"Auswählen";
    $("meta-select-all").hidden=!state.selectionMode;
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
  function activateMetaSelectionModeInPlace(index,desired=true){
    const files=state.scan?.files||[];
    state.selectionMode=true;
    state.selectedSet.clear();
    state.selected=index;
    state.lastSelected=index;
    if(desired)state.selectedSet.add(index);

    document.querySelectorAll("[data-meta-file]").forEach(row=>{
      const rowIndex=Number(row.dataset.metaFile);
      row.classList.add("selectable");
      row.classList.toggle("selected",state.selectedSet.has(rowIndex));
      let checkbox=row.querySelector("[data-meta-check]");
      if(!checkbox){
        checkbox=document.createElement("input");
        checkbox.className="meta-file-check";
        checkbox.dataset.metaCheck=String(rowIndex);
        checkbox.type="checkbox";
        checkbox.setAttribute("aria-label","Datei auswählen");
        row.prepend(checkbox);
      }
      checkbox.checked=state.selectedSet.has(rowIndex);
    });

    const fileCount=Number(state.scan?.summary?.file_count ?? files.length);
    const familyCount=Number(state.scan?.summary?.family_count ?? files.length);
    $("meta-summary").textContent=state.area==="library"
      ? familyCount+" Familien · "+fileCount+" Dateien · "+state.selectedSet.size+" ausgewählt"
      : files.length+" Datei"+(files.length===1?"":"en")+" · "+state.selectedSet.size+" ausgewählt";
    updateSelectionControls();
    renderDetails();
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
      updateSelectionControls();return;
    }
    $("meta-files").innerHTML='<div class="meta-files">'+files.map(fileRow).join("")+'</div>';
    document.querySelectorAll("[data-meta-file]").forEach(row=>{
      const index=Number(row.dataset.metaFile);
      row.addEventListener("mousedown",event=>{
        if(event.shiftKey && !event.target.closest("input,button"))event.preventDefault();
      });
      row.addEventListener("bk:pwa-select",event=>{
        const phase=String(event.detail?.phase||"");
        if(phase==="end"){
          renderFiles();renderDetails();
          syncMobileSelectionDetail("meta",state.selectedSet.size);
          return;
        }
        const desired=phase==="set"
          ? Boolean(event.detail?.selected)
          : true;
        if(phase==="start"&&!state.selectionMode){
          activateMetaSelectionModeInPlace(index,desired);
          return;
        }
        if(desired)state.selectedSet.add(index);
        else state.selectedSet.delete(index);
        if(desired)state.selected=index;
        state.lastSelected=index;
        const checkbox=row.querySelector("[data-meta-check]");
        if(checkbox)checkbox.checked=desired;
        row.classList.toggle("selected",desired);
        row.classList.add("selectable");
        updateSelectionControls();
        renderDetails();
      });
      row.addEventListener("click",event=>{
        if(event.target.closest("[data-meta-check]"))return;
        state.selected=index;
        if(state.selectionMode){
          if(event.shiftKey){
            selectRange(index,true);
          }else if(state.selectedSet.has(index)){
            state.selectedSet.delete(index);
          }else{
            state.selectedSet.add(index);
          }
          state.lastSelected=index;
        }
        renderFiles();renderDetails();
        if(!state.selectionMode)openMobileDetail("meta","full");
        else syncMobileSelectionDetail("meta",state.selectedSet.size);
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
    updateSelectionControls();
  }
  function selectedFiles(){
    const files=state.scan?.files||[];
    const indices=state.selectionMode
      ? [...state.selectedSet]
      : (Number.isInteger(state.selected)?[state.selected]:[]);
    return indices.map(index=>files[index]).filter(Boolean);
  }
  function selectedReadyFiles(){
    const files=selectedFiles();
    return files.length&&files.every(file=>file.reintegration_ready)?files:[];
  }
  function renderBulkDetails(files){
    const sourceTypes=commonSourceTypes(files);
    const options=sourceTypes.map(candidate=>
      '<option value="'+esc(candidateSourceType(candidate))+'">'+esc(candidateLabel(candidate))+'</option>'
    ).join("");
    const readyFiles=state.area==="library"&&files.every(file=>file.reintegration_ready)?files:[];
    const generalReady=state.area==="general"&&files.every(file=>
      Boolean(file.selected_capture_time)&&["high","medium"].includes(String(file.capture_time_confidence||""))
    );
    $("meta-details").innerHTML='<div class="meta-form">'
      +'<div class="meta-selection-note"><strong>'+files.length+' Einträge ausgewählt.</strong><div class="muted" style="margin-top:4px">Für jede Datei wird ihr eigener Wert des gewählten Metadaten-Tags verwendet.</div></div>'
      +(sourceTypes.length
        ? '<label><span>Gemeinsamer Metadaten-Quelltyp</span><select id="meta-bulk-source">'+options+'</select></label>'
          +'<button id="meta-bulk-apply" type="button" class="primary">Metadatenquelle übernehmen ('+files.length+')</button>'
        : '<div class="danger">Die ausgewählten Dateien besitzen keinen gemeinsamen nutzbaren Metadaten-Quelltyp.</div>')
      +(readyFiles.length
        ? '<button id="meta-reintegrate" type="button">In Tagesbestand einsortieren ('+readyFiles.length+')</button>'
        : '')
      +(generalReady
        ? '<button id="meta-general-reintegrate" type="button">In Tagesbestand übernehmen ('+files.length+')</button>'
        : '')
      +'</div>';
    $("meta-bulk-apply")?.addEventListener("click",()=>correctSelectedBySource(files));
    $("meta-reintegrate")?.addEventListener("click",reintegrateSelected);
    $("meta-general-reintegrate")?.addEventListener("click",()=>reintegrateGeneralSelected(files));
  }
  function renderDetails(){
    const chosen=selectedFiles();
    if(state.selectionMode&&chosen.length>1){renderBulkDetails(chosen);return;}
    const file=chosen[0]||(state.scan?.files||[])[state.selected];
    if(!file){$("meta-details").innerHTML='<div class="muted">Links eine Datei auswählen.</div>';return;}
    const hint=bestSuggestion(file), suggested=splitSuggestion(hint), filename=file.filename_suggestion;
    const familyLine=state.area==="library"
      ? '<span>Familie</span><span>'+esc(file.member_count||1)+' Dateien</span>'
      :"";
    const ready=state.area==="library"&&file.reintegration_ready;
    const readyFiles=selectedReadyFiles();
    const preferred=preferredMetadataCandidate(file);
    const others=usableCandidates(file).filter(candidate=>!preferred||candidate.tag_name!==preferred.tag_name);
    const firstOthers=others.slice(0,3);
    const remaining=others.slice(3);
    const original=file.original_metadata?.before_metadata||null;
    const originalCandidates=(original?.metadata_candidates||[]).filter(Boolean);
    const originalCandidateRows=originalCandidates.length
      ? '<div class="meta-candidate-list" style="margin-top:9px">'+originalCandidates.map(candidate=>
          '<div class="meta-candidate"><strong>'+esc(candidate.label_de||candidate.source_type||String(candidate.tag_name||"").split(":").pop()||"Metadaten")+'</strong>'
          +'<span>'+esc(String(candidate.normalized_datetime||candidate.raw_value||"nicht nutzbar").slice(0,80))+'</span>'
          +'<small class="muted"><code>'+esc(candidate.technical_tag||candidate.tag_name||"")+'</code></small></div>'
        ).join("")+'</div>'
      : "";
    const originalBlock=original
      ? '<details><summary>Ursprüngliche Metadaten vor der Korrektur</summary><div class="meta-kv" style="margin-top:9px">'
        +'<span>Aufnahmezeit</span><span>'+esc(original.selected_capture_time||"nicht vorhanden")+'</span>'
        +'<span>Quelle</span><span>'+esc(original.selected_capture_source||"—")+'</span>'
        +'<span>Vertrauen</span><span>'+esc(original.capture_time_confidence||"—")+'</span></div>'
        +originalCandidateRows+'</details>'
      : "";
    const candidateBlock='<div><strong>Bevorzugter Metadatenkandidat</strong><div class="meta-candidate-list" style="margin-top:7px">'
      +(preferred?formatCandidate(preferred):'<div class="muted">Kein nutzbarer Metadatenkandidat vorhanden.</div>')+'</div></div>'
      +(firstOthers.length
        ? '<details><summary>Weitere Metadaten</summary><div class="meta-candidate-list" style="margin-top:8px">'+firstOthers.map(formatCandidate).join("")+'</div>'
          +(remaining.length?'<details style="margin-top:8px"><summary>Weitere anzeigen ('+remaining.length+')</summary><div class="meta-candidate-list" style="margin-top:8px">'+remaining.map(formatCandidate).join("")+'</div></details>':'')
          +'</details>'
        : '');
    const sortButton=state.area==="library"&&readyFiles.length
      ? '<button id="meta-reintegrate" type="button">In Tagesbestand einsortieren</button>'
      :"";
    const generalSortButton=(
      state.area==="general"
      && file.selected_capture_time
      && ["high","medium"].includes(String(file.capture_time_confidence||""))
    ) ? '<button id="meta-general-reintegrate" type="button">In Tagesbestand übernehmen</button>' : "";
    $("meta-details").innerHTML='<div class="meta-form"><div class="meta-kv">'
      +'<span>Datei</span><strong>'+esc(file.filename)+'</strong>'+familyLine
      +'<span>Metadaten</span><span>'+esc(file.selected_capture_time||"kein belastbares Datum")+' · '+esc(file.capture_time_confidence||"")+'</span>'
      +'<span>Status</span><span>'+(ready?"korrigiert · wartet auf Einsortierung":"Prüfung/Korrektur erforderlich")+'</span>'
      +'<span>Dateiname</span><span>'+(filename?(esc(filename.date)+(filename.time?" "+esc(filename.time):" · Uhrzeit fehlt")):"kein Datum erkannt")+'</span></div>'
      +candidateBlock+originalBlock
      +'<label><span>Datum</span><input id="meta-date" type="date" value="'+esc(suggested.date)+'"></label>'
      +'<label><span>Uhrzeit</span><input id="meta-time" type="time" step="1" value="'+esc(suggested.time)+'"></label>'
      +'<button id="meta-prepare" type="button" class="primary">'+(ready?"Metadaten erneut ändern":"Metadaten ändern")+'</button>'
      +sortButton+generalSortButton+'</div>';
    document.querySelectorAll("[data-meta-use-candidate]").forEach(button=>button.addEventListener("click",()=>{
      const candidate=(file.metadata_candidates||[]).find(item=>String(item.tag_name||"")===String(button.dataset.metaUseCandidate||""));
      if(!candidate)return;
      const value=String(candidate.normalized_datetime||"").slice(0,19);
      if($("meta-date")){
        $("meta-date").value=value.slice(0,10);
        $("meta-date").dataset.sourceTag=String(candidate.tag_name||"");
      }
      if($("meta-time"))$("meta-time").value=value.slice(11,19);
    }));
    ["meta-date","meta-time"].forEach(id=>$(id)?.addEventListener("input",()=>{
      if($("meta-date"))delete $("meta-date").dataset.sourceTag;
    }));
    $("meta-prepare").addEventListener("click",()=>correctSelected(file));
    $("meta-reintegrate")?.addEventListener("click",reintegrateSelected);
    $("meta-general-reintegrate")?.addEventListener("click",()=>reintegrateGeneralSelected([file]));
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
    const date=$("meta-date")?.value||"",time=$("meta-time")?.value||"";
    if(!date||!time){setStatus("Datum und Uhrzeit müssen vollständig angegeben werden.",true);return;}
    const button=$("meta-prepare");
    if(button)button.disabled=true;
    setStatus("Metadaten werden geändert …");
    try{
      const payload={area:state.area,relative_path:file.relative_path,proposed_datetime:date+"T"+time};
      const sourceTag=String($("meta-date")?.dataset?.sourceTag||"");
      if(sourceTag)payload.proposal_source_tag=sourceTag;
      if(state.area==="library"){payload.library_id=file.library_id;payload.family_id=file.family_id;}
      await json("/api/metadata-correction/correct",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
      closeMobileDetail();
      await scan(false,true);
      await loadTasks(true);
      setStatus(state.area==="library"?"Metadaten geändert. Bereit zum Einsortieren.":"Metadaten geändert und geprüft.");
    }catch(error){
      await scan(false,true);
      await loadTasks(true);
      setStatus(error.message,true);
    }finally{
      const current=$("meta-prepare");
      if(current)current.disabled=false;
    }
  }
  async function correctSelectedBySource(files){
    const type=$("meta-bulk-source")?.value||"";
    if(!type||!files.length)return;
    const prepared=files.map(file=>({file,candidate:candidateForType(file,type)}));
    if(prepared.some(item=>!item.candidate)){
      setStatus("Mindestens eine ausgewählte Datei besitzt diesen Metadaten-Quelltyp nicht mehr.",true);return;
    }
    const button=$("meta-bulk-apply");
    if(button){button.disabled=true;button.classList.add("bk-busy");button.setAttribute("aria-busy","true");}
    setStatus(files.length+" Einträge werden mit ihrem jeweiligen "+type+"-Wert korrigiert …");
    try{
      const items=files.map(file=>state.area==="library"
        ? {library_id:file.library_id,family_id:file.family_id,relative_path:file.relative_path}
        : {relative_path:file.relative_path});
      const data=await json("/api/metadata-correction/correct-batch",{
        method:"POST",headers:{"Content-Type":"application/json"},
        body:JSON.stringify({area:state.area,source_type:type,items})
      });
      await scan(false,true);await loadTasks(true);
      setStatus(Number(data.count||files.length)+" Einträge mit ihren eigenen "+type+"-Werten korrigiert.");
    }catch(error){
      await scan(false,true);await loadTasks(true);
      setStatus(error.message,true);
    }finally{
      const current=$("meta-bulk-apply");
      if(current){current.disabled=false;current.classList.remove("bk-busy");current.removeAttribute("aria-busy");}
    }
  }
  async function reintegrateGeneralSelected(files){
    const selected=(files&&files.length)?files:selectedFiles();
    if(!selected.length){setStatus("Bitte mindestens eine Allgemein-Datei auswählen.",true);return;}
    const invalid=selected.filter(file=>
      !file.selected_capture_time||!["high","medium"].includes(String(file.capture_time_confidence||""))
    );
    if(invalid.length){
      setStatus("Vor der Übernahme müssen alle ausgewählten Dateien eine belastbare Aufnahmezeit besitzen.",true);return;
    }
    const button=$("meta-general-reintegrate");
    if(button){button.disabled=true;button.classList.add("bk-busy");}
    setStatus(selected.length===1?"Übernahme in den Tagesbestand wird vorbereitet …":selected.length+" Dateien werden für den Tagesbestand vorbereitet …");
    try{
      const data=await json("/api/metadata-correction/general/reintegrate",{
        method:"POST",headers:{"Content-Type":"application/json"},
        body:JSON.stringify({items:selected.map(file=>({relative_path:file.relative_path}))})
      });
      closeMobileDetail();
      setStatus((data.file_count||selected.length)+" Datei"+((data.file_count||selected.length)===1?"":"en")+" zur verifizierten Übernahme in den Tagesbestand vorgemerkt.");
    }catch(error){
      setStatus(error.message,true);
    }finally{
      const current=$("meta-general-reintegrate");
      if(current){current.disabled=false;current.classList.remove("bk-busy");}
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
      closeMobileDetail();
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
    if(!(await window.BibliothekarI18n.confirmAsync(question)))return;
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
  function updateMultipleSelectionControls(){
    const files=state.scan?.files||[];
    const all=files.length>0&&state.multipleSelectedSet.size===files.length;
    $("multi-select-mode").textContent=state.multipleSelectionMode?"Auswahl beenden":"Auswählen";
    $("multi-select-all").hidden=!state.multipleSelectionMode;
    $("multi-select-all").textContent=all?"Auswahl aufheben":"Alle auswählen";
    $("multi-select-all").disabled=!files.length;
  }
  function activateMultipleSelectionModeInPlace(index,desired=true){
    const files=state.scan?.files||[];
    state.multipleSelectionMode=true;
    state.multipleSelectedSet.clear();
    state.multipleReference=index;
    if(desired)state.multipleSelectedSet.add(index);
    state.multiplePreview=null;
    $("multi-preview-card").hidden=true;

    document.querySelectorAll("[data-multi-file]").forEach(row=>{
      const rowIndex=Number(row.dataset.multiFile);
      row.classList.add("selectable");
      row.classList.toggle("selected",state.multipleSelectedSet.has(rowIndex));
      let checkbox=row.querySelector("[data-multi-check]");
      if(!checkbox){
        checkbox=document.createElement("input");
        checkbox.className="meta-file-check";
        checkbox.dataset.multiCheck=String(rowIndex);
        checkbox.type="checkbox";
        checkbox.setAttribute("aria-label","Datei auswählen");
        const marker=row.firstElementChild;
        if(marker?.tagName==="SPAN")marker.replaceWith(checkbox);
        else row.prepend(checkbox);
      }
      checkbox.checked=state.multipleSelectedSet.has(rowIndex);
    });

    $("multi-summary").textContent=files.length+" Datei"+(files.length===1?"":"en")
      +" · "+state.multipleSelectedSet.size+" ausgewählt";
    updateMultipleSelectionControls();
    renderMultipleDetails();
  }
  function renderMultipleFiles(){
    const files=state.scan?.files||[];
    for(const index of [...state.multipleSelectedSet]){
      if(index<0||index>=files.length)state.multipleSelectedSet.delete(index);
    }
    const multipleChosen=state.multipleSelectedSet.size;
    $("multi-summary").textContent=files.length+" Datei"+(files.length===1?"":"en")
      +(multipleChosen?" · "+multipleChosen+" ausgewählt":"");
    updateMultipleSelectionControls();
    if(!files.length){
      $("multi-files").innerHTML='<div class="muted">Der Ordner ist leer.</div>';
      $("multi-details").innerHTML='<div class="muted">Dateien in den verwalteten Ordner legen und erneut prüfen.</div>';
      $("multi-preview-card").hidden=true;
      return;
    }
    $("multi-files").innerHTML='<div class="meta-files">'+files.map((file,index)=>{
      const active=state.multipleReference===index;
      const quickSelected=state.multipleSelectedSet.has(index);
      const confidence=String(file.capture_time_confidence||"missing");
      const badge=file.usable_time?(confidence==="high"?"Metadaten sicher":"Zeit vorhanden"):"Keine Aufnahmezeit";
      const cls=file.usable_time?(confidence==="high"?"good":"warn"):"danger";
      const selector=state.multipleSelectionMode
        ? '<input class="meta-file-check" data-multi-check="'+index+'" type="checkbox" '+(quickSelected?"checked":"")+' aria-label="Datei auswählen">'
        : '<span style="width:19px;text-align:center">'+(active?"●":"○")+'</span>';
      return '<div class="meta-file '+(state.multipleSelectionMode?"selectable ":"")+(active?"active ":"")+(quickSelected?"selected ":"")+'" data-multi-file="'+index+'" data-bk-pwa-select="metadata-multiple" data-bk-pwa-key="'+esc(file.relative_path||String(index))+'" role="button" tabindex="0">'
        +selector
        +'<span><strong>'+esc(file.filename)+'</strong><small class="muted">'+esc(file.relative_path||"")+'</small>'
        +'<small class="muted">Aktuell: '+esc(file.selected_capture_time||"keine Aufnahmezeit")+'</small></span>'
        +'<span class="badge '+cls+'">'+esc(badge)+'</span></div>';
    }).join("")+'</div>';
    document.querySelectorAll("[data-multi-file]").forEach(row=>{
      const index=Number(row.dataset.multiFile);
      row.addEventListener("bk:pwa-select",event=>{
        const phase=String(event.detail?.phase||"");
        if(phase==="end"){
          renderMultipleFiles();
          renderMultipleDetails();
          syncMobileSelectionDetail("multiple",state.multipleSelectedSet.size);
          return;
        }
        const desired=phase==="set"
          ? Boolean(event.detail?.selected)
          : true;
        if(phase==="start"&&!state.multipleSelectionMode){
          activateMultipleSelectionModeInPlace(index,desired);
          return;
        }
        if(desired)state.multipleSelectedSet.add(index);
        else state.multipleSelectedSet.delete(index);
        if(desired&&(state.multipleReference===null||phase==="start")){
          state.multipleReference=index;
        }
        state.multiplePreview=null;
        $("multi-preview-card").hidden=true;
        const checkbox=row.querySelector("[data-multi-check]");
        if(checkbox)checkbox.checked=desired;
        row.classList.toggle("selected",desired);
        updateMultipleSelectionControls();
        renderMultipleDetails();
      });
      row.addEventListener("click",event=>{
        if(event.target.closest("[data-multi-check]"))return;
        state.multiplePreview=null;
        $("multi-preview-card").hidden=true;
        if(state.multipleSelectionMode){
          if(state.multipleSelectedSet.has(index)){
            state.multipleSelectedSet.delete(index);
            if(state.multipleReference===index){
              state.multipleReference=[...state.multipleSelectedSet][0]??null;
            }
          }else{
            state.multipleSelectedSet.add(index);
            if(state.multipleReference===null)state.multipleReference=index;
          }
          renderMultipleFiles();
          renderMultipleDetails();
          syncMobileSelectionDetail("multiple",state.multipleSelectedSet.size);
          return;
        }
        state.multipleReference=index;
        renderMultipleFiles();
        renderMultipleDetails();
        openMobileDetail("multiple","full");
      });
    });
    document.querySelectorAll("[data-multi-check]").forEach(check=>{
      check.addEventListener("click",event=>{
        event.stopPropagation();
        const index=Number(check.dataset.multiCheck);
        if(check.checked){
          state.multipleSelectedSet.add(index);
          if(state.multipleReference===null)state.multipleReference=index;
        }else{
          state.multipleSelectedSet.delete(index);
          if(state.multipleReference===index){
            state.multipleReference=[...state.multipleSelectedSet][0]??null;
          }
        }
        state.multiplePreview=null;
        $("multi-preview-card").hidden=true;
        renderMultipleFiles();
        renderMultipleDetails();
        syncMobileSelectionDetail("multiple",state.multipleSelectedSet.size);
      });
    });
    renderMultipleDetails();
  }
  function renderMultipleDetails(){
    const file=(state.scan?.files||[])[state.multipleReference];
    if(!file){
      $("multi-details").innerHTML='<div class="muted">Links die Aufnahme auswählen, deren tatsächliche Zeit bekannt ist.</div>';
      return;
    }
    const current=String(file.selected_capture_time||"");
    const date=current.slice(0,10),time=current.slice(11,19);
    $("multi-details").innerHTML='<div class="meta-form"><div class="meta-kv">'
      +'<span>Datei</span><strong>'+esc(file.filename)+'</strong>'
      +'<span>Aktuell</span><span>'+esc(current||"keine Aufnahmezeit")+'</span>'
      +'<span>Vertrauen</span><span>'+esc(file.capture_time_confidence||"")+'</span></div>'
      +'<label><span>Tatsächliches Datum</span><input id="multi-date" type="date" value="'+esc(date)+'"></label>'
      +'<label><span>Tatsächliche Uhrzeit</span><input id="multi-time" type="time" step="1" value="'+esc(time)+'"></label>'
      +'<button id="multi-preview-button" type="button" class="primary">Vorschau berechnen</button></div>';
    $("multi-preview-button").addEventListener("click",previewMultiple);
  }
  function formatOffset(seconds){
    const sign=seconds<0?"−":"+";
    let rest=Math.abs(Number(seconds)||0);
    const days=Math.floor(rest/86400);rest-=days*86400;
    const hours=Math.floor(rest/3600);rest-=hours*3600;
    const minutes=Math.floor(rest/60);const secs=rest-minutes*60;
    const parts=[];
    if(days)parts.push(days+" T");
    parts.push(String(hours).padStart(2,"0")+":"+String(minutes).padStart(2,"0")+":"+String(secs).padStart(2,"0"));
    return sign+" "+parts.join(" ");
  }
  function renderMultiplePreview(){
    const preview=state.multiplePreview;
    if(!preview){$("multi-preview-card").hidden=true;return;}
    $("multi-preview-card").hidden=false;
    $("multi-offset").textContent="Zeitversatz: "+formatOffset(preview.offset_seconds)+" · "+preview.file_count+" Dateien"
      +(preview.selection_is_subset?" · Auswahl aus "+preview.total_file_count:"");
    const importButton=$("multi-apply-import");
    if(importButton){
      importButton.disabled=Boolean(preview.selection_is_subset);
      importButton.title=preview.selection_is_subset
        ?"Die direkte Übernahme in den Tagesbestand ist nur für den vollständig ausgewählten Mehrfachkorrektur-Ordner möglich."
        :"";
    }
    $("multi-preview").innerHTML=(preview.files||[]).map(row=>
      '<div class="multi-preview-row"><strong>'+esc(row.filename)+'</strong>'
      +'<span>'+esc(row.old_datetime)+'</span><span class="arrow">→</span><span><strong>'+esc(row.new_datetime)+'</strong></span></div>'
    ).join("");
  }
  async function previewMultiple(){
    const file=(state.scan?.files||[])[state.multipleReference];
    const date=$("multi-date")?.value||"",time=$("multi-time")?.value||"";
    if(!file||!date||!time){setStatus("Referenzdatei, Datum und Uhrzeit müssen vollständig angegeben werden.",true);return;}
    setStatus("Vorschau wird berechnet …");
    try{
      const data=await json("/api/metadata-correction/multiple/preview",{
        method:"POST",headers:{"Content-Type":"application/json"},
        body:JSON.stringify({
          reference_relative_path:file.relative_path,
          proposed_datetime:date+"T"+time,
          selected_relative_paths:[...state.multipleSelectedSet]
            .map(index=>(state.scan?.files||[])[index]?.relative_path)
            .filter(Boolean)
        })
      });
      state.multiplePreview=data.preview;
      renderMultiplePreview();
      closeMobileDetail();
      setStatus("Vorschau berechnet. Es wurde noch nichts verändert.");
    }catch(error){state.multiplePreview=null;renderMultiplePreview();setStatus(error.message,true);}
  }
  async function applyMultiple(mode){
    const preview=state.multiplePreview;
    if(!preview){setStatus("Bitte zuerst eine Vorschau berechnen.",true);return;}
    const buttons=[$("multi-apply"),$("multi-apply-import")].filter(Boolean);
    buttons.forEach(button=>button.disabled=true);
    setStatus(mode==="apply_and_import"?"Korrektur wird angewendet und die Übernahme vorbereitet …":"Korrektur wird angewendet …");
    try{
      const data=await json("/api/metadata-correction/multiple/apply",{
        method:"POST",headers:{"Content-Type":"application/json"},
        body:JSON.stringify({
          mode,
          reference_relative_path:preview.reference_relative_path,
          proposed_datetime:preview.reference_new_datetime,
          preview_fingerprint:preview.preview_fingerprint,
          selected_relative_paths:[...state.multipleSelectedSet]
            .map(index=>(state.scan?.files||[])[index]?.relative_path)
            .filter(Boolean)
        })
      });
      state.multiplePreview=null;
      state.multipleSelectedSet.clear();
      state.multipleSelectionMode=false;
      closeMobileDetail();
      await scanMultiple(false);
      if(mode==="apply_and_import"){
        setStatus("Korrektur angewendet. Die Übernahme in den Tagesbestand läuft im Hintergrund.");
      }else{
        setStatus("Korrektur vollständig angewendet. Die Dateien bleiben im Ordner Mehrfachkorrektur.");
      }
    }catch(error){setStatus(error.message,true);}
    finally{buttons.forEach(button=>button.disabled=false);}
  }
  async function scanMultiple(announce=true){
    if(announce)setStatus("Ordner und Metadaten werden gelesen …");
    setScanBusy(true);
    try{
      state.scan=await json("/api/metadata-correction/scan?area=multiple");
      state.multiplePreview=null;
      if(
        state.multipleReference===null
        || state.multipleReference>=((state.scan?.files||[]).length)
      )state.multipleReference=null;
      renderMultipleFiles();
      renderMultiplePreview();
      if(announce)setStatus("Prüfung abgeschlossen. Es wurde noch nichts verändert.");
      return true;
    }catch(error){
      if(announce)setStatus(error.message,true);
      return false;
    }finally{
      setScanBusy(false);
    }
  }
  async function scan(announce=true,preserve=true){
    if(state.area==="multiple")return scanMultiple(announce);
    const snapshot=preserve?selectionKeys():{keys:new Set(),primary:null,last:null};
    if(announce)setStatus(state.area==="library"?"Ohne-Datum-Bestand wird gelesen …":"Ordner und Metadaten werden gelesen …");
    setScanBusy(true);
    try{
      state.scan=await json("/api/metadata-correction/scan?area="+encodeURIComponent(state.area));
      restoreSelection(snapshot);
      renderFiles();renderDetails();
      if(announce)setStatus("Prüfung abgeschlossen. Es wurde noch nichts verändert.");
      return true;
    }catch(error){
      if(announce)setStatus(error.message,true);
      return false;
    }finally{
      setScanBusy(false);
    }
  }
  $("meta-select-mode").addEventListener("click",()=>{
    state.selectionMode=!state.selectionMode;
    state.selectedSet.clear();
    state.lastSelected=null;
    if(!state.selectionMode)closeMobileDetail();
    renderFiles();renderDetails();
  });
  $("meta-select-all").addEventListener("click",()=>{
    if(!state.selectionMode)return;
    const files=state.scan?.files||[];
    if(files.length&&state.selectedSet.size===files.length){
      state.selectedSet.clear();
    }else{
      state.selectedSet=new Set(files.map((_,index)=>index));
      if(files.length&&state.selected===null)state.selected=0;
    }
    renderFiles();renderDetails();
    syncMobileSelectionDetail("meta",state.selectedSet.size);
  });
  $("meta-scan").addEventListener("click",()=>scan(true,true));
  $("multi-select-mode").addEventListener("click",()=>{
    state.multipleSelectionMode=!state.multipleSelectionMode;
    state.multipleSelectedSet.clear();
    state.multiplePreview=null;
    $("multi-preview-card").hidden=true;
    if(!state.multipleSelectionMode)closeMobileDetail();
    renderMultipleFiles();
    renderMultipleDetails();
  });
  $("multi-select-all").addEventListener("click",()=>{
    if(!state.multipleSelectionMode)return;
    const files=state.scan?.files||[];
    if(files.length&&state.multipleSelectedSet.size===files.length){
      state.multipleSelectedSet.clear();
      state.multipleReference=null;
    }else{
      state.multipleSelectedSet=new Set(files.map((_,index)=>index));
      if(files.length&&state.multipleReference===null)state.multipleReference=0;
    }
    state.multiplePreview=null;
    $("multi-preview-card").hidden=true;
    renderMultipleFiles();
    renderMultipleDetails();
    syncMobileSelectionDetail("multiple",state.multipleSelectedSet.size);
  });
  $("meta-mobile-dialog-close").addEventListener("click",closeMobileDetail);
  $("meta-mobile-dialog").addEventListener("cancel",event=>{
    event.preventDefault();
    closeMobileDetail();
  });
  if(typeof ResizeObserver==="function"){
    new ResizeObserver(()=>updateMobileSelectionSheetClearance())
      .observe($("meta-mobile-dialog"));
  }
  $("multi-apply").addEventListener("click",()=>applyMultiple("apply"));
  $("multi-apply-import").addEventListener("click",()=>applyMultiple("apply_and_import"));
  configureArea();
  updateSelectionControls();
  Promise.all([
    loadAreas(),
    loadTasks()
  ]).finally(()=>{
    scan(true,false);
  });
})();
</script>
</body>
</html>"""
