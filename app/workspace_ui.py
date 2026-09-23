WORKSPACE_HTML = r"""<!doctype html>
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

  <title>Sortieren</title>

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

    [hidden] { display: none !important; }

    html {
      min-height: 100%;
      -webkit-text-size-adjust: 100%;
      text-size-adjust: 100%;
      overscroll-behavior-y: auto;
      background: #101114;
    }

    body {
      position: relative;
      min-height: 100vh;
      min-height: 100dvh;
      width: 100%;
      min-width: 0;
      margin: 0;
      overflow-x: hidden;
      background: var(--background);
      color: var(--text);
      font-family:
        -apple-system,
        BlinkMacSystemFont,
        "Segoe UI",
        sans-serif;
    }

    button,
    input,
    select {
      font: inherit;
    }

    button,
    input,
    select {
      min-height: 44px;
      border: 1px solid var(--border);
      border-radius: 12px;
      background: var(--surface);
      color: var(--text);
    }

    button {
      padding: 10px 14px;
      cursor: pointer;
    }

    input,
    select {
      width: 100%;
      min-width: 0;
      max-width: 100%;
      padding: 10px 12px;
    }

    input[type="date"],
    input[type="time"] {
      inline-size: 100%;
      min-inline-size: 0;
      max-inline-size: 100%;
    }

    .form-grid > * {
      min-width: 0;
      max-width: 100%;
    }

    button:hover {
      border-color: var(--accent);
    }

    button:focus-visible,
    input:focus-visible,
    select:focus-visible {
      outline: 3px solid var(--accent);
      outline-offset: 3px;
    }

    button:disabled {
      cursor: not-allowed;
      opacity: 0.5;
    }

    main {
      width: min(1240px, 100%);
      min-width: 0;
      max-width: 100%;
      min-height: 100vh;
      min-height: 100dvh;
      margin: 0 auto;
      padding: 18px;
      padding-bottom: calc(18px + env(safe-area-inset-bottom));
      overflow-x: clip;
      background: var(--background);
    }

    header {
      margin-bottom: 14px;
    }

    .command-header {
      position: static;
      margin: 0 -18px 18px;
      padding: 14px 18px;
      border-bottom: 1px solid var(--border);
      background: var(--background);
    }

    .command-header-top {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 16px;
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

    h2 {
      font-size: 1.2rem;
    }

    .muted {
      color: var(--muted);
    }

    .navigation { display:flex; flex-wrap:wrap; gap:8px; }
    .navigation button[aria-current="page"] { border:2px solid #f2f3f5; background:var(--surface-2); opacity:1; color:var(--text); }
    .top-button { width:42px; min-width:42px; padding:0; font-size:1.2rem; }

    .primary {
      border-color: var(--accent);
      background: #243653;
    }

    .warning-button {
      border-color: var(--warning);
    }

    .toolbar {
      display: grid;
      grid-template-columns:
        minmax(220px, 1fr)
        auto
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

    .summary {
      display: grid;
      grid-template-columns:
        repeat(auto-fit, minmax(145px, 1fr));
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
      overflow-wrap: anywhere;
    }

    .workspace-layout {
      display: grid;
      grid-template-columns:
        minmax(0, 1.3fr)
        minmax(310px, 0.7fr);
      gap: 16px;
    }

    .section-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 12px;
    }

    .day-list {
      display: grid;
      gap: 10px;
    }

    .day-card {
      display: grid;
      grid-template-columns:
        auto
        minmax(0, 1fr)
        auto;
      align-items: center;
      gap: 13px;
      width: 100%;
      min-width: 0;
      border: 1px solid var(--border);
      border-radius: 15px;
      background: var(--surface);
      padding: 14px;
    }

    .day-card.selected {
      border-color: var(--accent);
      background: #202a3a;
    }

    .day-card.without-date {
      border-color: var(--warning);
    }

    .day-check {
      width: 22px;
      height: 22px;
      min-height: auto;
      accent-color: var(--accent);
    }

    .day-main {
      min-width: 0;
    }

    .day-name {
      display: block;
      margin-bottom: 5px;
      font-size: 1.05rem;
      font-weight: 700;
      overflow-wrap: anywhere;
    }

    .day-meta {
      display: flex;
      flex-wrap: wrap;
      gap: 6px 14px;
      color: var(--muted);
      font-size: 0.9rem;
    }

    .badge {
      display: inline-flex;
      width: fit-content;
      flex: 0 0 auto;
      border: 1px solid currentColor;
      border-radius: 999px;
      padding: 4px 8px;
      font-size: 0.78rem;
      font-weight: 700;
    }

    .badge.warning {
      color: var(--warning);
    }

    .badge.success {
      color: var(--success);
    }

    .suggestions-panel { margin:0 20px 18px; border-color:#6ea8ff; }
    .suggestion-list { display:grid; gap:10px; margin-top:12px; }
    .suggestion-card { border:1px solid var(--border); border-radius:14px; padding:14px; background:var(--panel-soft); }
    .suggestion-head { display:flex; justify-content:space-between; align-items:flex-start; gap:12px; }
    .suggestion-title { font-weight:750; }
    .suggestion-meta { display:flex; flex-wrap:wrap; gap:8px 14px; margin-top:8px; color:var(--muted); font-size:.92rem; }
    .suggestion-actions { display:flex; flex-wrap:wrap; gap:10px; margin-top:12px; }
    .suggestion-files { margin-top:10px; }
    .suggestion-files code { white-space:normal; overflow-wrap:anywhere; }

    .selection-bar {
      position: sticky;
      top: 0;
      z-index: 40;
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      width: 100%;
      min-width: 0;
      margin-bottom: 16px;
      border: 1px solid var(--border);
      border-radius: 14px;
      background:
        color-mix(
          in srgb,
          var(--surface-2) 95%,
          transparent
        );
      padding: 12px;
      backdrop-filter: blur(14px);
      -webkit-backdrop-filter: blur(14px);
    }

    .selection-actions {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      min-width: 0;
    }

    .preview {
      position: sticky;
      top: 88px;
      height: fit-content;
    }

    .preview-toggle {
      display: none;
    }

    .preview-body[hidden] {
      display: none;
    }

    .tree {
      border: 1px solid var(--border);
      border-radius: 13px;
      background: var(--surface-2);
      padding: 13px;
      font-family:
        ui-monospace,
        SFMono-Regular,
        Menlo,
        monospace;
      font-size: 0.9rem;
      line-height: 1.5;
    }
    .preview-root-title { margin-bottom:8px; font-weight:750; }
    .preview-days { display:grid; gap:7px; }
    .preview-day {
      min-width:0;
      border:1px solid var(--border);
      border-radius:10px;
      background:var(--surface);
      overflow:hidden;
    }
    .preview-day > summary {
      display:flex;
      align-items:center;
      justify-content:space-between;
      gap:8px;
      padding:8px 10px;
      cursor:pointer;
      list-style-position:inside;
      white-space:nowrap;
    }
    .preview-day-title { min-width:0; overflow:hidden; text-overflow:ellipsis; font-weight:700; }
    .preview-day-count { flex:0 0 auto; color:var(--muted); font-size:.76rem; }
    .preview-family-list { display:grid; gap:4px; padding:7px 10px 9px; border-top:1px solid var(--border); }
    .preview-family-row {
      display:grid;
      grid-template-columns:minmax(0,1fr) auto;
      gap:8px;
      align-items:baseline;
      min-width:0;
      white-space:nowrap;
      font-size:clamp(.64rem, 1.05vw, .78rem);
      line-height:1.35;
    }
    .preview-family-stem { min-width:0; overflow:hidden; text-overflow:ellipsis; }
    .preview-family-time { white-space:nowrap; font-variant-numeric:tabular-nums; }
    .preview-selection-note { margin-top:9px; color:var(--muted); font-size:.78rem; line-height:1.4; }

    .timeline-event-card {
      min-width: 0;
      border: 1px solid var(--accent);
      border-radius: 16px;
      background:
        color-mix(
          in srgb,
          var(--accent) 12%,
          var(--surface)
        );
      padding: 15px;
    }

    .timeline-event-header {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 12px;
    }

    .timeline-event-title {
      font-weight: 750;
      overflow-wrap: anywhere;
    }

    .timeline-event-folder {
      margin-top: 5px;
      color: var(--muted);
      overflow-wrap: anywhere;
    }

    .timeline-event-meta {
      display: flex;
      flex-wrap: wrap;
      gap: 6px 14px;
      margin-top: 11px;
      color: var(--muted);
      font-size: 0.9rem;
    }

    .partial-note {
      display: block;
      margin-top: 7px;
      color: var(--warning);
      font-size: 0.86rem;
    }

    .events-section {
      margin-top: 24px;
      scroll-margin-top: 180px;
    }

    .event-list {
      display: grid;
      gap: 10px;
    }

    .event-card {
      min-width: 0;
      border: 1px solid var(--border);
      border-radius: 15px;
      background: var(--surface);
      padding: 14px;
    }

    .event-card-header {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 12px;
    }

    .event-name {
      margin-bottom: 5px;
      font-weight: 700;
      overflow-wrap: anywhere;
    }

    .event-folder,
    .event-meta {
      color: var(--muted);
      overflow-wrap: anywhere;
    }

    .event-meta {
      display: flex;
      flex-wrap: wrap;
      gap: 6px 14px;
      margin-top: 10px;
      font-size: 0.9rem;
    }

    .saved-message {
      margin-top: 12px;
      border: 1px solid var(--success);
      border-radius: 12px;
      padding: 11px;
      color: var(--success);
    }

    .empty {
      border: 1px dashed var(--border);
      border-radius: 14px;
      padding: 22px;
      color: var(--muted);
    }

    dialog {
      box-sizing: border-box;
      inline-size: min(
        620px,
        calc(100dvw - 32px)
      );
      max-inline-size: calc(100dvw - 32px);
      min-inline-size: 0;
      max-block-size: calc(100dvh - 32px);
      overflow: hidden;
      border: 1px solid var(--border);
      border-radius: 18px;
      background: var(--surface);
      color: var(--text);
      padding: 0;
    }

    dialog::backdrop {
      background: rgb(0 0 0 / 0.72);
    }

    .dialog-content {
      box-sizing: border-box;
      width: 100%;
      min-width: 0;
      max-width: 100%;
      max-height: calc(100dvh - 32px);
      padding: 22px;
      overflow-y: auto;
      overflow-x: hidden;
    }

    .dialog-content *,
    .dialog-content *::before,
    .dialog-content *::after {
      box-sizing: border-box;
    }

    .dialog-content input:not([type="checkbox"]),
    .dialog-content select,
    .dialog-content textarea {
      display: block;
      width: 100%;
      min-width: 0;
      max-width: 100%;
    }

    .dialog-content input[type="date"],
    .dialog-content input[type="time"] {
      inline-size: calc(100% - 8px);
      min-inline-size: 0;
      max-inline-size: calc(100% - 8px);
      margin-inline: 4px;
      -webkit-appearance: none;
      appearance: none;
    }

    .dialog-content
    input[type="date"]::-webkit-date-and-time-value,
    .dialog-content
    input[type="time"]::-webkit-date-and-time-value {
      min-width: 0;
      text-align: left;
    }

    .dialog-content input:focus-visible,
    .dialog-content select:focus-visible,
    .dialog-content textarea:focus-visible {
      outline: none;
      border-color: var(--accent);
      box-shadow:
        inset 0 0 0 2px var(--accent);
    }

    .form-grid {
      display: grid;
      grid-template-columns: minmax(0, 1fr);
      gap: 12px;
      width: 100%;
      min-width: 0;
      max-width: 100%;
    }

    label {
      display: grid;
      gap: 6px;
      min-width: 0;
    }

    .full-width {
      grid-column: auto;
      min-width: 0;
      max-width: 100%;
    }

    .check-row {
      display: flex;
      align-items: center;
      gap: 10px;
      min-height: 44px;
    }

    .check-row input {
      width: 21px;
      height: 21px;
      min-height: auto;
      flex: 0 0 auto;
    }

    .time-fields[hidden] {
      display: none;
    }

    .dialog-actions {
      display: flex;
      justify-content: flex-end;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 18px;
    }

    .preview-note {
      margin-top: 12px;
      border: 1px solid var(--warning);
      border-radius: 12px;
      padding: 11px;
      color: var(--warning);
    }

    @media (max-width: 820px) {
      main {
        padding: 14px;
      }

      .command-header {
        margin:
          0 -14px 18px;
        padding:
          12px 14px;
      }

      .command-header-top {
        display: block;
      }

      .navigation {
        margin-top: 12px;
      }

      .toolbar {
        grid-template-columns: 1fr;
      }

      .workspace-layout {
        grid-template-columns: 1fr;
      }

      .preview {
        position: static;
      }

      .form-grid {
        grid-template-columns: 1fr;
      }

      .full-width {
        grid-column: auto;
      }
    }

    @media (
      max-width: 820px
    ) and (
      orientation: portrait
    ) {
      #selection-period {
        display: inline;
      }

      .preview {
        display: none;
      }

      .selection-bar {
        max-height: 100dvh;
        overflow-y: auto;
        overflow-x: hidden;
      }
    }

    @media (max-width: 520px) {
      main {
        padding: 12px;
      }

      .summary {
        grid-template-columns:
          repeat(2, minmax(0, 1fr));
      }

      .day-card {
        grid-template-columns:
          auto
          minmax(0, 1fr);
      }

      .day-card > .badge {
        grid-column: 2;
      }

      .selection-bar {
        display: block;
      }

      .selection-actions {
        display: grid;
        grid-template-columns:
          repeat(2, minmax(0, 1fr));
        width: 100%;
        margin-top: 10px;
      }

      .selection-actions button {
        width: 100%;
      }

      .page-navigation {
        display: flex;
      }

      .form-grid {
        grid-template-columns: 1fr;
      }

      .full-width {
        grid-column: auto;
      }

      .dialog-actions {
        display: grid;
        grid-template-columns: 1fr;
      }
    }

    @media (
      min-width: 821px
    ), (
      orientation: landscape
    ) {
      #selection-period {
        display: none;
      }
    }

    @media (prefers-reduced-motion: reduce) {
      *,
      *::before,
      *::after {
        scroll-behavior: auto !important;
        transition-duration: 0.01ms !important;
        animation-duration: 0.01ms !important;
        animation-iteration-count: 1 !important;
      }
    }
    .global-header { position:static; }
    .page-intro { margin-bottom:12px; }
    .page-navigation { display:flex; flex-wrap:nowrap; overflow-x:auto; gap:8px; margin-bottom:16px; scrollbar-width:none; }
    .page-navigation::-webkit-scrollbar { display:none; }
    .page-navigation button { flex:0 0 auto; white-space:nowrap; }
    .selection-bar { padding-right:64px; }
    .selection-top-button { position:absolute; right:12px; top:12px; }
    .selection-top-button:active { transform:scale(.98); }
    .planned-choice { display:flex; gap:8px; align-items:center; }
    .planned-check { appearance:none; width:16px; height:16px; min-height:16px; padding:0; border:1px solid #d7dbe0; border-radius:3px; background:#111; }
    .planned-check:checked::after { content:"✓"; display:block; color:#fff; font-size:12px; line-height:14px; text-align:center; }
    .selection-summary { display:flex; align-items:baseline; gap:10px; min-width:0; }
    #selection-period { font-size:.82rem; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
    html, body { background: #090b0d !important; min-height: 100%; }
    #refresh-button { display:none !important; }
    body::before { content: ""; position: fixed; inset: -120px 0; background: #090b0d; z-index: -1000; pointer-events: none; }
  
    .global-task-fab { position:fixed; right:18px; bottom:18px; z-index:1200; width:50px; height:50px; border-radius:50%; display:flex; align-items:center; justify-content:center; font-size:22px; box-shadow:0 8px 28px rgba(0,0,0,.35); background:#20252b; border:1px solid #4a5663; }
    .global-task-fab.visible { display:flex; }
    .global-task-badge.hidden { display:none !important; }
    .global-task-badge { position:absolute; right:-4px; top:-6px; min-width:22px; height:22px; padding:0 5px; border-radius:12px; background:#e04f5f; color:white; border:2px solid #090b0d; font-size:12px; font-weight:800; display:flex; align-items:center; justify-content:center; }
    .global-task-panel { position:fixed; right:18px; bottom:78px; z-index:1199; width:min(390px,calc(100vw - 36px)); max-height:60vh; overflow:auto; padding:14px; border-radius:14px; border:1px solid #3b424a; background:#181c20; box-shadow:0 14px 44px rgba(0,0,0,.5); display:none; }
    .global-task-panel.open { display:block; }
    .global-task-item { display:block; padding:10px; margin-top:8px; border-radius:10px; border:1px solid #333a42; background:#20252b; color:inherit; text-decoration:none; }
    .global-task-item strong { display:block; margin-bottom:3px; }


    summary { cursor:pointer; user-select:none; }
    summary[style*="display:flex"]::before { content:"▸"; flex:0 0 auto; }
    details[open] > summary[style*="display:flex"]::before { content:"▾"; }
    .event-details > summary { display:list-item !important; list-style:disclosure-closed !important; }
    .event-details[open] > summary { list-style:disclosure-open !important; }
    button.plan-button, .plan-button, button.bk-positive-action, button[type=submit], #save-event-button { background:#2563eb !important; border-color:#2563eb !important; color:white !important; }
    #calculate-preview-button { background:#374151 !important; border-color:#4b5563 !important; color:white !important; }
    button.danger-button, .danger-button { background:#b42318 !important; border-color:#b42318 !important; color:white !important; }
  </style>
</head>

<body>
  <main>
    <section class="bk-workspace-command">
      <header class="page-intro">
        <h1>Sortieren</h1>

        <p class="muted">
          Tagesbestände auswählen, Ereignisse erstellen und Änderungen direkt anwenden.
        </p>
      </header>

      <nav class="navigation page-navigation" aria-label="Seitennavigation">
        <button type="button" onclick="location.href='/'">Import &amp; Prüfung</button>
        <button type="button" aria-current="page">Sortieren</button>
        <button type="button" onclick="location.href='/events?job=' + encodeURIComponent(document.getElementById('job-select').value)">Ereignisse</button>
        <button type="button" onclick="location.href='/transfer'">Archiv</button>
      </nav>

      <div class="bk-workspace-job-picker">
        <label>
          <span class="muted">
            Sicherung auswählen
          </span>

          <select
            id="job-select"
            aria-label="Sicherung auswählen"
          >
            <option value="">
              Sicherungen werden geladen …
            </option>
          </select>
        </label>


      </div>

    </section>

    <section id="post-save-action" class="card" hidden style="margin:0 0 18px; border-color:#6ea8ff;">
      <strong id="post-save-title">Geplante Änderungen</strong>
      <p id="post-save-detail" class="muted" style="margin:8px 0 12px;">Alle geplanten Ereignisse sind standardmäßig ausgewählt.</p>
      <details style="margin:0 0 14px;">
        <summary>Auswahl anpassen</summary>
        <div id="planned-event-selection" style="display:grid;gap:8px;margin-top:10px;"></div>
      </details>
      <button id="apply-saved-event-button" class="primary bk-positive-action" type="button">Alle geplanten Ereignisse anwenden</button>
      <span id="apply-saved-event-status" class="muted" style="margin-left:12px;"></span>
    </section>

    <section id="event-suggestions-panel" class="card suggestions-panel" hidden>
      <h2>Nachträgliche Aufnahmen erkannt</h2>
      <p class="muted">Die Aufnahmezeiten passen eindeutig zu bereits vorhandenen Ereignissen. Erst nach deiner Bestätigung wird eine sichere Ergänzung oder ein Nachtrag geplant.</p>
      <div id="event-suggestion-list" class="suggestion-list"></div>
      <p id="event-suggestion-status" class="muted" role="status" aria-live="polite"></p>
    </section>

    <section
      id="selection-bar"
      class="selection-bar"
    >
      <div class="selection-summary"><strong id="selection-label">0 Gruppen ausgewählt</strong><span id="selection-period" class="muted"></span></div>

      <div class="selection-actions">
        <button
          id="select-all-button"
          type="button"
        >
          Alle Tage
        </button>

        <button
          id="clear-selection-button"
          type="button"
        >
          Auswahl aufheben
        </button>

        <button
          id="no-event-button"
          class="warning-button"
          type="button"
        >
          Ohne Ereignis
        </button>

        <button id="existing-no-event-button" type="button" hidden aria-hidden="true" tabindex="-1">Zu bestehendem Ohne Ereignis</button>

        <button
          id="new-event-button"
          class="primary"
          type="button"
          disabled
        >
          Ereignis
        </button>


      </div>

      <button class="top-button selection-top-button" type="button" onclick="window.scrollTo({top:0,behavior:'smooth'})" aria-label="Nach oben">↑</button>
    </section>

    <p
      id="status"
      class="status muted"
      role="status"
      aria-live="polite"
    ></p>

    <section class="summary">
      <div class="card">
        <span class="muted">Tage</span>
        <span
          id="summary-days"
          class="number"
        >
          –
        </span>
      </div>

      <div class="card">
        <span class="muted">Dateien</span>
        <span
          id="summary-files"
          class="number"
        >
          –
        </span>
      </div>

      <div class="card">
        <span class="muted">Familien</span>
        <span
          id="summary-families"
          class="number"
        >
          –
        </span>
      </div>

      <div class="card">
        <span class="muted">Prüffälle</span>
        <span
          id="summary-review"
          class="number"
        >
          –
        </span>
      </div>
    </section>

    <section class="workspace-layout">
      <div>
        <div class="section-header">
          <h2>Tagesordner</h2>

          <span
            id="day-count-label"
            class="muted"
          ></span>
        </div>

        <div
          id="day-list"
          class="day-list"
        >
          <div class="empty">
            Noch kein Arbeitsbestand ausgewählt.
          </div>
        </div>

        <section
          id="saved-events-section"
          class="events-section"
        >
          <div class="section-header">
            <h2>Gespeicherte Ereignisse</h2>

            <span
              id="event-count-label"
              class="muted"
            ></span>
          </div>

          <div
            id="saved-event-list"
            class="event-list"
          >
            <div class="empty">
              Noch keine Ereignisse gespeichert.
            </div>
          </div>
        </section>
      </div>

      <aside class="card preview">
        <button
          id="preview-toggle"
          class="preview-toggle"
          type="button"
          aria-expanded="false"
          aria-controls="preview-body"
        >
          Zielstruktur anzeigen
        </button>

        <div
          id="preview-body"
          class="preview-body"
        >
          <h2>Zielstruktur-Vorschau</h2>

          <p class="muted">
            Die Vorschau zeigt nur die Planung.
            Es werden noch keine Ordner verändert.
          </p>

          <div
            id="structure-preview"
            class="tree"
          >Noch keine Auswahl.</div>
        </div>
      </aside>
    </section>
  </main>

  <dialog id="event-dialog">
    <form
      id="event-form"
      class="dialog-content"
      method="dialog"
    >
      <h2 id="dialog-title">
        Ereignis erstellen
      </h2>

      <p class="muted">
        Der Zeitraum kann aus ausgewählten
        Tagesordnern übernommen oder frei
        eingetragen werden.
      </p>

      <div class="form-grid">
        <label class="full-width">
          <span>Ereignisname</span>

          <input
            id="event-name"
            type="text"
            placeholder="Zum Beispiel Israel"
          >
        </label>

        <label id="existing-parent-row" class="full-width" hidden>
          <span>Oberereignis</span>
          <select id="existing-parent-event"></select>
          <small class="muted">Wenn an diesem Tag bereits ein geplantes Oberereignis existiert, wird es standardmäßig fortgeführt. „Neues Oberereignis“ bleibt jederzeit möglich.</small>
        </label>

        <div id="no-event-segment-editor" class="full-width" hidden>
          <label id="existing-no-event-target-row" class="full-width" hidden style="margin-bottom:10px">
            <span>Bestehende „Ohne Ereignis“-Sammlung</span>
            <select id="existing-no-event-target"></select>
          </label>
          <details id="no-event-range-details" class="card" style="padding:10px;margin-bottom:10px">
            <summary style="display:flex;align-items:center;justify-content:space-between;gap:10px;cursor:pointer">
              <span><strong>Zeitspanne</strong> <span class="muted">· Auswahlhilfe</span></span>
              <button id="add-no-event-range-block" type="button" style="margin-left:auto">＋ Zeitblock hinzufügen</button>
            </summary>
            <div id="no-event-range-generator" hidden style="margin-top:10px;padding-top:10px;border-top:1px solid var(--border-color, #30363d)">
              <div id="no-event-range-fields" class="form-grid"></div>
              <div style="display:flex;justify-content:flex-end;gap:8px;margin-top:8px">
                <button id="cancel-no-event-range-block" type="button">Abbrechen</button>
                <button id="apply-no-event-range-block" type="button" class="plan-button">Zeitblock übernehmen</button>
              </div>
            </div>
            <div id="no-event-range-summary" style="display:grid;gap:6px;margin-top:8px"></div>
          </details>
          <div style="display:flex;justify-content:space-between;gap:8px;align-items:center;margin-bottom:8px">
            <strong>Tagessegmente</strong>
            <button id="add-no-event-segment" type="button">＋ Tagessegment</button>
          </div>
          <div id="no-event-segment-list" style="display:grid;gap:6px"></div>
        </div>

        <label>
          <span>Beginn</span>

          <input
            id="event-start-date"
            type="date"
            required
          >
        </label>

        <label>
          <span>Ende</span>

          <input
            id="event-end-date"
            type="date"
            required
          >
        </label>

        <label class="full-width check-row">
          <input
            id="use-time-range"
            type="checkbox"
          >

          <span>Uhrzeiten berücksichtigen</span>
        </label>

        <div
          id="time-fields"
          class="form-grid full-width time-fields"
          hidden
        >
          <label class="full-width">
            <span>Unterereignis (optional)</span>

            <input
              id="child-event-name"
              type="text"
              placeholder="Zum Beispiel Stadtfest"
            >
          </label>

          <label>
            <span>Startzeit</span>

            <input
              id="event-start-time"
              type="time"
              value="00:00"
            >
          </label>

          <label>
            <span>Endzeit</span>

            <input
              id="event-end-time"
              type="time"
              value="23:59"
            >
          </label>
        </div>

        <label class="full-width check-row">
          <input
            id="preserve-day-folders"
            type="checkbox"
          >

          <span>
            Tagesordner innerhalb des
            Ereignisses behalten
          </span>
        </label>
      </div>

      <div
        id="dialog-preview"
        class="tree"
        style="margin-top: 16px"
        hidden
      >Noch keine Vorschau.</div>

      <div class="preview-note">
        Beim Speichern wird nur die Planung in SQLite
        eingetragen. Dateien und Ordner bleiben
        unverändert.
      </div>

      <div
        id="save-result"
        class="saved-message"
        hidden
        role="status"
        aria-live="polite"
      ></div>

      <div class="dialog-actions">
        <button
          id="close-dialog-button"
          type="button"
        >
          Schließen
        </button>

        <button
          id="calculate-preview-button"
          type="button"
        >
          Vorschau einblenden
        </button>

        <button
          id="save-event-button"
          class="primary bk-positive-action"
          type="button"
        >
          Ereignis speichern
        </button>
      </div>
    </form>
  </dialog>

  
  <dialog id="task-reassign-dialog">
    <div class="dialog-content">
      <div style="display:flex;justify-content:space-between;gap:12px;align-items:start">
        <div><h2 style="margin:0">Neu-Zuordnung</h2><p id="task-reassign-subtitle" class="muted">Offene Familien werden geladen …</p></div>
        <button id="task-reassign-close" type="button">Schließen</button>
      </div>
      <div id="task-reassign-body" style="display:grid;gap:10px;margin-top:14px"></div>
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

    const jobSelect =
      document.getElementById("job-select");


    const newEventButton =
      document.getElementById("new-event-button");
    const existingNoEventButton = document.getElementById("existing-no-event-button");

    const noEventButton =
      document.getElementById("no-event-button");

    const statusElement =
      document.getElementById("status");

    const dayList =
      document.getElementById("day-list");

    const selectionBar =
      document.getElementById("selection-bar");
    const eventSuggestionsPanel = document.getElementById("event-suggestions-panel");
    const eventSuggestionList = document.getElementById("event-suggestion-list");
    const eventSuggestionStatus = document.getElementById("event-suggestion-status");
    let eventSuggestions = [];

    const selectionLabel =
      document.getElementById("selection-label");

    const selectAllButton =
      document.getElementById("select-all-button");

    const clearSelectionButton =
      document.getElementById(
        "clear-selection-button"
      );

    const structurePreview =
      document.getElementById(
        "structure-preview"
      );

    const eventDialog =
      document.getElementById("event-dialog");
    const eventForm =
      document.getElementById("event-form");
    const taskReassignDialog = document.getElementById("task-reassign-dialog");
    const taskReassignBody = document.getElementById("task-reassign-body");
    const taskReassignSubtitle = document.getElementById("task-reassign-subtitle");
    const taskReassignClose = document.getElementById("task-reassign-close");
    let taskReassignContext = null;

    const dialogTitle =
      document.getElementById("dialog-title");

    const eventName =
      document.getElementById("event-name");

    const existingParentRow = document.getElementById("existing-parent-row");
    const existingParentEvent = document.getElementById("existing-parent-event");

    const eventStartDate =
      document.getElementById(
        "event-start-date"
      );

    const eventEndDate =
      document.getElementById(
        "event-end-date"
      );

    const noEventSegmentEditor = document.getElementById("no-event-segment-editor");
    const noEventSegmentList = document.getElementById("no-event-segment-list");
    const noEventRangeFields = document.getElementById("no-event-range-fields");
    const noEventRangeSummary = document.getElementById("no-event-range-summary");
    const noEventRangeDetails = document.getElementById("no-event-range-details");
    const noEventRangeGenerator = document.getElementById("no-event-range-generator");
    const addNoEventRangeBlock = document.getElementById("add-no-event-range-block");
    const applyNoEventRangeBlock = document.getElementById("apply-no-event-range-block");
    const cancelNoEventRangeBlock = document.getElementById("cancel-no-event-range-block");
    const existingNoEventTargetRow = document.getElementById("existing-no-event-target-row");
    const existingNoEventTarget = document.getElementById("existing-no-event-target");
    let noEventTargetCache = [];
    let activeNoEventTarget = null;

    const useTimeRange =
      document.getElementById("use-time-range");

    const timeFields =
      document.getElementById("time-fields");

    const childEventName =
      document.getElementById(
        "child-event-name"
      );

    const eventStartTime =
      document.getElementById(
        "event-start-time"
      );

    const eventEndTime =
      document.getElementById(
        "event-end-time"
      );

    const preserveDayFolders =
      document.getElementById(
        "preserve-day-folders"
      );

    const dialogPreview =
      document.getElementById(
        "dialog-preview"
      );

    const closeDialogButton =
      document.getElementById(
        "close-dialog-button"
      );

    const calculatePreviewButton =
      document.getElementById(
        "calculate-preview-button"
      );

    const saveEventButton =
      document.getElementById(
        "save-event-button"
      );

    const saveResult =
      document.getElementById(
        "save-result"
      );

    const postSaveAction = document.getElementById("post-save-action");
    const postSaveTitle = document.getElementById("post-save-title");
    const postSaveDetail = document.getElementById("post-save-detail");
    const applySavedEventButton = document.getElementById("apply-saved-event-button");
    const applySavedEventStatus = document.getElementById("apply-saved-event-status");
    const plannedEventSelection = document.getElementById("planned-event-selection");
    let lastSavedEvent = null;

    const savedEventList =
      document.getElementById(
        "saved-event-list"
      );

    const eventCountLabel =
      document.getElementById(
        "event-count-label"
      );

    const previewToggle =
      document.getElementById(
        "preview-toggle"
      );

    const previewBody =
      document.getElementById(
        "preview-body"
      );

    let jobs = [];
    let workspace = null;
    let selectedDays = new Set();
    let dialogMode = "event";


    function workspaceStatusLabel(status) {
      const labels = {
        draft: "Entwurf",
        planned: "Geplant",
        applied: "Angewendet",
        archived: "Archiviert"
      };
      return labels[String(status || "")] || String(status || "");
    }


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
      isError = false
    ) {
      statusElement.textContent = message;
      statusElement.classList.toggle(
        "error",
        isError
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


    function formatDay(dayKey) {
      if (!dayKey) {
        return "Ohne Datum";
      }

      const date = new Date(
        `${dayKey}T12:00:00`
      );

      return new Intl.DateTimeFormat(
        "de-DE",
        {
          weekday: "long",
          day: "2-digit",
          month: "2-digit",
          year: "numeric"
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

      let result = bytes;
      let unitIndex = -1;

      do {
        result /= 1024;
        unitIndex += 1;
      } while (
        result >= 1024
        && unitIndex < units.length - 1
      );

      return (
        new Intl.NumberFormat(
          "de-DE",
          {
            maximumFractionDigits: 1
          }
        ).format(result)
        + " "
        + units[unitIndex]
      );
    }


    async function getJson(url) {
      const response = await fetch(url);
      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail || "Anfrage fehlgeschlagen."
        );
      }

      return data;
    }


    async function postJson(
      url,
      payload
    ) {
      const response = await fetch(
        url,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify(payload)
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail || "Anfrage fehlgeschlagen."
        );
      }

      return data;
    }


    async function loadJobs() {
      setStatus("Arbeitsbestände werden geladen …");

      const data = await getJson("/api/jobs");

      jobs = (data.jobs || [])
        .filter(
          job =>
            [
              "metadata_fixture_analysis",
              "folder_import",
              "sd_import"
            ].includes(job.operation)
        )
        .sort(
          (a, b) =>
            String(b.created_at).localeCompare(
              String(a.created_at)
            )
        );

      jobSelect.innerHTML = "";

      if (!jobs.length) {
        const option =
          document.createElement("option");

        option.value = "";
        option.textContent =
          "Keine Arbeitsbestände vorhanden";

        jobSelect.appendChild(option);

        setStatus(
          "Noch kein analysierter Arbeitsbestand vorhanden."
        );

        return;
      }

      for (const job of jobs) {
        const option =
          document.createElement("option");

        option.value = job.id;
        option.textContent =
          formatJobLabel(job);

        jobSelect.appendChild(option);
      }

      const requestedJob =
        new URLSearchParams(
          location.search
        ).get("job");

      if (
        requestedJob
        && jobs.some(
          job => job.id === requestedJob
        )
      ) {
        jobSelect.value = requestedJob;
      }

      await loadWorkspace();
    }


    async function loadWorkspace() {
      const jobId = jobSelect.value;

      if (!jobId) {
        return;
      }

      setStatus("Arbeitsbereich wird geladen …");

      const [workspaceData, suggestionData] = await Promise.all([
        getJson(`/api/jobs/${encodeURIComponent(jobId)}/workspace-summary`),
        getJson(`/api/jobs/${encodeURIComponent(jobId)}/event-suggestions`)
      ]);
      workspace = workspaceData;
      eventSuggestions = suggestionData.suggestions || [];

      selectedDays.clear();

      renderSummary();
      renderEventSuggestions();
      renderDays();
      renderEvents();
      renderPlannedActions();
      renderSelection();

      setStatus(
        `${workspace.statistics.day_count} Tagesgruppen geladen.`
      );
    }


    function renderEventSuggestions() {
      eventSuggestionsPanel.hidden = eventSuggestions.length === 0;
      eventSuggestionList.innerHTML = "";
      eventSuggestionStatus.textContent = "";
      for (const item of eventSuggestions) {
        const card = document.createElement("article");
        card.className = "suggestion-card";
        const statusText = item.target_status === "planned"
          ? "Offene Planung"
          : item.target_status === "applied"
            ? "Bereits angewendet"
            : "Bereits archiviert";
        const consequence = item.target_status === "planned"
          ? "Wird als sichere Ergänzung der offenen Planung angelegt."
          : item.target_status === "applied"
            ? "Wird als verknüpfter Nachtrag angelegt und separat geprüft."
            : "Wird unter ‚Später zuzuordnen‘ für die manuelle Archiv-Ergänzung bereitgestellt.";
        const familyRows = (item.families || []).map(family => `
          <li><strong>${escapeHtml(family.original_stem || family.family_key || "Dateifamilie")}</strong>
          · ${escapeHtml(family.capture_time || "")}
          · ${Number(family.file_count || 0)} Dateien</li>`).join("");
        const familyIds = (item.family_ids || []).map(Number).filter(Number.isFinite);
        card.innerHTML = `
          <div class="suggestion-head">
            <div>
              <div class="suggestion-title">${Number(item.family_count || familyIds.length)} Familien passen zu ${escapeHtml(item.target_name)}</div>
              <div class="muted">Eindeutige Übereinstimmung mit dem bereits belegten Ereigniszeitraum aus einer anderen Sicherung.</div>
            </div>
            <span class="badge ${item.target_status === "archived" ? "warning" : "success"}">${escapeHtml(statusText)}</span>
          </div>
          <div class="suggestion-meta">
            <span>${Number(item.file_count || 0)} Dateien</span>
            <span>${escapeHtml(item.target_start_datetime)} bis ${escapeHtml(item.target_end_datetime)}</span>
          </div>
          <details class="suggestion-files">
            <summary>Vorschau und Wirkung</summary>
            <p>${escapeHtml(consequence)}</p>
            <ul>${familyRows}</ul>
            <code>${escapeHtml(item.target_folder_name || "")}</code>
          </details>
          <div class="suggestion-actions">
            <button type="button" class="primary accept-suggestion" data-family-ids="${escapeHtml(JSON.stringify(familyIds))}" data-target-event-id="${escapeHtml(item.target_event_id)}">${escapeHtml(item.action_label)}</button>
          </div>`;
        eventSuggestionList.appendChild(card);
      }
    }

    function renderPlannedActions() {
      const planned = (workspace?.events || []).filter(event =>
        event.event_level === "parent" && event.status === "planned"
      );
      postSaveAction.hidden = planned.length === 0;
      plannedEventSelection.innerHTML = planned.map(event => `
        <label class="planned-choice">
          <input class="planned-check" type="checkbox" data-planned-event="${escapeHtml(event.id)}" checked>
          <span>${escapeHtml(event.display_title || event.name)} · ${Number(event.assigned_family_count || 0)} Familien</span>
        </label>`).join("");
      const families = planned.reduce((sum,event)=>sum+Number(event.assigned_family_count||0),0);
      const files = planned.reduce((sum,event)=>sum+Number(event.assigned_file_count||0),0);
      postSaveTitle.textContent = planned.length === 1 ? "1 geplantes Ereignis" : `${planned.length} geplante Ereignisse`;
      postSaveDetail.textContent = `${families} Familien · ${files} Dateien. Standardmäßig werden alle geplanten Ereignisse angewendet.`;
      applySavedEventButton.textContent = planned.length === 1 ? "Ereignis anwenden" : "Alle geplanten Ereignisse anwenden";
      applySavedEventButton.disabled = planned.length === 0;
    }

    function renderSummary() {
      const statistics =
        workspace?.statistics || {};

      document.getElementById(
        "summary-days"
      ).textContent =
        statistics.day_count ?? "–";

      document.getElementById(
        "summary-files"
      ).textContent =
        statistics.file_count ?? "–";

      document.getElementById(
        "summary-families"
      ).textContent =
        statistics.family_count ?? "–";

      document.getElementById(
        "summary-review"
      ).textContent =
        statistics.review_required_count ?? "–";

      const withoutDate =
        Number(
          statistics.without_date_file_count
          || 0
        ) > 0;

      document.getElementById(
        "day-count-label"
      ).textContent =
        withoutDate
          ? `${statistics.day_count} Tage + Ohne Datum`
          : `${statistics.day_count} Tage`;
    }


    function renderEvents() {
      const allEvents =
        workspace?.events || [];

      const parentEvents =
        allEvents.filter(
          event =>
            event.event_level === "parent"
        );

      eventCountLabel.textContent =
        parentEvents.length === 1
          ? "1 Ereignis"
          : `${parentEvents.length} Ereignisse`;

      savedEventList.innerHTML = "";

      if (!parentEvents.length) {
        savedEventList.innerHTML =
          '<div class="empty">'
          + "Noch keine Ereignisse gespeichert."
          + "</div>";

        return;
      }

      for (const event of parentEvents) {
        const childEvents =
          allEvents.filter(
            child =>
              child.parent_event_id === event.id
          );

        const card =
          document.createElement("article");

        card.className = "event-card";
        card.addEventListener("click",async(e)=>{
          if(e.target.closest('button,input,a,summary')) return;
          const data=await getJson(`/api/jobs/${encodeURIComponent(jobSelect.value)}/events/${encodeURIComponent(event.id)}/structure`);
          structurePreview.textContent=data.structure_text; previewBody.hidden=false;
        });

        const kindLabel =
          event.event_kind === "no_event"
            ? "Ohne Ereignis"
            : "Ereignis";

        const childText =
          childEvents.length
            ? childEvents
                .map(
                  child =>
                    `<div class="event-folder">
                      Unterereignis:
                      ${escapeHtml(child.folder_name)}
                    </div>`
                )
                .join("")
            : "";

        card.innerHTML = `
          <div class="event-card-header">
            <div>
              <div class="event-name">
                ${escapeHtml(event.display_title || event.name)}
              </div>

              <div class="event-folder">
                ${escapeHtml(event.folder_name)}
              </div>

              ${childText}
            </div>

            <span class="badge success">
              ${escapeHtml(workspaceStatusLabel(event.status))}
            </span>
          </div>

          <div class="event-meta">
            <span>
              ${escapeHtml(kindLabel)}
            </span>

            <span>
              ${escapeHtml(event.start_datetime)}
            </span>

            <span>
              bis
              ${escapeHtml(event.end_datetime)}
            </span>

            <span>
              ${
                event.preserve_day_folders
                  ? "Tagesordner bleiben erhalten"
                  : "Ohne Tagesunterordner"
              }
            </span>

            <span>
              ${
                Number(
                  event.assigned_family_count || 0
                )
              }
              Familien
            </span>
          </div>
        `;

        savedEventList.appendChild(card);
      }
    }


    function planningOverview() {
      if (
        workspace
        && workspace.planning_overview
      ) {
        return workspace.planning_overview;
      }

      const groups =
        workspace
        && Array.isArray(
          workspace.day_groups
        )
          ? workspace.day_groups
          : [];

      return {
        event_groups: [],
        available_day_groups:
          groups,
        timeline_groups:
          groups.map(
            group => ({
              ...group,
              group_type: "day"
            })
          )
      };
    }


    function availableDayGroups() {
      return (
        planningOverview()
          .available_day_groups
        || []
      );
    }


    function formatTimelineDateRange(
      startValue,
      endValue
    ) {
      const start = String(
        startValue || ""
      ).slice(0, 10);

      const end = String(
        endValue || ""
      ).slice(0, 10);

      if (!start) {
        return "Ohne Zeitraum";
      }

      if (
        !end
        || start === end
      ) {
        return formatDay(start);
      }

      const startDate =
        new Date(
          `${start}T12:00:00`
        );

      const endDate =
        new Date(
          `${end}T12:00:00`
        );

      return (
        startDate.toLocaleDateString(
          "de-DE",
          {
            day: "2-digit",
            month: "2-digit"
          }
        )
        + "–"
        + endDate.toLocaleDateString(
          "de-DE",
          {
            day: "2-digit",
            month: "2-digit",
            year: "numeric"
          }
        )
      );
    }


    function renderDays() {
      dayList.innerHTML = "";

      const groups =
        planningOverview()
          .timeline_groups
        || [];

      if (!groups.length) {
        dayList.innerHTML =
          '<div class="empty">'
          + "Keine freien oder verplanten "
          + "Tagesbestände vorhanden."
          + "</div>";

        return;
      }

      const availableKeys =
        new Set(
          availableDayGroups().map(
            group =>
              group.card_key || group.day_key
              || "__without_date__"
          )
        );

      for (
        const selectedKey
        of [...selectedDays]
      ) {
        if (
          !availableKeys.has(
            selectedKey
          )
        ) {
          selectedDays.delete(
            selectedKey
          );
        }
      }

      for (const group of groups) {
        if (
          group.group_type
          === "event"
        ) {
          const card =
            document.createElement(
              "article"
            );

          card.className =
            "timeline-event-card";
          card.style.cursor="pointer";
          card.addEventListener("click",async()=>{
            const data=await getJson(`/api/jobs/${encodeURIComponent(jobSelect.value)}/events/${encodeURIComponent(group.event_id)}/structure`);
            structurePreview.textContent=data.structure_text;
            previewBody.hidden=false;
          });

          const range =
            formatTimelineDateRange(
              group.start_datetime,
              group.end_datetime
            );

          const childText =
            (group.child_events || [])
              .map(
                child => `
                  <div
                    class="timeline-event-folder"
                  >
                    Unterereignis:
                    ${escapeHtml(
                      child.folder_name
                    )}
                  </div>
                `
              )
              .join("");

          card.innerHTML = `
            <div
              class="timeline-event-header"
            >
              <div>
                <div
                  class="timeline-event-title"
                >
                  ${escapeHtml(range)}
                  ·
                  ${escapeHtml(
                    group.event_name
                  )}
                </div>

                <div
                  class="timeline-event-folder"
                >
                  ${escapeHtml(
                    group.folder_name
                  )}
                </div>

                ${childText}
              </div>

              <span class="badge success">
                ${escapeHtml(
                  workspaceStatusLabel(group.status)
                )}
              </span>
            </div>

            <div
              class="timeline-event-meta"
            >
              <span>
                ${Number(
                  group.file_count || 0
                )}
                Dateien
              </span>

              <span>
                ${Number(
                  group.family_count || 0
                )}
                Familien
              </span>

              <span>
                ${
                  group.preserve_day_folders
                    ? "Tagesordner bleiben erhalten"
                    : "Ohne Tagesunterordner"
                }
              </span>

              <span>
                Bereits verplant
              </span>
            </div>
          `;

          dayList.appendChild(
            card
          );

          continue;
        }

        const key =
          group.card_key || group.day_key
          || "__without_date__";

        const card =
          document.createElement(
            "label"
          );

        card.className =
          "day-card";

        if (!group.has_date) {
          card.classList.add(
            "without-date"
          );
        }

        if (
          selectedDays.has(key)
        ) {
          card.classList.add(
            "selected"
          );
        }

        const checkbox =
          document.createElement(
            "input"
          );

        checkbox.type = "checkbox";
        checkbox.className =
          "day-check";
        checkbox.checked =
          selectedDays.has(key);

        checkbox.addEventListener(
          "change",
          () => {
            if (checkbox.checked) {
              selectedDays.add(key);
            } else {
              selectedDays.delete(key);
            }

            renderDays();
            renderSelection();
          }
        );

        const main =
          document.createElement(
            "span"
          );

        main.className =
          "day-main";

        const name =
          document.createElement(
            "span"
          );

        name.className =
          "day-name";
        name.textContent =
          formatDay(group.day_key) + (group.start_time && (group.start_time !== "00:00" || group.end_time !== "23:59") ? ` · ${group.start_time}–${group.end_time}` : "");
        if (group.reassignment_pending) {
          const marker=document.createElement("span");
          marker.textContent="●"; marker.title="Offene Neu-Zuordnung";
          marker.style.cssText="color:#d99a20;margin-left:6px";
          name.appendChild(marker);
        }

        const metadata =
          document.createElement(
            "span"
          );

        metadata.className =
          "day-meta";

        metadata.innerHTML = `
          <span>
            ${Number(
              group.file_count || 0
            )}
            Dateien
          </span>

          <span>
            ${Number(
              group.family_count || 0
            )}
            Familien
          </span>

          <span>
            ${formatBytes(
              Number(
                group.total_size_bytes
                || 0
              )
            )}
          </span>
        `;

        main.appendChild(name);
        main.appendChild(metadata);

        if (
          group.partially_assigned
        ) {
          const partialNote =
            document.createElement(
              "span"
            );

          partialNote.className =
            "partial-note";

          partialNote.textContent =
            "Ein Teil dieses Tages ist bereits "
            + "einem Ereignis zugeordnet. "
            + "Angezeigt wird nur der freie Bestand.";

          main.appendChild(
            partialNote
          );
        }

        card.appendChild(checkbox);
        card.appendChild(main);

        const reviewCount =
          Number(
            group.review_required_count
            || 0
          );

        const badge =
          document.createElement(
            "span"
          );

        badge.className =
          reviewCount > 0
            ? "badge warning"
            : "badge success metadata-ok";

        badge.textContent =
          reviewCount > 0
            ? (
                reviewCount === 1
                  ? "1 Prüffall"
                  : `${reviewCount} Prüffälle`
              )
            : "Metadaten eindeutig";

        card.appendChild(badge);
        dayList.appendChild(card);
      }
    }


    function selectedDatedGroups() {
      return availableDayGroups().filter(
        group =>
          group.has_date
          && selectedDays.has(
            group.card_key || group.day_key
          )
      );
    }


    function selectedAllGroups() {
      return availableDayGroups().filter(
        group => {
          const key =
            group.card_key || group.day_key
            || "__without_date__";

          return selectedDays.has(key);
        }
      );
    }


    function renderSelection() {
      const groups =
        selectedAllGroups();

      selectionBar.hidden = false;

      const hasSelection = groups.length > 0;
      // 0.16.8: Datum/Uhrzeit sind führend. Eine Tagesauswahl ist nur noch
      // eine bequeme Vorbelegung, aber keine Voraussetzung für neue Ziele.
      newEventButton.disabled = !workspace;
      noEventButton.disabled = !workspace;
      // Eine bestehende Monats-Sammlung braucht weiterhin wenigstens einen
      // ausgewählten Tag, damit der passende Monat eindeutig ist.
      existingNoEventButton.disabled = !workspace || !hasSelection;

      selectionLabel.textContent =
        groups.length === 1
          ? "1 Gruppe ausgewählt"
          : `${groups.length} Gruppen ausgewählt`;

      if (!groups.length) {
        structurePreview.textContent =
          "Noch keine Auswahl.";

        return;
      }

      const dated =
        selectedDatedGroups();

      let preview =
        '<div class="preview-root-title">Arbeitsbestand</div><div class="preview-days">';

      for (const group of groups) {
        const dayLabel = group.has_date ? formatDay(group.day_key) : "Ohne Datum";
        const familyRows = (group.families || []).map(family => {
          const capture = String(family.selected_capture_time || "");
          const stem = family.original_stem || family.family_key || "Dateifamilie";
          const captureText = capture
            ? `${capture.slice(0,10)} ${capture.slice(11,19)}`
            : "Zeit unbekannt";
          return `<div class="preview-family-row"><span class="preview-family-stem" title="${escapeHtml(stem)}">${escapeHtml(stem)}</span><span class="preview-family-time">${escapeHtml(captureText)}</span></div>`;
        }).join("");

        preview +=
          `<details class="preview-day"><summary><span class="preview-day-title">${escapeHtml(dayLabel)}</span><span class="preview-day-count">${Number(group.file_count || 0)} Dateien</span></summary><div class="preview-family-list">${familyRows || '<span class="muted">Keine Familien in dieser Auswahl.</span>'}</div></details>`;
      }

      preview += "</div>";

      if (
        groups.some(
          group => !group.has_date
        )
      ) {
        preview +=
          '<div class="preview-selection-note">Hinweis: Dateien ohne Datum müssen zuerst geprüft werden.</div>';
      }

      if (dated.length) {
        preview +=
          `<div class="preview-selection-note"><strong>Auswahlzeitraum:</strong> ${escapeHtml(dated[0].day_key)} bis ${escapeHtml(dated[dated.length - 1].day_key)}</div>`;
      }

      structurePreview.innerHTML =
        preview;

    }


    function selectedNoEventSegments(includeLocked = true) {
      return [...noEventSegmentList.querySelectorAll("[data-no-event-segment]")]
        .filter(row => includeLocked || row.dataset.locked !== "1")
        .map(row => ({
          day_key: row.querySelector("[data-segment-day]")?.value || row.dataset.dayKey || "",
          start_time: row.querySelector("[data-segment-start]")?.value || row.dataset.startTime || "00:00",
          end_time: row.querySelector("[data-segment-end]")?.value || row.dataset.endTime || "23:59",
          _locked: row.dataset.locked === "1",
          _new: row.dataset.newSegment === "1",
          _existing: row.dataset.existingSegment === "1",
        })).filter(segment => segment.day_key)
        .sort((a,b) => a.day_key.localeCompare(b.day_key) || a.start_time.localeCompare(b.start_time));
    }

    function activeNoEventMonthKey() {
      const raw=String(activeNoEventTarget?.month_key || activeNoEventTarget?.start_datetime || "");
      const m=raw.match(/^(\d{4}-\d{2})/);
      return m ? m[1] : "";
    }

    function daysInMonth(monthKey) {
      const m=String(monthKey||"").match(/^(\d{4})-(\d{2})$/);
      if (!m) return 31;
      return new Date(Number(m[1]), Number(m[2]), 0).getDate();
    }

    function lockedMonthDayControls(dayKey, locked) {
      const monthKey=activeNoEventMonthKey();
      if (!monthKey) return `<label><span>Tag</span><input data-segment-day type="date" value="${escapeHtml(dayKey)}" ${locked?"disabled":""}></label>`;
      const dayPart=/^\d{4}-\d{2}-(\d{2})$/.exec(dayKey||"")?.[1] || "";
      return `<div style="display:grid;grid-template-columns:minmax(118px,.8fr) minmax(86px,.55fr);gap:8px;align-items:end">
        <label><span>Monat/Jahr</span><input type="text" value="${escapeHtml(monthKey.slice(5,7)+"/"+monthKey.slice(0,4))}" disabled></label>
        <label><span>Tag</span><input data-segment-day-number type="number" min="1" max="${daysInMonth(monthKey)}" value="${escapeHtml(dayPart ? String(Number(dayPart)) : "")}" ${locked?"disabled":""}></label>
        <input data-segment-day type="hidden" value="${escapeHtml(dayKey)}">
      </div>`;
    }

    function renderNoEventRangeGeneratorFields() {
      const fixedMonth=activeNoEventMonthKey();
      const startLabel=eventStartDate.closest("label");
      const endLabel=eventEndDate.closest("label");
      noEventRangeFields.querySelectorAll("[data-fixed-range-generator]").forEach(node=>node.remove());
      if (!fixedMonth) {
        startLabel.hidden=false;
        endLabel.hidden=false;
        startLabel.querySelector("span").textContent="Zeitspanne von";
        endLabel.querySelector("span").textContent="Zeitspanne bis";
        return;
      }
      startLabel.hidden=true;
      endLabel.hidden=true;
      const label=fixedMonth.slice(5,7)+"/"+fixedMonth.slice(0,4);
      const max=daysInMonth(fixedMonth);
      const wrapper=document.createElement("div");
      wrapper.dataset.fixedRangeGenerator="1";
      wrapper.className="full-width";
      wrapper.style.cssText="display:grid;grid-template-columns:minmax(130px,.9fr) minmax(90px,.55fr) minmax(130px,.9fr) minmax(90px,.55fr);gap:8px;align-items:end";
      wrapper.innerHTML=`
        <label><span>Monat/Jahr</span><input type="text" value="${escapeHtml(label)}" disabled></label>
        <label><span>Von Tag</span><input data-fixed-range-start-day type="number" min="1" max="${max}"></label>
        <label><span>Monat/Jahr</span><input type="text" value="${escapeHtml(label)}" disabled></label>
        <label><span>Bis Tag</span><input data-fixed-range-end-day type="number" min="1" max="${max}"></label>`;
      noEventRangeFields.appendChild(wrapper);
      const sync=()=>{
        const a=Number(wrapper.querySelector("[data-fixed-range-start-day]")?.value||0);
        const b=Number(wrapper.querySelector("[data-fixed-range-end-day]")?.value||0);
        eventStartDate.value=a>0 ? `${fixedMonth}-${String(Math.min(max,Math.max(1,a))).padStart(2,"0")}` : "";
        eventEndDate.value=b>0 ? `${fixedMonth}-${String(Math.min(max,Math.max(1,b))).padStart(2,"0")}` : "";
      };
      wrapper.querySelectorAll("input[type=number]").forEach(input=>input.addEventListener("input",sync));
    }

    function segmentRowHtml(day) {
      const dayKey = day.day_key || "";
      const start = day.start_time || "00:00";
      const end = day.end_time || "23:59";
      const count = Number(day.family_count || 0);
      const locked = Boolean(day._locked || day.locked);
      const isNew = Boolean(day._new || day.new_segment);
      const isExisting = Boolean(day._existing || day.existing_segment || locked);
      const state = isExisting ? "BESTEHEND" : (isNew ? "NEU" : "");
      const border = isNew ? "border:2px solid currentColor;" : "";
      return `
        <details data-no-event-segment data-day-key="${escapeHtml(dayKey)}" data-start-time="${escapeHtml(start)}" data-end-time="${escapeHtml(end)}" data-locked="${locked?"1":"0"}" data-new-segment="${isNew?"1":"0"}" data-existing-segment="${isExisting?"1":"0"}" class="card" style="padding:8px 10px;${border}">
          <summary style="display:flex;justify-content:space-between;gap:8px;align-items:center;cursor:pointer">
            <strong>${escapeHtml(dayKey || "Neues Segment")}${state ? ` · ${state}` : ""}</strong>
            <span class="muted">${escapeHtml(start)}–${escapeHtml(end)}${count ? ` · ${count} freie Familien` : ""}</span>
          </summary>
          <div style="display:grid;grid-template-columns:minmax(210px,1.7fr) 110px 110px auto;gap:8px;align-items:end;margin-top:8px">
            ${lockedMonthDayControls(dayKey, locked)}
            <label><span>Von</span><input data-segment-start type="time" value="${escapeHtml(start)}" ${locked?"disabled":""}></label>
            <label><span>Bis</span><input data-segment-end type="time" value="${escapeHtml(end)}" ${locked?"disabled":""}></label>
            ${locked ? '<span class="muted">bereits gespeichert</span>' : '<button type="button" class="danger-button" data-remove-no-event-segment>Entfernen</button>'}
          </div>
        </details>`;
    }

    function noEventContiguousRanges() {
      const days=[...new Set(selectedNoEventSegments().map(s=>s.day_key))].sort();
      const ranges=[];
      for (const day of days) {
        if (!ranges.length) { ranges.push([day,day]); continue; }
        const prev=new Date(`${ranges[ranges.length-1][1]}T12:00:00`);
        prev.setDate(prev.getDate()+1);
        const next=`${prev.getFullYear()}-${String(prev.getMonth()+1).padStart(2,"0")}-${String(prev.getDate()).padStart(2,"0")}`;
        if (day===next) ranges[ranges.length-1][1]=day; else ranges.push([day,day]);
      }
      return ranges;
    }

    function formatGermanIsoDate(value) {
      const m=String(value||"").match(/^(\d{4})-(\d{2})-(\d{2})$/);
      return m ? `${m[3]}.${m[2]}.${m[1]}` : String(value||"");
    }

    function renderNoEventRangeBlocks() {
      const ranges=noEventContiguousRanges();
      if (!ranges.length) {
        noEventRangeSummary.innerHTML='<span class="muted">Noch keine Zeitblöcke.</span>';
        return ranges;
      }
      const fixedMonth=activeNoEventMonthKey();
      const rangeField=(value, attr, label)=>{
        if (!fixedMonth) return `<label><span>${label}</span><input ${attr} type="date" value="${escapeHtml(value)}"></label>`;
        const day=String(Number(String(value||"").slice(8,10))||"");
        return `<div style="display:grid;grid-template-columns:minmax(118px,.8fr) minmax(86px,.55fr);gap:8px;align-items:end">
          <label><span>Monat/Jahr</span><input type="text" value="${escapeHtml(fixedMonth.slice(5,7)+"/"+fixedMonth.slice(0,4))}" disabled></label>
          <label><span>${label}</span><input ${attr}-day type="number" min="1" max="${daysInMonth(fixedMonth)}" value="${escapeHtml(day)}"></label>
          <input ${attr} type="hidden" value="${escapeHtml(value)}">
        </div>`;
      };
      noEventRangeSummary.innerHTML = ranges.map(([a,b],index)=>`
        <details class="card" style="padding:7px 9px">
          <summary style="cursor:pointer"><strong>Zeitblock ${index+1}</strong> <span class="muted">· ${escapeHtml(formatGermanIsoDate(a))}${a===b?"":` bis ${escapeHtml(formatGermanIsoDate(b))}`} · ${selectedNoEventSegments().filter(s=>s.day_key>=a && s.day_key<=b).length} Zeitsegmente</span></summary>
          <div class="form-grid" style="margin-top:8px">
            ${rangeField(a,'data-range-block-start','Von')}
            ${rangeField(b,'data-range-block-end','Bis')}
          </div>
          <div style="display:flex;justify-content:flex-end;margin-top:8px"><button type="button" data-extend-no-event-block>Fehlende Tagessegmente ergänzen</button></div>
        </details>`).join("");
      if (fixedMonth) {
        noEventRangeSummary.querySelectorAll('[data-range-block-start-day],[data-range-block-end-day]').forEach(input=>{
          input.oninput=()=>{
            const attr=input.hasAttribute('data-range-block-start-day')?'data-range-block-start':'data-range-block-end';
            const hidden=input.closest('div')?.querySelector(`[${attr}]`);
            const n=Math.max(1,Math.min(daysInMonth(fixedMonth),Number(input.value||0)));
            if (hidden && Number(input.value||0)>0) hidden.value=`${fixedMonth}-${String(n).padStart(2,'0')}`;
          };
        });
      }
      noEventRangeSummary.querySelectorAll("[data-extend-no-event-block]").forEach(button => {
        button.onclick = () => {
          const box=button.closest("details");
          const start=box?.querySelector("[data-range-block-start]")?.value || "";
          const end=box?.querySelector("[data-range-block-end]")?.value || "";
          if (!/^\d{4}-\d{2}-\d{2}$/.test(start) || !/^\d{4}-\d{2}-\d{2}$/.test(end) || end < start) return;
          const existing=new Map(selectedNoEventSegments(true).map(seg=>[`${seg.day_key}|${seg.start_time}|${seg.end_time}`,seg]));
          for (const dayKey of daysInRange(start,end)) {
            if (![...existing.values()].some(seg=>seg.day_key===dayKey)) existing.set(`${dayKey}|00:00|23:59`,{day_key:dayKey,start_time:"00:00",end_time:"23:59",_new:true});
          }
          renderNoEventSegmentEditor([...existing.values()]);
          syncNoEventRangeDisplayFromSegments();
        };
      });
      return ranges;
    }

    function syncNoEventRangeDisplayFromSegments({updateGenerator=true}={}) {
      if (!["no_event","existing_no_event"].includes(dialogMode)) return;
      const ranges=renderNoEventRangeBlocks();
      if (!updateGenerator) return;
      if (ranges.length===1) {
        eventStartDate.value=ranges[0][0];
        eventEndDate.value=ranges[0][1];
      } else {
        // Bei mehreren Blöcken bleiben die Generatorfelder bewusst leer.
        // So wird keine künstlich durchgehende Zeitspanne suggeriert.
        eventStartDate.value="";
        eventEndDate.value="";
      }
    }

    function bindNoEventSegmentRows() {
      noEventSegmentList.querySelectorAll("[data-remove-no-event-segment]").forEach(button => {
        button.onclick = event => {
          event.preventDefault();
          button.closest("[data-no-event-segment]")?.remove();
          syncNoEventRangeDisplayFromSegments();
        };
      });
      noEventSegmentList.querySelectorAll("[data-segment-day-number]").forEach(input => {
        input.oninput = () => {
          const month=activeNoEventMonthKey();
          const hidden=input.closest("[data-no-event-segment]")?.querySelector("[data-segment-day]");
          const n=Math.max(1,Math.min(daysInMonth(month),Number(input.value||0)));
          if (month && hidden && Number(input.value||0)>0) hidden.value=`${month}-${String(n).padStart(2,"0")}`;
        };
        input.onchange = () => syncNoEventRangeDisplayFromSegments();
      });
      noEventSegmentList.querySelectorAll("[data-segment-day],[data-segment-start],[data-segment-end]").forEach(input => {
        input.onchange = () => syncNoEventRangeDisplayFromSegments();
      });
    }

    function renderNoEventSegmentEditor(days) {
      noEventSegmentList.innerHTML = (days || []).map(day => segmentRowHtml(day)).join("");
      bindNoEventSegmentRows();
      if (["no_event","existing_no_event"].includes(dialogMode)) renderNoEventRangeBlocks();
      scheduleDialogPreview();
    }

    function daysInRange(start, end) {
      if (!/^\d{4}-\d{2}-\d{2}$/.test(start || "") || !/^\d{4}-\d{2}-\d{2}$/.test(end || "") || end < start) return [];
      const out=[];
      let d=new Date(`${start}T12:00:00`);
      const last=new Date(`${end}T12:00:00`);
      while (d <= last && out.length < 370) {
        out.push(`${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")}`);
        d.setDate(d.getDate()+1);
      }
      return out;
    }

    function syncNoEventSegmentsFromRange() {
      if (!["no_event","existing_no_event"].includes(dialogMode)) return;
      const existing = new Map(selectedNoEventSegments(true).map(seg => [`${seg.day_key}|${seg.start_time}|${seg.end_time}`, seg]));
      for (const dayKey of daysInRange(eventStartDate.value, eventEndDate.value)) {
        const alreadyForDay=[...existing.values()].some(seg=>seg.day_key===dayKey);
        if (!alreadyForDay) existing.set(`${dayKey}|00:00|23:59`, {day_key:dayKey,start_time:"00:00",end_time:"23:59",_new:true});
      }
      const groups = new Map((workspace?.day_groups || workspace?.days || []).map(day => [day.day_key, day]));
      renderNoEventSegmentEditor([...existing.values()].sort((a,b)=>a.day_key.localeCompare(b.day_key)||a.start_time.localeCompare(b.start_time)).map(seg => ({...seg, family_count:seg._locked?0:Number(groups.get(seg.day_key)?.family_count||0)})));
      syncNoEventRangeDisplayFromSegments();
    }

    function monthKeysForNoEventDialog() {
      const values=selectedNoEventSegments(true).map(seg=>String(seg.day_key||"").slice(0,7)).filter(Boolean);
      for (const value of [eventStartDate.value,eventEndDate.value]) if (/^\d{4}-\d{2}-\d{2}$/.test(value||"")) values.push(value.slice(0,7));
      return [...new Set(values)];
    }

    function activateNoEventTarget(target) {
      activeNoEventTarget=target || null;
      if (!activeNoEventTarget) {
        dialogTitle.textContent="Als „Ohne Ereignis“ zuordnen";
        return;
      }
      dialogTitle.textContent="„Ohne Ereignis“ fortführen";
      const currentNew=selectedNoEventSegments(false).filter(seg=>!seg._existing).map(seg=>({...seg,_new:true}));
      const targetLocked=String(activeNoEventTarget.status||"") !== "planned";
      const existing=(activeNoEventTarget.segments||[]).map(seg=>({
        day_key:seg.day_key,start_time:seg.start_time,end_time:seg.end_time,
        _locked:targetLocked,_existing:true
      }));
      const keys=new Set(existing.map(seg=>`${seg.day_key}|${seg.start_time}|${seg.end_time}`));
      const merged=[...existing,...currentNew.filter(seg=>!keys.has(`${seg.day_key}|${seg.start_time}|${seg.end_time}`))];
      renderNoEventSegmentEditor(merged);
      syncNoEventRangeDisplayFromSegments();
    }

    async function autoAttachExistingNoEventCollection() {
      if (dialogMode !== "no_event" || !jobSelect.value) return;
      const months=monthKeysForNoEventDialog();
      if (months.length > 1) {
        activeNoEventTarget=null;
        existingNoEventTargetRow.hidden=true;
        return;
      }
      try {
        const query=months.length===1 ? `?months=${encodeURIComponent(months[0])}` : "";
        const targetData=await getJson(`/api/jobs/${encodeURIComponent(jobSelect.value)}/no-event/targets${query}`);
        noEventTargetCache=targetData.targets||[];
      } catch (_) { noEventTargetCache=[]; }

      if (months.length===1) {
        const target=noEventTargetCache[0]||null;
        if (!target) {
          activeNoEventTarget=null;
          existingNoEventTargetRow.hidden=true;
          dialogTitle.textContent="Als „Ohne Ereignis“ zuordnen";
          return;
        }
        existingNoEventTargetRow.hidden=false;
        existingNoEventTarget.innerHTML=`<option value="${escapeHtml(target.id)}">${escapeHtml(String(target.month_key||"").slice(5,7))} – Ohne Ereignis · ${escapeHtml(workspaceStatusLabel(target.status))}</option>`;
        existingNoEventTarget.disabled=true;
        activateNoEventTarget(target);
        return;
      }

      // Ohne vorausgewählten Tag kann der Nutzer jede aktive Monats-Sammlung
      // öffnen oder mit neuen Segmenten zunächst eine neue Monatsauswahl erzeugen.
      existingNoEventTargetRow.hidden = noEventTargetCache.length===0;
      existingNoEventTarget.disabled=false;
      existingNoEventTarget.innerHTML='<option value="">Neue Monats-Sammlung / noch kein Ziel</option>' + noEventTargetCache.map(target=>
        `<option value="${escapeHtml(target.id)}">${escapeHtml(String(target.month_key||""))} · Ohne Ereignis · ${escapeHtml(workspaceStatusLabel(target.status))}</option>`
      ).join("");
      activateNoEventTarget(null);
    }

    async function handleNoEventRangeChange() {
      const start=eventStartDate.value || "";
      const end=eventEndDate.value || "";
      if (!/^\d{4}-\d{2}-\d{2}$/.test(start) || !/^\d{4}-\d{2}-\d{2}$/.test(end) || end < start) {
        // Ein noch unvollständiges Datum darf nicht durch die Segment-Synchronisierung
        // wieder geleert werden.
        return;
      }
      syncNoEventSegmentsFromRange();
      await autoAttachExistingNoEventCollection();
    }

    function applyAutomaticFreeTimeSuggestion(dated) {
      if (!dated.length) return;
      const ordered=[...dated].sort((a,b)=>String(a.start_datetime).localeCompare(String(b.start_datetime)));
      eventStartTime.value=ordered[0].start_time || "00:00";
      eventEndTime.value=ordered[ordered.length-1].end_time || "23:59";
      useTimeRange.checked=true;
      timeFields.hidden=false;
      childEventName.required=false;
    }

    async function openTaskReassignment(eventId) {
      const jobId = jobSelect.value;
      if (!jobId) throw new Error("Keine Sicherung ausgewählt.");
      // 0.24.1: one canonical reassignment dialog lives on the Ereignisse page.
      // It sends exact persisted segments and exposes the complete target model.
      location.href = `/events?job=${encodeURIComponent(jobId)}&task=reassign:${encodeURIComponent(eventId)}`;
    }

    taskReassignClose?.addEventListener("click",()=>taskReassignDialog.close());

    function plannedParentCandidates(dated) {
      if (!workspace || !dated.length) return [];
      return (workspace.events || []).filter(event => event.event_level === "parent" && event.event_kind === "event" && (dated[0].archive_change_request_id ? event.status === "archived" : ["planned","applied"].includes(event.status)) && dated.some(d =>
        Math.abs(Date.parse(d.start_datetime)-Date.parse(event.end_datetime)-1000)<1 || Math.abs(Date.parse(event.start_datetime)-Date.parse(d.end_datetime)-1000)<1));
    }

    function nextMinute(value) {
      const match=String(value||"").match(/(\d{2}):(\d{2})/);
      if (!match) return "00:00";
      const minutes=Math.min(23*60+59, Number(match[1])*60+Number(match[2])+1);
      return `${String(Math.floor(minutes/60)).padStart(2,"0")}:${String(minutes%60).padStart(2,"0")}`;
    }

    function applyExistingParentChoice() {
      const id=existingParentEvent?.value || "";
      const parent=(workspace?.events||[]).find(event=>event.id===id);
      if (!parent) {
        eventName.disabled=false;
        return;
      }
      eventName.value=parent.name || "";
      eventName.disabled=true;
      useTimeRange.checked=true;
      timeFields.hidden=false;
      childEventName.required=false;
      applyAutomaticFreeTimeSuggestion(selectedDatedGroups());
      childEventName.required=false;
    }

    async function openEventDialog(mode) {
      dialogMode = mode;
      const dated = selectedDatedGroups();
      const noEvent = mode === "no_event" || mode === "existing_no_event";
      const existingNoEvent = mode === "existing_no_event";
      activeNoEventTarget = null;
      const parentCandidates = noEvent ? [] : plannedParentCandidates(dated);
      existingParentRow.hidden = noEvent || parentCandidates.length === 0;
      const startLabel=eventStartDate.closest("label");
      const endLabel=eventEndDate.closest("label");
      const useTimeLabel=useTimeRange.closest("label");
      const formGrid=document.querySelector("#event-form .form-grid");
      if (noEvent) {
        noEventRangeFields.append(startLabel, endLabel);
      } else {
        formGrid.insertBefore(startLabel, useTimeLabel);
        formGrid.insertBefore(endLabel, useTimeLabel);
      }
      if (!existingParentRow.hidden) {
        existingParentEvent.innerHTML = `<option value="">Neues Oberereignis anlegen</option>` + parentCandidates.map(parent => `<option value="${escapeHtml(parent.id)}">${escapeHtml(parent.name)} · ${escapeHtml(String(parent.start_datetime||"").slice(0,10))}</option>`).join("");
        existingParentEvent.value = "";
      } else {
        existingParentEvent.innerHTML = "";
      }
      eventName.value = noEvent ? "Ohne Ereignis" : "";
      eventName.disabled = noEvent;
      dialogTitle.textContent = existingNoEvent ? "Zu bestehendem „Ohne Ereignis“ hinzufügen" : (noEvent ? "Als „Ohne Ereignis“ zuordnen" : "Ereignis erstellen");
      eventStartDate.value = dated.length ? dated[0].day_key : "";
      eventEndDate.value = dated.length ? dated[dated.length - 1].day_key : "";
      useTimeRange.checked = false;
      timeFields.hidden = true;
      childEventName.value = "";
      childEventName.required = false;
      eventStartTime.value = "00:00";
      eventEndTime.value = "23:59";
      preserveDayFolders.checked = false;
      preserveDayFolders.disabled = false;

      noEventSegmentEditor.hidden = !noEvent;
      existingNoEventTargetRow.hidden = !existingNoEvent;
      if (existingNoEvent) {
        const months=[...new Set(dated.map(group=>String(group.day_key||"").slice(0,7)).filter(Boolean))];
        noEventTargetCache = [];
        if (months.length) {
          try {
            const targetData=await getJson(`/api/jobs/${encodeURIComponent(jobSelect.value)}/no-event/targets?months=${encodeURIComponent(months.join(","))}`);
            noEventTargetCache=targetData.targets||[];
          } catch (_) {}
        }
        existingNoEventTarget.innerHTML=noEventTargetCache.map(e=>`<option value="${escapeHtml(e.id)}">${escapeHtml(String(e.month_key||"").slice(5,7))} – Ohne Ereignis · ${escapeHtml(workspaceStatusLabel(e.status))}${e.same_job?"":" · andere Sicherung"}</option>`).join("");
        if (!noEventTargetCache.length) {
          existingNoEventTarget.innerHTML='<option value="">Keine passende Monats-Sammlung vorhanden</option>';
        }
      }
      eventStartDate.closest("label").hidden = false;
      eventEndDate.closest("label").hidden = false;
      eventStartDate.closest("label").querySelector("span").textContent = noEvent ? "Zeitspanne von" : "Beginn";
      eventEndDate.closest("label").querySelector("span").textContent = noEvent ? "Zeitspanne bis" : "Ende";
      useTimeRange.closest("label").hidden = noEvent;
      preserveDayFolders.closest("label").hidden = false;
      if (noEvent) {
        if (noEventRangeDetails) noEventRangeDetails.open=false;
        if (noEventRangeGenerator) noEventRangeGenerator.hidden=true;
        renderNoEventSegmentEditor(dated.map(day=>({...day,_new:true})));

        await autoAttachExistingNoEventCollection();
      } else {
        applyAutomaticFreeTimeSuggestion(dated);
        if (parentCandidates.length) applyExistingParentChoice();
      }

      dialogPreview.textContent = "Vorschau wird vorbereitet …";
      dialogPreview.hidden = true;
      calculatePreviewButton.textContent = "Vorschau einblenden";
      saveResult.hidden = true;
      saveResult.textContent = "";
      eventDialog.showModal();
      scheduleDialogPreview();
    }


    function collectEventPayload() {
      const base = {
        event_kind: ["no_event","existing_no_event"].includes(dialogMode) ? "no_event" : "event",
        event_name: eventName.value.trim(),
        start_date: eventStartDate.value,
        end_date: eventEndDate.value,
        uses_time_range: useTimeRange.checked,
        child_event_name: childEventName.value.trim(),
        selected_intervals: selectedDatedGroups().map(g=>({start_datetime:g.start_datetime,end_datetime:g.end_datetime})),
        start_time: eventStartTime.value,
        end_time: eventEndTime.value,
        preserve_day_folders: preserveDayFolders.checked,
        selected_day_keys: selectedDatedGroups().map(group => group.day_key),
        existing_parent_event_id: (!["no_event","existing_no_event"].includes(dialogMode) ? (existingParentEvent?.value || null) : null)
      };
      if (["no_event","existing_no_event"].includes(dialogMode)) {
        const allSegments = selectedNoEventSegments(true);
        const newSegments = selectedNoEventSegments(false);
        base.no_event_segments = activeNoEventTarget ? newSegments : allSegments;
        base.display_no_event_segments = allSegments;
        base.uses_time_range = false;
        base.preserve_day_folders = preserveDayFolders.checked;
        if (allSegments.length) {
          base.start_date = allSegments[0].day_key;
          base.end_date = allSegments[allSegments.length-1].day_key;
        }
      }
      return base;
    }


    let dialogPreviewTimer = null;
    function scheduleDialogPreview() {
      if (!eventDialog.open) return;
      clearTimeout(dialogPreviewTimer);
      dialogPreviewTimer = setTimeout(() => {
        calculateDialogPreview().catch(error => { dialogPreview.textContent = error.message; });
      }, 120);
    }

    async function calculateDialogPreview() {
      const jobId = jobSelect.value;

      if (!jobId) {
        dialogPreview.textContent =
          "Keine Sicherung ausgewählt.";
        return;
      }

      const payload =
        collectEventPayload();

      if (dialogMode === "existing_no_event" || activeNoEventTarget) {
        const all=payload.display_no_event_segments||payload.no_event_segments||[];
        const newKeys=new Set((payload.no_event_segments||[]).map(segment=>`${segment.day_key}|${segment.start_time}|${segment.end_time}`));
        const folder=String(activeNoEventTarget?.folder_name||`${String(all[0]?.day_key||"").slice(5,7)} - Ohne Ereignis`);
        const year=String(all[0]?.day_key||activeNoEventTarget?.month_key||"").slice(0,4)||"Jahr";
        const preserve=Boolean(payload.preserve_day_folders || activeNoEventTarget?.preserve_day_folders);
        const lines=[year,`└── ${folder}`];
        if (preserve) {
          for (const day of [...new Set(all.map(s=>s.day_key))].sort()) {
            lines.push(`    ├── ${day}`,`    │   ├── Alle`,`    │   ├── Sortiert`,`    │   └── Export`);
          }
        } else {
          lines.push(`    ├── Alle`,`    ├── Sortiert`,`    └── Export`);
        }
        lines.push("",`Fortführung · ${String(activeNoEventTarget?.status||"")}`);
        for (const segment of all) lines.push(`${segment.day_key} · ${segment.start_time}–${segment.end_time}${newKeys.has(`${segment.day_key}|${segment.start_time}|${segment.end_time}`)?" · NEU":" · bestehend"}`);
        dialogPreview.textContent=lines.join("\n");
        return;
      }

      dialogPreview.textContent =
        "Vorschau wird berechnet …";

      calculatePreviewButton.disabled = true;

      try {
        const result = await postJson(
          `/api/jobs/${
            encodeURIComponent(jobId)
          }/event-preview`,
          payload
        );

        dialogPreview.textContent =
          result.preview.structure_text;

      } catch (error) {
        dialogPreview.textContent =
          error.message;

      } finally {
        calculatePreviewButton.disabled =
          false;
      }
    }


    async function saveEvent() {
      const jobId = jobSelect.value;

      if (!jobId) {
        saveResult.hidden = false;
        saveResult.textContent =
          "Keine Sicherung ausgewählt.";
        return;
      }

      saveEventButton.disabled = true;
      calculatePreviewButton.disabled = true;

      saveResult.hidden = false;
      saveResult.textContent =
        "Ereignis wird gespeichert …";

      try {
        let result;
        const selected=selectedDatedGroups();
        const archiveIds=[...new Set(selected.map(g=>g.archive_change_request_id).filter(Boolean))];
        if (archiveIds.length) {
          if (archiveIds.length!==1 || selected.some(g=>g.archive_change_request_id!==archiveIds[0])) throw new Error("Bitte die freien Bereiche eines Archivauftrags getrennt auswählen.");
          const payload=collectEventPayload();
          const targetId=activeNoEventTarget?.id || existingNoEventTarget.value;
          const noEvent=payload.event_kind==='no_event';
          const normalTarget=existingParentEvent?.value;
          await postJson(`/api/change-requests/${encodeURIComponent(archiveIds[0])}/reassignments`,{
            family_ids:selected.flatMap(g=>g.family_ids),
            target_mode:noEvent ? (targetId?'existing_no_event':'new_no_event') : (normalTarget?'existing_event':'new_event'),
            target_event_id:noEvent ? targetId : normalTarget,
            new_event_name:payload.event_name
          });
          selectedDays.clear(); await loadWorkspace(); eventDialog.close();
          setStatus("Neu zugeordnet. Den manuellen Archiv-Änderungsplan unter Ereignisse prüfen und bestätigen.");
          return;
        }
        if (dialogMode === "existing_no_event" || activeNoEventTarget) {
          const payload=collectEventPayload();
          const targetId=activeNoEventTarget?.id || existingNoEventTarget.value;
          if (!targetId) throw new Error("Für diesen Monat wurde keine bestehende „Ohne Ereignis“-Sammlung gefunden.");
          if (!(payload.no_event_segments||[]).length) throw new Error("Es gibt keine neuen Tagessegmente zum Hinzufügen.");
          result = await postJson(`/api/jobs/${encodeURIComponent(jobId)}/no-event/assign-existing`, {
            target_event_id: targetId,
            segments: payload.no_event_segments || []
          });
          saveResult.textContent = `Fortgeführt: ${result.assigned_family_count} Familien`;
        } else {
          result = await postJson(
            `/api/jobs/${encodeURIComponent(jobId)}/events`,
            collectEventPayload()
          );
          saveResult.textContent = `Gespeichert: ${result.parent_event.folder_name} · ${result.assigned_family_count} Familien`;
          lastSavedEvent = result.parent_event;
        }

        applySavedEventStatus.textContent = "";

        selectedDays.clear();

        await loadWorkspace();

        eventDialog.close();

      } catch (error) {
        saveResult.textContent =
          error.message;

        if (
          String(error.message).includes(
            "bereits"
          )
          || String(error.message).includes(
            "nicht mehr aktuell"
          )
        ) {
          await loadWorkspace();
        }

      } finally {
        saveEventButton.disabled = false;
        calculatePreviewButton.disabled =
          false;
      }
    }



    jobSelect.addEventListener(
      "change",
      () => {
        loadWorkspace().catch(
          error => setStatus(
            error.message,
            true
          )
        );
      }
    );

    selectAllButton.addEventListener(
      "click",
      () => {
        selectedDays.clear();

        for (
          const group
          of availableDayGroups()
        ) {
          if (group.has_date) {
            selectedDays.add(
              group.card_key || group.day_key
            );
          }
        }

        renderDays();
        renderSelection();
      }
    );

    clearSelectionButton.addEventListener(
      "click",
      () => {
        selectedDays.clear();
        renderDays();
        renderSelection();
      }
    );

    newEventButton.addEventListener(
      "click",
      () => openEventDialog("event")
    );

    existingNoEventButton?.addEventListener("click", () => openEventDialog("no_event"));

    noEventButton.addEventListener(
      "click",
      () => openEventDialog("no_event")
    );

    useTimeRange.addEventListener(
      "change",
      () => {
        timeFields.hidden =
          !useTimeRange.checked;

        childEventName.required = false;

        if (
          useTimeRange.checked
          && !childEventName.value
        ) {
          childEventName.focus();
        }
      }
    );

    existingParentEvent?.addEventListener("change", applyExistingParentChoice);
    addNoEventRangeBlock?.addEventListener("click", event => {
      event.preventDefault();
      event.stopPropagation();
      if (noEventRangeDetails) noEventRangeDetails.open=true;
      if (noEventRangeGenerator) noEventRangeGenerator.hidden=false;
      eventStartDate.value="";
      eventEndDate.value="";
      renderNoEventRangeGeneratorFields();
      const fixedStart=noEventRangeFields.querySelector("[data-fixed-range-start-day]");
      (fixedStart || eventStartDate).focus();
    });
    cancelNoEventRangeBlock?.addEventListener("click", () => {
      if (noEventRangeGenerator) noEventRangeGenerator.hidden=true;
      eventStartDate.value="";
      eventEndDate.value="";
      noEventRangeFields.querySelectorAll("[data-fixed-range-generator]").forEach(node=>node.remove());
    });
    applyNoEventRangeBlock?.addEventListener("click", async () => {
      const start=eventStartDate.value || "";
      const end=eventEndDate.value || "";
      if (!/^\d{4}-\d{2}-\d{2}$/.test(start) || !/^\d{4}-\d{2}-\d{2}$/.test(end) || end < start) {
        dialogPreview.textContent="Bitte einen gültigen Zeitraum für den neuen Zeitblock eingeben.";
        return;
      }
      syncNoEventSegmentsFromRange();
      await autoAttachExistingNoEventCollection();
      if (noEventRangeGenerator) noEventRangeGenerator.hidden=true;
      eventStartDate.value="";
      eventEndDate.value="";
    });

    existingNoEventTarget?.addEventListener("change", () => {
      const target=noEventTargetCache.find(item=>String(item.id)===String(existingNoEventTarget.value));
      if (target) {
        activateNoEventTarget(target);
        return;
      }
      // Ein bewusster Wechsel auf „Neue Monats-Sammlung“ muss den aus der
      // zuvor gewählten Sammlung übernommenen UI-Zustand vollständig lösen.
      // Zeitblöcke sind nur aus den sichtbaren Tagessegmenten abgeleitet.
      activeNoEventTarget=null;
      dialogTitle.textContent="Als „Ohne Ereignis“ zuordnen";
      renderNoEventSegmentEditor([]);
      syncNoEventRangeDisplayFromSegments();
      eventStartDate.value="";
      eventEndDate.value="";
    });

    document.getElementById("add-no-event-segment")?.addEventListener("click", () => {
      // Beim manuellen Ergänzen einer bestehenden Monats-Sammlung darf die
      // Ziel-Autoerkennung den gerade erzeugten leeren Editor nicht sofort
      // wieder durch die gespeicherten Segmente ersetzen.
      const rows = selectedNoEventSegments(true);
      rows.push({day_key:"",start_time:"00:00",end_time:"23:59",_new:true});
      renderNoEventSegmentEditor(rows);
      const items=noEventSegmentList.querySelectorAll("[data-no-event-segment]");
      const last=items[items.length-1];
      last?.setAttribute("open", "");
      last?.querySelector("[data-segment-day]")?.focus();
    });

    calculatePreviewButton.addEventListener("click", () => {
      const willShow = dialogPreview.hidden;
      dialogPreview.hidden = !willShow;
      calculatePreviewButton.textContent = willShow ? "Vorschau ausblenden" : "Vorschau einblenden";
      if (willShow) scheduleDialogPreview();
    });

    eventForm?.addEventListener("input", event => {
      if (event.target?.id === "calculate-preview-button") return;
      scheduleDialogPreview();
    });
    eventForm?.addEventListener("change", () => scheduleDialogPreview());

    async function applyPlannedEvents() {
      const jobId = jobSelect.value;
      const selectedIds = [...plannedEventSelection.querySelectorAll("input[data-planned-event]:checked")].map(input => input.dataset.plannedEvent);
      if (!jobId || !selectedIds.length) throw new Error("Keine geplanten Ereignisse ausgewählt.");
      applySavedEventButton.disabled = true;
      applySavedEventStatus.textContent = "Alle ausgewählten Pläne werden geprüft …";
      const plans = [];
      for (const eventId of selectedIds) {
        const plan = await getJson(`/api/jobs/${encodeURIComponent(jobId)}/events/${encodeURIComponent(eventId)}/sort-plan`);
        if (!plan.summary?.ready) throw new Error(`${plan.event?.name || eventId}: ${plan.summary?.blocker_count || 1} Blocker.`);
        plans.push({eventId, plan});
      }
      const familyCount = plans.reduce((sum,item)=>sum+Number(item.plan.summary.family_count||0),0);
      const fileCount = plans.reduce((sum,item)=>sum+Number(item.plan.summary.file_count||0),0);
      const ok = window.confirm(`${plans.length} geplante Ereignisse mit ${familyCount} Familien und ${fileCount} Dateien jetzt anwenden?`);
      if (!ok) { applySavedEventButton.disabled = false; applySavedEventStatus.textContent = "Nicht angewendet."; return; }
      for (let index=0; index<plans.length; index+=1) {
        const {eventId, plan} = plans[index];
        applySavedEventStatus.textContent = `Ereignis ${index+1} von ${plans.length} wird angewendet …`;
        const response = await postJson(`/api/jobs/${encodeURIComponent(jobId)}/events/${encodeURIComponent(eventId)}/apply-sort`, {plan_token: plan.plan_token, confirmation_phrase: plan.apply_confirmation_phrase});
        let run = response.run;
        while (!run.terminal) {
          applySavedEventStatus.textContent = `Ereignis ${index+1} von ${plans.length} · ${run.progress_percent || 0} %`;
          await new Promise(resolve => setTimeout(resolve, 800));
          run = await getJson(`/api/jobs/${encodeURIComponent(jobId)}/sort-runs/${encodeURIComponent(run.id)}`);
        }
        if (run.status !== "applied") throw new Error(run.error_message || `Ereignis ${index+1} wurde nicht abgeschlossen.`);
      }
      applySavedEventStatus.textContent = "Alle ausgewählten Ereignisse wurden vollständig angewendet und geprüft.";
      await loadWorkspace();
    }

    applySavedEventButton.addEventListener("click", () => {
      applyPlannedEvents().catch(error => {
        applySavedEventStatus.textContent = error.message;
        applySavedEventButton.disabled = false;
      });
    });

    saveEventButton.addEventListener(
      "click",
      () => {
        saveEvent().catch(
          error => {
            saveResult.hidden = false;
            saveResult.textContent =
              error.message;
          }
        );
      }
    );

    closeDialogButton.addEventListener(
      "click",
      () => eventDialog.close()
    );

    previewToggle.addEventListener(
      "click",
      () => {
        const isOpen =
          previewBody.classList.toggle(
            "open"
          );

        previewToggle.setAttribute(
          "aria-expanded",
          String(isOpen)
        );

        previewToggle.textContent =
          isOpen
            ? "Zielstruktur ausblenden"
            : "Zielstruktur anzeigen";
      }
    );

    eventSuggestionList.addEventListener("click", async event => {
      const button = event.target.closest(".accept-suggestion");
      if (!button) return;
      button.disabled = true;
      eventSuggestionStatus.textContent = "Zuordnung wird geprüft und geplant …";
      try {
        const result = await postJson(
          `/api/jobs/${encodeURIComponent(jobSelect.value)}/event-suggestions/accept`,
          {
            family_ids: JSON.parse(button.dataset.familyIds || "[]"),
            target_event_id: button.dataset.targetEventId
          }
        );
        eventSuggestionStatus.textContent = `${result.name} wurde als geplante Änderung angelegt.`;
        await loadWorkspace();
      } catch (error) {
        eventSuggestionStatus.textContent = error.message;
        button.disabled = false;
      }
    });

    loadJobs().then(async () => {
      const params = new URLSearchParams(location.search);
      const task = params.get("task") || "";
      if (task.startsWith("reassign:")) {
        await openTaskReassignment(task.slice("reassign:".length));
      } else if (task.startsWith("planned:")) {
        const wanted=task.slice("planned:".length);
        let matched=false;
        plannedEventSelection?.querySelectorAll("input[data-planned-event]").forEach(input=>{
          input.checked = input.dataset.plannedEvent === wanted;
          if (input.checked) matched=true;
        });
        if (matched) {
          postSaveAction.hidden = false;
          postSaveTitle.textContent = "Dieses geplante Ereignis anwenden";
          postSaveDetail.textContent = "Die Aufgabe hat genau dieses Ereignis vorausgewählt; andere geplante Ereignisse bleiben unangetastet.";
          applySavedEventButton.textContent = "Dieses Ereignis anwenden";
          applySavedEventStatus.textContent = "Offene Aufgabe: Dieses geplante Ereignis muss noch angewendet werden.";
        } else {
          applySavedEventStatus.textContent = "Das verknüpfte geplante Ereignis ist nicht mehr offen.";
        }
        postSaveAction?.scrollIntoView({behavior:"smooth",block:"center"});
      } else if (task === "free") {
        document.querySelector(".day-groups")?.scrollIntoView({behavior:"smooth",block:"start"});
        setStatus("Offene Aufgabe: In dieser Sicherung gibt es noch nicht zugeordnete Familien.");
      }
    }).catch(
      error => setStatus(
        error.message,
        true
      )
    );
  </script>
</body>
</html>
"""
