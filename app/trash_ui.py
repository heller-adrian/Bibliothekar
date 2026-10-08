TRASH_HTML = r"""<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Papierkorb</title>
  <style>
    .trash-toolbar{display:flex;gap:10px;align-items:center;justify-content:space-between;flex-wrap:wrap;margin-bottom:14px}
    .trash-summary{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin:14px 0}
    .trash-stat{padding:12px;border:1px solid var(--bk-line);border-radius:12px;background:var(--bk-panel)}
    .trash-stat strong{display:block;font-size:1.25rem;margin-top:4px}
    .trash-list{display:grid;gap:8px}
    .trash-row{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:12px;padding:11px 12px;border:1px solid var(--bk-line);border-radius:11px}
    .trash-path{overflow-wrap:anywhere}
    .trash-meta{color:var(--bk-muted);font-size:.88rem;margin-top:3px}
    .trash-danger{background:var(--bk-danger,#a92828)!important;color:white!important;border-color:transparent!important}
    .trash-empty{padding:24px;text-align:center;color:var(--bk-muted)}
    @media(max-width:700px){.trash-summary{grid-template-columns:1fr}.trash-row{grid-template-columns:1fr}}
  </style>
</head>
<body class="bibliothekar-redesign">
<main>
  <section class="card">
    <div class="trash-toolbar">
      <div>
        <h2 style="margin:0">Papierkorb</h2>
        <div id="trash-root" style="color:var(--bk-muted);margin-top:4px"></div>
      </div>
      <button id="trash-empty-button" type="button" class="trash-danger">Papierkorb entleeren</button>
    </div>
    <div id="trash-status" style="color:var(--bk-muted)">Papierkorb wird geprüft …</div>
    <div class="trash-summary">
      <div class="trash-stat"><span>Dateien</span><strong id="trash-files">—</strong></div>
      <div class="trash-stat"><span>Ordner</span><strong id="trash-directories">—</strong></div>
      <div class="trash-stat"><span>Größe</span><strong id="trash-size">—</strong></div>
    </div>
    <div id="trash-list" class="trash-list"></div>
  </section>
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
  async function json(url,options){
    const response=await fetch(url,options);
    let data={}; try{data=await response.json();}catch(_){}
    if(!response.ok) throw new Error(data.detail||("HTTP "+response.status));
    return data;
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
    list.innerHTML=entries.length
      ? entries.map(item=>'<div class="trash-row"><div><strong class="trash-path">'+esc(item.relative_path)+'</strong><div class="trash-meta">'
          +(item.entry_type==="file"?(item.tracked?"Katalogisiert":"Nur im Dateisystem"):"Dateisystemeintrag")
          +'</div></div><div>'+esc(item.entry_type==="file"?bytes(item.size_bytes):"")+'</div></div>').join("")
      : '<div class="trash-empty">Keine Dateien oder Ordner im Papierkorb.</div>';
  }
  async function load(){
    status.textContent="Papierkorb wird geprüft …";
    try{render(await json("/api/trash"));}
    catch(error){status.textContent=error.message;list.innerHTML="";}
  }
  emptyButton.addEventListener("click",async()=>{
    if(!confirm("Papierkorb wirklich endgültig entleeren?\n\nAlle Dateien und Ordner darin werden unwiderruflich gelöscht. Dieser Vorgang kann nicht rückgängig gemacht werden.")) return;
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