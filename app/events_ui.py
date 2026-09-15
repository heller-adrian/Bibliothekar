EVENTS_HTML = r"""<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta
    name="viewport"
    content="width=device-width, initial-scale=1, viewport-fit=cover"
  >

  <meta
    name="theme-color"
    content="#101114"
  >
  <title>Ereignisse verwalten</title>

  <style>
    :root {
      color-scheme: dark;
      --background: #101114;
      --surface: #191b20;
      --surface-2: #22252b;
      --surface-3: #292d35;
      --border: #373c47;
      --text: #f3f4f6;
      --muted: #a9afba;
      --accent: #8ab4ff;
      --success: #75d69c;
      --warning: #efc264;
      --danger: #ff7d75;
    }

    * {
      box-sizing: border-box;
    }

    html,
    body {
      min-height: 100%;
      background: #101114;
    }

    html {
      -webkit-text-size-adjust: 100%;
      text-size-adjust: 100%;
      overscroll-behavior-y: auto;
    }

    body {
      position: relative;
      min-height: 100vh;
      min-height: 100dvh;
      margin: 0;
      color: var(--text);
      font-family:
        -apple-system,
        BlinkMacSystemFont,
        "Segoe UI",
        sans-serif;
    }

    button,
    select,
    input,
    textarea {
      min-height: 44px;
      border: 1px solid var(--border);
      border-radius: 12px;
      background: var(--surface);
      color: var(--text);
      font: inherit;
    }

    button {
      padding: 10px 14px;
      cursor: pointer;
    }

    button:hover {
      border-color: var(--accent);
    }

    button:disabled {
      cursor: not-allowed;
      opacity: 0.55;
    }

    select, input, textarea {
      width: 100%;
      min-width: 0;
      padding: 10px 12px;
    }
    textarea { min-height: 110px; resize: vertical; }
    .edit-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:12px; }
    .no-event-segment { display:grid; grid-template-columns:minmax(170px,1.2fr) minmax(110px,.7fr) minmax(110px,.7fr) auto; align-items:end; padding:12px; border:1px solid #343942; border-radius:12px; margin-bottom:10px; }
    .no-event-segment .danger-button { width:auto; min-width:118px; align-self:end; padding:10px 12px; }
    @media (max-width:760px) { .no-event-segment { display:grid; grid-template-columns:1fr 1fr; } .no-event-segment .danger-button { grid-column:1/-1; justify-self:end; } }
    .edit-field { display:grid; gap:6px; }
    .edit-field.full { grid-column:1/-1; }
    .edit-family-list { display:grid; gap:8px; max-height:320px; overflow:auto; border:1px solid var(--border); border-radius:12px; padding:10px; background:var(--surface-2); }
    .edit-family { display:grid; grid-template-columns:auto minmax(0,1fr); gap:10px; align-items:start; padding:8px; border-radius:9px; }
    .edit-family input { width:20px; height:20px; margin-top:2px; }
    .edit-family.blocked { opacity:.55; }
    .edit-warning { border:1px solid var(--warning); border-radius:12px; padding:11px; color:var(--warning); }
    .edit-actions { display:flex; justify-content:flex-end; gap:10px; flex-wrap:wrap; margin-top:16px; }

    main {
      width: min(1120px, 100%);
      min-height: 100vh;
      min-height: 100dvh;
      margin: 0 auto;
      padding: 18px;
      padding-bottom: calc(18px + env(safe-area-inset-bottom));
      background: transparent;
    }

    h1,
    h2,
    h3,
    p {
      margin-top: 0;
    }

    h1 {
      margin-bottom: 5px;
      font-size: clamp(1.8rem, 5vw, 2.6rem);
    }

    .muted {
      color: var(--muted);
    }

    .header-top {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 18px;
      margin-bottom: 18px;
    }

    .navigation { display:flex; flex-wrap:wrap; gap:8px; }
    .navigation button[aria-current="page"] { border:2px solid #f2f3f5; background:var(--surface-2); opacity:1; color:var(--text); }
    .top-button { width:42px; min-width:42px; padding:0; font-size:1.2rem; }

    .toolbar {
      display: grid;
      grid-template-columns:
        minmax(220px, 1fr)
        auto;
      gap: 10px;
      margin-bottom: 16px;
    }

    .status {
      min-height: 24px;
      margin-bottom: 14px;
    }

    .error {
      color: var(--danger);
    }

    .success-text {
      color: var(--success);
    }

    .danger-text {
      color: var(--danger);
    }

    .plan-button.success {
      border-color: var(--success);
      color: var(--success);
    }

    .plan-button.danger {
      border-color: var(--danger);
      color: var(--danger);
    }

    .summary {
      display: grid;
      grid-template-columns:
        repeat(auto-fit, minmax(150px, 1fr));
      gap: 12px;
      margin-bottom: 20px;
    }

    .card {
      min-width: 0;
      border: 1px solid var(--border);
      border-radius: 16px;
      background: var(--surface);
      padding: 15px;
    }

    .number {
      display: block;
      margin-top: 5px;
      font-size: 1.65rem;
      font-weight: 700;
    }

    .intro {
      margin-bottom: 18px;
      border: 1px solid var(--border);
      border-radius: 14px;
      background: var(--surface-2);
      padding: 13px;
    }

    .event-list {
      display: grid;
      gap: 12px;
    }

    .event-card {
      min-width: 0;
      border: 1px solid var(--border);
      border-radius: 16px;
      background: var(--surface);
      padding: 16px;
    }

    .event-card-header {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 14px;
    }

    .event-title {
      margin-bottom: 5px;
      font-size: 1.15rem;
      font-weight: 750;
      overflow-wrap: anywhere;
    }

    .event-folder {
      color: var(--muted);
      overflow-wrap: anywhere;
    }

    .event-meta {
      display: flex;
      flex-wrap: wrap;
      gap: 7px 15px;
      margin-top: 12px;
      color: var(--muted);
      font-size: 0.92rem;
    }

    .badge {
      display: inline-flex;
      flex: 0 0 auto;
      border: 1px solid currentColor;
      border-radius: 999px;
      padding: 4px 8px;
      font-size: 0.78rem;
      font-weight: 700;
    }

    .badge.success {
      color: var(--success);
    }

    .badge.warning {
      color: var(--warning);
    }

    .children {
      display: grid;
      gap: 8px;
      margin-top: 13px;
      border-left: 2px solid var(--border);
      padding-left: 12px;
    }

    .child-event {
      min-width: 0;
      border-radius: 11px;
      background: var(--surface-2);
      padding: 10px 12px;
    }

    .child-title {
      font-weight: 700;
      overflow-wrap: anywhere;
    }

    .actions {
      display: flex;
      flex-wrap: wrap;
      justify-content: flex-end;
      gap: 8px;
      margin-top: 14px;
    }

    .danger-button {
      border-color: var(--danger);
      color: var(--danger);
    }

    .empty {
      border: 1px dashed var(--border);
      border-radius: 14px;
      padding: 22px;
      color: var(--muted);
    }


    .plan-button {
      border-color: var(--accent);
      color: var(--accent);
    }

    .sort-plan-dialog {
      inline-size: min(980px, calc(100dvw - 28px));
      max-inline-size: calc(100dvw - 28px);
      max-block-size: calc(100dvh - 28px);
      overflow: hidden;
      border: 1px solid var(--border);
      border-radius: 18px;
      background: var(--surface);
      color: var(--text);
      padding: 0;
    }

    .sort-plan-dialog::backdrop {
      background: rgb(0 0 0 / 0.76);
    }

    .sort-plan-content {
      max-height: calc(100dvh - 28px);
      overflow-y: auto;
      overflow-x: hidden;
      padding: 20px;
    }

    .sort-plan-header {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 14px;
      margin-bottom: 16px;
    }

    .sort-plan-header h2 {
      margin-bottom: 5px;
    }

    .sort-plan-summary {
      display: grid;
      grid-template-columns:
        repeat(auto-fit, minmax(135px, 1fr));
      gap: 10px;
      margin-bottom: 16px;
    }

    .sort-plan-summary .card {
      padding: 12px;
    }

    .sort-plan-section {
      margin-top: 18px;
    }

    .sort-plan-section h3 {
      margin-bottom: 8px;
    }

    .plan-ready {
      color: var(--success);
    }

    .plan-blocked {
      color: var(--danger);
    }

    .message-list {
      display: grid;
      gap: 8px;
    }

    .message-item {
      border: 1px solid var(--border);
      border-radius: 12px;
      background: var(--surface-2);
      padding: 10px 12px;
      overflow-wrap: anywhere;
    }

    .message-item.blocker {
      border-color: var(--danger);
      color: var(--danger);
    }

    .message-item.warning {
      border-color: var(--warning);
      color: var(--warning);
    }

    .plan-tree {
      margin: 0;
      overflow-x: auto;
      border: 1px solid var(--border);
      border-radius: 13px;
      background: var(--surface-2);
      padding: 13px;
      color: var(--text);
      font-family:
        ui-monospace,
        SFMono-Regular,
        Menlo,
        monospace;
      font-size: 0.88rem;
      line-height: 1.6;
      white-space: pre;
    }

    .path-box {
      display: grid;
      gap: 8px;
      border: 1px solid var(--border);
      border-radius: 13px;
      background: var(--surface-2);
      padding: 12px;
      font-family:
        ui-monospace,
        SFMono-Regular,
        Menlo,
        monospace;
      font-size: 0.83rem;
      overflow-wrap: anywhere;
    }

    .plan-file-list {
      display: grid;
      gap: 8px;
    }

    .plan-file {
      min-width: 0;
      border: 1px solid var(--border);
      border-radius: 12px;
      background: var(--surface-2);
      padding: 10px 12px;
    }

    .plan-file.blocked {
      border-color: var(--danger);
    }

    .plan-file-path {
      display: grid;
      grid-template-columns:
        minmax(0, 1fr)
        auto
        minmax(0, 1fr);
      gap: 8px;
      align-items: center;
      font-family:
        ui-monospace,
        SFMono-Regular,
        Menlo,
        monospace;
      font-size: 0.82rem;
    }

    .plan-file-path span {
      min-width: 0;
      overflow-wrap: anywhere;
    }

    .plan-file-meta {
      display: flex;
      flex-wrap: wrap;
      gap: 6px 12px;
      margin-top: 7px;
      color: var(--muted);
      font-size: 0.82rem;
    }

    .plan-target-list {
      display: grid;
      gap: 10px;
    }

    .plan-target-group,
    .plan-family {
      min-width: 0;
      overflow: hidden;
      border: 1px solid var(--border);
      border-radius: 13px;
      background: var(--surface-2);
    }

    .plan-target-group.blocked,
    .plan-family.blocked {
      border-color: var(--danger);
    }

    .plan-target-group > summary,
    .plan-family > summary {
      cursor: pointer;
      list-style-position: inside;
      padding: 12px 14px;
    }

    .plan-target-group > summary::marker,
    .plan-family > summary::marker {
      color: var(--accent);
    }

    .plan-target-group[open] > summary,
    .plan-family[open] > summary {
      border-bottom: 1px solid var(--border);
    }

    .plan-summary-grid {
      display: inline-grid;
      width: calc(100% - 22px);
      min-width: 0;
      grid-template-columns:
        minmax(0, 1fr)
        auto;
      gap: 8px 14px;
      vertical-align: top;
    }

    .plan-summary-lines {
      display: grid;
      min-width: 0;
      gap: 4px;
    }

    .plan-summary-title {
      min-width: 0;
      overflow-wrap: anywhere;
      font-weight: 750;
    }

    .plan-summary-meta,
    .plan-detail-hint {
      color: var(--muted);
      font-size: 0.84rem;
    }

    .plan-detail-hint {
      white-space: nowrap;
    }

    .plan-family-list {
      display: grid;
      gap: 8px;
      padding: 10px;
    }

    .plan-family {
      background: var(--surface-3);
    }

    .plan-family-detail {
      display: grid;
      gap: 10px;
      padding: 10px;
    }

    .plan-family-targets {
      display: grid;
      gap: 4px;
      border: 1px solid var(--border);
      border-radius: 10px;
      background: var(--surface-2);
      padding: 9px 10px;
      color: var(--muted);
      font-family:
        ui-monospace,
        SFMono-Regular,
        Menlo,
        monospace;
      font-size: 0.8rem;
      overflow-wrap: anywhere;
    }

    .plan-family-loading {
      color: var(--muted);
    }

    .sort-plan-footer {
      display: flex;
      justify-content: flex-end;
      margin-top: 20px;
    }

    .sort-apply-panel {
      display: grid;
      gap: 12px;
      margin-top: 20px;
      border: 1px solid var(--accent);
      border-radius: 14px;
      background:
        color-mix(
          in srgb,
          var(--accent) 10%,
          var(--surface-2)
        );
      padding: 14px;
    }

    .sort-apply-panel.blocked {
      border-color: var(--danger);
    }

    .sort-apply-confirm {
      display: flex;
      align-items: flex-start;
      gap: 10px;
      line-height: 1.45;
    }

    .sort-apply-confirm input {
      width: 22px;
      height: 22px;
      margin-top: 1px;
      flex: 0 0 auto;
    }

    .sort-apply-actions {
      display: flex;
      justify-content: flex-end;
      gap: 10px;
      flex-wrap: wrap;
    }

    .sort-apply-button {
      border-color: var(--danger);
      background: color-mix(
        in srgb,
        var(--danger) 20%,
        var(--surface)
      );
      color: var(--text);
    }

    .sort-run-progress {
      display: grid;
      gap: 10px;
      margin-top: 12px;
    }

    .sort-run-progress progress {
      width: 100%;
      height: 16px;
    }

    .sort-run-metrics {
      display: grid;
      grid-template-columns:
        repeat(auto-fit, minmax(130px, 1fr));
      gap: 8px;
    }

    .sort-run-metric {
      border: 1px solid var(--border);
      border-radius: 11px;
      background: var(--surface-2);
      padding: 10px;
    }

    .sort-run-result {
      border: 1px solid var(--border);
      border-radius: 12px;
      background: var(--surface-2);
      padding: 12px;
    }

    .sort-run-result.success {
      border-color: var(--success);
      color: var(--success);
    }

    .sort-run-result.error {
      border-color: var(--danger);
      color: var(--danger);
    }

    @media (max-width: 760px) {
      main {
        padding: 14px;
      }

      .header-top {
        display: block;
      }

      .navigation {
        margin-top: 12px;
      }

      .toolbar {
        grid-template-columns: 1fr;
      }

      .event-card-header {
        display: block;
      }

      .event-card-header .badge {
        margin-top: 10px;
      }
    }

    @media (max-width: 520px) {
      main {
        padding: 12px;
      }

      .navigation,
      .actions {
        display: grid;
        grid-template-columns: 1fr;
      }

      .navigation button,
      .actions button {
        width: 100%;
      }

      .sort-plan-content {
        padding: 14px;
      }

      .sort-plan-header {
        display: block;
      }

      .sort-plan-header button {
        width: 100%;
        margin-top: 10px;
      }

      .plan-file-path {
        grid-template-columns: 1fr;
      }

      .plan-file-path .arrow {
        transform: rotate(90deg);
        width: fit-content;
      }

      .plan-summary-grid {
        grid-template-columns: 1fr;
      }

      .plan-detail-hint {
        white-space: normal;
      }
    }
    html, body { background: #090b0d !important; min-height: 100%; }
    #refresh-button { display:none !important; }
    body::before { content: ""; position: fixed; inset: -120px 0; background: #090b0d; z-index: -1000; pointer-events: none; }
    .global-header { position:static; }
    .page-intro { margin-bottom:12px; }
    .global-navigation-bar { position:sticky; top:0; z-index:60; display:flex; align-items:center; gap:10px; margin-bottom:18px; padding:10px 0; background:rgba(9,11,13,.96); backdrop-filter:blur(16px); -webkit-backdrop-filter:blur(16px); }
    .global-navigation-bar .navigation { flex:1 1 auto; flex-wrap:nowrap; overflow-x:auto; scrollbar-width:none; }
    .global-navigation-bar .navigation::-webkit-scrollbar { display:none; }
    .global-navigation-bar .navigation button { flex:0 0 auto; white-space:nowrap; }
    .reassignment-list { display:grid; gap:8px; max-height:280px; overflow:auto; margin:12px 0; }
    .reassignment-family { display:grid; grid-template-columns:auto minmax(0,1fr); gap:10px; align-items:start; padding:10px; border:1px solid var(--border); border-radius:11px; background:var(--surface-2); }
    .reassignment-family input { width:20px; height:20px; margin-top:2px; }
    .reassignment-controls { display:grid; grid-template-columns:minmax(0,1fr) auto; gap:10px; align-items:end; }
    .reassignment-new-name { margin-top:10px; }
    .reassignment-new-name[hidden] { display:none !important; }
    .reassignment-resume { margin-top:12px; padding:10px 12px; border:1px solid var(--warning); border-radius:11px; background:rgba(255,193,7,.06); display:flex; flex-wrap:wrap; gap:10px; align-items:center; justify-content:space-between; }
    /* 0.20.7: Offene Neu-Zuordnung optisch sauber vom darunterliegenden
       <details>-Summary trennen. Auf schmalen Ansichten lag dessen native
       Marker-/Textzeile direkt auf dem gelben Rahmen. */
    .reassignment-resume + .event-details { margin-top:10px; }
    .reassignment-resume + .event-details > summary { display:inline-block; padding-top:2px; }
    .event-browser-toolbar { display:flex; gap:28px; align-items:end; justify-content:space-between; flex-wrap:wrap; margin:8px 0 20px; }
    .event-browser-heading { min-width:250px; }
    .event-browser-search { min-width:min(100%,380px); flex:0 1 420px; }
    .event-browser-search span { display:block; margin-bottom:7px; font-weight:650; }
    #event-list { margin-top:10px; }
    @media (max-width:640px) { .reassignment-controls { grid-template-columns:1fr; } }
  
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
      <h1>Ereignisse verwalten</h1>
      <p class="muted">
        Gespeicherte Planungen prüfen und noch nicht
        angewendete Planungen wieder freigeben.
      </p>
    </header>

    <div class="global-navigation-bar">
      <nav class="navigation" aria-label="Seitennavigation">
        <button type="button" onclick="location.href='/'">Import &amp; Prüfung</button>
        <button type="button" onclick="location.href='/workspace'">Sortieren</button>
        <button type="button" disabled aria-current="page">Ereignisse</button>
        <button type="button" onclick="location.href='/transfer'">Archiv</button>
      </nav>
      <button class="top-button" type="button" onclick="window.scrollTo({top:0,behavior:'smooth'})" aria-label="Nach oben">↑</button>
    </div>


    <p
      id="status"
      class="status muted"
      role="status"
      aria-live="polite"
    ></p>

    <div class="intro">
      <strong>Planung, Prüfung und bestätigte Sortierung</strong>
      <div class="muted">
        Der Sortierplan bleibt zunächst vollständig lesend. Erst nach
        einer zusätzlichen ausdrücklichen Bestätigung werden die Dateien
        im SSD-Arbeitsbereich vollständig per SHA-256 geprüft und anschließend
        ohne Überschreiben verschoben. Die Kamerabibliothek bleibt unberührt.
      </div>
    </div>

    <section
      id="summary"
      class="summary"
      aria-label="Ereignisübersicht"
    ></section>

    <section>
      <div class="event-browser-toolbar">
        <div class="event-browser-heading">
          <h2 style="margin-bottom:6px">Gespeicherte Ereignisse</h2>
          <div id="event-result-info" class="muted">Die zuletzt geänderten Ereignisse werden angezeigt.</div>
        </div>
        <label class="event-browser-search">
          <span>Ereignisse suchen</span>
          <input id="event-search" type="search" placeholder="Name, Datum oder Sicherung …" autocomplete="off">
        </label>
      </div>

      <div
        id="event-list"
        class="event-list"
      >
        <div class="empty">
          Ereignisse werden geladen …
        </div>
      </div>
      <div style="display:flex;justify-content:center;margin-top:14px">
        <button id="event-load-more" type="button" hidden>Weitere Ereignisse laden</button>
      </div>
    </section>
  </main>

  <dialog id="event-edit-dialog" class="sort-plan-dialog">
    <form id="event-edit-form" class="sort-plan-content" method="dialog">
      <div class="sort-plan-header">
        <div>
          <h2 id="event-edit-title">Ereignis bearbeiten</h2>
          <p id="event-edit-subtitle" class="muted"></p>
        </div>
        <button id="event-edit-close" type="button">Schließen</button>
      </div>
      <div id="event-edit-body">Bearbeitungsdaten werden geladen …</div>
    </form>
  </dialog>

  <dialog id="reassignment-dialog" class="sort-plan-dialog">
    <div class="sort-plan-content">
      <div class="sort-plan-header">
        <div>
          <h2>Herausfallende Tages-/Zeitsegmente neu zuordnen</h2>
          <p id="reassignment-subtitle" class="muted">Keine Datei bleibt ohne Ziel.</p>
        </div>
        <button id="reassignment-close" type="button">Schließen</button>
      </div>
      <div id="reassignment-body">Neu-Zuordnung wird geladen …</div>
    </div>
  </dialog>

  <dialog
    id="sort-plan-dialog"
    class="sort-plan-dialog"
  >
    <div class="sort-plan-content">
      <div class="sort-plan-header">
        <div>
          <h2 id="sort-plan-title">
            Sortierung prüfen
          </h2>
          <p
            id="sort-plan-subtitle"
            class="muted"
          >
            Rein lesende Vorschau. Es wird nichts verändert.
          </p>
        </div>

        <button
          id="sort-plan-close-button"
          type="button"
        >
          Schließen
        </button>
      </div>

      <div
        id="sort-plan-body"
        aria-live="polite"
      >
        Sortierplan wird geladen …
      </div>
    </div>
  </dialog>

  <dialog id="change-request-dialog" class="sort-plan-dialog">
    <div class="sort-plan-content">
      <div class="sort-plan-header">
        <div>
          <h2 id="change-request-title">Änderungsauftrag</h2>
          <p id="change-request-subtitle" class="muted"></p>
        </div>
        <button id="change-request-close" type="button">Schließen</button>
      </div>
      <div id="change-request-body">Änderungsauftrag wird geladen …</div>
    </div>
  </dialog>

  
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


    const statusElement =
      document.getElementById("status");

    const summaryElement =
      document.getElementById("summary");

    const eventList =
      document.getElementById("event-list");
    const eventSearch = document.getElementById("event-search");
    const eventLoadMore = document.getElementById("event-load-more");
    const eventResultInfo = document.getElementById("event-result-info");
    let eventOffset = 0;
    const eventLimit = 25;
    let eventSearchTimer = null;

    const sortPlanDialog =
      document.getElementById("sort-plan-dialog");

    const sortPlanTitle =
      document.getElementById("sort-plan-title");

    const sortPlanSubtitle =
      document.getElementById("sort-plan-subtitle");

    const sortPlanBody =
      document.getElementById("sort-plan-body");

    const sortPlanCloseButton =
      document.getElementById(
        "sort-plan-close-button"
      );

    const eventEditDialog = document.getElementById("event-edit-dialog");
    const eventEditForm = document.getElementById("event-edit-form");
    const eventEditTitle = document.getElementById("event-edit-title");
    const eventEditSubtitle = document.getElementById("event-edit-subtitle");
    const eventEditBody = document.getElementById("event-edit-body");
    const eventEditClose = document.getElementById("event-edit-close");
    let currentEditContext = null;

    const reassignmentDialog = document.getElementById("reassignment-dialog");
    const reassignmentBody = document.getElementById("reassignment-body");
    const reassignmentSubtitle = document.getElementById("reassignment-subtitle");
    const reassignmentClose = document.getElementById("reassignment-close");
    let reassignmentContext = null;

    const changeRequestDialog =
      document.getElementById("change-request-dialog");

    const changeRequestTitle =
      document.getElementById("change-request-title");

    const changeRequestSubtitle =
      document.getElementById("change-request-subtitle");

    const changeRequestBody =
      document.getElementById("change-request-body");

    const changeRequestClose =
      document.getElementById("change-request-close");

    let jobs = [];
    let currentEvents = [];
    let currentSortPlan = null;


    function escapeHtml(value) {
      return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
    }


    function setStatus(
      message,
      isError = false,
      isSuccess = false
    ) {
      statusElement.textContent = message;
      statusElement.classList.toggle(
        "error",
        isError
      );
      statusElement.classList.toggle(
        "success-text",
        isSuccess
      );
    }


    function formatJobLabel(job) {
      const date = new Date(job.created_at);

      const formattedDate =
        Number.isNaN(date.getTime())
          ? String(job.created_at || job.id)
          : new Intl.DateTimeFormat(
              "de-DE",
              {
                dateStyle: "short",
                timeStyle: "medium"
              }
            ).format(date);

      const sourceName =
        job.source_volume_label
        || (
          job.operation === "metadata_fixture_analysis"
            ? "Metadaten-Testbestand"
            : job.operation === "folder_import"
              ? "Ordnerimport"
              : job.kind === "simulation"
                ? "Simulierter SD-Import"
                : "SD-Kartenimport"
        );

      return `${sourceName} · ${formattedDate}`;
    }


    function formatDateTime(value) {
      const raw = String(value || "");
      const date = new Date(raw);

      if (Number.isNaN(date.getTime())) {
        return raw;
      }

      const hasMeaningfulTime =
        !raw.includes("T00:00:00")
        && !raw.includes("T23:59:59");

      return new Intl.DateTimeFormat(
        "de-DE",
        hasMeaningfulTime
          ? {
              dateStyle: "medium",
              timeStyle: "short"
            }
          : {
              dateStyle: "medium"
            }
      ).format(date);
    }


    function formatBytes(value) {
      const bytes = Number(value || 0);

      if (bytes < 1024) {
        return `${bytes} B`;
      }

      const units = [
        "KiB",
        "MiB",
        "GiB",
        "TiB"
      ];

      let current = bytes / 1024;
      let index = 0;

      while (
        current >= 1024
        && index < units.length - 1
      ) {
        current /= 1024;
        index += 1;
      }

      return `${current.toLocaleString(
        "de-DE",
        {
          maximumFractionDigits: 1
        }
      )} ${units[index]}`;
    }


    function isSortPlannable(event) {
      return (
        ["draft", "planned"].includes(
          event.status
        )
        && !event.applied_at
        && !event.archived_at
      );
    }


    async function requestJson(
      url,
      options = {}
    ) {
      const response = await fetch(
        url,
        options
      );

      const raw = await response.text();
      let data = {};
      if (raw) {
        try {
          data = JSON.parse(raw);
        } catch (_) {
          data = {detail: raw};
        }
      }

      if (!response.ok) {
        const error = new Error(data.detail || `Anfrage fehlgeschlagen (HTTP ${response.status}).`);
        error.data = data;
        error.status = response.status;
        throw error;
      }

      return data;
    }


    function openWorkspace() {
      location.href = "/workspace";
    }


    async function loadJobs() {
      // 0.16.6: Die Ereignisverwaltung lädt nicht mehr erst alle Sicherungen.
      // Der Name bleibt aus Kompatibilitätsgründen bestehen; die eigentliche
      // Arbeit erledigt die paginierte globale Ereignissuche.
      await loadEvents({reset:true});
    }


    function renderEmpty(message) {
      summaryElement.innerHTML = "";
      eventList.innerHTML = `
        <div class="empty">
          ${escapeHtml(message)}
        </div>
      `;
    }


    function renderSummary(events) {
      const familyCount = events.reduce((sum,event)=>sum+Number(event.assigned_family_count||0),0);
      const deletableCount = events.filter(isDeletable).length;
      const cards = [
        ["Angezeigte Ereignisse", events.length],
        ["Zugeordnete Familien", familyCount],
        ["Löschbare Planungen", deletableCount]
      ];
      summaryElement.innerHTML = cards.map(([label,value])=>`
        <article class="card"><span class="muted">${escapeHtml(label)}</span><strong class="number">${Number(value)}</strong></article>
      `).join("");
    }


    function isDeletable(event) {
      return ["draft","planned","applied","archived"].includes(event.status)
        && !Number(event.pending_delete||0)
        && !event.mutation_id;
    }


    function renderEvents(events) {
      currentEvents = events;
      renderSummary(events);
      eventList.innerHTML = "";
      if (!events.length) {
        renderEmpty("Keine passenden Ereignisse gefunden.");
        return;
      }
      for (const event of events) {
        const card = document.createElement("article");
        card.className = "event-card";
        card.dataset.eventId = event.id;
        card.dataset.jobId = event._job_id || event.job_id || "";
        const statusClass = ["planned","applied","archived"].includes(event.status) ? event.status : "";
        const isMutationAnchor = event.mutation_id && event.id === event.mutation_anchor_event_id;
        const reassign = Number(event.pending_reassignment_count||0) > 0 ? `
          <div class="reassignment-resume">
            <span><strong>⚠ ${Number(event.pending_reassignment_count)} ${Number(event.pending_reassignment_count)===1?"Familie":"Familien"} noch neu zuzuordnen</strong><br><span class="muted">Die Änderung bleibt bis zur Neu-Zuordnung im sicheren Schwebezustand. Ursprungs- und Zielzustand sind weiterhin nachvollziehbar.</span></span>
            <div style="display:flex;gap:8px;flex-wrap:wrap;justify-content:flex-end">
              <button type="button" class="plan-button" data-reassign-workspace="${escapeHtml(event.id)}" data-job-id="${escapeHtml(event._job_id||event.job_id||"")}">In Sortieren öffnen</button>
              ${isMutationAnchor ? `<button type="button" class="danger-button" data-cancel-mutation="${escapeHtml(event.mutation_id)}" data-job-id="${escapeHtml(event._job_id||event.job_id||"")}">Änderung verwerfen</button>` : ""}
            </div>
          </div>` : "";
        const mutation = isMutationAnchor && Number(event.pending_reassignment_count||0) === 0 ? `
          <div class="reassignment-resume"><span><strong>⚠ Änderung noch nicht angewendet</strong><br><span class="muted">Die Neu-Zuordnung ist vollständig. Die neue Struktur ist gespeichert, aber die verifizierte Nachsortierung auf der SSD steht noch aus.</span></span><button type="button" class="danger-button" data-cancel-mutation="${escapeHtml(event.mutation_id)}" data-job-id="${escapeHtml(event._job_id||event.job_id||"")}">Änderung verwerfen</button></div>` : "";
        card.innerHTML = `
          <div class="event-card-header"><div><strong class="event-name">${escapeHtml(event.name)}</strong><div class="event-folder">${escapeHtml(event.folder_name||"")}</div><div class="muted">${escapeHtml(String(event.start_datetime||"").slice(0,16))} bis ${escapeHtml(String(event.end_datetime||"").slice(0,16))} · ${Number(event.assigned_family_count||0)} Familien</div></div><span class="status-chip ${statusClass}">${escapeHtml(event.status)}</span></div>
          ${mutation}
          ${reassign}
          <details class="event-details"><summary>Öffnen</summary><div class="event-actions">
            <button type="button" data-edit-event="${escapeHtml(event.id)}" data-job-id="${escapeHtml(event._job_id||event.job_id||"")}" ${event.mutation_id ? 'disabled title="Offene Änderung zuerst abschließen oder verwerfen"' : ''}>Bearbeiten</button>
            <button type="button" class="plan-button" data-sort-plan-event="${escapeHtml(event.id)}" data-job-id="${escapeHtml(event._job_id||event.job_id||"")}" data-event-status="${escapeHtml(event.status)}">${event.status === "applied" ? "Nachsortierung prüfen" : "Sortierung prüfen"}</button>
            ${isDeletable(event)
              ? `<button type="button" class="danger-button" data-delete-event="${escapeHtml(event.id)}" data-job-id="${escapeHtml(event._job_id||event.job_id||"")}">Ereignis löschen</button>`
              : event.mutation_id
                ? `<button type="button" class="danger-button" disabled title="Offene Änderung dieser Sicherung zuerst abschließen oder verwerfen">Ereignis löschen</button>`
                : ""}
          </div></details>`;
        eventList.appendChild(card);
      }
    }


    async function loadEvents({reset=false}={}) {
      if (reset) eventOffset = 0;
      setStatus("Ereignisse werden geladen …");
      const q = eventSearch?.value?.trim() || "";
      const data = await requestJson(`/api/events/search?q=${encodeURIComponent(q)}&limit=${eventLimit}&offset=${eventOffset}`);
      const page = (data.events||[]).map(event=>({
        ...event,
        _job_id:event.job_id,
        _job_label:event.source_volume_label || event.job_id,
      }));
      const merged = reset ? page : [...currentEvents, ...page.filter(e=>!currentEvents.some(x=>x.id===e.id))];
      renderEvents(merged);
      eventOffset = merged.length;
      eventLoadMore.hidden = !data.has_more;
      const shown = merged.length;
      eventResultInfo.textContent = q
        ? `${shown} von ${Number(data.matching_count||0)} Treffern · insgesamt ${Number(data.total_count||0)} Ereignisse`
        : `${shown} von ${Number(data.total_count||0)} Ereignissen · zuletzt geändert`;
      setStatus(shown===1 ? "1 Ereignis geladen." : `${shown} Ereignisse geladen.`);
    }


    function planStatusLabel(status) {
      const labels = {
        move: "Verschieben",
        already_at_target: "Bereits am Ziel",
        blocked_missing_source: "Quelle fehlt",
        blocked_target_exists: "Ziel belegt",
        blocked_size_mismatch: "Größe abweichend",
        blocked_checksum_mismatch: "SHA-256 abweichend"
      };

      return labels[status] || status;
    }


    function renderMessageList(
      items,
      className,
      emptyMessage
    ) {
      if (!items.length) {
        return `
          <div class="message-item">
            ${escapeHtml(emptyMessage)}
          </div>
        `;
      }

      return `
        <div class="message-list">
          ${items.map(
            item => `
              <div class="message-item ${className}">
                ${escapeHtml(item.message)}
              </div>
            `
          ).join("")}
        </div>
      `;
    }


    function mediaTypeLabel(value) {
      const key = String(value || "other").toLowerCase();
      const labels = {
        jpeg: "JPEG",
        jpg: "JPEG",
        raw: "RAW",
        raf: "RAW",
        xmp: "XMP",
        heic: "HEIC",
        heif: "HEIF",
        png: "PNG",
        tiff: "TIFF",
        tif: "TIFF",
        video: "Video",
        mov: "Video",
        mp4: "Video",
        other: "Sonstige"
      };

      return labels[key] || key.toUpperCase();
    }


    function countLabel(
      value,
      singular,
      plural
    ) {
      const count = Number(value || 0);
      return `${count} ${count === 1 ? singular : plural}`;
    }


    function renderPlanFileCard(file) {
      const blocked = String(file.status)
        .startsWith("blocked_");

      return `
        <article class="plan-file ${
          blocked ? "blocked" : ""
        }">
          <div class="plan-file-path">
            <span>
              ${escapeHtml(
                file.source_relative_path
              )}
            </span>
            <span class="arrow">→</span>
            <span>
              ${escapeHtml(
                file.destination_relative_path
              )}
            </span>
          </div>

          <div class="plan-file-meta">
            <span>
              ${escapeHtml(
                planStatusLabel(file.status)
              )}
            </span>
            <span>
              ${formatBytes(
                file.expected_size_bytes
              )}
            </span>
            <span>
              ${escapeHtml(
                mediaTypeLabel(file.media_type)
              )}
            </span>
            <span>
              Größe: ${
                file.size_matches
                  ? "stimmt"
                  : "abweichend"
              }
            </span>
          </div>
        </article>
      `;
    }


    function renderFamilyDetails(
      container,
      family
    ) {
      const targetDirectories =
        family.target_directories || [];
      const files = family.files || [];

      const targetHtml = targetDirectories.length
        ? targetDirectories.map(
            target => `
              <div>
                Ziel: ${escapeHtml(target)}
              </div>
            `
          ).join("")
        : `
            <div>
              Kein eindeutiger Zielordner vorhanden.
            </div>
          `;

      container.innerHTML = `
        <div class="plan-family-targets">
          ${targetHtml}
        </div>

        <div class="plan-file-list">
          ${files.map(
            renderPlanFileCard
          ).join("") || `
            <div class="empty">
              Keine Einzeldateien in dieser Familie.
            </div>
          `}
        </div>
      `;
    }


    function renderSortPlan(plan) {
      currentSortPlan = plan;

      const summary = plan.summary || {};
      const ready = Boolean(summary.ready);
      const targetGroups = plan.target_groups || [];
      const filesById = new Map(
        (plan.files || []).map(
          file => [Number(file.file_id), file]
        )
      );
      const familiesByKey = new Map(
        (plan.families || []).map(
          family => [String(family.group_key), family]
        )
      );
      const familyLookup = new Map();
      let familyIndex = 0;

      sortPlanTitle.textContent =
        `Sortierplan · ${plan.event.name}`;

      sortPlanSubtitle.textContent = ready
        ? "Die rein lesende Prüfung ist ohne Blocker abgeschlossen."
        : "Die Planung ist blockiert. Es wurde nichts verändert.";

      const cards = [
        [
          "Ergebnis",
          ready ? "Bereit" : "Blockiert"
        ],
        ["Dateien", summary.file_count || 0],
        ["Familien", summary.family_count || 0],
        [
          "Zielgruppen",
          summary.target_group_count || 0
        ],
        [
          "Neue Ordner",
          summary.directory_create_count || 0
        ],
        [
          "Datenmenge",
          formatBytes(summary.total_size_bytes)
        ],
        ["Blocker", summary.blocker_count || 0]
      ];

      const targetGroupsHtml = targetGroups.map(
        target => {
          const familyHtml = (
            target.family_group_keys || []
          ).map(
            familyKey => {
              const family = familiesByKey.get(
                String(familyKey)
              );

              if (!family) {
                return "";
              }

              const familyWithFiles = {
                ...family,
                files: (family.file_ids || [])
                  .map(fileId => filesById.get(Number(fileId)))
                  .filter(Boolean)
              };

              const index = familyIndex;
              familyIndex += 1;
              familyLookup.set(index, familyWithFiles);

              const mediaTypes = (
                family.media_types || []
              ).map(mediaTypeLabel).join(", ")
                || "Keine Typangabe";

              return `
                <details
                  class="plan-family ${
                    family.ready ? "" : "blocked"
                  }"
                  data-family-index="${index}"
                >
                  <summary>
                    <span class="plan-summary-grid">
                      <span class="plan-summary-lines">
                        <span class="plan-summary-title">
                          Familie: ${escapeHtml(
                            family.display_name
                          )}
                        </span>
                        <span class="plan-summary-meta">
                          ${escapeHtml(
                            countLabel(
                              family.file_count,
                              "Datei",
                              "Dateien"
                            )
                          )}
                          · ${escapeHtml(mediaTypes)}
                          · ${formatBytes(
                            family.total_size_bytes
                          )}
                        </span>
                      </span>
                      <span class="plan-detail-hint">
                        Einzeldateien anzeigen
                      </span>
                    </span>
                  </summary>

                  <div
                    class="plan-family-detail"
                    data-family-detail
                  >
                    <span class="plan-family-loading">
                      Details werden beim Öffnen geladen.
                    </span>
                  </div>
                </details>
              `;
            }
          ).join("");

          const targetName =
            target.target_relative_path
            || target.display_name
            || "Mehrere Ziele";

          return `
            <details
              class="plan-target-group ${
                target.ready ? "" : "blocked"
              }"
            >
              <summary>
                <span class="plan-summary-grid">
                  <span class="plan-summary-lines">
                    <span class="plan-summary-title">
                      Ziel: ${escapeHtml(targetName)}
                    </span>
                    <span class="plan-summary-meta">
                      ${escapeHtml(
                        countLabel(
                          target.family_count,
                          "Familie",
                          "Familien"
                        )
                      )}
                      · ${escapeHtml(
                        countLabel(
                          target.file_count,
                          "Datei",
                          "Dateien"
                        )
                      )}
                      · ${formatBytes(
                        target.total_size_bytes
                      )}
                    </span>
                  </span>
                  <span class="plan-detail-hint">
                    Familien anzeigen
                  </span>
                </span>
              </summary>

              <div class="plan-family-list">
                ${familyHtml || `
                  <div class="empty">
                    Keine Familien für dieses Ziel.
                  </div>
                `}
              </div>
            </details>
          `;
        }
      ).join("");

      sortPlanBody.innerHTML = `
        <div class="sort-plan-summary">
          ${cards.map(
            ([label, value], index) => `
              <article class="card">
                <span class="muted">
                  ${escapeHtml(label)}
                </span>
                <strong class="number ${
                  index === 0
                    ? (
                        ready
                          ? "plan-ready"
                          : "plan-blocked"
                      )
                    : ""
                }">
                  ${escapeHtml(value)}
                </strong>
              </article>
            `
          ).join("")}
        </div>

        <section class="sort-plan-section">
          <h3>Sicherheitsstatus</h3>
          <div class="path-box">
            <div>
              Modus: rein lesender Sortierplan
            </div>
            <div>
              Dateien verändert: nein
            </div>
            <div>
              Ordner verändert: nein
            </div>
            <div>
              Datenbank verändert: nein
            </div>
            <div>
              Gleiches Dateisystem: ${
                summary.same_filesystem
                  ? "ja"
                  : "nein"
              }
            </div>
            <div>
              Familien auf mehrere Ziele verteilt: ${
                Number(summary.family_split_count || 0)
              }
            </div>
          </div>
        </section>

        <section class="sort-plan-section">
          <h3>Arbeitsbestand</h3>
          <div class="path-box">
            <div>
              Quelle: ${escapeHtml(plan.source_root)}
            </div>
            <div>
              Ziel: ${escapeHtml(plan.target_root)}
            </div>
            <div>
              Freier Speicher: ${formatBytes(
                summary.available_bytes
              )}
            </div>
          </div>
        </section>

        <section class="sort-plan-section">
          <h3>Zielstruktur</h3>
          <pre class="plan-tree">${escapeHtml(
            plan.structure_text
          )}</pre>
        </section>

        <section class="sort-plan-section">
          <h3>Blocker</h3>
          ${renderMessageList(
            plan.blockers || [],
            "blocker",
            "Keine Blocker erkannt."
          )}
        </section>

        <section class="sort-plan-section">
          <h3>Hinweise</h3>
          ${renderMessageList(
            plan.warnings || [],
            "warning",
            "Keine zusätzlichen Hinweise."
          )}
        </section>

        <section class="sort-plan-section">
          <h3>
            Geplante Ziele
            (${Number(summary.target_group_count || 0)})
          </h3>

          <p class="muted">
            Die Standardansicht ist nach Zielordnern gruppiert.
            Zielgruppen zeigen zunächst nur Familien- und Dateianzahl.
            Familien lassen sich anschließend bis zu den vollständigen
            Einzeldateipfaden aufklappen.
          </p>

          <div class="plan-target-list">
            ${targetGroupsHtml || `
              <div class="empty">
                Keine Zielgruppen im Sortierplan.
              </div>
            `}
          </div>
        </section>

        ${ready ? `
          <section class="sort-apply-panel">
            <strong>Sortierung anwenden</strong>

            <div class="muted">
              Nach der Bestätigung werden alle Quelldateien noch einmal
              vollständig per SHA-256 geprüft. Erst danach werden sie
              innerhalb des SSD-Arbeitsbereichs ohne Überschreiben an die
              geplanten Ziele verschoben. Bei einem Fehler wird automatisch
              zurückgerollt.
            </div>

            <label class="sort-apply-confirm">
              <input
                id="sort-apply-confirmation"
                type="checkbox"
              >
              <span>
                Ich bestätige diesen Zielplan. Die Kamerabibliothek bleibt
                unberührt; verändert wird ausschließlich der angezeigte
                SSD-Arbeitsbestand.
              </span>
            </label>

            <div class="sort-apply-actions">
              <button
                id="sort-apply-button"
                class="sort-apply-button"
                type="button"
                disabled
              >
                Sortierung jetzt anwenden
              </button>
            </div>

            <div
              id="sort-run-status"
              class="sort-run-progress"
              hidden
              aria-live="polite"
            ></div>
          </section>
        ` : `
          <section class="sort-apply-panel blocked">
            <strong>Sortierung blockiert</strong>
            <div class="muted">
              Die Sortierung kann erst angewendet werden, wenn alle Blocker
              beseitigt sind und der Plan erneut mit „Bereit“ abgeschlossen wird.
            </div>
          </section>
        `}
      `;

      sortPlanBody
        .querySelectorAll(".plan-family")
        .forEach(details => {
          details.addEventListener(
            "toggle",
            () => {
              if (
                !details.open
                || details.dataset.loaded === "true"
              ) {
                return;
              }

              const index = Number(
                details.dataset.familyIndex
              );
              const family = familyLookup.get(index);
              const container = details.querySelector(
                "[data-family-detail]"
              );

              if (!family || !container) {
                return;
              }

              renderFamilyDetails(
                container,
                family
              );
              details.dataset.loaded = "true";
            }
          );
        });

      const applyConfirmation =
        document.getElementById(
          "sort-apply-confirmation"
        );

      const applyButton =
        document.getElementById(
          "sort-apply-button"
        );

      if (applyConfirmation && applyButton) {
        applyConfirmation.addEventListener(
          "change",
          () => {
            applyButton.disabled =
              !applyConfirmation.checked;
          }
        );

        applyButton.addEventListener(
          "click",
          () => applyCurrentSortPlan().catch(
            error => {
              const statusContainer =
                document.getElementById(
                  "sort-run-status"
                );

              if (statusContainer) {
                statusContainer.hidden = false;
                statusContainer.innerHTML = `
                  <div class="sort-run-result error">
                    ${escapeHtml(error.message)}
                  </div>
                `;
              }

              setStatus(
                error.message,
                true
              );
            }
          )
        );
      }
    }

    function renderSortRunProgress(run) {
      const container =
        document.getElementById(
          "sort-run-status"
        );

      if (!container) {
        return;
      }

      container.hidden = false;

      const status = String(
        run.status || ""
      );
      const terminal = Boolean(run.terminal);
      const success = status === "applied";
      const failed = [
        "rolled_back",
        "failed",
        "interrupted"
      ].includes(status);

      const resultHtml = terminal
        ? `
          <div class="sort-run-result ${
            success ? "success" : "error"
          }">
            ${escapeHtml(
              success
                ? "Sortierung vollständig angewendet und geprüft."
                : (
                    run.error_message
                    || run.phase
                    || "Sortierlauf wurde nicht abgeschlossen."
                  )
            )}
          </div>
        `
        : "";

      container.innerHTML = `
        <strong>${escapeHtml(run.phase || status)}</strong>

        <progress
          max="100"
          value="${Number(run.progress_percent || 0)}"
        ></progress>

        <div class="sort-run-metrics">
          <div class="sort-run-metric">
            <div class="muted">Fortschritt</div>
            <strong>${Number(run.progress_percent || 0)} %</strong>
          </div>
          <div class="sort-run-metric">
            <div class="muted">SHA-256 geprüft</div>
            <strong>
              ${Number(run.verified_file_count || 0)}
              / ${Number(run.file_count || 0)}
            </strong>
          </div>
          <div class="sort-run-metric">
            <div class="muted">Verschoben</div>
            <strong>
              ${Number(run.moved_file_count || 0)}
              / ${Number(run.move_count || 0)}
            </strong>
          </div>
          <div class="sort-run-metric">
            <div class="muted">Datenmenge</div>
            <strong>${formatBytes(run.moved_bytes || 0)}</strong>
          </div>
        </div>

        ${resultHtml}
      `;
    }

    async function pollSortRun(
      jobId,
      runId
    ) {
      while (true) {
        const run = await requestJson(
          `/api/jobs/${
            encodeURIComponent(jobId)
          }/sort-runs/${
            encodeURIComponent(runId)
          }`
        );

        renderSortRunProgress(run);

        if (run.terminal) {
          if (run.status === "applied") {
            await loadEvents();
            setStatus(
              "Sortierung vollständig angewendet und geprüft.",
              false,
              true
            );
          } else {
            setStatus(
              run.error_message
                || run.phase
                || "Sortierung wurde nicht abgeschlossen.",
              true
            );
          }

          return run;
        }

        await new Promise(
          resolve => setTimeout(resolve, 800)
        );
      }
    }

    async function applyCurrentSortPlan() {
      const plan = currentSortPlan;
      const jobId = plan?._job_id || plan?.job?.id;

      if (!plan || !jobId) {
        throw new Error(
          "Der bestätigte Sortierplan ist nicht mehr verfügbar."
        );
      }

      if (!plan.summary?.ready) {
        throw new Error(
          "Ein blockierter Sortierplan kann nicht angewendet werden."
        );
      }

      const applyButton =
        document.getElementById(
          "sort-apply-button"
        );
      const confirmation =
        document.getElementById(
          "sort-apply-confirmation"
        );
      const statusContainer =
        document.getElementById(
          "sort-run-status"
        );

      if (!confirmation?.checked) {
        throw new Error(
          "Die ausdrückliche Bestätigung fehlt."
        );
      }

      if (applyButton) {
        applyButton.disabled = true;
      }
      confirmation.disabled = true;

      if (statusContainer) {
        statusContainer.hidden = false;
        statusContainer.innerHTML = `
          <strong>Sortierlauf wird angelegt …</strong>
        `;
      }

      const sortEndpoint = plan._reconcile
        ? "reconcile-sort"
        : (plan._reapply ? "reapply-sort" : "apply-sort");

      const response = await requestJson(
        `/api/jobs/${
          encodeURIComponent(jobId)
        }/events/${
          encodeURIComponent(plan.event.id)
        }/${sortEndpoint}`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify({
            plan_token: plan.plan_token,
            confirmation_phrase:
              plan.apply_confirmation_phrase
          })
        }
      );

      renderSortRunProgress(response.run);

      return pollSortRun(
        jobId,
        response.run.id
      );
    }


    function isoDate(value) {
      const raw = String(value || "");
      // Robuster Fallback: NULL/leere oder ungültige Datums-/Zeitwerte
      // muessen in gueltige Formularelemente ueberfuehrt werden, sonst
      // loest type="date" die Browser-Validierung "The string did not
      // match the expected pattern" aus.
      const m = raw.match(/^\d{4}-\d{2}-\d{2}/);
      return m ? m[0] : "1970-01-01";
    }

    function isoTime(value, fallback) {
      const raw = String(value || "");
      const m = raw.match(/\d{2}:\d{2}/);
      if (m) return m[0];
      const fb = String(fallback || "");
      const fm = fb.match(/^\d{2}:\d{2}$/);
      return fm ? fb : "00:00";
    }

    function noEventMonthKey(event, segments) {
      const first=String((segments||[])[0]?.day_key || event?.start_datetime || "");
      const m=first.match(/^(\d{4}-\d{2})/);
      return m ? m[1] : "";
    }

    function noEventDayControl(monthKey, day, structural) {
      const dayPart=/^\d{4}-\d{2}-(\d{2})$/.exec(day||"")?.[1] || "";
      if (!monthKey) return `<label class="edit-field"><span>Tag</span><input type="date" data-segment-day value="${escapeHtml(day)}" ${structural?"":"disabled"}></label>`;
      const maxDay=new Date(Number(monthKey.slice(0,4)),Number(monthKey.slice(5,7)),0).getDate();
      return `<div style="display:grid;grid-template-columns:minmax(118px,.85fr) minmax(86px,.55fr);gap:8px;align-items:end"><label class="edit-field"><span>Monat/Jahr</span><input value="${escapeHtml(monthKey.slice(5,7)+"/"+monthKey.slice(0,4))}" disabled></label><label class="edit-field"><span>Tag</span><input type="number" data-segment-day-number min="1" max="${maxDay}" value="${escapeHtml(dayPart?String(Number(dayPart)):"")}" ${structural?"":"disabled"}></label><input type="hidden" data-segment-day value="${escapeHtml(day)}"></div>`;
    }

    function contiguousDayRangesFromValues(values) {
      const days=[...new Set(values.filter(Boolean))].sort();
      const ranges=[];
      for (const day of days) {
        if (!ranges.length) { ranges.push([day,day]); continue; }
        const d=new Date(`${ranges[ranges.length-1][1]}T12:00:00`);
        d.setDate(d.getDate()+1);
        const next=`${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")}`;
        if (day===next) ranges[ranges.length-1][1]=day; else ranges.push([day,day]);
      }
      return ranges;
    }

    function germanDay(value) {
      const m=String(value||"").match(/^(\d{4})-(\d{2})-(\d{2})$/);
      return m ? `${m[3]}.${m[2]}.${m[1]}` : String(value||"");
    }

    function renderEventEditor(context) {
      currentEditContext = context;
      const event = context.event;
      const child = context.child_event;
      const childEvents = context.child_events || (child ? [child] : []);
      const structural = Boolean(context.structural_editable);
      const archivedChange = Boolean(context.archived_change_request);
      const noEvent = event.event_kind === "no_event";
      eventEditTitle.textContent = `${noEvent ? "Ohne Ereignis bearbeiten" : "Ereignis bearbeiten"} · ${event.name}`;
      eventEditSubtitle.textContent = archivedChange
        ? "Archivierter Bestand: Die App plant die Änderung vollständig, die Kamerabibliothek bleibt read-only."
        : (noEvent
          ? "„Ohne Ereignis“ besteht aus einzelnen Tagen und Zeitsegmenten. Die Dateizugehörigkeit wird ausschließlich daraus berechnet."
          : "Die Dateizugehörigkeit ergibt sich ausschließlich aus Datum und Uhrzeit. Einzelne Familien können nicht manuell herausgenommen werden.");

      const noEventSegments = context.time_segments || [];
      const fixedNoEventMonth = noEventMonthKey(event, noEventSegments);
      const noEventDays = noEventSegments.map(segment => segment.day_key || isoDate(segment.start_datetime)).filter(Boolean).sort();
      const noEventRangeStart = noEventDays.length ? noEventDays[0] : isoDate(event.start_datetime);
      const noEventRangeEnd = noEventDays.length ? noEventDays[noEventDays.length - 1] : isoDate(event.end_datetime);

      const segmentHtml = noEventSegments.map((segment, index) => {
        const day=segment.day_key || isoDate(segment.start_datetime);
        const start=segment.start_time || isoTime(segment.start_datetime,"00:00");
        const end=segment.end_time || isoTime(segment.end_datetime,"23:59");
        return `<details class="no-event-segment card" data-segment-row style="display:block;padding:8px 10px;margin:6px 0">
          <summary style="cursor:pointer;display:flex;align-items:center;gap:6px"><strong>${escapeHtml(day)}</strong> <span class="muted">· ${escapeHtml(start)}–${escapeHtml(end)}</span></summary>
          <div style="display:grid;grid-template-columns:minmax(0,2fr) minmax(0,1fr) minmax(0,1fr) 120px;gap:8px;align-items:end;margin-top:8px;width:100%;box-sizing:border-box">
            ${noEventDayControl(fixedNoEventMonth, day, structural)}
            <label class="edit-field"><span>Von</span><input type="time" data-segment-start value="${escapeHtml(start)}" ${structural ? "" : "disabled"}></label>
            <label class="edit-field"><span>Bis</span><input type="time" data-segment-end value="${escapeHtml(end)}" ${structural ? "" : "disabled"}></label>
            ${structural ? `<button type="button" data-remove-segment="${index}" class="danger-button" style="width:100%;min-width:0;align-self:end;white-space:nowrap">Entfernen</button>` : ""}
          </div>
        </details>`;
      }).join("");

      const normalSegmentHtml = childEvents.map((segment, index) => {
        const start=isoTime(segment.start_datetime,"00:00");
        const end=isoTime(segment.end_datetime,"23:59");
        return `<details class="card" data-child-segment data-child-id="${escapeHtml(segment.id)}" open style="padding:8px 10px;margin:6px 0">
          <summary style="cursor:pointer"><strong>Zeitsegment ${index+1}</strong> <span class="muted">· ${escapeHtml(start)}–${escapeHtml(end)} · ${escapeHtml(segment.name||"")}</span></summary>
          <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:8px;margin-top:8px">
            <label class="edit-field"><span>Bezeichnung</span><input data-child-name value="${escapeHtml(segment.name||"")}" ${structural ? "" : "disabled"}></label>
            <label class="edit-field"><span>Startzeit</span><input data-child-start type="time" value="${escapeHtml(start)}" ${structural ? "" : "disabled"}></label>
            <label class="edit-field"><span>Endzeit</span><input data-child-end type="time" value="${escapeHtml(end)}" ${structural ? "" : "disabled"}></label>
            ${structural ? `<button type="button" data-remove-child-segment class="danger-button">Zeitsegment entfernen</button>` : ""}
          </div>
        </details>`;
      }).join("");

      eventEditBody.innerHTML = `
        ${archivedChange ? `<div class="edit-warning">ARCHIVIERTES Ereignis: Die Kamerabibliothek bleibt strikt read-only. Nach dem Speichern erhältst du einen manuellen Änderungsauftrag mit IST- und SOLL-Zustand.</div><br>` : ""}
        <div class="edit-grid">
          <label class="edit-field full"><span>Ereignisname</span><input id="edit-name" maxlength="160" value="${escapeHtml(event.name)}" ${noEvent ? "disabled" : ""}></label>
          ${noEvent ? `
            <div class="edit-field full">
              <div style="display:flex;justify-content:space-between;align-items:center;gap:10px;margin-bottom:8px">
                <span>Zeitspanne · nur Auswahlhilfe</span>
                ${structural ? `<button id="edit-noevent-range-open" type="button">＋ Zeitspanne ergänzen</button>` : ""}
              </div>
              <div id="edit-noevent-existing-ranges" style="display:grid;gap:6px;margin-bottom:8px"></div>
              <div id="edit-noevent-range-panel" hidden style="padding:10px;border:1px solid var(--border-color, #30363d);border-radius:10px;margin-bottom:10px">
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;align-items:end">
                  <div style="display:grid;grid-template-columns:minmax(118px,.85fr) minmax(86px,.55fr);gap:8px"><label class="edit-field"><span>Monat/Jahr</span><input value="${escapeHtml(fixedNoEventMonth.slice(5,7)+"/"+fixedNoEventMonth.slice(0,4))}" disabled></label><label class="edit-field"><span>Von Tag</span><input id="edit-noevent-range-start-day" type="number" min="1" max="31" value=""></label><input id="edit-noevent-range-start" type="hidden" value=""></div>
                  <div style="display:grid;grid-template-columns:minmax(118px,.85fr) minmax(86px,.55fr);gap:8px"><label class="edit-field"><span>Monat/Jahr</span><input value="${escapeHtml(fixedNoEventMonth.slice(5,7)+"/"+fixedNoEventMonth.slice(0,4))}" disabled></label><label class="edit-field"><span>Bis Tag</span><input id="edit-noevent-range-end-day" type="number" min="1" max="31" value=""></label><input id="edit-noevent-range-end" type="hidden" value=""></div>
                </div>
                ${structural ? `<div style="display:flex;justify-content:flex-end;gap:8px;margin-top:8px"><button id="edit-noevent-range-cancel" type="button">Abbrechen</button><button id="edit-noevent-range-apply" type="button" class="plan-button">Zeitspanne übernehmen</button></div>` : ""}
              </div>
              <span>Tagessegmente</span>
              <div id="no-event-segments">${segmentHtml || `<p class="muted">Noch keine Segmente.</p>`}</div>
              ${structural ? `<button id="add-no-event-segment" type="button">＋ Tagessegment hinzufügen</button>` : ""}
              <p class="muted">Jeder Tag bzw. Teil eines Tages wird separat gespeichert. Zwischenräume gehören ausdrücklich nicht zu „Ohne Ereignis“.</p>
            </div>
            <label class="edit-field"><span>Tagesordner</span><select id="edit-preserve" ${structural ? "" : "disabled"}><option value="0" ${event.preserve_day_folders ? "" : "selected"}>Nicht erhalten</option><option value="1" ${event.preserve_day_folders ? "selected" : ""}>Erhalten</option></select></label>` : `
          <label class="edit-field"><span>Beginn</span><input id="edit-start-date" type="date" value="${escapeHtml(isoDate(event.start_datetime))}" ${structural ? "" : "disabled"}></label>
          <label class="edit-field"><span>Ende</span><input id="edit-end-date" type="date" value="${escapeHtml(isoDate(event.end_datetime))}" ${structural ? "" : "disabled"}></label>
          <label class="edit-field"><span>Tagesordner</span><select id="edit-preserve" ${structural ? "" : "disabled"}><option value="0" ${event.preserve_day_folders ? "" : "selected"}>Nicht erhalten</option><option value="1" ${event.preserve_day_folders ? "selected" : ""}>Erhalten</option></select></label>
          ${childEvents.length ? `<div class="edit-field full"><div style="display:flex;justify-content:space-between;align-items:center;gap:10px"><span>Zeitsegmente / Unterereignisse</span>${structural ? `<button id="add-normal-segment" type="button">＋ Zeitsegment hinzufügen</button>` : ""}</div><div id="normal-event-segments" style="display:grid;gap:6px;margin-top:6px">${normalSegmentHtml}</div><p class="muted">Zeitsegmente können geändert, ergänzt oder vollständig entfernt werden. Die Dateizugehörigkeit wird danach ausschließlich aus Datum und Uhrzeit neu berechnet.</p></div>` : `<label class="edit-field"><span>Unterereignis / Uhrzeit</span><select id="edit-time-enabled" ${structural ? "" : "disabled"}><option value="0" selected>Ganzer Zeitraum</option><option value="1">Ein Zeitbereich</option></select></label><label class="edit-field"><span>Bezeichnung Zeitbereich</span><input id="edit-child-name" value="${escapeHtml(event.name || "")}" disabled></label><label class="edit-field"><span>Startzeit</span><input id="edit-start-time" type="time" value="00:00" disabled></label><label class="edit-field"><span>Endzeit</span><input id="edit-end-time" type="time" value="23:59" disabled></label>${structural ? `<div class="edit-field full"><div style="display:flex;justify-content:space-between;align-items:center;gap:10px"><span>Mehrere Unterereignisse</span><button id="add-normal-segment" type="button">＋ Zeitsegment hinzufügen</button></div><div id="normal-event-segments" style="display:grid;gap:6px;margin-top:6px"></div><p class="muted">Sobald hier Zeitsegmente angelegt sind, bilden sie gemeinsam die neue Ereignisstruktur. Das funktioniert auch bei einem bisher einfachen archivierten Ereignis in einem einzigen Änderungsauftrag.</p></div>` : ""}`}`}
          <label class="edit-field full"><span>Notizen</span><textarea id="edit-notes" maxlength="4000">${escapeHtml(event.notes || "")}</textarea></label>
        </div>
        <div class="edit-actions">
          <button type="button" id="edit-cancel">Abbrechen</button>
          <button type="submit" class="plan-button">Änderungen speichern</button>
        </div>`;

      if (!noEvent) {
        const normalContainer = document.getElementById("normal-event-segments");
        const bindNormalRemove = () => normalContainer?.querySelectorAll("[data-remove-child-segment]").forEach(button => {
          button.onclick = () => button.closest("[data-child-segment]")?.remove();
        });
        bindNormalRemove();
        document.getElementById("add-normal-segment")?.addEventListener("click", () => {
          if (!normalContainer) return;
          const row=document.createElement("details");
          row.className="card"; row.dataset.childSegment="1"; row.open=true;
          row.style.cssText="padding:8px 10px;margin:6px 0";
          row.innerHTML=`<summary style="cursor:pointer"><strong>Neues Zeitsegment</strong></summary><div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:8px;margin-top:8px"><label class="edit-field"><span>Bezeichnung</span><input data-child-name value="${escapeHtml(event.name||"")}"></label><label class="edit-field"><span>Startzeit</span><input data-child-start type="time" value="00:00"></label><label class="edit-field"><span>Endzeit</span><input data-child-end type="time" value="23:59"></label><button type="button" data-remove-child-segment class="danger-button">Zeitsegment entfernen</button></div>`;
          normalContainer.appendChild(row); bindNormalRemove();
        });
        const timeEnabled = document.getElementById("edit-time-enabled");
        const updateTimeFields = () => {
          if (!timeEnabled) return;
          const enabled = structural && timeEnabled.value === "1";
          for (const id of ["edit-child-name","edit-start-time","edit-end-time"]) {
            const field=document.getElementById(id); if (field) field.disabled = !enabled;
          }
        };
        timeEnabled?.addEventListener("change", updateTimeFields);
      } else if (structural) {
        const container = document.getElementById("no-event-segments");
        const renderRangeSummary = () => {
          const host=document.getElementById("edit-noevent-existing-ranges");
          if (!host) return;
          const values=[...container.querySelectorAll("[data-segment-day]")].map(input=>input.value).filter(Boolean);
          const ranges=contiguousDayRangesFromValues(values);
          const monthLabel=fixedNoEventMonth.slice(5,7)+"/"+fixedNoEventMonth.slice(0,4);
          const maxDay=new Date(Number(fixedNoEventMonth.slice(0,4)),Number(fixedNoEventMonth.slice(5,7)),0).getDate();
          host.innerHTML=ranges.length ? ranges.map(([a,b],i)=>{
            const aDay=Number(a.slice(8,10));
            const bDay=Number(b.slice(8,10));
            return `<details class="card" data-existing-range data-range-start="${escapeHtml(a)}" data-range-end="${escapeHtml(b)}" style="padding:7px 9px">
              <summary style="cursor:pointer"><strong>Zeitblock ${i+1}</strong> <span class="muted">· ${escapeHtml(germanDay(a))}${a===b?"":` bis ${escapeHtml(germanDay(b))}`}</span></summary>
              <div style="display:grid;grid-template-columns:minmax(118px,.85fr) minmax(86px,.55fr) minmax(118px,.85fr) minmax(86px,.55fr);gap:8px;align-items:end;margin-top:8px">
                <label class="edit-field"><span>Monat/Jahr</span><input value="${escapeHtml(monthLabel)}" disabled></label>
                <label class="edit-field"><span>Von Tag</span><input data-edit-range-start-day type="number" min="1" max="${maxDay}" value="${aDay}"></label>
                <label class="edit-field"><span>Monat/Jahr</span><input value="${escapeHtml(monthLabel)}" disabled></label>
                <label class="edit-field"><span>Bis Tag</span><input data-edit-range-end-day type="number" min="1" max="${maxDay}" value="${bDay}"></label>
              </div>
              <div style="display:flex;justify-content:flex-end;margin-top:8px"><button type="button" data-apply-existing-range class="plan-button">Zeitblock übernehmen</button></div>
            </details>`;
          }).join("") : '<span class="muted">Noch keine Zeitblöcke.</span>';
          host.querySelectorAll("[data-apply-existing-range]").forEach(button=>{
            button.onclick=()=>{
              const box=button.closest("[data-existing-range]");
              const oldStart=box?.dataset.rangeStart||"";
              const oldEnd=box?.dataset.rangeEnd||"";
              const from=Number(box?.querySelector("[data-edit-range-start-day]")?.value||0);
              const to=Number(box?.querySelector("[data-edit-range-end-day]")?.value||0);
              if (!from || !to || from>to) return;
              const newStart=`${fixedNoEventMonth}-${String(Math.min(maxDay,Math.max(1,from))).padStart(2,"0")}`;
              const newEnd=`${fixedNoEventMonth}-${String(Math.min(maxDay,Math.max(1,to))).padStart(2,"0")}`;
              [...container.querySelectorAll("[data-segment-row]")].forEach(row=>{
                const day=row.querySelector("[data-segment-day]")?.value||"";
                if (day>=oldStart && day<=oldEnd && (day<newStart || day>newEnd)) row.remove();
              });
              const existing=new Set([...container.querySelectorAll("[data-segment-day]")].map(input=>input.value));
              let d=new Date(`${newStart}T12:00:00`), last=new Date(`${newEnd}T12:00:00`);
              while (d<=last) {
                const day=`${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")}`;
                if (!existing.has(day)) {
                  const row=document.createElement("details");
                  row.className="no-event-segment card"; row.dataset.segmentRow="1"; row.open=false; row.style.cssText="display:block;padding:8px 10px;margin:6px 0";
                  row.innerHTML=`<summary style="cursor:pointer;display:flex;align-items:center;gap:6px"><strong>${day}</strong> <span class="muted">· 00:00–23:59</span></summary><div style="display:grid;grid-template-columns:minmax(0,2fr) minmax(0,1fr) minmax(0,1fr) 120px;gap:8px;align-items:end;margin-top:8px;width:100%;box-sizing:border-box">${noEventDayControl(fixedNoEventMonth, day, true)}<label class="edit-field"><span>Von</span><input type="time" data-segment-start value="00:00"></label><label class="edit-field"><span>Bis</span><input type="time" data-segment-end value="23:59"></label><button type="button" data-remove-segment class="danger-button" style="width:100%;min-width:0;align-self:end;white-space:nowrap">Entfernen</button></div>`;
                  container.appendChild(row); existing.add(day);
                }
                d.setDate(d.getDate()+1);
              }
              bindRemove();
              bindLockedMonthDays();
              renderRangeSummary();
            };
          });
        };
        const bindRemove = () => {
          container.querySelectorAll("[data-remove-segment]").forEach(button => {
            button.onclick = () => { button.closest("[data-segment-row]").remove(); renderRangeSummary(); };
          });
        };
        bindRemove();
        renderRangeSummary();
        const bindLockedMonthDays = () => {
          container.querySelectorAll("[data-segment-day-number]").forEach(input=>{
            input.oninput=()=>{
              const hidden=input.closest("[data-segment-row]")?.querySelector("[data-segment-day]");
              const maxDay=new Date(Number(fixedNoEventMonth.slice(0,4)),Number(fixedNoEventMonth.slice(5,7)),0).getDate();
              const n=Math.max(1,Math.min(maxDay,Number(input.value||0)));
              if (hidden && Number(input.value||0)>0) hidden.value=`${fixedNoEventMonth}-${String(n).padStart(2,"0")}`;
              renderRangeSummary();
            };
          });
        };
        bindLockedMonthDays();
        const syncRangeDay=(id,hiddenId)=>{ const input=document.getElementById(id); const hidden=document.getElementById(hiddenId); if(!input||!hidden)return; input.oninput=()=>{ const maxDay=new Date(Number(fixedNoEventMonth.slice(0,4)),Number(fixedNoEventMonth.slice(5,7)),0).getDate(); const n=Math.max(1,Math.min(maxDay,Number(input.value||0))); if(Number(input.value||0)>0) hidden.value=`${fixedNoEventMonth}-${String(n).padStart(2,"0")}`; }; };
        syncRangeDay("edit-noevent-range-start-day","edit-noevent-range-start");
        syncRangeDay("edit-noevent-range-end-day","edit-noevent-range-end");
        const rangePanel=document.getElementById("edit-noevent-range-panel");
        document.getElementById("edit-noevent-range-open")?.addEventListener("click", () => {
          if (rangePanel) rangePanel.hidden=false;
          for (const id of ["edit-noevent-range-start-day","edit-noevent-range-end-day","edit-noevent-range-start","edit-noevent-range-end"]) { const el=document.getElementById(id); if (el) el.value=""; }
          document.getElementById("edit-noevent-range-start-day")?.focus();
        });
        document.getElementById("edit-noevent-range-cancel")?.addEventListener("click", () => {
          if (rangePanel) rangePanel.hidden=true;
        });
        document.getElementById("edit-noevent-range-apply")?.addEventListener("click", () => {
          const start=document.getElementById("edit-noevent-range-start")?.value || "";
          const end=document.getElementById("edit-noevent-range-end")?.value || "";
          if (!/^\d{4}-\d{2}-\d{2}$/.test(start) || !/^\d{4}-\d{2}-\d{2}$/.test(end) || end < start) return;
          const existing=new Set([...container.querySelectorAll("[data-segment-day]")].map(input=>input.value));
          let d=new Date(`${start}T12:00:00`), last=new Date(`${end}T12:00:00`);
          while (d<=last) {
            const day=`${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")}`;
            if (!existing.has(day)) {
              const row=document.createElement("details"); row.className="no-event-segment card"; row.dataset.segmentRow="1"; row.open=false; row.style.cssText="display:block;padding:8px 10px;margin:6px 0";
              row.innerHTML=`<summary style="cursor:pointer;display:flex;align-items:center;gap:6px"><strong>${day}</strong> <span class="muted">· 00:00–23:59</span></summary><div style="display:grid;grid-template-columns:minmax(0,2fr) minmax(0,1fr) minmax(0,1fr) 120px;gap:8px;align-items:end;margin-top:8px;width:100%;box-sizing:border-box">${noEventDayControl(fixedNoEventMonth, day, true)}<label class="edit-field"><span>Von</span><input type="time" data-segment-start value="00:00"></label><label class="edit-field"><span>Bis</span><input type="time" data-segment-end value="23:59"></label><button type="button" data-remove-segment class="danger-button" style="width:100%;min-width:0;align-self:end;white-space:nowrap">Entfernen</button></div>`;
              container.appendChild(row); existing.add(day);
            }
            d.setDate(d.getDate()+1);
          }
          bindRemove();
          bindLockedMonthDays();
          renderRangeSummary();
          if (rangePanel) rangePanel.hidden=true;
        });
        document.getElementById("add-no-event-segment")?.addEventListener("click", () => {
          const row = document.createElement("details");
          row.className = "no-event-segment card";
          row.dataset.segmentRow = "1";
          row.open = true;
          row.style.cssText = "display:block;padding:8px 10px;margin:6px 0";
          row.innerHTML = `<summary style="cursor:pointer;display:flex;align-items:center;gap:6px"><strong>Neues Tagessegment</strong> <span class="muted">· 00:00–23:59</span></summary><div style="display:grid;grid-template-columns:minmax(0,2fr) minmax(0,1fr) minmax(0,1fr) 120px;gap:8px;align-items:end;margin-top:8px;width:100%;box-sizing:border-box">${noEventDayControl(fixedNoEventMonth, "", true)}<label class="edit-field"><span>Von</span><input type="time" data-segment-start value="00:00"></label><label class="edit-field"><span>Bis</span><input type="time" data-segment-end value="23:59"></label><button type="button" data-remove-segment class="danger-button" style="width:100%;min-width:0;align-self:end;white-space:nowrap">Entfernen</button></div>`;
          container.appendChild(row);
          bindRemove();
          bindLockedMonthDays();
          renderRangeSummary();
          row.querySelector("[data-segment-day-number]")?.focus();
        });
      }
      document.getElementById("edit-cancel").addEventListener("click", () => eventEditDialog.close());
    }

    async function openEventEditor(eventId, jobId) {
      eventEditBody.textContent = "Bearbeitungsdaten werden geladen …";
      if (!eventEditDialog.open) eventEditDialog.showModal();
      const context = await requestJson(`/api/jobs/${encodeURIComponent(jobId)}/events/${encodeURIComponent(eventId)}/edit`);
      context._job_id = jobId;
      renderEventEditor(context);
    }

    async function saveEventEditor() {
      const context = currentEditContext;
      if (!context) return;
      const structural = Boolean(context.structural_editable);
      const noEvent = context.event.event_kind === "no_event";
      const payload = {
        revision: Number(context.event.revision || 1),
        event_name: noEvent ? "Ohne Ereignis" : document.getElementById("edit-name").value,
        notes: document.getElementById("edit-notes").value,
      };
      if (structural) {
        if (noEvent) {
          payload.event_kind = "no_event";
          payload.preserve_day_folders = document.getElementById("edit-preserve").value === "1";
          payload.uses_time_range = false;
          payload.no_event_segments = [...eventEditBody.querySelectorAll("[data-segment-row]")].map(row => ({
            day_key: row.querySelector("[data-segment-day]").value,
            start_time: row.querySelector("[data-segment-start]").value,
            end_time: row.querySelector("[data-segment-end]").value,
          }));
          if (!payload.no_event_segments.length) throw new Error("Mindestens ein „Ohne Ereignis“-Zeitsegment muss erhalten bleiben.");
          payload.start_date = payload.no_event_segments[0].day_key;
          payload.end_date = payload.no_event_segments[payload.no_event_segments.length - 1].day_key;
        } else {
          const segmentRows=[...eventEditBody.querySelectorAll("[data-child-segment]")];
          if (segmentRows.length) {
            Object.assign(payload, {
              event_kind: "event",
              start_date: document.getElementById("edit-start-date").value,
              end_date: document.getElementById("edit-end-date").value,
              preserve_day_folders: document.getElementById("edit-preserve").value === "1",
              uses_time_range: true,
              child_segments: segmentRows.map(row=>({
                id: row.dataset.childId || null,
                name: row.querySelector("[data-child-name]").value,
                start_time: row.querySelector("[data-child-start]").value,
                end_time: row.querySelector("[data-child-end]").value,
              })),
            });
          } else {
            const timeEnabled=document.getElementById("edit-time-enabled");
            const usesTime = timeEnabled ? timeEnabled.value === "1" : false;
            Object.assign(payload, {
              event_kind: "event",
              start_date: document.getElementById("edit-start-date").value,
              end_date: document.getElementById("edit-end-date").value,
              preserve_day_folders: document.getElementById("edit-preserve").value === "1",
              uses_time_range: usesTime,
              child_event_name: document.getElementById("edit-child-name")?.value || document.getElementById("edit-name").value,
              start_time: document.getElementById("edit-start-time")?.value || "00:00",
              end_time: document.getElementById("edit-end-time")?.value || "23:59",
            });
          }
        }
      }
      if (context.archived_change_request) {
        setStatus("Manueller Änderungsauftrag wird berechnet …");
        const result = await requestJson(`/api/change-requests/${encodeURIComponent(context.event.id)}/propose?job_id=${encodeURIComponent(context._job_id)}`, {
          method: "POST", headers: {"Content-Type":"application/json"}, body: JSON.stringify(payload),
        });
        eventEditDialog.close();
        if (!changeRequestDialog.open) changeRequestDialog.showModal();
        await showChangeRequestDetail(result.change_request_id);
        setStatus("Änderungsauftrag erstellt. Die Kamerabibliothek wurde nicht verändert.", false, true);
        refreshGlobalTasks();
        return;
      }
      setStatus("Ereignisänderungen werden gespeichert …");
      let result;
      try {
        result = await requestJson(`/api/jobs/${encodeURIComponent(context._job_id)}/events/${encodeURIComponent(context.event.id)}`, {
          method:"PUT", headers:{"Content-Type":"application/json"}, body:JSON.stringify(payload),
        });
      } catch (error) {
        const cascade = error.data?.cascade_preview;
        if (!cascade?.has_conflicts) throw error;
        const lines = (cascade.items || []).map(item => {
          const action = item.action === "trim_start" ? "Beginn verschieben"
            : item.action === "trim_end" ? "Ende verkürzen"
            : item.action === "trim_or_split_segment" ? "„Ohne Ereignis“-Segment anpassen"
            : "manuelle Klärung nötig";
          return `• ${item.name} (${item.status}): ${action}`;
        });
        const hardNonArchive = (cascade.items || []).some(item => String(item.status || "") !== "archived" && !item.automatic);
        if (hardNonArchive) {
          throw new Error(error.message + "\n\n" + lines.join("\n"));
        }
        const hasArchived = (cascade.items || []).some(item => String(item.status || "") === "archived");
        const accepted = window.confirm(
          (hasArchived
            ? "ACHTUNG: Diese Änderung betrifft mindestens ein ARCHIVIERTES Ereignis. Die Kamerabibliothek bleibt read-only; für den Archivanteil wird ein manueller IST→SOLL-Auftrag erzeugt.\n\n"
            : "Die Änderung betrifft weitere Zeitbereiche. Die App schlägt folgende gemeinsame Anpassung vor:\n\n")
          + lines.join("\n")
          + "\n\nDiese gemeinsame Änderung wirklich vorbereiten?"
        );
        if (!accepted) throw new Error("Änderung wurde nicht ausgeführt.");
        payload.cascade_confirmed = true;
        result = await requestJson(`/api/jobs/${encodeURIComponent(context._job_id)}/events/${encodeURIComponent(context.event.id)}`, {
          method:"PUT", headers:{"Content-Type":"application/json"}, body:JSON.stringify(payload),
        });
      }
      eventEditDialog.close();
      await loadEvents();
      if (result.archive_manual?.change_request_ids?.length) {
        const crId = result.archive_manual.change_request_ids[0];
        if (!changeRequestDialog.open) changeRequestDialog.showModal();
        await showChangeRequestDetail(crId);
        setStatus("Archivberührung erkannt: manueller IST→SOLL-Auftrag vorbereitet. Die Kamerabibliothek wurde nicht verändert.", false, true);
        refreshGlobalTasks();
        return;
      }
      if (result.reassignment_required && (result.removed_family_ids || []).length) {
        await openReassignmentWorkflow(context.event.id, context._job_id, Boolean(result.resort_required));
      } else {
        // 0.16.8: Eine bestaetigte Kaskade ist eine gemeinsame Operation.
        // Alle betroffenen applied-Ereignisse werden automatisch nachsortiert;
        // der Nutzer bekommt nur dann eine Aufgabe, wenn ein Lauf fehlschlaegt.
        const cascadeNeedsReconcile = (result.cascade?.preview?.items || []).some(
          item => String(item.status || "") === "applied"
        );
        const needsReconcile = Boolean(result.resort_required || cascadeNeedsReconcile);
        if (needsReconcile) {
          // 0.16.10: genau EIN Lauf für die gesamte verbundene Änderungsgruppe.
          // Der Abgleich ermittelt selbst alle betroffenen applied-Ereignisse.
          await runAutomaticReapply(context.event.id, context._job_id);
        } else {
          const plannedCascade = String(result.mutation_id || "") && !Boolean(result.resort_required);
          setStatus(
            plannedCascade
              ? "Gemeinsame Planänderung gespeichert. Es wurden keine Dateien verschoben; die beteiligten Ereignisse bleiben bis zur Anwendung gesperrt oder können gemeinsam verworfen werden."
              : "Ereignis wurde gespeichert.",
            false, true
          );
        }
        await loadEvents({reset:true});
        refreshGlobalTasks();
      }
    }

    async function openReassignmentWorkflow(eventId, jobId, resortRequired) {
      reassignmentContext = {eventId, jobId, resortRequired, autoTargetIds:[]};
      if (!reassignmentDialog.open) reassignmentDialog.showModal();
      await renderReassignmentWorkflow();
    }

    async function renderReassignmentWorkflow() {
      const ctx = reassignmentContext;
      if (!ctx) return;
      reassignmentBody.textContent = "Offene Familien und Ziele werden geladen …";
      const data = await requestJson(`/api/jobs/${encodeURIComponent(ctx.jobId)}/events/${encodeURIComponent(ctx.eventId)}/reassignments`);
      const families = data.families || [];
      if (!families.length) {
        reassignmentDialog.close();
        if (ctx.resortRequired) {
          // Ein gemeinsamer 0.16.10-Abgleich umfasst Quellereignis und alle
          // verbundenen applied-Ziele (auch „Ohne Ereignis“).
          await runAutomaticReapply(ctx.eventId, ctx.jobId);
        } else {
          setStatus("Ereignis gespeichert und alle herausfallenden Familien neu zugeordnet.", false, true);
        }
        await loadEvents({reset:true});
        refreshGlobalTasks();
        return;
      }
      reassignmentSubtitle.textContent = `${families.length} ${families.length === 1 ? "Dateifamilie liegt" : "Dateifamilien liegen"} in noch neu zuzuordnenden Tages-/Zeitsegmenten.`;
      const targets = data.targets || [];
      const options = targets.map(t => {
        const kind = t.event_kind === "no_event" ? "Ohne Ereignis" : "Ereignis";
        const existing=`<option value="${escapeHtml(t.event_id)}" data-kind="${escapeHtml(t.event_kind)}">${escapeHtml(kind)} · ${escapeHtml(t.name)} · ${escapeHtml(t.status)}</option>`;
        const child=t.event_kind === "event" && t.status !== "archived" ? `<option value="__child__:${escapeHtml(t.event_id)}" data-kind="new_child" data-parent-id="${escapeHtml(t.event_id)}">Neues Unterereignis in · ${escapeHtml(t.name)}</option>` : "";
        return existing+child;
      }).join("");
      const exactSegments=data.reassignment_segments || [];
      const dayGroups=exactSegments.map(segment=>{
        const ids=(segment.family_ids||[]).map(Number).join(",");
        const day=segment.day_key || String(segment.start_datetime||"").slice(0,10);
        const fallback=segment.fallback ? " · Legacy-Zeitraum aus Aufnahmen" : "";
        return `<label class="card" style="display:flex;align-items:center;gap:10px;padding:10px 12px"><input type="checkbox" data-reassign-day data-family-ids="${escapeHtml(ids)}" data-day="${escapeHtml(day)}" data-start="${escapeHtml(segment.start_datetime||"")}" data-end="${escapeHtml(segment.end_datetime||"")}" checked style="width:18px;height:18px;flex:0 0 auto"><span style="min-width:0"><strong>${escapeHtml(germanDay(day))} · ${escapeHtml(segment.start_time||"")}–${escapeHtml(segment.end_time||"")}</strong><br><span class="muted">${Number(segment.family_count||0)} Familien · ${Number(segment.file_count||0)} Dateien · nur gemeinsam zuordenbar${escapeHtml(fallback)}</span></span></label>`;
      }).join("");
      const newNoEventOption = data.new_no_event_supported ? '<option value="__new_no_event__">Neues „Ohne Ereignis“ erstellen</option>' : '';
      reassignmentBody.innerHTML = `
        <div class="edit-warning">Wähle ganze Tages-/Zeitsegmente, die gemeinsam dasselbe Ziel bekommen. Einzelne Familien oder Dateien können hier bewusst nicht herausgepickt werden.</div>
        <div class="reassignment-list">${dayGroups}</div>
        <div class="reassignment-controls">
          <label class="edit-field"><span>Ziel</span><select id="reassignment-target"><option value="__new__">Neues Ereignis erstellen</option>${newNoEventOption}${options}</select></label>
          <button id="reassignment-apply" type="button" class="plan-button">Auswahl zuordnen</button>
        </div>
        <label id="reassignment-new-wrap" class="edit-field reassignment-new-name"><span>Name des neuen Ereignisses</span><input id="reassignment-new-name" type="text" placeholder="Ereignisname"></label>
        <p id="reassignment-message" class="muted"></p>`;
      // 0.21.2: day/time rows are atomic. No family-level controls exist.
      const target = document.getElementById("reassignment-target");
      const newWrap = document.getElementById("reassignment-new-wrap");
      const updateNew = () => { newWrap.hidden = !(target.value === "__new__" || target.selectedOptions[0]?.dataset.kind === "new_child"); };
      target.addEventListener("change", updateNew); updateNew();
      document.getElementById("reassignment-apply").addEventListener("click", async () => {
        const selectedDays=[...reassignmentBody.querySelectorAll('[data-reassign-day]:checked')];
        const selectedIds=[...new Set(selectedDays.flatMap(i=>String(i.dataset.familyIds||"").split(",").filter(Boolean).map(Number)))];
        const selectedSegments=selectedDays.map(i=>({start_datetime:i.dataset.start,end_datetime:i.dataset.end,day_key:i.dataset.day}));
        if (!selectedIds.length) { document.getElementById("reassignment-message").textContent = "Bitte mindestens ein Tages-/Zeitsegment auswählen."; return; }
        const opt = target.selectedOptions[0];
        const isNew = target.value === "__new__";
        const isNewNoEvent = target.value === "__new_no_event__";
        const isNewChild = opt.dataset.kind === "new_child";
        const targetMode = isNew ? "new_event" : (isNewNoEvent ? "new_no_event" : (isNewChild ? "new_child" : (opt.dataset.kind === "no_event" ? "existing_no_event" : "existing_event")));
        document.getElementById("reassignment-apply").disabled = true;
        try {
          const assigned = await requestJson(`/api/jobs/${encodeURIComponent(ctx.jobId)}/events/${encodeURIComponent(ctx.eventId)}/reassignments`, {
            method:"POST", headers:{"Content-Type":"application/json"},
            body:JSON.stringify({family_ids:selectedIds, segments:selectedSegments, target_mode:targetMode, target_event_id:(isNew||isNewNoEvent) ? null : (isNewChild ? opt.dataset.parentId : target.value), new_event_name:(isNew||isNewChild) ? document.getElementById("reassignment-new-name").value : null})
          });
          if (assigned?.target?.status === "applied" && assigned?.target?.event_id) {
            if (!ctx.autoTargetIds.includes(assigned.target.event_id)) ctx.autoTargetIds.push(assigned.target.event_id);
          }
          await renderReassignmentWorkflow();
        } catch (error) {
          document.getElementById("reassignment-message").textContent = error.message;
          document.getElementById("reassignment-apply").disabled = false;
        }
      });
    }

    reassignmentClose.addEventListener("click", () => reassignmentDialog.close());

    async function runAutomaticReapply(eventId, jobId) {
      sortPlanTitle.textContent = "Nachsortierung wird automatisch ausgeführt";
      sortPlanSubtitle.textContent = "Die neue Struktur wird geprüft und anschließend direkt auf der SSD umgesetzt.";
      sortPlanBody.textContent = "Dateien, Ziele und Konflikte werden geprüft …";
      if (!sortPlanDialog.open) sortPlanDialog.showModal();

      const plan = await requestJson(`/api/jobs/${encodeURIComponent(jobId)}/events/${encodeURIComponent(eventId)}/reconcile-plan?verify_sha256=true`);
      if (!plan.summary?.ready) {
        plan._job_id = jobId;
        plan._reapply = true;
        plan._reconcile = true;
      plan._reconcile = true;
        renderSortPlan(plan);
        throw new Error(`${plan.summary?.blocker_count || 1} Blocker verhindern die automatische Nachsortierung.`);
      }

      const response = await requestJson(`/api/jobs/${encodeURIComponent(jobId)}/events/${encodeURIComponent(eventId)}/reconcile-sort`, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
          plan_token: plan.plan_token,
          confirmation_phrase: plan.apply_confirmation_phrase,
        }),
      });
      renderSortRunProgress(response.run);
      const run = await pollSortRun(jobId, response.run.id);
      if (run.status !== "applied") {
        throw new Error(run.error_message || "Die automatische Nachsortierung wurde nicht abgeschlossen.");
      }
      setStatus("Änderung gespeichert, SSD automatisch nachsortiert und geprüft.", false, true);
      return run;
    }

    async function loadReapplyPlan(eventId, jobId) {
      const event = currentEvents.find(item => item.id === eventId && (!jobId || item._job_id === jobId));
      if (!jobId || !event) throw new Error("Ereignis wurde nicht gefunden.");
      sortPlanTitle.textContent = `Nachsortierung · ${event.name}`;
      sortPlanSubtitle.textContent = "Alte und neue Pfade werden rein lesend geprüft …";
      sortPlanBody.textContent = "Dateien, Ziele und Konflikte werden geprüft …";
      if (!sortPlanDialog.open) sortPlanDialog.showModal();
      const plan = await requestJson(`/api/jobs/${encodeURIComponent(jobId)}/events/${encodeURIComponent(eventId)}/reconcile-plan`);
      plan._job_id = jobId;
      plan._reapply = true;
      plan._reconcile = true;
      renderSortPlan(plan);
    }

    async function loadSortPlan(eventId, jobId) {
      const event = currentEvents.find(
        item => item.id === eventId && (!jobId || item._job_id === jobId)
      );

      if (!jobId || !event) {
        setStatus(
          "Ereignis wurde nicht gefunden.",
          true
        );
        return;
      }

      sortPlanTitle.textContent =
        `Sortierplan · ${event.name}`;
      sortPlanSubtitle.textContent =
        "Rein lesende Prüfung wird berechnet …";
      sortPlanBody.textContent =
        "Quellen, Ziele und Konflikte werden geprüft …";

      if (!sortPlanDialog.open) {
        sortPlanDialog.showModal();
      }

      const plan = await requestJson(
        `/api/jobs/${
          encodeURIComponent(jobId)
        }/events/${
          encodeURIComponent(eventId)
        }/sort-plan`
      );

      plan._job_id = jobId;
      renderSortPlan(plan);

      setStatus(
        plan.summary.ready
          ? "Sortierplan ist ohne Blocker bereit."
          : `${plan.summary.blocker_count} Blocker im Sortierplan erkannt.`,
        !plan.summary.ready,
        plan.summary.ready
      );
    }


    async function deleteEvent(eventId, jobId) {
      const event = currentEvents.find(
        item => item.id === eventId && (!jobId || item._job_id === jobId)
      );

      if (!jobId || !event) {
        setStatus(
          "Ereignis wurde nicht gefunden.",
          true
        );
        return;
      }

      const statusText = event.status === "planned" || event.status === "draft"
        ? "Die Planung wird sofort entfernt; Dateien und Ordner bleiben unverändert."
        : event.status === "applied"
          ? "Die Familien müssen anschließend neu zugeordnet werden. Danach sortiert die App die SSD automatisch und löscht das leere Ereignis."
          : "Für den archivierten Bestand wird ein manueller IST→SOLL-Löschauftrag erstellt. Die Kamerabibliothek bleibt read-only.";
      const confirmed = window.confirm(`Ereignis „${event.name}“ löschen?\n\n${statusText}`);

      if (!confirmed) {
        return;
      }

      setStatus("Planung wird gelöscht …");

      const result = await requestJson(
        `/api/jobs/${
          encodeURIComponent(jobId)
        }/events/${
          encodeURIComponent(eventId)
        }`,
        {
          method: "DELETE"
        }
      );

      await loadEvents({reset:true});
      refreshGlobalTasks();
      if (result.change_request_id) {
        if (!changeRequestDialog.open) changeRequestDialog.showModal();
        await showChangeRequestDetail(result.change_request_id);
        setStatus("Manueller Löschauftrag erstellt. Die Kamerabibliothek wurde nicht verändert.", false, true);
        return;
      }
      if (result.pending_delete && result.reassignment_required) {
        setStatus(result.message || "Löschung vorbereitet; Familien neu zuordnen.", false, true);
        await openReassignmentWorkflow(eventId, jobId, true);
        return;
      }
      setStatus(`Ereignis gelöscht: ${result.event_name} · ${Number(result.released_family_count||0)} Familien wieder frei.`, false, true);
    }




    eventEditClose.addEventListener("click", () => eventEditDialog.close());
    changeRequestClose.addEventListener("click", () => changeRequestDialog.close());
    eventEditForm.addEventListener("submit", event => {
      event.preventDefault();
      saveEventEditor().catch(error => setStatus(error.message, true));
    });

    sortPlanCloseButton.addEventListener(
      "click",
      () => sortPlanDialog.close()
    );


    eventList.addEventListener(
      "click",
      event => {
        const planButton = event.target.closest(
          "[data-sort-plan-event]"
        );

        if (
          planButton
          && !planButton.disabled
        ) {
          const loader = planButton.dataset.eventStatus === "applied" ? loadReapplyPlan : loadSortPlan;
          loader(
            planButton.dataset.sortPlanEvent,
            planButton.dataset.jobId
          ).catch(
            error => {
              sortPlanBody.textContent =
                error.message;
              setStatus(
                error.message,
                true
              );
            }
          );
          return;
        }

        const workspaceReassignButton = event.target.closest("[data-reassign-workspace]");
        if (workspaceReassignButton) {
          location.href = `/workspace?job=${encodeURIComponent(workspaceReassignButton.dataset.jobId||"")}&task=reassign:${encodeURIComponent(workspaceReassignButton.dataset.reassignWorkspace)}`;
          return;
        }

        const reassignButton = event.target.closest("[data-reassign-event]");
        if (reassignButton && !reassignButton.disabled) {
          openReassignmentWorkflow(
            reassignButton.dataset.reassignEvent,
            reassignButton.dataset.jobId,
            reassignButton.dataset.resortRequired === "1"
          ).catch(error => setStatus(error.message, true));
          return;
        }

        const cancelMutationButton = event.target.closest("[data-cancel-mutation]");
        if (cancelMutationButton && !cancelMutationButton.disabled) {
          if (!window.confirm("Diese noch nicht abgeschlossene Änderung vollständig verwerfen und den gespeicherten Ursprungszustand wiederherstellen?")) return;
          requestJson(`/api/jobs/${encodeURIComponent(cancelMutationButton.dataset.jobId||"")}/event-mutations/${encodeURIComponent(cancelMutationButton.dataset.cancelMutation)}/cancel`, {method:"POST"})
            .then(async () => {
              setStatus("Änderung verworfen. Der gespeicherte Ursprungszustand wurde wiederhergestellt.", false, true);
              await loadEvents({reset:true});
              refreshGlobalTasks();
            })
            .catch(error => setStatus(error.message, true));
          return;
        }

        const editButton = event.target.closest("[data-edit-event]");
        if (editButton && !editButton.disabled) {
          // Auch archivierte Ereignisse öffnen denselben vollständigen Editor.
          // Beim Speichern wird dort ausschließlich ein manueller Change Request
          // erzeugt; die Kamerabibliothek bleibt read-only.
          openEventEditor(editButton.dataset.editEvent, editButton.dataset.jobId).catch(error => {
            eventEditBody.textContent = error.message;
            setStatus(error.message, true);
          });
          return;
        }

        const deleteButton = event.target.closest(
          "[data-delete-event]"
        );

        if (
          !deleteButton
          || deleteButton.disabled
        ) {
          return;
        }

        deleteEvent(
          deleteButton.dataset.deleteEvent,
          deleteButton.dataset.jobId
        ).catch(
          error => setStatus(
            error.message,
            true
          )
        );
      }
    );




    async function loadChangeRequests() {
      try {
        // job_id ist optional; der Default-Status ist leer, die Liste
        // laedt alle ChangeRequests.
        const res = await fetch(`/api/change-requests?job_id=&status=`);
        if (!res.ok) {
          throw new Error(
            `HTTP ${res.status}: ${res.statusText}`
          );
        }

        const data = await res.json();
        renderChangeRequestList(data.requests || []);
      } catch (error) {
        setStatus(error.message, true);
      }
    }

    function renderChangeRequestList(requests) {
      if (requests.length === 0) {
        changeRequestBody.textContent =
          "Keine Änderungsaufträge vorhanden.";
        return;
      }

      let html = "<h3>Änderungsaufträge</h3>";
      html += "<ul class=\"change-request-list\">";

      for (const cr of requests) {
        html += `<li>`;
        html += `<strong>Ereignis:</strong> ${escapeHtml(cr.event_name || cr.event_id)}<br>`;
        html += `<strong>Status:</strong> ${escapeHtml(cr.status)}<br>`;
        if (cr.modified_at) {
          html += `<strong>Geändert:</strong> ${escapeHtml(cr.modified_at)}<br>`;
        }
        html += `<button class="plan-button" type="button" data-cr-id="${escapeHtml(cr.id)}">Details</button>`;
        html += `</li>`;
      }

      html += "</ul>";
      changeRequestBody.innerHTML = html;

      // Click-Handler für Details
      for (const btn of changeRequestBody.querySelectorAll("[data-cr-id]")) {
        btn.addEventListener("click", () => {
          showChangeRequestDetail(btn.dataset.crId);
        });
      }
    }

    async function showChangeRequestDetail(crId) {
      try {
        changeRequestBody.textContent = "Lade Details …";
        changeRequestTitle.textContent = "Änderungsauftrag";
        changeRequestSubtitle.textContent = "";

        const res = await fetch(`/api/change-requests/${crId}`);

        if (!res.ok) {
          throw new Error(`HTTP ${res.status}: ${res.statusText}`);
        }

        const cr = await res.json();
        changeRequestSubtitle.textContent = `ID: ${cr.id}`;

        let html = "<h4>Änderungsdetails</h4>";
        html += `<p><strong>Status:</strong> ${escapeHtml(cr.status)}</p>`;
        html += `<p><strong>Beschreibung:</strong> ${escapeHtml(cr.description || "—")}</p>`;

        // Dateigenaue Arbeitsanweisung: IST -> SOLL.
        let reviewRows = [];
        const filesRes = await fetch(`/api/change-requests/${crId}/files`);
        if (filesRes.ok) {
          const files = await filesRes.json();
          const rows = Array.isArray(files) ? files : (files.files || []);
          reviewRows = rows;
          if (rows.length > 0) {
            const fileName = path => String(path || "").split("/").filter(Boolean).pop() || "Datei";
            const familyStem = row => fileName(row.old_path || row.new_path).replace(/\.[^.]+$/, "");
            // 0.20.0: Arbeitsgruppen werden nach dem tatsächlichen QUELL-Ereignis
            // gebildet. Der Nutzer arbeitet im Finder von einem realen Ausgangsordner
            // aus; das Ziel kann innerhalb desselben Ereignisses oder in einem anderen
            // Ereignis liegen. Dadurch entstehen keine irreführenden Zielgruppen mehr.
            const eventGroup = row => {
              const path = String(row.old_path || row.new_path || "");
              const parts = path.split("/").filter(Boolean);
              return parts.length > 1 && /^\d{4}$/.test(parts[0]) ? parts[1] : (parts[0] || cr.event_name || "Ereignis");
            };
            const groups = new Map();
            for (const row of rows) {
              const eventKey = eventGroup(row);
              if (!groups.has(eventKey)) groups.set(eventKey, new Map());
              const familyKey = String(row.family_id ?? familyStem(row));
              if (!groups.get(eventKey).has(familyKey)) groups.get(eventKey).set(familyKey, []);
              groups.get(eventKey).get(familyKey).push(row);
            }
            html += `<h4>Manuelle Änderungen · ${groups.size} Ereignis${groups.size===1?"":"se"}</h4>`;
            html += `<p class="muted">Kompakt nach Ereignis und Dateifamilie gruppiert. Für die Arbeit im Finder reicht meist der Von–Bis-Hinweis; Einzeldateien und exakte IST→SOLL-Pfade sind ausklappbar.</p>`;
            html += `<div class="change-file-instructions">`;
            for (const [eventKey, families] of groups) {
              const familyEntries=[...families.values()];
              const firstStem=familyStem(familyEntries[0][0]);
              const lastStem=familyStem(familyEntries[familyEntries.length-1][0]);
              const groupRows=rows.filter(r=>eventGroup(r)===eventKey);
              const sourceKeys=new Set(groupRows.map(r=>{
                const parts=String(r.old_path||"").split("/").filter(Boolean);
                return parts.length>1 && /^\d{4}$/.test(parts[0]) ? parts[1] : (parts[0]||"");
              }).filter(Boolean));
              const targetKeys=new Set(groupRows.map(r=>{
                const parts=String(r.new_path||"").split("/").filter(Boolean);
                return parts.length>1 && /^\d{4}$/.test(parts[0]) ? parts[1] : (parts[0]||"");
              }).filter(Boolean));
              const purpose=(targetKeys.size===1 && targetKeys.has(eventKey))
                ? "Innerhalb dieses Ereignisses verschieben"
                : (targetKeys.size===1 ? `Aus diesem Ereignis nach ${[...targetKeys][0]} verschieben` : "Aus diesem Ereignis in mehrere Ziele verschieben");
              html += `<section class="card" style="margin:10px 0;padding:12px"><h4 style="margin:0 0 4px">${escapeHtml(eventKey)}</h4>`;
              html += `<div style="font-weight:600;margin-bottom:3px">${escapeHtml(purpose)}</div>`;
              html += `<div class="muted">${families.size} Familien · ${groupRows.length} Dateien · ${escapeHtml(firstStem)}${firstStem===lastStem?"":` bis ${escapeHtml(lastStem)}`}</div>`;
              for (const filesOfFamily of familyEntries) {
                const stem=familyStem(filesOfFamily[0]);
                const targetDir=String(filesOfFamily[0].new_path||"").split("/").slice(0,-1).join("/") || "Noch neu zuzuordnen";
                const sourceDir=String(filesOfFamily[0].old_path||"").split("/").slice(0,-1).join("/") || "—";
                html += `<details class="card" style="margin:7px 0;padding:8px 10px"><summary style="cursor:pointer"><strong>${escapeHtml(stem)}</strong> <span class="muted">· ${filesOfFamily.length} Dateien · ${escapeHtml(sourceDir)} → ${escapeHtml(targetDir)}</span></summary>`;
                for (const f of filesOfFamily) {
                  const action=String(f.action||f.operation||"move");
                  html += `<div style="margin-top:8px"><strong>${escapeHtml(fileName(f.old_path||f.new_path))}</strong> <span class="muted">· ${escapeHtml(action)}</span>`;
                  html += `<div class="muted">IST</div><code style="display:block;white-space:pre-wrap;word-break:break-word">${escapeHtml(f.old_path||"—")}</code>`;
                  html += `<div class="muted">SOLL</div><code style="display:block;white-space:pre-wrap;word-break:break-word">${escapeHtml(f.new_path||"Noch neu zuzuordnen")}</code>`;
                  if (f.verification_status) html += `<div class="muted">Prüfung: ${escapeHtml(f.verification_status)}</div>`;
                  html += `</div>`;
                }
                html += `</details>`;
              }
              html += `</section>`;
            }
            html += `</div>`;
          }
        }

        // Herausfallende Archivfamilien müssen vor der Prüfung ein klares Ziel bekommen.
        const archiveReassignRes = await fetch(`/api/change-requests/${encodeURIComponent(crId)}/reassignments`);
        let archiveReassignData = null;
        if (archiveReassignRes.ok) archiveReassignData = await archiveReassignRes.json();
        if (archiveReassignData && Number(archiveReassignData.family_count || 0) > 0) {
          const targetOptions = (archiveReassignData.targets||[]).map(t => {
            if (t.event_kind === "no_event") return `<option value="existing-no-event:${escapeHtml(t.id)}">Bestehend · ${escapeHtml(t.folder_name||t.name||t.id)}</option>`;
            const parent=`<option value="existing-event:${escapeHtml(t.id)}">Bestehendes Ereignis · ${escapeHtml(t.name||t.folder_name||t.id)}</option>`;
            const child=(t.children||[]).map(c=>`<option value="existing-child:${escapeHtml(t.id)}:${escapeHtml(c.id)}">Bestehendes Unterereignis · ${escapeHtml(t.name)} / ${escapeHtml(c.name)}</option>`).join("");
            const newChild=`<option value="new-child:${escapeHtml(t.id)}">Neues Unterereignis in · ${escapeHtml(t.name)}</option>`;
            return parent+child+newChild;
          }).join("");
          html += `<section class="preview-note" style="margin-top:14px">
            <strong>Neu-Zuordnung vor Archivprüfung</strong><br>
            ${Number(archiveReassignData.family_count)} herausfallende ${Number(archiveReassignData.family_count)===1?"Familie benötigt":"Familien benötigen"} noch ein Ziel.
          </section>`;
          html += `<div data-archive-reassign-families style="display:grid;gap:8px;margin-top:10px">${(archiveReassignData.families||[]).map(f =>
            `<label class="card" style="padding:10px;display:flex;gap:10px;align-items:center"><input type="checkbox" data-archive-family value="${Number(f.family_id)}" checked><span><strong>${escapeHtml(f.original_stem||f.family_key||f.family_id)}</strong><br><span class="muted">${escapeHtml(String(f.selected_capture_time||"").slice(0,19))} · ${Number(f.file_count||0)} Dateien</span></span></label>`
          ).join("")}</div>`;
          html += `<label class="edit-field" style="margin-top:10px"><span>Ziel</span><select id="archive-reassign-target"><option value="new">Neues Ereignis erstellen</option><option value="new-no-event">Neues „Ohne Ereignis“ erstellen</option>${targetOptions}</select></label>`;
          html += `<label id="archive-reassign-name-row" class="edit-field"><span>Name des neuen Ereignisses / Unterereignisses</span><input id="archive-reassign-name" type="text" placeholder="Name"></label>`;
          html += `<div id="archive-reassign-time-row" class="edit-grid" hidden><label class="edit-field"><span>Startzeit</span><input id="archive-reassign-start" type="time"></label><label class="edit-field"><span>Endzeit</span><input id="archive-reassign-end" type="time"></label></div>`;
          html += `<button type="button" class="plan-button" id="archive-reassign-apply">Auswahl zuordnen</button><div id="archive-reassign-message" class="muted" style="margin-top:8px"></div>`;
        }

        // Workflow-Aktionen (propose -> preview -> confirm / cancel / archive)
        const status = String(cr.status || "");
        html += "<h4>Workflow</h4>";
        html += `<p><strong>Status:</strong> ${escapeHtml(status)}</p>`;
        if (status === "aenderbar_vorschlagen") {
          html +=
            `<button type="button" class="plan-button" data-cr-confirm="${escapeHtml(crId)}">Änderungen bestätigen</button>` +
            ` <button type="button" class="danger-button" data-cr-cancel="${escapeHtml(crId)}">Abbrechen</button>`;
        } else if (status === "aenderbar_bestaetigt") {
          const initiallyVerified = reviewRows.length > 0 && reviewRows.every(row => String(row.verification_status || "") === "verified");
          html +=
            `<div id="change-verify-panel" class="card" style="margin:10px 0;padding:12px">` +
              `<div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">` +
                `<button type="button" class="plan-button${initiallyVerified ? " success" : ""}" data-cr-verify="${escapeHtml(crId)}">${initiallyVerified ? "✓ Prüfung erfolgreich" : "Prüfen"}</button>` +
                `<span id="change-verify-summary" class="${initiallyVerified ? "success-text" : "muted"}">${initiallyVerified ? `${reviewRows.length}/${reviewRows.length} Dateien bestätigt.` : "Noch nicht vollständig geprüft."}</span>` +
              `</div>` +
              `<div id="change-verify-progress" style="display:none;margin-top:10px;height:8px;border-radius:999px;overflow:hidden;background:rgba(127,127,127,.22)"><div style="width:0%;height:100%;background:currentColor;transition:width .2s ease"></div></div>` +
              `<div id="change-verify-errors" style="display:${initiallyVerified ? "none" : "block"};margin-top:10px"></div>` +
            `</div>` +
            ` <button type="button" class="plan-button" data-cr-archive="${escapeHtml(crId)}" ${initiallyVerified ? "" : "disabled"}>Nach erfolgreicher Prüfung abschließen</button>` +
            ` <button type="button" class="danger-button" data-cr-cancel="${escapeHtml(crId)}">Abbrechen</button>`;
        } else {
          html += `<p class="muted">Dieser Aenderungsantrag ist abgeschlossen (${escapeHtml(status)}).</p>`;
        }

        changeRequestBody.innerHTML = html;

        const archiveTarget = changeRequestBody.querySelector("#archive-reassign-target");
        const archiveNameRow = changeRequestBody.querySelector("#archive-reassign-name-row");
        if (archiveTarget && archiveNameRow) {
          const archiveTimeRow=changeRequestBody.querySelector("#archive-reassign-time-row");
          const syncArchiveName = () => {
            const isNew=archiveTarget.value === "new";
            const isChild=archiveTarget.value.startsWith("new-child:");
            archiveNameRow.hidden = !(isNew || isChild);
            if (archiveTimeRow) archiveTimeRow.hidden = !isChild;
          };
          archiveTarget.addEventListener("change", syncArchiveName); syncArchiveName();
        }
        const archiveAssignButton = changeRequestBody.querySelector("#archive-reassign-apply");
        if (archiveAssignButton) archiveAssignButton.addEventListener("click", async () => {
          const message = changeRequestBody.querySelector("#archive-reassign-message");
          const familyIds = [...changeRequestBody.querySelectorAll("[data-archive-family]:checked")].map(x => Number(x.value));
          if (!familyIds.length) { if (message) message.textContent = "Wähle mindestens eine Familie aus."; return; }
          const value = archiveTarget.value;
          let targetMode="new_event", targetEventId=null, targetChildEventId=null;
          if (value === "new-no-event") targetMode="new_no_event";
          else if (value.startsWith("existing-no-event:")) { targetMode="existing_no_event"; targetEventId=value.slice(18); }
          else if (value.startsWith("existing-event:")) { targetMode="existing_event"; targetEventId=value.slice(15); }
          else if (value.startsWith("existing-child:")) { const bits=value.split(":"); targetMode="existing_event"; targetEventId=bits[1]; targetChildEventId=bits[2]; }
          else if (value.startsWith("new-child:")) { targetMode="new_child"; targetEventId=value.slice(10); }
          const isNamed = value === "new" || targetMode === "new_child";
          const body = { family_ids: familyIds, target_mode: targetMode, target_event_id: targetEventId, target_child_event_id: targetChildEventId, new_event_name: isNamed ? changeRequestBody.querySelector("#archive-reassign-name").value : null, new_child_start: targetMode === "new_child" ? changeRequestBody.querySelector("#archive-reassign-start").value : null, new_child_end: targetMode === "new_child" ? changeRequestBody.querySelector("#archive-reassign-end").value : null };
          archiveAssignButton.disabled = true; if (message) message.textContent = "Ziel und leere Arbeitsstruktur werden vorbereitet …";
          try {
            const assigned = await requestJson(`/api/change-requests/${encodeURIComponent(crId)}/reassignments`, {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
            if (message) message.textContent = assigned.prepared_structure ? `Vorbereitet: ${assigned.prepared_structure}` : "Zuordnung gespeichert.";
            await showChangeRequestDetail(crId);
            refreshGlobalTasks();
          } catch (error) { if (message) message.textContent = error.message; archiveAssignButton.disabled = false; }
        });

        // Workflow-Button-Handler
        const confirmBtn = changeRequestBody.querySelector("[data-cr-confirm]");
        if (confirmBtn) confirmBtn.addEventListener("click", () => changeRequestAction(crId, "confirm"));
        const cancelBtn = changeRequestBody.querySelector("[data-cr-cancel]");
        if (cancelBtn) cancelBtn.addEventListener("click", () => changeRequestAction(crId, "cancel"));
        const verifyBtn = changeRequestBody.querySelector("[data-cr-verify]");
        const archiveBtn = changeRequestBody.querySelector("[data-cr-archive]");
        if (verifyBtn) verifyBtn.addEventListener("click", async () => {
          const panel = changeRequestBody.querySelector("#change-verify-panel");
          const progress = changeRequestBody.querySelector("#change-verify-progress");
          const progressBar = progress?.firstElementChild;
          const summary = changeRequestBody.querySelector("#change-verify-summary");
          const errors = changeRequestBody.querySelector("#change-verify-errors");
          verifyBtn.disabled = true;
          verifyBtn.classList.remove("success", "danger");
          verifyBtn.textContent = "Prüfung läuft …";
          if (progress) progress.style.display = "block";
          if (progressBar) progressBar.style.width = "35%";
          if (summary) { summary.className = "muted"; summary.textContent = "Kamerabibliothek wird read-only nach Größe und SHA-256 geprüft …"; }
          if (errors) { errors.style.display = "none"; errors.innerHTML = ""; }
          try {
            const data = await requestJson(`/api/change-requests/${encodeURIComponent(crId)}/verify`, {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({})});
            if (progressBar) progressBar.style.width = "100%";
            const total = Number(data.file_count || 0);
            const ok = Number(data.verified_file_count || 0);
            const problems = (data.files || []).filter(row => String(row.status || "") !== "verified");
            if (data.complete) {
              verifyBtn.classList.add("success");
              verifyBtn.textContent = "✓ Prüfung erfolgreich";
              if (summary) { summary.className = "success-text"; summary.textContent = `${ok}/${total} Dateien bestätigt. Alle manuellen Änderungen stimmen.`; }
              if (archiveBtn) archiveBtn.disabled = false;
              if (errors) errors.style.display = "none";
            } else {
              verifyBtn.classList.add("danger");
              verifyBtn.textContent = "✕ Prüfung mit Problemen";
              if (summary) { summary.className = "danger-text"; summary.textContent = `${ok}/${total} Dateien bestätigt · ${problems.length} Problem${problems.length===1?"":"e"}.`; }
              if (archiveBtn) archiveBtn.disabled = true;
              if (errors) {
                errors.style.display = "block";
                errors.innerHTML = problems.map(row => {
                  const label = row.status === "missing" ? "Fehlt am Ziel" : row.status === "old_path_still_exists" ? "Liegt noch am alten Ort" : row.status === "size_mismatch" ? "Dateigröße abweichend" : row.status === "sha256_mismatch" ? "SHA-256 abweichend" : row.status === "needs_reassignment" ? "Noch neu zuzuordnen" : (row.message || row.status || "Problem");
                  return `<article class="card" style="margin:8px 0;padding:10px"><strong>${escapeHtml(label)}</strong>${row.message ? `<div class="muted">${escapeHtml(row.message)}</div>` : ""}<div class="muted" style="margin-top:6px">IST</div><code style="display:block;white-space:pre-wrap;word-break:break-word">${escapeHtml(row.old_path || "—")}</code><div class="muted" style="margin-top:6px">SOLL</div><code style="display:block;white-space:pre-wrap;word-break:break-word">${escapeHtml(row.new_path || "—")}</code></article>`;
                }).join("");
              }
            }
            setTimeout(() => { if (progress) progress.style.display = "none"; }, 400);
            refreshGlobalTasks();
          } catch (error) {
            if (progress) progress.style.display = "none";
            verifyBtn.classList.add("danger");
            verifyBtn.textContent = "✕ Prüfung fehlgeschlagen";
            if (summary) { summary.className = "danger-text"; summary.textContent = error.message; }
            if (archiveBtn) archiveBtn.disabled = true;
          } finally {
            verifyBtn.disabled = false;
          }
        });
        if (archiveBtn) archiveBtn.addEventListener("click", () => changeRequestAction(crId, "archive"));
      } catch (error) {
        changeRequestBody.textContent = `Fehler: ${error.message}`;
        setStatus(error.message, true);
      }
    }

    async function changeRequestAction(crId, action) {
      try {
        const res = await fetch(`/api/change-requests/${encodeURIComponent(crId)}/${action}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({}),
        });
        if (!res.ok) {
          const data = await res.json().catch(() => ({}));
          throw new Error(data.detail || `HTTP ${res.status}`);
        }
        const data = await res.json();
        setStatus(`Aenderungsauftrag: ${escapeHtml(data.status || action)}`);
        showChangeRequestDetail(crId);
        refreshGlobalTasks();
      } catch (error) {
        setStatus(error.message, true);
      }
    }

    async function proposeChangeRequest(eventId, jobId) {
      try {
        const res = await fetch(
          `/api/change-requests/${encodeURIComponent(eventId)}/propose?job_id=${encodeURIComponent(jobId || "")}`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({}),
          }
        );

        if (!res.ok) {
          const data = await res.json().catch(() => ({}));
          throw new Error(data.detail || `HTTP ${res.status}`);
        }

        const data = await res.json();
        setStatus(`Aenderungsantrag erstellt: ${data.change_request_id}`);
        if (!changeRequestDialog.open) changeRequestDialog.showModal();
        showChangeRequestDetail(data.change_request_id);
      } catch (error) {
        setStatus(error.message, true);
      }
    }

    // Fuer archivierte Ereignisse oeffnet "Bearbeiten" den
    // 0.16.0-Change-Request-Workflow: propose -> preview -> confirm /
    // cancel / archive. Es gibt KEINEN finish-Schritt; "archive"
    // ruft intern finish_event_change auf.
    async function openChangeRequestWorkflow(eventId, jobId) {
      await proposeChangeRequest(eventId, jobId);
    }

    eventSearch?.addEventListener("input", () => {
      clearTimeout(eventSearchTimer);
      eventSearchTimer = setTimeout(() => loadEvents({reset:true}).catch(error=>setStatus(error.message,true)), 250);
    });
    eventLoadMore?.addEventListener("click", () => loadEvents({reset:false}).catch(error=>setStatus(error.message,true)));

    loadJobs().then(async () => {
      const params = new URLSearchParams(location.search);
      const task = params.get("task") || "";
      const jobId = params.get("job") || "";
      if (task.startsWith("change:")) {
        const crId = task.slice("change:".length);
        if (!changeRequestDialog.open) changeRequestDialog.showModal();
        await showChangeRequestDetail(crId);
      } else if (task.startsWith("resort:")) {
        const eventId = task.slice("resort:".length);
        if (jobId) {
          const data = await requestJson(`/api/jobs/${encodeURIComponent(jobId)}/events`);
          const target = (data.events||[]).find(item=>item.id===eventId);
          if (target && !currentEvents.some(item=>item.id===eventId)) currentEvents.push({...target,_job_id:jobId});
          await loadReapplyPlan(eventId, jobId);
        }
      }
      refreshGlobalTasks();
    }).catch(error => setStatus(error.message,true));
  </script>
</body>
</html>
"""
