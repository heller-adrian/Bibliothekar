TRANSFER_HTML = r'''<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <meta name="theme-color" content="#0d0f12">
  <title>Archiv</title>
  <style>
    :root {
      color-scheme: dark;
      --background:#0d0f12;
      --surface:#171a1f;
      --surface-2:#1d2127;
      --border:#2b3038;
      --text:#f2f3f5;
      --muted:#9ba3ae;
      --success:#58c878;
      --warning:#e6b65c;
      --danger:#ee6b6e;
      --accent:#8eb8ff;
      font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
    }
    html,body {
      min-height:100%;
      margin:0;
      background:#0d0f12;
      color:var(--text);
      overscroll-behavior-y:auto;
    }
    body::before {
      content:"";
      position:fixed;
      inset:-20vh 0;
      z-index:-1;
      background:#0d0f12;
    }
    * { box-sizing:border-box; }
    main { width:min(1120px,100%); margin:0 auto; padding:18px; }
    h1,h2,h3,p { margin-top:0; }
    header { margin-bottom:18px; }
    .muted { color:var(--muted); }
    nav { display:flex; flex-wrap:wrap; gap:8px; margin:0; }
    nav button[aria-current="page"] { border:2px solid #f2f3f5; background:var(--surface-2); opacity:1; color:var(--text); }
    .global-header { position:static; }
    .page-intro { margin-bottom:12px; }
    .global-navigation-bar { position:sticky; top:0; z-index:60; display:flex; align-items:center; gap:10px; margin-bottom:18px; padding:10px 0; background:rgba(9,11,13,.96); backdrop-filter:blur(16px); -webkit-backdrop-filter:blur(16px); }
    .global-navigation-bar nav { flex:1 1 auto; flex-wrap:nowrap; overflow-x:auto; scrollbar-width:none; }
    .global-navigation-bar nav::-webkit-scrollbar { display:none; }
    .global-navigation-bar nav button { flex:0 0 auto; white-space:nowrap; }
    .top-button { width:42px; min-width:42px; padding:0; font-size:1.2rem; }
    button,select {
      min-height:42px;
      border:1px solid var(--border);
      border-radius:11px;
      background:var(--surface-2);
      color:var(--text);
      padding:9px 13px;
      font:inherit;
    }
    button { cursor:pointer; }
    button:disabled { cursor:not-allowed; opacity:.5; }
    .primary { border-color:var(--accent); }
    .archive-verify-button {
      background:var(--warning) !important;
      border-color:var(--warning) !important;
      color:#201a0b !important;
      font-weight:700;
    }
    .grid { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:12px; }
    .card { border:1px solid var(--border); border-radius:16px; background:var(--surface); padding:15px; min-width:0; }
    .summary strong { display:block; font-size:1.35rem; margin-top:5px; }
    section { margin-top:24px; }
    .section-head { display:flex; align-items:flex-start; justify-content:space-between; gap:12px; margin-bottom:12px; }
    .list { display:grid; gap:11px; }
    .item-head { display:flex; justify-content:space-between; align-items:flex-start; gap:12px; }
    .title { font-weight:750; overflow-wrap:anywhere; }
    .meta { display:flex; flex-wrap:wrap; gap:6px 14px; margin-top:10px; color:var(--muted); font-size:.9rem; }
    .path { margin-top:8px; font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:.82rem; color:var(--muted); overflow-wrap:anywhere; }
    .badge { border:1px solid var(--border); border-radius:999px; padding:4px 9px; font-size:.8rem; white-space:nowrap; }
    .success { border-color:var(--success); color:var(--success); }
    .warning { border-color:var(--warning); color:var(--warning); }
    .danger { border-color:var(--danger); color:var(--danger); }
    .actions { display:flex; flex-wrap:wrap; gap:8px; margin-top:12px; }
    .notice { border:1px solid var(--warning); border-radius:13px; padding:12px; color:var(--warning); margin:12px 0; }
    .empty { border:1px dashed var(--border); border-radius:14px; padding:20px; color:var(--muted); }
    details { margin-top:11px; }
    summary { cursor:pointer; color:var(--muted); }
    .result { margin-top:10px; padding:11px; border-radius:12px; background:var(--surface-2); overflow-wrap:anywhere; }
    @media (max-width:760px) {
      main { padding:13px; }
      .grid { grid-template-columns:1fr; }
      .item-head,.section-head { display:block; }
      .badge { display:inline-block; margin-top:8px; }
      .global-navigation-bar nav { display:flex; }
    }
    html, body { background: #090b0d !important; min-height: 100%; }
    body::before { content: ""; position: fixed; inset: -120px 0; background: #090b0d; z-index: -1000; pointer-events: none; }
  
    .global-task-fab { position:fixed; right:18px; bottom:18px; z-index:1200; width:50px; height:50px; border-radius:50%; display:flex; align-items:center; justify-content:center; font-size:22px; box-shadow:0 8px 28px rgba(0,0,0,.35); background:#20252b; border:1px solid #4a5663; }
    .global-task-fab.visible { display:flex; }
    .global-task-badge.hidden { display:none !important; }
    .global-task-badge { position:absolute; right:-4px; top:-6px; min-width:22px; height:22px; padding:0 5px; border-radius:12px; background:#e04f5f; color:white; border:2px solid #090b0d; font-size:12px; font-weight:800; display:flex; align-items:center; justify-content:center; }
    .global-task-panel { position:fixed; right:18px; bottom:78px; z-index:1199; width:min(390px,calc(100vw - 36px)); max-height:60vh; overflow:auto; padding:14px; border-radius:14px; border:1px solid #3b424a; background:#181c20; box-shadow:0 14px 44px rgba(0,0,0,.5); display:none; }
    .global-task-panel.open { display:block; }
    .global-task-item { display:block; padding:10px; margin-top:8px; border-radius:10px; border:1px solid #333a42; background:#20252b; color:inherit; text-decoration:none; }
    .global-task-item strong { display:block; margin-bottom:3px; }

  </style>
</head>
<body>
<main>
  <header class="page-intro">
    <h1>Archiv</h1>
    <p class="muted">Sicherungsabschluss verfolgen, Kamerabibliothek read-only prüfen und bestätigte SSD-Bestände freigeben.</p>
  </header>

  <div class="global-navigation-bar">
    <nav class="navigation" aria-label="Seitennavigation">
      <button onclick="location.href='/'">Import &amp; Prüfung</button>
      <button onclick="location.href='/workspace'">Sortieren</button>
      <button onclick="location.href='/events'">Ereignisse</button>
      <button disabled aria-current="page">Archiv</button>
    </nav>
    <button class="top-button" type="button" onclick="window.scrollTo({top:0,behavior:'smooth'})" aria-label="Nach oben">↑</button>
  </div>

  <div class="grid summary">
    <div class="card"><span class="muted">Offene Prüfungen</span><strong id="candidate-count">–</strong></div>
    <div class="card"><span class="muted">Vollständig geprüft</span><strong id="verified-count">–</strong></div>
    <div class="card"><span class="muted">SSD freigegeben</span><strong id="released-count">–</strong></div>
    <div class="card"><span class="muted">Gesperrt</span><strong id="blocked-count">–</strong></div>
  </div>

  <section>
    <div class="section-head"><div class="bk-section-title-row"><h2>Zur Archivprüfung</h2><button class="bk-help" type="button" aria-label="Hilfe zur Archivprüfung" data-help="Neu angewendete Ereignisse werden hier geprüft und anschließend von der SSD freigegeben. Neueste Ereignisse stehen zuerst.">?</button></div></div>
    <div id="archive-notice" class="notice" hidden></div>
    <div id="archive-list" class="list"><div class="empty">Wird geladen …</div></div>
  </section>
  <section>
    <div class="section-head"><div class="bk-section-title-row"><h2>Archivverlauf</h2><button class="bk-help" type="button" aria-label="Hilfe zum Archivverlauf" data-help="Freigegebene Ereignisse bleiben hier nachvollziehbar. Neueste Ereignisse stehen zuerst.">?</button></div></div>
    <div id="history-list" class="list"><div class="empty">Wird geladen …</div></div>
  </section>
</main>

  <button id="global-task-fab" class="global-task-fab" type="button" aria-label="Offene Aufgaben">☑<span id="global-task-badge" class="global-task-badge">0</span></button>
  <aside id="global-task-panel" class="global-task-panel" aria-live="polite"></aside>


  <script>

    async function refreshGlobalTasks() {
      const button=document.getElementById("global-task-fab");
      const badge=document.getElementById("global-task-badge");
      const panel=document.getElementById("global-task-panel");
      if (!button || !badge || !panel) return;
      try {
        const response=await fetch("/api/tasks",{cache:"no-store"});
        const data=await response.json();
        const tasks=data.tasks||[];
        const count=Number(data.count||0);
        button.classList.add("visible");
        badge.textContent=String(count);
        badge.classList.toggle("hidden",count===0);
        panel.innerHTML=count ? `<strong>Offene Aufgaben · ${count}</strong>`+tasks.map(task=>`<a class="global-task-item" href="${String(task.href||'/events').replaceAll('&','&amp;').replaceAll('"','&quot;')}"><strong>${String(task.title||'Aufgabe')}</strong><span>${String(task.detail||'')}</span></a>`).join("") : `<strong>Keine offenen Aufgaben</strong><span class="muted" style="display:block;margin-top:6px">Alles erledigt.</span>`;
      } catch (_) {}
    }
    document.getElementById("global-task-fab")?.addEventListener("click",()=>document.getElementById("global-task-panel")?.classList.toggle("open"));
    refreshGlobalTasks();
    setInterval(refreshGlobalTasks,30000);

  const historyList=document.getElementById('history-list');
  const archiveList=document.getElementById('archive-list');
  const archiveNotice=document.getElementById('archive-notice');
  const blockedCount=document.getElementById('blocked-count');
  const candidateCount=document.getElementById('candidate-count');
  const verifiedCount=document.getElementById('verified-count');
  const releasedCount=document.getElementById('released-count');

  function escapeHtml(value){return String(value??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'",'&#039;');}
  function formatBytes(value){const n=Number(value||0);if(n<1024)return `${n} B`;const units=['KiB','MiB','GiB','TiB'];let v=n/1024;let i=0;while(v>=1024&&i<units.length-1){v/=1024;i+=1;}return `${v.toLocaleString('de-DE',{maximumFractionDigits:1})} ${units[i]}`;}
  async function getJson(url){const response=await fetch(url,{cache:'no-store'});const data=await response.json();if(!response.ok)throw new Error(data.detail||`HTTP ${response.status}`);return data;}
  async function postJson(url){const response=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});const data=await response.json();if(!response.ok)throw new Error(data.detail||`HTTP ${response.status}`);return data;}

  function eventStatusLabel(status){const labels={draft:'Entwurf',planned:'geplant',applied:'angewendet',archived:'archiviert'};return labels[String(status||'')]||String(status||'');}
    function formatDate(value){
    const date=new Date(value||'');
    if(Number.isNaN(date.getTime()))return 'Zeitpunkt unbekannt';
    return new Intl.DateTimeFormat('de-DE',{dateStyle:'medium',timeStyle:'short'}).format(date);
  }
  function renderArchive(summary){
    candidateCount.textContent=summary.candidate_count;
    verifiedCount.textContent=summary.verified_count;
    releasedCount.textContent=summary.released_count||0;
    blockedCount.textContent=summary.blocked_count||0;
    archiveNotice.hidden=summary.archive_readable;
    archiveNotice.textContent=summary.archive_readable?'':`Kamerabibliothek ist noch nicht read-only unter ${summary.archive_root} eingebunden. Die Verwaltungsseite ist bereit; die Prüfung und SSD-Freigabe bleiben bis zur Einbindung gesperrt.`;
    archiveList.innerHTML=''; historyList.innerHTML='';
    const open=(summary.candidates||[]).filter(item=>!item.released);
    const history=(summary.candidates||[]).filter(item=>item.released);
    if(!open.length) archiveList.innerHTML='<div class="empty">Keine offenen Ereignisse zur Archivprüfung.</div>';
    for(const item of open){
      const card=document.createElement('article');card.className='card archive-check-card';
      const verification=item.released
        ?'SSD freigegeben'
        :(item.verified
          ?'Vollständig geprüft'
          :(item.verification_invalidated?'Erneut prüfen':(item.verification_status||'Noch nicht geprüft')));
      const releaseDisabled=!item.ssd_release_ready;
      const releaseLabel=item.released?'SSD freigegeben':'SSD freigeben';
      card.innerHTML=`<div class="item-head"><div><div class="title">${escapeHtml(item.name)}</div><div class="path">${escapeHtml(item.folder_name)}</div><div class="muted">Erstellt: ${escapeHtml(formatDate(item.event_created_at))}</div></div><span class="badge ${(item.verified||item.released)?'success':'warning'}">${escapeHtml(verification)}</span></div><div class="meta"><span>${Number(item.family_count||0)} Familien</span><span>${Number(item.file_count||0)} Dateien</span><span>${formatBytes(item.total_size_bytes)}</span><span>Status: ${escapeHtml(eventStatusLabel(item.status))}</span></div><div class="actions"><button class="verify archive-verify-button" ${summary.archive_readable?'':'disabled'}>Archiv prüfen</button><button class="release" ${releaseDisabled?'disabled':''}>${releaseLabel}</button></div><div class="result" hidden></div>`;
      const result=card.querySelector('.result');
      const verifyButton=card.querySelector('.verify');
      const releaseButton=card.querySelector('.release');
      verifyButton.addEventListener('click',async(event)=>{event.currentTarget.disabled=true;result.hidden=false;result.textContent='Kamerabibliothek wird vollständig per Größe und SHA-256 geprüft …';try{const data=await postJson(`/api/jobs/${encodeURIComponent(item.job_id)}/events/${encodeURIComponent(item.event_id)}/archive-verify`);result.className=`result ${data.verified?'success':'danger'}`;result.textContent=`${data.message} ${data.verified_file_count}/${data.file_count} Dateien bestätigt; ${data.missing_file_count} fehlen; ${data.mismatched_file_count} weichen ab.`;await load();}catch(error){result.className='result danger';result.textContent=error.message;event.currentTarget.disabled=false;}});
      releaseButton.addEventListener('click',async(event)=>{
        if(!confirm(`SSD-Bestand für „${item.name}“ freigeben? Die Kamerabibliothek wird erneut vollständig geprüft; erst danach werden ausschließlich die bestätigten Dateien im SSD-Arbeitsbereich entfernt.`))return;
        event.currentTarget.disabled=true;verifyButton.disabled=true;result.hidden=false;result.className='result';result.textContent='Kamerabibliothek und SSD-Dateien werden erneut per SHA-256 geprüft. Anschließend wird nur der bestätigte SSD-Ereignisbestand entfernt …';
        try{const data=await postJson(`/api/jobs/${encodeURIComponent(item.job_id)}/events/${encodeURIComponent(item.event_id)}/ssd-release`);result.className='result success';result.textContent=`${data.message} ${Number(data.file_count||0)} Dateien geprüft; ${Number(data.deleted_file_count||0)} SSD-Dateien entfernt.`;await load();}
        catch(error){result.className='result danger';result.textContent=error.message;event.currentTarget.disabled=false;verifyButton.disabled=false;}
      });
      archiveList.appendChild(card);
    }
    if(!history.length) historyList.innerHTML='<div class="empty">Noch keine freigegebenen Ereignisse im Verlauf.</div>';
    for(const item of history){
      const card=document.createElement('article');card.className='card';
      card.innerHTML=`<div class="item-head"><div><div class="title">${escapeHtml(item.name)}</div><div class="path">${escapeHtml(item.folder_name)}</div><div class="muted">Erstellt: ${escapeHtml(formatDate(item.event_created_at))}</div></div><span class="badge success">SSD freigegeben</span></div><div class="meta"><span>${Number(item.family_count||0)} Familien</span><span>${Number(item.file_count||0)} Dateien</span><span>${formatBytes(item.total_size_bytes)}</span><span>Status: ${escapeHtml(eventStatusLabel(item.status))}</span></div>`;
      historyList.appendChild(card);
    }
  }

  async function load(){
    const archive=await getJson('/api/archive/summary');
    renderArchive(archive);
  }
  load().catch(error=>{archiveList.innerHTML=`<div class="notice">${escapeHtml(error.message)}</div>`;historyList.innerHTML='';});
</script>
</body>
</html>'''
