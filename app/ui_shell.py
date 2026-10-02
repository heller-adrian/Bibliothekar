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
body[data-bk-area="assistant"],
body[data-bk-area="metadata"] {
  --bk-area-accent: #7c8790;
  --bk-page-bg: #f1f2ef;
}
html[data-bk-theme="dark"] body[data-bk-area="import"] { --bk-page-bg: #120f11; }
html[data-bk-theme="dark"] body[data-bk-area="workspace"] { --bk-page-bg: #0c1217; }
html[data-bk-theme="dark"] body[data-bk-area="archive"] { --bk-page-bg: #14120c; }
html[data-bk-theme="dark"] body[data-bk-area="assistant"],
html[data-bk-theme="dark"] body[data-bk-area="metadata"] { --bk-page-bg: #0f1418; }

html[data-bk-theme] body.bibliothekar-redesign,
html[data-bk-theme] body.bibliothekar-redesign main {
  background: var(--bk-page-bg, var(--bk-paper)) !important;
  color: var(--bk-ink) !important;
}
html[data-bk-theme] body.bibliothekar-redesign::before {
  background: var(--bk-page-bg, var(--bk-paper)) !important;
}

body.bibliothekar-redesign {
  margin: 0 !important;
  padding: 0 !important;
  background: var(--bk-page-bg, var(--bk-paper)) !important;
  color: var(--bk-ink) !important;
  min-height: 100vh;
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  -webkit-font-smoothing: antialiased;
}
body.bibliothekar-redesign button,
body.bibliothekar-redesign input,
body.bibliothekar-redesign select,
body.bibliothekar-redesign textarea {
  font: inherit;
}

body.bibliothekar-redesign::before {
  background: var(--bk-page-bg, var(--bk-paper)) !important;
}

body.bibliothekar-redesign main {
  width: min(1440px, calc(100% - 48px)) !important;
  box-sizing: border-box;
  margin-left: auto !important;
  margin-right: auto !important;
  padding-top: 22px !important;
  padding-left: 18px !important;
  padding-right: 18px !important;
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
  background: var(--bk-blue) !important;
  border-color: var(--bk-blue) !important;
  color: #fff !important;
}

body.bibliothekar-redesign .danger-button {
  background:var(--bk-danger) !important;
  border-color:var(--bk-danger) !important;
  color:#fff !important;
}

body.bibliothekar-redesign .warning-button {
  border-color: var(--bk-yellow) !important;
  color: var(--bk-ink) !important;
}

body[data-bk-area="workspace"] #new-event-button {
  background: var(--bk-blue) !important;
  border-color: var(--bk-blue) !important;
  color: #fff !important;
}
body[data-bk-area="workspace"] .bk-positive-action {
  background: var(--bk-blue) !important;
  border-color: var(--bk-blue) !important;
  color: #fff !important;
}
body[data-bk-area="workspace"] #apply-saved-event-button {
  background: var(--bk-blue) !important;
  border-color: var(--bk-blue) !important;
  color: #fff !important;
}
body[data-bk-area="workspace"] span.badge.success.metadata-ok {
  color: var(--bk-blue) !important;
  -webkit-text-fill-color: var(--bk-blue) !important;
  border-color: var(--bk-blue) !important;
}
body[data-bk-area="archive"] .archive-check-card {
  border-left: 4px solid var(--bk-yellow) !important;
}
body[data-bk-area="archive"] .archive-verify-button {
  background: var(--bk-yellow) !important;
  border-color: var(--bk-yellow) !important;
  color: #201a0b !important;
  font-weight: 700 !important;
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
html[data-bk-theme="light"] body.bibliothekar-redesign .planned-check:checked {
  background: var(--bk-blue) !important;
  border-color: var(--bk-blue) !important;
}
html[data-bk-theme="light"] body.bibliothekar-redesign .planned-check:checked::after {
  color: #fff !important;
}

/* Gemeinsamer App-Rahmen */
.bk-shell {
  --bk-page-bridge-height: clamp(9px, .8vw, 13px);
  --bk-tab-page-mask: clamp(3px, .35vw, 5px);
  position: sticky;
  top: 0;
  z-index: 3000;
  display: grid;
  grid-template-columns: minmax(190px, 235px) minmax(0, 1fr) auto;
  align-items: end;
  gap: 14px;
  min-height: 78px;
  margin-bottom: var(--bk-page-bridge-height);
  padding: 14px clamp(18px, 2vw, 30px) 0;
  background: #15222c;
  border-bottom: 0;
  color: #f8f4e9;
  overflow: visible;
  isolation: isolate;
}
.bk-shell::after {
  content: "";
  position: absolute;
  z-index: 25;
  left: 0;
  right: 0;
  bottom: calc(-1 * var(--bk-page-bridge-height));
  height: calc(var(--bk-page-bridge-height) + var(--bk-tab-page-mask));
  background: var(--bk-page-bg, var(--bk-paper));
  pointer-events: none;
}

.bk-brand,
.bk-tabs,
.bk-shell-actions {
  position: relative;
}
.bk-brand,
.bk-shell-actions {
  z-index: 50;
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
  --bk-tab-overlap: clamp(24px, 3vw, 64px);
  --bk-tab-seam-bleed: clamp(2px, .28vw, 4px);
  --bk-edge-gradient-width: clamp(22px, 2vw, 38px);
  display: flex;
  align-items: flex-end;
  justify-content: stretch;
  width: 100%;
  min-width: 0;
  overflow: visible;
  isolation: auto;
  z-index: auto;
  margin-bottom: 0;
}
.bk-tab {
  --bk-tab-accent: #87939a;
  --bk-tab-bg: #5f686d;
  --bk-tab-edge-gradient: linear-gradient(to right, transparent, transparent);
  --bk-tab-motion-tail: 9px;
  position: relative;
  flex: 1 1 0;
  min-width: 0;
  height: 57px;
  margin-left: calc(0px - var(--bk-tab-overlap));
  padding: 0 48px;
  border: 0 !important;
  border-radius: 0 !important;
  background: transparent !important;
  color: #fff !important;
  text-align: center;
  text-decoration: none;
  font: inherit;
  font-weight: 780;
  white-space: nowrap;
  display: grid;
  place-items: center;
  cursor: pointer;
  isolation: isolate;
  -webkit-tap-highlight-color: transparent;
  -webkit-touch-callout: none;
  user-select: none;
  transform: translateY(0);
  transition:
    transform 150ms cubic-bezier(.2,.8,.2,1),
    filter 150ms ease;
  will-change: transform;
}
.bk-tab:focus {
  outline: none;
}
.bk-tab:focus-visible {
  outline: 2px solid color-mix(in srgb, var(--bk-tab-accent) 72%, #fff);
  outline-offset: -5px;
}
.bk-tab:first-child { margin-left: 0; }
.bk-tab[data-area="import"] { --bk-tab-accent: var(--bk-red); }
.bk-tab[data-area="workspace"] { --bk-tab-accent: var(--bk-blue); }
.bk-tab[data-area="archive"] { --bk-tab-accent: var(--bk-yellow); }

/* Eigentliche Reiterfläche. Inaktive Reiter bleiben eigenständige Karten. */
.bk-tab::before {
  content: "";
  position: absolute;
  top: 0;
  bottom: 0;
  left: calc(0px - var(--bk-tab-seam-bleed));
  right: calc(0px - var(--bk-tab-seam-bleed));
  z-index: 1;
  background:
    var(--bk-tab-edge-gradient),
    linear-gradient(
      to bottom,
      var(--bk-tab-accent) 0,
      var(--bk-tab-accent) 5px,
      var(--bk-tab-bg) 5px,
      var(--bk-tab-bg) 100%
    );
  border-radius: 17px 17px 0 0;
  transform: perspective(108px) rotateX(7deg);
  transform-origin: center bottom;
  backface-visibility: hidden;
  box-shadow: none;
  pointer-events: none;
}

/*
 * Bewegungsreserve:
 * Inaktive Karten reichen unsichtbar unter den Seiten-Puffer. Dadurch kann
 * die Karte beim Hover/Klick nach oben gleiten, ohne unten die dunkle
 * Headerfläche freizulegen. Die Reserve liegt weiterhin hinter dem
 * Seiten-Puffer und hinter dem aktiven Reiter.
 */
.bk-tab:not(.active)::before {
  bottom: calc(-1 * var(--bk-tab-motion-tail));
}

/*
 * Aktiver Reiter + Seitenfläche:
 * Keine angeklebten Schultern mehr. Der aktive Reiter läuft direkt in den
 * seitenfarbigen Header-Puffer hinein und bildet mit der Seite eine Fläche.
 */

.bk-tab-label,
.bk-tab-mobile-label {
  position: relative;
  z-index: 2;
  display: block;
  width: 100%;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.bk-tab-mobile-label { display: none; }

/* Stapelreihenfolge: aktive Karte vorn; innere Abschlüsse verschwinden dahinter. */
.bk-tabs-active-import .bk-tab[data-area="import"] { z-index: 30; }
.bk-tabs-active-import .bk-tab[data-area="workspace"] { z-index: 20; }
.bk-tabs-active-import .bk-tab[data-area="archive"] { z-index: 10; }

.bk-tabs-active-workspace .bk-tab[data-area="import"] { z-index: 20; }
.bk-tabs-active-workspace .bk-tab[data-area="workspace"] { z-index: 30; }
.bk-tabs-active-workspace .bk-tab[data-area="archive"] { z-index: 20; }

.bk-tabs-active-archive .bk-tab[data-area="import"] { z-index: 10; }
.bk-tabs-active-archive .bk-tab[data-area="workspace"] { z-index: 20; }
.bk-tabs-active-archive .bk-tab[data-area="archive"] { z-index: 30; }

/*
 * Staffelungsverlauf:
 * Der Verlauf beginnt wieder an der VERDECKTEN Außenkante des jeweils
 * hinteren Reiters. Sein kräftiger Anfang liegt damit unter der davor
 * liegenden Karte; sichtbar wird nur der weiche Auslauf hinter der Naht.
 *
 * Das ist absichtlich anders als die vorige 0.22.3-Variante: Dort wurde der
 * stärkste Punkt auf --bk-tab-overlap verschoben. Dadurch wurde an der
 * sichtbaren Naht die Perspektivschräge des hinteren Reiters sichtbar und
 * wirkte spiegelverkehrt zur überdeckenden Karte.
 *
 * Die Gesamtlänge ist jetzt Überlappung + sichtbarer Auslauf. So bleibt die
 * auf Mobilgeräten bereits stimmige Logik erhalten und der Auslauf erscheint
 * auch bei den größeren Desktop-Überlappungen.
 */
/*
 * Untere Maskierung:
 * Die inaktiven Register werden an ihrer Unterkante nicht mehr konstruktiv
 * an die Seite angepasst. Stattdessen liegt die Seitenfarbe wenige Pixel
 * vor ihnen. Der aktive Reiter bleibt durch seinen höheren z-index sichtbar
 * und läuft weiterhin direkt in den Seiten-Puffer.
 */
.bk-tab::after {
  content: none;
}

.bk-tabs-active-import .bk-tab[data-area="archive"] {
  --bk-tab-edge-gradient:
    linear-gradient(
      to right,
      var(--bk-stack-blend) 0,
      transparent calc(var(--bk-tab-overlap) + var(--bk-edge-gradient-width)),
      transparent 100%
    );
}
.bk-tabs-active-archive .bk-tab[data-area="import"] {
  --bk-tab-edge-gradient:
    linear-gradient(
      to left,
      var(--bk-stack-blend) 0,
      transparent calc(var(--bk-tab-overlap) + var(--bk-edge-gradient-width)),
      transparent 100%
    );
}


/* Sonderseiten ohne aktiven Hauptreiter: Assistent und Metadatenkorrektion
 * behalten an beiden Fugen denselben dezenten Staffelungsverlauf. */
.bk-tabs-active-assistant .bk-tab[data-area="workspace"],
.bk-tabs-active-metadata .bk-tab[data-area="workspace"] {
  --bk-tab-edge-gradient:
    linear-gradient(
      to right,
      var(--bk-stack-blend) 0,
      transparent calc(var(--bk-tab-overlap) + var(--bk-edge-gradient-width)),
      transparent 100%
    );
}
.bk-tabs-active-assistant .bk-tab[data-area="archive"],
.bk-tabs-active-metadata .bk-tab[data-area="archive"] {
  --bk-tab-edge-gradient:
    linear-gradient(
      to right,
      var(--bk-stack-blend) 0,
      transparent calc(var(--bk-tab-overlap) + var(--bk-edge-gradient-width)),
      transparent 100%
    );
}

/* Archiv im schmalen Hochformat:
 * Die perspektivisch verjüngte Oberkante des Arbeitsbereich-Reiters wird
 * links um einen zusätzlichen responsiven Bleed verlängert. So bleibt die
 * Fuge Import -> Arbeitsbereich auch auf Handy/engen Fenstern geschlossen. */
@media (max-width: 820px) {
  .bk-capture-heading { display:block; }
  .bk-capture-summary-slot { margin-top:12px; }
  .bk-tabs-active-archive .bk-tab[data-area="workspace"] {
    --bk-tab-edge-gradient:
      linear-gradient(
        to right,
        var(--bk-stack-blend) 0,
        transparent calc(var(--bk-tab-overlap) + var(--bk-edge-gradient-width)),
        transparent 100%
      );
  }
  .bk-tabs-active-archive .bk-tab[data-area="workspace"]::before {
    left: calc(0px - var(--bk-tab-seam-bleed) - var(--bk-tab-seam-bleed));
  }
}

/* Innenliegende obere Rundungen werden unter der vorderen Karte verborgen. */
.bk-tabs-active-import .bk-tab[data-area="workspace"]::before,
.bk-tabs-active-import .bk-tab[data-area="archive"]::before {
  border-top-left-radius: 0;
}
.bk-tabs-active-workspace .bk-tab[data-area="import"]::before {
  border-top-right-radius: 0;
}
.bk-tabs-active-workspace .bk-tab[data-area="archive"]::before {
  border-top-left-radius: 0;
}
.bk-tabs-active-archive .bk-tab[data-area="import"]::before,
.bk-tabs-active-archive .bk-tab[data-area="workspace"]::before {
  border-top-right-radius: 0;
}

/* Alle inaktiven Register behalten dieselbe Grundfarbe. */
html[data-bk-theme="dark"] .bk-tabs {
  --bk-stack-blend: rgb(0 0 0 / .14);
}
html[data-bk-theme="light"] .bk-tabs {
  --bk-stack-blend: rgb(18 32 51 / .09);
}
html[data-bk-theme="dark"] .bk-tab:not(.active) {
  --bk-tab-bg: #5f686d;
  color: #fff !important;
}
html[data-bk-theme="light"] .bk-tab:not(.active) {
  --bk-tab-bg: #d3d6d5;
  color: #1b2731 !important;
}

.bk-tab.active {
  --bk-tab-bg: var(--bk-page-bg, var(--bk-paper));
  height: 66px;
  padding-top: 5px;
  color: var(--bk-ink) !important;
  z-index: 40 !important;
}
.bk-tab.active::before {
  --bk-tab-edge-gradient: linear-gradient(to right, transparent, transparent);
  bottom: calc(-1 * var(--bk-page-bridge-height));
  background:
    var(--bk-tab-edge-gradient),
    linear-gradient(
      to bottom,
      var(--bk-tab-accent) 0,
      var(--bk-tab-accent) 5px,
      var(--bk-page-bg, var(--bk-paper)) 5px,
      var(--bk-page-bg, var(--bk-paper)) 100%
    );
}
.bk-tab:hover:not(.active) {
  transform: translateY(-3px);
}
.bk-tab:active:not(.active),
.bk-tab.is-navigating:not(.active) {
  transform: translateY(-8px);
}

/*
 * Sobald eine inaktive Karte angehoben wird, wird ihre zuvor verdeckte
 * Innenkante wieder zur vollständigen Kartenrundung. Im Ruhezustand bleiben
 * die inneren Rundungen weiterhin verborgen, damit die Registerfugen glatt
 * unter der aktiven Karte verschwinden.
 */
.bk-tab:hover:not(.active)::before,
.bk-tab:active:not(.active)::before,
.bk-tab.is-navigating:not(.active)::before {
  border-top-left-radius: 17px;
  border-top-right-radius: 17px;
}

.bk-tab.active {
  animation: bk-tab-arrive 180ms cubic-bezier(.2,.8,.2,1);
}
@keyframes bk-tab-arrive {
  from { transform: translateY(-6px); }
  to { transform: translateY(0); }
}
@media (prefers-reduced-motion: reduce) {
  .bk-tab {
    transition: none !important;
    animation: none !important;
  }
  .bk-tab:hover:not(.active),
  .bk-tab:active:not(.active),
  .bk-tab.is-navigating:not(.active) {
    transform: none;
  }
}
.bk-shell-actions {
  position: relative;
  z-index: 80;
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
.bk-assistant-button,
.bk-menu-button {
  width: 44px;
  min-width: 44px;
  max-width: 44px;
  height: 44px;
  min-height: 44px;
  max-height: 44px;
  flex: 0 0 44px;
  box-sizing: border-box;
  padding: 0 !important;
  border-radius: 12px !important;
  align-self: center;
}
.bk-assistant-button {
  display: grid;
  place-items: center;
  color: #fff;
  text-decoration: none;
}
.bk-assistant-button svg {
  width: 19px;
  height: 19px;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.8;
  stroke-linecap: round;
  stroke-linejoin: round;
}
.bk-assistant-button.active {
  border-color: #8ea0ab;
  background: #2a3943;
}
.bk-menu-button { font-size: 1.18rem; }
.bk-menu,
.bk-task-panel {
  position: absolute;
  z-index: 120;
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
.bk-task-panel.bk-task-panel-portaled,
.bk-menu.bk-menu-portaled {
  position: fixed !important;
  z-index: 10000 !important;
  margin: 0 !important;
}
.bk-menu {
  display: grid;
  gap: 2px;
}
.bk-menu button,
.bk-menu a {
  width: 100%;
  box-sizing: border-box;
  height: 44px;
  min-height: 44px;
  flex: 0 0 44px;
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 0 !important;
  border: 0 !important;
  border-radius: 9px !important;
  background: var(--bk-surface-2) !important;
  color: var(--bk-ink) !important;
  text-align: left;
  text-decoration: none;
  line-height: 1.2;
  padding: 0 11px !important;
}
.bk-menu button:hover,
.bk-menu a:hover {
  background: color-mix(in srgb, var(--bk-surface-2) 78%, var(--bk-ink) 8%) !important;
}
.bk-menu-separator {
  height: 1px;
  background: var(--bk-line);
  margin: 4px 7px;
}


.bk-page-heading {
  width: min(1440px, calc(100% - 48px));
  box-sizing: border-box;
  margin: 24px auto 4px;
  padding-left: 18px;
  padding-right: 18px;
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
.bk-capture-heading {
  display:grid;
  grid-template-columns:minmax(260px,.75fr) minmax(430px,1.25fr);
  align-items:end;
  gap:18px;
}
.bk-capture-heading-copy { min-width:0; }
.bk-capture-summary-slot { min-width:0; }

.bk-workspace-subnav {
  width: min(1440px, calc(100% - 48px));
  box-sizing: border-box;
  margin: 24px auto -2px;
  padding-left: 18px;
  padding-right: 18px;
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

.bk-workspace-links {
  display: flex;
  gap: 6px;
  min-width: 0;
}
.bk-workspace-dock { display: none; }

@media (min-width: 821px) {
  .bk-workspace-subnav {
    position: sticky;
    top: var(--bk-shell-sticky-height, 92px);
    z-index: 3100;
    align-items: center;
    gap: 8px 14px;
    min-height: 49px;
    background: color-mix(in srgb, var(--bk-page-bg) 98%, transparent);
    border-radius: 0 0 15px 15px;
    box-shadow: none;
    -webkit-backdrop-filter: none;
    backdrop-filter: none;
    transition:
      background 180ms ease,
      box-shadow 180ms ease,
      padding-top 180ms ease,
      padding-bottom 180ms ease;
  }
  .bk-workspace-subnav.is-stuck {
    background: color-mix(in srgb, var(--bk-page-bg) 98%, transparent);
    box-shadow: 0 12px 24px -24px rgb(0 0 0 / .55);
    -webkit-backdrop-filter: blur(14px);
    backdrop-filter: blur(14px);
  }
  .bk-workspace-subnav.has-selection-dock {
    padding-top: 3px;
    padding-bottom: 3px;
  }
  .bk-workspace-dock {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    flex: 1 1 auto;
    min-width: 0;
  }
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
.bk-folder-layout-heading {
  display: flex; align-items: center; justify-content: space-between;
  gap: 12px; flex-wrap: nowrap;
}
.bk-folder-layout-toggle {
  display: inline-flex; align-items: center; gap: 8px;
  white-space: nowrap; line-height: 1.2; margin-left: auto;
}
#bk-folder-layout-settings input[type="checkbox"],
#bk-folder-layout-settings input[type="radio"] {
  width: 18px !important; min-width: 18px !important;
  height: 18px !important; min-height: 18px !important;
  padding: 0 !important; margin: 0 !important;
  flex: 0 0 18px;
}
#bk-folder-layout-settings input[type="checkbox"] { border-radius: 4px !important; }
#bk-folder-layout-settings input[type="radio"] { border-radius: 50% !important; }
.bk-folder-input-root {
  display: grid; grid-template-columns: 18px minmax(0, 1fr) auto;
  align-items: center; gap: 8px; padding: 7px 9px;
  border: 1px solid var(--bk-line); border-radius: 9px;
}
.bk-folder-input-root strong { white-space: nowrap; }
.bk-choice-row button.active {
  background: var(--bk-ink) !important;
  color: var(--bk-paper) !important;
  border-color: var(--bk-ink) !important;
}
.bk-language-note {
  margin-top: 9px; color: var(--bk-muted); font-size: .9rem;
}

body[data-bk-area="assistant"] main,
body[data-bk-area="metadata"] main {
  min-height: 0 !important;
  background: transparent !important;
}
body[data-bk-area="assistant"] main > .card {
  max-width: 900px;
  margin: 20px 0 0 !important;
  padding: 16px 18px !important;
}

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
body[data-bk-area="import"] .import-panel {
  border-left: 4px solid var(--bk-red) !important;
}

.bk-source-picker {
  width: 100%;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  margin: 14px 0 18px;
}
.bk-source-option {
  width: 100%;
  min-width: 0;
  min-height: 76px !important;
  display: grid !important;
  grid-template-columns: 44px minmax(0, 1fr);
  align-items: center;
  gap: 11px;
  margin: 0 !important;
  padding: 11px 13px !important;
  border: 1px solid var(--bk-line) !important;
  border-radius: 12px !important;
  background: var(--bk-surface-2) !important;
  color: var(--bk-ink) !important;
  text-align: left;
}
.bk-source-option:hover {
  border-color: color-mix(in srgb, var(--bk-red) 48%, var(--bk-line)) !important;
}
.bk-source-option.active {
  background: var(--bk-surface) !important;
  border-color: var(--bk-red) !important;
  box-shadow: inset 0 3px 0 var(--bk-red);
}
.bk-source-option-icon {
  width: 40px;
  height: 40px;
  display: grid;
  place-items: center;
  border-radius: 9px;
  background: var(--bk-surface);
  color: var(--bk-ink);
}
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
.bk-source-option > span:last-child {
  min-width: 0;
  display: grid;
  gap: 3px;
}
.bk-source-option strong {
  overflow-wrap: anywhere;
}
.bk-source-option small {
  color: var(--bk-muted);
  font-size: .78rem;
  line-height: 1.25;
}

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

body[data-bk-area="import"] [data-source-pane][hidden] {
  display: none !important;
}
body.bibliothekar-redesign .sd-actions {
  grid-template-columns: minmax(260px,1fr) repeat(3, minmax(142px, 165px)) !important;
  align-items: stretch !important;
  gap: 9px !important;
}
body.bibliothekar-redesign .sd-actions .mount-state {
  margin: 0 !important;
  min-height: 56px !important;
  padding: 8px 12px !important;
  display: flex;
  align-items: center;
}
.bk-action-tile {
  min-height: 56px !important;
  padding: 7px 11px !important;
  display: flex !important;
  flex-direction: column;
  align-items: flex-start !important;
  justify-content: center;
  gap: 5px;
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
body.bibliothekar-redesign .import-panel,
body.bibliothekar-redesign .source-device-card,
body.bibliothekar-redesign .sd-actions,
body.bibliothekar-redesign .source-detail,
body.bibliothekar-redesign .other-source-content {
  min-width: 0 !important;
  max-width: 100% !important;
  overflow-wrap: anywhere;
}
body.bibliothekar-redesign .sd-actions {
  width: 100% !important;
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
body[data-bk-area="import"] details > summary {
  list-style: none !important;
  display: grid !important;
  grid-template-columns: 20px minmax(0,1fr) !important;
  align-items: center !important;
  gap: 7px !important;
}
body[data-bk-area="import"] details > summary::-webkit-details-marker {
  display: none !important;
}
body[data-bk-area="import"] details > summary::marker {
  content: "" !important;
}
body[data-bk-area="import"] details > summary::before {
  content: "▸";
  display: block;
  width: 20px;
  font-size: 18px;
  line-height: 1;
  text-align: center;
  color: currentColor;
}
body[data-bk-area="import"] details[open] > summary::before {
  content: "▾";
}
body[data-bk-area="import"] .drive-actions {
  grid-template-columns: repeat(3,minmax(0,1fr));
  margin-top: 10px;
}
body[data-bk-area="import"] #drive-folder-browser {
  margin-top: 16px;
  padding-top: 14px;
  border-top: 1px solid var(--bk-line);
}
@media (max-width: 760px) {
  body[data-bk-area="import"] .drive-actions {
    grid-template-columns: 1fr;
  }
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

body[data-bk-area="workspace"] .bk-workspace-command,
body[data-bk-area="workspace"] .bk-workspace-job-picker,
body[data-bk-area="workspace"] .bk-workspace-job-picker label,
body[data-bk-area="import"] .bk-metadata-toolbar,
body[data-bk-area="import"] .bk-metadata-toolbar .notice {
  background: transparent !important;
  background-color: transparent !important;
  border: 0 !important;
  outline: 0 !important;
  box-shadow: none !important;
}
body[data-bk-area="workspace"] .bk-workspace-command {
  margin: 0 0 18px !important;
  padding: 0 !important;
}
body[data-bk-area="workspace"] .bk-workspace-job-picker {
  display: block;
  margin: 0 0 16px !important;
  padding: 0 !important;
}
body[data-bk-area="workspace"] .bk-workspace-job-picker label {
  display: grid;
  gap: 6px;
}
body[data-bk-area="import"] .bk-metadata-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: .75rem;
  padding: 0 !important;
  margin: 22px 0 24px !important;
}
body[data-bk-area="import"] .diagnostics {
  margin-top: 0 !important;
  margin-bottom: 30px !important;
}
body[data-bk-area="import"] .diagnostics + section {
  margin-top: 0 !important;
}
body[data-bk-area="import"] .diagnostics + section .bk-import-head {
  margin-bottom: 12px !important;
}

@media (min-width: 821px) and (max-width: 1120px) {
  .bk-shell {
    grid-template-columns: 170px minmax(0, 1fr) auto;
    gap: 10px;
    padding-inline: 16px;
  }
  .bk-brand { font-size: 1.08rem; }
  .bk-tabs {
    --bk-tab-overlap: clamp(24px, 3vw, 34px);
    --bk-tab-seam-bleed: clamp(2px, .32vw, 4px);
    --bk-edge-gradient-width: clamp(16px, 2.2vw, 28px);
  }
  .bk-tab {
    flex: 1 1 0;
    min-width: 0;
    padding-inline: 34px;
    font-size: .9rem;
  }
  .bk-task-label { display: none; }
}

@media (min-width: 1500px) {
  .bk-shell {
    grid-template-columns: 250px minmax(0, 1fr) auto;
    padding-inline: 26px;
  }
  .bk-tabs {
    --bk-tab-overlap: clamp(44px, 3vw, 72px);
    --bk-tab-seam-bleed: clamp(3px, .24vw, 5px);
    --bk-edge-gradient-width: clamp(22px, 1.7vw, 36px);
    width: 100%;
    max-width: none;
  }
  .bk-tab {
    flex: 1 1 0;
    min-width: 0;
    padding-inline: 50px;
  }
}

@media (max-width: 820px) {
  body.bibliothekar-redesign main {
    padding-left: 14px !important;
    padding-right: 14px !important;
  }
  .bk-page-heading,
  .bk-workspace-subnav {
    padding-left: 14px;
    padding-right: 14px;
  }

  .bk-shell {
    --bk-page-bridge-height: 10px;
    min-height: 0;
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    align-items: center;
    gap: 8px 10px;
    padding: 10px 12px 0;
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
  .bk-assistant-button,
  .bk-menu-button {
    width: 42px;
    min-width: 42px;
    max-width: 42px;
    height: 42px;
    min-height: 42px;
    max-height: 42px;
    flex-basis: 42px;
  }

  .bk-tabs {
    --bk-tab-overlap: clamp(12px, 4vw, 18px);
    --bk-tab-seam-bleed: clamp(3px, 1vw, 5px);
    --bk-edge-gradient-width: clamp(18px, 5vw, 28px);
    grid-column: 1 / -1;
    grid-row: 2;
    width: 100%;
    margin-top: 7px;
    margin-bottom: 0;
    display: flex;
  }
  .bk-tab {
    min-width: 0;
    max-width: none;
    height: 44px;
    margin-left: calc(0px - var(--bk-tab-overlap));
    padding: 0 16px;
    font-size: .76rem;
  }
  .bk-tab[data-area="import"],
  .bk-tab[data-area="workspace"],
  .bk-tab[data-area="archive"] {
    width: auto;
    flex: 1 1 0;
  }
  .bk-tab:first-child { margin-left: 0; }
  .bk-tab.active,
  .bk-tab.is-active {
    height: 49px;
  }
  .bk-tab::before {
    inset: 0 0 calc(-1 * var(--bk-tab-motion-tail)) 0;
    transform: perspective(88px) rotateX(5deg);
    border-radius: 12px 12px 0 0;
  }
  .bk-tab.active::before,
  .bk-tab.is-active::before {
    bottom: calc(-1 * var(--bk-page-bridge-height));
  }
  .bk-tab:hover:not(.active)::before,
  .bk-tab:active:not(.active)::before,
  .bk-tab.is-navigating:not(.active)::before {
    border-top-left-radius: 12px;
    border-top-right-radius: 12px;
  }
  .bk-tab-label { display: none; }
  .bk-tab-mobile-label {
    display: inline-block;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .bk-menu,
  .bk-task-panel {
    position: fixed;
    z-index: 9000;
    top: 126px;
    right: 12px;
    left: 12px;
    width: auto;
    max-height: calc(100dvh - 96px);
    overflow: auto;
  }

  .bk-page-heading {
    width: auto;
    margin: 18px 16px 6px;
  }
  .bk-page-heading h1 { font-size: clamp(1.9rem, 9vw, 2.35rem); }
  .bk-page-heading p { margin-top: 7px; font-size: .95rem; }

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
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 7px;
  }
  .bk-source-option {
    min-height: 72px !important;
    grid-template-columns: 1fr;
    justify-items: center;
    gap: 6px;
    padding: 8px 6px !important;
    text-align: center;
  }
  .bk-source-option-icon {
    width: 34px;
    height: 34px;
  }
  .bk-source-option small { display: none; }
  .bk-source-option strong {
    font-size: .78rem;
    line-height: 1.15;
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
  .bk-job-thumb { width: 54px; height: 54px; }

  .bk-status-grid { grid-template-columns: 1fr !important; }
  .bk-status-card { min-height: 82px; }

  body.bibliothekar-redesign section { scroll-margin-top: 132px; }
}

@media (max-width: 430px) {
  .bk-brand span:last-child { font-size: 1.02rem; }
  .bk-task-button { min-width: 70px; }
  .bk-tabs {
    --bk-tab-overlap: clamp(12px, 4vw, 18px);
    --bk-tab-seam-bleed: clamp(3px, 1vw, 5px);
    --bk-edge-gradient-width: clamp(18px, 6vw, 28px);
  }
  .bk-tab {
    font-size: .68rem;
    padding-inline: 5px;
  }
  body.bibliothekar-redesign .selection-actions {
    grid-template-columns: 1fr 1fr;
  }
}
"""


BIBLIOTHEKAR_0310_CSS = r"""
.bk-settings-tabs {
  display: flex; gap: 8px; flex-wrap: wrap;
  padding: 0 0 12px; border-bottom: 1px solid var(--bk-line);
}
.bk-settings-tabs button.active {
  background: var(--bk-ink) !important;
  color: var(--bk-paper) !important;
  border-color: var(--bk-ink) !important;
}
.bk-settings-panel[hidden] { display: none !important; }
.bk-library-list { display: grid; gap: 10px; margin-top: 10px; }
.bk-library-card {
  border: 1px solid var(--bk-line); border-radius: 12px;
  padding: 12px; background: var(--bk-surface);
  display: grid; gap: 9px;
}
.bk-library-card-head {
  display: flex; align-items: center; justify-content: space-between;
  gap: 10px; flex-wrap: wrap;
}
.bk-library-meta {
  display: grid; gap: 3px; color: var(--bk-muted);
  font-size: .84rem; overflow-wrap: anywhere;
}
.bk-library-actions { display: flex; gap: 7px; flex-wrap: wrap; }
.bk-library-form {
  display: grid; gap: 9px; margin-top: 10px;
  padding: 12px; border: 1px solid var(--bk-line);
  border-radius: 12px; background: var(--bk-surface);
}
.bk-library-form label { display: grid; gap: 5px; }
.bk-library-form input { width: 100%; box-sizing: border-box; }
.bk-library-status {
  color: var(--bk-muted); font-size: .88rem; line-height: 1.35;
  white-space: pre-wrap;
}
.bk-library-status.is-error { color: var(--bk-danger); }
.bk-library-status.is-ok { color: var(--bk-green); }
.bk-library-switch-list { display: grid; gap: 9px; }
.bk-library-switch {
  width: 100%; display: flex !important; align-items: center;
  justify-content: space-between; gap: 12px; text-align: left;
  padding: 12px !important; border: 1px solid var(--bk-line) !important;
  background: var(--bk-surface) !important;
}
.bk-library-switch.active {
  border-color: var(--bk-green) !important;
}
.bk-library-switch small {
  color: var(--bk-muted); display: block; margin-top: 3px;
}

.bk-brand-copy {
  display: grid;
  align-content: center;
  gap: 1px;
  min-width: 0;
  line-height: 1.04;
}
.bk-brand-title {
  font-size: 1.13rem;
  font-weight: 800;
  letter-spacing: -0.025em;
}
.bk-brand-library {
  max-width: 180px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: rgba(248, 244, 233, .72);
  font-size: .72rem;
  font-weight: 600;
  letter-spacing: .01em;
}

"""



BIBLIOTHEKAR_0311_CSS = r"""
/* 0.32.3: responsiver Dialog plus dauerhaft sichtbarer Bibliothekskontext. */
.bk-dialog {
  max-height: calc(100dvh - 28px) !important;
  overflow: hidden !important;
}
.bk-dialog-body {
  box-sizing: border-box;
  max-height: calc(100dvh - 30px);
  overflow-y: auto;
  overflow-x: hidden;
  overscroll-behavior: contain;
  scrollbar-gutter: stable;
}
#bk-settings-dialog {
  width: min(880px, calc(100vw - 28px));
}
#bk-settings-dialog .bk-settings-tabs {
  display: flex;
  flex-wrap: nowrap;
  gap: 8px;
  overflow-x: auto;
  overflow-y: hidden;
  scrollbar-width: thin;
  overscroll-behavior-inline: contain;
  -webkit-overflow-scrolling: touch;
  padding: 2px 0 6px;
}
#bk-settings-dialog .bk-settings-tabs button {
  min-width: 0 !important;
  flex: 1 1 0;
  white-space: nowrap;
  border-radius: 11px !important;
}
#bk-settings-dialog .bk-settings-group,
#bk-settings-dialog .bk-library-card,
#bk-settings-dialog .bk-library-form,
#bk-settings-dialog .bk-library-add-card {
  border: 1px solid var(--bk-line);
  border-radius: 14px !important;
  background: var(--bk-surface);
  padding: 14px;
}
#bk-settings-dialog .bk-settings-group {
  margin-top: 12px;
}
#bk-settings-dialog .bk-settings-group:first-of-type {
  border-top: 1px solid var(--bk-line);
}
#bk-settings-dialog .bk-library-add-card {
  margin-top: 10px;
}
#bk-settings-dialog .bk-library-add-card > summary {
  cursor: pointer;
  font-weight: 800;
  list-style: none;
}
#bk-settings-dialog .bk-library-add-card > summary::-webkit-details-marker {
  display: none;
}
#bk-settings-dialog .bk-library-add-card > summary::before {
  content: "▸";
  display: inline-block;
  margin-right: 8px;
  transition: transform .16s ease;
}
#bk-settings-dialog .bk-library-add-card[open] > summary::before {
  transform: rotate(90deg);
}
#bk-settings-dialog .bk-library-add-card .bk-library-form {
  margin-top: 12px;
  background: var(--bk-surface-2);
}
#bk-settings-dialog input:not([type="checkbox"]):not([type="radio"]),
#bk-settings-dialog select,
#bk-settings-dialog textarea,
#bk-library-dialog input,
#bk-library-dialog select,
#bk-library-dialog textarea {
  border-radius: 11px !important;
  border: 1px solid var(--bk-line) !important;
  background: var(--bk-surface-2) !important;
  box-shadow: none !important;
}
#bk-library-dialog .bk-library-switch {
  border-radius: 12px !important;
}
#bk-library-management-list,
.bk-settings-panel {
  min-width: 0;
}
@media (max-width: 700px) {
  #bk-settings-dialog {
    width: calc(100vw - 18px);
  }
  #bk-settings-dialog .bk-dialog-body {
    padding: 16px;
  }
  #bk-settings-dialog .bk-dialog-head {
    display: grid;
    grid-template-columns: 38px minmax(0, 1fr) 38px;
    align-items: start;
    gap: 8px;
  }
  #bk-settings-dialog .bk-dialog-head > div:first-child {
    grid-column: 2;
    text-align: center;
  }
  #bk-settings-dialog .bk-dialog-close {
    grid-column: 3;
    grid-row: 1;
  }
  #bk-settings-dialog .bk-settings-tabs {
    margin-inline: -4px;
    padding-inline: 4px;
  }
  #bk-settings-dialog .bk-settings-tabs button {
    flex: 0 0 auto;
    min-width: max-content !important;
  }
  #bk-settings-dialog .bk-choice-row {
    justify-content: center;
  }
}
"""


BIBLIOTHEKAR_JS = r"""
(() => {
  const root = document.documentElement;
  const pageUrl = new URL(window.location.href);
  const bkLibraryId = pageUrl.searchParams.get("library") || "main";
  const bkOriginalFetch = window.fetch.bind(window);

  function bkLibraryHref(href, libraryId=bkLibraryId) {
    try {
      const url = new URL(String(href || "/"), window.location.href);
      if (url.origin !== window.location.origin) return String(href || "/");
      if (!url.pathname.startsWith("/api/")) {
        url.searchParams.set("library", libraryId || "main");
      }
      return url.pathname + url.search + url.hash;
    } catch (_) {
      return String(href || "/");
    }
  }

  window.fetch = (input, init={}) => {
    let url;
    try {
      url = new URL(
        input instanceof Request ? input.url : String(input),
        window.location.href,
      );
    } catch (_) {
      return bkOriginalFetch(input, init);
    }
    if (url.origin !== window.location.origin || !url.pathname.startsWith("/api/")) {
      return bkOriginalFetch(input, init);
    }

    const headers = new Headers(
      input instanceof Request ? input.headers : undefined
    );
    new Headers(init.headers || {}).forEach((value, key) => headers.set(key, value));
    headers.set("X-Bibliothekar-Library", bkLibraryId);

    if (input instanceof Request) {
      return bkOriginalFetch(new Request(input, {...init, headers}));
    }
    return bkOriginalFetch(input, {...init, headers});
  };

  document.querySelectorAll('a[href^="/"]').forEach(link => {
    link.setAttribute("href", bkLibraryHref(link.getAttribute("href")));
  });

  const currentLibraryName = document.getElementById("bk-current-library-name");
  async function bkRefreshCurrentLibraryName() {
    if (!currentLibraryName) return;
    try {
      const response = await fetch("/api/libraries/current", {cache:"no-store"});
      if (!response.ok) throw new Error();
      const data = await response.json();
      const name = String(data.display_name || data.library_id || bkLibraryId || "Bibliothek");
      currentLibraryName.textContent = name;
      currentLibraryName.title = name;
    } catch (_) {
      currentLibraryName.textContent = bkLibraryId === "main" ? "Hauptbibliothek" : bkLibraryId;
      currentLibraryName.title = currentLibraryName.textContent;
    }
  }
  bkRefreshCurrentLibraryName();

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
  const taskPanelHome = taskPanel?.parentNode || null;
  const taskPanelHomeNext = taskPanel?.nextSibling || null;
  const menuHome = menu?.parentNode || null;
  const menuHomeNext = menu?.nextSibling || null;

  function restoreMenu() {
    if (!menu) return;
    menu.setAttribute("hidden", "");
    menu.classList.remove("bk-menu-portaled");
    menu.style.removeProperty("top");
    menu.style.removeProperty("right");
    menu.style.removeProperty("left");
    if (menuHome) menuHome.insertBefore(menu, menuHomeNext);
  }

  function openMenu() {
    if (!menu || !menuButton) return;
    const rect=menuButton.getBoundingClientRect();
    document.body.appendChild(menu);
    menu.classList.add("bk-menu-portaled");
    menu.style.top=Math.round(rect.bottom + 8)+"px";
    menu.style.right=Math.max(10,Math.round(window.innerWidth - rect.right))+"px";
    menu.removeAttribute("hidden");
  }

  function restoreTaskPanel() {
    if (!taskPanel) return;
    taskPanel.setAttribute("hidden", "");
    taskPanel.classList.remove("bk-task-panel-portaled");
    taskPanel.style.removeProperty("top");
    taskPanel.style.removeProperty("right");
    taskPanel.style.removeProperty("left");
    if (taskPanelHome) taskPanelHome.insertBefore(taskPanel, taskPanelHomeNext);
  }

  function openTaskPanel() {
    if (!taskPanel || !tasksButton) return;
    const rect=tasksButton.getBoundingClientRect();
    document.body.appendChild(taskPanel);
    taskPanel.classList.add("bk-task-panel-portaled");
    taskPanel.style.top=Math.round(rect.bottom + 8)+"px";
    taskPanel.style.right=Math.max(10,Math.round(window.innerWidth - rect.right))+"px";
    taskPanel.removeAttribute("hidden");
  }

  function closePopovers(except) {
    if (except !== menu) restoreMenu();
    if (except !== taskPanel) restoreTaskPanel();
  }

  menuButton?.addEventListener("click", (event) => {
    event.stopPropagation();
    const willOpen = menu?.hasAttribute("hidden");
    closePopovers(willOpen ? menu : null);
    if (willOpen) openMenu(); else restoreMenu();
  });

  tasksButton?.addEventListener("click", (event) => {
    event.stopPropagation();
    const willOpen = taskPanel?.hasAttribute("hidden");
    closePopovers(willOpen ? taskPanel : null);
    if (willOpen) openTaskPanel(); else restoreTaskPanel();
  });

  document.addEventListener("click", (event) => {
    if (!event.target.closest(".bk-shell-actions") && !event.target.closest(".bk-task-panel") && !event.target.closest(".bk-menu")) closePopovers(null);
  });

  function openDialog(id) {
    closePopovers(null);
    document.getElementById(id)?.showModal?.();
  }

  function setSettingsArea(area) {
    document.querySelectorAll("[data-bk-settings-area]").forEach(button => {
      button.classList.toggle("active", button.dataset.bkSettingsArea === area);
    });
    document.querySelectorAll("[data-bk-settings-panel]").forEach(panel => {
      panel.hidden = panel.dataset.bkSettingsPanel !== area;
    });
  }
  document.querySelectorAll("[data-bk-settings-area]").forEach(button => {
    button.addEventListener("click", () => setSettingsArea(button.dataset.bkSettingsArea));
  });
  setSettingsArea("appearance");

  document.querySelector("[data-bk-open-settings]")?.addEventListener("click", () => {
    openDialog("bk-settings-dialog");
    bkRefreshLibraryManagement();
  });
  document.querySelector("[data-bk-open-library]")?.addEventListener("click", () => {
    openDialog("bk-library-dialog");
    bkRefreshLibrarySwitcher();
  });
  document.querySelector("[data-bk-open-about]")?.addEventListener("click", () => openDialog("bk-about-dialog"));
  document.querySelectorAll("[data-bk-dialog-close]").forEach(button => {
    button.addEventListener("click", () => button.closest("dialog")?.close());
  });

  function bkEscape(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  async function bkJson(url, options={}) {
    const response = await fetch(url, options);
    const raw = await response.text();
    let data = {};
    try { data = raw ? JSON.parse(raw) : {}; }
    catch (_) { throw new Error("Ungültige Serverantwort."); }
    if (!response.ok) {
      const detail = data.detail;
      if (detail && typeof detail === "object") {
        throw new Error((detail.errors || []).join("\n") || "Prüfung fehlgeschlagen.");
      }
      throw new Error(String(detail || "Anfrage fehlgeschlagen."));
    }
    return data;
  }

  async function bkRefreshLibrarySwitcher() {
    const host = document.getElementById("bk-library-switch-list");
    if (!host) return;
    host.innerHTML = '<div style="color:var(--bk-muted)">Bibliotheken werden geladen …</div>';
    try {
      const [listData, currentData] = await Promise.all([
        bkJson("/api/libraries"),
        bkJson("/api/libraries/current"),
      ]);
      const current = String(currentData.library_id || bkLibraryId);
      const libraries = listData.libraries || [];
      host.innerHTML = libraries.map(row => {
        const id = String(row.library_id || "");
        const active = id === current;
        return '<button type="button" class="bk-library-switch '+(active?'active':'')+'" data-bk-library-switch="'+bkEscape(id)+'">'
          +'<span><strong>'+bkEscape(row.display_name || id)+'</strong><small>'
          +(row.is_main?'Hauptbibliothek':'Bibliothek')
          +(active?' · aktuell':'')
          +'</small></span>'
          +'<span class="badge '+(active?'success':'')+'">'+(active?'Aktiv':'Öffnen')+'</span>'
          +'</button>';
      }).join("") || '<div style="color:var(--bk-muted)">Keine aktive Bibliothek gefunden.</div>';
      host.querySelectorAll("[data-bk-library-switch]").forEach(button => {
        button.addEventListener("click", () => {
          const target = String(button.dataset.bkLibrarySwitch || "main");
          const next = new URL(window.location.href);
          next.searchParams.set("library", target);
          window.location.assign(next.pathname + next.search + next.hash);
        });
      });
    } catch (error) {
      host.innerHTML = '<div style="color:var(--bk-danger)">'+bkEscape(error.message)+'</div>';
    }
  }

  function bkLibraryCard(row) {
    const id = String(row.library_id || "");
    const inactive = !row.is_active;
    return '<div class="bk-library-card" data-bk-library-card="'+bkEscape(id)+'">'
      +'<div class="bk-library-card-head"><div><strong>'+bkEscape(row.display_name || id)+'</strong>'
      +'<div style="color:var(--bk-muted);font-size:.84rem;margin-top:3px">'+(row.is_main?'Hauptbibliothek':'Bibliothek')
      +(inactive?' · deaktiviert':' · aktiv')+'</div></div>'
      +'<span class="badge '+(!inactive?'success':'')+'">'+(!inactive?'Aktiv':'Inaktiv')+'</span></div>'
      +'<label style="display:grid;gap:5px"><span>Anzeigename</span>'
      +'<input data-bk-library-name value="'+bkEscape(row.display_name || id)+'"></label>'
      +'<div class="bk-library-meta"><span>Arbeitsbereich: '+bkEscape(row.work_root || "")+'</span>'
      +'<span>Archiv: '+bkEscape(row.archive_root || "")+'</span>'
      +'<span>Technische ID: '+bkEscape(id)+'</span></div>'
      +'<div class="bk-library-actions">'
      +'<button type="button" data-bk-library-save>Anzeige speichern</button>'
      +'<button type="button" data-bk-library-check>Prüfen</button>'
      +(row.is_main?'':(
        inactive
          ? '<button type="button" data-bk-library-activate class="bk-positive-action">Aktivieren</button>'
          : '<button type="button" data-bk-library-deactivate>Deaktivieren</button>'
      ))
      +(row.is_main?'':'<button type="button" data-bk-library-unregister class="danger-button">Abmelden</button>')
      +'</div><div class="bk-library-status" data-bk-library-status></div></div>';
  }

  async function bkRefreshLibraryManagement() {
    const host = document.getElementById("bk-library-management-list");
    if (!host) return;
    host.innerHTML = '<div style="color:var(--bk-muted)">Bibliotheken werden geladen …</div>';
    try {
      const data = await bkJson("/api/libraries?include_inactive=true");
      host.innerHTML = (data.libraries || []).map(bkLibraryCard).join("");
      bindLibraryManagementActions(host);
    } catch (error) {
      host.innerHTML = '<div style="color:var(--bk-danger)">'+bkEscape(error.message)+'</div>';
    }
  }

  function setLibraryCardStatus(card, message, ok=false) {
    const node = card?.querySelector("[data-bk-library-status]");
    if (!node) return;
    node.textContent = message || "";
    node.classList.toggle("is-ok", Boolean(ok));
    node.classList.toggle("is-error", Boolean(message) && !ok);
  }

  function bindLibraryManagementActions(host) {
    host.querySelectorAll("[data-bk-library-card]").forEach(card => {
      const id = String(card.dataset.bkLibraryCard || "");
      const name = card.querySelector("[data-bk-library-name]");
      card.querySelector("[data-bk-library-save]")?.addEventListener("click", async () => {
        try {
          await bkJson("/api/libraries/"+encodeURIComponent(id), {
            method:"PATCH", headers:{"Content-Type":"application/json"},
            body:JSON.stringify({display_name:name?.value || ""}),
          });
          setLibraryCardStatus(card, "Anzeigename gespeichert. Ordner und Mountpfade bleiben unverändert.", true);
          await bkRefreshLibrarySwitcher();
        } catch (error) { setLibraryCardStatus(card, error.message); }
      });
      card.querySelector("[data-bk-library-check]")?.addEventListener("click", async () => {
        const work = card.querySelector(".bk-library-meta span:nth-child(1)")?.textContent?.replace(/^Arbeitsbereich:\s*/, "") || "";
        const archive = card.querySelector(".bk-library-meta span:nth-child(2)")?.textContent?.replace(/^Archiv:\s*/, "") || "";
        try {
          const result = await bkJson("/api/libraries/check", {
            method:"POST", headers:{"Content-Type":"application/json"},
            body:JSON.stringify({library_id:id, work_root:work, archive_root:archive}),
          });
          setLibraryCardStatus(card, result.valid ? "Prüfung PASS." : (result.errors || []).join("\n"), result.valid);
        } catch (error) { setLibraryCardStatus(card, error.message); }
      });
      card.querySelector("[data-bk-library-deactivate]")?.addEventListener("click", async () => {
        if (!confirm("Bibliothek deaktivieren? Dateien, Datenbank und Archiv bleiben erhalten.")) return;
        try {
          await bkJson("/api/libraries/"+encodeURIComponent(id)+"/deactivate", {method:"POST"});
          if (id === bkLibraryId) {
            window.location.assign(bkLibraryHref(window.location.pathname, "main"));
            return;
          }
          await bkRefreshLibraryManagement();
        } catch (error) { setLibraryCardStatus(card, error.message); }
      });
      card.querySelector("[data-bk-library-activate]")?.addEventListener("click", async () => {
        try {
          await bkJson("/api/libraries/"+encodeURIComponent(id)+"/activate", {method:"POST"});
          await bkRefreshLibraryManagement();
        } catch (error) { setLibraryCardStatus(card, error.message); }
      });
      card.querySelector("[data-bk-library-unregister]")?.addEventListener("click", async () => {
        if (!confirm("Bibliothek abmelden? Es werden keine Dateien, keine Datenbank und kein Archiv gelöscht.")) return;
        try {
          await bkJson("/api/libraries/"+encodeURIComponent(id)+"/unregister", {method:"POST"});
          if (id === bkLibraryId) {
            window.location.assign(bkLibraryHref(window.location.pathname, "main"));
            return;
          }
          await bkRefreshLibraryManagement();
        } catch (error) { setLibraryCardStatus(card, error.message); }
      });
    });
  }

  const newLibraryName = document.getElementById("bk-new-library-name");
  const newLibraryWork = document.getElementById("bk-new-library-work");
  const newLibraryArchive = document.getElementById("bk-new-library-archive");
  const newLibraryCreate = document.getElementById("bk-new-library-create");
  const newLibraryStatus = document.getElementById("bk-new-library-status");
  let newLibraryChecked = false;

  function resetNewLibraryCheck() {
    newLibraryChecked = false;
    if (newLibraryCreate) newLibraryCreate.disabled = true;
    if (newLibraryStatus) {
      newLibraryStatus.textContent = "";
      newLibraryStatus.className = "bk-library-status";
    }
  }
  [newLibraryName,newLibraryWork,newLibraryArchive].forEach(input => input?.addEventListener("input", resetNewLibraryCheck));

  document.getElementById("bk-new-library-check")?.addEventListener("click", async () => {
    if (!newLibraryStatus) return;
    newLibraryStatus.textContent = "Mountpfade werden geprüft …";
    newLibraryStatus.className = "bk-library-status";
    try {
      const result = await bkJson("/api/libraries/check", {
        method:"POST", headers:{"Content-Type":"application/json"},
        body:JSON.stringify({
          work_root:newLibraryWork?.value || "",
          archive_root:newLibraryArchive?.value || "",
        }),
      });
      newLibraryChecked = Boolean(result.valid);
      newLibraryCreate.disabled = !newLibraryChecked;
      newLibraryStatus.textContent = result.valid
        ? "Prüfung PASS. Die Bibliothek kann erstellt werden."
        : (result.errors || []).join("\n");
      newLibraryStatus.className = "bk-library-status "+(result.valid?"is-ok":"is-error");
    } catch (error) {
      newLibraryChecked = false;
      newLibraryCreate.disabled = true;
      newLibraryStatus.textContent = error.message;
      newLibraryStatus.className = "bk-library-status is-error";
    }
  });

  newLibraryCreate?.addEventListener("click", async () => {
    if (!newLibraryChecked) return;
    newLibraryCreate.disabled = true;
    try {
      const result = await bkJson("/api/libraries", {
        method:"POST", headers:{"Content-Type":"application/json"},
        body:JSON.stringify({
          display_name:newLibraryName?.value || "",
          work_root:newLibraryWork?.value || "",
          archive_root:newLibraryArchive?.value || "",
        }),
      });
      const created = result.library || {};
      newLibraryStatus.textContent = "Bibliothek „"+String(created.display_name || "")+"“ wurde erstellt.";
      newLibraryStatus.className = "bk-library-status is-ok";
      newLibraryName.value = "";
      newLibraryWork.value = "";
      newLibraryArchive.value = "";
      newLibraryChecked = false;
      await bkRefreshLibraryManagement();
      await bkRefreshLibrarySwitcher();
    } catch (error) {
      newLibraryStatus.textContent = error.message;
      newLibraryStatus.className = "bk-library-status is-error";
    }
  });

  const folderSettings = document.getElementById("bk-folder-layout-settings");
  let folderLayoutState = null;

  function bkNodeId() {
    return (globalThis.crypto?.randomUUID?.() || ("node-" + Date.now() + "-" + Math.random().toString(16).slice(2))).replaceAll("/", "-");
  }

  function bkFlattenLayout(nodes, prefix="") {
    const rows=[];
    for (const node of (nodes||[])) {
      const path=prefix ? prefix + "/" + node.name : node.name;
      rows.push({node,path});
      rows.push(...bkFlattenLayout(node.children||[],path));
    }
    return rows;
  }

  function bkFindParent(nodes, id, parent=null) {
    for (const node of (nodes||[])) {
      if (node.id===id) return {node,parent,nodes};
      const hit=bkFindParent(node.children||[],id,node);
      if(hit) return hit;
    }
    return null;
  }

  function bkRenderFolderLayout() {
    if(!folderSettings || !folderLayoutState) return;
    const host=document.getElementById("bk-folder-layout-tree");
    const enabled=document.getElementById("bk-folder-layout-enabled");
    enabled.checked=Boolean(folderLayoutState.structure_enabled);
    const flattened=bkFlattenLayout(folderLayoutState.layout?.nodes||[]);
    const exportSelect=document.getElementById("bk-folder-export-node");
    if(exportSelect){
      const selectedExport=flattened.find(item=>String(item.node?.role||"").toLowerCase()==="export");
      exportSelect.innerHTML='<option value="">Kein Ordner fest als Exportordner klassifiziert</option>'
        + flattened.map(item=>'<option value="'+String(item.node.id).replaceAll('"','&quot;')+'">'
          +String(item.path).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('"','&quot;')
          +'</option>').join('');
      exportSelect.value=selectedExport ? String(selectedExport.node.id) : "";
    }
    const rows=[{node:null,path:"",depth:0},...flattened.map(item=>({...item,depth:item.path.split("/").length}))];
    host.innerHTML=rows.map(item=>{
      const root=item.node===null;
      const checked=String(folderLayoutState.input_path||"")===item.path;
      if(root) return '<label class="bk-folder-input-root"><input class="bk-folder-input-radio" data-bk-input-node="" type="radio" name="bk-input-folder" value="" '+(checked?'checked':'')+'><strong>Direkt im Ereignis</strong><span style="color:var(--bk-muted)">Input</span></label>';
      const id=String(item.node.id).replaceAll('"','&quot;');
      const name=String(item.node.name).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('"','&quot;');
      const pad=Math.max(0,(item.depth-1)*20);
      return '<div style="display:grid;grid-template-columns:auto minmax(0,1fr) auto auto auto;gap:7px;align-items:center;margin-left:'+pad+'px">'
        +'<input class="bk-folder-input-radio" data-bk-input-node="'+id+'" type="radio" name="bk-input-folder" value="'+String(item.path).replaceAll('"','&quot;')+'" '+(checked?'checked':'')+' title="Als Input-Ordner">'
        +'<input data-bk-layout-name="'+id+'" value="'+name+'" aria-label="Ordnername">'
        +'<button type="button" data-bk-layout-child="'+id+'" title="Unterordner hinzufügen">＋</button>'
        +'<button type="button" data-bk-layout-remove="'+id+'" class="danger-button" title="Ordner entfernen">×</button>'
        +'<span style="color:var(--bk-muted);font-size:.82rem">'+(checked?'Input':'')+'</span></div>';
    }).join("");
    host.querySelectorAll("[data-bk-layout-name]").forEach(input=>input.addEventListener("input",()=>{
      const selected=host.querySelector('input[name="bk-input-folder"]:checked');
      const selectedNodeId=String(selected?.dataset?.bkInputNode||"");
      const found=bkFindParent(folderLayoutState.layout.nodes,input.dataset.bkLayoutName);
      if(found) found.node.name=input.value;
      if(selectedNodeId){
        const selectedRow=bkFlattenLayout(folderLayoutState.layout.nodes).find(item=>String(item.node?.id||"")===selectedNodeId);
        folderLayoutState.input_path=selectedRow?.path||"";
      }else if(selected){
        folderLayoutState.input_path=selected.value;
      }
    }));
    host.querySelectorAll("[data-bk-layout-child]").forEach(button=>button.addEventListener("click",()=>{
      const found=bkFindParent(folderLayoutState.layout.nodes,button.dataset.bkLayoutChild);
      if(found){found.node.children=found.node.children||[];found.node.children.push({id:bkNodeId(),name:"Neuer Ordner",children:[]});bkRenderFolderLayout();}
    }));
    host.querySelectorAll("[data-bk-layout-remove]").forEach(button=>button.addEventListener("click",()=>{
      const found=bkFindParent(folderLayoutState.layout.nodes,button.dataset.bkLayoutRemove);
      if(!found)return;
      const removedPath=bkFlattenLayout([found.node]).map(x=>x.path);
      const index=found.nodes.findIndex(n=>n.id===found.node.id);
      if(index>=0)found.nodes.splice(index,1);
      if(removedPath.some(p=>String(folderLayoutState.input_path||"").endsWith(p)))folderLayoutState.input_path="";
      bkRenderFolderLayout();
    }));
    host.querySelectorAll('input[name="bk-input-folder"]').forEach(radio=>radio.addEventListener("change",()=>{
      if(radio.checked){folderLayoutState.input_path=radio.value;bkRenderFolderLayout();}
    }));
  }

  async function bkLoadFolderLayout() {
    if(!folderSettings)return;
    const status=document.getElementById("bk-folder-layout-status");
    try{
      const response=await fetch("/api/settings/event-folder-layout",{cache:"no-store"});
      if(!response.ok)throw new Error("Ordnerstruktur konnte nicht geladen werden.");
      folderLayoutState=await response.json();
      bkRenderFolderLayout();
      status.textContent="";
    }catch(error){status.textContent=error.message;}
  }

  document.querySelector("[data-bk-open-settings]")?.addEventListener("click", bkLoadFolderLayout);
  document.getElementById("bk-folder-layout-enabled")?.addEventListener("change",event=>{
    if(folderLayoutState)folderLayoutState.structure_enabled=Boolean(event.target.checked);
  });
  document.getElementById("bk-folder-export-node")?.addEventListener("change",event=>{
    if(!folderLayoutState)return;
    const selected=String(event.target.value||"");
    for(const item of bkFlattenLayout(folderLayoutState.layout?.nodes||[])){
      if(String(item.node?.role||"").toLowerCase()==="export")delete item.node.role;
      if(selected && String(item.node?.id||"")===selected)item.node.role="export";
    }
  });
  document.getElementById("bk-folder-add-root")?.addEventListener("click",()=>{
    if(!folderLayoutState)return;
    folderLayoutState.layout.nodes.push({id:bkNodeId(),name:"Neuer Ordner",children:[]});
    bkRenderFolderLayout();
  });
  document.getElementById("bk-folder-layout-save")?.addEventListener("click",async()=>{
    if(!folderLayoutState)return;
    const status=document.getElementById("bk-folder-layout-status");
    status.textContent="Wird gespeichert …";
    try{
      const response=await fetch("/api/settings/event-folder-layout",{
        method:"PUT",headers:{"Content-Type":"application/json"},
        body:JSON.stringify(folderLayoutState)
      });
      const raw=await response.text();
      let data={};
      try{data=raw?JSON.parse(raw):{};}
      catch(_){throw new Error(response.ok?"Ungültige Serverantwort beim Speichern.":`Speichern fehlgeschlagen (HTTP ${response.status}).`);}
      if(!response.ok)throw new Error(data.detail||"Speichern fehlgeschlagen.");
      folderLayoutState=data;
      bkRenderFolderLayout();
      document.dispatchEvent(new CustomEvent("bibliothekar:folder-layout-updated",{detail:data}));
      status.textContent="Gespeichert. Bestehende Ereignisse bleiben unverändert.";
    }catch(error){status.textContent=error.message;}
  });

  // Quellenwahl 0.22.1: drei gleichwertige Quellkarten im Importbereich.
  const sourcePicker = document.getElementById("bk-source-picker");
  if (sourcePicker) {
    const otherPanel = document.querySelector(".other-source-panel");

    const setSourceMode = (mode) => {
      sourcePicker.querySelectorAll("[data-source-mode]").forEach(button => {
        button.classList.toggle("active", button.dataset.sourceMode === mode);
        button.setAttribute("aria-pressed", button.dataset.sourceMode === mode ? "true" : "false");
      });

      document.querySelectorAll("[data-source-pane]").forEach(pane => {
        pane.hidden = pane.dataset.sourcePane !== mode;
      });

      // Die drei Quellkarten sind echte exklusive Ansichten. Insbesondere darf
      // der SD-Kartenstatus nicht unter Laufwerk oder Ordner/Sicherung stehen.
      document.body.dataset.bkSourceMode = mode;

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

    sourcePicker.querySelectorAll("[data-source-mode]").forEach(button => {
      button.addEventListener("click", () => setSourceMode(button.dataset.sourceMode));
    });
    setSourceMode("sd");
  }

  let structureTaskAutoOpened = false;

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
              bkLibraryHref(task.href || "/events").replaceAll("&", "&amp;").replaceAll('"', "&quot;") +
              '" style="display:block;padding:10px;border-radius:10px;color:inherit;text-decoration:none"><strong style="display:block">' +
              String(task.title || "Aufgabe").replaceAll("<", "&lt;") +
              '</strong><span style="color:var(--bk-muted);font-size:.9rem">' +
              String(task.detail || "").replaceAll("<", "&lt;") +
              '</span></a>').join("")
          : '<div style="padding:10px"><strong>Keine offenen Aufgaben</strong><div style="color:var(--bk-muted);margin-top:5px">Alles erledigt.</div></div>';
      }
      const hasStructureTask = tasks.some(task => task.kind === "event_structure_change");
      if (hasStructureTask && !structureTaskAutoOpened) {
        structureTaskAutoOpened = true;
        if (taskPanel?.hasAttribute("hidden")) openTaskPanel();
      }
    } catch (_) {
      if (countNode) countNode.textContent = "–";
    }
  }
  refreshTasks();
  setInterval(refreshTasks, 30000);

  function syncShellStickyHeight() {
    const shell=document.querySelector(".bk-shell");
    if(!shell)return;
    const bridge=parseFloat(getComputedStyle(shell).getPropertyValue("--bk-page-bridge-height"))||0;
    root.style.setProperty("--bk-shell-sticky-height", Math.ceil(shell.getBoundingClientRect().height + bridge) + "px");
  }
  syncShellStickyHeight();
  window.addEventListener("resize", syncShellStickyHeight);
  if(document.fonts?.ready)document.fonts.ready.then(syncShellStickyHeight).catch(()=>{});

  document.querySelectorAll(".bk-tab").forEach(tab => {
    tab.addEventListener("click", event => {
      if (
        tab.classList.contains("active")
        || event.defaultPrevented
        || event.button !== 0
        || event.metaKey
        || event.ctrlKey
        || event.shiftKey
        || event.altKey
        || matchMedia("(prefers-reduced-motion: reduce)").matches
      ) {
        return;
      }

      const href = tab.href;
      if (!href) return;

      event.preventDefault();
      tab.classList.add("is-navigating");
      window.setTimeout(() => {
        window.location.assign(href);
      }, 105);
    });
  });

  fetch("/api/health", {cache: "no-store"}).then(r => r.ok ? r.json() : null).then(data => {
    if (!data) return;
    document.querySelectorAll("[data-bk-version]").forEach(node => {
      const deployment = data.deployment_version || data.version || "";
      const core = data.version || "";
      node.textContent = deployment && core && deployment !== core
        ? `${deployment} · Kern ${core}`
        : deployment;
    });
  }).catch(() => {});
})();
"""


def _shell_markup(active_area: str, subarea: str | None) -> str:
    active = active_area if active_area in {"import", "workspace", "archive", "assistant", "metadata"} else "import"
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
        ("assistant", None): (
            "Bibliothekar Assistent",
            "Bibliothekar fragen, Vorschläge erhalten und später Aktionen nachvollziehbar auslösen.",
        ),
        ("metadata", None): (
            "Metadatenkorrektion",
            "Metadaten aus externen Quellen prüfen und später gezielt ergänzen oder korrigieren.",
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
        dock_slot = (
            '<div id="bk-workspace-dock" class="bk-workspace-dock"></div>'
            if subarea == "captures"
            else ""
        )
        subnav = f"""
<div class="bk-workspace-subnav" data-bk-workspace-subarea="{escape(subarea or 'root')}" aria-label="Arbeitsbereich">
  <div class="bk-workspace-links">
    <a href="/workspace" class="{'active' if subarea == 'captures' else ''}">Aufnahmen</a>
    <a href="/events" class="{'active' if subarea == 'events' else ''}">Ereignisse</a>
  </div>
  {dock_slot}
</div>
"""

    if active == "workspace" and subarea == "captures":
        heading = f"""
<section class="bk-page-heading bk-capture-heading">
  <div class="bk-capture-heading-copy">
    <h1>{escape(heading_title)}</h1>
    <p>{escape(heading_subtitle)}</p>
  </div>
  <div id="bk-capture-summary-slot" class="bk-capture-summary-slot"></div>
</section>
"""
    else:
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
    <span class="bk-brand-copy">
      <span class="bk-brand-title">Bibliothekar</span>
      <span id="bk-current-library-name" class="bk-brand-library">Bibliothek …</span>
    </span>
  </a>

  <nav class="bk-tabs bk-tabs-active-{active}" aria-label="Hauptbereiche">
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
    <a class="bk-shell-button bk-assistant-button{' active' if active == 'assistant' else ''}" href="/assistant" aria-label="Bibliothekar Assistent" title="Bibliothekar Assistent">
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3l1.5 4.5L18 9l-4.5 1.5L12 15l-1.5-4.5L6 9l4.5-1.5L12 3z"/><path d="M18.5 15.5l.8 2.2 2.2.8-2.2.8-.8 2.2-.8-2.2-2.2-.8 2.2-.8.8-2.2z"/></svg>
    </a>
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
      <a href="/metadata-correction">
        <span class="bk-menu-icon" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M4 5h16v14H4z"/><path d="M8 9h8M8 13h5M16.5 13.5l2 2M18.5 13.5l-2 2"/></svg></span>
        <span>Metadatenkorrektion</span>
      </a>
      <div class="bk-menu-separator"></div>
      <button type="button" data-bk-open-about>
        <span class="bk-menu-icon" aria-hidden="true"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 10v6M12 7h.01"/></svg></span>
        <span>Über Bibliothekar</span>
      </button>
    </div>
  </div>
</header>
{subnav}
{heading}

<dialog id="bk-settings-dialog" class="bk-dialog">
  <div class="bk-dialog-body">
    <div class="bk-dialog-head">
      <div><h2>Einstellungen</h2><div style="color:var(--bk-muted);margin-top:5px">Darstellung, Sprache, Ereignisordner und Bibliotheken</div></div>
      <button class="bk-dialog-close" type="button" data-bk-dialog-close aria-label="Schließen">×</button>
    </div>
    <div class="bk-settings-tabs" role="tablist" aria-label="Einstellungsbereiche">
      <button type="button" class="active" data-bk-settings-area="appearance">Erscheinungsbild</button>
      <button type="button" data-bk-settings-area="general">Allgemein</button>
      <button type="button" data-bk-settings-area="folders">Ereignisordner</button>
      <button type="button" data-bk-settings-area="libraries">Bibliotheken</button>
    </div>

    <div class="bk-settings-panel" data-bk-settings-panel="appearance">
      <section class="bk-settings-group">
        <strong>Erscheinungsbild</strong>
        <div class="bk-choice-row">
          <button type="button" data-bk-theme-choice="light">Hell</button>
          <button type="button" data-bk-theme-choice="dark">Dunkel</button>
          <button type="button" data-bk-theme-choice="system">System</button>
        </div>
      </section>
    </div>

    <div class="bk-settings-panel" data-bk-settings-panel="general" hidden>
      <section class="bk-settings-group">
        <strong>Sprache</strong>
        <div class="bk-choice-row">
          <button type="button" class="active">Deutsch</button>
          <button type="button" disabled title="Die vollständige englische Oberfläche folgt in einem eigenen Lokalisierungsschritt.">English</button>
        </div>
        <div class="bk-language-note">Die Oberfläche ist vollständig deutsch. Englisch bleibt vorbereitet und wird erst aktiviert, wenn alle dynamischen Texte mitübersetzt sind.</div>
      </section>
    </div>

    <div class="bk-settings-panel" data-bk-settings-panel="folders" hidden>
      <section class="bk-settings-group" id="bk-folder-layout-settings">
        <div class="bk-folder-layout-heading">
          <div><strong>Ereignisordner</strong><div style="color:var(--bk-muted);margin-top:4px">Vorlage nur für neue Ereignisse</div></div>
          <label class="bk-folder-layout-toggle"><input id="bk-folder-layout-enabled" type="checkbox"> <span>Unterordner standardmäßig erstellen</span></label>
        </div>
        <div id="bk-folder-layout-tree" style="display:grid;gap:7px;margin-top:12px"></div>
        <label style="display:grid;gap:6px;margin-top:11px">
          <span><strong>Exportordner</strong> <span style="color:var(--bk-muted)">· optional</span></span>
          <select id="bk-folder-export-node">
            <option value="">Kein Ordner fest als Exportordner klassifiziert</option>
          </select>
          <span style="color:var(--bk-muted);font-size:.86rem;line-height:1.35">Dateien in diesem Ordner gelten als Exporte, auch wenn der Ordner z. B. „Master“ heißt. Die Einstellung wird wie die Ordnerstruktur für neue Ereignisse eingefroren.</span>
        </label>
        <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:10px">
          <button id="bk-folder-add-root" type="button">＋ Ordner</button>
          <button id="bk-folder-layout-save" type="button" class="bk-positive-action">Speichern</button>
        </div>
        <div id="bk-folder-layout-status" style="color:var(--bk-muted);margin-top:8px"></div>
      </section>
    </div>

    <div class="bk-settings-panel" data-bk-settings-panel="libraries" hidden>
      <section class="bk-settings-group" id="bk-library-settings">
        <div><strong>Bibliotheken</strong><div style="color:var(--bk-muted);margin-top:4px">Anzeigenamen und registrierte Mountpfade verwalten</div></div>
        <div id="bk-library-management-list" class="bk-library-list"></div>
        <details class="bk-library-add-card">
          <summary>Bibliothek hinzufügen</summary>
          <div class="bk-library-form">
            <div style="color:var(--bk-muted);font-size:.88rem">Die Host Paths werden zuerst in TrueNAS eingebunden. Hier werden ausschließlich die Container-Mountpfade eingetragen.</div>
            <label><span>Anzeigename</span><input id="bk-new-library-name" placeholder="z. B. Business"></label>
            <label><span>Arbeitsbereich · RW</span><input id="bk-new-library-work" placeholder="/libraries/business/workspace"></label>
            <label><span>Archiv · RO</span><input id="bk-new-library-archive" placeholder="/libraries/business/archive"></label>
            <div class="bk-library-actions">
              <button id="bk-new-library-check" type="button">Prüfen</button>
              <button id="bk-new-library-create" type="button" class="bk-positive-action" disabled>Bibliothek hinzufügen</button>
            </div>
            <div id="bk-new-library-status" class="bk-library-status"></div>
          </div>
        </details>
      </section>
    </div>
  </div>
</dialog>

<dialog id="bk-library-dialog" class="bk-dialog">
  <div class="bk-dialog-body">
    <div class="bk-dialog-head">
      <div><h2>Bibliothek wechseln</h2><div style="color:var(--bk-muted);margin-top:5px">Jeder Tab kann unabhängig in einer anderen Bibliothek arbeiten.</div></div>
      <button class="bk-dialog-close" type="button" data-bk-dialog-close aria-label="Schließen">×</button>
    </div>
    <div id="bk-library-switch-list" class="bk-library-switch-list">
      <div style="color:var(--bk-muted)">Bibliotheken werden geladen …</div>
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
    <p style="color:var(--bk-muted)">Version <span data-bk-version>0.32.3 · Kern 0.28.7</span></p>
  </div>
</dialog>


"""


def apply_shell(html: str, *, active_area: str, subarea: str | None = None) -> str:
    result = html
    result = result.replace(
        "</head>",
        f"<style>{BIBLIOTHEKAR_CSS}</style>\n"
        f"<style>{BIBLIOTHEKAR_0310_CSS}</style>\n"
        f"<style>{BIBLIOTHEKAR_0311_CSS}</style>\n</head>",
        1,
    )
    area = active_area if active_area in {"import", "workspace", "archive", "assistant", "metadata"} else "import"
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

