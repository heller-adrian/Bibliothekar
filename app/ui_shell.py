from __future__ import annotations

from html import escape


BIBLIOTHEKAR_CSS = r"""
:root {
  --bk-paper: #f4f1e8;
  --bk-paper-2: #ebe6da;
  --bk-surface: #fbf9f3;
  --bk-surface-2: #f0ece2;
  --bk-ink: #122033;
  --bk-muted: #66717e;
  --bk-line: #d9d2c5;
  --bk-red: #db3b3f;
  --bk-blue: #1974c6;
  --bk-yellow: #f3b82f;
  --bk-green: #37ad78;
  --bk-danger: #cf3d45;
  --bk-shadow: 0 10px 30px rgb(18 32 51 / 0.08);
  --bk-radius: 16px;
}

html[data-bk-theme="dark"] {
  --bk-paper: #0c1115;
  --bk-paper-2: #12191e;
  --bk-surface: #171f25;
  --bk-surface-2: #202930;
  --bk-ink: #f4f1e8;
  --bk-muted: #a8b1b9;
  --bk-line: #303b43;
  --bk-red: #ee5155;
  --bk-blue: #4b9be2;
  --bk-yellow: #f5c451;
  --bk-green: #55cb94;
  --bk-danger: #f06a70;
  --bk-shadow: 0 12px 34px rgb(0 0 0 / 0.28);
}

html[data-bk-theme="light"] { color-scheme: light; }
html[data-bk-theme="dark"] { color-scheme: dark; }

/* 0.22.1: alte Seitenvariablen an das gemeinsame Theme anbinden. */
html[data-bk-theme="light"] {
  --background: var(--bk-paper);
  --surface: var(--bk-surface);
  --surface-2: var(--bk-surface-2);
  --surface-3: #e7e1d6;
  --panel-soft: var(--bk-surface-2);
  --border: var(--bk-line);
  --text: var(--bk-ink);
  --muted: var(--bk-muted);
  --accent: var(--bk-blue);
  --success: var(--bk-green);
  --warning: #b98514;
  --danger: var(--bk-danger);
}
html[data-bk-theme="dark"] {
  --background: var(--bk-paper);
  --surface: var(--bk-surface);
  --surface-2: var(--bk-surface-2);
  --surface-3: #28333b;
  --panel-soft: var(--bk-surface-2);
  --border: var(--bk-line);
  --text: var(--bk-ink);
  --muted: var(--bk-muted);
  --accent: var(--bk-blue);
  --success: var(--bk-green);
  --warning: var(--bk-yellow);
  --danger: var(--bk-danger);
}

body[data-bk-area="import"] {
  --bk-area-accent: var(--bk-red);
  --bk-page-bg: #f8efec;
}
body[data-bk-area="workspace"] {
  --bk-area-accent: var(--bk-blue);
  --bk-page-bg: #eef4f8;
}
body[data-bk-area="archive"] {
  --bk-area-accent: var(--bk-yellow);
  --bk-page-bg: #f8f4e8;
}
html[data-bk-theme="dark"] body[data-bk-area="import"] { --bk-page-bg: #120f11; }
html[data-bk-theme="dark"] body[data-bk-area="workspace"] { --bk-page-bg: #0c1217; }
html[data-bk-theme="dark"] body[data-bk-area="archive"] { --bk-page-bg: #14120c; }

html[data-bk-theme] body.bibliothekar-redesign,
html[data-bk-theme] body.bibliothekar-redesign main {
  background: var(--bk-page-bg, var(--bk-paper)) !important;
  color: var(--bk-ink) !important;
}
html[data-bk-theme] body.bibliothekar-redesign::before {
  background: var(--bk-page-bg, var(--bk-paper)) !important;
}

body.bibliothekar-redesign {
  background: var(--bk-page-bg, var(--bk-paper)) !important;
  color: var(--bk-ink) !important;
  min-height: 100vh;
}

body.bibliothekar-redesign::before {
  background: var(--bk-page-bg, var(--bk-paper)) !important;
}

body.bibliothekar-redesign main {
  width: min(1120px, 100%) !important;
  padding-top: 22px !important;
}

body.bibliothekar-redesign .page-intro,
body.bibliothekar-redesign .global-navigation-bar,
body.bibliothekar-redesign .page-navigation {
  display: none !important;
}

body.bibliothekar-redesign .command-header {
  background: transparent !important;
  border: 0 !important;
  box-shadow: none !important;
  padding-top: 0 !important;
}

body.bibliothekar-redesign .command-header .toolbar {
  margin-top: 0 !important;
}

body.bibliothekar-redesign .card,
body.bibliothekar-redesign .job,
body.bibliothekar-redesign .event-card,
body.bibliothekar-redesign .intro,
body.bibliothekar-redesign .selection-bar,
body.bibliothekar-redesign .source-device-card,
body.bibliothekar-redesign .result,
body.bibliothekar-redesign .child-event,
body.bibliothekar-redesign .suggestion-card {
  background: var(--bk-surface) !important;
  border-color: var(--bk-line) !important;
  box-shadow: none !important;
}

body.bibliothekar-redesign .card,
body.bibliothekar-redesign .job,
body.bibliothekar-redesign .event-card,
body.bibliothekar-redesign .intro {
  border-radius: var(--bk-radius) !important;
}

body.bibliothekar-redesign .muted,
body.bibliothekar-redesign .subtitle,
body.bibliothekar-redesign .section-description,
body.bibliothekar-redesign .status-detail,
body.bibliothekar-redesign .job-description,
body.bibliothekar-redesign .job-time,
body.bibliothekar-redesign .event-folder,
body.bibliothekar-redesign .meta,
body.bibliothekar-redesign .path {
  color: var(--bk-muted) !important;
}

body.bibliothekar-redesign button,
body.bibliothekar-redesign select,
body.bibliothekar-redesign input,
body.bibliothekar-redesign textarea {
  background: var(--bk-surface-2) !important;
  color: var(--bk-ink) !important;
  border-color: var(--bk-line) !important;
  box-shadow: none !important;
}

body.bibliothekar-redesign button {
  border-radius: 11px !important;
}

body.bibliothekar-redesign button.primary,
body.bibliothekar-redesign .primary,
body.bibliothekar-redesign .plan-button,
body.bibliothekar-redesign .sort-apply-button {
  background: var(--bk-red) !important;
  border-color: var(--bk-red) !important;
  color: #fff !important;
}

body.bibliothekar-redesign .warning-button {
  border-color: var(--bk-yellow) !important;
  color: var(--bk-ink) !important;
}

body.bibliothekar-redesign #new-event-button {
  background: var(--bk-green) !important;
  border-color: var(--bk-green) !important;
  color: #082419 !important;
}
html[data-bk-theme="dark"] body.bibliothekar-redesign #new-event-button {
  color: #071a12 !important;
}

body.bibliothekar-redesign .status-value,
body.bibliothekar-redesign .success-text,
body.bibliothekar-redesign .badge.success {
  color: var(--bk-green) !important;
}

body.bibliothekar-redesign .badge,
body.bibliothekar-redesign .status-chip {
  border-radius: 999px !important;
}

body.bibliothekar-redesign .progress {
  background: var(--bk-paper-2) !important;
}

body.bibliothekar-redesign .progress > div {
  background: var(--bk-blue) !important;
}

body.bibliothekar-redesign .progress > div.completed {
  background: var(--bk-green) !important;
}

body.bibliothekar-redesign #global-task-fab,
body.bibliothekar-redesign > .global-task-panel {
  display: none !important;
}

html[data-bk-theme="light"] body.bibliothekar-redesign .command-header,
html[data-bk-theme="light"] body.bibliothekar-redesign .workspace-layout,
html[data-bk-theme="light"] body.bibliothekar-redesign .day-list,
html[data-bk-theme="light"] body.bibliothekar-redesign .events-list,
html[data-bk-theme="light"] body.bibliothekar-redesign .archive-list {
  color: var(--bk-ink) !important;
}
html[data-bk-theme="light"] body.bibliothekar-redesign .day-card,
html[data-bk-theme="light"] body.bibliothekar-redesign .tree,
html[data-bk-theme="light"] body.bibliothekar-redesign .preview,
html[data-bk-theme="light"] body.bibliothekar-redesign .selection-bar,
html[data-bk-theme="light"] body.bibliothekar-redesign .toolbar,
html[data-bk-theme="light"] body.bibliothekar-redesign .event-card {
  background: var(--bk-surface) !important;
  color: var(--bk-ink) !important;
  border-color: var(--bk-line) !important;
}
html[data-bk-theme="light"] body.bibliothekar-redesign .day-card.selected {
  background: #e8f1f8 !important;
  border-color: var(--bk-blue) !important;
}
html[data-bk-theme="light"] body.bibliothekar-redesign .planned-check {
  background: #fff !important;
  border-color: var(--bk-line) !important;
}

/* Gemeinsamer App-Rahmen */
.bk-shell {
  position: sticky;
  top: 0;
  z-index: 3000;
  display: grid;
  grid-template-columns: minmax(180px, 0.75fr) minmax(420px, 1.8fr) minmax(190px, 0.8fr);
  align-items: end;
  gap: 18px;
  min-height: 78px;
  padding: 14px max(18px, calc((100vw - 1120px) / 2)) 0;
  background: #15222c;
  border-bottom: 1px solid #26343e;
  color: #f8f4e9;
}

.bk-brand {
  display: flex;
  align-items: center;
  gap: 12px;
  align-self: center;
  min-width: 0;
  padding-bottom: 15px;
  color: #fff;
  text-decoration: none;
  font-size: 1.25rem;
  font-weight: 800;
  letter-spacing: -0.025em;
}

.bk-mark {
  position: relative;
  width: 29px;
  height: 29px;
  flex: 0 0 29px;
}
.bk-mark span {
  position: absolute;
  width: 17px;
  height: 17px;
}
.bk-mark .y { left: 0; top: 0; background: var(--bk-yellow); }
.bk-mark .r { left: 0; bottom: 0; background: var(--bk-red); }
.bk-mark .b { right: 0; bottom: 2px; background: var(--bk-blue); }

.bk-tabs {
  display: flex;
  align-items: flex-end;
  min-width: 0;
  overflow: visible;
}
.bk-tab {
  --bk-tab-accent: #87939a;
  position: relative;
  z-index: 1;
  flex: 1 1 0;
  min-width: 132px;
  max-width: 224px;
  height: 52px;
  margin-left: -5px;
  padding: 0 22px;
  border: 0;
  background: transparent;
  color: #17232d;
  text-align: center;
  text-decoration: none;
  font-weight: 780;
  white-space: nowrap;
  display: grid;
  place-items: center;
}
.bk-tab:first-child { margin-left: 0; }
.bk-tab::before {
  content: "";
  position: absolute;
  inset: 0;
  z-index: -1;
  background: #d5d8d7;
  box-shadow: inset 0 4px 0 var(--bk-tab-accent);
  clip-path: polygon(10px 0, calc(100% - 10px) 0, 100% 100%, 0 100%);
}
.bk-tab[data-area="import"] { --bk-tab-accent: var(--bk-red); }
.bk-tab[data-area="workspace"] { --bk-tab-accent: var(--bk-blue); }
.bk-tab[data-area="archive"] { --bk-tab-accent: var(--bk-yellow); }
.bk-tab-label { display: inline-block; }
.bk-tab-mobile-label { display: none; }
.bk-tab.active {
  z-index: 4;
  height: 59px;
  padding-top: 4px;
  color: var(--bk-ink);
}
.bk-tab.active::before {
  background: var(--bk-page-bg, var(--bk-paper));
  box-shadow: inset 0 5px 0 var(--bk-tab-accent), 0 2px 0 var(--bk-page-bg, var(--bk-paper));
}
.bk-tab:hover:not(.active)::before {
  background: #e2e2dd;
}

.bk-shell-actions {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 9px;
  align-self: center;
  padding-bottom: 14px;
}
.bk-shell-button {
  position: relative;
  min-height: 40px;
  border: 1px solid #40505a;
  border-radius: 999px;
  background: #1d2c36;
  color: #fff;
  padding: 8px 13px;
  font: inherit;
  cursor: pointer;
}
.bk-shell-button:hover { border-color: #7e909c; }
.bk-task-button { display: inline-flex; align-items: center; gap: 8px; }
.bk-task-dot {
  width: 18px; height: 18px; border-radius: 50%;
  display: inline-flex; align-items: center; justify-content: center;
  background: var(--bk-green); color: #10251b; font-size: .72rem; font-weight: 900;
}
.bk-task-count {
  min-width: 20px; height: 20px; border-radius: 999px;
  display: inline-flex; align-items: center; justify-content: center;
  background: var(--bk-yellow); color: #202020; padding: 0 6px;
  font-size: .72rem; font-weight: 850;
}
.bk-menu-button {
  width: 42px;
  padding: 8px 0;
  font-size: 1.18rem;
}
.bk-menu,
.bk-task-panel {
  position: absolute;
  right: 0;
  top: calc(100% - 6px);
  width: min(300px, calc(100vw - 28px));
  padding: 7px;
  border: 1px solid var(--bk-line);
  border-radius: 13px;
  background: var(--bk-surface);
  color: var(--bk-ink);
  box-shadow: var(--bk-shadow);
}
.bk-menu[hidden],
.bk-task-panel[hidden] { display: none !important; }
.bk-menu {
  display: grid;
  gap: 2px;
}
.bk-menu button {
  width: 100%;
  min-height: 42px;
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 0 !important;
  border: 0 !important;
  border-radius: 8px !important;
  background: transparent !important;
  color: var(--bk-ink) !important;
  text-align: left;
  padding: 9px 10px !important;
}
.bk-menu button:hover { background: var(--bk-surface-2) !important; }
.bk-menu-separator {
  height: 1px;
  background: var(--bk-line);
  margin: 4px 7px;
}


.bk-page-heading {
  width: min(1120px, calc(100% - 36px));
  margin: 24px auto 4px;
}
.bk-page-heading h1 {
  margin: 0;
  color: var(--bk-ink);
  font-size: clamp(2rem, 4.5vw, 2.85rem);
  line-height: 1;
  letter-spacing: -0.045em;
}
.bk-page-heading p {
  margin: 9px 0 0;
  color: var(--bk-muted);
  max-width: 760px;
  line-height: 1.45;
}

.bk-workspace-subnav {
  width: min(1120px, calc(100% - 36px));
  margin: 18px auto -2px;
  display: flex;
  gap: 6px;
  border-bottom: 1px solid var(--bk-line);
}
.bk-workspace-subnav a {
  position: relative;
  padding: 10px 14px;
  color: var(--bk-muted);
  text-decoration: none;
  font-weight: 720;
}
.bk-workspace-subnav a.active { color: var(--bk-ink); }
.bk-workspace-subnav a.active::after {
  content: "";
  position: absolute;
  height: 3px;
  left: 12px;
  right: 12px;
  bottom: -2px;
  background: var(--bk-blue);
  border-radius: 3px;
}

.bk-dialog {
  width: min(560px, calc(100vw - 28px));
  border: 1px solid var(--bk-line);
  border-radius: 18px;
  background: var(--bk-surface);
  color: var(--bk-ink);
  padding: 0;
  box-shadow: var(--bk-shadow);
}
.bk-dialog::backdrop { background: rgb(0 0 0 / .52); }
.bk-dialog-body { padding: 20px; }
.bk-dialog-head {
  display: flex; justify-content: space-between; align-items: start; gap: 16px;
  margin-bottom: 18px;
}
.bk-dialog-head h2 { margin: 0; }
.bk-dialog-close {
  width: 38px; min-height: 38px; border-radius: 50%;
  padding: 0;
}
.bk-settings-group {
  padding: 14px 0;
  border-top: 1px solid var(--bk-line);
}
.bk-settings-group:first-of-type { border-top: 0; }
.bk-choice-row { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 9px; }
.bk-choice-row button.active {
  background: var(--bk-ink) !important;
  color: var(--bk-paper) !important;
  border-color: var(--bk-ink) !important;
}
.bk-language-note {
  margin-top: 9px; color: var(--bk-muted); font-size: .9rem;
}

.bk-ai-launcher {
  position: fixed;
  right: 18px;
  bottom: 18px;
  z-index: 2800;
  min-height: 46px;
  border: 1px solid #0d61ab;
  border-radius: 999px;
  background: var(--bk-blue);
  color: #fff;
  padding: 10px 15px;
  font: inherit;
  font-weight: 760;
  box-shadow: 0 10px 30px rgb(0 0 0 / .18);
  cursor: pointer;
}
.bk-ai-panel {
  position: fixed;
  right: 18px;
  bottom: 74px;
  z-index: 2799;
  width: min(390px, calc(100vw - 36px));
  border: 1px solid var(--bk-line);
  border-radius: 16px;
  background: var(--bk-surface);
  color: var(--bk-ink);
  padding: 15px;
  box-shadow: var(--bk-shadow);
}
.bk-ai-panel[hidden] { display: none !important; }
.bk-ai-panel strong { display: block; margin-bottom: 7px; }
.bk-ai-panel p { margin: 0; color: var(--bk-muted); line-height: 1.45; }

.bk-help {
  position: relative;
  width: 25px !important;
  min-width: 25px !important;
  min-height: 25px !important;
  height: 25px !important;
  border-radius: 50% !important;
  padding: 0 !important;
  background: var(--bk-muted) !important;
  border: 0 !important;
  color: var(--bk-paper) !important;
  font-size: .8rem !important;
  font-weight: 850;
}
.bk-help::after {
  content: attr(data-help);
  position: absolute;
  left: 50%;
  top: calc(100% + 8px);
  transform: translateX(-50%);
  width: min(300px, 80vw);
  padding: 9px 11px;
  border-radius: 10px;
  background: var(--bk-ink);
  color: var(--bk-paper);
  font-size: .82rem;
  line-height: 1.35;
  font-weight: 500;
  text-align: left;
  box-shadow: var(--bk-shadow);
  opacity: 0;
  pointer-events: none;
  transition: opacity .14s ease;
  z-index: 100;
}
.bk-help:hover::after,
.bk-help:focus-visible::after { opacity: 1; }


/* Importseite */
body.bibliothekar-redesign .import-panel {
  padding: 20px !important;
}
.bk-import-head {
  display: flex;
  align-items: center;
  gap: 9px;
  margin-bottom: 5px;
}
.bk-import-head h2 { margin: 0; }
.bk-source-picker {
  position: relative;
  width: fit-content;
  min-width: 245px;
  margin: 14px 0 18px;
}
.bk-source-trigger {
  width: 245px;
  min-height: 72px !important;
  display: grid !important;
  grid-template-columns: 48px minmax(0,1fr) 22px;
  align-items: center;
  gap: 11px;
  padding: 10px 12px !important;
  border: 1px solid var(--bk-line) !important;
  border-radius: 12px !important;
  background: var(--bk-surface) !important;
  color: var(--bk-ink) !important;
  text-align: left;
}
.bk-source-trigger:hover {
  border-color: var(--bk-blue) !important;
}
.bk-source-current-icon,
.bk-source-option-icon {
  display: grid;
  place-items: center;
  color: var(--bk-ink);
}
.bk-source-current-icon {
  width: 44px;
  height: 44px;
  border-radius: 10px;
  background: var(--bk-surface-2);
}
.bk-source-current-icon svg,
.bk-source-option-icon svg,
.bk-action-tile svg,
.bk-status-icon svg {
  width: 24px;
  height: 24px;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.7;
  stroke-linecap: round;
  stroke-linejoin: round;
}
.bk-source-current-copy {
  display: grid;
  gap: 3px;
}
.bk-source-current-copy strong { font-size: .96rem; }
.bk-source-current-copy small { color: var(--bk-muted); font-size: .78rem; }
.bk-source-chevron {
  color: var(--bk-muted);
  font-size: 1.1rem;
  text-align: center;
}
.bk-source-menu {
  position: absolute;
  z-index: 120;
  top: calc(100% + 7px);
  left: 0;
  width: 330px;
  padding: 7px;
  border: 1px solid var(--bk-line);
  border-radius: 12px;
  background: var(--bk-surface);
  box-shadow: var(--bk-shadow);
}
.bk-source-menu[hidden] { display: none !important; }
.bk-source-option {
  width: 100%;
  min-height: 58px !important;
  display: grid !important;
  grid-template-columns: 42px 1fr;
  align-items: center;
  gap: 10px;
  margin: 0 !important;
  padding: 8px 9px !important;
  border: 0 !important;
  border-radius: 8px !important;
  background: transparent !important;
  color: var(--bk-ink) !important;
  text-align: left;
}
.bk-source-option + .bk-source-option { margin-top: 2px !important; }
.bk-source-option:hover,
.bk-source-option.active { background: var(--bk-surface-2) !important; }
.bk-source-option span:last-child { display: grid; gap: 2px; }
.bk-source-option small { color: var(--bk-muted); font-size: .78rem; }

.bk-status-grid {
  gap: 12px !important;
}
.bk-status-card {
  display: grid !important;
  grid-template-columns: 46px minmax(0,1fr);
  align-items: center;
  gap: 13px;
  min-height: 104px;
  padding: 15px !important;
}
.bk-status-icon {
  width: 42px;
  height: 42px;
  display: grid;
  place-items: center;
  border-radius: 10px;
  background: var(--bk-surface-2);
  color: var(--bk-ink);
}
.bk-status-card:nth-child(1) .bk-status-icon { color: var(--bk-red); }
.bk-status-card:nth-child(2) .bk-status-icon { color: var(--bk-blue); }
.bk-status-card:nth-child(3) .bk-status-icon { color: #b98612; }

body.bibliothekar-redesign .sd-actions {
  grid-template-columns: minmax(260px,1fr) repeat(3, minmax(142px, 165px)) !important;
  align-items: stretch !important;
  gap: 9px !important;
}
body.bibliothekar-redesign .sd-actions .mount-state {
  margin: 0 !important;
  min-height: 72px !important;
  display: flex;
  align-items: center;
}
.bk-action-tile {
  min-height: 72px !important;
  padding: 10px 12px !important;
  display: flex !important;
  flex-direction: column;
  align-items: flex-start !important;
  justify-content: center;
  gap: 8px;
  border-radius: 10px !important;
  font-weight: 760;
  text-align: left;
}
.bk-action-tile svg {
  width: 21px;
  height: 21px;
}
body.bibliothekar-redesign .bk-action-mount {
  background: var(--bk-surface-2) !important;
  color: var(--bk-ink) !important;
  border-color: var(--bk-line) !important;
}
body.bibliothekar-redesign .bk-action-save {
  background: var(--bk-green) !important;
  color: #082419 !important;
  border-color: var(--bk-green) !important;
}
body.bibliothekar-redesign .bk-action-eject {
  background: #d8d5cd !important;
  color: #1d252b !important;
  border-color: #cbc5ba !important;
}
html[data-bk-theme="dark"] body.bibliothekar-redesign .bk-action-eject {
  background: #303940 !important;
  color: #eef1ee !important;
  border-color: #3b464e !important;
}
body.bibliothekar-redesign .bk-action-tile:disabled {
  opacity: .48 !important;
}
body.bibliothekar-redesign .other-source-panel {
  margin-top: 10px !important;
}
body.bibliothekar-redesign .other-source-panel > summary {
  display: none !important;
}
body.bibliothekar-redesign #sd-card-status {
  margin: 0 0 12px !important;
  padding: 11px 14px !important;
  border-radius: 10px !important;
}
.bk-menu-icon {
  width: 18px;
  height: 18px;
  display: inline-grid;
  place-items: center;
  flex: 0 0 18px;
}
.bk-menu-icon svg {
  width: 18px;
  height: 18px;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.7;
  stroke-linecap: round;
  stroke-linejoin: round;
}
.bk-source-mode-note {
  margin: -5px 0 5px;
  color: var(--bk-muted);
  font-size: .9rem;
}
.bk-source-pane {
  padding: 4px 0 2px;
}
.bk-source-pane > h3:first-child {
  margin-top: 0;
}

body.bibliothekar-redesign .jobs {
  gap: 9px !important;
}
body.bibliothekar-redesign .job {
  position: relative;
  display: grid !important;
  grid-template-columns: 68px minmax(0,1fr);
  column-gap: 14px;
  padding: 12px 14px !important;
}
body.bibliothekar-redesign .job > *:not(.bk-job-thumb) {
  grid-column: 2;
}
.bk-job-thumb {
  grid-column: 1;
  grid-row: 1 / span 6;
  width: 68px;
  height: 68px;
  border-radius: 10px;
  overflow: hidden;
  background: var(--bk-surface-2);
  border: 1px solid var(--bk-line);
  display: grid;
  place-items: center;
  color: var(--bk-muted);
  font-size: 1.35rem;
}
.bk-job-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
body.bibliothekar-redesign .job-description {
  display: none;
}
body.bibliothekar-redesign .job .message {
  margin-top: 6px !important;
}
body.bibliothekar-redesign .job details {
  margin-top: 5px !important;
}

@media (max-width: 820px) {
  .bk-shell {
    min-height: 78px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    padding: 10px 12px;
  }
  .bk-brand {
    padding-bottom: 0;
    font-size: 1.08rem;
  }
  .bk-mark {
    transform: scale(.9);
    transform-origin: left center;
  }
  .bk-shell-actions {
    padding-bottom: 0;
    gap: 6px;
  }
  .bk-task-label { display: none; }
  .bk-task-button { padding: 8px 9px; }
  .bk-menu-button { width: 42px; min-width: 42px; }

  .bk-menu,
  .bk-task-panel {
    position: fixed;
    z-index: 5600;
    top: 86px;
    right: 12px;
    left: 12px;
    width: auto;
    max-height: calc(100dvh - 104px);
    overflow: auto;
  }

  .bk-page-heading {
    width: auto;
    margin: 18px 16px 6px;
  }
  .bk-page-heading h1 {
    font-size: clamp(1.9rem, 9vw, 2.35rem);
  }
  .bk-page-heading p {
    margin-top: 7px;
    font-size: .95rem;
  }

  .bk-workspace-subnav {
    width: auto;
    margin: 10px 16px 0;
  }

  body.bibliothekar-redesign main {
    width: 100% !important;
    padding: 14px 16px 94px !important;
  }

  body.bibliothekar-redesign .grid.summary {
    grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
  }

  body.bibliothekar-redesign .selection-bar {
    position: static !important;
    padding: 12px !important;
  }
  body.bibliothekar-redesign .selection-actions {
    display: grid !important;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    width: 100%;
    gap: 8px;
  }
  body.bibliothekar-redesign .selection-actions button {
    min-height: 54px !important;
    padding: 9px 10px !important;
    font-size: .95rem;
  }

  .bk-source-picker {
    width: 100%;
    min-width: 0;
  }
  .bk-source-trigger {
    width: 100%;
    min-height: 64px !important;
  }
  .bk-source-menu {
    width: 100%;
    max-width: 100%;
  }
  body.bibliothekar-redesign .sd-actions {
    grid-template-columns: 1fr 1fr !important;
    gap: 8px !important;
  }
  body.bibliothekar-redesign .sd-actions .mount-state {
    grid-column: 1 / -1;
    min-height: 62px !important;
  }
  .bk-action-tile {
    min-height: 60px !important;
    flex-direction: row;
    align-items: center !important;
    justify-content: flex-start;
    gap: 9px;
    font-size: .92rem;
  }
  body.bibliothekar-redesign .bk-action-eject {
    grid-column: 1 / -1;
  }

  .bk-dialog {
    width: min(560px, calc(100vw - 24px));
    max-height: calc(100dvh - 28px);
    overflow: auto;
  }
}

.bk-mobile-nav-toggle {
  display: none;
}

@media (max-width: 700px) and (orientation: portrait) {
  .bk-tabs {
    --bk-mobile-rail-top: 122px;
    position: fixed;
    z-index: 4200;
    top: var(--bk-mobile-rail-top);
    right: 0;
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    overflow: visible;
    transition: transform .18s ease;
  }

  .bk-tab {
    width: 48px;
    min-width: 48px;
    max-width: 48px;
    height: 94px;
    min-height: 94px;
    margin: -4px 0 0 !important;
    padding: 0 !important;
    display: grid;
    place-items: center;
    overflow: visible;
  }
  .bk-tab::before {
    clip-path: polygon(9px 0, 100% 0, 100% 100%, 9px 100%, 0 calc(100% - 9px), 0 9px);
    box-shadow: inset 4px 0 0 var(--bk-tab-accent);
  }
  .bk-tab.active {
    width: 54px;
    min-width: 54px;
    max-width: 54px;
    height: 100px;
    min-height: 100px;
    transform: translateX(-2px);
  }
  .bk-tab.active::before {
    background: var(--bk-page-bg, var(--bk-paper));
    box-shadow: inset 5px 0 0 var(--bk-tab-accent);
  }
  .bk-tab-label { display: none; }
  .bk-tab-mobile-label {
    display: inline-block;
    writing-mode: vertical-rl;
    text-orientation: mixed;
    transform: rotate(180deg);
    font-size: .72rem;
    line-height: 1;
    letter-spacing: .02em;
  }

  .bk-mobile-nav-toggle {
    position: fixed;
    z-index: 4300;
    top: 88px;
    right: 0;
    display: grid;
    place-items: center;
    width: 28px;
    min-width: 28px;
    height: 31px;
    min-height: 31px;
    padding: 0 !important;
    border-radius: 10px 0 0 10px !important;
    background: #15222c !important;
    color: #fff !important;
    border: 1px solid #40505a !important;
    border-right: 0 !important;
    font-size: 1rem;
  }

  body.bk-mobile-nav-collapsed .bk-tabs {
    transform: translateX(40px);
  }
  body.bk-mobile-nav-collapsed .bk-ai-launcher {
    transform: translateX(40px);
  }

  .bk-ai-launcher {
    top: 414px;
    right: 0;
    bottom: auto;
    width: 48px;
    min-width: 48px;
    height: 70px;
    min-height: 70px;
    padding: 0 !important;
    display: grid;
    place-items: center;
    gap: 0;
    border-radius: 10px 0 0 10px;
    border: 1px solid #40505a;
    border-right: 0;
    background: #15222c;
    color: #fff;
    box-shadow: none;
    transition: transform .18s ease;
  }
  .bk-ai-launcher span {
    display: block;
    font-size: 0;
  }
  .bk-ai-launcher span::after {
    content: "KI";
    display: block;
    writing-mode: vertical-rl;
    transform: rotate(180deg);
    font-size: .72rem;
    font-weight: 800;
    letter-spacing: .05em;
  }

  .bk-ai-panel {
    position: fixed;
    z-index: 5100;
    top: 78px;
    right: 0;
    bottom: 0;
    left: 0;
    width: auto;
    border-radius: 0;
    border-left: 0;
    border-right: 0;
    border-bottom: 0;
    padding: 18px 16px;
    overflow: auto;
    background: var(--bk-page-bg, var(--bk-paper));
  }
  .bk-ai-panel-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 10px;
  }
  .bk-ai-close {
    width: 38px;
    min-width: 38px;
    min-height: 38px;
    padding: 0 !important;
    border-radius: 50% !important;
  }

  .bk-menu,
  .bk-task-panel {
    z-index: 5700;
  }

  body.bibliothekar-redesign .workspace-layout {
    display: block !important;
  }
  body.bibliothekar-redesign .preview {
    position: static !important;
    margin-top: 14px;
  }

  body.bibliothekar-redesign .job {
    grid-template-columns: 54px minmax(0,1fr) !important;
    column-gap: 10px !important;
  }
  .bk-job-thumb {
    width: 54px;
    height: 54px;
  }

  .bk-status-grid {
    grid-template-columns: 1fr !important;
  }
  .bk-status-card {
    min-height: 82px;
  }

  body.bibliothekar-redesign section {
    scroll-margin-top: 88px;
  }
}

@media (max-width: 430px) {
  .bk-brand span:last-child { font-size: 1.02rem; }
  .bk-task-button { min-width: 70px; }
  .bk-source-current-copy small { font-size: .72rem; }
  body.bibliothekar-redesign .selection-actions {
    grid-template-columns: 1fr 1fr;
  }
}
"""


BIBLIOTHEKAR_JS = r"""
(() => {
  const root = document.documentElement;
  const stored = localStorage.getItem("bibliothekar-theme") || "light";

  function applyTheme(choice) {
    const resolved = choice === "system"
      ? (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light")
      : choice;
    root.dataset.bkTheme = resolved;
    root.dataset.bkThemeChoice = choice;
    document.querySelectorAll("[data-bk-theme-choice]").forEach(button => {
      button.classList.toggle("active", button.dataset.bkThemeChoice === choice);
    });
  }

  applyTheme(stored);
  matchMedia("(prefers-color-scheme: dark)").addEventListener?.("change", () => {
    if ((localStorage.getItem("bibliothekar-theme") || "light") === "system") applyTheme("system");
  });

  document.querySelectorAll("[data-bk-theme-choice]").forEach(button => {
    button.addEventListener("click", () => {
      const choice = button.dataset.bkThemeChoice;
      localStorage.setItem("bibliothekar-theme", choice);
      applyTheme(choice);
    });
  });

  const menuButton = document.getElementById("bk-menu-button");
  const menu = document.getElementById("bk-menu");
  const tasksButton = document.getElementById("bk-task-button");
  const taskPanel = document.getElementById("bk-task-panel");

  function closePopovers(except) {
    if (except !== menu) menu?.setAttribute("hidden", "");
    if (except !== taskPanel) taskPanel?.setAttribute("hidden", "");
  }

  menuButton?.addEventListener("click", (event) => {
    event.stopPropagation();
    const willOpen = menu?.hasAttribute("hidden");
    closePopovers(willOpen ? menu : null);
    if (willOpen) menu?.removeAttribute("hidden"); else menu?.setAttribute("hidden", "");
  });

  tasksButton?.addEventListener("click", (event) => {
    event.stopPropagation();
    const willOpen = taskPanel?.hasAttribute("hidden");
    closePopovers(willOpen ? taskPanel : null);
    if (willOpen) taskPanel?.removeAttribute("hidden"); else taskPanel?.setAttribute("hidden", "");
  });

  document.addEventListener("click", (event) => {
    if (!event.target.closest(".bk-shell-actions")) closePopovers(null);
  });

  function openDialog(id) {
    closePopovers(null);
    document.getElementById(id)?.showModal?.();
  }
  document.querySelector("[data-bk-open-settings]")?.addEventListener("click", () => openDialog("bk-settings-dialog"));
  document.querySelector("[data-bk-open-library]")?.addEventListener("click", () => openDialog("bk-library-dialog"));
  document.querySelector("[data-bk-open-about]")?.addEventListener("click", () => openDialog("bk-about-dialog"));
  document.querySelectorAll("[data-bk-dialog-close]").forEach(button => {
    button.addEventListener("click", () => button.closest("dialog")?.close());
  });

  const mobileNavToggle = document.getElementById("bk-mobile-nav-toggle");
  const mobileNavStored = localStorage.getItem("bibliothekar-mobile-nav-collapsed") === "1";
  if (mobileNavStored) document.body.classList.add("bk-mobile-nav-collapsed");

  const syncMobileNavToggle = () => {
    if (!mobileNavToggle) return;
    const collapsed = document.body.classList.contains("bk-mobile-nav-collapsed");
    mobileNavToggle.textContent = collapsed ? "‹" : "›";
    mobileNavToggle.setAttribute(
      "aria-label",
      collapsed ? "Seitennavigation einblenden" : "Seitennavigation ausblenden"
    );
  };
  syncMobileNavToggle();

  mobileNavToggle?.addEventListener("click", () => {
    document.body.classList.toggle("bk-mobile-nav-collapsed");
    const collapsed = document.body.classList.contains("bk-mobile-nav-collapsed");
    localStorage.setItem("bibliothekar-mobile-nav-collapsed", collapsed ? "1" : "0");
    syncMobileNavToggle();
  });

  const aiButton = document.getElementById("bk-ai-launcher");
  const aiPanel = document.getElementById("bk-ai-panel");
  const aiClose = document.getElementById("bk-ai-close");

  const setAiOpen = (open) => {
    if (!aiPanel || !aiButton) return;
    if (open) aiPanel.removeAttribute("hidden"); else aiPanel.setAttribute("hidden", "");
    aiButton.setAttribute("aria-expanded", open ? "true" : "false");
  };
  aiButton?.addEventListener("click", () => setAiOpen(aiPanel?.hasAttribute("hidden")));
  aiClose?.addEventListener("click", () => setAiOpen(false));


  // Quellenwahl 0.22.1: eine aktive Quelle, Auswahl über kompaktes Popover.
  const sourcePicker = document.getElementById("bk-source-picker");
  if (sourcePicker) {
    const trigger = document.getElementById("bk-source-trigger");
    const sourceMenu = document.getElementById("bk-source-menu");
    const currentLabel = document.getElementById("bk-source-current-label");
    const currentIcon = document.getElementById("bk-source-current-icon");
    const otherPanel = document.querySelector(".other-source-panel");
    const icons = {
      sd: '<svg viewBox="0 0 24 24"><path d="M7 3h8l3 3v15H7z"/><path d="M10 3v5h5V3M10 13h5M10 16h5"/></svg>',
      drive: '<svg viewBox="0 0 24 24"><rect x="3" y="6" width="18" height="12" rx="2"/><path d="M6 14h12M7 10h.01M10 10h.01"/></svg>',
      folder: '<svg viewBox="0 0 24 24"><path d="M3 7h7l2 2h9v10H3z"/><path d="M3 7V5h7l2 2"/></svg>'
    };
    const labels = {
      sd: "SD-Karte",
      drive: "Laufwerk",
      folder: "Ordner / Sicherung"
    };

    const setSourceMode = (mode) => {
      sourceMenu?.querySelectorAll("[data-source-mode]").forEach(button => {
        button.classList.toggle("active", button.dataset.sourceMode === mode);
      });
      if (currentLabel) currentLabel.textContent = labels[mode] || labels.sd;
      if (currentIcon) currentIcon.innerHTML = icons[mode] || icons.sd;
      sourceMenu?.setAttribute("hidden", "");
      trigger?.setAttribute("aria-expanded", "false");

      document.querySelectorAll("[data-source-pane]").forEach(pane => {
        pane.hidden = pane.dataset.sourcePane !== mode;
      });

      if (mode === "sd") {
        if (otherPanel) otherPanel.open = false;
      } else {
        if (otherPanel) otherPanel.open = true;
        const target = mode === "drive"
          ? document.getElementById("device-select")
          : document.getElementById("folder-root-select");
        setTimeout(() => target?.scrollIntoView({behavior:"smooth", block:"center"}), 30);
      }
    };

    trigger?.addEventListener("click", (event) => {
      event.stopPropagation();
      const opens = sourceMenu?.hasAttribute("hidden");
      if (opens) sourceMenu?.removeAttribute("hidden"); else sourceMenu?.setAttribute("hidden", "");
      trigger.setAttribute("aria-expanded", opens ? "true" : "false");
    });
    sourceMenu?.querySelectorAll("[data-source-mode]").forEach(button => {
      button.addEventListener("click", () => setSourceMode(button.dataset.sourceMode));
    });
    document.addEventListener("click", (event) => {
      if (!event.target.closest("#bk-source-picker")) {
        sourceMenu?.setAttribute("hidden", "");
        trigger?.setAttribute("aria-expanded", "false");
      }
    });
    setSourceMode("sd");
  }

  async function refreshTasks() {
    const countNode = document.getElementById("bk-task-count");
    const panel = document.getElementById("bk-task-panel");
    try {
      const response = await fetch("/api/tasks", {cache: "no-store"});
      if (!response.ok) throw new Error();
      const data = await response.json();
      const tasks = data.tasks || [];
      const count = Number(data.count || 0);
      if (countNode) countNode.textContent = String(count);
      if (panel) {
        panel.innerHTML = count
          ? '<strong style="display:block;padding:7px 9px">Offene Aufgaben · ' + count + '</strong>' +
            tasks.map(task => '<a class="bk-task-entry" href="' +
              String(task.href || "/events").replaceAll("&", "&amp;").replaceAll('"', "&quot;") +
              '" style="display:block;padding:10px;border-radius:10px;color:inherit;text-decoration:none"><strong style="display:block">' +
              String(task.title || "Aufgabe").replaceAll("<", "&lt;") +
              '</strong><span style="color:var(--bk-muted);font-size:.9rem">' +
              String(task.detail || "").replaceAll("<", "&lt;") +
              '</span></a>').join("")
          : '<div style="padding:10px"><strong>Keine offenen Aufgaben</strong><div style="color:var(--bk-muted);margin-top:5px">Alles erledigt.</div></div>';
      }
    } catch (_) {
      if (countNode) countNode.textContent = "–";
    }
  }
  refreshTasks();
  setInterval(refreshTasks, 30000);

  fetch("/api/health", {cache: "no-store"}).then(r => r.ok ? r.json() : null).then(data => {
    if (!data) return;
    document.querySelectorAll("[data-bk-version]").forEach(node => node.textContent = data.version || "");
  }).catch(() => {});
})();
"""


def _shell_markup(active_area: str, subarea: str | None) -> str:
    active = active_area if active_area in {"import", "workspace", "archive"} else "import"
    heading_map = {
        ("import", None): (
            "Import & Prüfung",
            "Quellen einlesen, sicher prüfen und für den Arbeitsbereich vorbereiten.",
        ),
        ("workspace", "captures"): (
            "Aufnahmen",
            "Freie Aufnahmen ordnen und Ereignisse aus dem Arbeitsbestand bilden.",
        ),
        ("workspace", "events"): (
            "Ereignisse",
            "Geplante, angewendete und archivierte Ereignisse verwalten.",
        ),
        ("archive", None): (
            "Archiv",
            "Archivierung prüfen, abschließen und spätere Änderungen nachvollziehen.",
        ),
    }
    heading_title, heading_subtitle = heading_map.get(
        (active, subarea),
        heading_map.get((active, None), ("Bibliothekar", "")),
    )
    def tab(area: str, href: str, label: str, mobile_label: str) -> str:
        klass = "bk-tab active" if area == active else "bk-tab"
        return (
            f'<a class="{klass}" data-area="{area}" href="{href}">'
            f'<span class="bk-tab-label">{escape(label)}</span>'
            f'<span class="bk-tab-mobile-label">{escape(mobile_label)}</span>'
            f'</a>'
        )

    subnav = ""
    if active == "workspace":
        subnav = f"""
<div class="bk-workspace-subnav" aria-label="Arbeitsbereich">
  <a href="/workspace" class="{'active' if subarea == 'captures' else ''}">Aufnahmen</a>
  <a href="/events" class="{'active' if subarea == 'events' else ''}">Ereignisse</a>
</div>
"""

    heading = f"""
<section class="bk-page-heading">
  <h1>{escape(heading_title)}</h1>
  <p>{escape(heading_subtitle)}</p>
</section>
"""

    return f"""
<header class="bk-shell">
  <a class="bk-brand" href="/" aria-label="Bibliothekar Startseite">
    <span class="bk-mark" aria-hidden="true"><span class="y"></span><span class="r"></span><span class="b"></span></span>
    <span>Bibliothekar</span>
  </a>

  <nav class="bk-tabs" aria-label="Hauptbereiche">
    {tab('import', '/', 'Import & Prüfung', 'Import')}
    {tab('workspace', '/workspace', 'Arbeitsbereich', 'Arbeitsbereich')}
    {tab('archive', '/transfer', 'Archiv', 'Archiv')}
  </nav>

  <div class="bk-shell-actions">
    <button id="bk-task-button" class="bk-shell-button bk-task-button" type="button">
      <span class="bk-task-dot">✓</span>
      <span class="bk-task-label">Aufgaben</span>
      <span id="bk-task-count" class="bk-task-count">0</span>
    </button>
    <button id="bk-menu-button" class="bk-shell-button bk-menu-button" type="button" aria-label="Menü">☰</button>

    <div id="bk-task-panel" class="bk-task-panel" hidden></div>

    <div id="bk-menu" class="bk-menu" hidden>
      <button type="button" data-bk-open-settings>
        <span class="bk-menu-icon" aria-hidden="true"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="3"/><path d="M19 12a7 7 0 0 0-.1-1l2-1.6-2-3.4-2.4 1a8 8 0 0 0-1.7-1L14.5 3h-5L9.2 6a8 8 0 0 0-1.7 1L5 6 3 9.4 5.1 11a7 7 0 0 0 0 2L3 14.6 5 18l2.5-1a8 8 0 0 0 1.7 1l.3 3h5l.3-3a8 8 0 0 0 1.7-1l2.5 1 2-3.4-2.1-1.6a7 7 0 0 0 .1-1z"/></svg></span>
        <span>Einstellungen</span>
      </button>
      <button type="button" data-bk-open-library>
        <span class="bk-menu-icon" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M5 4h14v16H5z"/><path d="M8 8h8M8 12h8M8 16h5"/></svg></span>
        <span>Bibliothek wechseln</span>
      </button>
      <div class="bk-menu-separator"></div>
      <button type="button" data-bk-open-about>
        <span class="bk-menu-icon" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 10v6M12 7h.01"/></svg></span>
        <span>Über Bibliothekar</span>
      </button>
    </div>
  </div>
</header>
<button id="bk-mobile-nav-toggle" class="bk-mobile-nav-toggle" type="button" aria-label="Seitennavigation ein- oder ausblenden">‹</button>
{subnav}
{heading}

<dialog id="bk-settings-dialog" class="bk-dialog">
  <div class="bk-dialog-body">
    <div class="bk-dialog-head">
      <div><h2>Einstellungen</h2><div style="color:var(--bk-muted);margin-top:5px">Darstellung und allgemeines Verhalten</div></div>
      <button class="bk-dialog-close" type="button" data-bk-dialog-close aria-label="Schließen">×</button>
    </div>
    <section class="bk-settings-group">
      <strong>Erscheinungsbild</strong>
      <div class="bk-choice-row">
        <button type="button" data-bk-theme-choice="light">Hell</button>
        <button type="button" data-bk-theme-choice="dark">Dunkel</button>
        <button type="button" data-bk-theme-choice="system">System</button>
      </div>
    </section>
    <section class="bk-settings-group">
      <strong>Sprache</strong>
      <div class="bk-choice-row">
        <button type="button" class="active">Deutsch</button>
        <button type="button" disabled title="Die vollständige englische Oberfläche folgt in einem eigenen Lokalisierungsschritt.">English</button>
      </div>
      <div class="bk-language-note">Die Oberfläche ist in 0.22.1 vollständig deutsch. Englisch ist im Design bereits vorgesehen und wird erst aktiviert, wenn alle dynamischen Texte mitübersetzt sind.</div>
    </section>
  </div>
</dialog>

<dialog id="bk-library-dialog" class="bk-dialog">
  <div class="bk-dialog-body">
    <div class="bk-dialog-head">
      <div><h2>Bibliothek wechseln</h2><div style="color:var(--bk-muted);margin-top:5px">Bibliotheken werden später vollständig voneinander getrennt verwaltet.</div></div>
      <button class="bk-dialog-close" type="button" data-bk-dialog-close aria-label="Schließen">×</button>
    </div>
    <div class="card" style="display:flex;align-items:center;justify-content:space-between;gap:12px">
      <div><strong>Hauptbibliothek</strong><div style="color:var(--bk-muted);margin-top:4px">Aktuelle Bibliothek</div></div>
      <span class="badge success">Aktiv</span>
    </div>
  </div>
</dialog>

<dialog id="bk-about-dialog" class="bk-dialog">
  <div class="bk-dialog-body">
    <div class="bk-dialog-head">
      <div><h2>Bibliothekar</h2><div style="color:var(--bk-muted);margin-top:5px">Sichern · Ordnen · Bewahren</div></div>
      <button class="bk-dialog-close" type="button" data-bk-dialog-close aria-label="Schließen">×</button>
    </div>
    <p style="line-height:1.55">Bibliothekar organisiert Kameraimporte sicher vom ersten Einlesen bis in die dauerhafte Kamerabibliothek.</p>
    <p style="color:var(--bk-muted)">Version <span data-bk-version>0.22.1</span></p>
  </div>
</dialog>

<button id="bk-ai-launcher" class="bk-ai-launcher" type="button" aria-label="Bibliothekar Assistent" aria-expanded="false">
  ✦ <span>Bibliothekar Assistent</span>
</button>
<aside id="bk-ai-panel" class="bk-ai-panel" hidden>
  <div class="bk-ai-panel-head">
    <strong>Bibliothekar Assistent</strong>
    <button id="bk-ai-close" class="bk-ai-close" type="button" aria-label="Assistent schließen">×</button>
  </div>
  <p>Der Platz für die spätere KI-Unterstützung ist bereits vorgesehen. In diesem Designstand führt der Assistent noch keine Aktionen aus.</p>
</aside>
"""


def apply_shell(html: str, *, active_area: str, subarea: str | None = None) -> str:
    result = html
    result = result.replace(
        "</head>",
        f"<style>{BIBLIOTHEKAR_CSS}</style>\n</head>",
        1,
    )
    area = active_area if active_area in {"import", "workspace", "archive"} else "import"
    if "<body>" in result:
        result = result.replace(
            "<body>",
            f'<body class="bibliothekar-redesign" data-bk-area="{area}">',
            1,
        )
    elif "<body " in result:
        result = result.replace(
            "<body ",
            f'<body class="bibliothekar-redesign" data-bk-area="{area}" ',
            1,
        )
    result = result.replace(
        f'<body class="bibliothekar-redesign" data-bk-area="{area}">',
        f'<body class="bibliothekar-redesign" data-bk-area="{area}">\n'
        + _shell_markup(area, subarea),
        1,
    )
    result = result.replace(
        "</body>",
        f"<script>{BIBLIOTHEKAR_JS}</script>\n</body>",
        1,
    )
    return result
