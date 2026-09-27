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
    .edit-inline-error { border:1px solid var(--danger); border-radius:12px; padding:11px; margin-bottom:12px; background:color-mix(in srgb,var(--danger) 10%,var(--surface)); color:var(--text); font-weight:650; }
    .edit-actions { display:flex; justify-content:flex-end; gap:10px; flex-wrap:wrap; margin-top:16px; }
    .edit-boundaries { display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;grid-column:1/-1; }
    .edit-boundary { display:grid;grid-template-columns:minmax(0,1.45fr) minmax(105px,.7fr);gap:8px;align-items:end; }
    .inspect-more { margin-top:9px; }
    @media (max-width:760px){.edit-boundaries,.edit-boundary{grid-template-columns:1fr}}

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
      background: var(--surface-2);
      padding: 16px;
      cursor: pointer;
      transition: border-color .15s ease, background .15s ease;
    }

    .event-card.is-open {
      border-color: var(--accent);
      background:
        color-mix(
          in srgb,
          var(--accent) 9%,
          var(--surface)
        );
    }

    .event-card-actions {
      display:flex;
      flex-wrap:wrap;
      gap:10px;
      margin-top:14px;
      padding-top:14px;
      border-top:1px solid var(--border);
    }

    .event-card-actions[hidden] {
      display:none;
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

    #event-edit-dialog.edit-mode .sort-plan-content {
      background:
        color-mix(
          in srgb,
          var(--danger) 4%,
          var(--surface)
        );
    }

    .inspect-summary {
      display:grid;
      grid-template-columns:repeat(2,minmax(0,1fr));
      gap:10px;
      margin-bottom:14px;
    }
    .inspect-field {
      min-width:0;
      border:1px solid var(--border);
      border-radius:11px;
      background:var(--surface-2);
      padding:10px 12px;
    }
    .inspect-field span {
      display:block;
      margin-bottom:4px;
      color:var(--muted);
      font-size:.78rem;
    }
    .inspect-field strong {
      display:block;
      overflow-wrap:anywhere;
    }
    .inspect-section {
      margin-top:16px;
    }
    .inspect-card {
      margin-top:7px;
      padding:9px 11px;
      border:1px solid var(--border);
      border-radius:12px;
      background:var(--surface-2);
    }
    .inspect-card > summary {
      display:flex;
      align-items:center;
      justify-content:space-between;
      gap:10px;
    }
    .inspect-family-list {
      display:grid;
      gap:4px;
      max-height:320px;
      overflow:auto;
      padding-top:2px;
    }
    .inspect-family-row {
      display:grid;
      grid-template-columns:minmax(0,1fr) auto;
      gap:10px;
      align-items:baseline;
      min-width:0;
      font-family:ui-monospace,SFMono-Regular,Menlo,monospace;
      font-size:.78rem;
      line-height:1.35;
    }
    .inspect-family-row span:first-child {
      min-width:0;
      overflow:hidden;
      text-overflow:ellipsis;
      white-space:nowrap;
    }
    .inspect-family-row span:last-child {
      white-space:nowrap;
      color:var(--muted);
      font-variant-numeric:tabular-nums;
    }
    .inspect-structure {
      margin:8px 0 0;
      padding:11px;
      border:1px solid var(--border);
      border-radius:11px;
      background:var(--surface-2);
      white-space:pre-wrap;
      overflow-wrap:anywhere;
      font-family:ui-monospace,SFMono-Regular,Menlo,monospace;
      font-size:.82rem;
      line-height:1.5;
    }
    .inspect-actions {
      display:flex;
      justify-content:flex-end;
      gap:10px;
      flex-wrap:wrap;
      margin-top:16px;
    }

    @media (max-width:640px) {
      .inspect-summary { grid-template-columns:1fr; }
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
    a.plan-button { display:inline-flex; align-items:center; padding:10px 14px; border:1px solid var(--accent); border-radius:10px; text-decoration:none; }

    .sort-plan-dialog {
      inline-size: min(1240px, calc(100dvw - 28px));
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

    .sort-plan-header-actions {
      display: flex;
      align-items: center;
      justify-content: flex-end;
      gap: 8px;
      flex: 0 0 auto;
    }

    .sort-plan-summary {
      display: grid;
      grid-template-columns: repeat(7, minmax(0, 1fr));
      gap: 10px;
      margin-bottom: 16px;
    }

    @media (max-width: 1080px) {
      .sort-plan-summary {
        grid-template-columns: repeat(auto-fit, minmax(135px, 1fr));
      }
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

    .sort-plan-disclosure {
      border-top: 1px solid var(--border);
      padding-top: 10px;
    }

    .sort-plan-disclosure > summary {
      cursor: pointer;
      font-weight: 760;
      list-style-position: inside;
      padding: 4px 0 8px;
    }

    .sort-plan-disclosure > summary::marker {
      color: var(--accent);
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
      grid-template-columns: minmax(0, 1fr) auto;
      align-items: center;
      gap: 10px 14px;
      margin-top: 18px;
      border: 1px solid var(--accent);
      border-radius: 14px;
      background:
        color-mix(
          in srgb,
          var(--accent) 10%,
          var(--surface-2)
        );
      padding: 12px 14px;
    }

    .sort-apply-head {
      display: flex;
      align-items: center;
      gap: 8px;
      min-width: 0;
    }

    .sort-apply-panel.blocked {
      border-color: var(--danger);
    }

    .sort-apply-confirm {
      grid-column: 1 / -1;
      display: flex;
      align-items: center;
      gap: 9px;
      min-height: 28px;
      line-height: 1.3;
    }

    .sort-apply-confirm input {
      width: 22px;
      height: 22px;
      margin: 0;
      flex: 0 0 auto;
    }

    .sort-apply-actions {
      grid-column: 2;
      grid-row: 1;
      display: flex;
      align-items: center;
      justify-content: flex-end;
      gap: 8px;
      flex-wrap: nowrap;
    }

    .sort-apply-panel .sort-run-progress {
      grid-column: 1 / -1;
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

      .sort-plan-header-actions {
        width: 100%;
        margin-top: 10px;
      }

      .sort-plan-header-actions button,
      .sort-plan-header > button {
        width: 100%;
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
    .reassignment-resume + .event-details > summary { padding-top:6px; }
    .reassignment-dialog-action { display:flex; margin-top:14px; }
    #normal-event-segments { display:grid; gap:10px; }
    .child-segment-card { padding:12px 14px !important; margin:0 !important; }
    .child-segment-card > summary { padding:2px 0 8px; }
    .child-segment-fields { display:grid; grid-template-columns:minmax(0,1fr); gap:10px; padding-top:4px; }
    .child-segment-fields > label { display:grid; gap:6px; }
    .child-segment-boundary { display:grid; grid-template-columns:minmax(220px,1.65fr) minmax(130px,.65fr); gap:10px; align-items:end; }
    .child-segment-end-row { display:grid; grid-template-columns:minmax(0,1fr) auto; gap:12px; align-items:end; }
    .child-segment-remove { white-space:nowrap; align-self:end; min-height:44px; }
    @media (max-width:760px) {
      .child-segment-boundary,.child-segment-end-row { grid-template-columns:1fr; }
      .child-segment-remove { width:100%; }
    }
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


    summary { cursor:pointer; user-select:none; }
    summary[style*="display:flex"]::before { content:"▸"; flex:0 0 auto; }
    details[open] > summary[style*="display:flex"]::before { content:"▾"; }
    .event-details > summary {
      display:flex !important;
      align-items:center;
      gap:6px;
      list-style:none !important;
      padding:4px 0;
    }
    .event-details > summary::-webkit-details-marker { display:none; }
    .event-details > summary::before { content:none !important; display:none !important; }
    button.plan-button, .plan-button, button.bk-positive-action, button[type=submit], #save-event-button, #calculate-preview-button { background:#2563eb !important; border-color:#2563eb !important; color:white !important; }
    button.danger-button, .danger-button { background:#b42318 !important; border-color:#b42318 !important; color:white !important; }
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
        <div class="sort-plan-header-actions">
          <button id="event-edit-header-button" class="plan-button bk-positive-action" type="button" hidden>Bearbeiten</button>
          <button id="event-edit-close" type="button">Schließen</button>
        </div>
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
    const eventEditHeaderButton = document.getElementById("event-edit-header-button");
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
    let mandatoryMutationContext = null;


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


    function eventStatusLabel(status) {
      const labels = {
        draft: "Entwurf",
        planned: "geplant",
        applied: "angewendet",
        archived: "archiviert"
      };
      return labels[String(status || "")] || String(status || "");
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
        const isReconcileTarget = Boolean(Number(event.reconcile_target||0));
        const reassign = Number(event.pending_reassignment_count||0) > 0 ? `
          <div class="reassignment-resume">
            <span><strong>⚠ Neu-Zuordnung offen · ${Number(event.pending_reassignment_count)} ${Number(event.pending_reassignment_count)===1?"Familie":"Familien"}</strong><br><span class="muted">Das Ereignis bleibt angewendet. Die herausgefallenen Familien sind im Plan wieder frei, haben aber noch kein neues Ziel. Erst nach ihrer Zuordnung folgt die gemeinsame, ausdrücklich bestätigte Nachsortierung.</span></span>
            <div style="display:flex;gap:8px;flex-wrap:wrap;justify-content:flex-end">
              <a class="plan-button bk-positive-action" href="/workspace?job=${encodeURIComponent(event._job_id||event.job_id||"")}&task=free">In Aufnahmen öffnen</a>
              ${isMutationAnchor ? `<button type="button" class="danger-button" data-cancel-mutation="${escapeHtml(event.mutation_id)}" data-job-id="${escapeHtml(event._job_id||event.job_id||"")}">Änderung verwerfen</button>` : ""}
            </div>
          </div>` : "";
        const mutation = isMutationAnchor && Number(event.pending_reassignment_count||0) === 0 ? `
          <div class="reassignment-resume"><span><strong>⚠ Nachsortierung offen</strong><br><span class="muted">Das Ereignis bleibt angewendet und die Neu-Zuordnung ist vollständig. Der gespeicherte SOLL-Zustand muss nur noch per SHA-256 geprüft und ausdrücklich auf den SSD-Arbeitsbereich angewendet werden.</span></span><button type="button" class="danger-button" data-cancel-mutation="${escapeHtml(event.mutation_id)}" data-job-id="${escapeHtml(event._job_id||event.job_id||"")}">Änderung verwerfen</button></div>` : "";
        const reconcileTargetNotice = isReconcileTarget ? `
          <div class="reassignment-resume"><span><strong>↳ Ziel einer offenen Nachsortierung</strong><br><span class="muted">Dieses geplante Ereignis wird nicht separat angewendet. Es wird zusammen mit dem bearbeiteten Ursprungsereignis im gemeinsamen Nachsortierplan geprüft und angewendet.</span></span></div>` : "";
        card.innerHTML = `
          <div class="event-card-header"><div><strong class="event-name">${escapeHtml(event.display_title || event.name)}</strong><div class="event-folder">${escapeHtml(event.folder_name||"")}</div><div class="muted">${escapeHtml(String(event.start_datetime||"").slice(0,16))} bis ${escapeHtml(String(event.end_datetime||"").slice(0,16))} · ${Number(event.assigned_family_count||0)} Familien</div></div><span class="status-chip ${statusClass}">${escapeHtml(eventStatusLabel(event.status))}</span></div>
          ${mutation}
          ${reassign}
          ${reconcileTargetNotice}
          <div class="event-card-actions" hidden>
            <button type="button" data-view-event="${escapeHtml(event.id)}" data-job-id="${escapeHtml(event._job_id||event.job_id||"")}">Öffnen</button>
            ${isReconcileTarget && event.reconcile_source_event_id
              ? `<a class="plan-button bk-positive-action" href="/events?job=${encodeURIComponent(event._job_id||event.job_id||"")}&task=resort:${encodeURIComponent(event.reconcile_source_event_id)}">Gemeinsame Nachsortierung öffnen</a>`
              : `<button type="button" class="plan-button bk-positive-action" data-sort-plan-event="${escapeHtml(event.id)}" data-job-id="${escapeHtml(event._job_id||event.job_id||"")}" data-event-status="${escapeHtml(event.status)}">${event.status === "applied" ? "Nachsortierung prüfen" : "Sortierung prüfen"}</button>`}
            ${isDeletable(event)
              ? `<button type="button" class="danger-button" data-delete-event="${escapeHtml(event.id)}" data-job-id="${escapeHtml(event._job_id||event.job_id||"")}">Ereignis löschen</button>`
              : event.mutation_id
                ? `<button type="button" class="danger-button" disabled title="Offene Änderung dieser Sicherung zuerst abschließen oder verwerfen">Ereignis löschen</button>`
                : ""}
          </div>`;
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
      const seenMessages = new Set();
      const uniqueItems = (items || []).filter(item => {
        const message = String(item?.message || "").trim();
        if (!message || seenMessages.has(message)) return false;
        seenMessages.add(message);
        return true;
      });

      if (!uniqueItems.length) {
        return `
          <div class="message-item">
            ${escapeHtml(emptyMessage)}
          </div>
        `;
      }

      return `
        <div class="message-list">
          ${uniqueItems.map(
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
        `${plan._mandatory ? "Änderungen anwenden" : (plan._reconcile ? "Nachsortierplan" : "Sortierplan")} · ${plan.event.name}`;

      sortPlanSubtitle.textContent = plan._mandatory
        ? (ready
          ? "Diese Applied-Änderung muss jetzt angewendet oder vollständig verworfen werden."
          : "Die Änderung ist blockiert. Sie kann nur korrigiert/verworfen werden; nichts wurde physisch verändert.")
        : (ready
          ? "Die rein lesende Prüfung ist ohne Blocker abgeschlossen."
          : "Die Planung ist blockiert. Es wurde nichts verändert.");

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

        <details class="sort-plan-section sort-plan-disclosure">
          <summary>Sicherheitsstatus</summary>
          <div class="path-box">
            <div>Modus: rein lesender Sortierplan</div>
            <div>Dateien verändert: nein</div>
            <div>Ordner verändert: nein</div>
            <div>Datenbank verändert: nein</div>
            <div>Gleiches Dateisystem: ${summary.same_filesystem ? "ja" : "nein"}</div>
            <div>Familien auf mehrere Ziele verteilt: ${Number(summary.family_split_count || 0)}</div>
          </div>
        </details>

        <details class="sort-plan-section sort-plan-disclosure">
          <summary>Arbeitsbestand</summary>
          <div class="path-box">
            <div>Quelle: ${escapeHtml(plan.source_root)}</div>
            <div>Ziel: ${escapeHtml(plan.target_root)}</div>
            <div>Freier Speicher: ${formatBytes(summary.available_bytes)}</div>
          </div>
        </details>

        <details class="sort-plan-section sort-plan-disclosure" open>
          <summary>Zielstruktur</summary>
          <pre class="plan-tree">${escapeHtml(plan.structure_text)}</pre>
        </details>

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
            <div class="sort-apply-head">
              <strong>Sortierung anwenden</strong>
              <button
                class="bk-help"
                type="button"
                aria-label="Hinweis zur bestätigten Sortierung"
                data-help="Nach der Bestätigung werden alle Quelldateien vollständig per SHA-256 geprüft und erst danach innerhalb des SSD-Arbeitsbereichs ohne Überschreiben verschoben. Die Kamerabibliothek bleibt unberührt; bei einem Fehler wird automatisch zurückgerollt."
              >?</button>
            </div>

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

            <label class="sort-apply-confirm">
              <input
                id="sort-apply-confirmation"
                type="checkbox"
              >
              <span>Ich bestätige diesen Zielplan; verändert wird ausschließlich der angezeigte SSD-Arbeitsbestand.</span>
            </label>

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

      if (mandatoryMutationContext && applyConfirmation && applyButton) {
        applyConfirmation.checked = true;
        applyButton.disabled = false;
      }

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
          () => {
            if (applyButton.dataset.completed === "true") {
              mandatoryMutationContext=null;
              sortPlanCloseButton.hidden=false;
              sortPlanCloseButton.textContent="Schließen";
              sortPlanCloseButton.classList.remove("danger-button");
              sortPlanDialog.close();
              return;
            }
            applyCurrentSortPlan().catch(
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
          );
          }
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
            await loadEvents({reset:true});
            refreshGlobalTasks();

            const applyButton = document.getElementById("sort-apply-button");
            const confirmation = document.getElementById("sort-apply-confirmation");
            if (confirmation?.closest(".sort-apply-confirm")) {
              confirmation.closest(".sort-apply-confirm").hidden = true;
            }
            if (applyButton) {
              applyButton.disabled = false;
              applyButton.dataset.completed = "true";
              applyButton.textContent = "Schließen";
            }
            if (mandatoryMutationContext) {
              mandatoryMutationContext = null;
              sortPlanCloseButton.hidden = true;
            }

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

    function inspectDateTime(value) {
      const raw = String(value || "");
      const day = raw.slice(0, 10);
      const time = raw.slice(11, 16);
      return [germanDay(day), time].filter(Boolean).join(" ");
    }


    function inspectFamilyRows(families) {
      const rows = (families || []).map(family => {
        const key = String(family.family_key || "Dateifamilie").split("/").pop();
        const capture = String(family.selected_capture_time || "");
        const stamp = capture
          ? `${germanDay(capture.slice(0,10))} ${capture.slice(11,19)}`
          : "Zeit unbekannt";
        return `<div class="inspect-family-row"><span title="${escapeHtml(key)}">${escapeHtml(key)}</span><span>${escapeHtml(stamp)}</span></div>`;
      }).join("");
      return rows
        ? `<div class="inspect-family-list">${rows}</div>`
        : '<span class="muted">Keine Dateifamilien in diesem Bereich.</span>';
    }


    function inspectRangeFamilies(context, startValue, endValue) {
      const start = String(startValue || "").slice(0,19);
      const end = String(endValue || "").slice(0,19);
      return (context.families || []).filter(family => {
        if (!family.assigned_here) return false;
        const capture = String(family.selected_capture_time || "").slice(0,19);
        return Boolean(capture) && (!start || capture >= start) && (!end || capture <= end);
      });
    }


    function inspectDayEntries(context) {
      const grouped=new Map();
      for(const family of (context.families||[]).filter(item=>item.assigned_here)){
        const day=String(family.selected_capture_time||"").slice(0,10)||"Ohne Datum";
        if(!grouped.has(day))grouped.set(day,[]);
        grouped.get(day).push(family);
      }
      return [...grouped.entries()].sort((a,b)=>a[0].localeCompare(b[0]));
    }

    function inspectDayCards(entries) {
      return entries.map(([day,families])=>`
        <details class="inspect-card collapse-card">
          <summary><strong>${escapeHtml(day==="Ohne Datum"?day:germanDay(day))}</strong><span class="muted">${families.length} Familien</span></summary>
          ${inspectFamilyRows(families)}
        </details>`).join("");
    }

    function renderEventViewer(context, structureData) {
      currentEditContext=null;
      const event=context.event;
      const noEvent=event.event_kind==="no_event";
      const assigned=(context.families||[]).filter(item=>item.assigned_here);
      const segments=context.time_segments||[];
      const childEvents=context.child_events||[];
      const dayEntries=inspectDayEntries(context);
      eventEditDialog.classList.remove("edit-mode");
      eventEditDialog.classList.add("view-mode");
      eventEditHeaderButton.hidden = false;
      eventEditHeaderButton.onclick = () => renderEventEditor(context);
      eventEditTitle.textContent=`${noEvent?"Ohne Ereignis öffnen":"Ereignis öffnen"} · ${event.name}`;
      eventEditSubtitle.textContent="Nur-Lesen-Ansicht der aktuell in der Datenbank gespeicherten Definition und Dateizuordnung.";

      const childCards=!noEvent?childEvents.map(child=>{
        const families=inspectRangeFamilies(context,child.start_datetime,child.end_datetime);
        return `<details class="inspect-card collapse-card"><summary><strong>${escapeHtml(child.name||child.folder_name||"Unterereignis")}</strong><span class="muted">${escapeHtml(inspectDateTime(child.start_datetime))} – ${escapeHtml(inspectDateTime(child.end_datetime))}</span></summary>${inspectFamilyRows(families)}</details>`;
      }).join(""):"";

      eventEditBody.innerHTML=`
        <div class="inspect-summary">
          <div class="inspect-field"><span>Status</span><strong>${escapeHtml(eventStatusLabel(event.status))}</strong></div>
          <div class="inspect-field"><span>Art</span><strong>${noEvent?"Ohne Ereignis":"Ereignis"}</strong></div>
          ${noEvent
            ? '<div class="inspect-field"><span>Datenbank-Zeitraum</span><strong>komplex</strong></div>'
            : `<div class="inspect-field"><span>Datenbank-Beginn</span><strong>${escapeHtml(inspectDateTime(event.start_datetime))}</strong></div><div class="inspect-field"><span>Datenbank-Ende</span><strong>${escapeHtml(inspectDateTime(event.end_datetime))}</strong></div>`}
          <div class="inspect-field"><span>Tagesordner</span><strong>${event.preserve_day_folders?"Erhalten":"Nicht erhalten"}</strong></div>
          <div class="inspect-field"><span>Zugeordnet</span><strong>${assigned.length} Familien</strong></div>
        </div>
        ${event.notes?`<div class="inspect-section"><strong>Notizen</strong><p class="muted">${escapeHtml(event.notes)}</p></div>`:""}
        ${noEvent?`<div class="inspect-section"><strong>Gespeicherte Tages-/Zeitsegmente</strong><div id="inspect-segment-host"></div><button type="button" id="inspect-more-segments" class="inspect-more" hidden>Weitere</button></div>`:""}
        ${childEvents.length?`<div class="inspect-section"><strong>Unterereignisse</strong>${childCards}</div>`:""}
        <details class="inspect-section inspect-card collapse-card" id="inspect-family-days">
          <summary><strong>Dateifamilien nach Aufnahmetag</strong><span class="muted">${dayEntries.length} Tage</span></summary>
          <div id="inspect-family-day-host"></div>
          <button type="button" id="inspect-more-family-days" class="inspect-more" hidden>Weitere</button>
        </details>
        <div class="inspect-section"><strong>Zielstruktur</strong><pre class="inspect-structure">${escapeHtml(structureData?.structure_text||"Keine Struktur vorhanden.")}</pre></div>`;

      if(noEvent){
        let segmentLimit=10;
        const host=document.getElementById("inspect-segment-host");
        const more=document.getElementById("inspect-more-segments");
        const draw=()=>{
          host.innerHTML=segments.slice(0,segmentLimit).map((segment,index)=>{
            const start=segment.start_datetime||`${segment.day_key}T${segment.start_time||"00:00"}:00`;
            const end=segment.end_datetime||`${segment.day_key}T${segment.end_time||"23:59"}:59`;
            const families=inspectRangeFamilies(context,start,end);
            return `<details class="inspect-card collapse-card"><summary><strong>Tagessegment ${index+1} · ${escapeHtml(germanDay(String(segment.day_key||start).slice(0,10)))}</strong><span class="muted">${escapeHtml(String(segment.start_time||start.slice(11,16)))}–${escapeHtml(String(segment.end_time||end.slice(11,16)))} · ${families.length} Familien</span></summary>${inspectFamilyRows(families)}</details>`;
          }).join("")||'<p class="muted">Keine Segmente gespeichert.</p>';
          more.hidden=segmentLimit>=segments.length;
        };
        more.onclick=()=>{segmentLimit+=10;draw();};
        draw();
      }

      let familyDayLimit=10;
      const familyHost=document.getElementById("inspect-family-day-host");
      const familyMore=document.getElementById("inspect-more-family-days");
      const drawDays=()=>{
        familyHost.innerHTML=inspectDayCards(dayEntries.slice(0,familyDayLimit))||'<p class="muted">Keine zugeordneten Familien.</p>';
        familyMore.hidden=familyDayLimit>=dayEntries.length;
      };
      familyMore.onclick=()=>{familyDayLimit+=10;drawDays();};
      drawDays();
    }


    async function openEventViewer(eventId, jobId) {
      eventEditDialog.classList.remove("edit-mode");
      eventEditDialog.classList.add("view-mode");
      eventEditHeaderButton.hidden = true;
      eventEditHeaderButton.onclick = null;
      eventEditTitle.textContent = "Ereignis öffnen";
      eventEditSubtitle.textContent = "Datenbankzustand wird geladen …";
      eventEditBody.textContent = "Ereignisdaten werden geladen …";
      if (!eventEditDialog.open) eventEditDialog.showModal();
      const [context, structureData] = await Promise.all([
        requestJson(`/api/jobs/${encodeURIComponent(jobId)}/events/${encodeURIComponent(eventId)}/edit`),
        requestJson(`/api/jobs/${encodeURIComponent(jobId)}/events/${encodeURIComponent(eventId)}/structure`)
      ]);
      context._job_id = jobId;
      renderEventViewer(context, structureData);
    }


    function renderEventEditor(context) {
      currentEditContext = context;
      eventEditDialog.classList.remove("view-mode");
      eventEditDialog.classList.add("edit-mode");
      eventEditHeaderButton.hidden = true;
      eventEditHeaderButton.onclick = null;
      const event = context.event;
      if (context.legacy_disjoint) throw new Error(context.legacy_warning);
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
        return `<details class="no-event-segment card collapse-card" data-segment-row style="display:block;padding:8px 10px;margin:6px 0">
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
        const title=segment.name || "Unterereignis";
        return `<details class="card child-segment-card" data-child-segment data-child-id="${escapeHtml(segment.id)}" open>
          <summary><strong data-child-summary>${escapeHtml(title)}</strong> <span class="muted">· ${escapeHtml(start)}–${escapeHtml(end)}</span></summary>
          <div class="child-segment-fields">
            <label class="edit-field"><span>Name</span><input data-child-name value="${escapeHtml(segment.name||"")}" ${structural ? "" : "disabled"}></label>
            <div class="child-segment-boundary">
              <label class="edit-field"><span>Beginn</span><input data-child-start-date type="date" value="${escapeHtml(isoDate(segment.start_datetime))}" ${structural ? "" : "disabled"}></label>
              <label class="edit-field"><span>Startzeit</span><input data-child-start-time type="time" value="${escapeHtml(start)}" ${structural ? "" : "disabled"}></label>
            </div>
            <div class="child-segment-end-row">
              <div class="child-segment-boundary">
                <label class="edit-field"><span>Ende</span><input data-child-end-date type="date" value="${escapeHtml(isoDate(segment.end_datetime))}" ${structural ? "" : "disabled"}></label>
                <label class="edit-field"><span>Endzeit</span><input data-child-end-time type="time" value="${escapeHtml(end)}" ${structural ? "" : "disabled"}></label>
              </div>
              ${structural ? `<button type="button" data-remove-child-segment class="danger-button child-segment-remove">Unterereignis entfernen</button>` : ""}
            </div>
          </div>
        </details>`;
      }).join("");

      eventEditBody.innerHTML = `
        <div id="event-edit-inline-error" class="edit-inline-error" role="alert" hidden></div>
        ${archivedChange ? `<div class="edit-warning">ARCHIVIERTES Ereignis: Die Kamerabibliothek bleibt strikt read-only. Nach dem Speichern erhältst du einen manuellen Änderungsauftrag mit IST- und SOLL-Zustand.</div><br>` : ""}
        <div class="edit-grid">
          <label class="edit-field full"><span>Ereignisname</span><input id="edit-name" maxlength="160" value="${escapeHtml(event.display_title || event.name)}" ${noEvent ? "disabled" : ""}></label>
          ${noEvent ? `
            <div class="edit-field full">
              <div style="display:flex;justify-content:space-between;align-items:center;gap:10px;margin-bottom:8px"><span>Tagessegmente</span>${structural ? `<button id="add-no-event-segment" type="button">＋ Tagessegment hinzufügen</button>` : ""}</div>
              <div id="no-event-segments">${segmentHtml || `<p class="muted">Noch keine Segmente.</p>`}</div>
              <p class="muted">Jeder Tag bzw. Teil eines Tages wird separat gespeichert. Zwischenräume gehören ausdrücklich nicht zu „Ohne Ereignis“.</p>
            </div>
            <label class="edit-field"><span>Tagesordner</span><select id="edit-preserve" ${structural ? "" : "disabled"}><option value="0" ${event.preserve_day_folders ? "" : "selected"}>Nicht erhalten</option><option value="1" ${event.preserve_day_folders ? "selected" : ""}>Erhalten</option></select></label>` : `
          <div class="edit-boundaries">
            <div class="edit-boundary">
              <label class="edit-field"><span>Beginn</span><input id="edit-start-date" type="date" value="${escapeHtml(isoDate(event.start_datetime))}" ${structural ? "" : "disabled"}></label>
              <label class="edit-field"><span>Startzeit</span><input id="edit-start-time" type="time" value="${escapeHtml(isoTime(event.start_datetime,'00:00'))}" ${structural ? "" : "disabled"}></label>
            </div>
            <div class="edit-boundary">
              <label class="edit-field"><span>Ende</span><input id="edit-end-date" type="date" value="${escapeHtml(isoDate(event.end_datetime))}" ${structural ? "" : "disabled"}></label>
              <label class="edit-field"><span>Endzeit</span><input id="edit-end-time" type="time" value="${escapeHtml(isoTime(event.end_datetime,'23:59'))}" ${structural ? "" : "disabled"}></label>
            </div>
          </div>
          <label class="edit-field"><span>Tagesordner</span><select id="edit-preserve" ${structural ? "" : "disabled"}><option value="0" ${event.preserve_day_folders ? "" : "selected"}>Nicht erhalten</option><option value="1" ${event.preserve_day_folders ? "selected" : ""}>Erhalten</option></select></label>
          <input id="edit-time-enabled" type="hidden" value="1">
          <div class="edit-field full"><span>Optionale Unterereignisse</span><div id="normal-event-segments">${normalSegmentHtml}</div><button id="add-normal-segment" type="button">Unterereignis hinzufügen</button></div>`}

          <label class="edit-field full"><span>Notizen</span><textarea id="edit-notes" maxlength="4000">${escapeHtml(event.notes || "")}</textarea></label>
        </div>
        <div class="edit-actions">
          <button type="button" id="edit-cancel">Abbrechen</button>
          <button type="submit" class="plan-button bk-positive-action">${event.status === "applied" ? "Änderungen anwenden" : "Änderungen speichern"}</button>
        </div>`;

      if (!noEvent) {
        const normalContainer=document.getElementById('normal-event-segments');
        const bind=()=>{
          normalContainer.querySelectorAll('[data-child-segment]').forEach(row=>{
            const remove=row.querySelector('[data-remove-child-segment]');
            if (remove) remove.onclick=()=>row.remove();
            const nameInput=row.querySelector('[data-child-name]');
            const summary=row.querySelector('[data-child-summary]');
            if (nameInput && summary) {
              const syncSummary=()=>{ summary.textContent=String(nameInput.value||"").trim() || "Unterereignis"; };
              nameInput.oninput=syncSummary;
              syncSummary();
            }
          });
        };
        bind();
        document.getElementById('add-normal-segment').onclick=()=>{
          const row=document.createElement('details');
          row.open=true;
          row.dataset.childSegment='1';
          row.className='card child-segment-card';
          row.innerHTML=`<summary><strong data-child-summary>Unterereignis</strong></summary><div class="child-segment-fields">
            <label class="edit-field"><span>Name</span><input data-child-name></label>
            <div class="child-segment-boundary">
              <label class="edit-field"><span>Beginn</span><input data-child-start-date type="date" value="${isoDate(event.start_datetime)}"></label>
              <label class="edit-field"><span>Startzeit</span><input data-child-start-time type="time" value="${isoTime(event.start_datetime,"00:00")}"></label>
            </div>
            <div class="child-segment-end-row">
              <div class="child-segment-boundary">
                <label class="edit-field"><span>Ende</span><input data-child-end-date type="date" value="${isoDate(event.end_datetime)}"></label>
                <label class="edit-field"><span>Endzeit</span><input data-child-end-time type="time" value="${isoTime(event.end_datetime,"23:59")}"></label>
              </div>
              <button type="button" class="danger-button child-segment-remove" data-remove-child-segment>Unterereignis entfernen</button>
            </div>
          </div>`;
          normalContainer.appendChild(row);
          bind();
        };
      } else if (structural) {
        const container=document.getElementById("no-event-segments");
        const bindNoEventRows=()=>{
          container.querySelectorAll("[data-remove-segment]").forEach(button=>{button.onclick=()=>button.closest("[data-segment-row]")?.remove();});
          container.querySelectorAll("[data-segment-day-number]").forEach(input=>{input.oninput=()=>{const hidden=input.closest("[data-segment-row]")?.querySelector("[data-segment-day]");const maxDay=new Date(Number(fixedNoEventMonth.slice(0,4)),Number(fixedNoEventMonth.slice(5,7)),0).getDate();const n=Math.max(1,Math.min(maxDay,Number(input.value||0)));if(hidden&&Number(input.value||0)>0)hidden.value=`${fixedNoEventMonth}-${String(n).padStart(2,"0")}`;};});
        };
        bindNoEventRows();
        document.getElementById("add-no-event-segment")?.addEventListener("click",()=>{
          const row=document.createElement("details");row.className="no-event-segment card collapse-card";row.dataset.segmentRow="1";row.open=true;row.style.cssText="display:block;padding:8px 10px;margin:6px 0";
          row.innerHTML=`<summary style="cursor:pointer;display:flex;align-items:center;gap:6px"><strong>Neues Tagessegment</strong><span class="muted">· 00:00–23:59</span></summary><div style="display:grid;grid-template-columns:minmax(0,2fr) minmax(0,1fr) minmax(0,1fr) 120px;gap:8px;align-items:end;margin-top:8px;width:100%;box-sizing:border-box">${noEventDayControl(fixedNoEventMonth,"",true)}<label class="edit-field"><span>Von</span><input type="time" data-segment-start value="00:00"></label><label class="edit-field"><span>Bis</span><input type="time" data-segment-end value="23:59"></label><button type="button" data-remove-segment class="danger-button" style="width:100%;min-width:0;align-self:end;white-space:nowrap">Entfernen</button></div>`;
          container.appendChild(row);bindNoEventRows();row.querySelector("[data-segment-day-number]")?.focus();
        });
      }
      document.getElementById("edit-cancel").addEventListener("click", () => eventEditDialog.close());
    }

    function showEventEditError(message) {
      let node=document.getElementById("event-edit-inline-error");
      if(!node){node=document.createElement("div");node.id="event-edit-inline-error";node.className="edit-inline-error";node.setAttribute("role","alert");eventEditBody.prepend(node);}
      node.textContent=String(message||"Unbekannter Fehler");node.hidden=false;node.scrollIntoView({block:"nearest"});
    }

    async function openEventEditor(eventId, jobId) {
      eventEditDialog.classList.remove("view-mode");
      eventEditDialog.classList.add("edit-mode");
      eventEditBody.textContent = "Bearbeitungsdaten werden geladen …";
      if (!eventEditDialog.open) eventEditDialog.showModal();
      const context = await requestJson(`/api/jobs/${encodeURIComponent(jobId)}/events/${encodeURIComponent(eventId)}/edit`);
      context._job_id = jobId;
      renderEventEditor(context);
    }

    function confirmEditEmptySubevents(error) {
      if (error?.data?.confirmation_required !== "empty_subevents") return false;
      const names=(error.data.empty_subevents||[]).map(item=>String(item.name||"Unterereignis"));
      return window.confirm(
        "Mindestens ein Unterereignis enthält aktuell keine passenden Dateifamilien."
        + (names.length ? "\n\nOhne passende Dateifamilien: "+names.join(", ") : "")
        + "\n\nDie leere Ordnerstruktur wird trotzdem angelegt. Trotzdem fortfahren?"
      );
    }

    async function updateEventWithEmptySubeventConfirmation(context, payload) {
      const url=`/api/jobs/${encodeURIComponent(context._job_id)}/events/${encodeURIComponent(context.event.id)}`;
      const requestBody=body=>requestJson(url,{
        method:"PUT",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify(body),
      });
      try {
        return await requestBody(payload);
      } catch (error) {
        if (!confirmEditEmptySubevents(error)) throw error;
        return requestBody({...payload,confirm_empty_subevents:true});
      }
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
          Object.assign(payload, {
            event_kind:'event',start_date:document.getElementById('edit-start-date').value,
            end_date:document.getElementById('edit-end-date').value,
            start_time:document.getElementById('edit-start-time').value,end_time:document.getElementById('edit-end-time').value,
            uses_time_range:true,preserve_day_folders:document.getElementById('edit-preserve').value==='1',
            subevents:[...eventEditBody.querySelectorAll('[data-child-segment]')].map(row=>({
              id:row.dataset.childId||null,
              name:row.querySelector('[data-child-name]').value,
              start_datetime:row.querySelector('[data-child-start]')
                ? row.querySelector('[data-child-start]').value
                : `${row.querySelector('[data-child-start-date]').value}T${row.querySelector('[data-child-start-time]').value}:00`,
              end_datetime:row.querySelector('[data-child-end]')
                ? row.querySelector('[data-child-end]').value
                : `${row.querySelector('[data-child-end-date]').value}T${row.querySelector('[data-child-end-time]').value}:59`
            }))
          });
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
      result = await updateEventWithEmptySubeventConfirmation(context, payload);
      eventEditDialog.close();

      if (result.archive_manual?.change_request_ids?.length) {
        const crId = result.archive_manual.change_request_ids[0];
        if (!changeRequestDialog.open) changeRequestDialog.showModal();
        await showChangeRequestDetail(crId);
        setStatus("Archivberührung erkannt: manueller IST→SOLL-Auftrag vorbereitet. Die Kamerabibliothek wurde nicht verändert.", false, true);
        refreshGlobalTasks();
        return;
      }
      const cascadeNeedsReconcile = (result.cascade?.preview?.items || []).some(
        item => String(item.status || "") === "applied"
      );
      const needsReconcile = Boolean(result.resort_required || cascadeNeedsReconcile);
      const appliedTransaction = context.event.status === "applied" && Boolean(result.mutation_id);

      if (appliedTransaction && needsReconcile) {
        await loadEvents({reset:true});
        await loadReapplyPlan(
          context.event.id,
          context._job_id,
          {mandatory:true,mutationId:result.mutation_id}
        );
        setStatus(
          "Applied-Änderung vorbereitet. Jetzt anwenden oder vollständig verwerfen.",
          false,
          true
        );
        return;
      }

      if (result.reassignment_required && (result.removed_family_ids || []).length) {
        await openReassignmentWorkflow(context.event.id, context._job_id, Boolean(result.resort_required));
      } else {
        if (needsReconcile) {
          await loadReapplyPlan(context.event.id, context._job_id);
          setStatus(
            "Änderung gespeichert. Bitte den angezeigten Nachsortierplan prüfen und ausdrücklich bestätigen.",
            false,
            true
          );
        } else {
          const plannedCascade = String(result.mutation_id || "") && !Boolean(result.resort_required);
          setStatus(
            plannedCascade
              ? "Gemeinsame Planänderung gespeichert."
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
          await loadReapplyPlan(ctx.eventId, ctx.jobId);
          setStatus(
            "Neu-Zuordnung vollständig. Bitte den Nachsortierplan prüfen und ausdrücklich bestätigen.",
            false,
            true
          );
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
      reassignmentBody.innerHTML = `<p>Ausgangsereignis: ${escapeHtml(data.event?.name || ctx.eventId)}</p>` + exactSegments.map(segment=>
        `<div class="card"><strong>${escapeHtml(segment.day_key)} · ${escapeHtml(segment.start_time)}–${escapeHtml(segment.end_time)}</strong><p>${Number(segment.family_count||0)} Familien · ${Number(segment.file_count||0)} Dateien</p></div>`).join("") +
        `<div class="reassignment-dialog-action"><a class="plan-button bk-positive-action" href="/workspace?job=${encodeURIComponent(ctx.jobId)}&task=free">In Aufnahmen öffnen</a></div>`;
    }


    reassignmentClose.addEventListener("click", () => reassignmentDialog.close());

    async function loadReapplyPlan(eventId, jobId, options={}) {
      const event = currentEvents.find(item => item.id === eventId && (!jobId || item._job_id === jobId));
      if (!jobId || !event) throw new Error("Ereignis wurde nicht gefunden.");
      mandatoryMutationContext = options.mandatory
        ? {eventId,jobId,mutationId:String(options.mutationId||event.mutation_id||"")}
        : null;
      sortPlanCloseButton.hidden = false;
      sortPlanCloseButton.textContent = mandatoryMutationContext ? "Änderungen verwerfen" : "Schließen";
      sortPlanCloseButton.classList.toggle("danger-button", Boolean(mandatoryMutationContext));
      sortPlanTitle.textContent = mandatoryMutationContext
        ? `Änderungen anwenden · ${event.name}`
        : `Nachsortierung · ${event.name}`;
      sortPlanSubtitle.textContent = "Alte und neue Pfade werden rein lesend geprüft …";
      sortPlanBody.textContent = "Dateien, Ziele und Konflikte werden geprüft …";
      if (!sortPlanDialog.open) sortPlanDialog.showModal();
      const plan = await requestJson(`/api/jobs/${encodeURIComponent(jobId)}/events/${encodeURIComponent(eventId)}/reconcile-plan`);
      plan._job_id = jobId;
      plan._reapply = true;
      plan._reconcile = true;
      plan._mandatory = Boolean(mandatoryMutationContext);
      renderSortPlan(plan);
    }

    async function loadSortPlan(eventId, jobId) {
      mandatoryMutationContext = null;
      sortPlanCloseButton.hidden = false;
      sortPlanCloseButton.textContent = "Schließen";
      sortPlanCloseButton.classList.remove("danger-button");
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
          ? "Die Dateien werden nach deiner Bestätigung wieder in den freien Tagesbestand zurückgeführt. Anschließend wird das Ereignis wirklich entfernt. Dieser Vorgang muss jetzt angewendet oder verworfen werden."
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

      if (result.change_request_id) {
        await loadEvents({reset:true});
        refreshGlobalTasks();
        if (!changeRequestDialog.open) changeRequestDialog.showModal();
        await showChangeRequestDetail(result.change_request_id);
        setStatus("Manueller Löschauftrag erstellt. Die Kamerabibliothek wurde nicht verändert.", false, true);
        return;
      }
      if (result.pending_delete) {
        await loadEvents({reset:true});
        await loadReapplyPlan(
          eventId,
          jobId,
          {mandatory:true,mutationId:result.mutation_id}
        );
        setStatus(
          "Löschung vorbereitet. Jetzt anwenden oder vollständig verwerfen.",
          false,
          true
        );
        return;
      }
      await loadEvents({reset:true});
      refreshGlobalTasks();
      setStatus(`Ereignis gelöscht: ${result.event_name} · ${Number(result.released_family_count||0)} Familien wieder frei.`, false, true);
    }




    eventEditClose.addEventListener("click", () => eventEditDialog.close());
    changeRequestClose.addEventListener("click", () => changeRequestDialog.close());
    eventEditForm.addEventListener("submit", event => {
      event.preventDefault();
      const old=document.getElementById("event-edit-inline-error");if(old)old.hidden=true;
      saveEventEditor().catch(error => showEventEditError(error.message));
    });

    async function discardMandatoryMutation() {
      const ctx=mandatoryMutationContext;
      if (!ctx) {
        sortPlanDialog.close();
        return;
      }
      if (!window.confirm("Diese Applied-Änderung vollständig verwerfen und den Zustand vor der Bearbeitung wiederherstellen?")) return;
      await requestJson(
        `/api/jobs/${encodeURIComponent(ctx.jobId)}/event-mutations/${encodeURIComponent(ctx.mutationId)}/cancel`,
        {method:"POST"}
      );
      mandatoryMutationContext=null;
      sortPlanDialog.close();
      sortPlanCloseButton.classList.remove("danger-button");
      sortPlanCloseButton.textContent="Schließen";
      sortPlanCloseButton.hidden=false;
      await loadEvents({reset:true});
      refreshGlobalTasks();
      setStatus("Änderung verworfen. Der vorherige Zustand wurde wiederhergestellt.",false,true);
    }

    sortPlanCloseButton.addEventListener(
      "click",
      () => discardMandatoryMutation().catch(error=>setStatus(error.message,true))
    );

    sortPlanDialog.addEventListener("cancel", event => {
      if (mandatoryMutationContext) event.preventDefault();
    });


    eventList.addEventListener(
      "click",
      event => {
        const viewButton = event.target.closest("[data-view-event]");
        if (viewButton && !viewButton.disabled) {
          openEventViewer(
            viewButton.dataset.viewEvent,
            viewButton.dataset.jobId
          ).catch(error => {
            eventEditBody.textContent = error.message;
            setStatus(error.message, true);
          });
          return;
        }

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

        if (deleteButton && !deleteButton.disabled) {
          deleteEvent(
            deleteButton.dataset.deleteEvent,
            deleteButton.dataset.jobId
          ).catch(
            error => setStatus(
              error.message,
              true
            )
          );
          return;
        }

        if (event.target.closest("button,a,input,select,textarea,summary")) {
          return;
        }

        const card = event.target.closest(".event-card");
        if (card) {
          const actions = card.querySelector(".event-card-actions");
          if (actions) {
            const willOpen = actions.hidden;
            actions.hidden = !willOpen;
            card.classList.toggle("is-open", willOpen);
          }
        }
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
          html += `<section class="preview-note"><strong>Neu zuzuordnen</strong>${(archiveReassignData.reassignment_segments||[]).map(s=>`<p>${escapeHtml(s.day_key)} · ${escapeHtml(s.start_time)}–${escapeHtml(s.end_time)} · ${Number(s.family_count)} Familien · ${Number(s.file_count)} Dateien</p>`).join('')}<a class="plan-button bk-positive-action" href="/workspace?job=${encodeURIComponent(archiveReassignData.job_id)}&task=free">In Aufnahmen öffnen</a></section>`;
        }

        // Workflow-Aktionen (propose -> preview -> confirm / cancel / archive)
        const status = String(cr.status || "");
        html += "<h4>Workflow</h4>";
        html += `<p><strong>Status:</strong> ${escapeHtml(status)}</p>`;
        if (status === "aenderbar_vorschlagen") {
          html +=
            `<button type="button" class="plan-button" data-cr-confirm="${escapeHtml(crId)}">Änderungen bestätigen</button>` +
            ` <button type="button" class="danger-button" data-cr-cancel="${escapeHtml(crId)}">Änderung verwerfen</button>`;
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
            ` <button type="button" class="danger-button" data-cr-cancel="${escapeHtml(crId)}">Änderung verwerfen</button>`;
        } else {
          html += `<p class="muted">Dieser Aenderungsantrag ist abgeschlossen (${escapeHtml(status)}).</p>`;
        }

        changeRequestBody.innerHTML = html;

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
      } else if (task.startsWith("reassign:")) {
        const eventId = task.slice("reassign:".length);
        if (jobId) {
          const data = await requestJson(`/api/jobs/${encodeURIComponent(jobId)}/events`);
          const target = (data.events||[]).find(item=>item.id===eventId);
          if (target && !currentEvents.some(item=>item.id===eventId)) {
            currentEvents.push({...target,_job_id:jobId});
          }
          await openReassignmentWorkflow(
            eventId,
            jobId,
            Boolean(target?.resort_required)
          );
        }
      } else if (task.startsWith("resort:")) {
        const eventId = task.slice("resort:".length);
        if (jobId) {
          const data = await requestJson(`/api/jobs/${encodeURIComponent(jobId)}/events`);
          const target = (data.events||[]).find(item=>item.id===eventId);
          if (target && !currentEvents.some(item=>item.id===eventId)) currentEvents.push({...target,_job_id:jobId});
          await loadReapplyPlan(eventId, jobId);
        }
      }
      if (!task) {
        const pending=currentEvents.find(item =>
          item.status === "applied"
          && item.mutation_id
          && item.id === item.mutation_anchor_event_id
        );
        if (pending) {
          await loadReapplyPlan(
            pending.id,
            pending._job_id || pending.job_id,
            {mandatory:true,mutationId:pending.mutation_id}
          );
        }
      }
      refreshGlobalTasks();
    }).catch(error => setStatus(error.message,true));
  </script>
</body>
</html>
"""
