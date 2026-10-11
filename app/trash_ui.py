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
    <button id="trash-empty-button" type="button" class="danger-button trash-danger">Papierkorb entleeren</button>
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
    const kind=item.entry_type==="file"
      ? (item.tracked?"Katalogisiert":"Nur im Dateisystem")
      : item.entry_type==="symlink"?"Symbolischer Link":"Dateisystemeintrag";
    const showSize=item.entry_type==="file"||item.entry_type==="other";
    return '<div class="trash-row"><div><strong class="trash-path" title="'+esc(item.relative_path)+'">'+esc(item.filename||item.relative_path)+'</strong><div class="trash-meta">'+kind+'</div></div>'
      +'<span class="trash-size">'+(showSize?esc(bytes(item.size_bytes)):"")+'</span></div>';
  }
  function renderFolder(folder){
    const fileTotal=fileCount(folder);
    const label=fileTotal===1?"1 Datei":fileTotal+" Dateien";
    return '<details class="trash-folder"><summary><strong class="trash-summary-label">'+esc(folder.name)+'</strong>'
      +'<span class="trash-summary-count">'+label+'</span></summary>'
      +'<div class="trash-folder-items">'+renderChildren(folder)+'</div></details>';
  }
  function renderChildren(folder){
    const directories=sorted(folder.folders.keys()).map(name=>renderFolder(folder.folders.get(name)));
    const items=folder.items.slice().sort((a,b)=>String(a.filename).localeCompare(String(b.filename),"de",{numeric:true,sensitivity:"base"})).map(renderItem);
    return directories.concat(items).join("")||'<div class="trash-empty">Der Ordner ist leer.</div>';
  }
  function render(data){
    document.getElementById("trash-root").textContent=data.root||"";
    document.getElementById("trash-files").textContent=Number(data.file_count||0);
    document.getElementById("trash-directories").textContent=Number(data.directory_count||0);
    document.getElementById("trash-size").textContent=bytes(data.total_size_bytes);
    const entries=data.entries||[];
    emptyButton.disabled=entries.length===0;
    status.textContent=entries.length
      ? "Physischer Bestand geprüft · "+Number(data.tracked_file_count||0)+" bekannte Dateien"
        +(Number(data.untracked_file_count||0)?" · "+Number(data.untracked_file_count||0)+" nicht katalogisierte Dateien":"")
      : "Der Papierkorb ist leer.";
    const count=Number(data.file_count||0);
    const folders=Number(data.directory_count||0);
    list.innerHTML=entries.length
      ? '<details class="trash-content"><summary><span class="trash-summary-label">Inhalt des Papierkorbs</span>'
          +'<span class="trash-summary-count">'+count+' Dateien · '+folders+' Ordner</span></summary>'
          +'<div class="trash-content-body">'+renderChildren(makeTree(entries))+'</div></details>'
      : '<div class="trash-empty">Keine Dateien oder Ordner im Papierkorb.</div>';
  }
  async function load(){
    status.textContent="Papierkorb wird geprüft …";
    try{render(await json("/api/trash"));}
    catch(error){status.textContent=error.message;list.innerHTML="";}
  }
  emptyButton.addEventListener("click",async()=>{
    if(!(await window.BibliothekarI18n.confirmAsync("Papierkorb wirklich endgültig entleeren?\n\nAlle Dateien und Ordner darin werden unwiderruflich gelöscht. Dieser Vorgang kann nicht rückgängig gemacht werden."))) return;
    emptyButton.disabled=true;
    status.textContent="Papierkorb wird endgültig geleert …";
    try{
      const data=await json("/api/trash/empty",{
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify({confirmation:"PAPIERKORB ENDGÜLTIG LEEREN"})
      });
      render(data);
      status.textContent="Papierkorb wurde vollständig geleert und der Datenbankbestand synchronisiert.";
    }catch(error){
      status.textContent=error.message;
      emptyButton.disabled=false;
    }
  });
  load();
})();
</script>
</body>
</html>
"""