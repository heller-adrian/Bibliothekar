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
