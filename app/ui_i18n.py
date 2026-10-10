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

# Additional contextual messages from archive changes, sorting and reversals.
UI_TRANSLATIONS.update({
  "Suche nach Name, Datum oder Sicherung …": "Search by name, date or backup…",
  "Änderung fortsetzen": "Continue editing",
  "Gemeinsame Nachsortierung öffnen": "Open combined resort plan",
  "Offene Änderung dieser Sicherung zuerst abschließen oder verwerfen": "Complete or discard the pending change for this backup first",
  "Größe abweichend": "Size mismatch",
  "Änderungen": "Changes",
  "Dateien, Ziele und Konflikte werden rein lesend geprüft …": "Checking files, destinations and conflicts in read-only mode…",
  "Bitte warten. Der Prüfungsplan wird vorbereitet …": "Preparing verification plan…",
  "Änderungen anwenden": "Apply changes",
  "Diese Applied-Änderung muss jetzt angewendet oder vollständig verworfen werden.": "This applied-event change must now be applied or fully discarded.",
  "Die Änderung ist blockiert. Sie kann nur korrigiert/verworfen werden; nichts wurde physisch verändert.": "The change is blocked. It can only be corrected or discarded; no files were changed.",
  "Die rein lesende Prüfung ist ohne Blocker abgeschlossen.": "Read-only verification completed without blockers.",
  "Die Planung ist blockiert. Es wurde nichts verändert.": "The plan is blocked. Nothing was changed.",
  "Neue Ordner": "New folders",
  "Dateien verändert: nein": "Files modified: no",
  "Ordner verändert: nein": "Folders modified: no",
  "Datenbank verändert: nein": "Database modified: no",
  "Keine zusätzlichen Hinweise.": "No additional notices.",
  "Hinweis zur bestätigten Sortierung": "About confirmed sorting",
  "SHA-256 geprüft": "SHA-256 verified",
  "Sortierung vollständig angewendet und geprüft.": "Sorting applied and verified completely.",
  "Sortierlauf wurde nicht abgeschlossen.": "Sorting job did not complete.",
  "Sortierung wurde nicht abgeschlossen.": "Sorting did not complete.",
  "Der bestätigte Sortierplan ist nicht mehr verfügbar.": "The confirmed sorting plan is no longer available.",
  "Ein blockierter Sortierplan kann nicht angewendet werden.": "A blocked sorting plan cannot be applied.",
  "Die ausdrückliche Bestätigung fehlt.": "Explicit confirmation is missing.",
  "Sortierlauf wird angelegt …": "Creating sorting job…",
  "Tag": "Day",
  "Monat und Jahr": "Month and year",
  "Ereignis öffnen": "Open event",
  "Nur-Lesen-Ansicht der aktuell in der Datenbank gespeicherten Definition und Dateizuordnung.": "Read-only view of the event definition and file assignments stored in the database.",
  "Nicht erhalten": "Do not preserve",
  "Nicht erstellen": "Do not create",
  "Datenbankzustand wird geladen …": "Loading database state…",
  "Archivierter Bestand: Die App plant die Änderung vollständig, die Kamerabibliothek bleibt read-only.": "Archived inventory: the app prepares the entire change while the camera library remains read-only.",
  "Die Dateizugehörigkeit ergibt sich ausschließlich aus Datum und Uhrzeit. Einzelne Familien können nicht manuell herausgenommen werden.": "File membership is determined solely by date and time. Individual families cannot be excluded manually.",
  "Änderungen speichern": "Save changes",
  "＋ Tagessegment hinzufügen": "+ Add day segment",
  "Unterereignis hinzufügen": "Add subevent",
  "Im Oberereignis ist hinter dem letzten Unterereignis kein weiterer Zeitraum frei. Ändere zuerst dessen Endzeit.": "No free time remains in the parent event after the last subevent. Adjust its end time first.",
  "Mindestens ein Unterereignis enthält aktuell keine passenden Dateifamilien.": "At least one subevent has no matching file families.",
  "Mindestens ein „Ohne Ereignis“-Zeitsegment muss erhalten bleiben.": "At least one “No Event” time segment must remain.",
  "Archivänderung wird vorbereitet …": "Preparing archive change…",
  "IST- und SOLL-Zustand werden berechnet. Die Kamerabibliothek bleibt dabei unverändert.": "Calculating actual and target states. The camera library remains unchanged.",
  "Bitte einen Moment warten.": "Please wait a moment.",
  "Manueller Änderungsauftrag wird berechnet …": "Preparing manual change request…",
  "Änderungsauftrag erstellt. Die Kamerabibliothek wurde nicht verändert.": "Change request created. The camera library was not modified.",
  "Archivänderung konnte nicht vorbereitet werden.": "Could not prepare archive change.",
  "Ereignisänderungen werden vorbereitet …": "Preparing event changes…",
  "Applied-Änderung vorbereitet. Jetzt anwenden oder vollständig verwerfen.": "Applied-event change prepared. Apply or discard it completely.",
  "Änderung gespeichert. Bitte den angezeigten Nachsortierplan prüfen und ausdrücklich bestätigen.": "Change saved. Review and explicitly confirm the displayed resort plan.",
  "Gemeinsame Planänderung gespeichert.": "Combined plan change saved.",
  "Ereignis wurde gespeichert.": "Event saved.",
  "Offene Familien und Ziele werden geladen …": "Loading pending families and destinations…",
  "Neu-Zuordnung vollständig. Bitte den Nachsortierplan prüfen und ausdrücklich bestätigen.": "Reassignment complete. Review and explicitly confirm the resort plan.",
  "Ereignis gespeichert und alle herausfallenden Familien neu zugeordnet.": "Event saved; all displaced families have been reassigned.",
  "In Aufnahmen öffnen": "Open in Photos",
  "Ereignis wurde nicht gefunden.": "Event not found.",
  "Änderungen verwerfen": "Discard changes",
  "Alte und neue Pfade werden rein lesend geprüft …": "Checking old and new paths in read-only mode…",
  "Dateien, Ziele und Konflikte werden geprüft …": "Checking files, destinations and conflicts…",
  "Änderungsplan konnte nicht berechnet werden.": "Could not calculate change plan.",
  "Rein lesende Prüfung wird berechnet …": "Preparing read-only verification…",
  "Quellen, Ziele und Konflikte werden geprüft …": "Checking sources, destinations and conflicts…",
  "Die Planung wird sofort entfernt; Dateien und Ordner bleiben unverändert.": "The plan will be removed immediately; files and folders remain unchanged.",
  "Löschauftrag wird vorbereitet …": "Preparing deletion request…",
  "Der manuelle Löschauftrag wird vorbereitet …": "Preparing manual deletion request…",
  "Der Archivbestand wird rein lesend geprüft …": "Checking archive inventory in read-only mode…",
  "Manueller Löschauftrag erstellt. Die Kamerabibliothek wurde nicht verändert.": "Manual deletion request created. The camera library was not changed.",
  "Löschung vorbereitet. Jetzt anwenden oder vollständig verwerfen.": "Deletion prepared. Apply or discard it completely.",
  "Archivänderung wird verworfen …": "Discarding archive change…",
  "Änderung wird verworfen …": "Discarding change…",
  "Der Verwerfauftrag wurde nicht angenommen.": "Discard request was not accepted.",
  "Verwerfauftrag angenommen. Er läuft unabhängig von dieser Seite im Hintergrund.": "Discard request accepted. It will run independently in the background.",
  "Verwerfen fehlgeschlagen. Bitte erneut versuchen.": "Discard failed. Please try again.",
  "Keine Änderungsaufträge vorhanden.": "No change requests.",
  "Änderungsaufträge": "Change requests",
  "Ereignis:": "Event:",
  "Geändert:": "Modified:",
  "Rückänderungsauftrag": "Reversal request",
  "Rückänderung läuft": "Reversal in progress",
  "Prüfen & Verwerfen": "Verify & discard",
  "Finder-Rückarbeit": "Manual Finder restoration",
  "Ursprüngliches Ziel": "Original destination",
  "SSD-Rückbestand": "SSD restoration inventory",
  "Rückarbeit": "Restoration work",
  "Rückarbeit prüfen · weiter": "Verify restoration · continue",
  "Rückänderung prüfen": "Verify reversal",
  "Noch nicht geprüft.": "Not yet verified.",
  "Ursprungszustand bestätigen & Änderung verwerfen": "Confirm original state & discard change",
  "Notausstieg bei unmöglicher Rückänderung": "Emergency exit for an impossible reversal",
  "Abbrechen erzwingen · manuelle Klärung": "Force cancellation · manual review",
  "Warum ist die Wiederherstellung nicht möglich?": "Why is restoration not possible?",
  "✓ Rückänderung geprüft": "✓ Reversal verified",
  "Der ursprüngliche Archivzustand ist vollständig wiederhergestellt.": "The original archive state has been fully restored.",
  "Rückänderung abgeschlossen. Die Archivänderung wurde verworfen.": "Reversal complete. The archive change was discarded.",
  "Lade Änderungsauftrag …": "Loading change request…",
  "Der frühere Archivänderungsauftrag ist bereits abgeschlossen.": "The previous archive change request is already complete.",
  "Prüfen & Abschließen": "Verify & finish",
  "Die App bereitet nur SSD-Hilfsstrukturen vor. Die Kamerabibliothek und der gültige Datenbankzustand bleiben unverändert.": "The app only prepares temporary SSD structures. The camera library and valid database state remain unchanged.",
  "Hilfsbereich wird vorbereitet …": "Preparing temporary workspace…",
  "✓ Aktueller Archivbestand wurde read-only geprüft.": "✓ Current archive inventory verified read-only.",
  "SSD-Kopien prüfen": "Verify SSD copies",
  "✓ SSD-Kopien vollständig geprüft": "✓ SSD copies verified",
  "Alle freigewordenen Dateien stimmen nach Größe und SHA-256 mit dem geplanten Bestand überein.": "All released files match the planned inventory by size and SHA-256.",
  "2. Bestätigte Archivoriginale entfernen": "2. Remove confirmed archive originals",
  "Entfernung aus dem Archiv prüfen": "Verify removal from archive",
  "✓ Freigewordene Archivdateien sicher zurückgeholt": "✓ Released archive files safely recovered",
  "Bei diesem Löschauftrag wird keine neue Archivstruktur aufgebaut.": "This deletion request does not create a new archive structure.",
  "Alle vorgesehenen alten Ordner sind bereits entfernt.": "All designated old folders have already been removed.",
  "Finder-Arbeit erledigt · weiter zu Prüfen": "Finder work complete · proceed to verification",
  "✓ Prüfung erfolgreich": "✓ Verification successful",
  "Änderung abschließen & SSD freigeben": "Finish change & release SSD inventory",
  "Archivdateien werden geprüft und sicher auf die SSD kopiert …": "Checking archive files and safely copying them to the SSD…",
  "SSD-Kopien werden nach Größe und SHA-256 geprüft …": "Checking SSD copies by size and SHA-256…",
  "Alle SSD-Kopien sind vollständig geprüft.": "All SSD copies have been verified.",
  "SSD-Kopien und entfernte Archivoriginale werden geprüft …": "Checking SSD copies and removed archive originals…",
  "Archivoriginale sind entfernt und der SSD-Bestand ist bestätigt.": "Archive originals have been removed and the SSD inventory verified.",
  "Dateien werden verifiziert kopiert und der Hilfsbereich wird vorbereitet …": "Copying files with verification and preparing the temporary workspace…",
  "Dateien werden verifiziert verschoben und der Hilfsbereich wird vorbereitet …": "Moving files with verification and preparing the temporary workspace…",
  "Ordner und Hardlinks werden unter „Später zuordnen“ vorbereitet …": "Preparing folders and hardlinks under “Assign Later”…",
  "Hardlinks sind zwischen diesen Speicherorten nicht möglich.": "Hardlinks are not supported between these storage locations.",
  "Wähle, wie die Dateien nach „Später zuordnen“ gelangen sollen.": "Choose how files should be moved to “Assign Later”.",
  "Prüfung läuft …": "Verification in progress…",
  "Kamerabibliothek wird nach Pfad, Größe und SHA-256 geprüft …": "Checking camera library paths, sizes and SHA-256 hashes…",
  "Prüfung abgeschlossen.": "Verification complete.",
  "Zusätzliche nicht verwaltete Datei · nur Hinweis": "Additional unmanaged file · informational only",
  "✕ Prüfung mit Problemen": "✕ Verification found issues",
  "Bitte die angezeigten Abweichungen im Finder korrigieren und erneut prüfen.": "Correct the discrepancies in Finder and verify again.",
  "Dateigröße abweichend": "File size mismatch",
  "Erforderlicher Ordner fehlt": "Required folder is missing",
  "Alter Ordner noch vorhanden": "Old folder still exists",
  "Dieser Ordner wird im SOLL nicht mehr benötigt": "This folder is no longer required in the target state",
  "event.json stimmt noch nicht": "event.json does not match yet",
  "✕ Prüfung fehlgeschlagen": "✕ Verification failed",
  "Geprüften SOLL-Zustand in die Datenbank übernehmen …": "Writing verified target state to the database…",
  "SSD-Originale und Hilfslinks sicher freigeben …": "Safely releasing SSD originals and temporary links…",
  "Abgeschlossen · SSD freigegeben und leere Quellordner aufgeräumt.": "Completed · SSD released and empty source folders cleaned up.",
  "Änderung vollständig abgeschlossen.": "Change fully completed.",
  "Archivänderung abgeschlossen.": "Archive change completed.",
  "Archivänderung verworfen. Der vorherige Zustand bleibt gültig.": "Archive change discarded. The previous state remains valid.",
  "Bitte Input-Ordner wählen · momentan unbekannt": "Choose an input folder · currently unknown",
  "Unterereignis-/Tagesblätter besitzen unterschiedliche Ordnerstrukturen.": "Subevents/day groups have different folder structures.",
  "Keine Pfadänderungen.": "No path changes.",
  "Input-Ordner": "Input folder",
  "Bereits in der vorbereiteten event.json gespeichert.": "Already stored in the prepared event.json.",
  "Welcher Ordner soll zukünftig der Input-Ordner sein?": "Which folder should become the input folder?",
  "Erkannte Änderungen": "Detected changes",
  "Diese Änderung kann noch nicht übernommen werden.": "This change cannot be accepted yet.",
  "Änderungen übernehmen": "Accept changes",
  "Bitte einen zukünftigen Input-Ordner wählen.": "Choose a future input folder.",
  "event.json und SQLite werden aktualisiert …": "Updating event.json and SQLite…",
  "Manuelle Ereignisänderung übernommen. event.json und SQLite sind aktuell.": "Manual event change accepted. event.json and SQLite are up to date.",
  "im Archiv": "in archive",
  "Archivbestand und event.json werden geprüft …": "Checking archive inventory and event.json…",
  "Archivänderung geprüft und in SQLite übernommen.": "Archive change verified and recorded in SQLite.",
  "Bibliothekar erzeugt eine neue event.json unter „Später zuordnen“. Die Kamerabibliothek bleibt read-only.": "Bibliothekar creates a new event.json under “Assign Later”. The camera library remains read-only.",
  "Geprüfter Wartungsplan": "Verified maintenance plan",
  "Quellen werden erneut per SHA-256 geprüft und sicher verschoben …": "Rechecking source SHA-256 hashes and moving files safely…"
})

UI_TRANSLATIONS.update({
  "Geschützter Zugang zur Kamerabibliothek": "Secure access to your camera library",
  "Zu viele Versuche. Bitte später erneut versuchen.": "Too many attempts. Please try again later.",
  "Anmeldung fehlgeschlagen. Passwort oder Konfiguration prüfen.": "Sign-in failed. Check your password and configuration.",
  "Es ist noch kein Administratorpasswort eingerichtet.": "No administrator password has been configured.",
  "Erste Bibliothek einrichten": "Set up your first library",
  "Bibliothek prüfen und anlegen": "Check and create library",
  "Bibliothek wird geprüft …": "Checking library…",
  "Bibliothek eingerichtet. Bibliothekar wird geöffnet …": "Library created. Opening Bibliothekar…",
  "Bibliothekar besitzt noch keine Bibliothek. Lege jetzt Name, Arbeitsbereich und das in TrueNAS read-only gemountete Archiv fest. Es wird kein technischer": "Bibliothekar has no libraries yet. Configure a name, workspace and a read-only archive mounted in TrueNAS. No technical",
  "Arbeitsordner angelegt.": "workspace folder will be created.",
  "Leer lassen: Bibliothekar erzeugt unter": "Leave empty: Bibliothekar will create a folder under",
  "automatisch einen Ordner aus dem Bibliotheksnamen.": "automatically from the library name.",
  "Ordner wurden sicher aktualisiert; externe TrueNAS-Mounts bleiben unverändert.": "Folders updated safely; external TrueNAS mounts remain unchanged.",
  "Bibliothek deaktivieren? Dateien, Datenbank und Archiv bleiben erhalten.": "Deactivate this library? Files, database and archive will be retained.",
  "Bibliothek abmelden? Es werden keine Dateien, keine Datenbank und kein Archiv gelöscht.": "Unregister this library? No files, database or archive will be deleted.",
  "Pfadänderungen verschieben keine Dateien. Ein externer Pfad muss zuvor in TrueNAS gemountet sein.": "Changing paths does not move files. External paths must first be mounted in TrueNAS.",
  "Die Oberfläche wird in Englisch angezeigt. Bereits vorhandene Ordner und Dateien werden nicht umbenannt.": "The interface is displayed in English. Existing folders and files will not be renamed.",
  "Die Sprache betrifft die Oberfläche. Vorhandene Ordnernamen, Benutzereingaben und Dateipfade bleiben unverändert.": "The language setting only changes the interface. Existing folder names, user input and file paths remain unchanged.",
  "Der eingegebene Ereignisname bleibt Bestandteil des Ordnernamens. Bestehende Ereignisse behalten ihren gespeicherten Benennungsstand.": "The event name you enter remains part of the folder name. Existing events retain their saved names.",
  "Der eingegebene Unterereignisname bleibt immer erhalten. Jahr, Uhrzeit und Von–bis lassen sich frei kombinieren. Im Ereignisfenster kann der Standard pro Ereignis mit „Präfix: an/aus“ überschrieben werden.": "The subevent name is always preserved. Year, time and date range can be combined freely. You can override the default prefix for each event.",
  "Sammelordner werden monatsweise gebildet. Von–bis und Uhrzeit gehören deshalb nicht in ihre Ordnerbenennung.": "Collection folders are grouped by month, so date ranges and times are not included in their names.",
  "So sehen Ordnerstruktur und Standardbenennung für neue Inhalte aus.": "This is how folder structure and default naming will look for new content.",
  "Diese Namen betreffen ausschließlich von Bibliothekar verwaltete Ordner innerhalb des Workspace-Mounts.": "These names apply only to folders managed by Bibliothekar inside the workspace mount.",
  "Standardmäßig legt Bibliothekar den Arbeitsbereich unter dem konfigurierten Stamm „Bibliotheks-Arbeitsbereiche“ an.": "By default Bibliothekar creates the workspace inside the configured “Library Workspaces” directory.",
  "Nur für einen externen Arbeitsbereich ist ein zusätzlicher RW-Host-Path in TrueNAS nötig.": "Only an external workspace needs an additional read-write host path in TrueNAS.",
  "Das Archiv wird aus Sicherheitsgründen pro Bibliothek separat als Read Only Host Path eingebunden.": "For security, each library archive is mounted separately as a read-only host path.",
  "Standardmäßig legt Bibliothekar den Arbeitsbereich unter dem konfigurierten Stamm „Bibliotheks-Arbeitsbereiche“ an. Nur für einen externen Arbeitsbereich ist ein zusätzlicher RW-Host-Path in TrueNAS nötig. Das Archiv wird aus Sicherheitsgründen pro Bibliothek separat als Read Only Host Path eingebunden.": "Bibliothekar creates a workspace under the configured “Library Workspaces” directory by default. Only external workspaces require an additional TrueNAS read-write mount. Each archive must be mounted separately read-only.",
  "Die eingestellten Namen beeinflussen keine bestehenden Ordner.": "Configured names do not alter existing folders."
})

UI_TRANSLATIONS.update({
  "Die Aufnahmezeiten passen eindeutig zu bereits vorhandenen Ereignissen. Erst nach deiner Bestätigung werden die neuen Aufnahmen sicher zum passenden Ereignis hinzugefügt.": "The capture times clearly match existing events. The new photos will be added to the appropriate event only after your confirmation.",
  "0 Gruppen ausgewählt": "0 groups selected",
  "Mit Umschalt (Shift) lassen sich zusammenhängende Tagesgruppen auswählen.": "Hold Shift to select consecutive day groups.",
  "Direkt angrenzende freie Zeit kann ein bestehendes Ereignis erweitern. Gelb markierte, bereits freigegebene Applied-Bereiche sind normaler freier Bestand und erzeugen keine Neu-Zuordnungsaufgabe.": "Adjacent free time can extend an existing event. Yellow released applied areas are ordinary free inventory and do not require reassignment.",
  "Jeder Tag bzw. Teil eines Tages wird einzeln gespeichert.": "Each day or partial day is saved individually.",
  "＋ Unterereignis hinzufügen": "+ Add subevent",
  "Unterordner erstellen": "Create subfolder",
  "OK · vollständig übernehmen": "OK · accept all",
  "Die API hat keine gültige JSON-Antwort geliefert.": "The API did not return valid JSON.",
  "Keine Dateinamen verfügbar.": "No filenames available.",
  "Keine Sicherung": "No backup",
  "Arbeitsbestände werden geladen …": "Loading workspace inventory…",
  "Keine Sicherung im Filter ausgewählt.": "No backup selected in the filter.",
  "Gemeinsamer Arbeitsbestand wird geladen …": "Loading shared workspace inventory…",
  "Die neuen Aufnahmen werden der offenen Planung hinzugefügt.": "The new photos will be added to the pending plan.",
  "Die neuen Aufnahmen werden als sichere Ergänzung des angewendeten Ereignisses vorbereitet.": "The new photos will be prepared as a safe addition to the applied event.",
  "Die neuen Aufnahmen werden über den geprüften Archivänderungsweg unter ‚Später zuordnen‘ vorbereitet.": "The new photos will be prepared under “Assign Later” through the verified archive change workflow.",
  "Vorschau und Wirkung": "Preview and effects",
  "Dieses geplante Ziel wird nicht separat angewendet. Es wird zusammen mit dem bearbeiteten Ursprungsereignis geprüft und angewendet.": "This planned destination is not applied separately. It is verified and applied with the modified source event.",
  "Nachsortierung unter Ereignisse öffnen": "Open resort plan under Events",
  "1 geplantes Ereignis": "1 planned event",
  "Gespeichertes Ereignis": "Saved event",
  "Ereignisstruktur wird geladen …": "Loading event structure…",
  "Alle Aufnahmen sind zugeordnet und archiviert oder durch den Sicherungsfilter ausgeblendet.": "All photos are assigned and archived or hidden by the backup filter.",
  "Sicher aus dem Archiv auf die SSD zurückgeholter freier Bestand.": "Free inventory safely restored from the archive to the SSD.",
  "Prüffälle ohne Datum – Metadatenkorrektur öffnen": "Undated items requiring review – open metadata correction",
  "Prüffälle · Ohne Datum": "Review items · Undated",
  "Nicht für Ereignisse auswählbar · Doppelklick öffnet die Metadatenkorrektur": "Not selectable for events · double-click to open metadata correction",
  "1 Prüffall": "1 item requiring review",
  "Aus Archiv freigeworden": "Released from archive",
  "Freigegeben durch Applied-Änderung": "Released by applied-event change",
  "einem Ereignis zugeordnet.": "assigned to an event.",
  "Angezeigt wird nur der freie Bestand.": "Only unassigned inventory is shown.",
  "1 Gruppe ausgewählt": "1 group selected",
  "Hinweis: Dateien ohne Datum müssen zuerst geprüft werden.": "Note: undated files must be reviewed first.",
  "„Ohne Ereignis“ darf nur innerhalb eines Kalendermonats angelegt werden. Bitte die Monate getrennt zuordnen.": "“No Event” collections may only cover one calendar month. Assign the months separately.",
  "Keine Sicherung ausgewählt.": "No backup selected.",
  "Die ausgewählte freie Zeit grenzt nicht zusammenhängend an dieses Ereignis an.": "The selected free time is not continuously adjacent to this event.",
  "Ereignis erweitern": "Extend event",
  "Der bisherige Unterereigniszeitraum reicht bereits bis zum Ende des Oberereignisses. Ändere zuerst die letzte Endzeit.": "The existing subevent time range already extends to the end of its parent event. Adjust the last end time first.",
  "Namenspräfix für Unterereignisse ·": "Subevent naming prefix ·",
  "Zum Beispiel Tag 1": "For example, Day 1",
  "Neues Ereignis anlegen": "Create new event",
  "Vorschau wird vorbereitet …": "Preparing preview…",
  "Der Erweiterungsbereich ist nicht mehr aktuell.": "The extension range is no longer current.",
  "Neue Unterereignisse dürfen nur innerhalb des neu hinzugefügten Erweiterungsbereichs liegen.": "New subevents must lie within the newly added extension range.",
  "Fortführung ·": "Continuation ·",
  "Vorschau wird berechnet …": "Calculating preview…",
  "Ereignis wird gespeichert …": "Saving event…",
  "Bitte die freien Bereiche eines Archivauftrags getrennt auswählen.": "Select the free areas of an archive request separately.",
  "Neu zugeordnet. Den manuellen Archiv-Änderungsplan unter Ereignisse prüfen und bestätigen.": "Reassigned. Review and confirm the manual archive change plan under Events.",
  "Für diesen Monat wurde keine bestehende „Ohne Ereignis“-Sammlung gefunden.": "No existing “No Event” collection was found for this month.",
  "Es gibt keine neuen Tagessegmente zum Hinzufügen.": "There are no new day segments to add.",
  "· sicherungsübergreifend": "· across backups",
  "nicht mehr aktuell": "outdated",
  "Mehrfach-Anwendung wurde nicht abgeschlossen.": "Batch application did not finish.",
  "Alle ausgewählten Ereignisse wurden serverseitig vollständig angewendet und geprüft.": "All selected events were applied and verified completely on the server.",
  "Laufender Servervorgang wurde wieder aufgenommen …": "Resumed running server operation…",
  "Keine geplanten Ereignisse ausgewählt.": "No planned events selected.",
  "Alle ausgewählten Pläne werden geprüft …": "Checking all selected plans…",
  "Nicht angewendet.": "Not applied.",
  "Zuordnung wird geprüft und geplant …": "Checking and planning assignments…",
  "Dieses geplante Ereignis anwenden": "Apply this planned event",
  "Die Aufgabe hat genau dieses Ereignis vorausgewählt; andere geplante Ereignisse bleiben unangetastet.": "This task preselects only the specified event; all other planned events remain unchanged.",
  "Dieses Ereignis anwenden": "Apply this event",
  "Offene Aufgabe: Dieses geplante Ereignis muss noch angewendet werden.": "Pending task: this planned event still needs to be applied.",
  "Das geplante Ereignis ist nicht mehr offen.": "This planned event is no longer pending.",
  "Offene Aufgabe: Es gibt noch nicht zugeordnete Familien.": "Pending task: some families have not yet been assigned.",
  "Alter 0.27-Nachtrag wird rein lesend geprüft.": "Checking legacy 0.27 follow-up in read-only mode.",
  "Wartungsplan wird geladen …": "Loading maintenance plan…",
  "Löschbare Planungen": "Plans eligible for deletion",
  "Dieses geplante Ereignis wird nicht separat angewendet. Es wird zusammen mit dem bearbeiteten Ursprungsereignis im gemeinsamen Nachsortierplan geprüft und angewendet.": "This planned event is not applied separately. It is verified and applied with the edited source event in the combined resort plan.",
  "Ich bestätige diesen Zielplan; verändert wird ausschließlich der angezeigte SSD-Arbeitsbestand.": "I confirm this destination plan. Only the displayed SSD workspace inventory will be modified.",
  "die Browser-Validierung": "browser validation",
  "Prüfung starten.": "Start verification.",
  "Bestand prüfen.": "Verify inventory.",
  "Verwalteter Ordner": "Managed folder",
  "1 Datei": "1 file",
  "Physischer Bestand geprüft ·": "Physical inventory verified ·",
  "nicht katalogisierte Dateien": "uncatalogued files",
  "Sicherungsabschluss verfolgen, Kamerabibliothek read-only prüfen und bestätigte SSD-Bestände freigeben.": "Track backup completion, verify the camera library read-only and release confirmed SSD inventory.",
  "Neu angewendete Ereignisse werden hier geprüft und anschließend von der Arbeitsbereich freigegeben. Neueste Ereignisse stehen zuerst.": "Newly applied events are verified here, then released from the workspace. Most recent events appear first.",
  "· Die bisherigen Prüfschritte bleiben gespeichert.": "· Earlier verification steps are preserved.",
  "Arbeitsbereich wird im Hintergrund freigegeben ·": "Workspace inventory is being released in the background ·",
  "· Ein Seitenwechsel oder Browser-Neustart unterbricht den Serverauftrag nicht.": "· Switching pages or restarting the browser does not interrupt the server job.",
  "Auftragsstatus konnte nicht abgefragt werden:": "Could not retrieve job status:",
  "Manuelle Archivklärung erforderlich": "Manual archive review required",
  "Nach einem Notfallabbruch wurde der ursprüngliche Archivzustand noch nicht wieder bestätigt. Neue Änderungen bleiben gesperrt.": "After emergency cancellation, the original archive state has not yet been verified. New changes remain blocked.",
  "Originalbestand erneut prüfen": "Verify original inventory again",
  "Kamerabibliothek wird vollständig per Größe und SHA-256 geprüft …": "Verifying the entire camera library by size and SHA-256…",
  "Archiv wird geladen …": "Loading archive…",
  "Archivverlauf wird geladen …": "Loading archive history…",
  "Archivprüfung läuft …": "Archive verification in progress…"
})

UI_TRANSLATIONS.update({
  "Links die Aufnahme auswählen, deren tatsächliche Zeit bekannt ist.": "Select the photo with a known actual capture time on the left.",
  "Gemeinsamer Ohne-Datum-Bestand aller Kamerasicherungen: erst Metadaten prüfen oder korrigieren, danach bewusst einsortieren.": "Shared undated inventory from all camera backups: first verify or correct metadata, then explicitly assign files to dated inventory.",
  "Unabhängige Dateien direkt im verwalteten Ordner Allgemein korrigieren.": "Correct independent files directly in the managed General folder.",
  "Zeitlich zusammengehörige Kameraaufnahmen gemeinsam verschieben. Eine Referenzaufnahme festlegen, Vorschau prüfen und den Zeitversatz anschließend auf den gesamten Ordner anwenden.": "Shift capture times together for related camera photos. Choose a reference photo, review the preview, then apply the time offset to the entire folder.",
  "Dateien im Ordner Allgemein": "Files in General folder",
  "Ordner:": "Folder:",
  "Prüfung nötig": "Verification required",
  "ausgewählt": "selected",
  "Einträge ausgewählt.": "items selected.",
  "Für jede Datei wird ihr eigener Wert des gewählten Metadaten-Tags verwendet.": "Each file uses its own value for the selected metadata tag.",
  "Metadatenquelle übernehmen (": "Adopt metadata source (",
  "Die ausgewählten Dateien besitzen keinen gemeinsamen nutzbaren Metadaten-Quelltyp.": "The selected files do not share a usable metadata source type.",
  "In Tagesbestand übernehmen (": "Move to dated inventory (",
  "nicht nutzbar": "not usable",
  "Ursprüngliche Metadaten vor der Korrektur": "Original metadata before correction",
  "nicht vorhanden": "not available",
  "In Tagesbestand übernehmen": "Move to dated inventory",
  "Prüfung/Korrektur erforderlich": "Verification/correction required",
  "Metadaten erneut ändern": "Edit metadata again",
  "Metadaten ändern": "Edit metadata",
  "Datum und Uhrzeit müssen vollständig angegeben werden.": "Date and time must be entered in full.",
  "Metadaten werden geändert …": "Updating metadata…",
  "Metadaten geändert. Bereit zum Einsortieren.": "Metadata updated. Ready to assign to dated inventory.",
  "Metadaten geändert und geprüft.": "Metadata updated and verified.",
  "Mindestens eine ausgewählte Datei besitzt diesen Metadaten-Quelltyp nicht mehr.": "At least one selected file no longer has this metadata source type.",
  "Einträge werden mit ihrem jeweiligen": "items will use their respective",
  "Einträge mit ihren eigenen": "items with their own",
  "Bitte mindestens eine Allgemein-Datei auswählen.": "Select at least one file from General.",
  "Vor der Übernahme müssen alle ausgewählten Dateien eine belastbare Aufnahmezeit besitzen.": "All selected files must have a reliable capture time before transfer.",
  "Übernahme in den Tagesbestand wird vorbereitet …": "Preparing transfer to dated inventory…",
  "Dateien werden für den Tagesbestand vorbereitet …": "Preparing files for dated inventory…",
  "zur verifizierten Übernahme in den Tagesbestand vorgemerkt.": "queued for verified transfer to dated inventory.",
  "Bitte zuerst alle ausgewählten Einträge korrigieren.": "Correct all selected entries first.",
  "Korrigierte Familie wird einsortiert …": "Assigning corrected family…",
  "Familie wurde geprüft und in den Tagesbestand einsortiert.": "Family verified and assigned to dated inventory.",
  "Familien wurden geprüft und in den Tagesbestand einsortiert.": "Families verified and assigned to dated inventory.",
  "Keine offenen Metadatenaufträge.": "No pending metadata correction tasks.",
  "Jetzt ausführen": "Run now",
  "Metadaten familienweise schreiben und vollständig prüfen? Die Familie bleibt danach in Ohne_Datum.": "Write metadata for each family and verify completely? The family will remain under Undated afterwards.",
  "Metadaten in einer Arbeitskopie schreiben, prüfen und die Datei danach atomar ersetzen?": "Write metadata to a working copy, verify, then atomically replace the file?",
  "Korrektur wird geschrieben und vollständig geprüft …": "Writing and verifying correction…",
  "Korrektur geprüft. Die Familie kann jetzt separat einsortiert werden.": "Correction verified. The family can now be assigned separately.",
  "Korrektur vollständig geschrieben und geprüft.": "Correction fully written and verified.",
  "Dateien in den verwalteten Ordner legen und erneut prüfen.": "Place files in the managed folder and verify again.",
  "Tatsächliches Datum": "Actual date",
  "Tatsächliche Uhrzeit": "Actual time",
  "Die direkte Übernahme in den Tagesbestand ist nur für den vollständig ausgewählten Mehrfachkorrektur-Ordner möglich.": "Direct transfer to dated inventory is only available when the entire Batch Correction folder is selected.",
  "Referenzdatei, Datum und Uhrzeit müssen vollständig angegeben werden.": "Reference file, date and time must be entered in full.",
  "Vorschau berechnet. Es wurde noch nichts verändert.": "Preview calculated. Nothing has been changed.",
  "Bitte zuerst eine Vorschau berechnen.": "Calculate a preview first.",
  "Korrektur wird angewendet und die Übernahme vorbereitet …": "Applying correction and preparing transfer…",
  "Korrektur wird angewendet …": "Applying correction…",
  "Korrektur angewendet. Die Übernahme in den Tagesbestand läuft im Hintergrund.": "Correction applied. Transfer to dated inventory is running in the background.",
  "Korrektur vollständig angewendet. Die Dateien bleiben im Ordner Mehrfachkorrektur.": "Correction applied completely. Files remain in Batch Correction folder.",
  "Ordner und Metadaten werden gelesen …": "Reading folders and metadata…",
  "Prüfung abgeschlossen. Es wurde noch nichts verändert.": "Verification completed. Nothing was changed.",
  "Ohne-Datum-Bestand wird gelesen …": "Loading undated inventory…",
  "Papierkorb wirklich endgültig entleeren?\\n\\nAlle Dateien und Ordner darin werden unwiderruflich gelöscht. Dieser Vorgang kann nicht rückgängig gemacht werden.": "Permanently empty the trash?\\n\\nAll files and folders in the trash will be deleted irreversibly. This action cannot be undone.",
  "Der Ordner für SD-Kartensicherungen konnte nicht angelegt werden:": "Could not create the SD Card Backups folder:",
  "Der Pfad für SD-Kartensicherungen ist kein Ordner:": "The SD Card Backups path is not a directory:"
})

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
  const reverseDictionary = Object.create(null);
  for (const [german, english] of Object.entries(dictionary)) {
    if (!Object.prototype.hasOwnProperty.call(reverseDictionary, english)) {
      reverseDictionary[english] = german;
    }
  }
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
  function restoreGerman(value) {
    if (typeof value !== "string" || !value) return value;
    const core = value.trim();
    if (!core || !Object.prototype.hasOwnProperty.call(reverseDictionary, core)) return value;
    const offset = value.indexOf(core);
    return value.slice(0, offset) + reverseDictionary[core] + value.slice(offset + core.length);
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
    const desired = locale === "en" ? tr(source) : restoreGerman(source);
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
      const desired = locale === "en" ? tr(source) : restoreGerman(source);
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
    t: (value) => locale === "en" ? tr(String(value)) : restoreGerman(String(value)),
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
