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

body.bibliothekar-redesign {
  background: var(--bk-paper) !important;
  color: var(--bk-ink) !important;
  min-height: 100vh;
}

body.bibliothekar-redesign::before {
  background: var(--bk-paper) !important;
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
  position: relative;
  z-index: 1;
  flex: 1 1 0;
  min-width: 128px;
  max-width: 220px;
  height: 51px;
  margin-left: -7px;
  padding: 17px 22px 12px;
  border: 1px solid #3b4650;
  border-bottom: 0;
  border-radius: 14px 14px 0 0;
  background: #d7d8d5;
  color: #18232d;
  text-align: center;
  text-decoration: none;
  font-weight: 760;
  white-space: nowrap;
  box-shadow: 0 -2px 0 rgb(255 255 255 / 0.05) inset;
}
.bk-tab:first-child { margin-left: 0; }
.bk-tab::before {
  content: "";
  position: absolute;
  top: -1px;
  left: 12px;
  right: 12px;
  height: 5px;
  border-radius: 5px 5px 0 0;
  opacity: 0;
}
.bk-tab[data-area="import"]::before { background: var(--bk-red); }
.bk-tab[data-area="workspace"]::before { background: var(--bk-blue); }
.bk-tab[data-area="archive"]::before { background: var(--bk-yellow); }
.bk-tab.active {
  z-index: 4;
  height: 58px;
  padding-top: 20px;
  background: var(--bk-paper);
  color: var(--bk-ink);
  border-color: #6b747a;
}
.bk-tab.active::before { opacity: 1; }

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
  top: calc(100% - 7px);
  width: min(310px, calc(100vw - 28px));
  padding: 8px;
  border: 1px solid var(--bk-line);
  border-radius: 14px;
  background: var(--bk-surface);
  color: var(--bk-ink);
  box-shadow: var(--bk-shadow);
}
.bk-menu[hidden],
.bk-task-panel[hidden] { display: none !important; }
.bk-menu button {
  width: 100%;
  min-height: 42px;
  display: flex;
  align-items: center;
  gap: 10px;
  border: 0;
  background: transparent !important;
  color: var(--bk-ink) !important;
  text-align: left;
  padding: 9px 10px;
}
.bk-menu button:hover { background: var(--bk-surface-2) !important; }
.bk-menu-separator { height: 1px; background: var(--bk-line); margin: 6px; }

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
  display: grid;
  grid-template-columns: repeat(3, minmax(0,1fr));
  gap: 8px;
  max-width: 500px;
  margin: 16px 0 18px;
}
.bk-source-choice {
  min-height: 78px !important;
  display: grid;
  place-items: center;
  gap: 4px;
  padding: 10px !important;
  border-radius: 13px !important;
  opacity: .58;
  transform: scale(.96);
  transition: opacity .15s ease, transform .15s ease, border-color .15s ease;
}
.bk-source-choice:hover { opacity: .86; transform: scale(.985); }
.bk-source-choice.active {
  opacity: 1;
  transform: scale(1);
  border-color: var(--bk-red) !important;
  background: var(--bk-surface) !important;
}
.bk-source-icon {
  font-size: 1.55rem;
  line-height: 1;
}
.bk-source-choice strong {
  font-size: .82rem;
  white-space: nowrap;
}
body.bibliothekar-redesign .sd-actions {
  grid-template-columns: minmax(230px,1.5fr) repeat(3,minmax(125px,.75fr)) !important;
  align-items: stretch !important;
  gap: 10px !important;
}
body.bibliothekar-redesign .sd-actions > * {
  min-height: 54px !important;
}
body.bibliothekar-redesign .other-source-panel {
  margin-top: 12px !important;
}
body.bibliothekar-redesign .other-source-panel > summary {
  color: var(--bk-muted) !important;
}
.bk-source-mode-note {
  margin: -7px 0 10px;
  color: var(--bk-muted);
  font-size: .9rem;
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
    grid-template-columns: 1fr auto;
    align-items: center;
    gap: 8px;
    padding: 10px 12px 0;
  }
  .bk-brand { padding-bottom: 9px; }
  .bk-tabs {
    grid-column: 1 / -1;
    grid-row: 2;
    order: 3;
    overflow-x: auto;
  }
  .bk-shell-actions { padding-bottom: 8px; }
  .bk-tab { min-width: 150px; }
  .bk-task-label { display: none; }
}


@media (max-width: 760px) {
  .bk-source-picker { grid-template-columns: repeat(3, minmax(95px,1fr)); max-width: 100%; }
  body.bibliothekar-redesign .sd-actions { grid-template-columns: 1fr 1fr !important; }
  body.bibliothekar-redesign .sd-actions .mount-state { grid-column: 1 / -1; }
}
@media (max-width: 560px) {
  .bk-brand { font-size: 1.08rem; }
  .bk-mark { transform: scale(.9); transform-origin: left center; }
  .bk-shell-actions { gap: 6px; }
  .bk-tab { min-width: 138px; padding-inline: 14px; }
  .bk-ai-launcher span { display: none; }
  .bk-ai-launcher { width: 48px; padding: 0; border-radius: 50%; }
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

  const aiButton = document.getElementById("bk-ai-launcher");
  const aiPanel = document.getElementById("bk-ai-panel");
  aiButton?.addEventListener("click", () => {
    const open = aiPanel?.hasAttribute("hidden");
    if (open) aiPanel?.removeAttribute("hidden"); else aiPanel?.setAttribute("hidden", "");
  });


  // Quellenwahl der Importseite: gleiche vorhandene Funktionen, kompakter dargestellt.
  const sourcePicker = document.getElementById("bk-source-picker");
  if (sourcePicker) {
    const otherPanel = document.querySelector(".other-source-panel");
    const setSourceMode = (mode) => {
      sourcePicker.querySelectorAll("[data-source-mode]").forEach(button => {
        button.classList.toggle("active", button.dataset.sourceMode === mode);
      });
      if (mode === "sd") {
        if (otherPanel) otherPanel.open = false;
        document.getElementById("sd-card-status")?.scrollIntoView({behavior:"smooth", block:"nearest"});
      } else if (mode === "drive") {
        if (otherPanel) otherPanel.open = true;
        setTimeout(() => document.getElementById("device-select")?.scrollIntoView({behavior:"smooth", block:"center"}), 20);
      } else if (mode === "folder") {
        if (otherPanel) otherPanel.open = true;
        setTimeout(() => document.getElementById("folder-root-select")?.scrollIntoView({behavior:"smooth", block:"center"}), 20);
      }
    };
    sourcePicker.querySelectorAll("[data-source-mode]").forEach(button => {
      button.addEventListener("click", () => setSourceMode(button.dataset.sourceMode));
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
    def tab(area: str, href: str, label: str) -> str:
        klass = "bk-tab active" if area == active else "bk-tab"
        return f'<a class="{klass}" data-area="{area}" href="{href}">{escape(label)}</a>'

    subnav = ""
    if active == "workspace":
        subnav = f"""
<div class="bk-workspace-subnav" aria-label="Arbeitsbereich">
  <a href="/workspace" class="{'active' if subarea == 'captures' else ''}">Aufnahmen</a>
  <a href="/events" class="{'active' if subarea == 'events' else ''}">Ereignisse</a>
</div>
"""

    return f"""
<header class="bk-shell">
  <a class="bk-brand" href="/" aria-label="Bibliothekar Startseite">
    <span class="bk-mark" aria-hidden="true"><span class="y"></span><span class="r"></span><span class="b"></span></span>
    <span>Bibliothekar</span>
  </a>

  <nav class="bk-tabs" aria-label="Hauptbereiche">
    {tab('import', '/', 'Import & Prüfung')}
    {tab('workspace', '/workspace', 'Arbeitsbereich')}
    {tab('archive', '/transfer', 'Archiv')}
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
      <button type="button" data-bk-open-settings>⚙ <span>Einstellungen</span></button>
      <button type="button" data-bk-open-library>▤ <span>Bibliothek wechseln</span></button>
      <div class="bk-menu-separator"></div>
      <button type="button" data-bk-open-about>ⓘ <span>Über Bibliothekar</span></button>
    </div>
  </div>
</header>
{subnav}

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
      <div class="bk-language-note">Die Oberfläche ist in 0.22.0 vollständig deutsch. Englisch ist im Design bereits vorgesehen und wird erst aktiviert, wenn alle dynamischen Texte mitübersetzt sind.</div>
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
    <p style="color:var(--bk-muted)">Version <span data-bk-version>0.22.0</span></p>
  </div>
</dialog>

<button id="bk-ai-launcher" class="bk-ai-launcher" type="button" aria-label="Bibliothekar Assistent">
  ✦ <span>Bibliothekar Assistent</span>
</button>
<aside id="bk-ai-panel" class="bk-ai-panel" hidden>
  <strong>Bibliothekar Assistent</strong>
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
    if "<body>" in result:
        result = result.replace("<body>", '<body class="bibliothekar-redesign">', 1)
    elif "<body " in result:
        result = result.replace("<body ", '<body class="bibliothekar-redesign" ', 1)
    result = result.replace(
        '<body class="bibliothekar-redesign">',
        '<body class="bibliothekar-redesign">\n' + _shell_markup(active_area, subarea),
        1,
    )
    result = result.replace(
        "</body>",
        f"<script>{BIBLIOTHEKAR_JS}</script>\n</body>",
        1,
    )
    return result
