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
      font-family: Futura, "Helvetica Neue", Helvetica, Arial, sans-serif;
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

    .summary > .card { min-width:0; overflow:hidden; }
    .summary > .card > .muted { display:block; min-width:0; max-width:100%; font-size:clamp(.63rem, .84vw, .85rem); line-height:1.2; white-space:normal!important; overflow-wrap:anywhere; hyphens:auto; }
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
      user-select: none;
      -webkit-user-select: none;
    }

    .day-card.selected {
      border-color: var(--accent);
      background: #202a3a;
    }

    .day-card.without-date {
      border-color: var(--warning);
      background:
        color-mix(
          in srgb,
          var(--warning) 12%,
          var(--surface)
        );
    }

    .day-card.review-card {
      grid-template-columns: minmax(0, 1fr) auto;
      cursor: pointer;
    }

    .day-card.review-card:hover {
      border-color: var(--warning);
      background:
        color-mix(
          in srgb,
          var(--warning) 18%,
          var(--surface)
        );
    }

    .day-card.review-card:focus-visible {
      outline: 3px solid var(--warning);
      outline-offset: 3px;
    }

    .review-card-hint {
      display: block;
      margin-top: 7px;
      color: var(--muted);
      font-size: 0.84rem;
    }

    .metadata-review-preview {
      display: grid;
      gap: 12px;
    }

    .metadata-review-preview .primary {
      width: fit-content;
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

    .timeline-event-statuses {
      display: grid;
      justify-items: end;
      gap: 6px;
      flex: 0 0 auto;
    }

    .suggestions-panel { margin:0 0 18px; width:100%; box-sizing:border-box; border-color:#6ea8ff; }
    .suggestion-list { display:grid; gap:10px; margin-top:12px; }
    .suggestion-card { border:1px solid var(--border); border-radius:14px; padding:14px; background:var(--panel-soft); }
    .suggestion-head { display:flex; justify-content:space-between; align-items:flex-start; gap:12px; }
    .suggestion-title { font-weight:750; }
    .suggestion-meta { display:flex; flex-wrap:wrap; gap:8px 14px; margin-top:8px; color:var(--muted); font-size:.92rem; }
    .suggestion-actions { display:flex; flex-wrap:wrap; gap:10px; margin-top:12px; }
    .suggestion-files { margin-top:10px; }
    .suggestion-files code { white-space:normal; overflow-wrap:anywhere; }
    .backup-filter { min-width:min(620px,100%); }
    .backup-filter > summary { display:grid;grid-template-columns:auto auto minmax(0,1fr);align-items:center;gap:9px;padding:11px 14px;border:1px solid var(--border);border-radius:12px;background:var(--panel-soft);cursor:pointer; }
    .backup-filter > summary::marker { content:""; }
    .backup-filter-icon{width:19px;height:19px;display:grid;place-items:center;color:var(--text)}
    .backup-filter-icon svg{width:19px;height:19px;fill:none;stroke:currentColor;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round}
    .backup-filter-label { color:var(--muted);font-weight:500; }
    .backup-filter-value { font-weight:750;justify-self:end;text-align:right;min-width:0; }
    .backup-filter-panel { margin-top:8px;padding:12px;border:1px solid var(--border);border-radius:12px;background:var(--surface);display:grid;gap:10px; }
    .backup-filter-list { display:grid;gap:7px; }
    .backup-filter-choice { display:grid;grid-template-columns:auto minmax(0,1fr) auto;align-items:center;gap:9px;padding:8px 9px;border:1px solid var(--border);border-radius:10px;background:var(--panel-soft); }
    .backup-filter-choice > span:nth-child(2) { min-width:0; }
    .backup-filter-choice strong { display:block;min-width:0;white-space:normal;overflow-wrap:anywhere;word-break:break-word; }
    .backup-filter-choice small { color:var(--muted);white-space:normal;overflow-wrap:anywhere; }
    .backup-filter-actions { display:flex;gap:8px;flex-wrap:wrap; }
    .backup-filter-archived > summary { color:var(--muted);font-weight:650;cursor:pointer; }

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
    #event-dialog{inline-size:min(700px,calc(100dvw - 32px))}
    .event-boundaries{display:grid;grid-template-columns:minmax(0,1fr);gap:10px}
    .event-boundary{display:grid;grid-template-columns:minmax(150px,1.18fr) minmax(140px,.82fr);gap:10px;align-items:end}
    .create-subevents{display:grid;gap:10px;margin-top:4px}
    .create-subevent-head{display:flex;align-items:center;justify-content:space-between;gap:12px}
    .create-subevent-actions{display:flex;align-items:center;justify-content:flex-end;gap:7px;flex-wrap:wrap}
    .create-subevent-head button{white-space:nowrap;min-height:38px;padding:8px 12px}
    .subevent-prefix-toggle{min-height:34px!important;padding:6px 10px!important;font-size:.82rem}
    .subevent-prefix-toggle[aria-pressed="true"]{border-color:var(--accent);background:color-mix(in srgb,var(--accent) 14%,var(--surface))}
    .date-entry{display:grid;grid-template-columns:minmax(0,1fr) 42px;gap:6px;align-items:center}
    .date-entry>input{min-width:0}
    .date-picker-button{width:42px;min-width:42px;padding:0;display:grid;place-items:center}

    .create-subevent-card{border:1px solid var(--border);border-radius:12px;background:var(--surface-2);padding:12px}
    .create-subevent-grid{display:grid;grid-template-columns:minmax(0,1fr);gap:10px;align-items:end}
    .create-subevent-top{display:flex;align-items:end;justify-content:space-between;gap:10px}
    .create-subevent-name{display:grid;flex:0 1 55%;min-width:220px}
    .create-subevent-boundaries{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
    .create-subevent-boundary{display:grid;grid-template-columns:minmax(160px,1.25fr) minmax(130px,.75fr);gap:8px;align-items:end}
    .create-subevent-remove{white-space:nowrap;align-self:end;min-height:44px;flex:0 0 auto}
    .dialog-inline-error{margin-top:12px;border:1px solid var(--danger,#b42318);border-radius:10px;background:color-mix(in srgb,var(--danger,#b42318) 10%,var(--surface));color:var(--text);padding:10px 12px;font-weight:650}
    .existing-segment-static{display:flex;justify-content:space-between;gap:10px;align-items:center;border:1px solid var(--border);border-radius:11px;background:var(--surface-2);padding:9px 10px}
    .selection-bar-anchor{height:0}
    @media (min-width:821px){
      main{padding-bottom:18px !important}
      .selection-bar-anchor{display:none}
      html[data-bk-theme="light"] body.bibliothekar-redesign .selection-bar.is-header-docked,
      body.bibliothekar-redesign .selection-bar.is-header-docked{
        position:relative !important;
        z-index:1 !important;
        width:100%;
        min-height:42px;
        margin:0 !important;
        padding:2px 50px 2px 8px !important;
        border:0 !important;
        border-radius:0 !important;
        background:transparent !important;
        box-shadow:none !important;
        backdrop-filter:none !important;
        -webkit-backdrop-filter:none !important;
        flex-wrap:nowrap;
        align-items:center;
        overflow:visible;
      }
      .selection-bar.is-header-docked .selection-summary{
        position:absolute;
        top:50%;
        transform:translate(-50%,-50%);
        display:flex;
        align-items:center;
        white-space:nowrap;
        line-height:1;
        margin:0;
        z-index:2;
      }
      .selection-bar.is-header-docked .selection-actions{
        margin-left:auto;
        display:flex;
        flex-wrap:nowrap;
        align-items:center;
        gap:7px;
        z-index:3;
      }
      .selection-bar.is-header-docked .selection-actions button{
        min-height:38px !important;
        height:38px !important;
        padding:0 10px !important;
        font-size:.94rem !important;
        line-height:1 !important;
        white-space:nowrap;
      }
      .selection-bar.is-header-docked .selection-top-button{
        position:absolute;
        right:2px !important;
        top:50% !important;
        width:38px !important;
        min-width:38px !important;
        height:38px !important;
        min-height:38px !important;
        padding:0 !important;
        transform:translateY(-50%) !important;
      }
      .summary.compact-heading-summary{
        display:grid;
        grid-template-columns:repeat(4,minmax(82px,1fr));
        gap:8px;
        margin:0;
      }
      .summary.compact-heading-summary .card{
        padding:8px 10px;
        border-radius:12px;
      }
      .summary.compact-heading-summary .muted{
        font-size:.78rem;
        white-space:nowrap;
      }
      .summary.compact-heading-summary .number{
        margin-top:2px;
        font-size:clamp(1.05rem,1.6vw,1.45rem);
        line-height:1.05;
        white-space:nowrap;
        overflow:hidden;
        text-overflow:clip;
      }
    }
    @media (max-width:820px){.event-boundaries,.create-subevent-grid{grid-template-columns:1fr}.create-subevent-boundaries{grid-template-columns:1fr}}
    @media (max-width:460px){.event-boundary,.create-subevent-boundary{grid-template-columns:1fr}.create-subevent-name{min-width:0;flex:1 1 auto}}

    .preview {
      height: fit-content;
    }

    @media (min-width: 821px) {
      .preview {
        position: sticky;
        top: calc(var(--bk-secondary-sticky-bottom, 141px) + 12px);
        max-height: calc(100dvh - var(--bk-secondary-sticky-bottom, 141px) - 24px);
        overflow: hidden;
        display: flex;
        flex-direction: column;
      }
      .preview-body {
        min-height: 0;
        display: flex;
        flex-direction: column;
        overflow: hidden;
      }
      .preview #structure-preview {
        min-height: 0;
        max-height: calc(100dvh - var(--bk-secondary-sticky-bottom, 141px) - 122px);
        overflow-y: auto;
        overscroll-behavior: contain;
        scrollbar-gutter: stable;
      }
    }

    @media (max-width: 820px) {
      .preview {
        position: static;
        max-height: none;
        overflow: visible;
      }
      .preview-body,
      .preview #structure-preview {
        max-height: none;
        overflow: visible;
      }
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
      font-family: Futura, "Helvetica Neue", Helvetica, Arial, sans-serif;
      font-size: 0.9rem;
      line-height: 1.5;
      white-space: pre;
      overflow-wrap: normal;
      overflow-x: hidden;
    }
    .tree.rich-preview {
      white-space: normal;
      font-family: Futura, "Helvetica Neue", Helvetica, Arial, sans-serif;
    }
    .stored-preview-meta {
      display:grid;
      gap:5px;
      margin-bottom:12px;
      color:var(--muted);
      font-size:.84rem;
    }
    .stored-preview-meta strong { color:var(--text); }
    .structure-lines {
      margin:0;
      width:100%;
      box-sizing:border-box;
      padding-top:10px;
      padding-right:4px;
      border-top:1px solid var(--border);
      white-space:pre;
      overflow-wrap:normal;
      overflow-x:hidden;
      font-family: Futura, "Helvetica Neue", Helvetica, Arial, sans-serif;
      font-size:.88rem;
      line-height:1.5;
      color:var(--text);
    }
    .collapse-card {
      overflow:hidden;
    }
    .collapse-card > summary {
      list-style:none !important;
      cursor:pointer;
      user-select:none;
    }
    .collapse-card > summary::-webkit-details-marker { display:none; }
    .collapse-card > summary::marker { content:""; }
    .collapse-card > summary::before {
      content:none !important;
      display:none !important;
    }
    .collapse-card[open] > summary {
      border-bottom:1px solid var(--border);
      padding-bottom:9px;
      margin-bottom:9px;
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
    .preview-selection-note { margin-top:9px; color:var(--muted); font-size:.78rem; line-height:1.4; white-space:normal!important; overflow:visible!important; overflow-wrap:anywhere; word-break:normal; }
    .preview-selection-note strong { white-space:normal; }
    .preview-selection-note .preview-period-dates { display:inline; white-space:normal; overflow-wrap:anywhere; }

    .timeline-event-card {
      min-width: 0;
      border: 1px solid var(--border);
      border-radius: 16px;
      background: var(--surface-2);
      padding: 15px;
      transition: border-color .15s ease, background .15s ease;
    }

    .timeline-event-card.selected-preview,
    .event-card.selected-preview {
      border-color: var(--accent);
      background:
        color-mix(
          in srgb,
          var(--accent) 12%,
          var(--surface)
        );
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
      width: fit-content;
      max-width: 100%;
      justify-self: start;
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


/* 0.45.2: Auf dem Handy zuerst Anzahl und Neuladen, darunter Titel und Auswahl. */
.day-section-header .day-header-controls { display:flex; align-items:center; justify-content:flex-end; gap:8px; flex-wrap:wrap; }
.day-section-header #day-reload { min-height:34px; padding:6px 10px; }
@media(max-width:700px){
  .day-section-header { display:grid !important; grid-template-columns:minmax(0,1fr) auto; grid-template-rows:auto auto; gap:8px 10px; align-items:center; }
  .day-section-header h2 { grid-column:1; grid-row:2; margin:0; }
  .day-section-header .day-header-controls { display:contents; }
  .day-section-header #day-count-label { grid-column:1; grid-row:1; white-space:normal; font-size:.83rem; }
  .day-section-header #day-reload { grid-column:2; grid-row:1; justify-self:end; }
  .day-section-header #day-select-all { grid-column:2; grid-row:2; justify-self:end; min-height:34px; }
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

    /* 0.40.1: Tagessegmente im "Ohne Ereignis"-Dialog bleiben auf Handybreite vollständig sichtbar. */
    .no-event-segment-fields {
      display:grid;
      grid-template-columns:minmax(190px,1.55fr) 118px 118px auto;
      gap:8px;
      align-items:end;
      margin-top:8px;
      width:100%;
      box-sizing:border-box;
    }
    .no-event-day-controls {
      display:grid;
      grid-template-columns:88px minmax(0,1fr);
      gap:6px;
      min-width:0;
    }
    .no-event-segment-remove {
      width:100%;
      min-width:0;
      align-self:end;
      white-space:nowrap;
    }
    @media (max-width:820px) {
      .no-event-segment-fields {
        grid-template-columns:minmax(0,1.65fr) minmax(88px,.7fr);
        gap:8px;
      }
      .no-event-day-field {
        grid-column:1;
        grid-row:1;
        min-width:0;
      }
      .no-event-start-field {
        grid-column:2;
        grid-row:1;
        min-width:0;
      }
      .no-event-end-field {
        grid-column:1 / -1;
        grid-row:2;
        display:grid;
        grid-template-columns:minmax(0,1.65fr) minmax(88px,.7fr);
        gap:8px;
        align-items:end;
      }
      .no-event-end-field > span {
        align-self:center;
      }
      .no-event-segment-remove {
        grid-column:1 / -1;
        grid-row:3;
        width:auto;
        min-width:0;
        justify-self:end;
        padding:7px 10px;
      }
    }
    @media (max-width:430px) {
      .no-event-day-controls {
        grid-template-columns:76px minmax(0,1fr);
      }
    }

    /* 0.40.2: mobile Tagessegmente als zwei vollständige Von–Bis-Zeilen. */
    .no-event-mobile-range-title,
    .no-event-end-date-mirror {
      display:none;
    }
    @media (max-width:820px) {
      .no-event-segment-fields {
        grid-template-columns:minmax(0,1fr) minmax(96px,.42fr);
        gap:8px;
        align-items:end;
      }
      .no-event-mobile-range-title {
        display:block;
        grid-column:1 / -1;
        grid-row:1;
        font-weight:700;
        line-height:1.15;
        margin:0 0 1px;
      }
      .no-event-day-field {
        grid-column:1;
        grid-row:2;
        min-width:0;
      }
      .no-event-start-field {
        grid-column:2;
        grid-row:2;
        min-width:0;
      }
      .no-event-end-date-mirror {
        display:grid;
        grid-column:1;
        grid-row:3;
        grid-template-columns:76px minmax(0,1fr);
        gap:6px;
        min-width:0;
      }
      .no-event-end-date-mirror input {
        width:100%;
        min-width:0;
      }
      .no-event-end-field {
        display:block;
        grid-column:2;
        grid-row:3;
        min-width:0;
      }
      .no-event-segment-fields .no-event-desktop-caption {
        display:none;
      }
      .no-event-segment-remove {
        grid-column:1 / -1;
        grid-row:4;
        width:auto;
        min-width:0;
        justify-self:end;
        padding:7px 10px;
      }
    }

    /* 0.54.4: Only the narrow CREATE dialog (including the phone web app).
       Keep the working 0.54.3 edit-dialog and the wide desktop layout intact. */
    #event-dialog { container-type:inline-size; container-name:mobile-event-create; }
    @container mobile-event-create (max-width:620px) {
      /* Start date | start time and end date | end time, also in new subevents.
         Later, more specific rules override the old 460px stacking rule. */
      #event-form .event-boundary,
      #event-form .create-subevent-boundary {
        display:grid;
        grid-template-columns:minmax(0,3fr) minmax(0,2fr) !important;
        gap:8px;
        align-items:end;
      }
      #event-form .event-boundaries,
      #event-form .create-subevent-boundaries,
      #event-form .create-subevent-grid,
      #event-form .create-subevent-card,
      #event-form .event-boundary > label,
      #event-form .create-subevent-boundary > label {
        min-inline-size:0;
        max-inline-size:100%;
        box-sizing:border-box;
      }
      /* WKWebKit/Firefox-iOS can add native padding outside the border-box.
         Match the proven 0.54.2/0.54.3 edit fix only inside this dialog. */
      #event-form input[type="date"],
      #event-form input[type="time"] {
        -webkit-appearance:none !important;
        appearance:none !important;
        display:block;
        box-sizing:border-box !important;
        inline-size:calc(100% - 2px) !important;
        width:calc(100% - 2px) !important;
        min-inline-size:0 !important;
        min-width:0 !important;
        max-inline-size:100% !important;
        max-width:100% !important;
        padding:0 !important;
        block-size:48px !important;
        min-block-size:48px !important;
        line-height:48px !important;
        text-align:center;
      }
      #event-form input[type="date"]::-webkit-date-and-time-value,
      #event-form input[type="time"]::-webkit-date-and-time-value,
      #event-form input[type="date"]::-webkit-datetime-edit,
      #event-form input[type="time"]::-webkit-datetime-edit {
        box-sizing:border-box;
        block-size:100%;
        min-block-size:100%;
        display:flex;
        align-items:center;
        justify-content:center;
        padding:0;
        line-height:normal;
      }
      /* "Ohne Ereignis": a single selected DAY, with both times BELOW it.
         Hide the old second date mirror, never change canonical day_key data. */
      #event-form .no-event-segment-fields {
        display:grid;
        grid-template-columns:repeat(2,minmax(0,1fr)) !important;
        gap:8px;
        align-items:end;
      }
      #event-form .no-event-mobile-range-title,
      #event-form .no-event-end-date-mirror { display:none !important; }
      #event-form .no-event-segment-fields > .no-event-day-field {
        grid-column:1 / -1 !important;
        grid-row:1 !important;
        min-width:0;
      }
      #event-form .no-event-segment-fields > .no-event-start-field {
        grid-column:1 !important;
        grid-row:2 !important;
        min-width:0;
      }
      #event-form .no-event-segment-fields > .no-event-end-field {
        display:grid;
        grid-template-columns:minmax(0,1fr);
        grid-column:2 !important;
        grid-row:2 !important;
        min-width:0;
      }
      #event-form .no-event-segment-fields .no-event-desktop-caption {
        display:block !important;
      }
      #event-form .no-event-segment-fields > .no-event-segment-remove {
        grid-column:1 / -1 !important;
        grid-row:3 !important;
        justify-self:end;
        width:auto;
        min-width:0;
      }
      /* Day selection + fixed month/year form one visible date control. */
      #event-form .no-event-day-controls {
        display:grid;
        grid-template-columns:76px minmax(0,1fr);
        gap:0;
        border:1px solid var(--border);
        border-radius:12px;
        background:var(--surface);
        overflow:hidden;
        min-width:0;
      }
      #event-form .no-event-day-controls > select,
      #event-form .no-event-day-controls > input {
        border:0;
        border-radius:0;
        background:transparent;
        min-width:0;
        width:100%;
        padding:10px 8px;
        box-sizing:border-box;
      }
      #event-form .no-event-day-controls > input:disabled {
        opacity:1;
        -webkit-text-fill-color:var(--text);
      }
    }

    /* 0.55.0: A measured-width fallback for the CREATE editor ONLY.
       0.54.4 relied on a container query which did not enforce two columns
       on all Firefox-iOS/mobile-app builds. No-event day rows are untouched.
       Stronger selector and explicit auto placement prevent old 1fr grids. */
    #event-dialog.bk-create-pairs #event-form .event-boundary,
    #event-dialog.bk-create-pairs #event-form .create-subevent-boundary {
      display:grid !important;
      grid-template-columns:minmax(0,3fr) minmax(0,2fr) !important;
      grid-auto-flow:row !important;
      align-items:end;
      gap:8px;
      min-inline-size:0;
      max-inline-size:100%;
    }
    #event-dialog.bk-create-pairs #event-form .event-boundary > label,
    #event-dialog.bk-create-pairs #event-form .create-subevent-boundary > label {
      grid-column:auto !important;
      grid-row:auto !important;
      inline-size:100%;
      min-inline-size:0 !important;
      max-inline-size:100%;
      box-sizing:border-box;
    }
    #event-dialog.bk-create-pairs #event-form .event-boundary input[type="date"],
    #event-dialog.bk-create-pairs #event-form .event-boundary input[type="time"],
    #event-dialog.bk-create-pairs #event-form .create-subevent-boundary input[type="date"],
    #event-dialog.bk-create-pairs #event-form .create-subevent-boundary input[type="time"] {
      -webkit-appearance:none !important;
      appearance:none !important;
      width:calc(100% - 2px) !important;
      inline-size:calc(100% - 2px) !important;
      min-inline-size:0 !important;
      max-inline-size:100% !important;
      padding:0 !important;
      box-sizing:border-box !important;
      text-align:center;
      block-size:48px;
      line-height:48px;
    }


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
        <details id="backup-filter" class="backup-filter">
          <summary>
            <span class="backup-filter-icon" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M4 5h16l-6.2 7.1v5.1l-3.6 1.8v-6.9z"/></svg></span>
            <span class="backup-filter-label">Sicherungsfilter</span>
            <strong id="backup-filter-value" class="backup-filter-value">Alle aktiven Sicherungen</strong>
          </summary>
          <div class="backup-filter-panel">
            <div class="backup-filter-actions">
              <button id="backup-filter-all" type="button">Alle aktiven Sicherungen</button>
              <button id="backup-filter-none" type="button">Auswahl aufheben</button>
            </div>
            <div id="backup-filter-active-list" class="backup-filter-list"></div>
            <details id="backup-filter-archived" class="backup-filter-archived">
              <summary>Archivierte Sicherungen einblenden</summary>
              <div id="backup-filter-archived-list" class="backup-filter-list" style="margin-top:8px"></div>
            </details>
          </div>
        </details>
        <select id="job-select" hidden aria-hidden="true" tabindex="-1">
          <option value="">Technischer Anker</option>
        </select>
      </div>

    </section>

    <section id="post-save-action" class="card" hidden style="margin:0 0 18px; border-color:#6ea8ff;">
      <strong id="post-save-title">Geplante Änderungen</strong>
      <p id="post-save-detail" class="muted" style="margin:8px 0 12px;">Alle geplanten Ereignisse sind standardmäßig ausgewählt.</p>
      <details class="collapse-card card" style="margin:0 0 14px;padding:10px 12px;">
        <summary>Auswahl anpassen</summary>
        <div id="planned-event-selection" style="display:grid;gap:8px;margin-top:10px;"></div>
      </details>
      <button id="apply-saved-event-button" class="primary bk-positive-action" type="button">Alle geplanten Ereignisse anwenden</button>
      <span id="apply-saved-event-status" class="muted" style="margin-left:12px;"></span>
    </section>

    <section id="event-suggestions-panel" class="card suggestions-panel" hidden>
      <h2>Neue Aufnahmen passen zu bestehenden Ereignissen</h2>
      <p class="muted">Die Aufnahmezeiten passen eindeutig zu bereits vorhandenen Ereignissen. Erst nach deiner Bestätigung werden die neuen Aufnahmen sicher zum passenden Ereignis hinzugefügt.</p>
      <div id="event-suggestion-list" class="suggestion-list"></div>
      <p id="event-suggestion-status" class="muted" role="status" aria-live="polite"></p>
    </section>

    <div id="selection-bar-anchor" class="selection-bar-anchor" aria-hidden="true"></div>
    <section
      id="selection-bar"
      class="selection-bar"
    >
      <div class="selection-summary"><strong id="selection-label">0 Gruppen ausgewählt</strong><span id="selection-period" class="muted"></span></div>

      <div class="selection-actions">
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
        <div class="section-header day-section-header">
          <h2>Tagesordner</h2>

          <div class="day-header-controls">
            <span
              id="day-count-label"
              class="muted day-count-label"
            ></span>
            <button id="day-reload" type="button" title="Dateibestand und Zuordnung erneut prüfen">Neuladen</button>
            <button
              id="day-select-all"
              type="button"
              title="Mit Umschalt (Shift) lassen sich zusammenhängende Tagesgruppen auswählen."
              style="min-height:34px;padding:6px 10px"
            >
              Alle auswählen
            </button>
          </div>
        </div>

        <div
          id="day-list"
          class="day-list"
        >
          <div class="empty">
            Noch kein Arbeitsbestand ausgewählt.
          </div>
        </div>
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
          <h2>Destination structure preview</h2>

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
            placeholder="Zum Beispiel Urlaub"
          >
        </label>

        <label id="existing-parent-row" class="full-width" hidden>
          <span>Bestehendes Ereignis erweitern</span>
          <select id="existing-parent-event"></select>
          <small class="muted">Direkt angrenzende freie Zeit kann ein bestehendes Ereignis erweitern. Gelb markierte, bereits freigegebene Applied-Bereiche sind normaler freier Bestand und erzeugen keine Neu-Zuordnungsaufgabe.</small>
        </label>

        <div id="no-event-segment-editor" class="full-width" hidden>
          <label id="existing-no-event-target-row" class="full-width" hidden style="margin-bottom:10px">
            <span>Bestehende „Ohne Ereignis“-Sammlung</span>
            <select id="existing-no-event-target"></select>
          </label>
          <div style="display:flex;justify-content:space-between;gap:8px;align-items:center;margin-bottom:8px">
            <div><strong>Tagessegmente</strong><div class="muted" style="font-size:.86rem;margin-top:2px">Jeder Tag bzw. Teil eines Tages wird einzeln gespeichert.</div></div>
            <button id="add-no-event-segment" type="button">＋ Tagessegment</button>
          </div>
          <div id="no-event-segment-list" style="display:grid;gap:6px"></div>
        </div>

        <div id="event-boundaries" class="event-boundaries full-width">
          <div class="event-boundary">
            <label><span>Beginn</span><input id="event-start-date" type="date" required></label>
            <label id="event-start-time-label"><span>Startzeit</span><input id="event-start-time" type="time" value="00:00"></label>
          </div>
          <div class="event-boundary">
            <label><span>Ende</span><input id="event-end-date" type="date" required></label>
            <label id="event-end-time-label"><span>Endzeit</span><input id="event-end-time" type="time" value="23:59"></label>
          </div>
        </div>

        <input id="use-time-range" type="checkbox" checked hidden aria-hidden="true">

        <div id="create-subevents" class="create-subevents full-width">
          <div class="create-subevent-head">
            <strong id="create-subevent-heading">Unterereignisse (optional)</strong>
            <div class="create-subevent-actions">
              <button id="subevent-prefix-toggle" type="button" class="subevent-prefix-toggle" hidden>Präfix: an</button>
              <button id="add-create-subevent" type="button">＋ Unterereignis hinzufügen</button>
            </div>
          </div>
          <div id="create-subevent-list" style="display:grid;gap:8px"></div>
        </div>

        <label id="create-subfolders-row" class="full-width check-row">
          <input id="create-subfolders" type="checkbox">
          <span>Unterordner erstellen</span>
        </label>

        <label id="preserve-day-folders-row" class="full-width check-row">
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

      <div id="dialog-error" class="dialog-inline-error" role="alert" hidden></div>

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

  
  <dialog id="cross-backup-membership-dialog">
    <div class="dialog-content">
      <h2 style="margin-top:0">Weitere Aufnahmen aus ausgeblendeten Sicherungen</h2>
      <p id="cross-backup-membership-summary" class="muted"></p>
      <div id="cross-backup-membership-sources" style="display:grid;gap:9px;margin-top:12px"></div>
      <p class="muted" style="margin-top:14px">
        Nicht angehakte Tageskarten innerhalb sichtbarer Sicherungen werden automatisch
        nach Zeitraum einbezogen. Hier werden nur zusätzliche Aufnahmen aus aktuell
        ausgeblendeten aktiven Sicherungen bestätigt.
      </p>
      <div class="dialog-actions">
        <button id="cross-backup-membership-cancel" type="button">Abbrechen</button>
        <button id="cross-backup-membership-confirm" class="primary bk-positive-action" type="button">OK · vollständig übernehmen</button>
      </div>
    </div>
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
        panel.innerHTML=count ? `<strong>Offene Aufgaben · ${count}</strong>`+tasks.map(task=>{const rawHref=String(task.href||'/events');const safeHref=rawHref.startsWith('/')&&!rawHref.startsWith('//')?rawHref:'/events';return `<a class="global-task-item" href="${escapeHtml(safeHref)}"><strong>${escapeHtml(String(task.title||'Aufgabe'))}</strong><span>${escapeHtml(String(task.detail||''))}</span></a>`;}).join("") : `<strong>Keine offenen Aufgaben</strong><span class="muted" style="display:block;margin-top:6px">Alles erledigt.</span>`;
      } catch (_) {}
    }
    document.getElementById("global-task-fab")?.addEventListener("click",()=>document.getElementById("global-task-panel")?.classList.toggle("open"));
    refreshGlobalTasks();
    setInterval(refreshGlobalTasks,30000);

    const jobSelect =
      document.getElementById("job-select");
    const backupFilter = document.getElementById("backup-filter");
    const backupFilterValue = document.getElementById("backup-filter-value");
    const backupFilterActiveList = document.getElementById("backup-filter-active-list");
    const backupFilterArchivedList = document.getElementById("backup-filter-archived-list");
    const backupFilterArchived = document.getElementById("backup-filter-archived");
    const backupFilterAll = document.getElementById("backup-filter-all");
    const backupFilterNone = document.getElementById("backup-filter-none");


    const newEventButton =
      document.getElementById("new-event-button");
    const existingNoEventButton = document.getElementById("existing-no-event-button");

    const noEventButton =
      document.getElementById("no-event-button");
    let noEventLabel = "Ohne Ereignis";
    let globalSubeventDateMode = "start";
    let globalSubeventIncludeYear = false;
    let globalSubeventIncludeTime = false;
    let globalSubeventPrefixEnabled = true;

    function applyEventNamingSettings(value={}) {
      noEventLabel = String(value.no_event_label || "Ohne Ereignis").trim() || "Ohne Ereignis";
      globalSubeventDateMode = String(value.subevent_date_mode || "start");
      globalSubeventIncludeYear = Boolean(value.subevent_include_year);
      globalSubeventIncludeTime = Boolean(value.subevent_include_time);
      globalSubeventPrefixEnabled = value.subevent_prefix_enabled !== false;
      if (noEventButton) noEventButton.textContent = noEventLabel;
      if (existingNoEventButton) existingNoEventButton.textContent = "Zu bestehendem " + noEventLabel;
    }

    async function loadEventNamingSettings() {
      try {
        const data = await getJson("/api/settings/event-naming");
        applyEventNamingSettings(data);
      } catch (_) {
        applyEventNamingSettings({});
      }
    }

    document.addEventListener("bibliothekar:event-naming-updated", event => {
      applyEventNamingSettings(event.detail || {});
    });

    const statusElement =
      document.getElementById("status");

    const dayList =
      document.getElementById("day-list");

    const daySelectAllButton =
      document.getElementById("day-select-all");

    const selectionBar =
      document.getElementById("selection-bar");
    const selectionSummary=selectionBar?.querySelector(".selection-summary");
    const selectionBarAnchor=document.getElementById("selection-bar-anchor");
    const selectionDockTarget=document.getElementById("bk-workspace-dock");
    const workspaceTab=document.querySelector('.bk-tab[data-area="workspace"]');
    const captureSummarySlot=document.getElementById("bk-capture-summary-slot");
    const summarySection=document.querySelector("section.summary");
    const summaryHomeParent=summarySection?.parentNode || null;
    const summaryHomeNext=summarySection?.nextSibling || null;

    function workspaceStaticDesktop(){
      return window.matchMedia("(min-width: 821px)").matches;
    }

    function workspaceStandaloneMobile(){
      return (
        document.documentElement.dataset.bkDisplayMode === "standalone"
        && window.matchMedia("(max-width: 820px)").matches
      );
    }

    function workspaceBrowserPortrait(){
      return (
        document.documentElement.dataset.bkDisplayMode === "browser"
        && window.matchMedia("(max-width: 700px) and (orientation: portrait)").matches
      );
    }

    function workspaceHeaderDock(){
      return workspaceStaticDesktop() || workspaceStandaloneMobile() || workspaceBrowserPortrait();
    }

    function alignHeaderSelectionSummary(){
      if(!workspaceStaticDesktop() || !selectionSummary || !workspaceTab || !selectionBar)return;
      const tabRect=workspaceTab.getBoundingClientRect();
      const barRect=selectionBar.getBoundingClientRect();
      selectionSummary.style.left=(tabRect.left+tabRect.width/2-barRect.left)+"px";
    }

    function fitTreeText(root){
      if(!root)return;
      const nodes=root.matches?.(".structure-lines,.plan-tree")
        ? [root]
        : [...root.querySelectorAll?.(".structure-lines,.plan-tree")||[]];
      for(const node of nodes){
        node.style.removeProperty("font-size");
        let size=parseFloat(getComputedStyle(node).fontSize)||14;
        const minimum=10;
        while(node.scrollWidth>node.clientWidth+1 && size>minimum){
          size-=.5;
          node.style.fontSize=size+"px";
        }
      }
    }

    function scheduleTreeFit(root){
      const run=()=>fitTreeText(root);
      requestAnimationFrame(()=>requestAnimationFrame(run));
      if(document.fonts?.ready)document.fonts.ready.then(()=>requestAnimationFrame(run));
      setTimeout(run,120);
      setTimeout(run,360);
    }

    function positionWorkspaceChrome(){
      if(!selectionBar || !selectionBarAnchor)return;
      if(workspaceHeaderDock() && selectionDockTarget){
        if(selectionBar.parentNode!==selectionDockTarget) selectionDockTarget.appendChild(selectionBar);
        selectionBar.classList.add("is-header-docked");
        document.querySelector(".bk-workspace-subnav")?.classList.add("has-selection-dock");
        requestAnimationFrame(alignHeaderSelectionSummary);
      } else {
        if(selectionBar.parentNode!==selectionBarAnchor.parentNode){
          selectionBarAnchor.parentNode?.insertBefore(selectionBar,selectionBarAnchor.nextSibling);
        }
        selectionBar.classList.remove("is-header-docked");
        selectionSummary?.style.removeProperty("left");
        document.querySelector(".bk-workspace-subnav")?.classList.remove("has-selection-dock");
      }
      if(summarySection && captureSummarySlot && summarySection.parentNode!==captureSummarySlot){
        captureSummarySlot.appendChild(summarySection);
      }
      summarySection?.classList.toggle("compact-heading-summary", workspaceStaticDesktop());
      fitTreeText(document);
    }

    window.addEventListener("resize",positionWorkspaceChrome);
    requestAnimationFrame(positionWorkspaceChrome);
    const eventSuggestionsPanel = document.getElementById("event-suggestions-panel");
    const eventSuggestionList = document.getElementById("event-suggestion-list");
    const eventSuggestionStatus = document.getElementById("event-suggestion-status");
    let eventSuggestions = [];

    const selectionLabel =
      document.getElementById("selection-label");

    const structurePreview =
      document.getElementById(
        "structure-preview"
      );

    const structureFitMutationObserver = new MutationObserver(()=>{
      scheduleTreeFit(structurePreview);
    });
    if(structurePreview){
      structureFitMutationObserver.observe(structurePreview,{
        childList:true,
        subtree:true,
        characterData:true
      });
    }

    const eventDialog =
      document.getElementById("event-dialog");
    const eventForm =
      document.getElementById("event-form");

    // 0.55.0: check ACTUAL dialog width, not just the viewport/container.
    // Split-view on iPad and installed web apps can disagree with CSS
    // viewport queries. Only parent/child date-time pairs are affected.
    function syncCreateEventCompactPairs() {
      if (!eventDialog || !eventDialog.open) return;
      const dialogWidth=eventDialog.getBoundingClientRect().width;
      const viewportWidth=document.documentElement.clientWidth;
      const compact=dialogWidth>0 && (dialogWidth<=620 || viewportWidth<=820);
      eventDialog.classList.toggle("bk-create-pairs", compact);
    }
    if (typeof ResizeObserver !== "undefined") {
      const createDialogWidthObserver=new ResizeObserver(syncCreateEventCompactPairs);
      createDialogWidthObserver.observe(eventDialog);
    }
    window.addEventListener("resize",syncCreateEventCompactPairs);


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
    let activeExtension = null;

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
    // 0.26.6: „Ohne Ereignis“ besitzt nur noch kanonische Tagessegmente.
    const existingNoEventTargetRow = document.getElementById("existing-no-event-target-row");
    const existingNoEventTarget = document.getElementById("existing-no-event-target");
    let noEventTargetCache = [];
    let activeNoEventTarget = null;

    const useTimeRange =
      document.getElementById("use-time-range");

    const eventBoundaries=document.getElementById("event-boundaries");
    const eventStartTimeLabel=document.getElementById("event-start-time-label");
    const eventEndTimeLabel=document.getElementById("event-end-time-label");
    const createSubevents=document.getElementById("create-subevents");
    const createSubeventHeading=document.getElementById("create-subevent-heading");
    const createSubeventList=document.getElementById("create-subevent-list");
    const addCreateSubevent=document.getElementById("add-create-subevent");
    const subeventPrefixToggle=document.getElementById("subevent-prefix-toggle");
    let dialogSubeventPrefixEnabled=true;
    const dialogError=document.getElementById("dialog-error");

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
    const preserveDayFoldersRow =
      document.getElementById("preserve-day-folders-row");
    const createSubfolders = document.getElementById("create-subfolders");
    const createSubfoldersRow = document.getElementById("create-subfolders-row");
    let globalFolderLayout = null;

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
    let selectedJobIds = new Set();
    let selectedDays = new Set();
    let lastSelectedDayKey = null;
    let selectedPreviewEventId = null;
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


    function validIsoDateText(value) {
      const text=String(value||"").trim();
      if(!/^\d{4}-\d{2}-\d{2}$/.test(text))return false;
      const date=new Date(text+"T12:00:00");
      return !Number.isNaN(date.getTime()) && date.toISOString().slice(0,10)===text;
    }

    function openOptionalDatePicker(input) {
      if(!input)return;
      const picker=document.createElement("input");
      picker.type="date";
      picker.value=validIsoDateText(input.value) ? input.value : "";
      const min=String(input.dataset.dateMin||input.min||"");
      const max=String(input.dataset.dateMax||input.max||"");
      if(min)picker.min=min;
      if(max)picker.max=max;
      picker.style.position="fixed";
      picker.style.left="50%";
      picker.style.bottom="12px";
      picker.style.width="2px";
      picker.style.height="2px";
      picker.style.opacity=".01";
      picker.style.zIndex="99999";
      document.body.appendChild(picker);
      let finished=false;
      const cleanup=()=>{
        if(finished)return;
        finished=true;
        setTimeout(()=>picker.remove(),0);
      };
      picker.addEventListener("change",()=>{
        if(picker.value){
          input.value=picker.value;
          input.dispatchEvent(new Event("change",{bubbles:true}));
          input.dispatchEvent(new Event("input",{bubbles:true}));
        }
        cleanup();
      },{once:true});
      picker.addEventListener("blur",()=>setTimeout(cleanup,250),{once:true});
      picker.focus({preventScroll:true});
      try{
        if(typeof picker.showPicker==="function")picker.showPicker();
        else picker.click();
      }catch(_){
        picker.click();
      }
    }

    document.addEventListener("click",event=>{
      const button=event.target.closest?.("[data-date-picker-target],[data-date-picker-inline]");
      if(!button)return;
      event.preventDefault();
      const id=String(button.dataset.datePickerTarget||"");
      const input=id
        ? document.getElementById(id)
        : button.parentElement?.querySelector("input[type='text']");
      openOptionalDatePicker(input);
    });


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
              (document.documentElement.lang === "de" ? "de-DE" : "en-US"),
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
        (document.documentElement.lang === "de" ? "de-DE" : "en-US"),
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
          (document.documentElement.lang === "de" ? "de-DE" : "en-US"),
          {
            maximumFractionDigits: 1
          }
        ).format(result)
        + " "
        + units[unitIndex]
      );
    }


    async function decodeApiResponse(response) {
      const text = await response.text();
      let data = {};
      if (text) {
        try {
          data = JSON.parse(text);
        } catch (_) {
          if (!response.ok) {
            const error = new Error(
              `Serverfehler ${response.status}: ${text.slice(0, 240) || "keine Antwort"}`
            );
            error.data = {detail:text};
            error.status = response.status;
            throw error;
          }
          throw new Error("Die API hat keine gültige JSON-Antwort geliefert.");
        }
      }
      if (!response.ok) {
        const error = new Error(
          data.detail || `Anfrage fehlgeschlagen (HTTP ${response.status}).`
        );
        error.data = data;
        error.status = response.status;
        throw error;
      }
      return data;
    }

    async function getJson(url) {
      const response = await fetch(url);
      return decodeApiResponse(response);
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
      return decodeApiResponse(response);
    }


    const crossBackupMembershipDialog = document.getElementById("cross-backup-membership-dialog");
    const crossBackupMembershipSummary = document.getElementById("cross-backup-membership-summary");
    const crossBackupMembershipSources = document.getElementById("cross-backup-membership-sources");
    const crossBackupMembershipCancel = document.getElementById("cross-backup-membership-cancel");
    const crossBackupMembershipConfirm = document.getElementById("cross-backup-membership-confirm");

    function confirmCrossBackupMembership(error) {
      const membership=error?.data?.membership || {};
      const sources=membership.hidden_sources || membership.sources || [];
      const familyCount=Number(
        membership.hidden_additional_family_count
        ?? membership.additional_family_count
        ?? 0
      );
      const fileCount=Number(
        membership.hidden_additional_file_count
        ?? membership.additional_file_count
        ?? 0
      );
      crossBackupMembershipSummary.textContent =
        `${familyCount} weitere Familien · `
        + `${fileCount} Dateien liegen in aktuell ausgeblendeten aktiven Sicherungen und gehören ebenfalls zu diesem Zeitraum.`;

      crossBackupMembershipSources.innerHTML=sources.map(source=>{
        const familyRows=(source.families||[]).map(family=>{
          const files=(family.file_names||[]).map(name=>`<li><code>${escapeHtml(name)}</code></li>`).join("");
          return `<details class="card" style="margin:7px 0 0;padding:8px 10px">
            <summary><strong>${escapeHtml(family.original_stem||"Dateifamilie")}</strong>
              · ${escapeHtml(family.capture_time||"")}
              · ${Number(family.file_count||0)} Dateien</summary>
            <ul style="margin:8px 0 0">${files||"<li class='muted'>Keine Dateinamen verfügbar.</li>"}</ul>
          </details>`;
        }).join("");
        return `<details class="card" style="margin:0;padding:10px 12px">
          <summary><strong>${escapeHtml(source.source_label||source.job_id||"Sicherung")}</strong>
            · ${Number(source.family_count||0)} Familien
            · ${Number(source.file_count||0)} Dateien</summary>
          <div style="margin-top:8px">${familyRows}</div>
        </details>`;
      }).join("");

      return new Promise(resolve=>{
        let settled=false;
        const finish=value=>{
          if(settled)return;
          settled=true;
          crossBackupMembershipDialog.close();
          resolve(value);
        };
        crossBackupMembershipConfirm.onclick=()=>finish(true);
        crossBackupMembershipCancel.onclick=()=>finish(false);
        crossBackupMembershipDialog.oncancel=event=>{event.preventDefault();finish(false);};
        crossBackupMembershipDialog.showModal();
      });
    }

    async function postWithCanonicalMembership(url,payload) {
      try {
        return await postJson(url,payload);
      } catch(error) {
        if(error?.data?.confirmation_required!=="cross_backup_membership") throw error;
        const confirmed=await confirmCrossBackupMembership(error);
        if(!confirmed)return null;
        return postJson(url,{...payload,confirm_cross_backup_membership:true});
      }
    }


    function backupWorkflowLabel(status) {
      return {
        planned: "Planned",
        applied: "Applied",
        archived: "Archived"
      }[String(status || "")] || "Planned";
    }

    function renderBackupFilter() {
      const active = jobs.filter(job => job.workflow_status !== "archived");
      const archived = jobs.filter(job => job.workflow_status === "archived");

      const choice = job => `
        <label class="backup-filter-choice">
          <input type="checkbox" data-backup-filter-job="${escapeHtml(job.id)}" ${selectedJobIds.has(job.id) ? "checked" : ""}>
          <span><strong>${escapeHtml(formatJobLabel(job))}</strong><small style="display:block">${Number(job.active_family_count || 0)} aktive Familien</small></span>
          <span class="badge ${job.workflow_status === "applied" ? "success" : ""}">${escapeHtml(backupWorkflowLabel(job.workflow_status))}</span>
        </label>`;

      backupFilterActiveList.innerHTML = active.length
        ? active.map(choice).join("")
        : '<div class="muted">Keine aktiven Sicherungen.</div>';
      backupFilterArchivedList.innerHTML = archived.length
        ? archived.map(choice).join("")
        : '<div class="muted">Keine archivierten Sicherungen.</div>';

      const selectedArchived = archived.filter(job => selectedJobIds.has(job.id)).length;
      const selectedActive = active.filter(job => selectedJobIds.has(job.id)).length;
      if (active.length && selectedActive === active.length && selectedArchived === 0) {
        backupFilterValue.textContent = "Alle aktiven Sicherungen";
      } else if (selectedJobIds.size === 0) {
        backupFilterValue.textContent = "Keine Sicherung";
      } else {
        backupFilterValue.textContent = `${selectedJobIds.size} Sicherungen`;
      }
      if (selectedArchived) backupFilterArchived.open = true;
    }

    function updateTechnicalAnchor(preferred = "") {
      const selected = jobs.filter(job => selectedJobIds.has(job.id));
      const chosen = selected.find(job => job.id === preferred)
        || selected.find(job => job.workflow_status !== "archived")
        || selected[0]
        || null;
      jobSelect.innerHTML = jobs.map(job =>
        `<option value="${escapeHtml(job.id)}">${escapeHtml(formatJobLabel(job))}</option>`
      ).join("");
      jobSelect.value = chosen?.id || "";
    }

    function sourceGroupsForSelection() {
      const result = new Map();
      for (const group of selectedDatedGroups()) {
        const sources = Array.isArray(group.source_groups) && group.source_groups.length
          ? group.source_groups
          : [{job_id:group.job_id, group}];
        for (const source of sources) {
          const jobId = String(source.job_id || "");
          if (!jobId) continue;
          const local = source.group || group;
          const bucket = result.get(jobId) || {groups:[], family_ids:new Set()};
          bucket.groups.push(local);
          for (const id of (local.family_ids || [])) bucket.family_ids.add(Number(id));
          for (const family of (local.families || [])) {
            if (Number.isFinite(Number(family.family_id))) bucket.family_ids.add(Number(family.family_id));
          }
          result.set(jobId,bucket);
        }
      }
      return result;
    }

    function anchorJobIdForSelection() {
      const byJob = sourceGroupsForSelection();
      if (jobSelect.value && byJob.has(jobSelect.value)) return jobSelect.value;
      const first = [...byJob.keys()][0];
      if (first) return first;
      if (jobSelect.value && selectedJobIds.has(jobSelect.value)) return jobSelect.value;
      return [...selectedJobIds][0] || "";
    }

    function visibleActiveJobIds(){
      return jobs
        .filter(job=>job.workflow_status!=="archived" && selectedJobIds.has(job.id))
        .map(job=>String(job.id));
    }

    function payloadForSourceJob(base, jobId) {
      const bucket = sourceGroupsForSelection().get(jobId);
      if (!bucket) return {...base};
      const groups = bucket.groups;
      const intervals = groups
        .filter(group => group.start_datetime && group.end_datetime)
        .map(group => ({start_datetime:group.start_datetime,end_datetime:group.end_datetime}));
      const dayKeys = [...new Set(groups.map(group => group.day_key).filter(Boolean))].sort();
      const familyIds = [...bucket.family_ids]
        .map(Number)
        .filter(Number.isFinite)
        .sort((a,b)=>a-b);
      return {
        ...base,
        selected_intervals: intervals,
        selected_day_keys: dayKeys,
        selected_family_ids: familyIds,
        visible_active_job_ids: visibleActiveJobIds()
      };
    }

    function payloadForAllSources(base) {
      const groups = selectedDatedGroups();
      const familyIds = [...new Set(
        [...sourceGroupsForSelection().values()]
          .flatMap(bucket => [...bucket.family_ids])
          .map(Number)
          .filter(Number.isFinite)
      )].sort((a,b)=>a-b);
      return {
        ...base,
        selected_intervals: groups
          .filter(group => group.start_datetime && group.end_datetime)
          .map(group => ({start_datetime:group.start_datetime,end_datetime:group.end_datetime})),
        selected_day_keys: [...new Set(groups.map(group=>group.day_key).filter(Boolean))].sort(),
        selected_family_ids: familyIds,
        visible_active_job_ids: visibleActiveJobIds()
      };
    }

    function mergeWorkspacePayloads(items) {
      if (!items.length) {
        return {
          job:null,jobs:[],selected_job_ids:[],
          statistics:{day_count:0,file_count:0,family_count:0,review_required_count:0,without_date_file_count:0},
          events:[],day_groups:[],time_segments:[],
          planning_overview:{event_groups:[],available_day_groups:[],timeline_groups:[]},
          released_archive_groups:[],archive_change_reviews:[]
        };
      }

      const rawEvents = [];
      const rawChildren = [];
      const eventComponents = new Map();
      const planningEvents = new Map();
      const dayMap = new Map();
      const timeSegments = [];
      const reviews = [];

      for (const item of items) {
        const jobId = item.jobId;
        for (const event of (item.data.events || [])) {
          const enriched = {...event, job_id:event.job_id || jobId};
          if (enriched.event_level === "parent") rawEvents.push(enriched);
          else rawChildren.push(enriched);
        }
        timeSegments.push(...(item.data.time_segments || []).map(row=>({...row,job_id:row.job_id||jobId})));
        reviews.push(...(item.data.archive_change_reviews || []).map(row=>({...row,job_id:row.job_id||jobId})));

        for (const group of (item.data.planning_overview?.event_groups || [])) {
          const enriched={...group,job_id:group.job_id||jobId};
          const canonical=String(enriched.linked_event_id || enriched.event_id);
          const current=planningEvents.get(canonical);
          const component={job_id:jobId,event_id:String(enriched.event_id),status:String(enriched.status||""),linkage_kind:enriched.linkage_kind||null};
          if(!current){
            planningEvents.set(canonical,{
              ...enriched,
              event_id:canonical,
              canonical_event_id:canonical,
              component_events:[component],
              family_ids:[...(enriched.family_ids||[])],
              source_job_ids:[jobId],
              linked_pending_count: enriched.linked_event_id && enriched.status==="planned" ? 1 : 0
            });
          }else{
            current.component_events.push(component);
            if(!current.source_job_ids.includes(jobId))current.source_job_ids.push(jobId);
            current.family_ids=[...new Set([...(current.family_ids||[]),...(enriched.family_ids||[])])];
            current.family_count=Number(current.family_count||0)+Number(enriched.family_count||0);
            current.file_count=Number(current.file_count||0)+Number(enriched.file_count||0);
            current.total_size_bytes=Number(current.total_size_bytes||0)+Number(enriched.total_size_bytes||0);
            current.review_required_count=Number(current.review_required_count||0)+Number(enriched.review_required_count||0);
            if(enriched.linked_event_id && enriched.status==="planned")current.linked_pending_count=Number(current.linked_pending_count||0)+1;
            if(!enriched.linked_event_id){
              const keep={
                event_name:enriched.event_name,folder_name:enriched.folder_name,
                start_datetime:enriched.start_datetime,end_datetime:enriched.end_datetime,
                status:enriched.status,event_kind:enriched.event_kind,
                preserve_day_folders:enriched.preserve_day_folders,resort_required:enriched.resort_required,
                job_id:enriched.job_id,linked_event_id:null,linkage_kind:null
              };
              Object.assign(current,keep);
            }
          }
        }

        for (const group of (item.data.planning_overview?.available_day_groups || [])) {
          const start=String(group.start_datetime||"");
          const end=String(group.end_datetime||"");
          const key=`${group.has_date ? group.day_key : "__without_date__"}|${start}|${end}`;
          const sourceGroup={...group,job_id:jobId};
          const current=dayMap.get(key);
          if(!current){
            dayMap.set(key,{
              ...sourceGroup,
              card_key:`global:${key}`,
              family_ids:[...(group.family_ids||[])],
              families:(group.families||[]).map(f=>({...f,job_id:jobId})),
              source_job_ids:[jobId],
              source_groups:[{job_id:jobId,group:sourceGroup}]
            });
          }else{
            current.file_count=Number(current.file_count||0)+Number(group.file_count||0);
            current.family_count=Number(current.family_count||0)+Number(group.family_count||0);
            current.total_size_bytes=Number(current.total_size_bytes||0)+Number(group.total_size_bytes||0);
            current.review_required_count=Number(current.review_required_count||0)+Number(group.review_required_count||0);
            current.family_ids=[...new Set([...(current.family_ids||[]),...(group.family_ids||[])])];
            current.families.push(...(group.families||[]).map(f=>({...f,job_id:jobId})));
            if(!current.source_job_ids.includes(jobId))current.source_job_ids.push(jobId);
            current.source_groups.push({job_id:jobId,group:sourceGroup});
            current.partially_assigned=Boolean(current.partially_assigned||group.partially_assigned);
          }
        }
      }

      for (const root of rawEvents.filter(event=>!event.linkage_kind)) {
        eventComponents.set(String(root.id),{
          ...root,
          component_events:[{job_id:String(root.job_id),event_id:String(root.id),status:String(root.status||""),linkage_kind:null}]
        });
      }
      for (const linked of rawEvents.filter(event=>event.linkage_kind)) {
        const canonical=String(linked.linked_event_id||linked.id);
        const current=eventComponents.get(canonical) || {
          ...linked,id:canonical,linked_event_id:null,linkage_kind:null,component_events:[]
        };
        current.component_events.push({
          job_id:String(linked.job_id),event_id:String(linked.id),
          status:String(linked.status||""),linkage_kind:linked.linkage_kind
        });
        current.assigned_family_count=Number(current.assigned_family_count||0)+Number(linked.assigned_family_count||0);
        current.assigned_file_count=Number(current.assigned_file_count||0)+Number(linked.assigned_file_count||0);
        eventComponents.set(canonical,current);
      }
      for(const event of eventComponents.values()){
        event.has_planned_component=(event.component_events||[]).some(component=>component.status==="planned");
      }

      const available=[...dayMap.values()].sort((a,b)=>String(a.start_datetime||a.day_key||"").localeCompare(String(b.start_datetime||b.day_key||"")));
      const visibleEvents=[...planningEvents.values()].sort((a,b)=>String(a.start_datetime||"").localeCompare(String(b.start_datetime||"")));
      const timeline=[...visibleEvents,...available].sort((a,b)=>{
        const aUndated = a.group_type !== "event" && !a.has_date;
        const bUndated = b.group_type !== "event" && !b.has_date;
        if (aUndated !== bUndated) return aUndated ? -1 : 1;
        const aa=String(a.start_datetime||a.day_key||"9999");
        const bb=String(b.start_datetime||b.day_key||"9999");
        return aa.localeCompare(bb) || (a.group_type==="event"?-1:1);
      });

      const releasedMap=new Map();
      for(const group of (items[0].data.released_archive_groups||[])){
        releasedMap.set(String(group.card_key||group.id||JSON.stringify(group)),group);
      }
      const released=[...releasedMap.values()];

      const dayKeys=new Set();
      for(const group of timeline){
        if(group.day_key)dayKeys.add(group.day_key);
        for(const day of (group.day_keys||[]))if(day)dayKeys.add(day);
      }
      let fileCount=0,familyCount=0,reviewCount=0,withoutDate=0;
      for(const group of [...visibleEvents,...available]){
        fileCount+=Number(group.file_count||0);
        familyCount+=Number(group.family_count||0);
        reviewCount+=Number(group.review_required_count||0);
        if(!group.has_date && group.group_type!=="event")withoutDate+=Number(group.file_count||0);
      }

      return {
        job:items[0].data.job,
        jobs:items.map(item=>item.data.job),
        selected_job_ids:items.map(item=>item.jobId),
        statistics:{
          day_count:dayKeys.size,
          file_count:fileCount,
          family_count:familyCount,
          review_required_count:reviewCount,
          without_date_file_count:withoutDate
        },
        events:[...eventComponents.values(),...rawChildren],
        day_groups:available,
        time_segments:timeSegments,
        planning_overview:{
          event_groups:visibleEvents,
          available_day_groups:available,
          timeline_groups:timeline
        },
        released_archive_groups:released,
        archive_change_reviews:reviews
      };
    }

    async function loadJobs({physicalRefresh=false}={}) {
      const cacheKey = "bk-workspace-jobs-0452:" + (window.__bkLibraryId || "main");
      if (!jobs.length) {
        try {
          const saved = JSON.parse(sessionStorage.getItem(cacheKey) || "null");
          if (Array.isArray(saved?.jobs)) {
            jobs = saved.jobs.filter(job => ["metadata_fixture_analysis","folder_import","sd_import","metadata_general_import","metadata_multiple_import","trash_import"].includes(job.operation) && !(job.operation==="trash_import" && Number(job.total_family_count||0)===0));
            selectedJobIds = new Set(jobs.filter(job => job.workflow_status !== "archived").map(job => job.id));
            updateTechnicalAnchor(); renderBackupFilter();
            const ids = [...selectedJobIds];
            const snapshotKey = "bk-workspace-0452:" + (window.__bkLibraryId || "main") + ":" + ids.map(encodeURIComponent).join(",");
            const snap = JSON.parse(sessionStorage.getItem(snapshotKey) || "null");
            if (snap?.statistics && snap?.planning_overview) {
              workspace = snap; eventSuggestions = snap.event_suggestions || [];
              renderSummary(); renderEventSuggestions(); renderDays(); renderPlannedActions(); renderSelection();
            }
          }
        } catch (_) {}
      }
      if (!workspace?.statistics) setStatus("Arbeitsbestände werden geladen …");
      const data = await getJson("/api/jobs");
      try { sessionStorage.setItem(cacheKey, JSON.stringify(data)); } catch (_) {}
      const previous = new Set(selectedJobIds);

      jobs = (data.jobs || [])
        .filter(job => ["metadata_fixture_analysis","folder_import","sd_import","metadata_general_import","metadata_multiple_import","trash_import"].includes(job.operation) && !(job.operation==="trash_import" && Number(job.total_family_count||0)===0))
        .sort((a,b)=>String(b.created_at).localeCompare(String(a.created_at)));

      const active=jobs.filter(job=>job.workflow_status!=="archived");
      if(previous.size){
        selectedJobIds=new Set([...previous].filter(id=>jobs.some(job=>job.id===id)));
      }else{
        selectedJobIds=new Set(active.map(job=>job.id));
      }

      const requestedJob=new URLSearchParams(location.search).get("job");
      if(requestedJob && jobs.some(job=>job.id===requestedJob)){
        if(jobs.find(job=>job.id===requestedJob)?.workflow_status==="archived"){
          selectedJobIds.add(requestedJob);
        }
      }

      updateTechnicalAnchor(requestedJob || "");
      renderBackupFilter();

      if(!jobs.length){
        setStatus("Noch kein analysierter Arbeitsbestand vorhanden.");
        await loadWorkspace({physicalRefresh});
        return;
      }
      await loadWorkspace({physicalRefresh});
    }

    async function loadWorkspace({physicalRefresh=false}={}) {
      if (!globalFolderLayout) {
        try { globalFolderLayout = await getJson("/api/settings/event-folder-layout"); }
        catch (_) { globalFolderLayout = {structure_enabled:true,input_path:"Alle",layout:{version:1,nodes:[]}}; }
      }
      const ids=[...selectedJobIds].filter(id=>jobs.some(job=>job.id===id));
      selectedDays.clear();

      if(!ids.length){
        workspace=mergeWorkspacePayloads([]);
        eventSuggestions=[];
        renderSummary();
        renderEventSuggestions();
        renderDays();
        renderPlannedActions();
        renderSelection();
        setStatus("Keine Sicherung im Filter ausgewählt.");
        return;
      }

      const query=ids.map(encodeURIComponent).join(",");
      const snapshotKey = "bk-workspace-0452:" + (window.__bkLibraryId || "main") + ":" + query;
      if (!physicalRefresh) {
        try {
          const saved = JSON.parse(sessionStorage.getItem(snapshotKey) || "null");
          if (saved && saved.statistics && saved.planning_overview) {
            workspace = saved;
            eventSuggestions = saved.event_suggestions || [];
            renderSummary(); renderEventSuggestions(); renderDays();
            renderPlannedActions(); renderSelection();
          }
        } catch (_) {}
      }
      if (!workspace?.statistics || physicalRefresh) setStatus("Gemeinsamer Arbeitsbestand wird geladen …");
      statusElement.classList.add("bk-loading-status");
      try {
        workspace=await getJson(
          `/api/workspace/summary?jobs=${query}&physical_refresh=${physicalRefresh ? "true" : "false"}`
        );
      } finally {
        statusElement.classList.remove("bk-loading-status");
      }
      eventSuggestions=workspace.event_suggestions || [];
      try {
        const packed = JSON.stringify(workspace);
        if (packed.length < 1800000) sessionStorage.setItem(snapshotKey, packed);
      } catch (_) {}

      updateTechnicalAnchor(jobSelect.value);
      renderSummary();
      renderEventSuggestions();
      renderDays();
      renderPlannedActions();
      renderSelection();

      setStatus("");
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
          ? "Die neuen Aufnahmen werden der offenen Planung hinzugefügt."
          : item.target_status === "applied"
            ? "Die neuen Aufnahmen werden als sichere Ergänzung des angewendeten Ereignisses vorbereitet."
             : "Die neuen Aufnahmen werden über den geprüften Archivänderungsweg unter ‚Später zuordnen‘ vorbereitet.";
        const familyRows = (item.families || []).map(family => `
          <li><strong>${escapeHtml(family.original_stem || family.family_key || "Dateifamilie")}</strong>
          · ${escapeHtml(family.capture_time || "")}
          · ${Number(family.file_count || 0)} Dateien</li>`).join("");
        const familyIds = (item.family_ids || []).map(Number).filter(Number.isFinite);
        card.innerHTML = `
          <div class="suggestion-head">
            <div>
              <div class="suggestion-title">${Number(item.family_count || familyIds.length)} neue Familien passen zu ${escapeHtml(item.target_name)}</div>
              <div class="muted">Diese neuen Aufnahmen liegen vollständig im Zeitraum des bestehenden Ereignisses · Herkunft: ${escapeHtml(item.source_label || "Sicherung")}.</div>
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
            <button type="button" class="primary accept-suggestion" data-source-job-id="${escapeHtml(item.source_job_id || "")}" data-family-ids="${escapeHtml(JSON.stringify(familyIds))}" data-target-event-id="${escapeHtml(item.target_event_id)}">${escapeHtml(item.action_label)}</button>
          </div>`;
        eventSuggestionList.appendChild(card);
      }
    }

    function renderPlannedActions() {
      const allPlanned = (workspace?.events || []).filter(event =>
        event.event_level === "parent"
        && (event.status === "planned" || event.has_planned_component)
      );
      const reconcileTargets = allPlanned.filter(event => Boolean(Number(event.reconcile_target||0)));
      const planned = allPlanned.filter(event => !Boolean(Number(event.reconcile_target||0)));

      postSaveAction.hidden = allPlanned.length === 0;
      plannedEventSelection.innerHTML =
        planned.map(event => `
          <label class="planned-choice">
            <input class="planned-check" type="checkbox"
              data-planned-event="${escapeHtml(event.id)}"
              data-planned-components="${escapeHtml(JSON.stringify((event.component_events || [{job_id:event.job_id,event_id:event.id,status:event.status}]).filter(component=>component.status==="planned")))}"
              checked>
            <span><span data-bk-preserve-language>${escapeHtml(event.display_title || event.name)}</span> · <span>${Number(event.assigned_family_count || 0)} Familien${(event.component_events||[]).length>1?" · mehrere Sicherungen":""}</span></span>
          </label>`).join("")
        + reconcileTargets.map(event => `
          <div class="planned-choice">
            <span>↳</span>
            <span><strong data-bk-preserve-language>${escapeHtml(event.display_title || event.name)}</strong> · <span>Ziel einer offenen gemeinsamen Nachsortierung</span></span>
          </div>`).join("");

      const families = planned.reduce((sum,event)=>sum+Number(event.assigned_family_count||0),0);
      const files = planned.reduce((sum,event)=>sum+Number(event.assigned_file_count||0),0);

      applySavedEventButton.dataset.action = "apply";
      delete applySavedEventButton.dataset.reconcileSource;

      if (!planned.length && reconcileTargets.length) {
        const source = reconcileTargets.find(event=>event.reconcile_source_event_id)?.reconcile_source_event_id || "";
        postSaveTitle.textContent = reconcileTargets.length === 1
          ? "Gemeinsame Nachsortierung offen"
          : `${reconcileTargets.length} Ziele gehören zu offenen Nachsortierungen`;
        postSaveDetail.textContent = "Dieses geplante Ziel wird nicht separat angewendet. Es wird zusammen mit dem bearbeiteten Ursprungsereignis geprüft und angewendet.";
        applySavedEventButton.textContent = "Nachsortierung unter Ereignisse öffnen";
        applySavedEventButton.dataset.action = "reconcile";
        applySavedEventButton.dataset.reconcileSource = source;
        applySavedEventButton.disabled = !source;
        return;
      }

      postSaveTitle.textContent = planned.length === 1 ? "1 geplantes Ereignis" : `${planned.length} geplante Ereignisse`;
      postSaveDetail.textContent = `${families} Familien · ${files} Dateien. Standardmäßig werden alle unabhängigen geplanten Ereignisse angewendet.`
        + (reconcileTargets.length ? ` ${reconcileTargets.length} Ziel(e) einer offenen Nachsortierung sind davon ausgenommen und werden gemeinsam reconciled.` : "");
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


    function setSelectedPreviewEvent(eventId) {
      selectedPreviewEventId = eventId || null;
      document.querySelectorAll("[data-preview-event-id]").forEach(node => {
        node.classList.toggle(
          "selected-preview",
          Boolean(selectedPreviewEventId)
          && node.dataset.previewEventId === selectedPreviewEventId
        );
      });
    }


    function formatStoredDateTime(value) {
      const raw = String(value || "");
      if (!raw) return "–";
      const date = new Date(raw);
      if (Number.isNaN(date.getTime())) return raw.replace("T", ", ");
      const locale = document.documentElement.lang || navigator.language || "de-DE";
      return new Intl.DateTimeFormat(locale, {
        day:"2-digit",
        month:"2-digit",
        year:"numeric",
        hour:"2-digit",
        minute:"2-digit"
      }).format(date);
    }


    function bk0511PreviewLabel(german, english) {
      return document.documentElement.dataset.bkLocale === "de" ? german : english;
    }

    function renderStoredEventPreview(data) {
      const event = data?.event || {};
      const start = String(event.start_datetime || "");
      const end = String(event.end_datetime || "");
      const status = workspaceStatusLabel(event.status || "");
      const kind = event.event_kind === "no_event"
        ? bk0511PreviewLabel("Ohne Ereignis", "Unassigned")
        : bk0511PreviewLabel("Ereignis", "Event");
      const subfolders = event.folder_layout?.structure_enabled === false
        ? bk0511PreviewLabel("Direkt im Ereignis", "Directly in event")
        : bk0511PreviewLabel("Unterordnerstruktur aktiv", "Subfolder structure enabled");
      const dayFolders = event.preserve_day_folders
        ? bk0511PreviewLabel("Tagesordner bleiben erhalten", "Day folders preserved")
        : bk0511PreviewLabel("Ohne Tagesunterordner", "Without day subfolders");
      const childCount = Array.isArray(event.child_events) ? event.child_events.length : 0;
      const segmentCount = Array.isArray(event.time_segments) ? event.time_segments.length : 0;
      const details = [
        event.event_kind === "no_event"
          ? `<div><strong>${bk0511PreviewLabel("Datenbank-Zeitraum:", "Database period:")}</strong> ${bk0511PreviewLabel("mehrere gespeicherte Zeitsegmente", "multiple saved time segments")}</div>`
          : `<div><strong>${bk0511PreviewLabel("Datenbank-Zeitraum:", "Database period:")}</strong> ${bk0511PreviewLabel("von", "from")} ${escapeHtml(formatStoredDateTime(start))} ${bk0511PreviewLabel("bis", "to")} ${escapeHtml(formatStoredDateTime(end))}</div>`,
        `<div><strong>${bk0511PreviewLabel("Status:", "Status:")}</strong> ${escapeHtml(bk0511PreviewLabel(status, window.BibliothekarI18n?.t?.(status) || status))} · ${escapeHtml(kind)}</div>`,
        `<div><strong>${bk0511PreviewLabel("Ordnerlogik:", "Folder logic:")}</strong> ${escapeHtml(dayFolders)} · ${escapeHtml(subfolders)}</div>`,
        `<div><strong>${bk0511PreviewLabel("Zugeordnet:", "Assigned:")}</strong> ${Number(event.assigned_family_count || 0)} ${bk0511PreviewLabel("Familien", "families")}</div>`
      ];
      if (childCount) {
        details.push(`<div><strong>${bk0511PreviewLabel("Unterereignisse:", "Subevents:")}</strong> ${childCount}</div>`);
      }
      if (segmentCount) {
        details.push(`<div><strong>${bk0511PreviewLabel("Zeitsegmente:", "Time segments:")}</strong> ${segmentCount}</div>`);
      }
      const physical=data?.physical_state||{};
      const available=physical.available===true;
      const actualTree=available
        ? String(physical.tree_text||bk0511PreviewLabel("(keine Unterordner gefunden)","(no subfolders found)"))
        : String(physical.reason||bk0511PreviewLabel("Physischer Bestand nicht prüfbar","Physical inventory unavailable"));
      const observedPaths=new Set(physical.directories||[]);
      const removed=(physical.directory_removed||[]).filter(path=>!observedPaths.has(String(path)));
      const added=(physical.directory_added||[]).filter(path=>!removed.includes(String(path)));
      const discrepancy=available && (removed.length>0 || added.length>0);
      const note=discrepancy
        ? `<div class="muted" role="status">${bk0511PreviewLabel("Physische Abweichung vom gespeicherten Ordnerlayout erkannt.","Physical directory layout differs from the saved event layout.")}`
           + (removed.length ? `<div>${bk0511PreviewLabel("Fehlende Sollordner:","Missing expected folders:")} <code>${escapeHtml(removed.join(", "))}</code></div>` : "")
           + (added.length ? `<div>${bk0511PreviewLabel("Zusätzliche IST-Ordner:","Additional physical folders:")} <code>${escapeHtml(added.join(", "))}</code></div>` : "")
           + `</div>` : "";
      structurePreview.classList.add("rich-preview");
      structurePreview.innerHTML =
        `<div class="preview-root-title" data-bk-preserve-language>${escapeHtml(event.name || "Gespeichertes Ereignis")}</div>`
        + `<div class="stored-preview-meta">${details.join("")}</div>`
        + `<div class="stored-preview-meta"><strong>${bk0511PreviewLabel("Physischer IST-Bestand","Physical actual inventory")}</strong></div>`
        + `<pre class="structure-lines">${escapeHtml(actualTree)}</pre>`
        + note;
      previewBody.hidden = false;
      scheduleTreeFit(structurePreview);
    }


    async function openStoredEventPreview(eventId, ownerJobId = "") {
      const previewJobId=ownerJobId || jobSelect.value;
      if (!eventId || !previewJobId) return;
      setSelectedPreviewEvent(eventId);
      structurePreview.classList.add("rich-preview");
      structurePreview.innerHTML = '<span class="muted">Ereignisstruktur wird geladen …</span>';
      previewBody.hidden = false;
      try {
        const data = await getJson(
          `/api/jobs/${encodeURIComponent(previewJobId)}/events/${encodeURIComponent(eventId)}/structure`
        );
        if (selectedPreviewEventId === eventId) {
          renderStoredEventPreview(data);
        }
      } catch (error) {
        if (selectedPreviewEventId === eventId) {
          structurePreview.classList.remove("rich-preview");
          structurePreview.textContent = error.message;
        }
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


    function releasedArchiveGroups() {
      return Array.isArray(workspace?.released_archive_groups)
        ? workspace.released_archive_groups
        : [];
    }

    function availableDayGroups() {
      const regular = (
        planningOverview()
          .available_day_groups
        || []
      );
      return [...regular, ...releasedArchiveGroups()];
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
          (document.documentElement.lang === "de" ? "de-DE" : "en-US"),
          {
            day: "2-digit",
            month: "2-digit"
          }
        )
        + "–"
        + endDate.toLocaleDateString(
          (document.documentElement.lang === "de" ? "de-DE" : "en-US"),
          {
            day: "2-digit",
            month: "2-digit",
            year: "numeric"
          }
        )
      );
    }


    function selectableDayKeys() {
      return availableDayGroups()
        .filter(group => group.has_date)
        .map(group => group.card_key || group.day_key);
    }

    function updateDaySelectAllButton() {
      if (typeof daySelectAllButton === "undefined" || !daySelectAllButton) return;
      const keys = selectableDayKeys();
      const allSelected = keys.length > 0 && keys.every(key => selectedDays.has(key));
      daySelectAllButton.textContent = allSelected ? "Auswahl aufheben" : "Alle auswählen";
      daySelectAllButton.disabled = keys.length === 0;
    }

    function selectDayRange(targetKey, checked) {
      const keys = selectableDayKeys();
      const targetIndex = keys.indexOf(targetKey);
      const anchorIndex = keys.indexOf(lastSelectedDayKey);
      if (targetIndex < 0 || anchorIndex < 0) {
        if (checked) selectedDays.add(targetKey);
        else selectedDays.delete(targetKey);
        return;
      }
      const start = Math.min(anchorIndex, targetIndex);
      const end = Math.max(anchorIndex, targetIndex);
      for (let index = start; index <= end; index += 1) {
        if (checked) selectedDays.add(keys[index]);
        else selectedDays.delete(keys[index]);
      }
    }


    function renderDays() {
      dayList.innerHTML = "";

      const timelineGroups =
        planningOverview()
          .timeline_groups
        || [];
      const releasedGroups = releasedArchiveGroups();
      const groups = releasedGroups.length
        ? [
            ...timelineGroups,
            {group_type:"released_archive_separator"},
            ...releasedGroups
          ]
        : timelineGroups;

      if (!groups.length) {
        dayList.innerHTML =
          '<div class="empty">'
          + "Alle Aufnahmen sind zugeordnet und archiviert oder durch den Sicherungsfilter ausgeblendet."
          + "</div>";

        updateDaySelectAllButton();
        return;
      }

      const availableKeys =
        new Set(selectableDayKeys());

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
        if (group.group_type === "released_archive_separator") {
          const separator=document.createElement("div");
          separator.style.cssText="margin:16px 0 8px;padding-top:14px;border-top:1px solid var(--border)";
          separator.innerHTML='<div style="display:flex;align-items:center;gap:7px;font-weight:700">Freigewordene Archivaufnahmen <button class="bk-help" type="button" aria-label="Hinweis zu freigewordenen Archivaufnahmen" data-help="Sicher aus dem Archiv auf die SSD zurückgeholter freier Bestand.">?</button></div>';
          dayList.appendChild(separator);
          continue;
        }

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
          card.dataset.previewEventId = group.event_id;
          card.dataset.previewJobId = group.job_id || "";
          card.style.cursor="pointer";
          card.addEventListener("click",()=>{
            openStoredEventPreview(group.event_id, group.job_id || jobSelect.value);
          });

          const range =
            formatTimelineDateRange(
              group.start_datetime,
              group.end_datetime
            );

          const pendingSortBadge =
            group.status === "applied" && Boolean(group.resort_required)
              ? '<span class="badge warning">Nachsortierung ausstehend</span>'
              : "";

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

              <div class="timeline-event-statuses">
                <span class="badge success">
                  ${escapeHtml(
                    workspaceStatusLabel(group.status)
                  )}
                </span>
                ${pendingSortBadge}
              </div>
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

        if (!group.has_date) {
          const card = document.createElement("article");
          card.className = "day-card without-date review-card";
          card.tabIndex = 0;
          card.setAttribute("role", "button");
          card.setAttribute(
            "aria-label",
            "Prüffälle ohne Datum – Metadatenkorrektur öffnen"
          );

          const main = document.createElement("span");
          main.className = "day-main";

          const name = document.createElement("span");
          name.className = "day-name";
          name.textContent = "Prüffälle · Ohne Datum";

          const metadata = document.createElement("span");
          metadata.className = "day-meta";
          metadata.innerHTML = `
            <span>${Number(group.file_count || 0)} Dateien</span>
            <span>${Number(group.family_count || 0)} Familien</span>
            <span>${formatBytes(Number(group.total_size_bytes || 0))}</span>
          `;

          const hint = document.createElement("span");
          hint.className = "review-card-hint";
          hint.textContent =
            "Nicht für Ereignisse auswählbar · Doppelklick öffnet die Metadatenkorrektur";

          main.appendChild(name);
          main.appendChild(metadata);
          main.appendChild(hint);

          const reviewCount = Number(group.review_required_count || 0);
          const badge = document.createElement("span");
          badge.className = "badge warning";
          badge.textContent =
            reviewCount === 1
              ? "1 Prüffall"
              : `${reviewCount} Prüffälle`;

          const showReviewPreview = () => {
            selectedDays.clear();
            lastSelectedDayKey = null;
            setSelectedPreviewEvent(null);
            renderDays();
            renderSelection();

            selectionLabel.textContent = "Prüffälle";
            newEventButton.disabled = true;
            noEventButton.disabled = true;
            existingNoEventButton.disabled = true;

            structurePreview.classList.add("rich-preview");
            structurePreview.innerHTML = `
              <div class="metadata-review-preview">
                <div class="preview-root-title">Prüffälle · Ohne Datum</div>
                <div class="preview-selection-note">
                  Diese Dateien besitzen noch kein belastbares Aufnahmedatum
                  und können deshalb keinem Ereignis zugeordnet werden.
                </div>
                <div class="preview-selection-note">
                  <strong>${Number(group.file_count || 0)} Dateien ·
                  ${Number(group.family_count || 0)} Familien</strong>
                  ${reviewCount ? ` · ${reviewCount} Prüffälle` : ""}
                </div>
                <button type="button" class="primary" data-open-metadata-review>
                  Metadatenkorrektur
                </button>
              </div>
            `;
            structurePreview
              .querySelector("[data-open-metadata-review]")
              ?.addEventListener("click", () => {
                location.href = "/metadata-correction?area=library";
              });
          };

          card.addEventListener("click", showReviewPreview);
          card.addEventListener("dblclick", () => {
            location.href = "/metadata-correction?area=library";
          });
          card.addEventListener("keydown", event => {
            if (event.key === "Enter" || event.key === " ") {
              event.preventDefault();
              showReviewPreview();
            }
          });

          card.appendChild(main);
          card.appendChild(badge);
          dayList.appendChild(card);
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
        card.dataset.bkPwaSelect = "workspace-capture";
        card.dataset.bkPwaKey = key;
        card.dataset.bkSelectionKey = key;
        if (group.released_archive) {
          card.classList.add("released-archive-card");
        }

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

        card.addEventListener("bk:pwa-select", event => {
          const phase = String(event.detail?.phase || "");
          if (phase === "end") {
            renderDays();
            renderSelection();
            return;
          }

          const desired = phase === "set"
            ? Boolean(event.detail?.selected)
            : true;
          if (desired) selectedDays.add(key);
          else selectedDays.delete(key);

          checkbox.checked = desired;
          card.classList.toggle("selected", desired);
          lastSelectedDayKey = key;
          updateDaySelectAllButton();
          renderSelection();
        });

        checkbox.addEventListener(
          "click",
          async event => {
            event.stopPropagation();
            if (event.shiftKey && lastSelectedDayKey) {
              selectDayRange(key, checkbox.checked);
            } else if (checkbox.checked) {
              selectedDays.add(key);
            } else {
              selectedDays.delete(key);
            }
            lastSelectedDayKey = key;

            renderDays();
            renderSelection();
          }
        );

        card.addEventListener("mousedown", event => {
          if (event.shiftKey && event.target !== checkbox) {
            event.preventDefault();
          }
        });

        card.addEventListener("click", event => {
          if (event.target === checkbox) return;
          event.preventDefault();
          const nextChecked = event.shiftKey ? true : !selectedDays.has(key);
          if (event.shiftKey && lastSelectedDayKey) {
            selectDayRange(key, nextChecked);
          } else if (nextChecked) {
            selectedDays.add(key);
          } else {
            selectedDays.delete(key);
          }
          lastSelectedDayKey = key;
          renderDays();
          renderSelection();
        });

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
        if (group.released_archive) {
          const marker=document.createElement("span");
          marker.className="badge warning";
          marker.textContent="Aus Archiv freigeworden";
          marker.style.marginLeft="8px";
          name.appendChild(marker);
        }
        if (group.reassignment_pending || group.released_free) {
          const marker=document.createElement("span");
          marker.textContent="●";
          marker.title=group.reassignment_pending
            ? "Offene Neu-Zuordnung"
            : "Freigegeben durch Applied-Änderung";
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
      updateDaySelectAllButton();
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
        if (!selectedPreviewEventId) {
          structurePreview.classList.remove("rich-preview");
          structurePreview.textContent =
            "Noch keine Auswahl.";
        }

        return;
      }

      setSelectedPreviewEvent(null);
      structurePreview.classList.remove("rich-preview");

      const dated =
        selectedDatedGroups();

      let preview =
        '<div class="preview-root-title">' + (document.documentElement.dataset.bkLocale==="de" ? "Arbeitsbestand" : "Workspace inventory") + '</div><div class="preview-days">';

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
          `<div class="preview-selection-note"><strong>${document.documentElement.dataset.bkLocale==="de" ? "Auswahlzeitraum:" : "Selection period:"}</strong> <span class="preview-period-dates">${escapeHtml(dated[0].day_key)} ${document.documentElement.dataset.bkLocale==="de" ? "bis" : "to"} ${escapeHtml(dated[dated.length - 1].day_key)}</span></div>`;
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

    function activeNoEventMonthKey(fallbackDay="") {
      const candidates=[
        activeNoEventTarget?.month_key,
        activeNoEventTarget?.start_datetime,
        fallbackDay,
        eventStartDate?.value,
        eventEndDate?.value,
      ];
      for(const value of candidates){
        const m=String(value||"").match(/^(\d{4}-\d{2})/);
        if(m)return m[1];
      }
      return "";
    }

    function daysInMonth(monthKey) {
      const m=String(monthKey||"").match(/^(\d{4})-(\d{2})$/);
      if (!m) return 31;
      return new Date(Number(m[1]), Number(m[2]), 0).getDate();
    }

    function lockedMonthDayControls(dayKey, locked) {
      const monthKey=activeNoEventMonthKey(dayKey) || String(dayKey||"").slice(0,7);
      if (!/^\d{4}-\d{2}$/.test(monthKey)) {
        return `<label class="no-event-day-field"><span class="no-event-desktop-caption">Tag</span><select data-segment-day ${locked?"disabled":""}><option value="${escapeHtml(dayKey)}">${escapeHtml(String(dayKey||"").slice(8,10)||"—")}</option></select></label>`;
      }
      const maxDay=daysInMonth(monthKey);
      const fallback=`${monthKey}-01`;
      const current=String(dayKey||"").startsWith(monthKey+"-") ? String(dayKey) : fallback;
      const options=Array.from({length:maxDay},(_,index)=>{
        const day=String(index+1).padStart(2,"0");
        const value=`${monthKey}-${day}`;
        return `<option value="${escapeHtml(value)}" ${value===current?"selected":""}>${day}</option>`;
      }).join("");
      return `<label class="no-event-day-field"><span class="no-event-desktop-caption">Tag</span><span class="no-event-day-controls"><select data-segment-day data-locked-month="${escapeHtml(monthKey)}" ${locked?"disabled":""}>${options}</select><input type="text" value="${escapeHtml(monthYearForIso(current))}" disabled aria-label="Monat und Jahr"></span></label>`;
    }

    function noEventDateMirror(dayKey) {
      const value=String(dayKey||"");
      const day=value.slice(8,10)||"—";
      const monthYear=monthYearForIso(value);
      return `<div class="no-event-end-date-mirror" aria-label="Enddatum"><input type="text" data-segment-end-day-display value="${escapeHtml(day)}" disabled aria-label="Tag"><input type="text" data-segment-end-month-year-display value="${escapeHtml(monthYear)}" disabled aria-label="Monat und Jahr"></div>`;
    }

    function syncNoEventDateMirror(row) {
      if(!row)return;
      const control=row.querySelector("[data-segment-day]");
      if(!control)return;
      const value=String(control.value||"");
      const dayDisplay=row.querySelector("[data-segment-end-day-display]");
      const monthDisplay=row.querySelector("[data-segment-end-month-year-display]");
      if(dayDisplay)dayDisplay.value=value.slice(8,10)||"—";
      if(monthDisplay)monthDisplay.value=monthYearForIso(value);
    }

    function segmentRowHtml(day) {
      const dayKey=day.day_key||"",start=day.start_time||"00:00",end=day.end_time||"23:59",count=Number(day.family_count||0);
      const existing=Boolean(day._existing||day.existing_segment||day._locked||day.locked),isNew=Boolean(day._new||day.new_segment);
      if(existing)return `<div data-no-event-segment data-day-key="${escapeHtml(dayKey)}" data-start-time="${escapeHtml(start)}" data-end-time="${escapeHtml(end)}" data-locked="1" data-new-segment="0" data-existing-segment="1" class="existing-segment-static"><strong>${escapeHtml(dayKey)} · BESTEHEND</strong><span class="muted">${escapeHtml(start)}–${escapeHtml(end)}${count?` · ${count} Familien`:""}</span></div>`;
      return `<details data-no-event-segment data-day-key="${escapeHtml(dayKey)}" data-start-time="${escapeHtml(start)}" data-end-time="${escapeHtml(end)}" data-locked="0" data-new-segment="${isNew?"1":"0"}" data-existing-segment="0" class="card collapse-card" style="padding:8px 10px;${isNew?"border:2px solid currentColor;":""}"><summary style="display:flex;justify-content:space-between;gap:8px;align-items:center;cursor:pointer"><strong>${escapeHtml(dayKey||"Neues Segment")}${isNew?" · NEU":""}</strong><span class="muted">${escapeHtml(start)}–${escapeHtml(end)}${count?` · ${count} freie Familien`:""}</span></summary><div class="no-event-segment-fields"><div class="no-event-mobile-range-title">Von–Bis</div>${lockedMonthDayControls(dayKey,false)}<label class="no-event-start-field"><span class="no-event-desktop-caption">Von</span><input data-segment-start type="time" value="${escapeHtml(start)}" aria-label="Von"></label>${noEventDateMirror(dayKey)}<label class="no-event-end-field"><span class="no-event-desktop-caption">Bis</span><input data-segment-end type="time" value="${escapeHtml(end)}" aria-label="Bis"></label><button type="button" class="danger-button no-event-segment-remove" data-remove-no-event-segment>Entfernen</button></div></details>`;
    }

    function syncNoEventRangeDisplayFromSegments(){
      const segs=selectedNoEventSegments(true);
      if(segs.length){
        eventStartDate.value=segs[0].day_key;
        eventEndDate.value=segs[segs.length-1].day_key;
      }
      if(["no_event","existing_no_event"].includes(dialogMode)){
        const months=[...new Set(segs.map(seg=>String(seg.day_key||"").slice(0,7)).filter(Boolean))];
        eventName.value=noEventLabel;
        if(months.length>1){
          dialogError.hidden=false;
          dialogError.textContent="„Ohne Ereignis“ darf nur innerhalb eines Kalendermonats angelegt werden. Bitte die Monate getrennt zuordnen.";
          dialogError.dataset.monthRangeError="1";
          saveEventButton.disabled=true;
        }else{
          if(dialogError.dataset.monthRangeError==="1"){
            dialogError.hidden=true;
            dialogError.textContent="";
            delete dialogError.dataset.monthRangeError;
          }
          saveEventButton.disabled=false;
        }
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
      noEventSegmentList.querySelectorAll("[data-segment-day]").forEach(input => {
        input.dataset.lastValid=input.value||"";
        input.onchange = () => {
          const month=String(input.dataset.lockedMonth||"");
          if(month && input.value){
            const min=`${month}-01`;
            const max=`${month}-${String(daysInMonth(month)).padStart(2,"0")}`;
            if(input.value < min) input.value=min;
            if(input.value > max) input.value=max;
            if(!input.value.startsWith(month+"-")){
              input.value=input.dataset.lastValid||min;
            }
          }
          input.dataset.lastValid=input.value||"";
          const row=input.closest("[data-no-event-segment]");
          if(row && input.value) row.dataset.dayKey=input.value;
          syncNoEventDateMirror(row);
          syncNoEventRangeDisplayFromSegments();
        };
        syncNoEventDateMirror(input.closest("[data-no-event-segment]"));
      });
      noEventSegmentList.querySelectorAll("[data-segment-start],[data-segment-end]").forEach(input => {
        input.onchange = () => syncNoEventRangeDisplayFromSegments();
      });
    }

    function renderNoEventSegmentEditor(days) {
      noEventSegmentList.innerHTML = (days || []).map(day => segmentRowHtml(day)).join("");
      bindNoEventSegmentRows();
      syncNoEventRangeDisplayFromSegments();
      scheduleDialogPreview();
    }

    function monthKeysForNoEventDialog() {
      const values=selectedNoEventSegments(true).map(seg=>String(seg.day_key||"").slice(0,7)).filter(Boolean);
      for (const value of [eventStartDate.value,eventEndDate.value]) if (/^\d{4}-\d{2}-\d{2}$/.test(value||"")) values.push(value.slice(0,7));
      return [...new Set(values)];
    }

    function activateNoEventTarget(target) {
      activeNoEventTarget=target || null;
      if (!activeNoEventTarget) {
        dialogTitle.textContent="Als „"+noEventLabel+"“ zuordnen";
        return;
      }
      dialogTitle.textContent="„"+noEventLabel+"“ fortführen";
      const currentNew=selectedNoEventSegments(false).filter(seg=>!seg._existing).map(seg=>({...seg,_new:true}));
      const existing=(activeNoEventTarget.segments||[]).map(seg=>({
        day_key:seg.day_key,start_time:seg.start_time,end_time:seg.end_time,
        _locked:true,_existing:true
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
          dialogTitle.textContent="Als „"+noEventLabel+"“ zuordnen";
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

    function applyAutomaticFreeTimeSuggestion(dated) {
      if (!dated.length) return;
      const ordered=[...dated].sort((a,b)=>String(a.start_datetime).localeCompare(String(b.start_datetime)));
      eventStartTime.value=ordered[0].start_time || String(ordered[0].start_datetime||"").slice(11,16) || "00:00";
      eventEndTime.value=ordered[ordered.length-1].end_time || String(ordered[ordered.length-1].end_datetime||"").slice(11,16) || "23:59";
      useTimeRange.checked=true;
      setParentTimeFieldsVisible(true);
    }

    async function openTaskReassignment(eventId) {
      const jobId = jobSelect.value;
      if (!jobId) throw new Error("Keine Sicherung ausgewählt.");
      // 0.24.1: one canonical reassignment dialog lives on the Ereignisse page.
      // It sends exact persisted segments and exposes the complete target model.
      location.href = `/events?job=${encodeURIComponent(jobId)}&task=reassign:${encodeURIComponent(eventId)}`;
    }

    taskReassignClose?.addEventListener("click",()=>taskReassignDialog.close());

    function extensionSelectionForParent(parent, dated) {
      if (!parent || !dated.length) return null;
      const ordered=[...dated].sort((a,b)=>String(a.start_datetime).localeCompare(String(b.start_datetime)));
      for(let index=1;index<ordered.length;index+=1){
        const previousEnd=Date.parse(String(ordered[index-1].end_datetime||""));
        const currentStart=Date.parse(String(ordered[index].start_datetime||""));
        if(!Number.isFinite(previousEnd)||!Number.isFinite(currentStart)||currentStart-previousEnd!==1000) return null;
      }
      const extensionStart=String(ordered[0].start_datetime||"").slice(0,19);
      const extensionEnd=String(ordered[ordered.length-1].end_datetime||"").slice(0,19);
      const parentStart=String(parent.start_datetime||"").slice(0,19);
      const parentEnd=String(parent.end_datetime||"").slice(0,19);
      const extensionStartMs=Date.parse(extensionStart);
      const extensionEndMs=Date.parse(extensionEnd);
      const parentStartMs=Date.parse(parentStart);
      const parentEndMs=Date.parse(parentEnd);
      if (![extensionStartMs,extensionEndMs,parentStartMs,parentEndMs].every(Number.isFinite)) return null;
      let direction="";
      if(extensionStartMs-parentEndMs===1000) direction="after";
      else if(parentStartMs-extensionEndMs===1000) direction="before";
      else return null;
      return {
        direction,
        start_datetime:extensionStart,
        end_datetime:extensionEnd,
        start_date:extensionStart.slice(0,10),
        end_date:extensionEnd.slice(0,10),
        start_time:extensionStart.slice(11,16)||"00:00",
        end_time:extensionEnd.slice(11,16)||"23:59",
        parent_start:parentStart,
        parent_end:parentEnd,
      };
    }

    function plannedParentCandidates(dated) {
      if (!workspace || !dated.length) return [];
      if (dated.some(group => Boolean(group.reassignment_pending))) return [];
      const sourceJobs=new Set(dated.flatMap(group=>group.source_job_ids || [group.job_id]).filter(Boolean));
      if(sourceJobs.size!==1)return [];
      const sourceJob=[...sourceJobs][0];
      return (workspace.events || []).filter(event =>
        event.event_level === "parent"
        && event.event_kind === "event"
        && String(event.job_id||"")===String(sourceJob)
        && (dated[0].archive_change_request_id
          ? event.status === "archived"
          : ["planned","applied","archived"].includes(event.status))
        && extensionSelectionForParent(event,dated)
      );
    }

    function renderExistingSubeventCards(parent) {
      const children=(workspace?.events||[])
        .filter(event=>event.parent_event_id===parent.id)
        .sort((a,b)=>String(a.start_datetime||"").localeCompare(String(b.start_datetime||"")));
      for(const child of children){
        const row=document.createElement("details");
        row.className="create-subevent-card";
        row.dataset.existingSubevent="1";
        const sd=String(child.start_datetime||"").slice(0,10);
        const st=String(child.start_datetime||"").slice(11,16);
        const ed=String(child.end_datetime||"").slice(0,10);
        const et=String(child.end_datetime||"").slice(11,16);
        row.innerHTML=`<summary style="cursor:pointer"><strong>${escapeHtml(child.name||"Unterereignis")}</strong> <span class="muted">· Bestehend</span></summary><div class="create-subevent-grid" style="margin-top:9px"><div class="create-subevent-top"><label class="create-subevent-name"><span>Name</span><input value="${escapeHtml(child.name||"")}" disabled></label></div><div class="create-subevent-boundaries"><div class="create-subevent-boundary"><label><span>Beginn</span><input type="date" value="${escapeHtml(sd)}" disabled></label><label><span>Startzeit</span><input type="time" value="${escapeHtml(st)}" disabled></label></div><div class="create-subevent-boundary"><label><span>Ende</span><input type="date" value="${escapeHtml(ed)}" disabled></label><label><span>Endzeit</span><input type="time" value="${escapeHtml(et)}" disabled></label></div></div></div>`;
        createSubeventList.appendChild(row);
      }
    }

    function applyExistingParentChoice() {
      const id=existingParentEvent?.value || "";
      const parent=(workspace?.events||[]).find(event=>event.id===id);
      const dated=[...selectedDatedGroups()].sort((a,b)=>String(a.start_datetime).localeCompare(String(b.start_datetime)));

      if (!parent) {
        activeExtension=null;
        dialogTitle.textContent="Ereignis erstellen";
        eventName.disabled=false;
        eventStartDate.disabled=false;
        eventStartTime.disabled=false;
        eventEndDate.disabled=false;
        eventEndTime.disabled=false;
        eventStartDate.removeAttribute("min");
        eventStartDate.removeAttribute("max");
        eventEndDate.removeAttribute("min");
        eventEndDate.removeAttribute("max");
        useTimeRange.checked=true;
        useTimeRange.disabled=true;
        preserveDayFolders.disabled=false;
        preserveDayFoldersRow.hidden=false;
        createSubevents.hidden=false;
        createSubeventHeading.textContent="Unterereignisse (optional)";
        createSubeventList.innerHTML="";
        updateSubeventPrefixToggle();
        if (dated.length) {
          eventStartDate.value=dated[0].day_key || String(dated[0].start_datetime||"").slice(0,10);
          eventEndDate.value=dated[dated.length-1].day_key || String(dated[dated.length-1].end_datetime||"").slice(0,10);
          applyAutomaticFreeTimeSuggestion(dated);
        }
        setParentTimeFieldsVisible(true);
        scheduleDialogPreview();
        return;
      }

      const extension=extensionSelectionForParent(parent,dated);
      if(!extension){
        dialogError.hidden=false;
        dialogError.textContent="Die ausgewählte freie Zeit grenzt nicht zusammenhängend an dieses Ereignis an.";
        return;
      }
      activeExtension=extension;
      dialogError.hidden=true;
      dialogError.textContent="";
      const parentStart=extension.parent_start;
      const parentEnd=extension.parent_end;

      dialogTitle.textContent="Ereignis erweitern";
      eventName.value=parent.display_title || parent.name || "";
      eventName.disabled=true;
      createSubeventList.innerHTML="";
      renderExistingSubeventCards(parent);
      updateSubeventPrefixToggle();

      useTimeRange.checked=true;
      useTimeRange.disabled=true;
      setParentTimeFieldsVisible(true);

      eventStartDate.removeAttribute("min");
      eventStartDate.removeAttribute("max");
      eventEndDate.removeAttribute("min");
      eventEndDate.removeAttribute("max");

      if(extension.direction==="after"){
        eventStartDate.value=parentStart.slice(0,10);
        eventStartTime.value=parentStart.slice(11,16)||"00:00";
        eventStartDate.disabled=true;
        eventStartTime.disabled=true;

        eventEndDate.value=extension.end_date;
        eventEndTime.value=extension.end_time;
        eventEndDate.disabled=false;
        eventEndTime.disabled=false;
        eventEndDate.min=extension.start_date;
        eventEndDate.max=extension.end_date;
      }else{
        eventEndDate.value=parentEnd.slice(0,10);
        eventEndTime.value=parentEnd.slice(11,16)||"23:59";
        eventEndDate.disabled=true;
        eventEndTime.disabled=true;

        eventStartDate.value=extension.start_date;
        eventStartTime.value=extension.start_time;
        eventStartDate.disabled=false;
        eventStartTime.disabled=false;
        eventStartDate.min=extension.start_date;
        eventStartDate.max=extension.end_date;
      }

      preserveDayFolders.checked=Boolean(parent.preserve_day_folders);
      preserveDayFolders.disabled=true;
      preserveDayFoldersRow.hidden=true;

      createSubevents.hidden=false;
      createSubeventHeading.textContent="Unterereignisse";
      scheduleDialogPreview();
    }

    function setParentTimeFieldsVisible(visible){
      eventStartTimeLabel.hidden=false;
      eventEndTimeLabel.hidden=false;
    }

    function subeventBounds(){
      const minDate=activeExtension?.start_date || eventStartDate.value || "";
      const maxDate=activeExtension?.end_date || eventEndDate.value || minDate;
      const minTime=activeExtension?.start_time
        || (minDate===eventStartDate.value ? (eventStartTime.value||"00:00") : "00:00");
      const maxTime=activeExtension?.end_time
        || (maxDate===eventEndDate.value ? (eventEndTime.value||"23:59") : "23:59");
      return {minDate,maxDate,minTime,maxTime};
    }

    function shiftIsoDay(value,amount){
      if(!/^\d{4}-\d{2}-\d{2}$/.test(String(value||""))) return "";
      const date=new Date(`${value}T12:00:00`);
      date.setDate(date.getDate()+amount);
      const y=date.getFullYear();
      const m=String(date.getMonth()+1).padStart(2,"0");
      const d=String(date.getDate()).padStart(2,"0");
      return `${y}-${m}-${d}`;
    }

    function subeventAllowedDays(){
      const {minDate,maxDate}=subeventBounds();
      if(!minDate||!maxDate||minDate>maxDate) return [];
      const result=[];
      let current=minDate;
      for(let guard=0;guard<3700 && current<=maxDate;guard+=1){
        result.push(current);
        current=shiftIsoDay(current,1);
      }
      return result;
    }

    function monthYearForIso(value){
      const m=String(value||"").match(/^(\d{4})-(\d{2})-(\d{2})$/);
      return m ? `${m[2]}.${m[1]}` : "";
    }

    function subeventDayOptions(selected){
      const days=subeventAllowedDays();
      return days.map(day=>{
        const label=day.slice(8,10);
        return `<option value="${escapeHtml(day)}" ${day===selected?"selected":""}>${escapeHtml(label)}</option>`;
      }).join("");
    }

    function subeventDayControl(attribute, displayAttribute, selected, label){
      const bounds=subeventBounds();
      const days=subeventAllowedDays();
      const current=days.includes(selected) ? selected : (days[0]||selected||"");
      return `<label><span>${escapeHtml(label)}</span><input ${attribute} type="date" min="${escapeHtml(bounds.minDate||"")}" max="${escapeHtml(bounds.maxDate||"")}" value="${escapeHtml(current)}"></label>`;
    }
    function minuteAfter(value){
      const match=/^(\d{2}):(\d{2})$/.exec(String(value||""));
      if(!match)return null;
      const total=Number(match[1])*60+Number(match[2])+1;
      if(total>=24*60)return null;
      return `${String(Math.floor(total/60)).padStart(2,"0")}:${String(total%60).padStart(2,"0")}`;
    }

    function nextSubeventDefaults(){
      const bounds=subeventBounds();
      if(!bounds.minDate||!bounds.maxDate)return null;
      const rows=[...createSubeventList.querySelectorAll("[data-create-subevent]")];
      if(!rows.length){
        return {
          start_date:bounds.minDate,
          start_time:bounds.minTime||"00:00",
          end_date:bounds.minDate,
          end_time:bounds.minDate===bounds.maxDate ? (bounds.maxTime||"23:59") : "23:59",
        };
      }

      const previous=rows[rows.length-1];
      const previousDay=previous.querySelector("[data-create-child-end-date]")?.value||bounds.minDate;
      const previousTime=previous.querySelector("[data-create-child-end-time]")?.value||"23:59";
      let startDate=previousDay;
      let startTime=minuteAfter(previousTime);
      if(!startTime){
        startDate=shiftIsoDay(previousDay,1);
        startTime="00:00";
      }
      if(!startDate || startDate>bounds.maxDate){
        dialogError.hidden=false;
        dialogError.textContent="Der bisherige Unterereigniszeitraum reicht bereits bis zum Ende des Oberereignisses. Ändere zuerst die letzte Endzeit.";
        return null;
      }
      const endTime=startDate===bounds.maxDate ? (bounds.maxTime||"23:59") : "23:59";
      if(startDate===bounds.maxDate && startTime>endTime){
        dialogError.hidden=false;
        dialogError.textContent="Im Oberereignis ist hinter dem letzten Unterereignis kein weiterer Zeitraum frei.";
        return null;
      }
      return {
        start_date:startDate,
        start_time:startTime,
        end_date:startDate,
        end_time:endTime,
      };
    }

    function refreshCreateSubeventDayControls(){
      const bounds=subeventBounds();
      const allowed=subeventAllowedDays();
      if(!bounds.minDate||!bounds.maxDate||!allowed.length)return;
      for(const row of createSubeventList.querySelectorAll("[data-create-subevent]")){
        for(const selector of [
          "[data-create-child-start-date]",
          "[data-create-child-end-date]",
        ]){
          const control=row.querySelector(selector);
          if(!control)continue;
          control.min=bounds.minDate;
          control.max=bounds.maxDate;
          let value=String(control.value||"");
          if(!validIsoDateText(value) || value<bounds.minDate)value=bounds.minDate;
          else if(value>bounds.maxDate)value=bounds.maxDate;
          control.value=value;
        }
      }
    }
    function updateSubeventPrefixToggle(){
      const count=createSubeventList.querySelectorAll("[data-create-subevent]").length;
      const visible=!createSubevents.hidden && !activeExtension && count>0;
      subeventPrefixToggle.hidden=!visible;
      subeventPrefixToggle.textContent=dialogSubeventPrefixEnabled ? "Präfix: an" : "Präfix: aus";
      subeventPrefixToggle.setAttribute("aria-pressed",dialogSubeventPrefixEnabled ? "true" : "false");
      const parts=["Datum"];
      if(globalSubeventDateMode==="range")parts.push("Von–bis");
      if(globalSubeventIncludeTime)parts.push("Uhrzeit");
      if(globalSubeventIncludeYear)parts.push("Jahr");
      subeventPrefixToggle.title="Namenspräfix für Unterereignisse · "+parts.join(" · ");
    }

    function addCreateSubeventCard(value={}){
      const defaults=Object.keys(value||{}).length ? value : nextSubeventDefaults();
      if(!defaults)return;
      const row=document.createElement("details");row.className="create-subevent-card";row.dataset.createSubevent="1";row.open=true;
      const bounds=subeventBounds();
      const allowed=subeventAllowedDays();
      const wantedStart=String(defaults.start_date||bounds.minDate||"");
      const sd=allowed.includes(wantedStart)?wantedStart:(allowed[0]||wantedStart);
      const wantedEnd=String(defaults.end_date||sd);
      const ed=allowed.includes(wantedEnd)?wantedEnd:sd;
      const defaultStart=String(defaults.start_time||(
        sd===bounds.minDate ? bounds.minTime : "00:00"
      )||"00:00");
      const defaultEnd=String(defaults.end_time||(
        ed===bounds.maxDate ? bounds.maxTime : "23:59"
      )||"23:59");
      row.innerHTML=`<summary style="cursor:pointer"><strong data-create-child-summary>${escapeHtml(defaults.name||"Unterereignis")}</strong></summary><div class="create-subevent-grid" style="margin-top:9px"><div class="create-subevent-top"><label class="create-subevent-name"><span>Name</span><input data-create-child-name value="${escapeHtml(defaults.name||"")}" placeholder="Zum Beispiel Tag 1"></label><button type="button" class="danger-button create-subevent-remove" data-remove-create-subevent>Remove subevent</button></div><div class="create-subevent-boundaries"><div class="create-subevent-boundary">${subeventDayControl("data-create-child-start-date","data-create-child-start-month-year",sd,"Beginn")}<label><span>Startzeit</span><input data-create-child-start-time type="time" value="${escapeHtml(defaultStart)}"></label></div><div class="create-subevent-boundary">${subeventDayControl("data-create-child-end-date","data-create-child-end-month-year",ed,"Ende")}<label><span>Endzeit</span><input data-create-child-end-time type="time" value="${escapeHtml(defaultEnd)}"></label></div></div></div>`;
      const name=row.querySelector("[data-create-child-name]"),summary=row.querySelector("[data-create-child-summary]");
      const syncDayDisplays=()=>{
        for(const [selector,displaySelector] of [
          ["[data-create-child-start-date]","[data-create-child-start-month-year]"],
          ["[data-create-child-end-date]","[data-create-child-end-month-year]"],
        ]){
          const control=row.querySelector(selector);
          const display=row.querySelector(displaySelector);
          if(control&&display)display.value=monthYearForIso(control.value);
        }
      };
      name?.addEventListener("input",()=>{summary.textContent=String(name.value||"").trim()||"Unterereignis";scheduleDialogPreview();});
      row.querySelector("[data-remove-create-subevent]")?.addEventListener("click",()=>{row.remove();updateSubeventPrefixToggle();scheduleDialogPreview();});
      row.querySelectorAll("input,select").forEach(input=>input.addEventListener("change",()=>{syncDayDisplays();scheduleDialogPreview();}));
      createSubeventList.appendChild(row);
      syncDayDisplays();
      updateSubeventPrefixToggle();
      name?.focus();
      dialogError.hidden=true;
      dialogError.textContent="";
    }
    function collectCreateSubevents(){return [...createSubeventList.querySelectorAll("[data-create-subevent]")].map(row=>{const name=row.querySelector("[data-create-child-name]")?.value?.trim()||"",sd=row.querySelector("[data-create-child-start-date]")?.value||"",st=row.querySelector("[data-create-child-start-time]")?.value||"00:00",ed=row.querySelector("[data-create-child-end-date]")?.value||"",et=row.querySelector("[data-create-child-end-time]")?.value||"23:59";return{name,start_datetime:`${sd}T${st}:00`,end_datetime:`${ed}T${et}:59`};});}

    async function openEventDialog(mode){
      dialogMode=mode;const dated=selectedDatedGroups(),noEvent=mode==="no_event"||mode==="existing_no_event",existingNoEvent=mode==="existing_no_event";activeNoEventTarget=null;
      const parentCandidates=noEvent?[]:plannedParentCandidates(dated);existingParentRow.hidden=noEvent||parentCandidates.length===0;
      if(!existingParentRow.hidden){existingParentEvent.innerHTML=`<option value="">Neues Ereignis anlegen</option>`+parentCandidates.map(parent=>`<option value="${escapeHtml(parent.id)}">${escapeHtml(parent.name)} · ${escapeHtml(String(parent.start_datetime||"").slice(0,10))}</option>`).join("");existingParentEvent.value="";}else existingParentEvent.innerHTML="";
      eventName.value=noEvent?noEventLabel:"";eventName.disabled=noEvent;dialogTitle.textContent=existingNoEvent?("Zu bestehendem „"+noEventLabel+"“ hinzufügen"):(noEvent?("Als „"+noEventLabel+"“ zuordnen"):"Ereignis erstellen");
      activeExtension=null;
      eventStartDate.value=dated.length?dated[0].day_key:"";eventEndDate.value=dated.length?dated[dated.length-1].day_key:"";eventStartTime.value="00:00";eventEndTime.value="23:59";
      eventStartDate.disabled=false;eventStartTime.disabled=false;eventEndDate.disabled=false;eventEndTime.disabled=false;eventStartDate.removeAttribute("min");eventStartDate.removeAttribute("max");eventEndDate.removeAttribute("min");eventEndDate.removeAttribute("max");
      useTimeRange.checked=!noEvent;useTimeRange.disabled=true;setParentTimeFieldsVisible(true);
      dialogSubeventPrefixEnabled=globalSubeventPrefixEnabled;
      createSubeventList.innerHTML="";createSubevents.hidden=noEvent;createSubeventHeading.textContent="Unterereignisse (optional)";eventBoundaries.hidden=noEvent;preserveDayFolders.checked=false;preserveDayFolders.disabled=false;preserveDayFoldersRow.hidden=false;createSubfolders.checked=Boolean(globalFolderLayout?.structure_enabled ?? true);createSubfolders.disabled=false;createSubfoldersRow.hidden=false;dialogError.hidden=true;dialogError.textContent="";updateSubeventPrefixToggle();
      noEventSegmentEditor.hidden=!noEvent;existingNoEventTargetRow.hidden=!existingNoEvent;
      if(existingNoEvent){const months=[...new Set(dated.map(group=>String(group.day_key||"").slice(0,7)).filter(Boolean))];noEventTargetCache=[];if(months.length){try{const d=await getJson(`/api/jobs/${encodeURIComponent(jobSelect.value)}/no-event/targets?months=${encodeURIComponent(months[0])}`);noEventTargetCache=d.targets||[];}catch(_){}}const target=noEventTargetCache[0]||null;if(target){existingNoEventTargetRow.hidden=false;existingNoEventTarget.innerHTML=`<option value="${escapeHtml(target.id)}">${escapeHtml(String(target.month_key||"").slice(5,7))} – Ohne Ereignis · ${escapeHtml(workspaceStatusLabel(target.status))}</option>`;existingNoEventTarget.value=target.id;existingNoEventTarget.disabled=true;activateNoEventTarget(target);}else renderNoEventSegmentEditor(dated.map(day=>({...day,_new:true})));}
      else if(noEvent){renderNoEventSegmentEditor(dated.map(day=>({...day,_new:true})));await autoAttachExistingNoEventCollection();}
      else{applyAutomaticFreeTimeSuggestion(dated);if(parentCandidates.length)applyExistingParentChoice();}
      dialogPreview.textContent="Vorschau wird vorbereitet …";dialogPreview.hidden=true;calculatePreviewButton.textContent="Vorschau einblenden";saveResult.hidden=true;saveResult.textContent="";eventDialog.showModal();syncCreateEventCompactPairs();scheduleDialogPreview();
    }

    function collectEventPayload() {
      const base = {
        event_kind: ["no_event","existing_no_event"].includes(dialogMode) ? "no_event" : "event",
        event_name: eventName.value.trim(),
        start_date: eventStartDate.value,
        end_date: eventEndDate.value,
        uses_time_range: !["no_event","existing_no_event"].includes(dialogMode),
        subevents: ["no_event","existing_no_event"].includes(dialogMode) ? [] : collectCreateSubevents(),
        selected_intervals: selectedDatedGroups().map(g=>({start_datetime:g.start_datetime,end_datetime:g.end_datetime})),
        start_time: eventStartTime.value,
        end_time: eventEndTime.value,
        preserve_day_folders: preserveDayFolders.checked,
        create_subfolders: createSubfolders.checked,
        selected_day_keys: selectedDatedGroups().map(group => group.day_key),
        existing_parent_event_id: (!["no_event","existing_no_event"].includes(dialogMode) ? (existingParentEvent?.value || null) : null)
      };
      if (!["no_event","existing_no_event"].includes(dialogMode) && !base.existing_parent_event_id) {
        base.subevent_prefix_enabled=dialogSubeventPrefixEnabled;
      }
      const parentId = base.existing_parent_event_id;
      const parent = parentId ? (workspace?.events||[]).find(event=>event.id===parentId) : null;
      if (parent) {
        if(!activeExtension) throw new Error("Der Erweiterungsbereich ist nicht mehr aktuell.");
        if(activeExtension.direction==="after"){
          const extensionEnd=base.end_date ? `${base.end_date}T${base.end_time||"23:59"}:59` : "";
          base.selected_intervals = extensionEnd
            ? [{start_datetime:activeExtension.start_datetime,end_datetime:extensionEnd}]
            : [];
        }else{
          const extensionStart=base.start_date ? `${base.start_date}T${base.start_time||"00:00"}:00` : "";
          base.selected_intervals = extensionStart
            ? [{start_datetime:extensionStart,end_datetime:activeExtension.end_datetime}]
            : [];
        }
        base.preserve_day_folders = Boolean(parent.preserve_day_folders);
        base.create_subfolders = Boolean(parent.folder_layout?.structure_enabled ?? createSubfolders.checked);
        for(const segment of base.subevents || []){
          const a=String(segment.start_datetime||"").slice(0,19);
          const b=String(segment.end_datetime||"").slice(0,19);
          if(a < activeExtension.start_datetime || b > activeExtension.end_datetime){
            throw new Error("Neue Unterereignisse dürfen nur innerhalb des neu hinzugefügten Erweiterungsbereichs liegen.");
          }
        }
      }

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
        calculateDialogPreview().catch(error=>{dialogPreview.textContent=error.message;dialogError.hidden=false;dialogError.textContent=error.message;});
      }, 120);
    }

    async function calculateDialogPreview() {
      const jobId = anchorJobIdForSelection();

      if (!jobId) {
        dialogPreview.textContent =
          "Keine Sicherung ausgewählt.";
        return;
      }

      const basePayload = collectEventPayload();
      const selectedParent = basePayload.existing_parent_event_id
        ? (workspace?.events || []).find(event=>String(event.id)===String(basePayload.existing_parent_event_id))
        : null;
      if (selectedParent?.job_id) jobId = String(selectedParent.job_id);
      const payload = payloadForAllSources(basePayload);

      if (dialogMode === "existing_no_event" || activeNoEventTarget) {
        const all=payload.display_no_event_segments||payload.no_event_segments||[];
        const newKeys=new Set((payload.no_event_segments||[]).map(segment=>`${segment.day_key}|${segment.start_time}|${segment.end_time}`));
        const folder=String(activeNoEventTarget?.folder_name||`${String(all[0]?.day_key||"").slice(5,7)} - Ohne Ereignis`);
        const year=String(all[0]?.day_key||activeNoEventTarget?.month_key||"").slice(0,4)||"Jahr";
        const preserve=Boolean(payload.preserve_day_folders || activeNoEventTarget?.preserve_day_folders);
        const state=activeNoEventTarget?.id
          ? await getJson(`/api/events/${encodeURIComponent(activeNoEventTarget.id)}/folder-layout`)
          : (globalFolderLayout || {structure_enabled:true,input_path:"All",layout:{nodes:[{name:"All",children:[]},{name:"Sorted",children:[]},{name:"Export",children:[]}]}});
        const flatten=(nodes,prefix="")=>(nodes||[]).flatMap(node=>{
          const path=prefix?`${prefix}/${node.name}`:String(node.name||"");
          return [path,...flatten(node.children||[],path)];
        });
        const layoutPaths=state.structure_enabled?flatten(state.layout?.nodes||[]):[""];
        const lines=[year,`└── ${folder}`];
        const leaves=preserve?[...new Set(all.map(s=>s.day_key))].sort():[""];
        for(const leaf of leaves){
          if(leaf) lines.push(`    ├── ${leaf}`);
          const indent=leaf?"    │   ":"    ";
          for(const p of layoutPaths) if(p) lines.push(`${indent}├── ${p}`);
        }
        lines.push("",`Fortführung · ${String(activeNoEventTarget?.status||"")}`);
        for (const segment of all) lines.push(`${segment.day_key} · ${segment.start_time}–${segment.end_time}${newKeys.has(`${segment.day_key}|${segment.start_time}|${segment.end_time}`)?" · NEU":" · bestehend"}`);
        dialogPreview.textContent=window.BibliothekarI18n?.previewText?.(lines.join("\n")) ?? lines.join("\n");
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

        const empty=(result.preview.empty_subevents||[]);
        dialogPreview.textContent =
          (window.BibliothekarI18n?.previewText?.(result.preview.structure_text) ?? result.preview.structure_text)
          + (empty.length
            ? "\n\nHinweis: ohne passende Dateifamilien · "+empty.map(item=>item.name).join(", ")
            : "");
        scheduleTreeFit(dialogPreview);

      } catch (error) {
        dialogPreview.textContent =
          window.BibliothekarI18n?.previewText?.(error.message) ?? error.message;

      } finally {
        calculatePreviewButton.disabled =
          false;
      }
    }


    async function confirmEmptySubevents(error) {
      if (error?.data?.confirmation_required !== "empty_subevents") return false;
      const names=(error.data.empty_subevents||[]).map(item=>String(item.name||"Unterereignis"));
      const detail=names.length
        ? "\n\nOhne passende Dateifamilien: "+names.join(", ")
        : "";
      return window.BibliothekarI18n.confirmAsync(
        "Mindestens ein Unterereignis enthält aktuell keine passenden Dateifamilien."
        + detail
        + "\n\nDie leere Ordnerstruktur wird trotzdem angelegt. Trotzdem fortfahren?"
      );
    }

    async function createEventWithEmptySubeventConfirmation(jobId, payload) {
      let current={...payload};
      while(true){
        try {
          return await postJson(
            `/api/jobs/${encodeURIComponent(jobId)}/events`,
            current
          );
        } catch (error) {
          if(error?.data?.confirmation_required==="cross_backup_membership"){
            const confirmed=await confirmCrossBackupMembership(error);
            if(!confirmed)return null;
            current={...current,confirm_cross_backup_membership:true};
            continue;
          }
          if(await confirmEmptySubevents(error)){
            current={...current,confirm_empty_subevents:true};
            continue;
          }
          throw error;
        }
      }
    }

    async function saveEvent() {
      const jobId = anchorJobIdForSelection();

      if (!jobId) {
        saveResult.hidden = false;
        saveResult.textContent =
          "Keine Sicherung ausgewählt.";
        return;
      }

      saveEventButton.disabled = true;
      saveEventButton.classList.add("bk-busy");
      saveEventButton.setAttribute("aria-busy", "true");
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
          const globalPayload=payloadForAllSources(payload);
          const target=(workspace?.events||[]).find(event=>String(event.id)===String(targetId));
          const requestJobId=String(target?.job_id || jobId);
          result=await postWithCanonicalMembership(
            `/api/jobs/${encodeURIComponent(requestJobId)}/no-event/assign-existing`,
            {
              target_event_id: targetId,
              segments: payload.no_event_segments || [],
              family_ids: globalPayload.selected_family_ids || []
            }
          );
          if(!result){
            saveResult.hidden=true;
            return;
          }
          const total=Number(result?.assigned_family_count||0);
          saveResult.textContent = `Fortgeführt: ${total} Familien${(result?.source_job_ids||[]).length>1?" · sicherungsübergreifend":""}`;
        } else {
          const eventPayload=collectEventPayload();
          const selectedParent=eventPayload.existing_parent_event_id
            ? (workspace?.events||[]).find(event=>String(event.id)===String(eventPayload.existing_parent_event_id))
            : null;
          const requestJobId=String(selectedParent?.job_id || jobId);
          const globalPayload=payloadForAllSources(eventPayload);
          result = await createEventWithEmptySubeventConfirmation(
            requestJobId,
            globalPayload
          );
          if(!result){
            saveResult.hidden=true;
            return;
          }
          const sourceCount=Number((result.source_job_ids||[]).length) || sourceGroupsForSelection().size;
          const totalFamilies=Number(result.assigned_family_count||0);
          saveResult.textContent = `Gespeichert: ${result.parent_event.folder_name} · ${totalFamilies} Familien${sourceCount>1?" · sicherungsübergreifend":""}`;
          lastSavedEvent = result.parent_event;
        }

        if (result?.change_request_id) {
          selectedDays.clear();
          await loadWorkspace();
          eventDialog.close();
          location.href = `/events?job=${encodeURIComponent(jobId)}&task=change:${encodeURIComponent(result.change_request_id)}`;
          return;
        }

        applySavedEventStatus.textContent = "";

        selectedDays.clear();

        const fastPlannedRefresh = (
          String(result?.status || "") === "planned"
          && String(result?.parent_event?.status || "") === "planned"
          && !result?.change_request_id
        );
        await loadWorkspace({physicalRefresh: !fastPlannedRefresh});

        eventDialog.close();

      } catch (error) {
        saveResult.hidden=true;
        saveResult.textContent="";
        dialogError.hidden=false;
        dialogError.textContent=error.message;

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
        saveEventButton.classList.remove("bk-busy");
        saveEventButton.removeAttribute("aria-busy");
        calculatePreviewButton.disabled =
          false;
      }
    }



    function onBackupFilterChange(event){
      const checkbox=event.target.closest("input[data-backup-filter-job]");
      if(!checkbox)return;
      const id=String(checkbox.dataset.backupFilterJob||"");
      if(checkbox.checked)selectedJobIds.add(id);
      else selectedJobIds.delete(id);
      updateTechnicalAnchor(jobSelect.value);
      renderBackupFilter();
      loadWorkspace().catch(error=>setStatus(error.message,true));
    }
    backupFilterActiveList.addEventListener("change",onBackupFilterChange);
    backupFilterArchivedList.addEventListener("change",onBackupFilterChange);
    backupFilterAll.addEventListener("click",()=>{
      selectedJobIds=new Set(jobs.filter(job=>job.workflow_status!=="archived").map(job=>job.id));
      backupFilterArchived.open=false;
      updateTechnicalAnchor();
      renderBackupFilter();
      loadWorkspace().catch(error=>setStatus(error.message,true));
    });
    backupFilterNone.addEventListener("click",()=>{
      selectedJobIds.clear();
      updateTechnicalAnchor();
      renderBackupFilter();
      loadWorkspace().catch(error=>setStatus(error.message,true));
    });

    newEventButton.addEventListener(
      "click",
      () => openEventDialog("event")
    );

    loadEventNamingSettings();

    existingNoEventButton?.addEventListener("click", () => openEventDialog("no_event"));

    noEventButton.addEventListener(
      "click",
      () => openEventDialog("no_event")
    );

    // Normale Ereignisse besitzen immer exakte Datum-/Uhrzeitgrenzen.
    addCreateSubevent?.addEventListener("click",()=>addCreateSubeventCard());
    subeventPrefixToggle?.addEventListener("click",()=>{
      dialogSubeventPrefixEnabled=!dialogSubeventPrefixEnabled;
      updateSubeventPrefixToggle();
      scheduleDialogPreview();
    });

    existingParentEvent?.addEventListener("change", applyExistingParentChoice);

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
      dialogTitle.textContent="Als „"+noEventLabel+"“ zuordnen";
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

    function clearDialogFeedbackForEdit() {
      saveResult.hidden=true;
      saveResult.textContent="";
      dialogError.hidden=true;
      dialogError.textContent="";
    }

    eventForm?.addEventListener("input", event => {
      if (event.target?.id === "calculate-preview-button") return;
      clearDialogFeedbackForEdit();
      scheduleDialogPreview();
    });
    eventForm?.addEventListener("change", event => {
      clearDialogFeedbackForEdit();
      if (
        event?.target === eventStartDate
        || event?.target === eventEndDate
      ) {
        refreshCreateSubeventDayControls();
      }
      scheduleDialogPreview();
    });

    let activeApplyBatchId = "";

    async function pollApplyBatch(batchId) {
      activeApplyBatchId = String(batchId || "");
      applySavedEventButton.disabled = true;
      while (activeApplyBatchId === String(batchId || "")) {
        const batch = await getJson(
          `/api/operation-batches/${encodeURIComponent(batchId)}`
        );
        const total = Number(batch.item_count || 0);
        const done = Number(batch.completed_item_count || 0);
        const percent = Number(batch.progress_percent || 0);
        applySavedEventStatus.textContent =
          `Servervorgang · ${done} von ${total} Ereignissen · ${percent} %`;

        if (batch.terminal) {
          activeApplyBatchId = "";
          applySavedEventButton.disabled = false;
          if (batch.status !== "applied") {
            throw new Error(
              batch.error_message
              || "Mehrfach-Anwendung wurde nicht abgeschlossen."
            );
          }
          applySavedEventStatus.textContent =
            "Alle ausgewählten Ereignisse wurden serverseitig vollständig angewendet und geprüft.";
          await loadWorkspace();
          return batch;
        }

        await new Promise(resolve => setTimeout(resolve, 800));
      }
      return null;
    }

    async function resumeActiveApplyBatch() {
      if (activeApplyBatchId) return;
      const data = await getJson("/api/operation-batches/active");
      const batch = (data.batches || [])[0];
      if (!batch) return;
      applySavedEventStatus.textContent =
        "Laufender Servervorgang wurde wieder aufgenommen …";
      pollApplyBatch(batch.id).catch(error => {
        applySavedEventStatus.textContent = error.message;
        applySavedEventButton.disabled = false;
      });
    }

    async function applyPlannedEvents() {
      const selectedInputs = [
        ...plannedEventSelection.querySelectorAll(
          "input[data-planned-event]:checked"
        )
      ];
      const components = [];
      const seen = new Set();

      for (const input of selectedInputs) {
        let rows = [];
        try {
          rows = JSON.parse(
            input.dataset.plannedComponents || "[]"
          );
        } catch (_) {}
        for (const row of rows) {
          const key = `${row.job_id}:${row.event_id}`;
          if (
            !row.job_id
            || !row.event_id
            || seen.has(key)
          ) continue;
          seen.add(key);
          components.push(row);
        }
      }

      if (!components.length) {
        throw new Error(
          "Keine geplanten Ereignisse ausgewählt."
        );
      }

      applySavedEventButton.disabled = true;
      applySavedEventStatus.textContent =
        "Alle ausgewählten Pläne werden geprüft …";

      const plans = [];
      for (const component of components) {
        const plan = await getJson(
          `/api/jobs/${encodeURIComponent(component.job_id)}/events/${encodeURIComponent(component.event_id)}/sort-plan`
        );
        if (!plan.summary?.ready) {
          throw new Error(
            `${plan.event?.name || component.event_id}: ${plan.summary?.blocker_count || 1} Blocker.`
          );
        }
        plans.push({component, plan});
      }

      const familyCount = plans.reduce(
        (sum, item) =>
          sum + Number(item.plan.summary.family_count || 0),
        0
      );
      const fileCount = plans.reduce(
        (sum, item) =>
          sum + Number(item.plan.summary.file_count || 0),
        0
      );

      const german = window.BibliothekarI18n?.getLocale?.() === "de";
      const confirmation = german
        ? `${selectedInputs.length} Ereignis${selectedInputs.length === 1 ? "" : "se"} mit ${familyCount} Familien und ${fileCount} Dateien jetzt anwenden? Der Server führt den Vorgang auch weiter, wenn diese Seite geschlossen wird.`
        : `Apply ${selectedInputs.length} event${selectedInputs.length === 1 ? "" : "s"} with ${familyCount} families and ${fileCount} files now? The server will continue the operation even if this page is closed.`;
      const ok = window.BibliothekarI18n?.confirmAsync
        ? await window.BibliothekarI18n.confirmAsync(confirmation)
        : window.confirm(confirmation);
      if (!ok) {
        applySavedEventButton.disabled = false;
        applySavedEventStatus.textContent =
          "Nicht angewendet.";
        return;
      }

      const response = await postJson(
        "/api/operation-batches/apply-events",
        {
          confirmation_phrase:
            plans[0]?.plan?.apply_confirmation_phrase
            || "SORTIERUNG ANWENDEN",
          items: plans.map(({component, plan}) => ({
            job_id: component.job_id,
            event_id: component.event_id,
            plan_token: plan.plan_token
          }))
        }
      );

      window.dispatchEvent(new Event("bk-activity-refresh"));
      await pollApplyBatch(response.batch.id);
    }

    document.addEventListener("bibliothekar:folder-layout-updated", event => {
      if(event?.detail) globalFolderLayout=event.detail;
    });

    applySavedEventButton.addEventListener("click", () => {
      if (applySavedEventButton.dataset.action === "reconcile") {
        const source = applySavedEventButton.dataset.reconcileSource || "";
        if (source && jobSelect.value) {
          location.href = `/events?job=${encodeURIComponent(jobSelect.value)}&task=resort:${encodeURIComponent(source)}`;
        }
        return;
      }
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
          `/api/jobs/${encodeURIComponent(button.dataset.sourceJobId || jobSelect.value)}/event-suggestions/accept`,
          {
            family_ids: JSON.parse(button.dataset.familyIds || "[]"),
            target_event_id: button.dataset.targetEventId
          }
        );
        if (result?.change_request_id) {
          eventSuggestionStatus.textContent = `${result.name} wurde als manueller Archivauftrag vorbereitet.`;
          location.href = `/events?job=${encodeURIComponent(result.target_job_id || button.dataset.sourceJobId || jobSelect.value)}&task=change:${encodeURIComponent(result.change_request_id)}`;
          return;
        }
        if(result?.resort_required || result?.target_status==="applied"){
          eventSuggestionStatus.textContent = `${result.name} wurde logisch ergänzt. Die physische Übernahme wird jetzt geprüft.`;
          location.href = `/events?job=${encodeURIComponent(result.target_job_id || button.dataset.sourceJobId || jobSelect.value)}&task=resort:${encodeURIComponent(result.target_event_id || button.dataset.targetEventId)}`;
          return;
        }
        eventSuggestionStatus.textContent = `${result.name} wurde der offenen Planung hinzugefügt.`;
        await loadWorkspace();
      } catch (error) {
        eventSuggestionStatus.textContent = error.message;
        button.disabled = false;
      }
    });

    document.getElementById("day-reload")?.addEventListener("click", async event => {
      const button = event.currentTarget;
      button.disabled = true; button.classList.add("bk-busy");
      try {
        await loadJobs({physicalRefresh:true});
        await window.bkForceExternalChangeCheck?.();
      } catch (error) { setStatus(error.message, true); }
      finally { button.disabled = false; button.classList.remove("bk-busy"); }
    });

    daySelectAllButton.addEventListener("click", () => {
      const keys = selectableDayKeys();
      const allSelected = keys.length > 0 && keys.every(key => selectedDays.has(key));
      if (allSelected) {
        for (const key of keys) selectedDays.delete(key);
        lastSelectedDayKey = null;
      } else {
        for (const key of keys) selectedDays.add(key);
        lastSelectedDayKey = keys[keys.length - 1] || null;
      }
      renderDays();
      renderSelection();
    });

    // Recover server progress without waiting for the complete 4,000-file
    // workspace view. The separate global activity dock can also poll early.
    resumeActiveApplyBatch().catch(error => {
      applySavedEventStatus.textContent = error.message;
    });
    loadJobs().then(async () => {
      const params = new URLSearchParams(location.search);
      const task = params.get("task") || "";
      if (task.startsWith("batch:")) {
        const wanted = task.slice("batch:".length);
        const batch = await getJson(
          `/api/operation-batches/${encodeURIComponent(wanted)}`
        );
        if (
          !batch.terminal
          && !activeApplyBatchId
        ) {
          pollApplyBatch(batch.id).catch(error => {
            applySavedEventStatus.textContent =
              error.message;
            applySavedEventButton.disabled = false;
          });
        }
        postSaveAction.hidden = false;
        postSaveAction?.scrollIntoView({
          behavior: "smooth",
          block: "center"
        });
      } else if (task.startsWith("reassign:")) {
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
          applySavedEventStatus.textContent = "Das geplante Ereignis ist nicht mehr offen.";
        }
        postSaveAction?.scrollIntoView({behavior:"smooth",block:"center"});
      } else if (task === "free") {
        document.querySelector(".day-groups")?.scrollIntoView({behavior:"smooth",block:"start"});
        setStatus("Offene Aufgabe: Es gibt noch nicht zugeordnete Familien.");
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
