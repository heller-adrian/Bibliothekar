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
      font-family: Futura, "Helvetica Neue", Helvetica, Arial, sans-serif;
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
    .edit-boundary { display:grid;grid-template-columns:minmax(150px,1.18fr) minmax(140px,.82fr);gap:8px;align-items:end; }
    .edit-date-entry{display:grid;grid-template-columns:minmax(0,1fr) 42px;gap:6px;align-items:center}
    .edit-date-entry>input{min-width:0}
    .edit-date-picker{width:42px;min-width:42px;padding:0;display:grid;place-items:center}
    .inspect-more { margin-top:9px; }
    @media (max-width:760px){.edit-boundaries{grid-template-columns:1fr}}
    @media (max-width:440px){.edit-boundary{grid-template-columns:1fr}}

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
    .status:empty { display:none; }

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

    .change-stepper {
      display:grid;
      grid-template-columns:repeat(auto-fit,minmax(150px,1fr));
      gap:8px;
      margin:0 0 18px;
    }
    .change-step {
      min-height:56px;
      display:grid;
      grid-template-columns:auto minmax(0,1fr);
      gap:9px;
      align-items:center;
      border:1px solid var(--border);
      border-radius:13px;
      background:var(--surface-2);
      padding:9px 11px;
      text-align:left;
    }
    .change-step:disabled {
      opacity:1;
      cursor:default;
    }
    .change-step.active {
      border:2px solid var(--accent) !important;
      background:color-mix(in srgb,var(--accent) 16%,var(--surface-2)) !important;
      color:var(--text);
    }
    .change-step.active .change-step-number {
      background:var(--accent);
      color:var(--surface);
      border-color:var(--accent);
    }
    .change-step.done {
      border-color:var(--success) !important;
      color:var(--success);
    }
    .change-step-number {
      display:grid;
      place-items:center;
      width:28px;
      height:28px;
      border:1px solid currentColor;
      border-radius:999px;
      font-weight:800;
    }
    .change-pane {
      display:grid;
      gap:12px;
    }
    .change-pane-heading {
      display:flex;
      justify-content:space-between;
      gap:12px;
      align-items:flex-start;
    }
    .change-pane-heading h3 { margin-bottom:4px; }
    .change-operation {
      padding:0;
      overflow:hidden;
    }
    .change-operation > summary {
      cursor:pointer;
      padding:13px 14px;
      font-weight:750;
    }
    #change-request-dialog details > summary {
      list-style:none !important;
      display:grid !important;
      grid-template-columns:22px minmax(0,1fr) auto !important;
      align-items:center !important;
      justify-content:initial !important;
      gap:8px !important;
      text-align:left !important;
      cursor:pointer;
    }
    #change-request-dialog details > summary::-webkit-details-marker {
      display:none !important;
    }
    #change-request-dialog details > summary::marker {
      content:"" !important;
    }
    #change-request-dialog details > summary::before {
      content:"▸";
      display:block;
      width:22px;
      font-size:19px;
      font-weight:700;
      line-height:1;
      text-align:center;
      color:currentColor;
    }
    #change-request-dialog details[open] > summary::before {
      content:"▾";
    }

    .change-operation[open] > summary {
      border-bottom:1px solid var(--border);
    }
    .change-operation-body {
      display:grid;
      gap:8px;
      padding:12px 14px 14px;
    }
    .change-footer {
      display:flex;
      justify-content:flex-end;
      gap:9px;
      flex-wrap:wrap;
      margin-top:14px;
    }
    .change-progress {
      display:none;
      gap:8px;
      margin-top:12px;
    }
    .change-progress.active { display:grid; }
    .change-refresh-button {
      position:relative;
      overflow:hidden;
      white-space:nowrap;
    }
    .change-refresh-button.loading::after {
      content:"";
      position:absolute;
      left:0;
      bottom:0;
      height:3px;
      width:38%;
      background:currentColor;
      animation:change-refresh-slide .8s ease-in-out infinite alternate;
    }
    @keyframes change-refresh-slide {
      from { transform:translateX(-15%); }
      to { transform:translateX(180%); }
    }
    .badge.danger { color:var(--danger); }
    .change-progress-track {
      height:9px;
      overflow:hidden;
      border-radius:999px;
      background:rgba(127,127,127,.22);
    }
    .change-progress-bar {
      width:0;
      height:100%;
      background:currentColor;
      transition:width .25s ease;
    }
    .change-target-tree {
      margin:0;
      padding:12px;
      border:1px solid var(--border);
      border-radius:12px;
      background:var(--surface-2);
      white-space:pre;
      overflow:auto;
      font-family:Futura, "Helvetica Neue", Helvetica, Arial, sans-serif;
      font-size:.84rem;
      line-height:1.5;
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
      font-family:Futura, "Helvetica Neue", Helvetica, Arial, sans-serif;
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
      white-space:pre;
      overflow-wrap:normal;
      overflow-x:hidden;
      font-family:Futura, "Helvetica Neue", Helvetica, Arial, sans-serif;
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
      overflow-x: hidden;
      border: 1px solid var(--border);
      border-radius: 13px;
      background: var(--surface-2);
      padding: 13px;
      color: var(--text);
      font-family: Futura, "Helvetica Neue", Helvetica, Arial, sans-serif;
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
      font-family: Futura, "Helvetica Neue", Helvetica, Arial, sans-serif;
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
      font-family: Futura, "Helvetica Neue", Helvetica, Arial, sans-serif;
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
      font-family: Futura, "Helvetica Neue", Helvetica, Arial, sans-serif;
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
    .event-operation-loading { display:flex; align-items:center; gap:12px; padding:18px 14px; border:1px solid var(--bk-line,var(--border)); border-radius:12px; background:var(--bk-surface,var(--surface)); color:var(--bk-muted,var(--muted)); }
    .event-operation-spinner { flex:0 0 18px; width:18px; height:18px; border:2px solid currentColor; border-right-color:transparent; border-radius:50%; animation:event-operation-spin .75s linear infinite; }
    @keyframes event-operation-spin { to { transform:rotate(360deg); } }
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
    .child-segment-top { display:flex; align-items:end; justify-content:space-between; gap:12px; }
    .child-segment-name { flex:0 1 55%; min-width:220px; }
    .child-segment-boundaries { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:10px; }
    .child-segment-boundary { display:grid; grid-template-columns:minmax(160px,1.25fr) minmax(130px,.75fr); gap:8px; align-items:end; }
    .child-segment-remove { white-space:nowrap; align-self:end; min-height:44px; flex:0 0 auto; }
    @media (max-width:760px) {
      .child-segment-boundaries { grid-template-columns:1fr; }
    }
    @media (max-width:520px) {
      .child-segment-top { align-items:stretch; }
      .child-segment-name { min-width:0; flex:1 1 auto; }
      .child-segment-boundary { grid-template-columns:1fr; }
      .child-segment-remove { min-width:44px; }
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
  
    /* 0.40.1: mobile Ereignisansicht kompakt und vollständig bedienbar. */
    .no-event-segment-fields {
      display:grid;
      grid-template-columns:minmax(0,2fr) minmax(0,1fr) minmax(0,1fr) 120px;
      gap:8px;
      align-items:end;
      margin-top:8px;
      width:100%;
      box-sizing:border-box;
    }
    .no-event-segment-remove {
      width:100%;
      min-width:0;
      align-self:end;
      white-space:nowrap;
    }

    @media (max-width:820px) {
      section.summary {
        grid-template-columns:repeat(3,minmax(0,1fr));
        gap:6px;
        margin-bottom:12px;
      }
      section.summary .card {
        min-height:40px;
        padding:6px 7px;
        border-radius:11px;
        display:flex;
        align-items:center;
        justify-content:space-between;
        gap:4px;
      }
      section.summary .card .muted {
        min-width:0;
        font-size:clamp(.56rem,2.15vw,.72rem);
        line-height:1.05;
      }
      section.summary .card .number {
        flex:0 0 auto;
        margin:0;
        font-size:clamp(.95rem,4vw,1.2rem);
        line-height:1;
        text-align:right;
        white-space:nowrap;
      }

      .event-card-actions {
        display:flex;
        flex-wrap:nowrap;
        gap:4px;
      }
      .event-card-actions > button,
      .event-card-actions > a {
        flex:1 1 0;
        min-width:0;
        min-height:34px;
        padding:6px 3px !important;
        font-size:clamp(.62rem,2.65vw,.78rem);
        line-height:1.05;
        white-space:nowrap;
        justify-content:center;
        text-align:center;
      }

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
      section.summary .card {
        padding-inline:6px;
      }
      section.summary .card .muted {
        font-size:clamp(.54rem,2.35vw,.66rem);
      }
      .event-card-actions {
        gap:3px;
      }
      .event-card-actions > button,
      .event-card-actions > a {
        padding-inline:2px !important;
        font-size:clamp(.59rem,2.72vw,.7rem);
      }
    }

    /* 0.47.8: mobile Browserseite und installierte Web-App.
       Drei Aktionen bei geplanten Ereignissen muessen nebeneinander
       bleiben, ohne dass 'Sortierung prüfen' den Button verlaesst. */
    @media (max-width:820px) {
      body.bibliothekar-redesign[data-bk-area="workspace"]
      .event-card-actions > button,
      body.bibliothekar-redesign[data-bk-area="workspace"]
      .event-card-actions > a {
        min-width:0 !important;
        max-width:100%;
        padding-inline:2px !important;
        font-size:clamp(.625rem,2.8vw,.72rem) !important;
        letter-spacing:-.02em;
        line-height:1.12;
        white-space:nowrap;
        text-align:center;
      }
    }

    /* 0.40.2: mobile No-Event-Zeitsegmente mit zwei vollständigen Datums-/Zeitzeilen. */
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

/* 0.45.2: Neuladen neben der Suche, auch auf kleinen Geräten. */
.event-browser-toolbar { display:flex; gap:12px; align-items:end; flex-wrap:wrap; }
.event-browser-toolbar .event-browser-search { flex:1 1 220px; min-width:0; }
#event-reload { min-height:40px; white-space:nowrap; }
@media(max-width:700px){
 .event-browser-toolbar { display:grid; grid-template-columns:minmax(0,1fr) auto; align-items:end; }
 .event-browser-toolbar .event-browser-heading { grid-column:1 / -1; }
 .event-browser-toolbar .event-browser-search { grid-column:1; min-width:0; }
 #event-reload { grid-column:2; }
}


/* 0.45.3: Ruhe und Abstand zwischen Überschrift und Ereignissuche. */
.event-browser-toolbar {
  display:grid !important;
  grid-template-columns:minmax(0,max-content) minmax(200px,1fr) auto;
  gap:12px 32px !important;
  align-items:end;
}
.event-browser-heading { min-width:0; }
.event-browser-search { min-width:0 !important; width:100%; }
.bk-event-search-field { position:relative; width:100%; }
.bk-event-search-field #event-search {
  box-sizing:border-box; width:100%; min-width:0;
  padding-left:40px !important; min-height:42px;
}
.bk-event-search-icon {
  position:absolute; left:13px; top:50%; transform:translateY(-50%);
  pointer-events:none; z-index:1; color:var(--muted);
}
.bk-visually-hidden {
  position:absolute !important; width:1px;height:1px;
  overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;
}
@media(max-width:760px){
  .event-browser-toolbar { grid-template-columns:minmax(0,1fr) auto; gap:14px 10px !important; }
  .event-browser-heading { grid-column:1 / -1; }
  .event-browser-search { grid-column:1; }
  #event-reload { grid-column:2; }
}

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
        <div class="event-browser-search">
          <label class="bk-visually-hidden" for="event-search">Ereignisse durchsuchen</label>
          <div class="bk-event-search-field">
            <svg class="bk-event-search-icon" viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
              <circle cx="10.8" cy="10.8" r="6.8" fill="none" stroke="currentColor" stroke-width="1.8"></circle>
              <path d="m16 16 5 5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"></path>
            </svg>
            <input id="event-search" type="search" placeholder="Suche nach Name, Datum oder Sicherung …" autocomplete="off">
          </div>
        </div>
        <button id="event-reload" type="button" title="Ereignisse und Dateibestand erneut vollständig prüfen">Neuladen</button>
      </div>

      <div
        id="event-list"
        class="event-list"
      >
        <div class="empty bk-loading-status">
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

  <dialog id="structure-change-dialog" class="sort-plan-dialog">
    <div class="sort-plan-content">
      <div class="sort-plan-header">
        <div>
          <h2>Manuelle Ereignisänderung</h2>
          <p id="structure-change-subtitle" class="muted">Der reale Dateisystemzustand wird mit Bibliothekar abgeglichen.</p>
        </div>
        <button id="structure-change-close" type="button">Schließen</button>
      </div>
      <div id="structure-change-body">Änderung wird geladen …</div>
    </div>
  </dialog>

  <dialog id="legacy-maintenance-dialog" class="sort-plan-dialog">
    <div class="sort-plan-content">
      <div class="sort-plan-header">
        <div>
          <h2>Legacy-Mehrsicherungsstruktur vereinheitlichen</h2>
          <p id="legacy-maintenance-subtitle" class="muted">Alter 0.27-Nachtrag wird rein lesend geprüft.</p>
        </div>
        <button id="legacy-maintenance-close" type="button">Schließen</button>
      </div>
      <div id="legacy-maintenance-body">Wartungsplan wird geladen …</div>
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
      <div id="change-request-inline-error" class="error-box" hidden style="margin:0 0 12px"></div>
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
        panel.innerHTML=count ? `<strong>Offene Aufgaben · ${count}</strong>`+tasks.map(task=>{const rawHref=String(task.href||'/events');const safeHref=rawHref.startsWith('/')&&!rawHref.startsWith('//')?rawHref:'/events';return `<a class="global-task-item" href="${escapeHtml(safeHref)}"><strong>${escapeHtml(String(task.title||'Aufgabe'))}</strong><span>${escapeHtml(String(task.detail||''))}</span></a>`;}).join("") : `<strong>Keine offenen Aufgaben</strong><span class="muted" style="display:block;margin-top:6px">Alles erledigt.</span>`;
      } catch (_) {}
    }
    document.getElementById("global-task-fab")?.addEventListener("click",()=>document.getElementById("global-task-panel")?.classList.toggle("open"));
    refreshGlobalTasks();
    setInterval(refreshGlobalTasks,30000);
    window.addEventListener("resize",()=>requestAnimationFrame(()=>fitVisibleTrees(document)));


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

    const structureChangeDialog = document.getElementById("structure-change-dialog");
    const structureChangeBody = document.getElementById("structure-change-body");
    const structureChangeSubtitle = document.getElementById("structure-change-subtitle");
    document.getElementById("structure-change-close")?.addEventListener("click",()=>structureChangeDialog.close());

    const legacyMaintenanceDialog = document.getElementById("legacy-maintenance-dialog");
    const legacyMaintenanceBody = document.getElementById("legacy-maintenance-body");
    const legacyMaintenanceSubtitle = document.getElementById("legacy-maintenance-subtitle");
    document.getElementById("legacy-maintenance-close")?.addEventListener("click",()=>legacyMaintenanceDialog.close());

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
    let mandatoryArchiveChangeContext = null;

    function archiveChangeIsActive(status) {
      return ["aenderbar_vorschlagen", "aenderbar_bestaetigt"].includes(String(status || ""));
    }

    function hasMandatoryTransaction() {
      return Boolean(mandatoryMutationContext || mandatoryArchiveChangeContext);
    }

    function setChangeTaskInUrl(crId, jobId) {
      const url = new URL(window.location.href);
      if (jobId) url.searchParams.set("job", jobId);
      url.searchParams.set("task", `change:${crId}`);
      history.replaceState(null, "", url);
    }

    function setChangeStepInUrl(step) {
      const url = new URL(window.location.href);
      if (step) url.searchParams.set("change_step", step);
      else url.searchParams.delete("change_step");
      history.replaceState(null, "", url);
    }

    function clearChangeTaskFromUrl(crId) {
      const url = new URL(window.location.href);
      if (url.searchParams.get("task") === `change:${crId}`) {
        url.searchParams.delete("task");
      }
      url.searchParams.delete("change_step");
      history.replaceState(null, "", url);
    }

    function syncArchiveChangeContext(cr) {
      if (archiveChangeIsActive(cr?.status)) {
        mandatoryArchiveChangeContext = {
          crId: String(cr.id),
          eventId: String(cr.event_id || ""),
          jobId: String(cr.job_id || "")
        };
        changeRequestClose.disabled = false;
        changeRequestClose.textContent = "Änderung verwerfen";
        changeRequestClose.classList.add("danger-button");
        setChangeTaskInUrl(cr.id, cr.job_id || "");
        return true;
      }
      if (mandatoryArchiveChangeContext?.crId === String(cr?.id || "")) {
        mandatoryArchiveChangeContext = null;
      }
      changeRequestClose.textContent = "Schließen";
      changeRequestClose.classList.remove("danger-button");
      if (cr?.id) clearChangeTaskFromUrl(cr.id);
      return false;
    }

    async function findOpenArchiveChangeRequest(eventId = null) {
      const res = await fetch("/api/change-requests?job_id=&status=");
      if (!res.ok) return null;
      const data = await res.json();
      return (data.requests || []).find(cr =>
        archiveChangeIsActive(cr.status)
        && (!eventId || String(cr.event_id) === String(eventId))
      ) || null;
    }

    window.addEventListener("beforeunload", event => {
      if (!hasMandatoryTransaction()) return;
      event.preventDefault();
      event.returnValue = "";
    });


    function escapeHtml(value) {
      return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
    }


    function validEditableIsoDate(value){
      const text=String(value||"").trim();
      if(!/^\d{4}-\d{2}-\d{2}$/.test(text))return false;
      const date=new Date(text+"T12:00:00");
      return !Number.isNaN(date.getTime()) && date.toISOString().slice(0,10)===text;
    }

    function openEditableDatePicker(input){
      if(!input||input.disabled)return;
      const picker=document.createElement("input");
      picker.type="date";
      picker.value=validEditableIsoDate(input.value)?input.value:"";
      const min=String(input.dataset.dateMin||input.min||"");
      const max=String(input.dataset.dateMax||input.max||"");
      if(min)picker.min=min;
      if(max)picker.max=max;
      picker.style.cssText="position:fixed;left:50%;bottom:12px;width:2px;height:2px;opacity:.01;z-index:99999";
      document.body.appendChild(picker);
      let done=false;
      const cleanup=()=>{if(done)return;done=true;setTimeout(()=>picker.remove(),0);};
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
      }catch(_){picker.click();}
    }

    document.addEventListener("click",event=>{
      const button=event.target.closest?.("[data-edit-date-picker]");
      if(!button)return;
      event.preventDefault();
      const id=String(button.dataset.editDatePicker||"");
      const input=id
        ? document.getElementById(id)
        : button.parentElement?.querySelector("input[type='text']");
      openEditableDatePicker(input);
    });


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
        (document.documentElement.lang === "de" ? "de-DE" : "en-US"),
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
        (document.documentElement.lang === "de" ? "de-DE" : "en-US"),
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
        const reconcileTargetNotice = isReconcileTarget ? `
          <div class="reassignment-resume"><span><strong>↳ Ziel einer offenen Nachsortierung</strong><br><span class="muted">Dieses geplante Ereignis wird nicht separat angewendet. Es wird zusammen mit dem bearbeiteten Ursprungsereignis im gemeinsamen Nachsortierplan geprüft und angewendet.</span></span></div>` : "";
        card.innerHTML = `
          <div class="event-card-header"><div><strong class="event-name" data-bk-preserve-language>${escapeHtml(event.display_title || event.name)}</strong><div class="event-folder" data-bk-preserve-language>${escapeHtml(event.folder_name||"")}</div><div class="muted">${escapeHtml(String(event.start_datetime||"").slice(0,16))} bis ${escapeHtml(String(event.end_datetime||"").slice(0,16))} · ${Number(event.assigned_family_count||0)} Familien</div></div><span class="status-chip ${statusClass}">${escapeHtml(eventStatusLabel(event.status))}</span></div>
          ${reconcileTargetNotice}
          <div class="event-card-actions" hidden>
            <button type="button" data-view-event="${escapeHtml(event.id)}" data-job-id="${escapeHtml(event._job_id||event.job_id||"")}">Öffnen</button>
            ${isMutationAnchor && Number(event.pending_reassignment_count||0) > 0
              ? `<button type="button" class="plan-button bk-positive-action" data-reassign-event="${escapeHtml(event.id)}" data-job-id="${escapeHtml(event._job_id||event.job_id||"")}" data-resort-required="1">Neu-Zuordnung fortsetzen</button>`
              : ""}
            ${isMutationAnchor && !Number(event.pending_reassignment_count||0)
              ? `<button type="button" class="plan-button bk-positive-action" data-sort-plan-event="${escapeHtml(event.id)}" data-job-id="${escapeHtml(event._job_id||event.job_id||"")}" data-event-status="${escapeHtml(event.status)}">Änderung fortsetzen</button>`
              : ""}
            ${isMutationAnchor
              ? `<button type="button" class="danger-button" data-cancel-mutation="${escapeHtml(event.mutation_id)}" data-job-id="${escapeHtml(event._job_id||event.job_id||"")}">Änderung verwerfen</button>`
              : ""}
            ${isReconcileTarget && event.reconcile_source_event_id
              ? `<a class="plan-button bk-positive-action" href="/events?job=${encodeURIComponent(event._job_id||event.job_id||"")}&task=resort:${encodeURIComponent(event.reconcile_source_event_id)}">Gemeinsame Nachsortierung öffnen</a>`
              : isSortPlannable(event) && !isMutationAnchor
                ? `<button type="button" class="plan-button bk-positive-action" data-sort-plan-event="${escapeHtml(event.id)}" data-job-id="${escapeHtml(event._job_id||event.job_id||"")}" data-event-status="${escapeHtml(event.status)}">Sortierung prüfen</button>`
                : ""}
            ${isDeletable(event)
              ? `<button type="button" class="danger-button" data-delete-event="${escapeHtml(event.id)}" data-job-id="${escapeHtml(event._job_id||event.job_id||"")}">Ereignis löschen</button>`
              : event.mutation_id
                ? `<button type="button" class="danger-button" disabled title="Offene Änderung dieser Sicherung zuerst abschließen oder verwerfen">Ereignis löschen</button>`
                : ""}
          </div>`;
        eventList.appendChild(card);
      }
    }


    async function loadEvents({reset=false,physicalRefresh=false}={}) {
      if (reset) eventOffset = 0;
      const q = eventSearch?.value?.trim() || "";
      const snapshotKey = "bk-events-0452:" + (window.__bkLibraryId || "main") + ":" + q + ":" + eventOffset;
      if (reset && !physicalRefresh) {
        try {
          const saved = JSON.parse(sessionStorage.getItem(snapshotKey) || "null");
          if (saved && Array.isArray(saved.events)) {
            renderEvents(saved.events.map(event => ({...event,_job_id:event.job_id,_job_label:event.source_volume_label || event.job_id})));
            eventResultInfo.textContent = saved.resultInfo || "";
            eventLoadMore.hidden = !saved.has_more;
          }
        } catch (_) {}
      }
      if (!currentEvents.length || physicalRefresh) setStatus("Ereignisse werden geladen …");
      statusElement.classList.add("bk-loading-status");
      let data;
      try {
        data = await requestJson(`/api/events/search?q=${encodeURIComponent(q)}&limit=${eventLimit}&offset=${eventOffset}&physical_refresh=${physicalRefresh ? "true" : "false"}`);
      } finally {
        statusElement.classList.remove("bk-loading-status");
      }
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
      setStatus("");
      if (reset) {
        try {
          const packed = JSON.stringify({...data,resultInfo:eventResultInfo.textContent});
          if (packed.length < 1500000) sessionStorage.setItem(snapshotKey, packed);
        } catch (_) {}
      }
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
        export: "Export",
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
      const assets = family.assets || [];

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
          ${[...files, ...assets].map(
            renderPlanFileCard
          ).join("") || `
            <div class="empty">
              Keine Einzeldateien in dieser Familie.
            </div>
          `}
        </div>
      `;
    }


    function fitMonospaceTree(node) {
      if (!node) return;
      node.style.removeProperty("font-size");
      let size=parseFloat(getComputedStyle(node).fontSize)||14;
      const minimum=10;
      while(node.scrollWidth>node.clientWidth+1 && size>minimum){
        size-=.5;
        node.style.fontSize=size+"px";
      }
    }

    function fitVisibleTrees(root=document) {
      root.querySelectorAll?.(".plan-tree,.inspect-structure").forEach(node=>fitMonospaceTree(node));
    }

    function scheduleVisibleTreeFit(root=document) {
      const run=()=>fitVisibleTrees(root);
      requestAnimationFrame(()=>requestAnimationFrame(run));
      if (document.fonts?.ready) document.fonts.ready.then(()=>requestAnimationFrame(run));
      setTimeout(run,120);
      setTimeout(run,360);
    }
    window.addEventListener("resize",()=>fitVisibleTrees(document));

    function showSortPreparation(eventName, operation="Änderungen") {
      sortPlanTitle.textContent = `${operation} · ${eventName}`;
      sortPlanSubtitle.textContent = "Dateien, Ziele und Konflikte werden rein lesend geprüft …";
      sortPlanBody.innerHTML = '<div class="event-operation-loading" role="status"><span class="event-operation-spinner" aria-hidden="true"></span><span>Bitte warten. Der Prüfungsplan wird vorbereitet …</span></div>';
      sortPlanCloseButton.disabled = true;
      sortPlanCloseButton.hidden = false;
      if (!sortPlanDialog.open) sortPlanDialog.showModal();
    }

    function releaseSortPreparation() {
      sortPlanCloseButton.disabled = false;
    }

    function setEventOperationBusy(message, busy=true) {
      setStatus(message);
      statusElement.classList.toggle("bk-loading-status", Boolean(busy));
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
      const assetsByFamily = new Map();
      for (const asset of (plan.assets || [])) {
        const familyId = Number(asset.family_id);
        if (!Number.isFinite(familyId)) continue;
        if (!assetsByFamily.has(familyId)) assetsByFamily.set(familyId, []);
        assetsByFamily.get(familyId).push({
          ...asset,
          media_type: asset.asset_kind || "other",
          size_matches: Number(asset.source_size_bytes) === Number(asset.expected_size_bytes)
        });
      }
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
                  .filter(Boolean),
                assets: assetsByFamily.get(Number(family.family_id)) || []
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
          <pre class="plan-tree">${escapeHtml(window.BibliothekarI18n?.previewText?.(plan.structure_text) ?? plan.structure_text)}</pre>
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

      scheduleVisibleTreeFit(sortPlanBody);

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
            }
            sortPlanCloseButton.hidden = false;
            sortPlanCloseButton.textContent = "Schließen";
            sortPlanCloseButton.classList.remove("danger-button");

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

    function monthYearForIso(value) {
      const m=String(value||"").match(/^(\d{4})-(\d{2})-(\d{2})$/);
      return m ? `${m[2]}.${m[1]}` : "";
    }

    function noEventDayControl(monthKey, day, structural) {
      const fixedMonth=/^\d{4}-\d{2}$/.test(String(monthKey||""))
        ? String(monthKey)
        : String(day||"").slice(0,7);
      if (!/^\d{4}-\d{2}$/.test(fixedMonth)) {
        return `<label class="edit-field no-event-day-field"><span class="no-event-desktop-caption">Tag</span><select data-segment-day ${structural?"":"disabled"}><option value="${escapeHtml(day)}">${escapeHtml(String(day||"").slice(8,10)||"—")}</option></select></label>`;
      }
      const maxDay=new Date(Number(fixedMonth.slice(0,4)),Number(fixedMonth.slice(5,7)),0).getDate();
      const current=String(day||"").startsWith(fixedMonth+"-") ? String(day) : `${fixedMonth}-01`;
      const options=Array.from({length:maxDay},(_,index)=>{
        const number=String(index+1).padStart(2,"0");
        const value=`${fixedMonth}-${number}`;
        return `<option value="${escapeHtml(value)}" ${value===current?"selected":""}>${number}</option>`;
      }).join("");
      return `<label class="edit-field no-event-day-field"><span class="no-event-desktop-caption">Tag</span><span style="display:grid;grid-template-columns:88px minmax(0,1fr);gap:6px"><select data-segment-day data-locked-month="${escapeHtml(fixedMonth)}" ${structural?"":"disabled"}>${options}</select><input type="text" value="${escapeHtml(monthYearForIso(current))}" disabled aria-label="Monat und Jahr"></span></label>`;
    }
    function noEventDateMirror(day) {
      const value=String(day||"");
      return `<div class="no-event-end-date-mirror" aria-label="Enddatum"><input type="text" data-segment-end-day-display value="${escapeHtml(value.slice(8,10)||"—")}" disabled aria-label="Tag"><input type="text" data-segment-end-month-year-display value="${escapeHtml(monthYearForIso(value))}" disabled aria-label="Monat und Jahr"></div>`;
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
        const key = String(
          family.live_display_stem
          || family.original_stem
          || family.family_key
          || "Dateifamilie"
        ).split("/").pop();
        const capture = String(family.selected_capture_time || "");
        const stamp = capture
          ? `${germanDay(capture.slice(0,10))} ${capture.slice(11,19)}`
          : "Zeit unbekannt";
        const liveKinds = (family.live_asset_kinds || []).map(mediaTypeLabel);
        const count = Number(family.file_count || 0);
        const details = [
          `${count} ${count === 1 ? "Datei" : "Dateien"}`,
          ...liveKinds,
          stamp
        ].join(" · ");
        return `<div class="inspect-family-row"><span title="${escapeHtml(key)}">${escapeHtml(key)}</span><span>${escapeHtml(details)}</span></div>`;
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
      eventEditTitle.textContent=noEvent ? `${event.name} öffnen` : `Ereignis öffnen · ${event.name}`;
      eventEditSubtitle.textContent="Nur-Lesen-Ansicht der aktuell in der Datenbank gespeicherten Definition und Dateizuordnung.";

      const childCards=!noEvent?childEvents.map(child=>{
        const families=inspectRangeFamilies(context,child.start_datetime,child.end_datetime);
        return `<details class="inspect-card collapse-card"><summary><strong>${escapeHtml(child.name||child.folder_name||"Unterereignis")}</strong><span class="muted">${escapeHtml(inspectDateTime(child.start_datetime))} – ${escapeHtml(inspectDateTime(child.end_datetime))}</span></summary>${inspectFamilyRows(families)}</details>`;
      }).join(""):"";

      eventEditBody.innerHTML=`
        <div class="inspect-summary">
          <div class="inspect-field"><span>Status</span><strong>${escapeHtml(eventStatusLabel(event.status))}</strong></div>
          <div class="inspect-field"><span>Art</span><strong>${noEvent?escapeHtml(event.name||"Ohne Ereignis"):"Ereignis"}</strong></div>
          ${noEvent
            ? '<div class="inspect-field"><span>Datenbank-Zeitraum</span><strong>komplex</strong></div>'
            : `<div class="inspect-field"><span>Datenbank-Beginn</span><strong>${escapeHtml(inspectDateTime(event.start_datetime))}</strong></div><div class="inspect-field"><span>Datenbank-Ende</span><strong>${escapeHtml(inspectDateTime(event.end_datetime))}</strong></div>`}
          <div class="inspect-field"><span>Tagesordner</span><strong>${event.preserve_day_folders?"Erhalten":"Nicht erhalten"}</strong></div>
          <div class="inspect-field"><span>Unterordner</span><strong>${context.folder_layout?.structure_enabled?"Erstellen":"Nicht erstellen"}</strong></div>
          <div class="inspect-field"><span>Input</span><strong>${escapeHtml(context.folder_layout?.input_path || "Direkt im Ereignis")}</strong></div>
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
      scheduleVisibleTreeFit(eventEditBody);
    }


    async function openEventViewer(eventId, jobId) {
      const pendingChange = await findOpenArchiveChangeRequest(eventId);
      if (pendingChange) {
        if (eventEditDialog.open) eventEditDialog.close();
        if (!changeRequestDialog.open) changeRequestDialog.showModal();
        await showChangeRequestDetail(pendingChange.id, {resume:true});
        return;
      }
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
      eventEditTitle.textContent = noEvent ? `${event.name} bearbeiten` : `Ereignis bearbeiten · ${event.name}`;
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
          <div class="no-event-segment-fields">
            <div class="no-event-mobile-range-title">Von–Bis</div>
            ${noEventDayControl(fixedNoEventMonth, day, structural)}
            <label class="edit-field no-event-start-field"><span class="no-event-desktop-caption">Von</span><input type="time" data-segment-start value="${escapeHtml(start)}" aria-label="Von" ${structural ? "" : "disabled"}></label>
            ${noEventDateMirror(day)}
            <label class="edit-field no-event-end-field"><span class="no-event-desktop-caption">Bis</span><input type="time" data-segment-end value="${escapeHtml(end)}" aria-label="Bis" ${structural ? "" : "disabled"}></label>
            ${structural ? `<button type="button" data-remove-segment="${index}" class="danger-button no-event-segment-remove">Entfernen</button>` : ""}
          </div>
        </details>`;
      }).join("");

      function editSubeventBounds(){
        return {
          minDate: document.getElementById("edit-start-date")?.value || isoDate(event.start_datetime),
          maxDate: document.getElementById("edit-end-date")?.value || isoDate(event.end_datetime),
          minTime: document.getElementById("edit-start-time")?.value || isoTime(event.start_datetime,"00:00"),
          maxTime: document.getElementById("edit-end-time")?.value || isoTime(event.end_datetime,"23:59"),
        };
      }

      function editShiftDay(value,amount){
        if(!/^\d{4}-\d{2}-\d{2}$/.test(String(value||"")))return "";
        const date=new Date(`${value}T12:00:00`);
        date.setDate(date.getDate()+amount);
        const y=date.getFullYear();
        const m=String(date.getMonth()+1).padStart(2,"0");
        const d=String(date.getDate()).padStart(2,"0");
        return `${y}-${m}-${d}`;
      }

      function editSubeventDays(){
        const {minDate,maxDate}=editSubeventBounds();
        if(!minDate||!maxDate||minDate>maxDate)return [];
        const days=[];
        let day=minDate;
        for(let guard=0;guard<3700 && day<=maxDate;guard+=1){
          days.push(day);
          day=editShiftDay(day,1);
        }
        return days;
      }

      function editSubeventDayOptions(selected){
        const days=editSubeventDays();
        return days.map(day=>{
          const label=day.slice(8,10);
          return `<option value="${escapeHtml(day)}" ${day===selected?"selected":""}>${escapeHtml(label)}</option>`;
        }).join("");
      }

      function editSubeventDayControl(attribute, displayAttribute, selected, label, disabled){
        const days=editSubeventDays();
        const bounds=editSubeventBounds();
        const current=days.includes(selected) ? selected : (days[0]||selected||"");
        return `<label class="edit-field"><span>${escapeHtml(label)}</span><input ${attribute} type="date" min="${escapeHtml(bounds.minDate||"")}" max="${escapeHtml(bounds.maxDate||"")}" value="${escapeHtml(current)}" ${disabled?"disabled":""}></label>`;
      }

      function syncEditSubeventDayDisplay(row, prefix){
        const control=row.querySelector(`[data-child-${prefix}-date]`);
        const display=row.querySelector(`[data-child-${prefix}-month-year]`);
        if(control&&display)display.value=monthYearForIso(control.value);
      }
      function editMinuteAfter(value){
        const match=/^(\d{2}):(\d{2})$/.exec(String(value||""));
        if(!match)return null;
        const total=Number(match[1])*60+Number(match[2])+1;
        if(total>=24*60)return null;
        return `${String(Math.floor(total/60)).padStart(2,"0")}:${String(total%60).padStart(2,"0")}`;
      }

      function nextEditSubeventDefaults(container){
        const bounds=editSubeventBounds();
        const rows=[...container.querySelectorAll("[data-child-segment]")];
        if(!rows.length){
          return {
            startDate:bounds.minDate,
            startTime:bounds.minTime||"00:00",
            endDate:bounds.minDate,
            endTime:bounds.minDate===bounds.maxDate ? (bounds.maxTime||"23:59") : "23:59",
          };
        }
        const previous=rows[rows.length-1];
        const previousDate=previous.querySelector("[data-child-end-date]")?.value||bounds.minDate;
        const previousTime=previous.querySelector("[data-child-end-time]")?.value||"23:59";
        let startDate=previousDate;
        let startTime=editMinuteAfter(previousTime);
        if(!startTime){
          startDate=editShiftDay(previousDate,1);
          startTime="00:00";
        }
        if(!startDate||startDate>bounds.maxDate)return null;
        const endTime=startDate===bounds.maxDate ? (bounds.maxTime||"23:59") : "23:59";
        if(startDate===bounds.maxDate && startTime>endTime)return null;
        return {startDate,startTime,endDate:startDate,endTime};
      }

      const normalSegmentHtml = childEvents.map((segment, index) => {
        const start=isoTime(segment.start_datetime,"00:00");
        const end=isoTime(segment.end_datetime,"23:59");
        const startDate=isoDate(segment.start_datetime);
        const endDate=isoDate(segment.end_datetime);
        const title=segment.name || "Unterereignis";
        return `<details class="card child-segment-card" data-child-segment data-child-id="${escapeHtml(segment.id)}" open>
          <summary><strong data-child-summary>${escapeHtml(title)}</strong> <span class="muted">· ${escapeHtml(start)}–${escapeHtml(end)}</span></summary>
          <div class="child-segment-fields">
            <div class="child-segment-top">
              <label class="edit-field child-segment-name"><span>Name</span><input data-child-name value="${escapeHtml(segment.name||"")}" ${structural ? "" : "disabled"}></label>
              ${structural ? `<button type="button" data-remove-child-segment class="danger-button child-segment-remove">Unterereignis entfernen</button>` : ""}
            </div>
            <div class="child-segment-boundaries">
              <div class="child-segment-boundary">
                ${editSubeventDayControl("data-child-start-date","data-child-start-month-year",startDate,"Beginn",!structural)}
                <label class="edit-field"><span>Startzeit</span><input data-child-start-time type="time" value="${escapeHtml(start)}" ${structural ? "" : "disabled"}></label>
              </div>
              <div class="child-segment-boundary">
                ${editSubeventDayControl("data-child-end-date","data-child-end-month-year",endDate,"Ende",!structural)}
                <label class="edit-field"><span>Endzeit</span><input data-child-end-time type="time" value="${escapeHtml(end)}" ${structural ? "" : "disabled"}></label>
              </div>
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
            <label class="edit-field"><span>Tagesordner</span><select id="edit-preserve" ${structural ? "" : "disabled"}><option value="0" ${event.preserve_day_folders ? "" : "selected"}>Nicht erhalten</option><option value="1" ${event.preserve_day_folders ? "selected" : ""}>Erhalten</option></select></label>
            <label class="edit-field"><span>Unterordner</span><select id="edit-subfolders" ${structural ? "" : "disabled"}><option value="1" ${context.folder_layout?.structure_enabled ? "selected" : ""}>Erstellen</option><option value="0" ${context.folder_layout?.structure_enabled ? "" : "selected"}>Nicht erstellen</option></select></label>` : `
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
          <label class="edit-field"><span>Unterordner</span><select id="edit-subfolders" ${structural ? "" : "disabled"}><option value="1" ${context.folder_layout?.structure_enabled ? "selected" : ""}>Erstellen</option><option value="0" ${context.folder_layout?.structure_enabled ? "" : "selected"}>Nicht erstellen</option></select></label>
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
          normalContainer.querySelectorAll("[data-child-segment]").forEach(row=>{
            const remove=row.querySelector("[data-remove-child-segment]");
            if(remove)remove.onclick=()=>row.remove();
            const nameInput=row.querySelector("[data-child-name]");
            const summary=row.querySelector("[data-child-summary]");
            if(nameInput&&summary){
              const syncSummary=()=>{ summary.textContent=String(nameInput.value||"").trim() || "Unterereignis"; };
              nameInput.oninput=syncSummary;
              syncSummary();
            }
            for(const prefix of ["start","end"]){
              const control=row.querySelector(`[data-child-${prefix}-date]`);
              if(control)control.onchange=()=>syncEditSubeventDayDisplay(row,prefix);
              syncEditSubeventDayDisplay(row,prefix);
            }
          });
        };
        bind();
        const refreshNormalDayControls=()=>{
          const bounds=editSubeventBounds();
          const days=editSubeventDays();
          if(!bounds.minDate||!bounds.maxDate||!days.length)return;
          normalContainer.querySelectorAll("[data-child-segment]").forEach(row=>{
            for(const prefix of ["start","end"]){
              const control=row.querySelector(`[data-child-${prefix}-date]`);
              if(!control)continue;
              control.min=bounds.minDate;
              control.max=bounds.maxDate;
              let value=String(control.value||"");
              if(!validEditableIsoDate(value)||value<bounds.minDate)value=bounds.minDate;
              else if(value>bounds.maxDate)value=bounds.maxDate;
              control.value=value;
            }
          });
        };
        document.getElementById("edit-start-date")?.addEventListener("change",refreshNormalDayControls);
        document.getElementById("edit-end-date")?.addEventListener("change",refreshNormalDayControls);
        document.getElementById('add-normal-segment').onclick=()=>{
          const defaults=nextEditSubeventDefaults(normalContainer);
          if(!defaults){
            showEventEditError("Im Oberereignis ist hinter dem letzten Unterereignis kein weiterer Zeitraum frei. Ändere zuerst dessen Endzeit.");
            return;
          }
          const row=document.createElement('details');
          row.open=true;
          row.dataset.childSegment='1';
          row.className='card child-segment-card';
          row.innerHTML=`<summary><strong data-child-summary>Unterereignis</strong></summary><div class="child-segment-fields">
            <div class="child-segment-top">
              <label class="edit-field child-segment-name"><span>Name</span><input data-child-name></label>
              <button type="button" class="danger-button child-segment-remove" data-remove-child-segment>Unterereignis entfernen</button>
            </div>
            <div class="child-segment-boundaries">
              <div class="child-segment-boundary">
                ${editSubeventDayControl("data-child-start-date","data-child-start-month-year",defaults.startDate,"Beginn",false)}
                <label class="edit-field"><span>Startzeit</span><input data-child-start-time type="time" value="${escapeHtml(defaults.startTime)}"></label>
              </div>
              <div class="child-segment-boundary">
                ${editSubeventDayControl("data-child-end-date","data-child-end-month-year",defaults.endDate,"Ende",false)}
                <label class="edit-field"><span>Endzeit</span><input data-child-end-time type="time" value="${escapeHtml(defaults.endTime)}"></label>
              </div>
            </div>
          </div>`;
          normalContainer.appendChild(row);
          bind();
          row.querySelector("[data-child-name]")?.focus();
        };
      } else if (structural) {
        const container=document.getElementById("no-event-segments");
        const bindNoEventRows=()=>{
          container.querySelectorAll("[data-remove-segment]").forEach(button=>{button.onclick=()=>button.closest("[data-segment-row]")?.remove();});
          container.querySelectorAll("[data-segment-day]").forEach(input=>{
            input.dataset.lastValid=input.value||"";
            input.onchange=()=>{
              const month=String(input.dataset.lockedMonth||fixedNoEventMonth||"");
              if(month&&input.value){
                const maxDay=new Date(Number(month.slice(0,4)),Number(month.slice(5,7)),0).getDate();
                const min=`${month}-01`;
                const max=`${month}-${String(maxDay).padStart(2,"0")}`;
                if(input.value<min)input.value=min;
                if(input.value>max)input.value=max;
                if(!input.value.startsWith(month+"-"))input.value=input.dataset.lastValid||min;
              }
              input.dataset.lastValid=input.value||"";
              syncNoEventDateMirror(input.closest("[data-segment-row]"));
            };
            syncNoEventDateMirror(input.closest("[data-segment-row]"));
          });
        };
        bindNoEventRows();
        document.getElementById("add-no-event-segment")?.addEventListener("click",()=>{
          const row=document.createElement("details");row.className="no-event-segment card collapse-card";row.dataset.segmentRow="1";row.open=true;row.style.cssText="display:block;padding:8px 10px;margin:6px 0";
          row.innerHTML=`<summary style="cursor:pointer;display:flex;align-items:center;gap:6px"><strong>Neues Tagessegment</strong><span class="muted">· 00:00–23:59</span></summary><div class="no-event-segment-fields"><div class="no-event-mobile-range-title">Von–Bis</div>${noEventDayControl(fixedNoEventMonth,"",true)}<label class="edit-field no-event-start-field"><span class="no-event-desktop-caption">Von</span><input type="time" data-segment-start value="00:00" aria-label="Von"></label>${noEventDateMirror(fixedNoEventMonth ? fixedNoEventMonth+"-01" : "")}<label class="edit-field no-event-end-field"><span class="no-event-desktop-caption">Bis</span><input type="time" data-segment-end value="23:59" aria-label="Bis"></label><button type="button" data-remove-segment class="danger-button no-event-segment-remove">Entfernen</button></div>`;
          container.appendChild(row);bindNoEventRows();row.querySelector("[data-segment-day]")?.focus();
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

    async function confirmEditEmptySubevents(error) {
      if (error?.data?.confirmation_required !== "empty_subevents") return false;
      const names=(error.data.empty_subevents||[]).map(item=>String(item.name||"Unterereignis"));
      return window.BibliothekarI18n.confirmAsync(
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
        if (!(await confirmEditEmptySubevents(error))) throw error;
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
        event_name: noEvent ? String(context.event.name || "Ohne Ereignis") : document.getElementById("edit-name").value,
        notes: document.getElementById("edit-notes").value,
      };
      if (structural) {
        payload.create_subfolders = document.getElementById("edit-subfolders").value === "1";
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
        eventEditDialog.close();
        changeRequestTitle.textContent = "Archivänderung";
        changeRequestSubtitle.textContent = String(context.event.name || "Ereignis");
        changeRequestBody.innerHTML =
          `<section class="change-pane"><div class="card"><strong>Archivänderung wird vorbereitet …</strong><p class="muted" style="margin-top:6px">IST- und SOLL-Zustand werden berechnet. Die Kamerabibliothek bleibt dabei unverändert.</p><div class="change-progress active"><div class="muted">Bitte einen Moment warten.</div><div class="change-progress-track"><div class="change-progress-bar" style="width:55%"></div></div></div></div></section>`;
        if (!changeRequestDialog.open) changeRequestDialog.showModal();
        setStatus("Manueller Änderungsauftrag wird berechnet …");
        try {
          const result = await requestJson(`/api/change-requests/${encodeURIComponent(context.event.id)}/propose?job_id=${encodeURIComponent(context._job_id)}`, {
            method: "POST", headers: {"Content-Type":"application/json"}, body: JSON.stringify(payload),
          });
          setChangeTaskInUrl(result.change_request_id, context._job_id);
          await showChangeRequestDetail(result.change_request_id);
          setStatus("Änderungsauftrag erstellt. Die Kamerabibliothek wurde nicht verändert.", false, true);
          refreshGlobalTasks();
        } catch (error) {
          changeRequestBody.innerHTML =
            `<div class="card"><strong class="danger-text">Archivänderung konnte nicht vorbereitet werden.</strong><p class="muted" style="margin-top:7px">${escapeHtml(error.message)}</p></div>`;
          setStatus(error.message, true);
        }
        return;
      }
      const preparingApplied = context.event.status === "applied";
      setEventOperationBusy("Ereignisänderungen werden vorbereitet …");
      if (preparingApplied) {
        // Sichtbares Feedback sofort nach dem Klick, VOR der PUT-Anfrage.
        eventEditDialog.close();
        showSortPreparation(context.event.name, "Änderungen anwenden");
      }
      let result;
      try {
        result = await updateEventWithEmptySubeventConfirmation(context, payload);
      } catch (error) {
        if (preparingApplied) {
          releaseSortPreparation();
          sortPlanDialog.close();
          if (!eventEditDialog.open) eventEditDialog.showModal();
        }
        statusElement.classList.remove("bk-loading-status");
        throw error;
      }
      eventEditDialog.close();
      if (preparingApplied && result.archive_manual?.change_request_ids?.length) {
        releaseSortPreparation();
        sortPlanDialog.close();
      }

      if (result.archive_manual?.change_request_ids?.length) {
        statusElement.classList.remove("bk-loading-status");
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
        statusElement.classList.remove("bk-loading-status");
        return;
      }

      if (preparingApplied) {
        releaseSortPreparation();
        sortPlanDialog.close();
      }
      statusElement.classList.remove("bk-loading-status");
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
      releaseSortPreparation();
      sortPlanCloseButton.textContent = mandatoryMutationContext ? "Änderungen verwerfen" : "Schließen";
      sortPlanCloseButton.classList.toggle("danger-button", Boolean(mandatoryMutationContext));
      sortPlanTitle.textContent = mandatoryMutationContext
        ? `Änderungen anwenden · ${event.name}`
        : `Nachsortierung · ${event.name}`;
      sortPlanSubtitle.textContent = "Alte und neue Pfade werden rein lesend geprüft …";
      sortPlanBody.innerHTML = '<div class="event-operation-loading" role="status"><span class="event-operation-spinner" aria-hidden="true"></span><span>Dateien, Ziele und Konflikte werden geprüft …</span></div>';
      if (!sortPlanDialog.open) sortPlanDialog.showModal();
      try {
        const plan = await requestJson(`/api/jobs/${encodeURIComponent(jobId)}/events/${encodeURIComponent(eventId)}/reconcile-plan`);
        plan._job_id = jobId;
        plan._reapply = true;
        plan._reconcile = true;
        plan._mandatory = Boolean(mandatoryMutationContext);
        renderSortPlan(plan);
      } catch (error) {
        sortPlanSubtitle.textContent = "Änderungsplan konnte nicht berechnet werden.";
        sortPlanBody.innerHTML = `<div class="card"><strong class="danger-text">Nachsortierung blockiert</strong><p class="muted" style="margin-top:7px">${escapeHtml(error.message)}</p></div>`;
        setStatus(error.message, true);
        throw error;
      }
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
      const confirmed = await window.BibliothekarI18n.confirmAsync(`Ereignis „${event.name}“ löschen?\n\n${statusText}`);

      if (!confirmed) {
        return;
      }

      // Sofortige Rückmeldung statt eines wartenden Ladekreises hinter dem Dialog.
      const preparingApplied = event.status === "applied";
      const preparingArchived = event.status === "archived";
      setEventOperationBusy("Löschauftrag wird vorbereitet …");
      if (preparingApplied) showSortPreparation(event.name, "Änderungen anwenden");
      if (preparingArchived) {
        changeRequestTitle.textContent = "Ereignis löschen · " + event.name;
        changeRequestSubtitle.textContent = "Der manuelle Löschauftrag wird vorbereitet …";
        changeRequestBody.innerHTML = '<div class="event-operation-loading" role="status"><span class="event-operation-spinner" aria-hidden="true"></span><span>Der Archivbestand wird rein lesend geprüft …</span></div>';
        if (!changeRequestDialog.open) changeRequestDialog.showModal();
      }
      let result;
      try {
        result = await requestJson(
        `/api/jobs/${
          encodeURIComponent(jobId)
        }/events/${
          encodeURIComponent(eventId)
        }`,
        {
          method: "DELETE"
        }
      );
      } catch (error) {
        if (preparingApplied) {
          releaseSortPreparation();
          sortPlanDialog.close();
        }
        if (preparingArchived) changeRequestDialog.close();
        statusElement.classList.remove("bk-loading-status");
        throw error;
      }
      statusElement.classList.remove("bk-loading-status");

      if (result.change_request_id) {
        if (preparingApplied) {
          releaseSortPreparation();
          sortPlanDialog.close();
        }
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
      if (preparingApplied) {
        releaseSortPreparation();
        sortPlanDialog.close();
      }
      if (preparingArchived) changeRequestDialog.close();
      await loadEvents({reset:true});
      refreshGlobalTasks();
      setStatus(`Ereignis gelöscht: ${result.event_name} · ${Number(result.released_family_count||0)} Familien wieder frei.`, false, true);
    }




    eventEditClose.addEventListener("click", () => eventEditDialog.close());
    changeRequestClose.addEventListener("click", async () => {
      if (!mandatoryArchiveChangeContext) {
        changeRequestDialog.close();
        return;
      }
      if (!(await window.BibliothekarI18n.confirmAsync("Diese Archivänderung vollständig verwerfen?\n\nWenn du im Archiv bereits manuelle Änderungen vorgenommen hast, wird anschließend ein eigener Rückänderungsauftrag geöffnet. Er führt dich Schritt für Schritt durch die Wiederherstellung und prüft den ursprünglichen Zustand, bevor die Änderung endgültig verworfen wird."))) return;
      setEventOperationBusy("Archivänderung wird verworfen …");
      changeRequestAction(mandatoryArchiveChangeContext.crId, "cancel")
        .catch(error => {
          const inlineError=document.getElementById("change-request-inline-error");
          if (inlineError) {
            inlineError.textContent=error.message;
            inlineError.hidden=false;
          }
        })
        .finally(() => statusElement.classList.remove("bk-loading-status"));
    });
    changeRequestDialog.addEventListener("cancel", event => {
      if (mandatoryArchiveChangeContext) event.preventDefault();
    });
    eventEditForm.addEventListener("submit", async event => {
      event.preventDefault();
      const old=document.getElementById("event-edit-inline-error");if(old)old.hidden=true;
      const submit=eventEditForm.querySelector('button[type="submit"]');
      if(submit){
        submit.disabled=true;
        submit.classList.add("bk-busy");
        submit.setAttribute("aria-busy","true");
      }
      try {
        await saveEventEditor();
      } catch (error) {
        showEventEditError(error.message);
      } finally {
        if(submit){
          submit.disabled=false;
          submit.classList.remove("bk-busy");
          submit.removeAttribute("aria-busy");
        }
      }
    });

    async function discardMandatoryMutation() {
      const ctx=mandatoryMutationContext;
      if (!ctx) { sortPlanDialog.close(); return; }
      if (!(await window.BibliothekarI18n.confirmAsync("Diese Applied-Änderung vollständig verwerfen und den Zustand vor der Bearbeitung wiederherstellen?"))) return;
      // Das Modal schließen und den Fortschritt direkt auf der Ereignisseite zeigen.
      sortPlanCloseButton.disabled=true;
      sortPlanDialog.close();
      setEventOperationBusy("Änderung wird verworfen …");
      try {
        const accepted=await requestJson(
          `/api/jobs/${encodeURIComponent(ctx.jobId)}/event-mutations/${encodeURIComponent(ctx.mutationId)}/cancel`,
          {method:"POST"}
        );
        if (!["queued","running","completed"].includes(String(accepted.status))) {
          throw new Error("Der Verwerfauftrag wurde nicht angenommen.");
        }
        // Nach persistenter Annahme darf der Browser ohne Warnung wechseln.
        mandatoryMutationContext=null;
        window.dispatchEvent(new Event("bk-cancellation-queued"));
        sortPlanCloseButton.classList.remove("danger-button");
        sortPlanCloseButton.textContent="Schließen";
        sortPlanCloseButton.hidden=false;
        refreshGlobalTasks();
        setStatus("Verwerfauftrag angenommen. Er läuft unabhängig von dieser Seite im Hintergrund.",false,true);
        loadEvents({reset:true}).catch(error=>setStatus(error.message,true));
      } catch (error) {
        // Bei einem fehlgeschlagenen Verwerfen muss der Nutzer erneut versuchen können.
        sortPlanSubtitle.textContent="Verwerfen fehlgeschlagen. Bitte erneut versuchen.";
        sortPlanBody.insertAdjacentHTML("afterbegin",
          `<div class="card" role="alert"><strong class="danger-text">Verwerfen fehlgeschlagen</strong><p class="muted">${escapeHtml(error.message)}</p></div>`);
        if (!sortPlanDialog.open) sortPlanDialog.showModal();
        throw error;
      } finally {
        statusElement.classList.remove("bk-loading-status");
        sortPlanCloseButton.disabled=false;
      }
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
      async event => {
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
          const targetEvent = currentEvents.find(item => item.id === planButton.dataset.sortPlanEvent);
          loader(
            planButton.dataset.sortPlanEvent,
            planButton.dataset.jobId,
            loader === loadReapplyPlan
              ? {
                  mandatory: Boolean(targetEvent?.mutation_id && targetEvent.id === targetEvent.mutation_anchor_event_id),
                  mutationId: targetEvent?.mutation_id || ""
                }
              : undefined
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
          if (!(await window.BibliothekarI18n.confirmAsync("Diese noch nicht abgeschlossene Änderung vollständig verwerfen und den gespeicherten Ursprungszustand wiederherstellen?"))) return;
          cancelMutationButton.disabled=true;
          setEventOperationBusy("Änderung wird verworfen …");
          requestJson(`/api/jobs/${encodeURIComponent(cancelMutationButton.dataset.jobId||"")}/event-mutations/${encodeURIComponent(cancelMutationButton.dataset.cancelMutation)}/cancel`, {method:"POST"})
            .then(accepted => {
              if (!["queued","running","completed"].includes(String(accepted.status))) {
                throw new Error("Der Verwerfauftrag wurde nicht angenommen.");
              }
              window.dispatchEvent(new Event("bk-cancellation-queued"));
              setStatus("Verwerfauftrag angenommen. Er läuft unabhängig von dieser Seite im Hintergrund.", false, true);
              loadEvents({reset:true}).catch(error=>setStatus(error.message,true));
              refreshGlobalTasks();
            })
            .catch(error => setStatus(error.message, true))
            .finally(() => {
              statusElement.classList.remove("bk-loading-status");
              if (cancelMutationButton.isConnected) cancelMutationButton.disabled=false;
            });
          return;
        }

        const editButton = event.target.closest("[data-edit-event]");
        if (editButton && !editButton.disabled) {
          // Auch archivierte Ereignisse öffnen denselben vollständigen Editor.
          // Beim Speichern wird dort ausschließlich ein manueller Change Request
          // erzeugt; die Kamerabibliothek bleibt read-only.
          (async () => {
            const pendingChange = await findOpenArchiveChangeRequest(editButton.dataset.editEvent);
            if (pendingChange) {
              if (!changeRequestDialog.open) changeRequestDialog.showModal();
              await showChangeRequestDetail(pendingChange.id, {resume:true});
              return;
            }
            await openEventEditor(editButton.dataset.editEvent, editButton.dataset.jobId);
          })().catch(error => {
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

    async function showArchiveReversalDetail(crId, options={}) {
      const assistant = options.assistant || await requestJson(
        `/api/change-requests/${encodeURIComponent(crId)}/reversal`
        + (options.refreshLive ? "?refresh=true" : "")
      );
      if (!assistant.active) {
        return showChangeRequestDetail(crId, {resume:true, skipReversalCheck:true});
      }

      mandatoryArchiveChangeContext = {
        ...(mandatoryArchiveChangeContext || {}),
        crId:String(crId),
        mode:"reversal"
      };
      changeRequestTitle.textContent = "Rückänderungsauftrag";
      changeRequestSubtitle.textContent =
        `Ursprünglichen Archivzustand wiederherstellen · ${String(crId)}`;
      changeRequestClose.textContent = "Rückänderung läuft";
      changeRequestClose.classList.remove("danger-button");
      changeRequestClose.disabled = true;

      const reversalPathLabels=assistant.path_labels||{};
      const reversalArchiveRoot=String(reversalPathLabels.archive_root||"Kamerabibliothek");
      const reversalWorkRoot=String(reversalPathLabels.work_root||"Arbeitsbereich");
      const phase = String(assistant.phase || "prepare");
      const logicalOrder = ["prepare","finder","verify"];
      const currentLogical = logicalOrder.indexOf(phase);
      const visualSteps = [
        {phase:"verify", number:3, label:"Prüfen & Verwerfen"},
        {phase:"finder", number:2, label:"Finder-Rückarbeit"},
        {phase:"prepare", number:1, label:"Vorbereiten"}
      ];

      let html = '<div class="change-stepper reversal-stepper">';
      for (const step of visualSteps) {
        const logical = logicalOrder.indexOf(step.phase);
        const state = logical < currentLogical
          ? " done"
          : logical === currentLogical
            ? " active"
            : "";
        html += `<button type="button" class="change-step${state}" disabled><span class="change-step-number">${step.number}</span><span><strong>${step.label}</strong></span></button>`;
      }
      html += "</div>";

      if (phase === "prepare") {
        html += `<section class="change-pane"><div class="change-pane-heading"><div><h3>Rückänderung vorbereiten</h3><p class="muted">Du hast bestätigt, dass die Archivänderung verworfen werden soll. Der ursprüngliche Zustand wird jetzt als eigener Rückweg vorbereitet.</p></div></div>`;
        html += `<div class="card"><strong>Dieser Wiederherstellungsbereich wird erst mit „Rückänderung vorbereiten“ angelegt:</strong><code style="display:block;margin-top:8px;white-space:pre-wrap;word-break:break-word">${escapeHtml(assistant.original_stock_path || (reversalWorkRoot+"/Später zuordnen"))}</code><p class="muted" style="margin-top:9px">Vor diesem Schritt muss der angezeigte Ordner noch nicht existieren. Beim Vorbereiten prüft die App den tatsächlichen Archivzustand sowie Größe und SHA-256. Nur Originale, die für den Rückweg wirklich auf SSD benötigt werden, werden dort sicher materialisiert.</p></div>`;
        html += '<div class="change-footer"><button type="button" class="plan-button bk-positive-action" data-reversal-prepare>Rückänderung vorbereiten</button></div></section>';
      } else if (phase === "finder") {
        html += `<section class="change-pane"><div class="change-pane-heading"><div><div style="display:flex;align-items:center;gap:8px"><h3 style="margin:0">Finder-Rückarbeit</h3><button class="bk-help" type="button" aria-label="Hinweis zur Finder-Rückarbeit" data-help="Die App prüft den realen Archivzustand read-only. Noch vorhandene Dateien werden an ihren ursprünglichen Ort zurückverschoben; fehlende Originale kommen aus dem vorbereiteten SSD-Rückbestand.">?</button></div>${assistant.live_refreshed ? '<p class="success-text" style="margin-top:6px">✓ Aktueller Archivbestand wurde read-only geprüft.</p>' : ''}</div><button type="button" class="plan-button change-refresh-button" data-reversal-refresh>↻ Aktualisieren</button></div>`;
        html += `<div class="card"><strong>Ursprüngliches Ziel</strong><code style="display:block;margin-top:7px">${escapeHtml(reversalArchiveRoot)}/${escapeHtml(assistant.original_root || "")}</code><div class="muted" style="margin-top:7px">SSD-Rückbestand</div><code style="display:block;white-space:pre-wrap;word-break:break-word">${escapeHtml(assistant.original_stock_path || "")}</code></div>`;
        let number=1;
        for (const operation of assistant.operations || []) {
          html += `<details class="card change-operation" ${number===1?"open":""}><summary><span>${number}. ${escapeHtml(operation.title || "Rückarbeit")}</span><span class="badge warning">Ausstehend</span></summary><div class="change-operation-body"><div>${escapeHtml(operation.detail || "")}</div>`;
          if (operation.source) html += `<div class="muted">VON</div><code style="display:block;white-space:pre-wrap;word-break:break-word">${escapeHtml(operation.source)}</code>`;
          if (operation.target) html += `<div class="muted">NACH</div><code style="display:block;white-space:pre-wrap;word-break:break-word">${escapeHtml(operation.target)}</code>`;
          if ((operation.paths || []).length) html += `<div class="muted">ZU ENTFERNEN</div>${operation.paths.map(path=>`<code style="display:block;white-space:pre-wrap;word-break:break-word">${escapeHtml(path)}</code>`).join("")}`;
          if ((operation.items || []).length) html += `<details><summary>${operation.items.length} Element${operation.items.length===1?"":"e"} anzeigen</summary><div style="margin-top:7px">${operation.items.map(name=>`<code style="display:block">${escapeHtml(name)}</code>`).join("")}</div></details>`;
          html += "</div></details>";
          number++;
        }
        if (!(assistant.operations || []).length) {
          html += '<div class="card success-text">✓ Der ursprüngliche Finder-Zustand ist bereits wiederhergestellt.</div>';
        }
        html += '<div class="change-footer"><button type="button" class="plan-button bk-positive-action" data-reversal-finder-check>Rückarbeit prüfen · weiter</button></div></section>';
      } else {
        html += '<section class="change-pane"><div class="change-pane-heading"><div><h3>Prüfen & Verwerfen</h3><p class="muted">Der ursprüngliche Archivzustand wird vollständig read-only nach Ordnern, Pfaden, Größen und SHA-256 geprüft.</p></div></div>';
        html += '<div id="reversal-verify-panel" class="card"><div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap"><button type="button" class="plan-button" data-reversal-verify>Rückänderung prüfen</button><span class="muted" data-reversal-summary>Noch nicht geprüft.</span></div><div data-reversal-errors style="display:none;margin-top:10px"></div></div>';
        html += '<div class="change-footer"><button type="button" class="plan-button bk-positive-action" data-reversal-finish disabled>Ursprungszustand bestätigen & Änderung verwerfen</button></div></section>';
      }

      html += '<div class="card" style="margin-top:10px;border-color:var(--bk-danger,#c75050)"><details><summary><strong>Notausstieg bei unmöglicher Rückänderung</strong></summary><p class="muted" style="margin-top:8px">Nur verwenden, wenn die Wiederherstellung unmöglich ist. Der Auftrag wird beendet, aber das Ereignis bleibt gesperrt, bis der Originalbestand gesondert geprüft wurde. Es werden keine Archivdateien verändert oder als geprüft markiert.</p><button type="button" class="plan-button danger-button" data-reversal-force>Abbrechen erzwingen · manuelle Klärung</button></details></div>';
      changeRequestBody.innerHTML = html;
      changeRequestBody.querySelector("[data-reversal-force]")?.addEventListener("click", async event => {
        if (!(await window.BibliothekarI18n.confirmAsync("NOTFALLABBRUCH: Der ursprüngliche Archivbestand ist danach NICHT als wiederhergestellt bestätigt. Das Ereignis bleibt bis zur erneuten Prüfung gesperrt. Fortfahren?"))) return;
        const confirmation = window.prompt("Gib zur Bestätigung exakt NOTFALLABBRUCH ein:");
        if (confirmation !== "NOTFALLABBRUCH") return;
        const reason = window.prompt("Warum ist die Wiederherstellung nicht möglich?") || "";
        if (reason.trim().length < 8) return;
        const button = event.currentTarget;
        button.disabled = true;
        try {
          const result = await requestJson(
            `/api/change-requests/${encodeURIComponent(crId)}/reversal/force-stop`,
            {method:"POST",headers:{"Content-Type":"application/json"},
             body:JSON.stringify({confirmation,reason})}
          );
          mandatoryArchiveChangeContext = null;
          clearChangeTaskFromUrl(crId);
          changeRequestClose.disabled = false;
          changeRequestClose.textContent = "Schließen";
          changeRequestDialog.close();
          await loadEvents({reset:true});
          refreshGlobalTasks();
          setStatus(result.message,true);
        } catch (error) {
          button.disabled = false;
          showReversalError(error.message);
        }
      });
      const showReversalError = message => {
        let box=changeRequestBody.querySelector("#reversal-inline-error");
        if(!box){
          box=document.createElement("div");
          box.id="reversal-inline-error";
          box.className="card danger-text";
          box.style.marginBottom="12px";
          changeRequestBody.prepend(box);
        }
        box.textContent=String(message||"Unbekannter Fehler");
        box.hidden=false;
      };

      changeRequestBody.querySelector("[data-reversal-prepare]")?.addEventListener("click", async event => {
        const button=event.currentTarget;
        button.disabled=true;
        try {
          const next=await requestJson(
            `/api/change-requests/${encodeURIComponent(crId)}/reversal/prepare`,
            {method:"POST",headers:{"Content-Type":"application/json"},body:"{}"}
          );
          await showArchiveReversalDetail(crId,{assistant:next});
        } catch(error) {
          button.disabled=false;
          showReversalError(error.message);
        }
      });

      changeRequestBody.querySelector("[data-reversal-refresh]")?.addEventListener("click", async event => {
        const button=event.currentTarget;
        button.disabled=true;
        button.classList.add("loading");
        button.textContent="Aktualisiere …";
        try {
          await showArchiveReversalDetail(crId,{refreshLive:true});
        } catch(error) {
          button.disabled=false;
          showReversalError(error.message);
        }
      });

      changeRequestBody.querySelector("[data-reversal-finder-check]")?.addEventListener("click", async () => {
        await showArchiveReversalDetail(crId,{refreshLive:true});
      });

      const verifyButton=changeRequestBody.querySelector("[data-reversal-verify]");
      const finishButton=changeRequestBody.querySelector("[data-reversal-finish]");
      verifyButton?.addEventListener("click", async () => {
        verifyButton.disabled=true;
        const summary=changeRequestBody.querySelector("[data-reversal-summary]");
        const errors=changeRequestBody.querySelector("[data-reversal-errors]");
        try {
          const result=await requestJson(
            `/api/change-requests/${encodeURIComponent(crId)}/reversal/verify`,
            {method:"POST",headers:{"Content-Type":"application/json"},body:"{}"}
          );
          if (result.complete) {
            verifyButton.classList.add("success");
            verifyButton.textContent="✓ Rückänderung geprüft";
            if(summary){summary.className="success-text";summary.textContent="Der ursprüngliche Archivzustand ist vollständig wiederhergestellt.";}
            if(errors){errors.style.display="none";errors.innerHTML="";}
            if(finishButton) finishButton.disabled=false;
          } else {
            verifyButton.disabled=false;
            if(summary){summary.className="danger-text";summary.textContent=`${Number(result.problem_count||0)} Punkt(e) sind noch offen.`;}
            if(errors){
              errors.style.display="block";
              errors.innerHTML=(result.problems||[]).map(problem=>`<div class="card" style="margin-top:7px"><strong>${escapeHtml(problem.message||"Noch offen")}</strong><code style="display:block;margin-top:5px;white-space:pre-wrap;word-break:break-word">${escapeHtml(problem.path||"")}</code></div>`).join("");
            }
          }
        } catch(error) {
          verifyButton.disabled=false;
          showReversalError(error.message);
        }
      });

      finishButton?.addEventListener("click", async () => {
        finishButton.disabled=true;
        try {
          await requestJson(
            `/api/change-requests/${encodeURIComponent(crId)}/reversal/finish`,
            {method:"POST",headers:{"Content-Type":"application/json"},body:"{}"}
          );
          mandatoryArchiveChangeContext=null;
          clearChangeTaskFromUrl(crId);
          changeRequestClose.disabled=false;
          changeRequestClose.textContent="Schließen";
          changeRequestClose.classList.remove("danger-button");
          if(changeRequestDialog.open) changeRequestDialog.close();
          await loadEvents({reset:true});
          refreshGlobalTasks();
          setStatus("Rückänderung abgeschlossen. Die Archivänderung wurde verworfen.",false,true);
        } catch(error) {
          finishButton.disabled=false;
          showReversalError(error.message);
        }
      });
    }


    async function showChangeRequestDetail(crId, options={}) {
      try {
        changeRequestBody.textContent = "Lade Änderungsauftrag …";
        changeRequestTitle.textContent = "Archivänderung";
        changeRequestSubtitle.textContent = "";
        const inlineError=document.getElementById("change-request-inline-error");
        if (inlineError) {
          inlineError.hidden=true;
          inlineError.textContent="";
        }

        const crRes = await fetch(`/api/change-requests/${encodeURIComponent(crId)}`);
        if (!crRes.ok) throw new Error(`HTTP ${crRes.status}: ${crRes.statusText}`);
        const cr = await crRes.json();
        const active = syncArchiveChangeContext(cr);
        if (active && !options.skipReversalCheck) {
          const reversalRes = await fetch(
            `/api/change-requests/${encodeURIComponent(crId)}/reversal`
          );
          if (reversalRes.ok) {
            const reversal = await reversalRes.json();
            if (reversal.active) {
              await showArchiveReversalDetail(crId,{assistant:reversal});
              return;
            }
          }
        }
        if (options.resume && !active) {
          if (changeRequestDialog.open) changeRequestDialog.close();
          setStatus("Der frühere Archivänderungsauftrag ist bereits abgeschlossen.", false, true);
          return;
        }

        const [assistantRes, filesRes] = await Promise.all([
          fetch(
            `/api/change-requests/${encodeURIComponent(crId)}/assistant`
            + (options.refreshLive ? "?refresh=true" : "")
          ),
          fetch(`/api/change-requests/${encodeURIComponent(crId)}/files`)
        ]);
        if (!assistantRes.ok) {
          const data = await assistantRes.json().catch(() => ({}));
          throw new Error(data.detail || `HTTP ${assistantRes.status}`);
        }
        const assistant = await assistantRes.json();
        const reviewRows = filesRes.ok ? await filesRes.json() : [];
        const releaseStock = assistant.release_stock || {};
        const pathLabels = assistant.path_labels || {};
        const archiveRootLabel = String(pathLabels.archive_root || "Kamerabibliothek");
        const workRootLabel = String(pathLabels.work_root || "Arbeitsbereich");
        const backupRootLabel = String(pathLabels.backup_root || "SD-Kartensicherungen");
        const finderNeeded =
          (assistant.operations || []).length > 0
          || Boolean(releaseStock.required);

        const sequence = [];
        if (assistant.preparation_required) sequence.push("prepare");
        if (finderNeeded) sequence.push("finder");
        sequence.push("verify");

        const urlStep = new URL(window.location.href).searchParams.get("change_step");
        let phase = options.phase || urlStep || assistant.phase || sequence[0];
        if (!sequence.includes(phase)) phase = sequence[0];
        if (
          assistant.preparation_required
          && String(cr.status) === "aenderbar_vorschlagen"
        ) phase = "prepare";
        if (!assistant.preparation_required && phase === "prepare") {
          phase = finderNeeded ? "finder" : "verify";
        }
        setChangeStepInUrl(phase);

        changeRequestSubtitle.textContent =
          `${assistant.event_name || cr.event_name || "Ereignis"} · ${cr.id}`;

        const labels = {
          prepare: "Vorbereiten",
          finder: "Finder-Arbeit",
          verify: "Prüfen & Abschließen"
        };
        const currentIndex = sequence.indexOf(phase);
        let html = `<div class="change-stepper">`;
        sequence.forEach((step, index) => {
          const state = index < currentIndex ? " done" : index === currentIndex ? " active" : "";
          html += `<button type="button" class="change-step${state}" data-change-step="${step}" ${index > currentIndex ? "disabled" : ""}><span class="change-step-number">${index + 1}</span><span><strong>${labels[step]}</strong></span></button>`;
        });
        html += `</div>`;

        const targetTree = (assistant.target_structure?.lines || []).join("\n");
        const targetStructureDeleted = Boolean(assistant.target_structure?.deleted);

        const renderTechnicalDetails = () => {
          const rows = (Array.isArray(reviewRows) ? reviewRows : []).filter(row => {
            const action = String(row.action || "");
            return action && action !== "keep";
          });
          if (!rows.length) return "";
          let detail = `<details class="card change-disclosure"><summary><strong>Technische Details</strong> <span class="muted">· ${rows.length} Dateioperationen</span></summary><div style="margin-top:10px;display:grid;gap:8px">`;
          for (const row of rows) {
            const sourceRelative = row.source_root_kind === "shared_workspace"
              ? (row.workspace_staging_path || row.workspace_original_path || row.old_path || "—")
              : (row.old_path || "—");
            const source = sourceRelative === "—"
              ? sourceRelative
              : `${row.source_root_kind === "shared_workspace" ? workRootLabel : archiveRootLabel}/${sourceRelative}`;
            const releaseTarget = String(row.workspace_release_path || "");
            const targetText = releaseTarget
              ? `${backupRootLabel}/${releaseTarget}`
              : (row.new_path ? `${archiveRootLabel}/${row.new_path}` : "—");
            const actionText = releaseTarget
              ? "Freigewordene Archivdatei"
              : String(row.action || "Änderung");
            detail += `<div class="card" style="padding:9px 10px"><strong>${escapeHtml(actionText)}</strong><div class="muted">IST</div><code style="display:block;white-space:pre-wrap;word-break:break-word">${escapeHtml(source)}</code><div class="muted" style="margin-top:5px">SOLL</div><code style="display:block;white-space:pre-wrap;word-break:break-word">${escapeHtml(targetText)}</code></div>`;
          }
          detail += `</div></details>`;
          return detail;
        };

        if (phase === "prepare") {
          const prep = assistant.preparation || {};
          const missing = prep.missing_directories || [];
          html += `<section class="change-pane"><div class="change-pane-heading"><div><h3>Hilfsbereiche vorbereiten</h3><p class="muted">Die App bereitet nur SSD-Hilfsstrukturen vor. Die Kamerabibliothek und der gültige Datenbankzustand bleiben unverändert.</p></div></div>`;
          html += `<div class="card"><strong>${Number(prep.incoming_file_count || 0)} neue Dateien</strong> werden unter <em>Später zuordnen</em> vorbereitet · <strong>${missing.length} fehlende Ordner</strong> werden ergänzt. Hardlinks werden bevorzugt; falls Quelle und Ziel auf unterschiedlichen Dateisystemen liegen, fragt Bibliothekar ausdrücklich nach <strong>Kopieren</strong> oder <strong>Verschieben</strong>.`;
          if (Number(prep.release_file_count || 0) > 0) {
            html += `<div style="margin-top:7px"><strong>${Number(prep.release_file_count)} freigewordene Archivdateien</strong>: Die benötigten Zielordner unter <em>Freigewordene Archivdateien</em> werden angelegt. Die Dateien selbst kopiert Bibliothekar erst im nächsten Schritt nach deiner ausdrücklichen Freigabe.</div>`;
          }
          if (prep.helper_root) html += `<div class="muted" style="margin-top:7px">Hilfsbereich</div><code style="display:block;white-space:pre-wrap;word-break:break-word">${escapeHtml(prep.helper_root)}</code>`;
          if (missing.length) {
            html += `<details style="margin-top:10px"><summary>Fehlende Struktur anzeigen</summary><div style="margin-top:7px">${missing.map(path => `<code style="display:block">${escapeHtml(path)}</code>`).join("")}</div></details>`;
          }
          html += `</div>`;
          html += `<details class="card"><summary><strong>Was passiert beim Vorbereiten?</strong></summary><p class="muted" style="margin-top:9px">Die App erzeugt ausschließlich benötigte SSD-Ordner und versucht für eingehende freie Dateien zuerst Hardlinks unter „Später zuordnen“. Sind Hardlinks zwischen den Speicherorten nicht möglich, wird angehalten und du wählst ausdrücklich Kopieren oder Verschieben. Freigewordene Archivdateien aus dem Archiv werden hier noch nicht kopiert; das geschieht erst nach einem eigenen Klick. Die Kamerabibliothek bleibt unverändert.</p></details>`;
          html += `<div id="change-prep-progress" class="change-progress"><div class="muted" data-progress-label>Hilfsbereich wird vorbereitet …</div><div class="change-progress-track"><div class="change-progress-bar"></div></div></div>`;
          if (String(cr.status) === "aenderbar_bestaetigt") {
            html += `<div class="success-text">✓ Hilfsbereich ist bereits vorbereitet.</div><div class="change-footer"><button type="button" class="plan-button bk-positive-action" data-cr-prepared-next>Weiter</button></div></section>`;
          } else {
            html += `<div class="change-footer"><button type="button" class="plan-button bk-positive-action" data-cr-prepare>Hilfsbereich vorbereiten</button></div></section>`;
          }
        }

        if (phase === "finder") {
          const releaseRequired = Boolean(releaseStock.required);
          const releaseStage = String(releaseStock.stage || "complete");
          const releaseRows = releaseStock.rows || [];
          const releaseSegments = releaseStock.segments || [];
          const liveRefreshAvailable = releaseStage === "complete";
          html += `<section class="change-pane"><div class="change-pane-heading"><div><div style="display:flex;align-items:center;gap:8px"><h3 style="margin:0">Finder-Arbeit</h3><button class="bk-help" type="button" aria-label="Hinweis zur Finder-Arbeit" data-help="Freigewordene Archivdateien werden zuerst sicher auf die SSD zurückgeholt. Erst danach folgt die eigentliche Umstrukturierung im Archiv. „Aktualisieren“ prüft den tatsächlichen Archivbestand und passt VON-Pfade sowie Erledigt-Status an.">?</button></div>${assistant.live_refreshed ? '<p class="success-text" style="margin-top:6px">✓ Aktueller Archivbestand wurde read-only nach Pfad, Größe und SHA-256 geprüft.</p>' : ''}</div>${liveRefreshAvailable ? '<button type="button" class="plan-button change-refresh-button" data-cr-refresh-live>↻ Aktualisieren</button>' : ''}</div>`;

          if (releaseRequired && (releaseStage === "copy_to_ssd" || releaseStage === "verify_copy")) {
            const copiesReady = releaseStage === "verify_copy";
            html += `<div class="card"><strong>1. Freigewordene Archivdateien auf SSD sichern</strong><p class="muted" style="margin-top:5px">${copiesReady ? "Bibliothekar hat die geplanten Archivdateien auf die SSD kopiert. Prüfe jetzt die Kopien nochmals gegen Größe und SHA-256, bevor du im Archiv etwas entfernst." : "Bibliothekar kann die unten exakt aufgeführten Archivdateien nach deiner Freigabe read-only lesen, auf die SSD kopieren und die Kopien sofort nach Größe und SHA-256 bestätigen. Ziel ist <em>${escapeHtml(backupRootLabel)}/Freigewordene Archivdateien</em>. Noch nichts im Archiv löschen."}</p>`;
            if (releaseSegments.length) {
              html += `<div style="display:grid;gap:8px;margin-top:10px">`;
              for (const segment of releaseSegments) {
                const label = `${String(segment.day_key || "")} · ${String(segment.start_time || "")}–${String(segment.end_time || "")}`;
                const families = Array.isArray(segment.families) ? segment.families : [];
                const targetDirectory = String(segment.workspace_release_directory || "");
                html += `<details class="card change-operation" style="padding:0"><summary style="display:flex;justify-content:space-between;gap:12px;align-items:center"><strong>${escapeHtml(label)}</strong><span class="muted">${Number(segment.family_count || families.length || 0)} Familien · ${Number(segment.release_file_count ?? segment.file_count ?? 0)} Dateien</span></summary><div class="change-operation-body">`;
                if (targetDirectory) {
                  html += `<div><div class="muted">ZIELORDNER AUF DER SSD</div><code style="display:block;white-space:pre-wrap;word-break:break-word">${escapeHtml(backupRootLabel)}/${escapeHtml(targetDirectory)}</code></div>`;
                }
                for (const family of families) {
                  const familyLabel = String(family.original_stem || family.family_key || `Familie ${family.family_id || ""}`);
                  const sourcePaths = Array.isArray(family.source_paths) ? family.source_paths : [];
                  html += `<div class="card" style="padding:9px 10px"><strong>${escapeHtml(familyLabel)}</strong><span class="muted" style="margin-left:8px">${Number(family.file_count || sourcePaths.length || 0)} Dateien</span>`;
                  if (sourcePaths.length) {
                    html += `<div class="muted" style="margin-top:7px">IM ARCHIV</div>${sourcePaths.map(path => `<code style="display:block;white-space:pre-wrap;word-break:break-word">${escapeHtml(archiveRootLabel)}/${escapeHtml(path)}</code>`).join("")}`;
                  }
                  html += `</div>`;
                }
                html += `</div></details>`;
              }
              html += `</div>`;
            }
            html += `<details style="margin-top:10px"><summary>Konkrete Kopierpfade anzeigen</summary><div style="display:grid;gap:8px;margin-top:8px">`;
            for (const row of releaseRows) {
              html += `<div class="card" style="padding:9px 10px"><div class="muted">VON</div><code style="display:block;white-space:pre-wrap;word-break:break-word">${escapeHtml(archiveRootLabel)}/${escapeHtml(row.old_path || "")}</code><div class="muted" style="margin-top:5px">NACH</div><code style="display:block;white-space:pre-wrap;word-break:break-word">${escapeHtml(backupRootLabel)}/${escapeHtml(row.workspace_release_path || row.calculated_workspace_release_path || "")}</code></div>`;
            }
            html += `</div></details></div>`;
            html += `<div id="change-release-progress" class="change-progress"><div class="muted" data-progress-label></div><div class="change-progress-track"><div class="change-progress-bar"></div></div><div id="change-release-errors" class="danger-text" style="display:none"></div></div>`;
            html += copiesReady
              ? `<div class="change-footer"><button type="button" class="plan-button bk-positive-action" data-cr-release-copy-verify>SSD-Kopien prüfen</button></div></section>`
              : `<div class="change-footer"><button type="button" class="plan-button bk-positive-action" data-cr-release-copy-create>SSD-Kopien anlegen</button></div></section>`;
          } else if (releaseRequired && releaseStage === "remove_archive") {
            html += `<div class="card"><strong>✓ SSD-Kopien vollständig geprüft</strong><p class="success-text" style="margin-top:5px">Alle freigewordenen Dateien stimmen nach Größe und SHA-256 mit dem geplanten Bestand überein.</p></div>`;
            html += `<div class="card"><strong>2. Bestätigte Archivoriginale entfernen</strong><p class="muted" style="margin-top:5px">Jetzt kannst du ausschließlich die unten aufgeführten Originale manuell aus der Kamerabibliothek entfernen. Die App löscht dort selbst nichts.</p><details style="margin-top:10px"><summary>${releaseRows.length} Archivpfade anzeigen</summary><div style="margin-top:8px">${releaseRows.map(row => `<code style="display:block;white-space:pre-wrap;word-break:break-word">${escapeHtml(archiveRootLabel)}/${escapeHtml(row.old_path || "")}</code>`).join("")}</div></details></div>`;
            html += `<div id="change-release-progress" class="change-progress"><div class="muted" data-progress-label></div><div class="change-progress-track"><div class="change-progress-bar"></div></div><div id="change-release-errors" class="danger-text" style="display:none"></div></div>`;
            html += `<div class="change-footer"><button type="button" class="plan-button bk-positive-action" data-cr-release-removal-verify>Entfernung aus dem Archiv prüfen</button></div></section>`;
          } else {
            let number = 1;
            if (releaseRequired) {
              html += `<div class="card"><strong>✓ Freigewordene Archivdateien sicher zurückgeholt</strong><p class="success-text" style="margin-top:5px">${Number(releaseStock.family_count || 0)} Familien bleiben nach Abschluss als freier Bestand unter <em>Freigewordene Archivdateien</em> auf der SSD erhalten.</p></div>`;
            }

            if (targetTree) {
              const targetTitle = targetStructureDeleted ? "Zielzustand" : "Zielstruktur-Vorschau";
              const targetHint = targetStructureDeleted
                ? "Bei diesem Löschauftrag wird keine neue Archivstruktur aufgebaut."
                : "So soll das bearbeitete Ereignis nach den folgenden Finder-Schritten im Archiv aussehen.";
              html += `<details class="card change-disclosure"><summary><strong>${targetTitle}</strong></summary><p class="muted" style="margin-top:8px">${targetHint}</p><pre class="change-target-tree" style="margin-top:9px">${escapeHtml(targetTree)}</pre></details>`;
            }

            for (const operation of assistant.operations || []) {
              const state = String(operation.state || "");
              const stateBadge =
                state === "done" ? '<span class="badge success">Erledigt</span>'
                : state === "pending" ? '<span class="badge warning">Ausstehend</span>'
                : state === "attention" ? '<span class="badge danger">Prüfen</span>'
                : "";
              html += `<details class="card change-operation" ${number === 1 ? "open" : ""}><summary><span>${number}. ${escapeHtml(operation.title || "Finder-Schritt")}</span>${stateBadge}</summary><div class="change-operation-body"><div>${escapeHtml(operation.detail || "")}</div>`;
              if ((operation.sources || []).length) {
                html += `<div class="muted">VON</div>${operation.sources.map(source => `<code style="display:block;white-space:pre-wrap;word-break:break-word">${escapeHtml(source)}</code>`).join("")}`;
              } else if (operation.source) {
                html += `<div class="muted">VON</div><code style="display:block;white-space:pre-wrap;word-break:break-word">${escapeHtml(operation.source)}</code>`;
              }
              if ((operation.items || []).length && operation.kind !== "remove_directories") {
                html += `<details><summary>${operation.items.length} Element${operation.items.length===1?"":"e"} anzeigen</summary><div style="margin-top:7px">${operation.items.map(name => `<code style="display:block">${escapeHtml(name)}</code>`).join("")}</div></details>`;
              }
              if (operation.target) html += `<div class="muted">NACH</div><code style="display:block;white-space:pre-wrap;word-break:break-word">${escapeHtml(operation.target)}</code>`;
              if ((operation.paths || []).length) {
                html += `<div class="muted">NOCH ZU ENTFERNEN</div>${operation.paths.map(path => `<code style="display:block;white-space:pre-wrap;word-break:break-word">${escapeHtml(path)}</code>`).join("")}`;
              } else if (operation.kind === "remove_directories" && state === "done") {
                html += `<div class="success-text">Alle vorgesehenen alten Ordner sind bereits entfernt.</div>`;
              }
              html += `</div></details>`;
              number += 1;
            }
            html += renderTechnicalDetails();
            html += `<div class="change-footer"><button type="button" class="plan-button bk-positive-action" data-cr-finder-done>Finder-Arbeit erledigt · weiter zu Prüfen</button></div></section>`;
          }
        }

        if (phase === "verify") {
          const managedReviewRows = Array.isArray(reviewRows)
            ? reviewRows.filter(row => !Boolean(row.advisory))
            : [];
          const initiallyVerified =
            Array.isArray(reviewRows)
            && reviewRows.length > 0
            && managedReviewRows.every(row => String(row.verification_status || "") === "verified");
          html += `<section class="change-pane"><div class="change-pane-heading"><div><h3>Prüfen & Abschließen</h3><p class="muted">So soll die Kamerabibliothek jetzt aussehen. Die Prüfung selbst bleibt vollständig read-only.</p></div></div>`;
          if (targetTree) html += `<div class="card"><strong>SOLL-Struktur</strong><pre class="change-target-tree" style="margin-top:9px">${escapeHtml(targetTree)}</pre></div>`;
          html += `<div id="change-verify-panel" class="card"><div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap"><button type="button" class="plan-button${initiallyVerified ? " success" : ""}" data-cr-verify>${initiallyVerified ? "✓ Prüfung erfolgreich" : "Prüfen"}</button><span id="change-verify-summary" class="${initiallyVerified ? "success-text" : "muted"}">${initiallyVerified ? `${reviewRows.length}/${reviewRows.length} Dateien bestätigt.` : "Noch nicht geprüft."}</span></div><div id="change-work-progress" class="change-progress"><div class="muted" data-progress-label></div><div class="change-progress-track"><div class="change-progress-bar"></div></div></div><div id="change-verify-errors" style="display:none;margin-top:10px"></div></div>`;
          html += renderTechnicalDetails();
          html += `<div class="change-footer"><button type="button" class="plan-button bk-positive-action" data-cr-archive ${initiallyVerified ? "" : "disabled"}>Änderung abschließen & SSD freigeben</button></div></section>`;
        }

        changeRequestBody.innerHTML = html;

        const liveRefreshButton=changeRequestBody.querySelector("[data-cr-refresh-live]");
        liveRefreshButton?.addEventListener("click", async () => {
          liveRefreshButton.disabled=true;
          liveRefreshButton.classList.add("loading");
          liveRefreshButton.textContent="Aktualisiere …";
          try {
            await showChangeRequestDetail(crId,{phase:"finder",refreshLive:true});
          } catch (error) {
            liveRefreshButton.disabled=false;
            liveRefreshButton.classList.remove("loading");
            liveRefreshButton.textContent="↻ Aktualisieren";
            setStatus(error.message,true);
          }
        });

        const releaseCreateButton=changeRequestBody.querySelector("[data-cr-release-copy-create]");
        releaseCreateButton?.addEventListener("click", async () => {
          const progress=changeRequestBody.querySelector("#change-release-progress");
          const bar=progress?.querySelector(".change-progress-bar");
          const label=progress?.querySelector("[data-progress-label]");
          const errors=progress?.querySelector("#change-release-errors");
          releaseCreateButton.disabled=true;
          progress?.classList.add("active");
          if(bar) bar.style.width="35%";
          if(label) label.textContent="Archivdateien werden geprüft und sicher auf die SSD kopiert …";
          if(errors){errors.style.display="none";errors.innerHTML="";}
          try {
            const result=await requestJson(
              `/api/change-requests/${encodeURIComponent(crId)}/release-copy/create`,
              {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(options.body || {})}
            );
            if(bar) bar.style.width="100%";
            if(label) label.textContent=`${Number(result.verified_file_count||result.copied_file_count||0)} SSD-Kopien wurden angelegt und vollständig geprüft.`;
            await new Promise(resolve=>setTimeout(resolve,180));
            await showChangeRequestDetail(crId,{phase:"finder"});
          } catch(error) {
            releaseCreateButton.disabled=false;
            if(bar) bar.style.width="100%";
            if(label) label.textContent="Kopieren fehlgeschlagen.";
            if(errors){
              errors.style.display="block";
              errors.textContent=error.message;
            }
          }
        });

        const releaseCopyButton=changeRequestBody.querySelector("[data-cr-release-copy-verify]");
        releaseCopyButton?.addEventListener("click", async () => {
          const progress=changeRequestBody.querySelector("#change-release-progress");
          const bar=progress?.querySelector(".change-progress-bar");
          const label=progress?.querySelector("[data-progress-label]");
          const errors=progress?.querySelector("#change-release-errors");
          releaseCopyButton.disabled=true;
          progress?.classList.add("active");
          if(bar) bar.style.width="25%";
          if(label) label.textContent="SSD-Kopien werden nach Größe und SHA-256 geprüft …";
          if(errors){errors.style.display="none";errors.innerHTML="";}
          try {
            const result=await requestJson(
              `/api/change-requests/${encodeURIComponent(crId)}/release-copy/verify`,
              {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({})}
            );
            if(bar) bar.style.width="100%";
            if(!result.complete) {
              const problems=(result.files||[]).filter(row=>String(row.status||"")!=="release_copy_verified");
              if(label) label.textContent=`${Number(result.verified_file_count||0)}/${Number(result.file_count||0)} SSD-Kopien sind korrekt.`;
              if(errors){
                errors.style.display="block";
                errors.innerHTML=problems.map(row=>`<div style="margin-top:5px"><strong>${escapeHtml(String(row.workspace_release_path||row.old_path||"Datei"))}</strong><br>${escapeHtml(String(row.message||row.status||"Prüfung fehlgeschlagen"))}</div>`).join("");
              }
              releaseCopyButton.disabled=false;
              return;
            }
            if(label) label.textContent="Alle SSD-Kopien sind vollständig geprüft.";
            await new Promise(resolve=>setTimeout(resolve,180));
            await showChangeRequestDetail(crId,{phase:"finder"});
          } catch(error) {
            releaseCopyButton.disabled=false;
            if(bar) bar.style.width="100%";
            if(label) label.textContent="Prüfung fehlgeschlagen.";
            if(errors){
              errors.style.display="block";
              errors.textContent=error.message;
            }
          }
        });

        const releaseRemovalButton=changeRequestBody.querySelector("[data-cr-release-removal-verify]");
        releaseRemovalButton?.addEventListener("click", async () => {
          const progress=changeRequestBody.querySelector("#change-release-progress");
          const bar=progress?.querySelector(".change-progress-bar");
          const label=progress?.querySelector("[data-progress-label]");
          const errors=progress?.querySelector("#change-release-errors");
          releaseRemovalButton.disabled=true;
          progress?.classList.add("active");
          if(bar) bar.style.width="25%";
          if(label) label.textContent="SSD-Kopien und entfernte Archivoriginale werden geprüft …";
          if(errors){errors.style.display="none";errors.innerHTML="";}
          try {
            const result=await requestJson(
              `/api/change-requests/${encodeURIComponent(crId)}/release-removal/verify`,
              {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({})}
            );
            if(bar) bar.style.width="100%";
            if(!result.complete) {
              const problems=(result.files||[]).filter(row=>String(row.status||"")!=="verified");
              if(label) label.textContent=`${Number(result.verified_file_count||0)}/${Number(result.file_count||0)} Dateien sind vollständig freigegeben.`;
              if(errors){
                errors.style.display="block";
                errors.innerHTML=problems.map(row=>`<div style="margin-top:5px"><strong>${escapeHtml(String(row.old_path||"Datei"))}</strong><br>${escapeHtml(String(row.message||row.status||"Prüfung fehlgeschlagen"))}</div>`).join("");
              }
              releaseRemovalButton.disabled=false;
              return;
            }
            if(label) label.textContent="Archivoriginale sind entfernt und der SSD-Bestand ist bestätigt.";
            await new Promise(resolve=>setTimeout(resolve,180));
            await showChangeRequestDetail(crId,{phase:"finder"});
          } catch(error) {
            releaseRemovalButton.disabled=false;
            if(bar) bar.style.width="100%";
            if(label) label.textContent="Prüfung fehlgeschlagen.";
            if(errors){
              errors.style.display="block";
              errors.textContent=error.message;
            }
          }
        });

        for (const button of changeRequestBody.querySelectorAll("[data-change-step]")) {
          button.addEventListener("click", () => {
            showChangeRequestDetail(crId, {phase:button.dataset.changeStep})
              .catch(error => setStatus(error.message, true));
          });
        }

        const preparedNextBtn = changeRequestBody.querySelector("[data-cr-prepared-next]");
        if (preparedNextBtn) preparedNextBtn.addEventListener("click", () => {
          showChangeRequestDetail(crId, {phase:finderNeeded ? "finder" : "verify"})
            .catch(error => setStatus(error.message, true));
        });

        const prepareBtn = changeRequestBody.querySelector("[data-cr-prepare]");
        if (prepareBtn) {
          const runArchivePreparation = async (transferMode=null) => {
            const progress = changeRequestBody.querySelector("#change-prep-progress");
            const bar = progress?.querySelector(".change-progress-bar");
            const label = progress?.querySelector("[data-progress-label]");
            prepareBtn.disabled = true;
            progress?.classList.add("active");
            if (label) {
              label.textContent = transferMode
                ? (transferMode === "copy"
                    ? "Dateien werden verifiziert kopiert und der Hilfsbereich wird vorbereitet …"
                    : "Dateien werden verifiziert verschoben und der Hilfsbereich wird vorbereitet …")
                : "Ordner und Hardlinks werden unter „Später zuordnen“ vorbereitet …";
            }
            if (bar) bar.style.width = "35%";
            try {
              await changeRequestAction(
                crId,
                "confirm",
                {
                  terminal:false,
                  payload: transferMode ? {transfer_mode:transferMode} : {}
                }
              );
              if (bar) bar.style.width = "100%";
              if (label) label.textContent = "Hilfsbereich ist vorbereitet.";
              changeRequestBody.querySelector("#change-transfer-choice")?.remove();
              await new Promise(resolve => setTimeout(resolve, 180));
              await showChangeRequestDetail(
                crId,
                {phase:finderNeeded ? "finder" : "verify"}
              );
            } catch (error) {
              prepareBtn.disabled = false;
              const message = String(error?.message || error || "");
              if (message.includes("TRANSFER_CHOICE_REQUIRED")) {
                if (bar) bar.style.width = "100%";
                if (label) {
                  label.textContent =
                    "Hardlinks sind zwischen diesen Speicherorten nicht möglich. "
                    + "Wähle, wie die Dateien nach „Später zuordnen“ gelangen sollen.";
                }
                let chooser = changeRequestBody.querySelector("#change-transfer-choice");
                if (!chooser) {
                  chooser = document.createElement("div");
                  chooser.id = "change-transfer-choice";
                  chooser.className = "card";
                  chooser.style.marginTop = "12px";
                  chooser.innerHTML = `
                    <strong>Speicherorte liegen auf unterschiedlichen Dateisystemen</strong>
                    <p class="muted" style="margin-top:6px">
                      Ein Hardlink ist deshalb nicht möglich. Beide Varianten prüfen Größe und SHA-256 vollständig.
                    </p>
                    <div style="display:grid;gap:9px;margin-top:10px">
                      <button type="button" class="plan-button" data-cr-transfer-choice="copy">
                        Kopieren
                      </button>
                      <div class="muted">
                        Die freie Quelldatei bleibt zunächst erhalten. Nach erfolgreichem Abschluss wird die nicht mehr benötigte SSD-Kopie bereinigt.
                      </div>
                      <button type="button" class="plan-button" data-cr-transfer-choice="move">
                        Verschieben
                      </button>
                      <div class="muted">
                        Erst nach vollständig verifizierter Hilfskopie wird die freie Quelldatei entfernt. Beim Verwerfen wird sie sicher zurückgestellt.
                      </div>
                    </div>
                  `;
                  progress?.insertAdjacentElement("afterend", chooser);
                  chooser.querySelectorAll("[data-cr-transfer-choice]").forEach(button => {
                    button.addEventListener("click", () => {
                      const mode = String(button.dataset.crTransferChoice || "");
                      chooser.remove();
                      runArchivePreparation(mode).catch(err => setStatus(err.message, true));
                    });
                  });
                }
                return;
              }
              if (label) label.textContent = message;
              throw error;
            }
          };
          prepareBtn.addEventListener("click", () => {
            runArchivePreparation(null).catch(error => setStatus(error.message, true));
          });
        }

        const finderDoneBtn = changeRequestBody.querySelector("[data-cr-finder-done]");
        if (finderDoneBtn) finderDoneBtn.addEventListener("click", async () => {
          finderDoneBtn.disabled = true;
          try {
            if (String(cr.status) === "aenderbar_vorschlagen") {
              await changeRequestAction(crId, "confirm", {terminal:false});
            }
            await showChangeRequestDetail(crId, {phase:"verify"});
          } catch (error) {
            finderDoneBtn.disabled = false;
            setStatus(error.message, true);
          }
        });

        const verifyBtn = changeRequestBody.querySelector("[data-cr-verify]");
        const archiveBtn = changeRequestBody.querySelector("[data-cr-archive]");
        if (verifyBtn) verifyBtn.addEventListener("click", async () => {
          const progress = changeRequestBody.querySelector("#change-work-progress");
          const bar = progress?.querySelector(".change-progress-bar");
          const label = progress?.querySelector("[data-progress-label]");
          const summary = changeRequestBody.querySelector("#change-verify-summary");
          const errors = changeRequestBody.querySelector("#change-verify-errors");
          verifyBtn.disabled = true;
          verifyBtn.classList.remove("success", "danger");
          verifyBtn.textContent = "Prüfung läuft …";
          progress?.classList.add("active");
          if (bar) bar.style.width = "20%";
          if (label) label.textContent = "Kamerabibliothek wird nach Pfad, Größe und SHA-256 geprüft …";
          if (errors) { errors.style.display = "none"; errors.innerHTML = ""; }
          try {
            if (String(cr.status) === "aenderbar_vorschlagen") {
              await changeRequestAction(crId, "confirm", {terminal:false});
            }
            if (bar) bar.style.width = "45%";
            const data = await requestJson(
              `/api/change-requests/${encodeURIComponent(crId)}/verify`,
              {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({})}
            );
            if (bar) bar.style.width = "100%";
            const total = Number(data.file_count || 0);
            const ok = Number(data.verified_file_count || 0);
            const advisories = data.advisories || [];
            const problems = (data.files || []).filter(row => !["verified","advisory"].includes(String(row.status || "")));
            const directoryProblems = (data.directories || []).filter(row => String(row.status || "") !== "verified");
            const obsoleteDirectoryProblems = (data.obsolete_directories || []).filter(row => String(row.status || "") !== "verified");
            const eventDocumentProblem =
              data.event_document && String(data.event_document.status || "") !== "verified"
                ? data.event_document
                : null;
            if (data.complete) {
              verifyBtn.classList.add("success");
              verifyBtn.textContent = "✓ Prüfung erfolgreich";
              if (summary) {
                summary.className = "success-text";
                summary.textContent = ok + "/" + total + " verwaltete Dateien bestätigt."
                  + (advisories.length ? " · " + advisories.length + " zusätzliche Datei" + (advisories.length===1?"":"en") + " nur als Hinweis." : "");
              }
              if (label) label.textContent = "Prüfung abgeschlossen.";
              if (errors && advisories.length) {
                errors.style.display = "block";
                errors.innerHTML = advisories.map(row => {
                  const title = row.advisory_reason === "redundant_duplicate"
                    ? "Byte-identische Zusatzkopie · nur Hinweis"
                    : "Zusätzliche nicht verwaltete Datei · nur Hinweis";
                  return '<div class="card" style="margin-top:8px"><strong>'+escapeHtml(title)+'</strong><div class="muted">'
                    + escapeHtml(row.message || "") + '</div><code style="display:block;white-space:pre-wrap;word-break:break-word">'
                    + escapeHtml(row.path || "—") + '</code></div>';
                }).join("");
              }
              if (archiveBtn) archiveBtn.disabled = false;
            } else {
              verifyBtn.classList.add("danger");
              verifyBtn.textContent = "✕ Prüfung mit Problemen";
              const problemCount = problems.length + directoryProblems.length + obsoleteDirectoryProblems.length + (eventDocumentProblem ? 1 : 0);
              if (summary) { summary.className = "danger-text"; summary.textContent = `${ok}/${total} Dateien bestätigt · ${problemCount} Problem${problemCount===1?"":"e"}.`; }
              if (label) label.textContent = "Bitte die angezeigten Abweichungen im Finder korrigieren und erneut prüfen.";
              if (archiveBtn) archiveBtn.disabled = true;
              if (errors) {
                errors.style.display = "block";
                const fileHtml = problems.map(row => {
                  const problemLabel =
                    row.status === "missing" ? "Fehlt am Ziel"
                    : row.status === "old_path_still_exists" ? "Liegt noch am alten Ort"
                    : row.status === "size_mismatch" ? "Dateigröße abweichend"
                    : row.status === "sha256_mismatch" ? "SHA-256 abweichend"
                    : row.status === "needs_reassignment" ? "Noch neu zuzuordnen"
                    : (row.message || row.status || "Problem");
                  return `<div class="card" style="margin-top:8px"><strong>${escapeHtml(problemLabel)}</strong>${row.message ? `<div class="muted">${escapeHtml(row.message)}</div>` : ""}<div class="muted" style="margin-top:5px">SOLL</div><code style="display:block;white-space:pre-wrap;word-break:break-word">${escapeHtml(row.new_path || "—")}</code></div>`;
                }).join("");
                const directoryHtml = directoryProblems.map(row =>
                  `<div class="card" style="margin-top:8px"><strong>Erforderlicher Ordner fehlt</strong><div class="muted">SOLL · Kamerabibliothek</div><code style="display:block;white-space:pre-wrap;word-break:break-word">${escapeHtml(row.path || "—")}</code></div>`
                ).join("");
                const obsoleteHtml = obsoleteDirectoryProblems.map(row =>
                  `<div class="card" style="margin-top:8px"><strong>Alter Ordner noch vorhanden</strong><div class="muted">Dieser Ordner wird im SOLL nicht mehr benötigt</div><code style="display:block;white-space:pre-wrap;word-break:break-word">${escapeHtml(row.path || "—")}</code></div>`
                ).join("");
                const eventDocumentHtml = eventDocumentProblem
                  ? `<div class="card" style="margin-top:8px"><strong>event.json stimmt noch nicht</strong><div class="muted">${escapeHtml(eventDocumentProblem.message || "")}</div><code style="display:block;white-space:pre-wrap;word-break:break-word">${escapeHtml(eventDocumentProblem.path || "event.json")}</code></div>`
                  : "";
                const advisoryHtml = advisories.map(row => {
                  const title = row.advisory_reason === "redundant_duplicate"
                    ? "Byte-identische Zusatzkopie · nur Hinweis"
                    : "Zusätzliche nicht verwaltete Datei · nur Hinweis";
                  return '<div class="card" style="margin-top:8px"><strong>'+escapeHtml(title)+'</strong><div class="muted">'
                    + escapeHtml(row.message || "") + '</div><code style="display:block;white-space:pre-wrap;word-break:break-word">'
                    + escapeHtml(row.path || "—") + '</code></div>';
                }).join("");
                errors.innerHTML = fileHtml + directoryHtml + obsoleteHtml + eventDocumentHtml + advisoryHtml;
              }
            }
          } catch (error) {
            verifyBtn.classList.add("danger");
            verifyBtn.textContent = "✕ Prüfung fehlgeschlagen";
            if (summary) { summary.className = "danger-text"; summary.textContent = error.message; }
            if (archiveBtn) archiveBtn.disabled = true;
          } finally {
            verifyBtn.disabled = false;
          }
        });

        if (archiveBtn) archiveBtn.addEventListener("click", async () => {
          const progress = changeRequestBody.querySelector("#change-work-progress");
          const bar = progress?.querySelector(".change-progress-bar");
          const label = progress?.querySelector("[data-progress-label]");
          const summary = changeRequestBody.querySelector("#change-verify-summary");
          archiveBtn.disabled = true;
          verifyBtn && (verifyBtn.disabled = true);
          progress?.classList.add("active");
          if (bar) bar.style.width = "12%";
          if (label) label.textContent = "Geprüften SOLL-Zustand in die Datenbank übernehmen …";

          let pct = 12;
          const pulse = window.setInterval(() => {
            pct = Math.min(78, pct + 7);
            if (bar) bar.style.width = `${pct}%`;
            if (pct >= 48 && label) label.textContent = "SSD-Originale und Hilfslinks sicher freigeben …";
          }, 220);
          try {
            const res = await fetch(`/api/change-requests/${encodeURIComponent(crId)}/archive`, {
              method:"POST",
              headers:{"Content-Type":"application/json"},
              body:JSON.stringify({})
            });
            const data = await res.json().catch(() => ({}));
            if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
            window.clearInterval(pulse);
            if (bar) bar.style.width = "100%";
            if (label) label.textContent = "Abgeschlossen · SSD freigegeben und leere Quellordner aufgeräumt.";
            if (summary) { summary.className = "success-text"; summary.textContent = "Änderung vollständig abgeschlossen."; }
            await new Promise(resolve => setTimeout(resolve, 280));

            mandatoryArchiveChangeContext = null;
            clearChangeTaskFromUrl(crId);
            changeRequestClose.textContent = "Schließen";
            changeRequestClose.classList.remove("danger-button");
            if (changeRequestDialog.open) changeRequestDialog.close();
            await loadEvents({reset:true});
            refreshGlobalTasks();
            setStatus("Archivänderung abgeschlossen.", false, true);
          } catch (error) {
            window.clearInterval(pulse);
            archiveBtn.disabled = false;
            verifyBtn && (verifyBtn.disabled = false);
            if (label) label.textContent = error.message;
            setStatus(error.message, true);
          }
        });
      } catch (error) {
        changeRequestBody.textContent = `Fehler: ${error.message}`;
        setStatus(error.message, true);
      }
    }

    async function changeRequestAction(crId, action, options={}) {
      const res = await fetch(`/api/change-requests/${encodeURIComponent(crId)}/${action}`, {
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify(options.payload || {})
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);

      if (action === "cancel") {
        if (data.reversal_required) {
          await showArchiveReversalDetail(
            crId,
            {assistant:data.reversal || undefined}
          );
          setStatus(
            "Rückänderungsauftrag gestartet. Stelle jetzt den ursprünglichen Archivzustand wieder her.",
            false,
            true
          );
          return data;
        }
        mandatoryArchiveChangeContext = null;
        clearChangeTaskFromUrl(crId);
        changeRequestClose.disabled = false;
        changeRequestClose.textContent = "Schließen";
        changeRequestClose.classList.remove("danger-button");
        if (changeRequestDialog.open) changeRequestDialog.close();
        await loadEvents({reset:true});
        refreshGlobalTasks();
        const cleanupWarnings=Array.isArray(data.cleanup_warnings) ? data.cleanup_warnings : [];
        if (cleanupWarnings.length) {
          setStatus(
            "Archivänderung verworfen. Eigene SSD-Kopien wurden entfernt; fremde oder unbekannte Inhalte blieben unangetastet: "
              + cleanupWarnings.join(" · "),
            true
          );
        } else {
          setStatus("Archivänderung verworfen. Der vorherige Zustand bleibt gültig.", false, true);
        }
        return data;
      }

      if (options.terminal !== false) {
        setStatus(`Änderungsauftrag: ${escapeHtml(data.status || action)}`);
      }
      refreshGlobalTasks();
      return data;
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
        setChangeTaskInUrl(data.change_request_id, jobId || "");
        if (!changeRequestDialog.open) changeRequestDialog.showModal();
        await showChangeRequestDetail(data.change_request_id);
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

    document.getElementById("event-reload")?.addEventListener("click", async event => {
      const button = event.currentTarget;
      button.disabled = true; button.classList.add("bk-busy");
      try {
        await loadEvents({reset:true,physicalRefresh:true});
        await window.bkForceExternalChangeCheck?.();
      } catch (error) { setStatus(error.message, true); }
      finally { button.disabled = false; button.classList.remove("bk-busy"); }
    });

    eventSearch?.addEventListener("input", () => {
      clearTimeout(eventSearchTimer);
      eventSearchTimer = setTimeout(() => loadEvents({reset:true}).catch(error=>setStatus(error.message,true)), 250);
    });
    eventLoadMore?.addEventListener("click", () => loadEvents({reset:false}).catch(error=>setStatus(error.message,true)));

    function structurePathLabel(value) {
      return value ? value : "Direkt im Ereignis";
    }

    function friendlyWorkspacePath(value) {
      const raw=String(value||"").replaceAll("\\","/");
      for(const marker of ["/Arbeitsbereich/","/SD-Kartensicherungen/"]){
        const index=raw.lastIndexOf(marker);
        if(index>=0) return raw.slice(index+1);
      }
      return raw;
    }

    function clearStructureTaskFromUrl(changeId) {
      const url=new URL(window.location.href);
      if(url.searchParams.get("task")===`structure:${changeId}`){
        url.searchParams.delete("task");
        history.replaceState(null,"",url.pathname+(url.search||"")+url.hash);
      }
    }

    async function showStructureChange(changeId) {
      const change=await requestJson(`/api/event-structure-changes/${encodeURIComponent(changeId)}`);
      if(change.status==="completed"){
        if(structureChangeDialog.open) structureChangeDialog.close();
        clearStructureTaskFromUrl(changeId);
        await refreshGlobalTasks();
        return false;
      }
      if (!structureChangeDialog.open) structureChangeDialog.showModal();
      structureChangeBody.textContent="Änderung wird geladen …";
      const d=change.detected||{};
      structureChangeSubtitle.textContent=(d.status==="archived"?"Archiviert":"Angewendet")+" · "+String(d.event_name||change.event_id||"");
      const added=d.directory_added||[], removed=d.directory_removed||[], moves=d.file_moves||[];
      const rootRename=d.root_rename||null;
      const childRenames=d.child_renames||[];
      const structureEnabled=Boolean(d.proposed_structure_enabled);
      const rawInputOptions=d.input_options||[""];
      const inputOptions=structureEnabled
        ? rawInputOptions.filter(path=>String(path)!=="")
        : [""];
      const preparedInput=String(d.selected_input_path||change.proposed_input_path||"");
      const currentInput=change.status==="prepared"
        ? preparedInput
        : String(d.current_input_path||"");
      const currentKnown=inputOptions.some(path=>String(path)===currentInput);
      const options=(!currentKnown
        ? ['<option value="__choose__" selected disabled>Bitte Input-Ordner wählen · momentan unbekannt</option>']
        : []
      ).concat(inputOptions.map(path=>{
        const current=String(path)===currentInput;
        return `<option value="${escapeHtml(path)}" ${current?"selected":""}>${escapeHtml(structurePathLabel(path))}${current?" · momentan Input":""}</option>`;
      })).join("");
      const blockers=[
        ...(d.missing_file_ids||[]).map(id=>`Kameraoriginal fehlt · Datei-ID ${id}`),
        ...(d.duplicate_file_ids||[]).map(id=>`Kameraoriginal mehrfach gefunden · Datei-ID ${id}`),
        ...(d.unclassified_directories||[]).map(path=>`Strukturpfad nicht eindeutig · ${path}`),
        ...(d.inconsistent_leaf_layouts?["Unterereignis-/Tagesblätter besitzen unterschiedliche Ordnerstrukturen."]:[])
      ];
      const folderChangeCount=added.length+removed.length+(rootRename?1:0)+childRenames.length;
      const folderChanges=[
        ...(rootRename?[ `<div>↪ Ereignisordner: <code>${escapeHtml(rootRename.old_folder||rootRename.old_path||"")}</code><br><span class="muted">nach</span> <code>${escapeHtml(rootRename.new_folder||rootRename.new_path||"")}</code></div>` ]:[]),
        ...childRenames.map(row=>`<div>↪ Unterereignisordner: <code>${escapeHtml(row.old_folder||"")}</code><br><span class="muted">nach</span> <code>${escapeHtml(row.new_folder||"")}</code></div>`),
        ...added.map(path=>`<div>＋ Ordner: <code>${escapeHtml(path)}</code></div>`),
        ...removed.map(path=>`<div>− Ordner: <code>${escapeHtml(path)}</code></div>`)
      ].join("");
      const fileChanges=moves.map(row=>`<div>→ Datei: <code>${escapeHtml(row.old_path||"")}</code><br><span class="muted">nach</span> <code>${escapeHtml(row.new_path||"")}</code></div>`).join("");
      const changeDetails=(folderChangeCount||moves.length)
        ? `
          ${folderChangeCount?`<details class="card" style="margin:9px 0 0;padding:9px 11px">
            <summary><strong>Ordneränderungen · ${folderChangeCount}</strong></summary>
            <div style="display:grid;gap:6px;margin-top:9px">${folderChanges}</div>
          </details>`:""}
          ${moves.length?`<details class="card" style="margin:9px 0 0;padding:9px 11px">
            <summary><strong>Dateiänderungen · ${moves.length}</strong></summary>
            <div style="display:grid;gap:6px;margin-top:9px">${fileChanges}</div>
          </details>`:""}`
        : '<div class="muted" style="margin-top:9px">Keine Pfadänderungen.</div>';
      const inputControl=change.status==="prepared"
        ? `<div class="card" style="margin-top:14px">
            <strong>Input-Ordner</strong>
            <div style="margin-top:6px">${escapeHtml(structurePathLabel(preparedInput))}</div>
            <div class="muted" style="margin-top:4px">Bereits in der vorbereiteten event.json gespeichert.</div>
          </div>`
        : `<label class="edit-field" style="margin-top:14px"><span>Welcher Ordner soll zukünftig der Input-Ordner sein?</span>
            <select id="structure-change-input" ${blockers.length?"disabled":""}>${options}</select>
          </label>
          <div id="structure-change-input-error" class="error-box" hidden style="margin-top:10px"></div>`;
      const preview=`
        <div class="card">
          <strong>Erkannte Änderungen</strong>
          ${changeDetails}
        </div>
        ${blockers.length?`<div class="error-box" style="margin-top:12px"><strong>Diese Änderung kann noch nicht übernommen werden.</strong>${blockers.map(x=>`<div style="margin-top:6px">${escapeHtml(x)}</div>`).join("")}</div>`:""}
        ${inputControl}`;
      if(change.root_kind==="shared_workspace"){
        structureChangeBody.innerHTML=preview+`
          <div class="edit-actions">
            <button type="button" id="structure-change-confirm" class="plan-button bk-positive-action" ${blockers.length?"disabled":""}>Änderungen übernehmen</button>
          </div>`;
        document.getElementById("structure-change-confirm")?.addEventListener("click",async()=>{
          const input=document.getElementById("structure-change-input").value;
          const inlineError=document.getElementById("structure-change-input-error");
          if(input==="__choose__"){
            if(inlineError){inlineError.textContent="Bitte einen zukünftigen Input-Ordner wählen.";inlineError.hidden=false;}
            return;
          }
          if(inlineError) inlineError.hidden=true;
          try{
            structureChangeBody.insertAdjacentHTML("beforeend",'<p class="muted">event.json und SQLite werden aktualisiert …</p>');
            await requestJson(`/api/event-structure-changes/${encodeURIComponent(changeId)}/confirm-applied`,{
              method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({input_path:input})
            });
            clearStructureTaskFromUrl(changeId);
            structureChangeDialog.close();
            await loadEvents({reset:true});
            await refreshGlobalTasks();
            setStatus("Manuelle Ereignisänderung übernommen. event.json und SQLite sind aktuell.",false,true);
          }catch(error){
            if(inlineError){inlineError.textContent=error.message;inlineError.hidden=false;}
          }
        });
        return;
      }
      if(change.status==="prepared"){
        const prepared=friendlyWorkspacePath(d.prepared_event_json_path||"");
        const target=(String(d.event_name||"") && String(d.status||"")==="archived") ? "im Ereignisordner des Archivs" : "im Archiv";
        structureChangeBody.innerHTML=preview+`
          <div class="card" style="margin-top:14px"><strong>Schritt 2 von 2 · event.json ersetzen</strong>
            <p>Vorbereitet:</p><code style="display:block;white-space:pre-wrap;word-break:break-all">${escapeHtml(prepared)}</code>
            <p>Ersetze damit die vorhandene <code>event.json</code> ${target}. Andere Archivdateien werden von Bibliothekar nicht verändert.</p>
          </div>
          <div class="edit-actions"><button type="button" id="structure-change-verify" class="plan-button bk-positive-action">Prüfen</button></div>`;
        document.getElementById("structure-change-verify")?.addEventListener("click",async(event)=>{
          const button=event.currentTarget;
          button.disabled=true;
          const oldFeedback=document.getElementById("structure-change-verify-feedback");
          oldFeedback?.remove();
          structureChangeBody.insertAdjacentHTML("beforeend",'<p id="structure-change-verify-feedback" class="muted">Archivbestand und event.json werden geprüft …</p>');
          try{
            await requestJson(`/api/event-structure-changes/${encodeURIComponent(changeId)}/verify-archive`,{method:"POST"});
            clearStructureTaskFromUrl(changeId);
            structureChangeDialog.close();
            await loadEvents({reset:true});
            await refreshGlobalTasks();
            setStatus("Archivänderung geprüft und in SQLite übernommen.",false,true);
          }catch(error){
            button.disabled=false;
            const feedback=document.getElementById("structure-change-verify-feedback");
            if(feedback){
              feedback.className="error-box";
              feedback.textContent=error.message;
            }
            setStatus(error.message,true);
          }
        });
      }else{
        structureChangeBody.innerHTML=preview+`
          <div class="card" style="margin-top:14px"><strong>Archiv · Schritt 1 von 2</strong><p>Bibliothekar erzeugt eine neue event.json unter „Später zuordnen“. Die Kamerabibliothek bleibt read-only.</p></div>
          <div class="edit-actions"><button type="button" id="structure-change-prepare" class="plan-button bk-positive-action" ${blockers.length?"disabled":""}>event.json vorbereiten</button></div>`;
        document.getElementById("structure-change-prepare")?.addEventListener("click",async()=>{
          const input=document.getElementById("structure-change-input").value;
          const inlineError=document.getElementById("structure-change-input-error");
          if(input==="__choose__"){
            if(inlineError){inlineError.textContent="Bitte einen zukünftigen Input-Ordner wählen.";inlineError.hidden=false;}
            return;
          }
          if(inlineError) inlineError.hidden=true;
          try{
            await requestJson(`/api/event-structure-changes/${encodeURIComponent(changeId)}/prepare-archive`,{
              method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({input_path:input})
            });
            await showStructureChange(changeId);
            await refreshGlobalTasks();
          }catch(error){
            if(inlineError){inlineError.textContent=error.message;inlineError.hidden=false;}
          }
        });
      }
    }

    async function showLegacyMaintenance(legacyEventId) {
      if (!legacyMaintenanceDialog.open) legacyMaintenanceDialog.showModal();
      legacyMaintenanceBody.textContent = "Wartungsplan wird geladen …";
      const plan = await requestJson(
        `/api/legacy-multi-backup/${encodeURIComponent(legacyEventId)}/plan`
      );
      const summary = plan.summary || {};
      const blockers = plan.blockers || [];
      const warnings = plan.warnings || [];
      const target = plan.target_event || {};
      const legacy = plan.legacy_event || {};
      legacyMaintenanceSubtitle.textContent =
        `${legacy.name || legacyEventId} → ${target.name || plan.target_event_id || ""}`;

      const operationRows = [...(plan.files || []), ...(plan.assets || [])]
        .filter(item => item.status === "move")
        .map(item => `
          <div style="margin-top:7px">
            <code>${escapeHtml(item.source_relative_path || "")}</code>
            <br><span class="muted">→</span>
            <code>${escapeHtml(item.destination_relative_path || "")}</code>
          </div>`)
        .join("");

      legacyMaintenanceBody.innerHTML = `
        <div class="card">
          <strong>Geprüfter Wartungsplan</strong>
          <div style="margin-top:8px">${Number(summary.camera_file_count || 0)} Kameradateien ·
            ${Number(summary.asset_count || 0)} Zusatzdateien ·
            ${Number(summary.move_count || 0)} Verschiebungen</div>
          <div class="muted" style="margin-top:8px">
            Die 0.27-Zweitstruktur wird erst nach erneuter SHA-256-Prüfung in das kanonische Ereignis übernommen.
            Kein bestehender Zielpfad wird überschrieben.
          </div>
        </div>
        ${blockers.length ? `
          <div class="error-box" style="margin-top:12px">
            <strong>Vereinheitlichung blockiert</strong>
            ${blockers.map(item=>`<div style="margin-top:6px">${escapeHtml(item.message || item.code || "Blocker")}</div>`).join("")}
          </div>` : ""}
        ${warnings.length ? `
          <div class="card" style="margin-top:12px">
            <strong>Hinweise</strong>
            ${warnings.map(item=>`<div style="margin-top:6px">${escapeHtml(item.message || "")}</div>`).join("")}
          </div>` : ""}
        ${operationRows ? `<details class="card" style="margin-top:12px"><summary>Dateipfade anzeigen</summary>${operationRows}</details>` : ""}
        ${summary.ready ? `
          <label style="display:flex;gap:9px;align-items:flex-start;margin-top:15px">
            <input id="legacy-maintenance-confirm" type="checkbox">
            <span>Ich möchte diese geprüfte Legacy-Struktur jetzt in das kanonische Ereignis vereinheitlichen.</span>
          </label>
          <div class="edit-actions">
            <button id="legacy-maintenance-apply" type="button" class="plan-button bk-positive-action" disabled>
              Vereinheitlichung anwenden
            </button>
          </div>` : ""}
      `;

      if (!summary.ready) return;
      const checkbox = document.getElementById("legacy-maintenance-confirm");
      const applyButton = document.getElementById("legacy-maintenance-apply");
      checkbox?.addEventListener("change",()=>{
        applyButton.disabled = !checkbox.checked;
      });
      applyButton?.addEventListener("click", async()=>{
        applyButton.disabled = true;
        legacyMaintenanceBody.insertAdjacentHTML(
          "beforeend",
          '<p class="muted">Quellen werden erneut per SHA-256 geprüft und sicher verschoben …</p>'
        );
        const result = await requestJson(
          `/api/legacy-multi-backup/${encodeURIComponent(legacyEventId)}/apply`,
          {
            method:"POST",
            headers:{"Content-Type":"application/json"},
            body:JSON.stringify({
              plan_token:plan.plan_token,
              confirmation_phrase:plan.apply_confirmation_phrase
            })
          }
        );
        legacyMaintenanceDialog.close();
        await loadEvents({reset:true});
        refreshGlobalTasks();
        setStatus(
          `Legacy-Mehrsicherungsstruktur vereinheitlicht · ${Number(result.moved_file_count || 0)} Dateien verschoben.`,
          false,
          true
        );
      });
    }

    loadJobs().then(async () => {
      const params = new URLSearchParams(location.search);
      const task = params.get("task") || "";
      const jobId = params.get("job") || "";
      if (
        task.startsWith("run:")
        && jobId
      ) {
        const runId = task.slice("run:".length);
        const run = await requestJson(
          `/api/jobs/${encodeURIComponent(jobId)}/sort-runs/${encodeURIComponent(runId)}`
        );
        sortPlanTitle.textContent =
          "Laufender Vorgang";
        sortPlanSubtitle.textContent =
          run.phase || "Sortierlauf";
        sortPlanBody.innerHTML =
          '<div id="sort-run-status"></div>';
        if (!sortPlanDialog.open) {
          sortPlanDialog.showModal();
        }
        renderSortRunProgress(run);
        if (!run.terminal) {
          await pollSortRun(jobId, runId);
        }
      } else if (task.startsWith("structure:")) {
        await showStructureChange(task.slice("structure:".length));
      } else if (task.startsWith("legacy:")) {
        await showLegacyMaintenance(task.slice("legacy:".length));
      } else if (task.startsWith("change:")) {
        const crId = task.slice("change:".length);
        if (!changeRequestDialog.open) changeRequestDialog.showModal();
        await showChangeRequestDetail(crId, {resume:true});
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
          await loadReapplyPlan(
            eventId,
            jobId,
            {
              mandatory: Boolean(target?.mutation_id && target.id === target.mutation_anchor_event_id),
              mutationId: target?.mutation_id || ""
            }
          );
        }
      }
      if (!task) {
        const pendingArchive = await findOpenArchiveChangeRequest();
        if (pendingArchive) {
          if (!changeRequestDialog.open) changeRequestDialog.showModal();
          await showChangeRequestDetail(pendingArchive.id, {resume:true});
        } else {
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
      }
      refreshGlobalTasks();
    }).catch(error => setStatus(error.message,true));
  </script>
</body>
</html>
"""
