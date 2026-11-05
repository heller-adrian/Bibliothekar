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
      font-family:Futura, "Helvetica Neue", Helvetica, Arial, sans-serif;
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
    .path { margin-top:8px; font-family:Futura, "Helvetica Neue", Helvetica, Arial, sans-serif; font-size:.82rem; color:var(--muted); overflow-wrap:anywhere; }
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


    .history-field-label { display:block; font-size:.75rem; font-weight:400; margin-bottom:3px; }
    .path .history-field-label { display:inline; margin-right:5px; }
    @media(max-width:760px) {
      #history-list .card { padding:11px; }
      #history-list .meta { gap:4px 10px; margin-top:7px; font-size:.8rem; }
      #history-list .path { margin-top:5px; }
      #history-list .badge { font-size:.74rem; padding:3px 7px; }
    }
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
    <div class="card"><span class="muted">Arbeitsbereich freigegeben</span><strong id="released-count">–</strong></div>
    <div class="card"><span class="muted">Gesperrt</span><strong id="blocked-count">–</strong></div>
  </div>

  <section>
    <div class="section-head"><div class="bk-section-title-row"><h2 class="bk-title-help" tabindex="0" role="button" aria-expanded="false" data-bk-title-help data-help="Neu angewendete Ereignisse werden hier geprüft und anschließend von der Arbeitsbereich freigegeben. Neueste Ereignisse stehen zuerst.">Zur Archivprüfung</h2></div></div>
    <div id="archive-notice" class="notice" hidden></div>
    <div id="archive-list" class="list"><div class="empty bk-loading-status">Wird geladen …</div></div>
  </section>
  <section>
    <div class="section-head"><div class="bk-section-title-row"><h2 class="bk-title-help" tabindex="0" role="button" aria-expanded="false" data-bk-title-help data-help="Freigegebene Ereignisse bleiben hier nachvollziehbar. Neueste Ereignisse stehen zuerst.">Archivverlauf</h2></div></div>
    <div id="history-list" class="list"><div class="empty bk-loading-status">Wird geladen …</div></div>
  </section>
</main>

  <button id="global-task-fab" class="global-task-fab" type="button" aria-label="Offene Aufgaben">☑<span id="global-task-badge" class="global-task-badge">0</span></button>
  <aside id="global-task-panel" class="global-task-panel" aria-live="polite"></aside>


  <script>

    async function refreshGlobalTasks() {
      const taskText=value=>String(value).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'",'&#039;');
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
        panel.innerHTML=count ? `<strong>Offene Aufgaben · ${count}</strong>`+tasks.map(task=>`<a class="global-task-item" href="${taskText(task.href||'/events')}"><strong>${taskText(task.title||'Aufgabe')}</strong><span>${taskText(task.detail||'')}</span></a>`).join("") : `<strong>Keine offenen Aufgaben</strong><span class="muted" style="display:block;margin-top:6px">Alles erledigt.</span>`;
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
  function formatBytes(value){const n=Number(value||0);if(n<1024)return `${n} B`;const units=['KiB','MiB','GiB','TiB'];let v=n/1024;let i=0;while(v>=1024&&i<units.length-1){v/=1024;i+=1;}return `${v.toLocaleString((document.documentElement.lang === "de" ? "de-DE" : "en-US"),{maximumFractionDigits:1})} ${units[i]}`;}
  async function getJson(url){const response=await fetch(url,{cache:'no-store'});const data=await response.json();if(!response.ok)throw new Error(data.detail||`HTTP ${response.status}`);return data;}
  async function postJson(url){const response=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});const data=await response.json();if(!response.ok)throw new Error(data.detail||`HTTP ${response.status}`);return data;}

  const releaseConflictMessage='Archivdateien wurden verändert oder ein Sicherheitskonflikt wurde festgestellt. Weitere Löschungen wurden gestoppt. Bereits gelöschte Arbeitskopien sind möglicherweise nicht wiederherstellbar. Prüfen Sie das Archiv und starten Sie die Freigabe ausdrücklich erneut. Noch vorhandene Arbeitsdateien und Archivkopien werden vollständig neu geprüft.';
  function showReleaseConflict(error){
    const dialog=document.createElement('dialog');
    const title=document.createElement('h2');title.textContent='Arbeitsbereich freigeben – unterbrochen';
    const message=document.createElement('p');message.textContent=releaseConflictMessage;
    const detail=document.createElement('p');detail.textContent=String(error||'');
    const close=document.createElement('button');close.textContent='Schließen';close.addEventListener('click',()=>dialog.close());
    dialog.append(title,message,detail,close);document.body.appendChild(dialog);
    dialog.addEventListener('close',()=>dialog.remove(),{once:true});dialog.showModal();
  }

  async function followRelease(jobId,eventId,result,verifyButton,releaseButton){
    const url=`/api/jobs/${encodeURIComponent(jobId)}/events/${encodeURIComponent(eventId)}/ssd-release/task`;
    const check=async()=>{
      try{
        const task=await getJson(url);
        const pct=Number.isFinite(Number(task.progress_percent))
          ? Math.round(Number(task.progress_percent))+" %" : "–";
        if(task.status==="completed"){
          result.className="result success";
          result.textContent="SSD-Freigabe abgeschlossen · "+pct;
          await load({forceRefresh:true});
          return;
        }
        if(task.status==="failed"){
          result.className="result danger";
          result.textContent="Freigabe angehalten: "+String(task.error_message||"Unbekannter Fehler")
            +" · Die bisherigen Prüfschritte bleiben gespeichert.";
          showReleaseConflict(task.error_message);
          releaseButton.textContent='Freigabe erneut versuchen';
          releaseButton.disabled=false;
          verifyButton.disabled=false;
          return;
        }
        result.textContent="Arbeitsbereich wird im Hintergrund freigegeben · "+pct
          +" · Ein Seitenwechsel oder Browser-Neustart unterbricht den Serverauftrag nicht.";
        setTimeout(check,2000);
      }catch(error){
        result.className="result danger";
        result.textContent="Auftragsstatus konnte nicht abgefragt werden: "+error.message;
      }
    };
    await check();
  }
  function eventStatusLabel(status){const labels={draft:'Entwurf',planned:'geplant',applied:'angewendet',archived:'archiviert'};return labels[String(status||'')]||String(status||'');}
    function formatDate(value){
    const date=new Date(value||'');
    if(Number.isNaN(date.getTime()))return 'Zeitpunkt unbekannt';
    return new Intl.DateTimeFormat((document.documentElement.lang === "de" ? "de-DE" : "en-US"),{dateStyle:'medium',timeStyle:'short'}).format(date);
  }
  function attachRecoveryAction(card,item){
    if(!Number(item.unresolved_recovery_count||0))return;
    const panel=document.createElement("div");
    panel.className="result danger";
    panel.innerHTML="<strong>Manuelle Archivklärung erforderlich</strong><p>Nach einem Notfallabbruch wurde der ursprüngliche Archivzustand noch nicht wieder bestätigt. Neue Änderungen bleiben gesperrt.</p>";
    const action=document.createElement("button");
    action.type="button"; action.className="plan-button";
    action.textContent="Originalbestand erneut prüfen";
    panel.appendChild(action);
    card.appendChild(panel);
    action.addEventListener("click",async()=>{
      action.disabled=true;
      try{
        const data=await postJson(`/api/archive/recovery/${encodeURIComponent(item.event_id)}/verify-and-unlock`);
        if(data.resolved){
          panel.className="result success";
          panel.textContent=data.message;
          await load({forceRefresh:true});
        }else{
          panel.className="result danger";
          panel.textContent=data.message+" "+(data.problems||[]).slice(0,4)
            .map(p=>String(p.path||"")+": "+String(p.message||"")).join(" · ");
        }
      }catch(error){panel.textContent=error.message;}
      finally{action.disabled=false;}
    });
  }
  function archiveHistoryCounts(item){
    const live=item.current_archive;
    const observation=live?.available
      ? `<span>${Number(live.file_count)} Dateien</span><span>${Number(live.family_count)} Familien</span><span>${Number(live.uncatalogued_file_count||0)} nicht katalogisiert</span>`
      : `<span>${escapeHtml(live?.error||'Aktueller Archivbestand nicht verfügbar.')}</span>`;
    return `<div class="meta"><strong>Aktueller Archivbestand</strong>${observation}</div>`
      + `<details class="archive-history-details"><summary>Historische Details anzeigen</summary><div class="muted">Verwaltungsdateien wie event.json werden nicht mitgezählt.</div>`
      + `<div class="muted">Bestand geprüft: <span data-bk-preserve-language>${escapeHtml(formatDate(live?.scanned_at))}</span></div>`
      + `<div class="meta"><strong>Historische Archivverifikation</strong><span>${Number(item.verification_file_count||0)} Dateien</span><span data-bk-preserve-language>${escapeHtml(formatDate(item.verification_completed_at))}</span></div></details>`;
  }
  function syncArchiveHistoryDetails() {
    // Native details start collapsed on every screen; retain user expansion.
  }
  function renderArchive(summary){
    candidateCount.textContent=summary.candidate_count;
    verifiedCount.textContent=summary.verified_count;
    releasedCount.textContent=summary.released_count||0;
    blockedCount.textContent=summary.blocked_count||0;
    archiveNotice.hidden=summary.archive_readable;
    archiveNotice.textContent=summary.archive_readable?'':`Kamerabibliothek ist noch nicht read-only unter ${summary.archive_root} eingebunden. Die Verwaltungsseite ist bereit; die Prüfung und Arbeitsbereich-Freigabe bleiben bis zur Einbindung gesperrt.`;
    archiveList.innerHTML=''; historyList.innerHTML='';
    const open=(summary.candidates||[]).filter(item=>!item.released);
    const history=(summary.candidates||[]).filter(item=>item.released);
    if(!open.length) archiveList.innerHTML='<div class="empty">Keine offenen Ereignisse zur Archivprüfung.</div>';
    for(const item of open){
      const card=document.createElement('article');card.className='card archive-check-card';
      const verification=item.released
        ?'Arbeitsbereich freigegeben'
        :(item.verified
          ?'Vollständig geprüft'
          :(item.verification_invalidated?'Erneut prüfen':(item.verification_status||'Noch nicht geprüft')));
      const releaseDisabled=!item.ssd_release_ready;
      const releaseLabel=item.released?'Arbeitsbereich freigegeben':'Arbeitsbereich freigeben';
      card.innerHTML=`<div class="item-head"><div><div class="title" data-bk-preserve-language>${escapeHtml(item.name)}</div><div class="path" data-bk-preserve-language>${escapeHtml(item.folder_name)}</div><div class="muted">Erstellt: ${escapeHtml(formatDate(item.event_created_at))}</div></div><span class="badge ${(item.verified||item.released)?'success':'warning'}">${escapeHtml(verification)}</span></div><div class="meta"><span>${Number(item.family_count||0)} Familien</span><span>${Number(item.file_count||0)} Dateien</span><span>${formatBytes(item.total_size_bytes)}</span><span>Status: ${escapeHtml(eventStatusLabel(item.status))}</span></div><div class="actions"><button class="verify archive-verify-button" ${summary.archive_readable?'':'disabled'}>Archiv prüfen</button><button class="release" ${releaseDisabled?'disabled':''}>${releaseLabel}</button></div><div class="result" hidden></div>`;
      const result=card.querySelector('.result');
      const verifyButton=card.querySelector('.verify');
      const releaseButton=card.querySelector('.release');
      verifyButton.addEventListener('click',async(event)=>{const button=event.currentTarget;button.disabled=true;button.classList.add('bk-busy');button.setAttribute('aria-busy','true');result.hidden=false;result.textContent='Kamerabibliothek wird vollständig per Größe und SHA-256 geprüft …';try{const data=await postJson(`/api/jobs/${encodeURIComponent(item.job_id)}/events/${encodeURIComponent(item.event_id)}/archive-verify`);result.className=`result ${data.verified?'success':'danger'}`;result.textContent=`${data.message} ${data.verified_file_count}/${data.file_count} Dateien bestätigt; ${data.missing_file_count} fehlen; ${data.mismatched_file_count} weichen ab.`;await load({forceRefresh:true});}catch(error){result.className='result danger';result.textContent=error.message;button.disabled=false;}finally{button.classList.remove('bk-busy');button.removeAttribute('aria-busy');}});
      releaseButton.addEventListener('click',async(event)=>{
        const button=event.currentTarget;
        try {
          const question=`Arbeitsbereich-Bestand für „${item.name}“ freigeben? Die Kamerabibliothek wird erneut vollständig geprüft; erst danach werden ausschließlich die bestätigten Dateien im Arbeitsbereich entfernt.` + '\n\nArchivdateien während der Freigabe nicht extern verändern. Gleichzeitige externe Änderungen können zum Verlust der letzten passenden Kopie führen; die Änderungsüberwachung bietet keine vollständige Erhaltungsgarantie.';
          const confirmation=window.BibliothekarI18n?.confirmAsync
            ? await window.BibliothekarI18n.confirmAsync(question)
            : window.confirm(window.BibliothekarI18n?.t?.(question) || question);
          if (!confirmation) return;
          button.disabled=true;verifyButton.disabled=true;
          result.hidden=false;result.className='result';
          result.textContent='Kamerabibliothek und Arbeitsbereich-Dateien werden erneut per SHA-256 geprüft. Anschließend wird nur der bestätigte SSD-Ereignisbestand entfernt …';
          const response=await postJson(`/api/jobs/${encodeURIComponent(item.job_id)}/events/${encodeURIComponent(item.event_id)}/ssd-release`);
          if (!response.task_id) throw new Error('Der Freigabeauftrag wurde vom Server nicht bestätigt.');
          window.dispatchEvent(new Event("bk-activity-refresh"));
          await followRelease(item.job_id,item.event_id,result,verifyButton,releaseButton);
        } catch(error) {
          result.hidden=false;result.className='result danger';result.textContent=error.message || String(error);
          button.disabled=false;verifyButton.disabled=false;
        }
      });
      // Reloading a page only observes persisted tasks; it never retries a POST.
      getJson(`/api/jobs/${encodeURIComponent(item.job_id)}/events/${encodeURIComponent(item.event_id)}/ssd-release/task`)
        .then(task=>{if(['failed','running','queued'].includes(task.status)){result.hidden=false;return followRelease(item.job_id,item.event_id,result,verifyButton,releaseButton);}}).catch(()=>{});
      attachRecoveryAction(card,item);
      archiveList.appendChild(card);
    }
    if(!history.length) historyList.innerHTML='<div class="empty">Noch keine freigegebenen Ereignisse im Verlauf.</div>';
    for(const item of history){
      const card=document.createElement('article');card.className='card';
      card.innerHTML=`<div class="item-head"><div><div class="title"><span class="muted history-field-label">Ereignisname im Katalog</span><span data-bk-preserve-language>${escapeHtml(item.name)}</span></div><div class="path"><span class="history-field-label">Aktueller Archivordner</span><span data-bk-preserve-language>${escapeHtml(item.current_archive?.event_prefix || item.folder_name)}</span></div><div class="muted">Erstellt: ${escapeHtml(formatDate(item.event_created_at))}</div></div><span class="badge success">Arbeitsbereich freigegeben</span></div>${archiveHistoryCounts(item)}`;
      attachRecoveryAction(card,item);
      historyList.appendChild(card);
    }
    syncArchiveHistoryDetails();
  }

  async function load({forceRefresh=false}={}){
    const snapshotKey = "bk-archive-0452:" + (window.__bkLibraryId || "main");
    if(!forceRefresh){
      try {
        const cached=JSON.parse(sessionStorage.getItem(snapshotKey) || "null");
        if(cached && Array.isArray(cached.candidates)) renderArchive(cached);
      } catch (_) {}
    }
    if(!archiveList.children.length)archiveList.innerHTML='<div class="empty bk-loading-status">Archiv wird geladen …</div>';
    if(!historyList.children.length)historyList.innerHTML='<div class="empty bk-loading-status">Archivverlauf wird geladen …</div>';
    const archive=await getJson('/api/archive/summary' + (forceRefresh ? '?force_refresh=true' : ''));
    renderArchive(archive);
    try {
      const value=JSON.stringify(archive);
      if(value.length<1200000)sessionStorage.setItem(snapshotKey,value);
    }catch(_){}
  }

  async function autoVerifyFromLocation(){
    const params=new URLSearchParams(location.search);
    const job=params.get('verify_job')||'';
    const eventId=params.get('verify_event')||'';
    if(!job||!eventId)return;
    archiveNotice.hidden=false;
    archiveNotice.textContent='Archivprüfung läuft …';
    try{
      const data=await postJson(
        `/api/jobs/${encodeURIComponent(job)}/events/${encodeURIComponent(eventId)}/archive-verify`
      );
      archiveNotice.hidden=false;
      archiveNotice.textContent=data.manual_archive_finalized
        ? data.message
        : `${data.message} ${data.verified_file_count}/${data.file_count} Dateien bestätigt.`;
      await load({forceRefresh:true});
      history.replaceState({},'',location.pathname);
    }catch(error){
      archiveNotice.hidden=false;
      archiveNotice.textContent=error.message;
    }
  }

  load()
    .then(autoVerifyFromLocation)
    .catch(error=>{archiveList.innerHTML=`<div class="notice">${escapeHtml(error.message)}</div>`;historyList.innerHTML='';});
</script>
</body>
</html>'''

from app.ui_rc13 import workspace_words as _workspace_words
TRANSFER_HTML = _workspace_words(TRANSFER_HTML)
