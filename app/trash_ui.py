TRASH_HTML = r"""<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Papierkorb</title>
  <style>
    /* Sonderseite: Titel und Seitengrund stammen aus dem gemeinsamen Rahmen. */
    .trash-page{min-width:0}
    .trash-toolbar{display:flex;gap:16px;align-items:center;justify-content:space-between;flex-wrap:wrap;margin:4px 0 16px}
    .trash-root-label{color:var(--bk-muted);font-size:.85rem;margin-bottom:3px}
    .trash-root{color:var(--bk-muted);overflow-wrap:anywhere}
    .trash-status{color:var(--bk-muted);line-height:1.45;margin:0 0 15px}
    .trash-summary{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin:14px 0 18px}
    .trash-stat{min-width:0;box-sizing:border-box;padding:14px 16px;border:1px solid var(--bk-line);border-radius:12px;background:var(--bk-surface)}
    .trash-stat strong{display:block;font-size:1.25rem;margin-top:5px;overflow-wrap:anywhere}
    .trash-action{min-height:38px;padding:9px 15px;border:1px solid var(--bk-line);border-radius:10px;cursor:pointer;background:var(--bk-surface);color:var(--bk-ink)}
    .trash-action-primary{background:var(--bk-blue);color:#fff;border-color:var(--bk-blue);font-weight:650}
    .trash-action:disabled{opacity:.5;cursor:not-allowed}
    .trash-toolbar-actions{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
    .trash-file-main{display:flex;align-items:flex-start;gap:10px;min-width:0}
    .trash-file-main>div{min-width:0}
    .trash-checkbox{width:19px;height:19px;min-width:19px;min-height:19px;accent-color:var(--bk-blue);cursor:pointer}
    .trash-row.trash-selected{border-color:var(--bk-blue);background:var(--bk-surface-2)}
    .trash-row.trash-pickable{cursor:pointer}
    .trash-danger{min-height:38px;padding:9px 15px;border:1px solid var(--bk-danger);font-weight:600;cursor:pointer}
    .trash-danger:disabled{opacity:.55;cursor:not-allowed}
    .trash-content{border:1px solid var(--bk-line);border-radius:var(--bk-radius);background:var(--bk-surface);overflow:hidden}
    .trash-content>summary,.trash-folder>summary{display:flex;align-items:center;gap:10px;cursor:pointer;list-style:none;min-width:0}
    .trash-content>summary::-webkit-details-marker,.trash-folder>summary::-webkit-details-marker{display:none}
    .trash-content>summary::before,.trash-folder>summary::before{content:"▸";display:block;flex:0 0 16px;font-size:1.1rem;color:var(--bk-muted);transition:transform .15s ease}
    .trash-content[open]>summary::before,.trash-folder[open]>summary::before{transform:rotate(90deg)}
    .trash-content>summary{padding:16px 18px;font-weight:700}
    .trash-content[open]>summary{border-bottom:1px solid var(--bk-line)}
    .trash-summary-label{min-width:0;overflow-wrap:anywhere}
    .trash-summary-count{font-size:.85rem;font-weight:500;color:var(--bk-muted);margin-left:auto;text-align:right}
    .trash-content-body{display:grid;gap:12px;padding:16px 18px 20px}
    .trash-folder{min-width:0;border:1px solid var(--bk-line);border-radius:12px;background:var(--bk-surface-2);overflow:hidden}
    .trash-folder>summary{padding:13px 15px;min-height:24px}
    .trash-folder[open]>summary{border-bottom:1px solid var(--bk-line)}
    .trash-folder-items{display:grid;gap:10px;padding:12px 14px 15px;min-width:0}
    .trash-row{display:grid;grid-template-columns:minmax(0,1fr) auto;align-items:start;gap:12px;min-width:0;box-sizing:border-box;padding:12px 14px;border:1px solid var(--bk-line);border-radius:11px;background:var(--bk-surface)}
    .trash-path{display:block;overflow-wrap:anywhere}
    .trash-meta{color:var(--bk-muted);font-size:.85rem;margin-top:4px}
    .trash-size{white-space:nowrap;font-size:.9rem;color:var(--bk-ink)}
    .trash-empty{padding:23px;text-align:center;color:var(--bk-muted)}
    .trash-content>summary:focus-visible,.trash-folder>summary:focus-visible{outline:2px solid var(--bk-blue);outline-offset:-3px}
    @media(max-width:700px){
      .trash-summary{grid-template-columns:1fr}
      .trash-toolbar{align-items:flex-start}
      .trash-row{grid-template-columns:minmax(0,1fr)}
      .trash-content>summary{padding:14px 12px}
      .trash-content-body{padding:12px;gap:10px}
      .trash-folder>summary{padding:12px}
      .trash-folder-items{padding:10px;gap:9px}
      .trash-summary-count{font-size:.78rem}
    }
    @media(min-width:701px){
      body[data-bk-area="trash"] main.trash-page{padding-bottom:72px!important}
    }
  </style>
</head>
<body class="bibliothekar-redesign">
<main class="trash-page">
  <div class="trash-toolbar">
    <div>
      <div class="trash-root-label">Verwalteter Ordner</div>
      <div id="trash-root" class="trash-root"></div>
    </div>
    <div class="trash-toolbar-actions">
      <button id="trash-select-button" type="button" class="trash-action">Auswählen</button>
      <button id="trash-select-all-button" type="button" class="trash-action" hidden>Alle auswählen</button>
      <button id="trash-restore-button" type="button" class="trash-action trash-action-primary">Alle wiederherstellen</button>
      <button id="trash-empty-button" type="button" class="danger-button trash-danger">Gesamten Papierkorb leeren</button>
    </div>
  </div>
  <p id="trash-status" class="trash-status" role="status" aria-live="polite">Papierkorb wird geprüft …</p>
  <div class="trash-summary" aria-label="Papierkorb-Statistik">
    <div class="trash-stat"><span>Dateien</span><strong id="trash-files">—</strong></div>
    <div class="trash-stat"><span>Ordner</span><strong id="trash-directories">—</strong></div>
    <div class="trash-stat"><span>Größe</span><strong id="trash-size">—</strong></div>
  </div>
  <div id="trash-list" class="trash-list"></div>
</main>
<script>
(function(){
  const status=document.getElementById("trash-status");
  const list=document.getElementById("trash-list");
  const emptyButton=document.getElementById("trash-empty-button");
  const restoreButton=document.getElementById("trash-restore-button");
  const selectButton=document.getElementById("trash-select-button");
  const selectAllButton=document.getElementById("trash-select-all-button");
  const selected=new Set();
  let selectablePaths=[],selectMode=false,lastSelected=null,busy=false,lastInventory=null;
  const bilingual=(de,en)=>window.BibliothekarI18n?.getLocale?.()==="de"?de:en;
  const localError=raw=>{
    const value=String(raw||"");
    const prefixes={
      "Datei keiner Sicherung zuzuordnen; Wiederherstellung nicht möglich:":"File has no backup provenance; restoration is not possible:",
      "Nicht katalogisierte Datei:":"Uncatalogued file:",
      "Größe oder Prüfsumme abweichend:":"Size or checksum mismatch:",
      "Zieldatei existiert bereits:":"Destination already exists:",
      "Datei nicht mehr im Papierkorb:":"File no longer in trash:",
      "Ungültige Dateiauswahl.":"Invalid file selection.",
      "Aufnahmezeit unbekannt:":"Unknown capture time:",
      "Noch einem Ereignis zugeordnet:":"Still assigned to an event:",
      "Papierkorb konnte nicht sicher geleert werden:":"Could not empty trash safely:",
      "Symbolische Links dürfen nicht wiederhergestellt werden.":"Symbolic links cannot be restored.",
      "Diese Dateien werden bereits wiederhergestellt.":"These files are already being restored.",
      "Ein Papierkorb-Importjournal ist nicht lesbar.":"A trash import journal cannot be read."
    };
    if(window.BibliothekarI18n?.getLocale?.()==="de")return value;
    for(const [source,target] of Object.entries(prefixes))
      if(value.startsWith(source))return target+value.slice(source.length);
    return window.BibliothekarI18n?.t?.(value)||value;
  };
  function updateControls(){
    restoreButton.textContent=selected.size?"Auswahl wiederherstellen":"Alle wiederherstellen";
    restoreButton.disabled=busy||!selectablePaths.length;
    emptyButton.disabled=busy||!document.querySelector(".trash-content");
    emptyButton.textContent=selected.size?"Auswahl leeren":"Gesamten Papierkorb leeren";
    selectButton.disabled=busy||!selectablePaths.length;
    selectButton.textContent=selectMode?"Auswahl beenden":"Auswählen";
    selectAllButton.hidden=!selectMode;
    selectAllButton.disabled=busy||!selectablePaths.length;
    selectAllButton.textContent=selected.size===selectablePaths.length?"Auswahl aufheben":"Alle auswählen";
    list.querySelectorAll("[data-trash-restore-path]").forEach(row=>{
      const checked=selected.has(row.dataset.trashRestorePath);
      row.classList.toggle("trash-selected",checked);
      const input=row.querySelector(".trash-checkbox");
      if(input)input.checked=checked;
    });
  }
  const esc=value=>String(value==null?"":value).replace(/[&<>"']/g,ch=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[ch]));
  const bytes=value=>{
    let n=Number(value||0); const units=["B","KB","MB","GB","TB"]; let i=0;
    while(n>=1024&&i<units.length-1){n/=1024;i++;}
    return (i===0?Math.round(n):n.toFixed(n>=10?1:2))+" "+units[i];
  };
  const sorted=values=>Array.from(values).sort((a,b)=>String(a).localeCompare(String(b),"de",{numeric:true,sensitivity:"base"}));
  async function json(url,options){
    const response=await fetch(url,options);
    let data={}; try{data=await response.json();}catch(_){}
    if(!response.ok) throw new Error(data.detail||("HTTP "+response.status));
    return data;
  }
  function makeFolder(name){
    return {name:name,folders:new Map(),items:[]};
  }
  function makeTree(entries){
    const root=makeFolder("");
    for(const entry of entries){
      const parts=String(entry.relative_path||"").split("/").filter(Boolean);
      if(!parts.length) continue;
      let parent=root;
      const depth=entry.entry_type==="directory"?parts.length:parts.length-1;
      for(let i=0;i<depth;i++){
        if(!parent.folders.has(parts[i])) parent.folders.set(parts[i],makeFolder(parts[i]));
        parent=parent.folders.get(parts[i]);
      }
      if(entry.entry_type!=="directory") parent.items.push(entry);
    }
    return root;
  }
  function fileCount(folder){
    let count=folder.items.filter(item=>item.entry_type==="file").length;
    for(const child of folder.folders.values()) count+=fileCount(child);
    return count;
  }
  function renderItem(item){
    const path=String(item.relative_path||"");
    const pickable=selectMode&&item.entry_type==="file";
    const picked=selected.has(path);
    const checkbox=pickable
      ? '<input class="trash-checkbox" type="checkbox" aria-label="Datei auswählen" '+(picked?"checked":"")+'>'
      : "";
    const kind=item.entry_type==="file"
      ? (item.tracked?"Katalogisiert":"Nur im Dateisystem")
      : item.entry_type==="symlink"?"Symbolischer Link":"Dateisystemeintrag";
    const showSize=item.entry_type==="file"||item.entry_type==="other";
    return '<div class="trash-row '+(pickable?"trash-pickable ":"")+(picked?"trash-selected":"")+'"'
      +(pickable?' data-trash-restore-path="'+esc(path)+'" tabindex="0"':"")
      +'><div class="trash-file-main">'+checkbox+'<div><strong class="trash-path" title="'+esc(item.relative_path)+'">'+esc(item.filename||item.relative_path)+'</strong><div class="trash-meta">'+kind+'</div></div></div>'
      +'<span class="trash-size">'+(showSize?esc(bytes(item.size_bytes)):"")+'</span></div>';
  }
  function renderFolder(folder){
    const fileTotal=fileCount(folder);
    const label=fileTotal===1?"1 Datei":fileTotal+" Dateien";
    return '<details class="trash-folder"><summary data-trash-group="'+esc(folder.name)+'"><strong class="trash-summary-label">'+esc(folder.name)+'</strong>'
      +'<span class="trash-summary-count">'+label+'</span></summary>'
      +'<div class="trash-folder-items">'+renderChildren(folder)+'</div></details>';
  }
  function renderChildren(folder){
    const directories=sorted(folder.folders.keys()).map(name=>renderFolder(folder.folders.get(name)));
    const items=folder.items.slice().sort((a,b)=>String(a.filename).localeCompare(String(b.filename),"de",{numeric:true,sensitivity:"base"})).map(renderItem);
    return directories.concat(items).join("")||'<div class="trash-empty">Der Ordner ist leer.</div>';
  }
  function render(data){
    lastInventory=data;
    document.getElementById("trash-root").textContent=data.root||"";
    document.getElementById("trash-files").textContent=Number(data.file_count||0);
    document.getElementById("trash-directories").textContent=Number(data.directory_count||0);
    document.getElementById("trash-size").textContent=bytes(data.total_size_bytes);
    const entries=data.entries||[];
    const previousOpen=new Set([...list.querySelectorAll("details[open]")].map(d=>d.dataset.trashGroup||d.querySelector("summary")?.dataset.trashGroup||"root"));
    selectablePaths=entries.filter(e=>e.entry_type==="file").map(e=>String(e.relative_path));
    for(const path of [...selected]) if(!selectablePaths.includes(path))selected.delete(path);
    status.textContent=entries.length
      ? "Physischer Bestand geprüft · "+Number(data.tracked_file_count||0)+" bekannte Dateien"
        +(Number(data.untracked_file_count||0)?" · "+Number(data.untracked_file_count||0)+" nicht katalogisierte Dateien":"")
      : "Der Papierkorb ist leer.";
    const conflicts=data.restore_conflicts||[];
    if(conflicts.length)status.textContent+=" · Wiederherstellung blockiert: "+conflicts.map(c=>c.operation_id+" – "+c.message).join("; ");
    const count=Number(data.file_count||0);
    const folders=Number(data.directory_count||0);
    list.innerHTML=entries.length
      ? '<details class="trash-content"><summary><span class="trash-summary-label">Inhalt des Papierkorbs</span>'
          +'<span class="trash-summary-count">'+count+' Dateien · '+folders+' Ordner</span></summary>'
          +'<div class="trash-content-body">'+renderChildren(makeTree(entries))+'</div></details>'
      : '<div class="trash-empty">Keine Dateien oder Ordner im Papierkorb.</div>';
    if(previousOpen.size){
      list.querySelectorAll("details.trash-folder").forEach(d=>{
        if(previousOpen.has(d.querySelector("summary")?.dataset.trashGroup))d.open=true;
      });
    }
    if(previousOpen.has("root")){
      const panel=list.querySelector("details.trash-content");
      if(panel)panel.open=true;
    }
    updateControls();
  }
  async function load(){
    status.textContent="Papierkorb wird geprüft …";
    try{render(await json("/api/trash"));}
    catch(error){status.textContent=error.message;list.innerHTML="";}
  }
  selectButton.addEventListener("click",()=>{
    selectMode=!selectMode;
    if(!selectMode){selected.clear();lastSelected=null;}
    if(lastInventory)render(lastInventory);
  });
  selectAllButton.addEventListener("click",()=>{
    if(selected.size===selectablePaths.length)selected.clear();
    else selectablePaths.forEach(path=>selected.add(path));
    updateControls();
  });
  list.addEventListener("click",event=>{
    const row=event.target.closest("[data-trash-restore-path]");
    if(!row||!selectMode||busy)return;
    const path=row.dataset.trashRestorePath;
    const index=selectablePaths.indexOf(path);
    const input=event.target.closest(".trash-checkbox");
    const wanted=input?input.checked:!selected.has(path);
    if(event.shiftKey&&lastSelected!==null){
      for(let i=Math.min(index,lastSelected);i<=Math.max(index,lastSelected);i++){
        if(wanted)selected.add(selectablePaths[i]);
        else selected.delete(selectablePaths[i]);
      }
    }else if(wanted)selected.add(path);
    else selected.delete(path);
    lastSelected=index;
    updateControls();
  });
  list.addEventListener("keydown",event=>{
    if(!selectMode||!["Enter"," "].includes(event.key))return;
    const row=event.target.closest("[data-trash-restore-path]");
    if(!row||event.target.matches("input"))return;
    event.preventDefault();row.click();
  });
  restoreButton.addEventListener("click",async()=>{
    const count=selected.size||selectablePaths.length;
    if(!count||busy)return;
    const question=selected.size
      ? bilingual("Die "+count+" ausgewählten Dateien in den Tagesbestand wiederherstellen?",
                  "Restore "+count+" selected files to the daily inventory?")
      : bilingual("Alle "+count+" Dateien im Papierkorb in den Tagesbestand wiederherstellen?",
                  "Restore all "+count+" files from trash to the daily inventory?");
    if(!(await window.BibliothekarI18n.confirmAsync(question)))return;
    busy=true;updateControls();
    status.textContent="Dateien werden in den Tagesbestand wiederhergestellt …";
    try{
      const result=await json("/api/trash/restore",{
        method:"POST",headers:{"Content-Type":"application/json"},
        body:JSON.stringify({relative_paths:selected.size?[...selected]:null})
      });
      selected.clear();selectMode=false;lastSelected=null;
      render(result.inventory);
      const queued=Number(result.queued_file_count||0);
      const skipped=(result.skipped_paths||[]).length;
      status.textContent=bilingual(
        queued+" Dateien zur Wiederherstellung im Hintergrund vorgemerkt."+
          (skipped?" "+skipped+" Systemdateien übersprungen.":""),
        queued+" files queued for background restoration."+
          (skipped?" "+skipped+" system files skipped.":"")
      );
      window.dispatchEvent(new Event("bk-activity-refresh"));
    }catch(error){
      status.textContent=localError(error.message);
    }finally{
      busy=false;updateControls();
    }
  });
  emptyButton.addEventListener("click",async()=>{
    if(busy)return;
    const selection=[...selected];
    const isPartial=selection.length>0;
    const prompt=isPartial
      ? bilingual(
          "Die "+selection.length+" ausgewählten Dateien endgültig löschen? Dies kann nicht rückgängig gemacht werden.",
          "Permanently delete "+selection.length+" selected files? This cannot be undone."
        )
      : bilingual(
          "Den gesamten Papierkorb endgültig leeren? Alle Dateien und Ordner werden unwiderruflich gelöscht.",
          "Permanently empty the entire trash? All files and folders will be deleted and cannot be recovered."
        );
    if(!(await window.BibliothekarI18n.confirmAsync(prompt)))return;
    busy=true;updateControls();
    status.textContent=bilingual("Papierkorb wird geleert …","Emptying trash…");
    try{
      const data=await json(isPartial?"/api/trash/empty-selection":"/api/trash/empty",{
        method:"POST",headers:{"Content-Type":"application/json"},
        body:JSON.stringify(isPartial?{relative_paths:selection}:{confirmation:"PAPIERKORB ENDGÜLTIG LEEREN"})
      });
      selected.clear();selectMode=false;lastSelected=null;
      render(isPartial?data.inventory:data);
      status.textContent=isPartial
        ? bilingual("Ausgewählte Dateien endgültig gelöscht.","Selected files permanently deleted.")
        : bilingual("Gesamter Papierkorb endgültig geleert.","Entire trash permanently emptied.");
    }catch(error){
      status.textContent=localError(error.message);
    }finally{
      busy=false;updateControls();
    }
  });
  load();
})();
</script>
</body>
</html>
"""