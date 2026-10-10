"""Client-only, non-destructive UI localisation for Bibliothekar.

Do not translate stored paths, IDs, event.json payloads or filesystem data.
The user interface can be switched without changing the database.
"""
from __future__ import annotations

import json

UI_TRANSLATIONS = {
  "Einstellungen": "Settings",
  "Darstellung, Sprache, Ordner, Speicherpfade und Bibliotheken": "Appearance, language, folders, storage paths and libraries",
  "Erscheinungsbild": "Appearance",
  "Allgemein": "General",
  "Ereignisordner": "Event folders",
  "Pfade": "Paths",
  "Bibliotheken": "Libraries",
  "Sprache": "Language",
  "Sitzung": "Session",
  "Hell": "Light",
  "Dunkel": "Dark",
  "System": "System",
  "Deutsch": "Deutsch",
  "English": "English",
  "Abmelden": "Sign out",
  "Schließen": "Close",
  "Zurück": "Back",
  "Weiter": "Continue",
  "Abbrechen": "Cancel",
  "Speichern": "Save",
  "Prüfen": "Verify",
  "Bearbeiten": "Edit",
  "Anwenden": "Apply",
  "Entfernen": "Remove",
  "Löschen": "Delete",
  "Hinzufügen": "Add",
  "Erstellen": "Create",
  "Sichern · Ordnen · Bewahren": "Back up · Organize · Preserve",
  "Bibliothekar organisiert Kameraimporte sicher vom ersten Einlesen bis in die dauerhafte Kamerabibliothek.": "Bibliothekar safely organizes camera imports from initial ingestion to the permanent camera library.",
  "Import & Prüfung": "Import & Review",
  "Import &amp; Prüfung": "Import & Review",
  "Import und Prüfung": "Import and Review",
  "Arbeitsbereich": "Workspace",
  "Ereignisse": "Events",
  "Ereignisübersicht": "Event overview",
  "Sortieren": "Sort",
  "Archiv": "Archive",
  "Kamerabibliothek": "Camera library",
  "Archivprüfung": "Archive verification",
  "Papierkorb": "Trash",
  "Metadatenkorrektur": "Metadata correction",
  "Aufgaben": "Tasks",
  "Menü": "Menu",
  "Menü öffnen": "Open menu",
  "Dateibestand": "File inventory",
  "Einstellungsbereiche": "Settings sections",
  "Ordnerstruktur": "Folder structure",
  "Vorlage für neue Ereignisse": "Template for new events",
  "Unterordner standardmäßig erstellen": "Create subfolders by default",
  "Exportordner": "Export folder",
  "· optional": "· optional",
  "Kein Ordner fest als Exportordner klassifiziert": "No folder explicitly classified as an export folder",
  "Dateien in diesem Ordner gelten als Exporte. Die Einstellung wird für neue Ereignisse eingefroren.": "Files in this folder count as exports. This setting is locked in for new events.",
  "＋ Ordner": "+ Folder",
  "Normale Ereignisse": "Regular events",
  "Standardbenennung": "Default naming",
  "Jahr einbeziehen": "Include year",
  "Uhrzeit einbeziehen": "Include time",
  "Von–bis im Namen": "Include date range in name",
  "Unterereignisse": "Subevents",
  "Standardmäßig verwenden": "Use by default",
  "Sammelordner": "Collection folders",
  "bisher „Ohne Ereignis“": "previously “No Event”",
  "Ohne Ereignis": "No Event",
  "Ohne Datum": "Undated",
  "Ohne_Datum": "Undated",
  "Bezeichnung für Sammelordner": "Label for collection folders",
  "Vorschau": "Preview",
  "Benennung speichern": "Save naming",
  "Verwaltete Pfade": "Managed paths",
  "Ordner innerhalb des gemeinsamen Kamera-Arbeitsbereichs": "Folders within the shared camera workspace",
  "SD-Kartensicherungen": "SD Card Backups",
  "Bibliotheks-Arbeitsbereiche": "Library Workspaces",
  "Arbeitsbereiche": "Workspaces",
  "Workspace-Mount:": "Workspace mount:",
  "TrueNAS stellt nur diesen RW-Stamm bereit. Bibliothekar verwaltet die folgenden Unterordner.": "TrueNAS provides only this read-write root. Bibliothekar manages the following subfolders.",
  "Pfade speichern": "Save paths",
  "Anzeigenamen, Arbeitsbereiche und einzeln gemountete Archive verwalten": "Manage display names, workspaces and individually mounted archives",
  "Bibliothek hinzufügen": "Add library",
  "Anzeigename": "Display name",
  "Bibliotheksname": "Library name",
  "Arbeitsbereich · optional": "Workspace · optional",
  "Arbeitsbereich · RW": "Workspace · read/write",
  "Archiv · eigener RO-Mount": "Archive · separate read-only mount",
  "Leer = automatisch im gemeinsamen Workspace": "Empty = create automatically in shared workspace",
  "Hauptbibliothek": "Main library",
  "Bibliothek": "Library",
  "aktuell": "current",
  "Aktiv": "Active",
  "Inaktiv": "Inactive",
  "Öffnen": "Open",
  "Deaktivieren": "Deactivate",
  "Aktivieren": "Activate",
  "Bibliothek wechseln": "Switch library",
  "Jeder Tab kann unabhängig in einer anderen Bibliothek arbeiten.": "Each tab can work in a different library independently.",
  "Bibliotheken werden geladen …": "Loading libraries…",
  "Keine aktive Bibliothek gefunden.": "No active library found.",
  "Mountpfade werden geprüft …": "Checking mount paths…",
  "Prüfung PASS": "Verification passed",
  "Prüfung fehlgeschlagen.": "Verification failed.",
  "Anfrage fehlgeschlagen.": "Request failed.",
  "Ungültige Serverantwort.": "Invalid server response.",
  "Ordner entfernen": "Remove folder",
  "Unterordner hinzufügen": "Add subfolder",
  "Direkt im Ereignis": "Directly in event",
  "Als Input-Ordner": "As input folder",
  "Ereignisname": "Event name",
  "Ereignis": "Event",
  "Unterereignis": "Subevent",
  "Start": "Start",
  "Ende": "End",
  "Datum": "Date",
  "Uhrzeit": "Time",
  "Zeitraum": "Date range",
  "Zeitbereich": "Time range",
  "Jahr": "Year",
  "Monat": "Month",
  "Tag": "Day",
  "Dateien": "Files",
  "Datei": "File",
  "Ordner": "Folder",
  "Tagesordner": "Day folder",
  "Tagessegment": "Day segment",
  "Aufnahmen": "Photos",
  "Aufnahme": "Photo",
  "Dateifamilie": "File family",
  "Familien": "Families",
  "Familie": "Family",
  "Sortierung": "Sorting",
  "Status": "Status",
  "Größe": "Size",
  "Name": "Name",
  "Anzahl": "Count",
  "Ergebnis": "Result",
  "Details": "Details",
  "Alle": "All",
  "Sortiert": "Sorted",
  "Export": "Export",
  "Quellen": "Sources",
  "Quelle": "Source",
  "Neue Sicherung": "New backup",
  "Sicherung": "Backup",
  "Sicherungen": "Backups",
  "SD-Karte": "SD card",
  "SD-Karten": "SD cards",
  "Ordnerimport": "Folder import",
  "SD-Kartenimport": "SD card import",
  "Import": "Import",
  "Import starten": "Start import",
  "Dateien prüfen": "Verify files",
  "Metadaten": "Metadata",
  "Abgeschlossen": "Completed",
  "Abgeschlossen.": "Completed.",
  "Ausstehend": "Pending",
  "Geplant": "Planned",
  "Angewendet": "Applied",
  "Archiviert": "Archived",
  "Fehlgeschlagen": "Failed",
  "Läuft": "Running",
  "Wird geladen …": "Loading…",
  "Laden …": "Loading…",
  "Bitte warten …": "Please wait…",
  "Erneut prüfen": "Verify again",
  "Noch nicht geprüft": "Not yet verified",
  "Vollständig geprüft": "Fully verified",
  "Bestand prüfen": "Verify inventory",
  "Datei prüfen": "Verify file",
  "Dateibestand und Zuordnung erneut prüfen": "Recheck file inventory and assignments",
  "Ereignisse und Dateibestand erneut vollständig prüfen": "Recheck all events and files",
  "Die zuletzt geänderten Ereignisse werden angezeigt.": "Showing recently modified events.",
  "Neu-Zuordnung": "Reassignment",
  "Neu zuordnen": "Reassign",
  "Neu-Zuordnung wird geladen …": "Loading reassignment…",
  "Herausfallende Tages-/Zeitsegmente neu zuordnen": "Reassign days and time segments that no longer fit",
  "Keine Datei bleibt ohne Ziel.": "Every file retains a destination.",
  "Manuelle Ereignisänderung": "Manual event change",
  "Der reale Dateisystemzustand wird mit Bibliothekar abgeglichen.": "Comparing the actual filesystem state with Bibliothekar.",
  "Änderung wird geladen …": "Loading change…",
  "Änderungsauftrag": "Change request",
  "Änderungsauftrag wird geladen …": "Loading change request…",
  "Änderung verwerfen": "Discard change",
  "Verwerfen": "Discard",
  "Rückänderung": "Reversal",
  "Wiederherstellen": "Restore",
  "Rückänderung vorbereiten": "Prepare reversal",
  "Archivänderung": "Archive change",
  "Archivänderungsauftrag": "Archive change request",
  "Archiv · Schritt 1 von 2": "Archive · Step 1 of 2",
  "Prüffälle": "Items requiring review",
  "Geplante Änderungen": "Planned changes",
  "Alle aktiven Sicherungen": "All active backups",
  "Alle geplanten Ereignisse sind standardmäßig ausgewählt.": "All planned events are selected by default.",
  "Alle geplanten Ereignisse anwenden": "Apply all planned events",
  "Bereits geprüft": "Already verified",
  "Prüfung starten": "Start verification",
  "Keine offenen Ereignisse zur Archivprüfung.": "No events are awaiting archive verification.",
  "Offene Prüfungen": "Pending checks",
  "Zur Archivprüfung": "Go to archive verification",
  "Papierkorb wird geprüft …": "Checking trash…",
  "Der Papierkorb ist leer.": "Trash is empty.",
  "Der Ordner ist leer.": "The folder is empty.",
  "Keine Dateien oder Ordner im Papierkorb.": "No files or folders in trash.",
  "Papierkorb wird endgültig geleert …": "Emptying trash permanently…",
  "PAPIERKORB ENDGÜLTIG LEEREN": "PERMANENTLY EMPTY TRASH",
  "Papierkorb wurde vollständig geleert und der Datenbankbestand synchronisiert.": "Trash was emptied completely and the database inventory synchronized.",
  "Links eine Datei auswählen.": "Select a file on the left.",
  "Auswählen": "Select",
  "Alle auswählen": "Select all",
  "Mehrere Einträge lassen sich auch mit Umschalt (Shift) auswählen.": "Hold Shift to select multiple items.",
  "Anwenden und in Tagesbestand übernehmen": "Apply and move to daily inventory",
  "Übernehmen": "Accept",
  "Metadaten korrigieren": "Correct metadata",
  "Zeit korrigieren": "Correct time",
  "Dateien im Ordner Mehrfachkorrektur": "Files in batch correction folder",
  "Wird geladen": "Loading",
  "Arbeitet …": "Processing…",
  "Erneut versuchen": "Try again",
  "Unbekannter Fehler": "Unknown error",
  "Fehler": "Error",
  "Warnung": "Warning",
  "Hinweis": "Notice",
  "Information": "Information",
  "Erfolg": "Success",
  "Bestätigen": "Confirm",
  "Bestätigung": "Confirmation",
  "Ignorieren": "Dismiss",
  "Quittieren": "Acknowledge",
  "Erledigt": "Done",
  "Offen": "Open",
  "Abbrechen?": "Cancel?",
  "Weiter?": "Continue?",
  "Ja": "Yes",
  "Nein": "No",
  "OK": "OK",
  "Neustart": "Restart",
  "Später zuordnen": "Assign Later",
  "Freigewordene Archivdateien": "Released Archive Files",
  "Mehrfachkorrektur": "Batch Correction",
  "Technische ID:": "Technical ID:",
  "Datenbank": "Database",
  "Einstellungen speichern": "Save settings",
  "Speichern und schließen": "Save and close",
  "Seite aktualisieren": "Refresh page",
  "Aktualisieren": "Refresh",
  "Aktuelle Bibliothek": "Current library",
  "Archiv prüfen": "Verify archive",
  "Sortierung prüfen": "Verify sorting",
  "Ereignis bearbeiten": "Edit event",
  "Ereignis löschen": "Delete event",
  "Neues Ereignis": "New event",
  "Ereignis erstellen": "Create event",
  "Ereignis anwenden": "Apply event",
  "Unterereignis hinzufügen": "Add subevent",
  "Geprüfte Dateien": "Verified files",
  "Fehlende Dateien": "Missing files",
  "Fehlende Datei": "Missing file",
  "Datei falsch zugeordnet": "File assigned to wrong location",
  "Dateiposition ist mehrdeutig": "File location is ambiguous",
  "Ereignisordner extern gelöscht": "Event folder deleted externally",
  "Ereignis-Unterordner extern gelöscht": "Event subfolder deleted externally",
  "Tages-/Zeitordner gelöscht": "Day/time folder deleted",
  "Mögliche Archivübernahme erkannt": "Potential archive transfer detected",
  "Gemeinsam zugeordnete Datei fehlt": "Shared assigned file is missing",
  "Die Aufgabe „Dateizuordnung prüfen“ bleibt offen": "The “Review file assignment” task remains open",
  "Dateizuordnung prüfen": "Review file assignment",
  "Der aktuelle Bestand wird geprüft.": "Checking current inventory.",
  "Zu bestehendem Ohne Ereignis": "To existing No Event",
  "Bestehendes Ereignis erweitern": "Extend existing event",
  "Bestehende „Ohne Ereignis“-Sammlung": "Existing “No Event” collection",
  "Präfix: an": "Prefix: on",
  "Präfix: aus": "Prefix: off",
  "Keine Treffer": "No results",
  "Keine Ergebnisse": "No results",
  "Suchen": "Search",
  "Filter": "Filter",
  "Zurücksetzen": "Reset",
  "Wert": "Value",
  "Datei auswählen": "Choose file",
  "Neue Dateien": "New files",
  "fehlende Dateien": "missing files",
  "Dateien fehlen": "Files are missing",
  "Speichern erfolgreich": "Saved successfully",
  "Keine Änderungen": "No changes",
  "Gespeichert": "Saved",
  "Nicht eingerichtet": "Not configured",
  "Erste Bibliothek einrichten": "Set up your first library",
  "Bibliothek prüfen und anlegen": "Check and create library",
  "Bibliothek wird geprüft …": "Checking library…",
  "Bibliothek eingerichtet. Bibliothekar wird geöffnet …": "Library created. Opening Bibliothekar…",
  "Bibliothekar ist noch nicht eingerichtet. Bitte zuerst eine Bibliothek anlegen.": "Bibliothekar has not been set up. Create a library first.",
  "Abmelden?": "Sign out?",
  "Sitzung abgelaufen": "Session expired",
  "Anmelden": "Sign in",
  "Passwort": "Password",
  "Administratorpasswort": "Administrator password",
  "Falsches Passwort": "Incorrect password",
  "Prüfung erfolgreich": "Verification successful",
  "Prüfung läuft …": "Verification in progress…",
  "Dateien werden geprüft …": "Checking files…",
  "Bitte zuerst prüfen": "Verify first",
  "Zuordnung": "Assignment",
  "Zugeordnet": "Assigned",
  "Nicht zugeordnet": "Unassigned",
  "Abweichung": "Discrepancy",
  "Korrigieren": "Correct",
  "Erneut laden": "Reload",
  "Standort": "Location",
  "Dateipfad": "File path",
  "Zielordner": "Destination folder",
  "Quellordner": "Source folder",
  "Schritt": "Step",
  "von": "of",
  "Dateisystem": "Filesystem",
  "Prüfergebnis": "Verification result",
  "Anzahl Dateien": "Number of files",
  "Dateien gesamt": "Total files",
  "Quelle auswählen": "Choose source"
} 

UI_PATTERNS = [
  [
    "^([0-9]+) Gruppen ausgewählt$",
    "$1 groups selected"
  ],
  [
    "^([0-9]+) Familien$",
    "$1 families"
  ],
  [
    "^([0-9]+) Dateien$",
    "$1 files"
  ],
  [
    "^([0-9]+) Datei$",
    "$1 file"
  ],
  [
    "^([0-9]+) neue Dateien$",
    "$1 new files"
  ],
  [
    "^([0-9]+) fehlende Dateien$",
    "$1 missing files"
  ],
  [
    "^([0-9]+) von ([0-9]+) Dateien$",
    "$1 of $2 files"
  ],
  [
    "^Archiv · Schritt ([0-9]+) von ([0-9]+)$",
    "Archive · Step $1 of $2"
  ],
  [
    "^Prüfung fehlgeschlagen: (.+)$",
    "Verification failed: $1"
  ],
  [
    "^Fehler: (.+)$",
    "Error: $1"
  ],
  [
    "^Verwerfen fehlgeschlagen: (.+)$",
    "Discard failed: $1"
  ],
  [
    "^Arbeitsbereiche: (.+)$",
    "Workspaces: $1"
  ],
  [
    "^Tagessegment ([0-9]+) · (.+)$",
    "Day segment $1 · $2"
  ]
]

I18N_UI_JS = r"""
(function () {
  "use strict";
  const dictionary = __DICTIONARY__;
  const patterns = __PATTERNS__.map(([source, target]) => [new RegExp(source, "u"), target]);
  const key = "bibliothekar-language";
  let locale = "en";
  try { locale = localStorage.getItem(key) === "de" ? "de" : "en"; } catch (_) {}
  const originalText = new WeakMap();
  const lastText = new WeakMap();
  const originalAttrs = new WeakMap();
  const lastAttrs = new WeakMap();
  const attributes = ["title", "aria-label", "placeholder", "alt", "data-help"];
  const ignored = "script,style,textarea,code,pre,kbd,samp,[contenteditable],[data-bk-preserve-language]";
  function tr(value) {
    if (typeof value !== "string" || !value) return value;
    const core = value.trim();
    if (!core) return value;
    let result = dictionary[core];
    if (result === undefined) {
      for (const [pattern, translation] of patterns) {
        if (pattern.test(core)) { result = core.replace(pattern, translation); break; }
      }
    }
    if (result === undefined) return value;
    const lead = value.slice(0, value.indexOf(core));
    return lead + result + value.slice(value.indexOf(core) + core.length);
  }
  function eligible(node) {
    const parent = node.nodeType === Node.TEXT_NODE ? node.parentElement : node;
    return !!parent && !parent.closest(ignored);
  }
  function translateText(node) {
    if (!eligible(node)) return;
    const observed = node.nodeValue;
    const last = lastText.get(node);
    if (observed !== last) originalText.set(node, observed);
    const source = originalText.get(node) ?? observed;
    const desired = locale === "en" ? tr(source) : source;
    lastText.set(node, desired);
    if (observed !== desired) node.nodeValue = desired;
  }
  function translateAttributes(element) {
    if (!eligible(element)) return;
    let originals = originalAttrs.get(element);
    if (!originals) { originals = new Map(); originalAttrs.set(element, originals); }
    let latest = lastAttrs.get(element);
    if (!latest) { latest = new Map(); lastAttrs.set(element, latest); }
    for (const name of attributes) {
      if (!element.hasAttribute(name)) continue;
      const observed = element.getAttribute(name);
      if (observed !== latest.get(name)) originals.set(name, observed);
      const source = originals.get(name) ?? observed;
      const desired = locale === "en" ? tr(source) : source;
      latest.set(name, desired);
      if (desired !== observed) element.setAttribute(name, desired);
    }
  }
  function walk(node) {
    if (!node) return;
    if (node.nodeType === Node.TEXT_NODE) { translateText(node); return; }
    if (node.nodeType !== Node.ELEMENT_NODE || !eligible(node)) return;
    translateAttributes(node);
    const walker = document.createTreeWalker(node, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT);
    while (walker.nextNode()) {
      const item = walker.currentNode;
      if (item.nodeType === Node.TEXT_NODE) translateText(item);
      else translateAttributes(item);
    }
  }
  let scheduled = false;
  const queue = new Set();
  function flush() {
    scheduled = false;
    for (const node of queue) walk(node);
    queue.clear();
  }
  function schedule(node) {
    queue.add(node);
    if (!scheduled) { scheduled = true; queueMicrotask(flush); }
  }
  function updateChoiceButtons() {
    document.querySelectorAll("[data-bk-language-choice]").forEach(button => {
      const active = button.dataset.bkLanguageChoice === locale;
      button.classList.toggle("active", active);
      button.setAttribute("aria-pressed", String(active));
    });
  }
  function setLocale(next) {
    if (next !== "de" && next !== "en") return;
    locale = next;
    document.documentElement.lang = next;
    document.documentElement.dataset.bkLocale = next;
    try { localStorage.setItem(key, next); } catch (_) {}
    if (document.body) walk(document.body);
    updateChoiceButtons();
    window.dispatchEvent(new CustomEvent("bk-language-changed", {detail: {locale: next}}));
  }
  window.BibliothekarI18n = Object.freeze({
    t: (german) => locale === "en" ? tr(String(german)) : String(german),
    getLocale: () => locale,
    setLocale,
  });
  document.documentElement.lang = locale;
  document.documentElement.dataset.bkLocale = locale;
  function init() {
    document.querySelectorAll("[data-bk-language-choice]").forEach(button => {
      button.addEventListener("click", () => setLocale(button.dataset.bkLanguageChoice));
    });
    updateChoiceButtons();
    walk(document.body);
    const observer = new MutationObserver(mutations => {
      for (const mutation of mutations) {
        if (mutation.type === "characterData") schedule(mutation.target);
        else if (mutation.type === "attributes") schedule(mutation.target);
        else for (const node of mutation.addedNodes) schedule(node);
      }
    });
    observer.observe(document.body, {
      subtree: true, childList: true, characterData: true,
      attributes: true, attributeFilter: attributes,
    });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init, {once: true});
  else init();
})();
""".replace("__DICTIONARY__", json.dumps(UI_TRANSLATIONS, ensure_ascii=False)).replace(
    "__PATTERNS__", json.dumps(UI_PATTERNS, ensure_ascii=False)
)
