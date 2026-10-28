"""Client-only, non-destructive UI localisation for Bibliothekar.

Do not translate stored paths, IDs, event.json payloads or filesystem data.
The user interface can be switched without changing the database.
"""
from __future__ import annotations

import json

UI_TRANSLATIONS = {
  "Speicherordner nicht verfügbar": "Storage folder unavailable",
  "Ein benötigter Verwaltungsordner fehlt, wurde verschoben oder ist nicht eindeutig zugänglich.": "A required storage folder is missing, has been moved, or cannot be accessed reliably.",
  "Betroffene Vorgänge sind zum Schutz Ihrer Dateien angehalten.": "Affected operations have been paused to protect your files.",
  "Bitte stellen Sie den ursprünglichen Ordner gegebenenfalls außerhalb der App im NAS-Dateisystem wieder her. Prüfen Sie die Einbindung und den erwarteten Pfad. Es werden keine Ordner automatisch ersetzt.": "If necessary, restore the original folder outside the app in the NAS filesystem. Check the mount and the expected path. No folders will be replaced automatically.",
  "Erneut prüfen": "Check Again",

  "Verwaltungsordnernamen sind fest vorgegeben. Neue Installationen verwenden englische Namen. Bestehende Ordner und gespeicherte Pfade bleiben unverändert.": "Storage folder names are fixed. New installations use English names. Existing folders and saved paths remain unchanged.",
  "Die Verwaltungsordnernamen sind nicht mehr änderbar. Bestehende Pfade bleiben erhalten.": "Storage folder names can no longer be changed. Existing paths are preserved.",
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

UI_TRANSLATIONS.update({
  "Alle wiederherstellen": "Restore all",
  "Auswahl wiederherstellen": "Restore selection",
  "Auswahl beenden": "Finish selection",
  "Auswahl aufheben": "Clear selection",
  "Dateien werden in den Tagesbestand wiederhergestellt …": "Restoring files to daily inventory…",
  "Datenabgleich prüfen:": "Check inventory synchronization:",
  "Ausgewählte Dateien in den Tagesbestand wiederherstellen?": "Restore selected files to daily inventory?",
  "Alle Dateien im Papierkorb in den Tagesbestand wiederherstellen?": "Restore all files in trash to daily inventory?",
  "Wiederherstellung fehlgeschlagen:": "Restoration failed:",
  "Nicht katalogisierte Datei:": "Uncatalogued file:",
  "Zieldatei existiert bereits:": "Destination file already exists:",
})

# UI copy that was previously split across multiline HTML and browser alerts.
UI_TRANSLATIONS.update({
  "Papierkorb wirklich endgültig entleeren?": "Permanently empty the trash?",
  "Alle Dateien und Ordner darin werden unwiderruflich gelöscht. Dieser Vorgang kann nicht rückgängig gemacht werden.": "All files and folders in the trash will be permanently deleted. This cannot be undone.",
  "Normales Ereignis": "Regular event",
  "Zuordnung prüfen": "Verify assignment",
  "Weitere Bestandsänderungen": "Additional inventory changes",
  "Änderungen rückgängig machen": "Undo changes",
  "Nicht automatisch zurückgesetzt": "Not automatically reverted",
  "Du kannst die Datei notfalls selbst an den Sollort zurücklegen und danach erneut prüfen.": "You can manually return the file to its expected location and check again.",
  "Bitte den angezeigten Sollort prüfen, die Datei bei Bedarf manuell zurücklegen und danach erneut prüfen.": "Check the expected location shown, return the file manually if necessary, and verify again.",
  "Hinweis schließen": "Dismiss notice",
  "Über Bibliothekar": "About Bibliothekar",
  "Hintergrundvorgänge": "Background operations",
  "Leeren": "Clear",
  "Beendete Meldungen ausblenden": "Hide finished notifications",
  "Meldungen konnten nicht entfernt werden.": "Could not clear notifications.",
  "Die zuletzt geänderten Ereignisse werden angezeigt.": "Recently modified events are displayed.",
  "Gespeicherte Planungen prüfen und noch nicht angewendete Planungen wieder freigeben.": "Review saved plans and release plans that have not yet been applied.",
  "Rein lesende Vorschau. Es wird nichts verändert.": "Read-only preview. Nothing will be modified.",
  "Sortierplan wird geladen …": "Loading sorting plan…",
  "Alter 0.27-Nachtrag wird rein lesend geprüft.": "The older 0.27 follow-up is being checked in read-only mode.",
  "Dieses geplante Ereignis wird nicht separat angewendet. Es wird zusammen mit dem bearbeiteten Ursprungsereignis im gemeinsamen Nachsortierplan geprüft und angewendet.": "This planned event will not be applied separately. It is reviewed and applied with the edited source event in the combined resort plan.",
  "Details werden beim Öffnen geladen.": "Details load when opened.",
  "Keine Familien für dieses Ziel.": "No families for this destination.",
  "Jeder Tag bzw. Teil eines Tages wird separat gespeichert. Zwischenräume gehören ausdrücklich nicht zu „Ohne Ereignis“.": "Each day or partial day is saved separately. Gaps are not part of “No Event”.",
  "Du hast bestätigt, dass die Archivänderung verworfen werden soll. Der ursprüngliche Zustand wird jetzt als eigener Rückweg vorbereitet.": "You confirmed that the archive change should be discarded. A separate reversal procedure is now being prepared to restore the original state.",
  "✓ Der ursprüngliche Finder-Zustand ist bereits wiederhergestellt.": "✓ The original Finder state has already been restored.",
  "Der ursprüngliche Archivzustand wird vollständig read-only nach Ordnern, Pfaden, Größen und SHA-256 geprüft.": "The original archive state is being verified read-only by folders, paths, sizes and SHA-256 hashes.",
  "✓ Aktueller Archivbestand wurde read-only nach Pfad, Größe und SHA-256 geprüft.": "✓ The current archive inventory was verified read-only by path, size and SHA-256.",
  "So soll die Kamerabibliothek jetzt aussehen. Die Prüfung selbst bleibt vollständig read-only.": "This is the expected new camera library state. The verification remains completely read-only.",
  "Ein Hardlink ist deshalb nicht möglich. Beide Varianten prüfen Größe und SHA-256 vollständig.": "A hard link is not possible. Both options fully verify file size and SHA-256.",
  "Die freie Quelldatei bleibt zunächst erhalten. Nach erfolgreichem Abschluss wird die nicht mehr benötigte SSD-Kopie bereinigt.": "The free source file is retained initially. After successful completion, the unnecessary SSD copy is cleaned up.",
  "Erst nach vollständig verifizierter Hilfskopie wird die freie Quelldatei entfernt. Beim Verwerfen wird sie sicher zurückgestellt.": "The free source file is removed only after the auxiliary copy has been fully verified. It is safely restored when discarding.",
  "Die 0.27-Zweitstruktur wird erst nach erneuter SHA-256-Prüfung in das kanonische Ereignis übernommen. Kein bestehender Zielpfad wird überschrieben.": "The legacy 0.27 secondary structure is merged into the canonical event only after another SHA-256 check. No existing destination path is overwritten.",
  "Ich möchte diese geprüfte Legacy-Struktur jetzt in das kanonische Ereignis vereinheitlichen.": "I want to consolidate this verified legacy structure into the canonical event now.",
  "Tagesbestände auswählen, Ereignisse erstellen und Änderungen direkt anwenden.": "Select daily inventory, create events and apply changes directly.",
  "Noch kein Arbeitsbestand ausgewählt.": "No workspace inventory selected yet.",
  "Der Zeitraum kann aus ausgewählten Tagesordnern übernommen oder frei eingetragen werden.": "The date range can be taken from selected day folders or entered manually.",
  "Beim Speichern wird nur die Planung in SQLite eingetragen. Dateien und Ordner bleiben unverändert.": "Saving only writes the plan to SQLite. Files and folders remain unchanged.",
  "Neues Ereignis anlegen": "Create new event",
  "Prüfung starten.": "Start verification.",
  "Links die Aufnahme auswählen, deren tatsächliche Zeit bekannt ist.": "On the left, select the photo with a known actual capture time.",
  "Ursprüngliche Metadaten vor der Korrektur": "Original metadata before correction",
  "Die ausgewählten Dateien besitzen keinen gemeinsamen nutzbaren Metadaten-Quelltyp.": "The selected files have no shared usable metadata source type.",
  "Keine offenen Metadatenaufträge.": "No pending metadata tasks.",
  "Dateien in den verwalteten Ordner legen und erneut prüfen.": "Place files in the managed folder and verify again.",
  "Tatsächliches Datum": "Actual date",
  "Tatsächliche Uhrzeit": "Actual time",
  "Sicherungsabschluss verfolgen, Kamerabibliothek read-only prüfen und bestätigte SSD-Bestände freigeben.": "Track backup completion, verify the camera library read-only and release confirmed SSD inventory.",
  "Manuelle Archivklärung erforderlich": "Manual archive review required",
  "Nach einem Notfallabbruch wurde der ursprüngliche Archivzustand noch nicht wieder bestätigt. Neue Änderungen bleiben gesperrt.": "After an emergency interruption, the original archive state has not yet been reconfirmed. New changes remain blocked.",
  "Archiv wird geladen …": "Loading archive…",
  "Archivverlauf wird geladen …": "Loading archive history…",
  "Verwalteter Ordner": "Managed folder",
  "Vollständig geprüft": "Fully verified",
  "Bestand geprüft": "Inventory verified",
  "Bestehender Bestand": "Existing inventory",
  "Benutzerdefiniert": "Custom",
  "Benutzerdefinierter Ordner": "Custom folder",
})

UI_TRANSLATIONS.update({
  "· Hardlinks zum Zentralbestand möglich.": "· Hardlinks to central inventory possible.",
  "Prüfung PASS. Die Bibliothek kann erstellt werden.": "Verification passed. The library can be created.",
  "“ wurde erstellt.": "” was created.",
  "Pfade werden geprüft und gespeichert …": "Checking and saving paths…",
  "Gespeichert. App-eigene Ordner wurden sicher aktualisiert; externe TrueNAS-Mounts bleiben unverändert.": "Saved. Application-owned folders updated safely; external TrueNAS mounts remain unchanged.",
  "Neuer Ordner": "New folder",
  "Ordnerstruktur konnte nicht geladen werden.": "Could not load folder structure.",
  "Wird gespeichert …": "Saving…",
  "Ungültige Serverantwort beim Speichern.": "Invalid server response while saving.",
  "Speichern fehlgeschlagen.": "Saving failed.",
  "Gespeichert. Bestehende Ereignisse bleiben unverändert.": "Saved. Existing events remain unchanged.",
  "Benennung wird gespeichert …": "Saving naming settings…",
  "Gespeichert. Die Einstellung gilt nur für neue Ereignisse, Unterereignisse und Sammelordner.": "Saved. These settings only affect new events, subevents and collection folders.",
  "Dateisystemhinweise konnten nicht geladen werden.": "Could not load filesystem notices.",
  "Hinweis konnte nicht bestätigt werden.": "Could not acknowledge notice.",
  "Dateibestand und Zuordnung prüfen": "Check file inventory and assignment",
  "Änderung im Dateibestand erkannt": "Change in file inventory detected",
  "Bibliothekar hat gleichzeitig fachliche Zuordnungsabweichungen und weitere externe Bestandsänderungen erkannt.": "Bibliothekar detected both assignment inconsistencies and other external inventory changes.",
  "Eine Datei liegt an einem fachlich unpassenden Ort. Der physische IST-Zustand wurde erkannt; die Zuordnung bleibt als Aufgabe offen.": "A file is in the wrong logical location. The actual physical location has been detected; assignment remains a pending task.",
  "Dateien liegen an fachlich unpassenden Orten. Der physische IST-Zustand wurde erkannt; die Zuordnung bleibt als eine Aufgabe offen.": "Files are in the wrong logical locations. Their physical positions have been detected; the assignment issue remains as one task.",
  "Bibliothekar hat eine externe Änderung übernommen.": "Bibliothekar accepted an external change.",
  "externe Änderungen übernommen.": "external changes accepted.",
  "Die Änderungen konnten nicht vollständig zurückgesetzt werden.": "Changes could not be fully reverted.",
  "Automatisches Rückgängigmachen fehlgeschlagen. Die Aufgabe bleibt offen.": "Automatic recovery failed. The task remains open.",
  "Die physische Ablage bleibt damit vorerst bestehen.": "The physical file location remains unchanged for now.",
  "Die Aufgabe „Dateizuordnung prüfen“ bleibt offen, bis die": "The “Review file assignment” task remains open until the",
  "Quellen einlesen, sicher prüfen und für den Arbeitsbereich vorbereiten.": "Read sources, verify safely and prepare them for the workspace.",
  "Freie Aufnahmen ordnen und Ereignisse aus dem Arbeitsbestand bilden.": "Organize unassigned photos and create events from workspace files.",
  "Geplante, angewendete und archivierte Ereignisse verwalten.": "Manage planned, applied and archived events.",
  "Archivierung prüfen, abschließen und spätere Änderungen nachvollziehen.": "Verify and finalize archiving, and track subsequent changes.",
  "Manuell ausgesonderte Dateien und Ordner im gemeinsamen Kamera-Arbeitsbereich.": "Manually discarded files and folders in the shared camera workspace.",
  "Bibliothekar fragen, Vorschläge erhalten und später Aktionen nachvollziehbar auslösen.": "Ask Bibliothekar, get suggestions and trigger traceable actions later.",
  "Metadaten aus externen Quellen prüfen und später gezielt ergänzen oder korrigieren.": "Verify metadata from external sources, then add or correct it where needed.",
  "Aufgaben öffnen": "Open tasks",
  "; dafür ist kein zusätzlicher TrueNAS-Host-Path nötig.": "; no additional TrueNAS host path is needed.",
  "Änderung zum Verwerfen vorgemerkt. Du kannst in andere Bereiche wechseln.": "Discard request queued. You can switch to other sections.",
  "Änderung wird im Hintergrund verworfen. Bitte betroffene Dateien noch nicht bearbeiten.": "Discarding the change in the background. Do not edit the affected files yet.",
  "Änderung erfolgreich verworfen. Der ursprüngliche Zustand ist wiederhergestellt.": "Change discarded successfully. The original state has been restored.",
  ". Du kannst die Änderung erneut verwerfen.": ". You can retry discarding the change.",
  "Auftrag konnte nicht erneut vorgemerkt werden.": "Could not queue the job again.",
  "Hintergrundvorgänge anzeigen": "Show background operations",
  "Hintergrundvorgänge verkleinern": "Collapse background operations",
  "Dateibestand wurde aktualisiert.": "File inventory updated.",
  "Keine Aufgaben vorhanden.": "No pending tasks.",
  "Neue Ereignisse": "New events",
  "Ereignisordner für neue Aufnahmen": "Event folders for new photos"
})

# 0.50.3: strings audited against real iPhone/PWA screens and all import panels.
UI_TRANSLATIONS.update({
  "Anwendung": "Application",
  "Bereit": "Ready",
  "Verbunden": "Connected",
  "Beschreibbar": "Writable",
  "Eingeschränkt": "Restricted",
  "Benutzer": "User",
  "Datenbank": "Database",
  "Schema": "Schema",
  "Wird geprüft": "Checking",
  "Wird geprüft …": "Checking…",
  "Quelle sichern": "Back up source",
  "Achtung:": "Warning:",
  "Sicherungen werden als Kopie angelegt und belegen zusätzlichen Speicherplatz.": "Backups are stored as copies and require additional storage space.",
  "Hilfe zur Quellenwahl": "Help with choosing a source",
  "Quelle auswählen und anschließend sicher einlesen. Wähle SD-Karte, externes Laufwerk oder einen Ordner. Achtung: Jede Sicherung wird als vollständige Kopie angelegt; dabei werden Daten in den Arbeitsbestand geschrieben und zusätzlicher Speicherplatz benötigt.": "Choose a source, then import it safely. Select an SD card, external drive or folder. Warning: Each backup is stored as a complete copy, added to the working inventory and requires extra disk space.",
  "Importquelle wählen": "Choose import source",
  "SD-Karte": "SD card",
  "SD-Kartenimport": "SD Card Import",
  "Ordnerimport": "Folder Import",
  "Ordner-Import": "Folder Import",
  "Ordner importieren": "Folder Import",
  "Ordnerimport wird vorbereitet.": "Preparing folder import.",
  "Ordnerimport wird angelegt …": "Creating folder import…",
  "Ordnerimport wurde angenommen.": "Folder import accepted.",
  "Ordnerimport wurde in die Warteschlange aufgenommen.": "Folder import queued.",
  "Ordnerimport erfolgreich abgeschlossen.": "Folder import completed successfully.",
  "Der Ordnerimport ist vollständig geprüft.": "Folder import has been fully verified.",
  "Ordnerimport konnte nicht gestartet werden.": "Could not start folder import.",
  "Ordnerimport ist derzeit nicht verfügbar.": "Folder import is currently unavailable.",
  "Karte im Kartenleser": "Card in reader",
  "Laufwerk": "Drive",
  "USB-Festplatte oder Stick": "USB drive or flash drive",
  "Ordner / Sicherung": "Folder / Backup",
  "NAS-Ordner oder vorhandene Sicherung": "NAS folder or existing backup",
  "SD-Karte wird gesucht …": "Searching for SD card…",
  "SD-Karte noch nicht eingebunden": "SD card not mounted",
  "SD-Karte einbinden": "Mount SD card",
  "SD-Karte sichern": "Back up SD card",
  "SD-Karte auswerfen": "Eject SD card",
  "SD-Karte wurde ausschließlich lesend eingebunden.": "SD card mounted read-only.",
  "Bitte die SD-Karte zuerst ausschließlich lesend einbinden.": "Mount the SD card read-only first.",
  "Bereit zum Einbinden": "Ready to mount",
  "Nur lesend eingebunden": "Mounted read-only",
  "Externes Laufwerk sichern": "Back up external drive",
  "USB-Festplatte oder USB-Stick ausschließlich lesend einbinden. Danach kannst du das komplette Laufwerk oder nur einen Ordner daraus sichern.": "Mount a USB drive or flash drive read-only, then back up the entire drive or one of its folders.",
  "Externe Laufwerke": "External drives",
  "Laufwerke werden geladen …": "Loading drives…",
  "Laufwerk einbinden": "Mount drive",
  "Laufwerk auswerfen": "Eject drive",
  "Ordner auswählen": "Select folder",
  "Ordner im Laufwerk auswählen": "Select folder on drive",
  "Nur der ausgewählte Ordner und sein Inhalt werden importiert.": "Only the selected folder and its contents will be imported.",
  "Eine Ebene höher": "Up one level",
  "Diesen Ordner importieren": "Import this folder",
  "Sicherungsordner auswählen": "Select backup folder",
  "Wähle einen einzelnen Ordner auf dem NAS oder auf einem bereits eingebundenen Wechselmedium. Nur dieser Ordner wird importiert.": "Select a single folder on the NAS or a mounted removable device. Only this folder will be imported.",
  "Quellenbereich": "Source location",
  "NAS-Speicher": "NAS storage",
  "Eingebundene Wechselmedien": "Mounted removable devices",
  "Andere Quelle verwenden": "Use another source",
  "Aktualisieren": "Refresh",
  "Import- und Prüfverlauf": "Import & verification history",
  "Hilfe zum Verlauf": "History help",
  "Jeder Eintrag zeigt einen Importvorgang. Fortschritt und Status aktualisieren sich automatisch; technische Details bleiben ausklappbar.": "Each entry represents an import. Progress and status update automatically; technical details can be expanded.",
  "Zuletzt aktualisiert": "Last updated",
  "Aufträge werden geladen …": "Loading jobs…",
  "Keine sichtbaren Importe vorhanden.": "No visible imports.",
  "Ausgeblendete Importe werden geladen …": "Loading hidden imports…",
  "Karteninhalt wird geprüft …": "Checking card contents…",
  "Karteninhalt konnte nicht geprüft werden.": "Could not verify card contents.",
  "Karteninformationen nicht verfügbar:": "Card information unavailable:",
  "Quellen-Helfer nicht erreichbar": "Source helper unavailable",
  "Keine Unterordner": "No subfolders",
  "Dateiprüfung": "File verification",
  "Einzelne Dateien, Dateifamilien und Metadaten kontrollieren.": "Review individual files, file families and metadata.",
  "Importübersicht": "Import overview",
  "Prüfstatus": "Verification status",
  "Keine Prüfung nötig": "No verification required",
  "Noch kein Auftrag ausgewählt.": "No job selected yet.",
  "Metadatenkandidaten werden geladen …": "Loading metadata candidates…",
  "Keine Metadatenkandidaten vorhanden.": "No metadata candidates available.",
  "Dateigröße:": "File size:",
  "Sicherung prüfen": "Verify backup",
  "Sicherung bestätigt": "Backup confirmed",
  "Prüfbeleg erstellen": "Create verification record",
  "Übernahme prüfen": "Verify transfer",
  "Wartet": "Queued",
  "Prüft": "Verifying",
  "Sicherung geprüft": "Backup verified",
  "Bereit fürs Archiv": "Ready for archive",
  "Archiv geprüft": "Archive verified",
  "Löschen freigegeben": "Deletion approved",
  "Fehlgeschlagen": "Failed",
  "Unterbrochen": "Interrupted",
  "Abgeschlossen": "Completed",
  "Tage": "Days",
  "6 Tage": "6 days",
  "Sicherungsfilter": "Backup filter",
  "Neuladen": "Reload",
  "Alle aktiven Sicherungen": "All active backups",
  "Day folder": "Day folder",
  "Weitere Aufnahmen aus ausgeblendeten Sicherungen": "More photos from hidden backups",
  "Neue Aufnahmen passen zu bestehenden Ereignissen": "New photos match existing events",
  "Keine aktiven Sicherungen.": "No active backups.",
  "Keine archivierten Sicherungen.": "No archived backups.",
  "Neu-Zuordnung fortsetzen": "Resume reassignment",
  "Angewendet": "Applied",
  "angewendet": "applied",
  "Bereits verplant": "Already planned",
  "Bereits geplant": "Already planned",
  "Ohne Tagesunterordner": "Without day subfolders",
  "Metadaten eindeutig": "Metadata confirmed",
  "Zugeordnet:": "Assigned:",
  "Noch nicht zugeordnet": "Not yet assigned",
  "Keine Familien in dieser Auswahl.": "No families in this selection.",
  "Von–Bis": "From–To",
  "Von": "From",
  "Bis": "To",
  "Unterereignis:": "Subevent:",
  "Status:": "Status:",
  "Erstellt:": "Created:",
  "Geändert:": "Modified:",
  "Ordner:": "Folder:",
  "Quelle:": "Source:",
  "Dateien:": "Files:",
  "Familien:": "Families:",
  "Sicherung:": "Backup:",
  "Pending checks": "Pending checks",
  "Archivprüfung öffnen": "Open archive verification",
  "Archivprüfung starten": "Start archive verification",
  "Arbeitsbereich freigeben": "Release workspace",
  "Arbeitsbereich freigeben – unterbrochen": "Release workspace – interrupted",
  "Freigabe erneut versuchen": "Retry workspace release",
  "Archivdateien wurden verändert oder ein Sicherheitskonflikt wurde festgestellt. Weitere Löschungen wurden gestoppt. Bereits gelöschte Arbeitskopien sind möglicherweise nicht wiederherstellbar. Prüfen Sie das Archiv und starten Sie die Freigabe ausdrücklich erneut. Noch vorhandene Arbeitsdateien und Archivkopien werden vollständig neu geprüft.": "Archive files changed or a safety conflict was detected. Further deletions have stopped. Work copies already deleted may not be recoverable. Check the archive and explicitly retry the release. Remaining work files and archive copies will be fully checked again.",
  "Archivdateien während der Freigabe nicht extern verändern. Gleichzeitige externe Änderungen können zum Verlust der letzten passenden Kopie führen; die Änderungsüberwachung bietet keine vollständige Erhaltungsgarantie.": "Do not change archive files externally during release. Concurrent external changes can cause loss of the last matching copy; change monitoring does not provide a complete preservation guarantee.",

  "Gesperrt": "Blocked",
  "Offene Prüfungen": "Pending checks",
  "Archivverlauf": "Archive history",
  "Offene Aufgaben": "Open tasks",
  "Offene Aufgaben ·": "Open tasks ·",
  "Keine offenen Aufgaben": "No pending tasks",
  "Alles erledigt.": "All done.",
  "Noch keine freigegebenen Ereignisse im Verlauf.": "No released events in archive history yet.",
  "Prüfung fehlgeschlagen": "Verification failed",
  "Manuelle Archivänderung": "Manual archive change",
  "Testbestand": "Test inventory",
  "Archivbestand und event.json werden geprüft …": "Verifying archive inventory and event.json…",
  "Bitte warten. Der Prüfungsplan wird vorbereitet …": "Please wait. Preparing verification plan…",
  "Dateien, Ziele und Konflikte werden geprüft …": "Verifying files, destinations and conflicts…",
  "Der Archivbestand wird rein lesend geprüft …": "Verifying archive inventory read-only…",
  "Diese Applied-Änderung vollständig verwerfen und den Zustand vor der Bearbeitung wiederherstellen?": "Discard this applied change and restore the state before editing?",
  "Diese noch nicht abgeschlossene Änderung vollständig verwerfen und den gespeicherten Ursprungszustand wiederherstellen?": "Discard this unfinished change and restore the saved original state?",
  "Rückänderung vorbereiten": "Prepare reversal",
  "Rückarbeit prüfen · weiter": "Verify restoration · continue",
  "Hinweis zur Finder-Rückarbeit": "Finder restoration note",
  "NOTFALLABBRUCH": "EMERGENCY CANCEL",
  "Schritt 2 von 2 · event.json ersetzen": "Step 2 of 2 · replace event.json",
  "Keine Pfadänderungen.": "No path changes.",
  "Quellen werden erneut per SHA-256 geprüft und sicher verschoben …": "Rechecking sources with SHA-256 and moving files safely…",
  "Metadatenkorrektion": "Metadata correction",
  "Metadatenkorrektur": "Metadata correction",
  "Ohne-Datum-Bestand": "Undated inventory",
  "Keine Ohne-Datum-Familien vorhanden.": "No undated families found.",
  "Ohne-Datum-Familien": "Undated families",
  "Prüfung starten.": "Start verification.",
  "Der Ordner ist leer.": "This folder is empty.",
  "Quelle": "Source",
  "Quellen": "Sources",
  "Auswählen": "Select",
  "Noch nicht geprüft": "Not yet verified",
  "Keine offenen Metadatenaufträge.": "No pending metadata tasks.",
  "Metadatenkorrektur · Allgemein": "Metadata Correction · General",
  "Prüfung abgeschlossen. Es wurde noch nichts verändert.": "Verification completed. Nothing was changed.",
  "Mehrfachkorrektur": "Batch correction",
  "Metadaten prüfen": "Review metadata",
  "Tatsächliches Datum": "Actual date",
  "Tatsächliche Uhrzeit": "Actual time",
  "Dateien in den verwalteten Ordner legen und erneut prüfen.": "Place files in the managed folder and verify again.",
  "Links eine Datei auswählen.": "Select a file on the left.",
  "Korrigieren": "Correct",
  "Auswahl aufheben": "Clear selection",
  "Auswahl beenden": "Finish selection",
  "Datei auswählen": "Select file",
  "Ordner leer": "Folder empty",
  "Dateien auswählen": "Select files",
  "Einträge ausgewählt.": "Entries selected.",
  "Keine Aufnahmezeit": "No capture time",
  "keine Aufnahmezeit": "no capture time",
  "korrigiert · wartet auf Einsortierung": "corrected · awaiting sorting",
  "Prüfung/Korrektur erforderlich": "Verification/correction required",
  "Metadaten erneut ändern": "Edit metadata again",
  "Metadaten ändern": "Edit metadata",
  "Zuletzt geprüft": "Last checked",
  "Aufnahmen": "Photos",
  "Mehrere Aufnahmegeräte": "Multiple cameras",
  "Mehrere Kameras": "Multiple cameras",
  "Metadatenquelle übernehmen": "Use metadata source",
  "In Tagesbestand übernehmen": "Move into daily inventory",
  "Bestand prüfen.": "Verify inventory.",
  "Ordnerimport fehlgeschlagen; Rollback unvollständig:": "Folder import failed; rollback incomplete:",
})

# Patterns only translate fixed interface prefixes/counters, retaining arbitrary paths,
# event names and user input unchanged in capture groups.
# New event/import/archival UI literals; existing stored values are not migrated.
UI_TRANSLATIONS.update({
  "Laufwerksimport": "Drive Import",
  "Metadaten-Testbestand": "Metadata Test Dataset",
  "Simulierter SD-Import": "Simulated SD Import",
  "Hintergrundauftrag": "Background Job",
  "Künstlicher Testbestand für Aufnahmedaten, Dateifamilien und Prüffälle.": "Synthetic test data for capture timestamps, file families and review cases.",
  "Testlauf des automatischen Ablaufs vom Kopieren bis zum geprüften Arbeitsbereich.": "Dry run of the automated process from copying to the verified workspace.",
  "Echter Import mit Sicherung, SHA-256-Prüfung und Überführung in den Arbeitsbereich.": "Real import with backup, SHA-256 verification and transfer into the workspace.",
  "Technischer Verarbeitungsvorgang der Kamera-Automatisierung.": "Technical background processing job for the camera automation.",
  "Ordnerimport mit SHA-256, ExifTool, Gerätenamen und Tagesgruppierung.": "Folder import with SHA-256, ExifTool, device names and day grouping.",
  "SD-Kartenimport mit SHA-256, ExifTool, Gerätenamen und Tagesgruppierung.": "SD card import with SHA-256, ExifTool, device names and day grouping.",
  "Laufwerksimport mit SHA-256, ExifTool, Gerätenamen und Tagesgruppierung.": "Drive import with SHA-256, ExifTool, device names and day grouping.",
  "Auftragsverlauf": "Job history",
  "Import erfolgreich abgeschlossen.": "Import completed successfully.",
  "Bitte warten. Der Prüfungsplan wird vorbereitet …": "Please wait. Preparing the verification plan…",
  "Die Sortierung kann erst angewendet werden, wenn alle Blocker beseitigt sind und der Plan erneut mit „Bereit“ abgeschlossen wird.": "Sorting can only be applied after all blockers are resolved and the plan is marked ready again.",
  "ARCHIVIERTES Ereignis: Die Kamerabibliothek bleibt strikt read-only. Nach dem Speichern erhältst du einen manuellen Änderungsauftrag mit IST- und SOLL-Zustand.": "ARCHIVED event: the camera library stays strictly read-only. Saving creates a manual change request comparing actual and intended states.",
  "Keine Zielgruppen im Sortierplan.": "No destination groups in the sorting plan.",
  "Keine Dateifamilien in diesem Bereich.": "No file families in this area.",
  "Keine Segmente gespeichert.": "No saved segments.",
  "Keine zugeordneten Familien.": "No assigned families.",
  "Keine Einzeldateien in dieser Familie.": "No individual files in this family.",
  "Die Standardansicht ist nach Zielordnern gruppiert. Zielgruppen zeigen zunächst nur Familien- und Dateianzahl. Familien lassen sich anschließend bis zu den vollständigen Einzeldateipfaden aufklappen.": "The default view is grouped by destination folders. Destination groups initially show only the number of families and files. Expand a family to view its individual file paths.",
  "Dieser Wiederherstellungsbereich wird erst mit „Rückänderung vorbereiten“ angelegt:": "The recovery area is created only after selecting “Prepare reversal”:",
  "ZIELORDNER AUF DER SSD": "DESTINATION FOLDERS ON SSD",
  "IM ARCHIV": "IN ARCHIVE",
  "NOCH ZU ENTFERNEN": "STILL TO REMOVE",
  "VON": "FROM",
  "IST": "ACTUAL",
  "ZU ENTFERNEN": "TO REMOVE",
  "NOTFALLABBRUCH: Der ursprüngliche Archivbestand ist danach NICHT als wiederhergestellt bestätigt. Das Ereignis bleibt bis zur erneuten Prüfung gesperrt. Fortfahren?": "EMERGENCY CANCEL: The original archive inventory will NOT be marked as restored. This event will remain blocked until reverified. Continue?",
  "Gib zur Bestätigung exakt NOTFALLABBRUCH ein:": "Type NOTFALLABBRUCH exactly to confirm:",
  "Rückänderungsauftrag gestartet. Stelle jetzt den ursprünglichen Archivzustand wieder her.": "Reversal request started. Restore the original archive state now.",
  "Bitte Input-Ordner wählen · momentan unbekannt": "Choose an input folder · currently unknown",
  "Prüfung fehlgeschlagen": "Verification failed",
  "Mehrere Aufnahmegeräte": "Multiple cameras",
  "Alle": "All",
  "Sortiert": "Sorted",
  "Ohne_Datum": "Undated",
  "Allgemein": "General",
  "Später zuordnen": "Assign Later",
  "Freigewordene Archivdateien": "Released Archive Files",
  "Prüffälle": "Items requiring review",
  "Tag": "Day",
  "Ort": "Location",
})

# Additional user-facing API error messages and import status strings.
UI_TRANSLATIONS.update({
  "Ungültige Importkennung.": "Invalid import ID.",
  "Nur Kamera-/Ordnerimporte können entfernt werden.": "Only camera and folder imports can be removed.",
  "Nur fehlgeschlagene oder unterbrochene Importe können entfernt werden.": "Only failed or interrupted imports can be removed.",
  "Unsicherer temporärer Importpfad.": "Unsafe temporary import path.",
  "Mehrere Aufnahmegeräte": "Multiple cameras",
  "Kontrollierter Testbestand wurde als unverändert bestätigt.": "Controlled test inventory verified without changes.",
  "Quelldatei stimmt nach der Übernahme nicht mehr mit dem verifizierten Import überein.": "The source file no longer matches the verified import after transfer.",
  "Mehrfachkorrektur wurde in den Tagesbestand übernommen.": "Batch correction was transferred into daily inventory.",
  "Ausgewählte Allgemein-Dateien wurden in den Tagesbestand übernommen.": "Selected General files were transferred into daily inventory.",
  "Abgebrochener Import konnte nicht vollständig bereinigt werden:": "Cancelled import could not be fully cleaned up:",
  "Keine registrierte Primärbibliothek.": "No registered primary library.",
  "Der Workspace-Mount ist nicht verfügbar.": "Workspace mount is unavailable.",
  "Arbeitsbereich und Archiv dürfen nicht ineinander liegen.": "The workspace and archive must not overlap.",
  "Ungültiger relativer Quellpfad.": "Invalid relative source path.",
  "Die ausgewählte Importquelle wurde nicht gefunden.": "Selected import source not found.",
  "Importquelle ist kein zulässiger Ordner.": "The import source is not an allowed directory.",
  "Ungültiger Ordnerpfad.": "Invalid folder path.",
  "Bitte einen einzelnen Quellordner auswählen.": "Select a single source folder.",
  "Der gesamte NAS-Quellenbereich kann nicht importiert werden. Bitte einen einzelnen Unterordner wählen.": "You cannot import the entire NAS source root. Select one of its subfolders.",
  "Nur laufende Kameraimporte können hier abgebrochen werden.": "Only active camera imports can be cancelled here.",
  "Erzwungener Abbruch angefordert. Nur eigene Importdateien werden sicher zurückgerollt.": "Forced cancellation requested. Only files owned by this import will be rolled back safely.",
  "Abbruch wurde angefordert. Der Import wird sicher zurückgerollt.": "Cancellation requested. The import will be rolled back safely.",
  "Unterbrochener Import wurde vollständig aus dem Verlauf entfernt.": "Interrupted import was fully removed from history.",
  "Kein JPEG-Vorschaubild verfügbar.": "No JPEG preview available.",
  "Die ausdrückliche Sicherheitsbestätigung fehlt.": "Explicit safety confirmation is missing.",
  "Papierkorb ist noch nicht vollständig leer.": "The trash is not completely empty.",
  "Metadatenauftrag auswählen": "Select metadata task",
  "Metadatenaufträge werden geladen …": "Loading metadata tasks…",
  "Keine Metadatenaufträge vorhanden": "No metadata tasks available",
  "keine Prüfung nötig": "no verification required",
  "automatisch ausgewählt": "selected automatically",
  "Das passende Ereignis ist nicht mehr verfügbar.": "The matching event is no longer available.",
  "Mindestens eine ausgewählte Familie ist nicht mehr frei.": "At least one selected family is no longer available.",
  "Für die Archiv-Erweiterung fehlt der ausgewählte freie Zeitraum.": "The selected free time range for the archive extension is missing.",
  "Die Änderung überschneidet sich mit belegter Zeit. Bitte zuerst das andere Ereignis bearbeiten und die Zeit freigeben.": "This change overlaps occupied time. Edit the other event first and release the period.",
  "Die Änderung würde ein nicht archiviertes Ereignis teilen oder vollständig überdecken. Dieser Sonderfall muss zuerst eindeutig aufgelöst werden.": "The change would split or completely overlap an unarchived event. Resolve this case first.",
  "In den gewählten Zeitsegmenten gibt es keine freien Dateifamilien.": "No free file families were found in the selected time segments.",
  "Mehrfachkorrektur ist für diesen Bereich nicht verfügbar.": "Batch correction is not available for this area.",
  "Metadatenpfad verlässt den verwalteten Bereich.": "Metadata path lies outside the managed directory.",
  "Eine ausgewählte Ohne-Datum-Familie wurde nicht gefunden.": "A selected undated family was not found.",
  "Eine ausgewählte Allgemein-Datei wurde nicht gefunden.": "A selected General file was not found.",
  "Die Mehrfachauswahl enthält ungültige Einträge.": "The multiple selection contains invalid entries.",
  "Bibliothek für die Ohne-Datum-Familie fehlt.": "The library for the undated family is missing.",
  "Keine Allgemein-Datei zum Einsortieren ausgewählt.": "No General file selected for sorting.",
  "Vor der Übernahme in den Tagesbestand muss jede ausgewählte Datei eine belastbare Aufnahmezeit besitzen.": "Each selected file must have a reliable capture time before transfer into daily inventory.",
  "Keine korrigierte Dateifamilie zum Einsortieren ausgewählt.": "No corrected file family selected for sorting.",
  "Die ausgewählte Allgemein-Datei wurde nicht gefunden:": "Selected General file not found:",
  "Bitte das externe Laufwerk zuerst ausschließlich lesend einbinden.": "Mount the external drive read-only first.",
  "Der Ordner liegt außerhalb des ausgewählten Laufwerks.": "The folder is outside the selected drive.",
  "Bitte einen Unterordner auswählen.": "Select a subfolder.",
  "Ausgewählten Ordner prüfen …": "Checking selected folder…",
  "Ordner konnte nicht geprüft werden.": "Could not verify folder.",
  "Sichtbarkeit konnte nicht geändert werden.": "Could not change visibility.",
  "Sicherung konnte nicht gelöscht werden.": "Could not delete backup.",
  "Zähler für ausgeblendete Importe konnte nicht geladen werden.": "Could not load hidden import count.",
  "Import & Prüfung wird aktualisiert …": "Refreshing Import & Review…",
  "Externes Laufwerk wurde ausschließlich lesend eingebunden.": "External drive mounted read-only.",
  "Bitte zuerst einen Ordner im eingebundenen Laufwerk auswählen.": "Select a folder on the mounted drive first.",
  "Bitte zuerst eine Importquelle auswählen.": "Select an import source first.",
  "Ungültige Transferauswahl.": "Invalid transfer selection.",
  "Freigewordene Archivdateien nach ausdrücklicher Freigabe auf die SSD kopieren.": "Copy released archive files to the SSD after explicit approval.",
  "Freigewordene Archivdateien auf der SSD gegen gespeicherte SHA-256 prüfen.": "Verify released archive files on SSD against stored SHA-256 checksums.",
  "Nach bestätigter SSD-Kopie prüfen, dass die Archivoriginale entfernt wurden.": "After verifying the SSD copy, confirm the original archive files were removed.",
  "Manuelle Archivänderung rein lesend gegen die Kamerabibliothek prüfen.": "Verify the manual archive change against the camera library read-only.",
  "Die zugehörigen Dateien werden unwiderruflich gelöscht.": "Associated files will be permanently deleted.",
  "Möchtest du wirklich fortfahren?": "Do you really want to continue?",
  "Diese Sicherung wird vollständig aus dem Arbeitsbestand gelöscht.": "This backup will be completely removed from the working inventory.",
  "Keine Unterordner": "No subfolders",
  "Metadatenkandidaten": "Metadata candidates",
  "Datum/Uhrzeit": "Date/time",
  "Dateigröße": "File size",
  "Die Standardansicht ist nach Zielordnern gruppiert.": "The default view groups items by destination folder.",
  "Keine registrierte Bibliothek.": "No registered library.",
})

# Archive verification/status fragments shown inside dynamically rendered cards.
UI_TRANSLATIONS.update({
  "Arbeitsbereich freigegeben": "Workspace released",
  "Kamerabibliothek wird vollständig per Größe und SHA-256 geprüft …": "Verifying the entire camera library using file sizes and SHA-256…",
  "Kamerabibliothek und Arbeitsbereich-Dateien werden erneut per SHA-256 geprüft. Anschließend wird nur der bestätigte SSD-Ereignisbestand entfernt …": "Rechecking camera library and workspace files using SHA-256. Only verified SSD event files will then be removed…",
  "Keine offenen Ereignisse zur Archivprüfung.": "No events pending archive verification.",
  "Archiv wird geladen …": "Loading archive…",
  "Archivverlauf wird geladen …": "Loading archive history…",
  "Keine offenen Aufgaben": "No open tasks",
  "Keine freigegebenen Ereignisse": "No released events",
  "Quellpfad": "Source path",
  "Zielpfad": "Destination path",
  "Dateibestand": "File inventory",
  "Belegter Speicher": "Used storage",
  "Sichtbare Importe": "Visible imports",
  "Dateien bestätigt": "Files verified",
  "fehlen": "missing",
  "weichen ab": "mismatched",
  "Von": "From",
  "Zu": "To",
  "Quelle löschen": "Delete source",
  "Umbenennen": "Rename",
  "Ordner prüfen": "Verify folder",
  "Ort ändern": "Change location",
  "Schreibgeschützt": "Read-only",
  "Prüfprotokoll": "Verification log",
  "Jeder Schritt wird dokumentiert.": "Every step is logged.",
  "Prüfauftrag": "Verification task",
  "Ausgeführt": "Executed",
  "Nicht ausgeführt": "Not executed",
  "Quelle sichern": "Back up source",
  "Zuordnung": "Assignment",
  "Zugeordnet": "Assigned",
  "Anzahl": "Count",
  "Sortierplan": "Sorting plan",
  "Tagesübersicht": "Day overview",
  "Ereignisstatus": "Event status",
})

# All remaining literal German HTML labels and help attributes from the
# audit of the seven browser page modules, excluding variable user data.
UI_TRANSLATIONS.update({
  "SD-Importe, Systemstatus und Prüfvorgänge an einem Ort": "SD imports, system status and verification in one place",
  "Nur Dateien mit identischer Größe und identischem SHA-256 werden automatisch übersprungen.": "Only files with identical size and SHA-256 are automatically skipped.",
  "Sicherung löschen": "Delete backup",
  "werden ergänzt. Hardlinks werden bevorzugt; falls Quelle und Ziel auf unterschiedlichen Dateisystemen liegen, fragt Bibliothekar ausdrücklich nach": "will be added. Hard links are preferred; if source and destination are on different file systems, Bibliothekar explicitly asks for",
  ": Die benötigten Zielordner unter": ": The required destination folders under",
  "werden angelegt. Die Dateien selbst kopiert Bibliothekar erst im nächsten Schritt nach deiner ausdrücklichen Freigabe.": "will be created. Bibliothekar only copies files in the next step after your explicit approval.",
  "Jetzt kannst du ausschließlich die unten aufgeführten Originale manuell aus der Kamerabibliothek entfernen. Die App löscht dort selbst nichts.": "You may now manually remove only the originals listed below from the camera library. The app itself does not delete anything there.",
  "Die Vorschau zeigt nur die Planung. Es werden noch keine Ordner verändert.": "The preview only shows the plan. No folders have been changed.",
  "Nicht angehakte Tageskarten innerhalb sichtbarer Sicherungen werden automatisch nach Zeitraum einbezogen. Hier werden nur zusätzliche Aufnahmen aus aktuell ausgeblendeten aktiven Sicherungen bestätigt.": "Unselected day cards from visible backups are included automatically by date range. Only additional photos from currently hidden active backups are confirmed here.",
  "Diese Dateien besitzen noch kein belastbares Aufnahmedatum und können deshalb keinem Ereignis zugeordnet werden.": "These files do not have a reliable capture date and cannot yet be assigned to an event.",
  "Diese Namen betreffen ausschließlich von Bibliothekar verwaltete Ordner innerhalb des Workspace-Mounts. Metadatenkorrektur → Allgemein liegt automatisch im Unterordner": "These names apply only to folders managed by Bibliothekar inside the workspace mount. Metadata Correction → General is automatically placed in the subfolder",
  "Diese Namen betreffen ausschließlich von Bibliothekar verwaltete Ordner innerhalb des Workspace-Mounts. Der Standardunterordner für allgemeine Metadatenkorrektur heißt": "These names apply only to folders managed by Bibliothekar inside the workspace mount. The default subfolder for general metadata correction is called",
  ". Bereits vorhandene Ordnernamen bleiben unverändert; ein zusätzlicher TrueNAS-Host-Path ist nicht nötig.": ". Existing folder names are preserved; no additional TrueNAS host path is required.",
  "Nach der Bestätigung werden alle Quelldateien vollständig per SHA-256 geprüft und erst danach innerhalb des SSD-Arbeitsbereichs ohne Überschreiben verschoben. Die Kamerabibliothek bleibt unberührt; bei einem Fehler wird automatisch zurückgerollt.": "After confirmation, all source files are fully verified by SHA-256 and then moved within the SSD workspace without overwriting existing files. The camera library remains unchanged; errors trigger an automatic rollback.",
  "Die App prüft den realen Archivzustand read-only. Noch vorhandene Dateien werden an ihren ursprünglichen Ort zurückverschoben; fehlende Originale kommen aus dem vorbereiteten SSD-Rückbestand.": "The app verifies the actual archive state read-only. Files still present are moved back to their original location; missing originals come from the prepared SSD recovery inventory.",
  "Freigewordene Archivdateien werden zuerst sicher auf die SSD zurückgeholt. Erst danach folgt die eigentliche Umstrukturierung im Archiv. „Aktualisieren“ prüft den tatsächlichen Archivbestand und passt VON-Pfade sowie Erledigt-Status an.": "Released archive files are first recovered safely to SSD. Archive restructuring follows only afterward. Refresh checks the actual archive inventory and updates source paths and completion states.",
  "Keine Dateien entsprechen den gewählten Filtern.": "No files match the selected filters.",
  "Dateien entsprechen den gewählten Filtern.": "Files match the selected filters.",
  "Metadatenkorrektur → Allgemein": "Metadata Correction → General",
})

UI_PATTERNS = [
  ["^Arbeitsbereich-Bestand für „(.+)“ freigeben\\? Die Kamerabibliothek wird erneut vollständig geprüft; erst danach werden ausschließlich die bestätigten Dateien im Arbeitsbereich entfernt\\.$", "Release workspace files for “$1”? The camera library will be fully reverified first. Only confirmed workspace files will then be removed."],
  ["^([0-9]+)/([0-9]+) Dateien bestätigt; ([0-9]+) fehlen; ([0-9]+) weichen ab\\.$", "$1/$2 files verified; $3 missing; $4 mismatched."],
  ["^([0-9]+) Dateien bestätigt; ([0-9]+) fehlen; ([0-9]+) weichen ab\\.$", "$1 files verified; $2 missing; $3 mismatched."],
  ["^([0-9]+) Familien · Mehrere Aufnahmegeräte - (.+)$", "$1 families · Multiple cameras - $2"],
  ["^Ordnerimport · (.+)$", "Folder Import · $1"],
  ["^Laufwerksimport · (.+)$", "Drive Import · $1"],
  ["^SD-Kartenimport · (.+)$", "SD Card Import · $1"],
  ["^([0-9]+) Datei(en)? · ([0-9]+) Familien$", "$1 files · $3 families"],
  ["^([0-9]+) Familien · Mehrere Aufnahmegeräte(.*)$", "$1 families · Multiple cameras$2"],
  ["^([0-9]+) Familien · ([0-9]+) Dateien · ([0-9.,]+) GiB$", "$1 families · $2 files · $3 GiB"],
  ["^([0-9]+) Familien · (.+?) - ([0-9]{4}\\.[0-9]{2}\\.[0-9]{2}) - (.+)$", "$1 families · $2 - $3 - $4"],
  ["^([0-9]+) Dateien · ([0-9]+) Familien · ([0-9]+) Sicherungen$", "$1 files · $2 families · $3 backups"],
  ["^([0-9]+) Dateien · ([0-9]+) Familien · ([0-9]+) Tagen$", "$1 files · $2 families · $3 days"],
  ["^Zuletzt aktualisiert:\\s*(.+)$", "Last updated: $1"],
  ["^Unterereignis:\\s*(.+)$", "Subevent: $1"],
  ["^Erstellt:\\s*(.+)$", "Created: $1"],
  ["^Quelle:\\s*(.+)$", "Source: $1"],
  ["^Status:\\s*angewendet$", "Status: applied"],
  ["^Status:\\s*archiviert$", "Status: archived"],
  ["^Status:\\s*geplant$", "Status: planned"],
  ["^Status:\\s*gesperrt$", "Status: blocked"],
  ["^Status:\\s*(.+)$", "Status: $1"],
  ["^Ordner:\\s*(.+)$", "Folder: $1"],
  ["^Sicherung:\\s*(.+)$", "Backup: $1"],
  ["^([0-9]+) Tage$", "$1 days"],
  ["^([0-9]+) aktive Familien$", "$1 active families"],
  ["^([0-9]+) Familien · ([0-9]+) Dateien$", "$1 families · $2 files"],
  ["^([0-9]+) Dateien · ([0-9]+) Familien$", "$1 files · $2 families"],
  ["^([0-9]+) Familien\\s+([0-9]+) Dateien$", "$1 families   $2 files"],
  ["^([0-9]+) Dateien\\s+([0-9]+) Familien$", "$1 files   $2 families"],
  ["^([0-9]+) Familien · ([0-9]+) Dateien · (.+)$", "$1 families · $2 files · $3"],
  ["^([0-9]+) Dateien · ([0-9]+) Familien · (.+)$", "$1 files · $2 families · $3"],
  ["^([0-9]+) Dateien und ([0-9]+) Familien$", "$1 files and $2 families"],
  ["^([0-9]+) Familien und ([0-9]+) Dateien$", "$1 families and $2 files"],
  ["^([0-9]+) Einträge ausgewählt\\.$", "$1 entries selected."],
  ["^Metadatenquelle übernehmen \\(([0-9]+)\\)$", "Use metadata source ($1)"],
  ["^In Tagesbestand übernehmen \\(([0-9]+)\\)$", "Move into daily inventory ($1)"],
  ["^Offene Aufgaben · ([0-9]+)$", "Open tasks · $1"],
  ["^Offene Aufgaben · ([0-9]+) · (.+)$", "Open tasks · $1 · $2"],
  ["^([0-9]+) Dateien liegen in aktuell ausgeblendeten aktiven Sicherungen und gehören ebenfalls zu diesem Zeitraum\\.$", "$1 files are in currently hidden active backups and belong to the same date range."],
  ["^([0-9]+) weitere Familien · (.+)$", "$1 more families · $2"],
  ["^([0-9]+) neue Familien passen zu (.+)$", "$1 new families match $2"],
  ["^Fortgeführt: ([0-9]+) Familien$", "Continued: $1 families"],
  ["^Gespeichert: (.+) · ([0-9]+) Familien$", "Saved: $1 · $2 families"],
  ["^([0-9]+) Familien · Mehrere Aufnahmegeräte - (.+)$", "$1 families · Multiple cameras - $2"],
  ["^Mehrere Aufnahmegeräte - (.+)$", "Multiple cameras - $1"],
  ["^SD-Karte · (.+) · Bereit zum Einbinden$", "SD card · $1 · Ready to mount"],
  ["^SD-Karte · (.+) · Nur lesend eingebunden$", "SD card · $1 · Mounted read-only"],
  ["^SD-Karte · (.+)$", "SD card · $1"],
  ["^([0-9]+) Familien · ([0-9]+) Dateien · ([0-9]+) (.+)$", "$1 families · $2 files · $3 $4"],
  ["^([0-9]+) freigegebene Ereignisse$", "$1 released events"],
  ["^([0-9]+) Sicherungen$", "$1 backups"],
  ["^([0-9]+) Importaufträge$", "$1 import jobs"],
  ["^([0-9]+) neue Dateien$", "$1 new files"],
  ["^([0-9]+) Familien · mehrere Sicherungen$", "$1 families · multiple backups"],
  ["^([0-9]+) Ziele gehören zu offenen Nachsortierungen$", "$1 destinations belong to pending resort plans"],
  ["^([0-9]+) SSD-Kopien wurden angelegt und vollständig geprüft\\.$", "$1 SSD copies were created and fully verified."],
  ["^([0-9]+) ([^ ]+) wurden geprüft und in den Tagesbestand einsortiert\\.$", "$1 $2 were verified and sorted into daily inventory."],
  ["^Keine Ohne-Datum-Familien vorhanden\\.$", "No undated families found."],
  ["^Physischer Bestand geprüft · ([0-9]+) bekannte Dateien$", "Physical inventory verified · $1 known files"],
  ["^([0-9]+) Familien · (.+) - ([0-9]{4}\\.[0-9]{2}\\.[0-9]{2}) - (.+)$", "$1 families · $2 - $3 - $4"],
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

from app.ui_i18n_0504 import UI_0504_TRANSLATIONS, UI_0504_PATTERNS
UI_TRANSLATIONS.update(UI_0504_TRANSLATIONS)
UI_PATTERNS[:0] = UI_0504_PATTERNS
from app.ui_i18n_0505 import UI_0505_TRANSLATIONS, UI_0505_PATTERNS
UI_TRANSLATIONS.update(UI_0505_TRANSLATIONS)
UI_PATTERNS[len(UI_0504_PATTERNS):len(UI_0504_PATTERNS)] = UI_0505_PATTERNS
from app.ui_i18n_0506 import UI_0506_TRANSLATIONS, UI_0506_PATTERNS
UI_TRANSLATIONS.update(UI_0506_TRANSLATIONS)
UI_PATTERNS[len(UI_0504_PATTERNS) + len(UI_0505_PATTERNS):len(UI_0504_PATTERNS) + len(UI_0505_PATTERNS)] = UI_0506_PATTERNS

from app.ui_i18n_0507 import UI_0507_TRANSLATIONS, UI_0507_PATTERNS
UI_TRANSLATIONS.update(UI_0507_TRANSLATIONS)
UI_PATTERNS[:0] = UI_0507_PATTERNS

from app.ui_i18n_0508 import UI_0508_TRANSLATIONS, UI_0508_PATTERNS
UI_TRANSLATIONS.update(UI_0508_TRANSLATIONS)
UI_PATTERNS.extend(UI_0508_PATTERNS)

from app.ui_i18n_0509 import UI_0509_TRANSLATIONS, UI_0509_PATTERNS
UI_TRANSLATIONS.update(UI_0509_TRANSLATIONS)
UI_PATTERNS.extend(UI_0509_PATTERNS)

from app.ui_i18n_0511 import UI_0511_TRANSLATIONS, UI_0511_PATTERNS
UI_TRANSLATIONS.update(UI_0511_TRANSLATIONS)
UI_PATTERNS.extend(UI_0511_PATTERNS)

# 0.53.2 – trash selection, restoration, provenance, manual Undo and task labels.
UI_TRANSLATIONS.update({
    "Gesamten Papierkorb leeren": "Empty entire trash",
    "Auswahl leeren": "Empty selection",
    "Aus Papierkorb": "From Trash",
    "Ereignis archivieren": "Archive event",
    "Dateien werden in den Tagesbestand wiederhergestellt …": "Restoring files to daily inventory…",
    "Papierkorb wird geleert …": "Emptying trash…",
    "Manuelle Änderung rückgängig gemacht.": "Manual changes undone.",
    "Änderungen rückgängig machen": "Undo changes",
    "Rückgängig-Anleitung": "Undo instructions",
    "Nur im Dateisystem": "Only in the file system",
    "Nicht katalogisierte Datei:": "Uncatalogued file:",
    "Datei ist nicht mehr im Papierkorb:": "File is no longer in trash:",
    "Ungültige Lösch-Auswahl.": "Invalid deletion selection.",
    "Papierkorb-Löschjournal darf kein Symlink sein.": "The trash deletion journal must not be a symlink.",
})
UI_PATTERNS.extend([
    [r"^Aus Papierkorb(?=\s|$)", "From Trash"],
    [r"^([0-9]+) Dateien wiederhergestellt\.", "$1 files restored."],
    [r"^([0-9]+) Dateien wiederhergestellt\. ([0-9]+) unbekannte Dateien zur geprüften Übernahme vorgemerkt\\.", "$1 files restored. $2 previously unknown files queued for verified import."],
])

UI_TRANSLATIONS["Erneut prüfen"] = "Check Again"

from app.ui_i18n_rc1 import RC1_TRANSLATIONS, RC1_PATTERNS
UI_TRANSLATIONS.update(RC1_TRANSLATIONS)
UI_PATTERNS.extend(RC1_PATTERNS)


UI_TRANSLATIONS["Neu einrichten"] = "Set up again"

UI_TRANSLATIONS.update({
    "Quellprüfung wartet auf Verarbeitung.":"Source check is waiting to run.",
    "Prüfung abbrechen":"Cancel check",
    "Prüfung abgebrochen. Keine Dateien verändert.":"Check cancelled. No files were changed.",
    "Quelle wird vollständig geprüft.":"Checking the complete source.",
})

UI_TRANSLATIONS.update({'Die historischen Einrichtungsbelege sind unvollständig oder widersprüchlich.': 'Historical setup records '
                                                                                 'are incomplete or '
                                                                                 'contradictory.',
 'Die früheren Verwaltungsordner sind nicht vollständig durch Identitäten belegt.': 'The previous management '
                                                                                    'folders do not all have '
                                                                                    'recorded identities.',
 'Die historischen Verwaltungsordner sind nicht eindeutig zugeordnet.': 'Historical management folders '
                                                                        'cannot be identified unambiguously.',
 'Die Workspace-Identität oder die historischen Ordnernamen sind nicht eindeutig bestätigt.': 'The workspace '
                                                                                              'identity or '
                                                                                              'historical '
                                                                                              'folder names '
                                                                                              'cannot be '
                                                                                              'confirmed.',
 'Die Datenbankablage widerspricht den historischen Bindungen.': 'The database location conflicts with the '
                                                                 'historical bindings.',
 'Im Archiv sind noch Daten vorhanden. Diese dürfen nicht als neue Installation übergangen werden.': 'The '
                                                                                                     'archive '
                                                                                                     'still '
                                                                                                     'contains '
                                                                                                     'data. '
                                                                                                     'A new '
                                                                                                     'setup '
                                                                                                     'cannot '
                                                                                                     'disregard '
                                                                                                     'it.',
 'Das konfigurierte Archiv ist nicht nachweislich erreichbar. Prüfen Sie zuerst seine Einbindung und Leserechte.': 'The '
                                                                                                                   'configured '
                                                                                                                   'archive '
                                                                                                                   'cannot '
                                                                                                                   'be '
                                                                                                                   'confirmed '
                                                                                                                   'as '
                                                                                                                   'accessible. '
                                                                                                                   'Check '
                                                                                                                   'its '
                                                                                                                   'mount '
                                                                                                                   'and '
                                                                                                                   'read '
                                                                                                                   'permissions '
                                                                                                                   'first.',
 'Ein früher gebundener externer Speicherort fehlt, wurde ersetzt oder enthält noch Daten.': 'A previously '
                                                                                             'bound external '
                                                                                             'location is '
                                                                                             'missing, has '
                                                                                             'been replaced, '
                                                                                             'or still '
                                                                                             'contains data.',
 'Im Arbeitsbereich sind noch Daten oder unbekannte Einträge vorhanden.': 'The workspace still contains data '
                                                                          'or unknown entries.',
 'Eine erhaltene Datenbank enthält noch frühere Aufträge oder Bestandsdaten.': 'A surviving database still '
                                                                               'contains previous jobs or '
                                                                               'media records.',
 'Die Registry enthält noch Bibliotheks- oder Bestandszuordnungen.': 'The registry still contains library or '
                                                                     'stock associations.',
 'Private Rückfallkopien sind noch vorhanden und müssen erhalten bleiben.': 'Private recovery copies still '
                                                                            'exist and must be preserved.',
 'Es bestehen noch ungeklärte Operations- oder Recoverybelege.': 'Unresolved operation or recovery records '
                                                                 'still exist.',
 'Die sichere Leerheit und Zuordnung der Installation ist noch nicht vollständig nachgewiesen.': 'The '
                                                                                                 'installation '
                                                                                                 'has not '
                                                                                                 'been fully '
                                                                                                 'verified '
                                                                                                 'as empty '
                                                                                                 'and '
                                                                                                 'correctly '
                                                                                                 'bound.',
 'Neue Einrichtung derzeit gesperrt': 'New setup is currently blocked',
 'Diagnose:': 'Diagnostic:',
 'Die leere Installation und ihre verbleibenden Bindungen wurden geprüft. Eine neue Einrichtung erfordert Ihre Bestätigung und bewahrt die bisherigen Identitätsbelege.': 'The '
                                                                                                                                                                          'empty '
                                                                                                                                                                          'installation '
                                                                                                                                                                          'and '
                                                                                                                                                                          'its '
                                                                                                                                                                          'remaining '
                                                                                                                                                                          'bindings '
                                                                                                                                                                          'have '
                                                                                                                                                                          'been '
                                                                                                                                                                          'checked. '
                                                                                                                                                                          'Setting '
                                                                                                                                                                          'it '
                                                                                                                                                                          'up '
                                                                                                                                                                          'again '
                                                                                                                                                                          'requires '
                                                                                                                                                                          'your '
                                                                                                                                                                          'confirmation '
                                                                                                                                                                          'and '
                                                                                                                                                                          'preserves '
                                                                                                                                                                          'previous '
                                                                                                                                                                          'identity '
                                                                                                                                                                          'records.',
 'Stoppen Sie die App und weitere Schreibzugriffe. Sichern Sie alle erhaltenen Datenbanken einschließlich WAL-Dateien, Konfiguration, Journale und Retentionskopien. Stellen Sie die ursprünglichen Dataset-Einbindungen und einen zusammengehörigen Sicherungsstand wieder her. Danach erneut prüfen. Keine Operationsnachweise löschen und keine leeren Ersatzordner über vorhandene Daten legen.': 'Stop '
                                                                                                                                                                                                                                                                                                                                                                                                      'the '
                                                                                                                                                                                                                                                                                                                                                                                                      'app '
                                                                                                                                                                                                                                                                                                                                                                                                      'and '
                                                                                                                                                                                                                                                                                                                                                                                                      'other '
                                                                                                                                                                                                                                                                                                                                                                                                      'writers. '
                                                                                                                                                                                                                                                                                                                                                                                                      'Back '
                                                                                                                                                                                                                                                                                                                                                                                                      'up '
                                                                                                                                                                                                                                                                                                                                                                                                      'all '
                                                                                                                                                                                                                                                                                                                                                                                                      'surviving '
                                                                                                                                                                                                                                                                                                                                                                                                      'databases '
                                                                                                                                                                                                                                                                                                                                                                                                      'including '
                                                                                                                                                                                                                                                                                                                                                                                                      'WAL '
                                                                                                                                                                                                                                                                                                                                                                                                      'files, '
                                                                                                                                                                                                                                                                                                                                                                                                      'configuration, '
                                                                                                                                                                                                                                                                                                                                                                                                      'journals '
                                                                                                                                                                                                                                                                                                                                                                                                      'and '
                                                                                                                                                                                                                                                                                                                                                                                                      'retention '
                                                                                                                                                                                                                                                                                                                                                                                                      'copies. '
                                                                                                                                                                                                                                                                                                                                                                                                      'Restore '
                                                                                                                                                                                                                                                                                                                                                                                                      'the '
                                                                                                                                                                                                                                                                                                                                                                                                      'original '
                                                                                                                                                                                                                                                                                                                                                                                                      'dataset '
                                                                                                                                                                                                                                                                                                                                                                                                      'mounts '
                                                                                                                                                                                                                                                                                                                                                                                                      'and '
                                                                                                                                                                                                                                                                                                                                                                                                      'a '
                                                                                                                                                                                                                                                                                                                                                                                                      'consistent '
                                                                                                                                                                                                                                                                                                                                                                                                      'backup '
                                                                                                                                                                                                                                                                                                                                                                                                      'set, '
                                                                                                                                                                                                                                                                                                                                                                                                      'then '
                                                                                                                                                                                                                                                                                                                                                                                                      'check '
                                                                                                                                                                                                                                                                                                                                                                                                      'again. '
                                                                                                                                                                                                                                                                                                                                                                                                      'Do '
                                                                                                                                                                                                                                                                                                                                                                                                      'not '
                                                                                                                                                                                                                                                                                                                                                                                                      'delete '
                                                                                                                                                                                                                                                                                                                                                                                                      'operation '
                                                                                                                                                                                                                                                                                                                                                                                                      'records '
                                                                                                                                                                                                                                                                                                                                                                                                      'or '
                                                                                                                                                                                                                                                                                                                                                                                                      'place '
                                                                                                                                                                                                                                                                                                                                                                                                      'empty '
                                                                                                                                                                                                                                                                                                                                                                                                      'replacement '
                                                                                                                                                                                                                                                                                                                                                                                                      'folders '
                                                                                                                                                                                                                                                                                                                                                                                                      'over '
                                                                                                                                                                                                                                                                                                                                                                                                      'existing '
                                                                                                                                                                                                                                                                                                                                                                                                      'data.'})

from app.ui_rc13 import workspace_words, TRANSLATIONS as RC13_TRANSLATIONS, PATTERNS as RC13_PATTERNS
UI_TRANSLATIONS.update(RC13_TRANSLATIONS)
UI_TRANSLATIONS.update({workspace_words(k):workspace_words(v) for k,v in list(UI_TRANSLATIONS.items())})
UI_TRANSLATIONS.update({k:workspace_words(v) for k,v in list(UI_TRANSLATIONS.items())})
UI_PATTERNS[:0] = RC13_PATTERNS
UI_PATTERNS = [[workspace_words(k),workspace_words(v)] for k,v in UI_PATTERNS]

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
  // Page titles are outside document.body and are not visited by the DOM walk.
  const originalDocumentTitle = typeof document.title === "string" ? document.title : null;
  function updateDocumentTitle() {
    if (originalDocumentTitle !== null) {
      document.title = locale === "en" ? tr(originalDocumentTitle) : originalDocumentTitle;
    }
  }
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
    // Standalone dated source labels are stored names, including old generated
    // labels. Translate the surrounding UI separately, never the saved name.
    if (!core.includes(" · ") && /^.+ - [0-9]{4}\.[0-9]{2}\.[0-9]{2} - [0-9]{4}\.[0-9]{2}\.[0-9]{2}$/u.test(core)) return value;
    // HTML templates often wrap fixed labels across indented lines.
    // Normalize whitespace *only for exact dictionary lookups*, never for
    // user-supplied paths/filenames or captured dynamic values.
    let result = dictionary[core];
    if (result === undefined) result = dictionary[core.replace(/\s+/gu, " ")];
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
    const desired = locale === "en" ? tr(source) : (tr(source) !== source ? source : restoreGerman(source));
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
      const desired = locale === "en" ? tr(source) : (tr(source) !== source ? source : restoreGerman(source));
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
    updateDocumentTitle();
    try { localStorage.setItem(key, next); } catch (_) {}
    if (document.body) walk(document.body);
    updateChoiceButtons();
    window.dispatchEvent(new CustomEvent("bk-language-changed", {detail: {locale: next}}));
  }
  // Native browser dialogs do not create DOM nodes. Localise only their
  // visible messages, never confirmation return values or typed user input.
  function dialogMessage(value) {
    const text = String(value ?? "");
    if (locale !== "en") return text;
    return text.split(/(\r?\n)/u).map(part => part === "\n" || part === "\r\n" ? part : tr(part)).join("");
  }
  const originalAlert = window.alert.bind(window);
  const originalConfirm = window.confirm.bind(window);
  const originalPrompt = window.prompt.bind(window);
  window.alert = function (message) { return originalAlert(dialogMessage(message)); };
  window.confirm = function (message) { return originalConfirm(dialogMessage(message)); };
  window.prompt = function (message, defaultValue) {
    return arguments.length > 1
      ? originalPrompt(dialogMessage(message), defaultValue)
      : originalPrompt(dialogMessage(message));
  };
  // Unlike native Safari confirm(), these buttons use the selected application
  // language rather than the phone's system UI language.
  function confirmAsync(message) {
    if (!document.body || typeof document.createElement !== "function") {
      return Promise.resolve(originalConfirm(dialogMessage(message)));
    }
    const dialog = document.createElement("dialog");
    if (typeof dialog.showModal !== "function") {
      return Promise.resolve(originalConfirm(dialogMessage(message)));
    }
    dialog.className = "bk-i18n-dialog";
    dialog.setAttribute("aria-label", locale === "en" ? "Confirmation" : "Bestätigung");
    const text = document.createElement("p");
    text.className = "bk-i18n-dialog-message";
    text.textContent = dialogMessage(message);
    const actions = document.createElement("div");
    actions.className = "bk-i18n-dialog-actions";
    const cancel = document.createElement("button");
    cancel.type = "button";
    cancel.textContent = locale === "en" ? "Cancel" : "Abbrechen";
    const accept = document.createElement("button");
    accept.type = "button";
    accept.className = "bk-i18n-confirm";
    accept.textContent = locale === "en" ? "Confirm" : "Bestätigen";
    actions.append(cancel, accept);
    dialog.append(text, actions);
    return new Promise(resolve => {
      let completed = false;
      const finish = accepted => {
        if (completed) return;
        completed = true;
        try { dialog.close(); } catch (_) {}
        dialog.remove();
        resolve(accepted);
      };
      cancel.addEventListener("click", () => finish(false));
      accept.addEventListener("click", () => finish(true));
      dialog.addEventListener("cancel", event => { event.preventDefault(); finish(false); });
      dialog.addEventListener("close", () => finish(false));
      document.body.appendChild(dialog);
      try { dialog.showModal(); cancel.focus(); }
      catch (_) { finish(originalConfirm(dialogMessage(message))); }
    });
  }
  // Translate generated preview labels while leaving actual paths and folder
  // names unchanged (including legacy German directory names).
  function previewText(value) {
    const source = String(value ?? "");
    if (locale !== "en") return source;
    return source.split(/(\r?\n)/u).map(line => {
      if (line === "\n" || line === "\r\n") return line;
      const m = line.match(/^(\s*)(Zeitraum:|Auswahl:|Keine Zielstruktur vorhanden\.|Der gewählte Zeitraum ist ungültig\.)(.*)$/u);
      if (m) {
        const labels = {
          "Zeitraum:": "Period:",
          "Auswahl:": "Selection:",
          "Keine Zielstruktur vorhanden.": "No destination structure available.",
          "Der gewählte Zeitraum ist ungültig.": "The selected date range is invalid."
        };
        let details = m[3];
        if (m[2] === "Auswahl:") {
          details = details.replace(/([0-9]+) Dateien/u, "$1 files").replace(/([0-9]+) Familien/u, "$1 families");
        }
        return m[1] + labels[m[2]] + details;
      }
      if (/^\s*bis [0-9]{4}-[0-9]{2}-[0-9]{2}/u.test(line))
        return line.replace(/^(\s*)bis /u, "$1to ");
      if (/^\s*[0-9]{4}-[0-9]{2}-[0-9]{2} /u.test(line))
        return line.replace(/ bis (?=[0-9]{4}-[0-9]{2}-[0-9]{2})/u, " to ");
      return tr(line);
    }).join("");
  }
  // Application-owned prompt: Safari's native buttons follow the device
  // locale rather than Bibliothekar's selected locale.
  function promptAsync(message, defaultValue = "") {
    if (!document.body || typeof document.createElement !== "function")
      return Promise.resolve(originalPrompt(dialogMessage(message), defaultValue));
    const dialog = document.createElement("dialog");
    if (typeof dialog.showModal !== "function")
      return Promise.resolve(originalPrompt(dialogMessage(message), defaultValue));
    dialog.className = "bk-i18n-dialog";
    dialog.setAttribute("aria-label", locale === "en" ? "Input required" : "Eingabe erforderlich");
    const text = document.createElement("p");
    text.className = "bk-i18n-dialog-message";
    text.textContent = dialogMessage(message);
    const input = document.createElement("input");
    input.className = "bk-i18n-prompt-input";
    input.type = "text";
    input.value = String(defaultValue ?? "");
    const actions = document.createElement("div");
    actions.className = "bk-i18n-dialog-actions";
    const cancel = document.createElement("button");
    cancel.type = "button";
    cancel.textContent = locale === "en" ? "Cancel" : "Abbrechen";
    const accept = document.createElement("button");
    accept.type = "button";
    accept.className = "bk-i18n-confirm";
    accept.textContent = locale === "en" ? "Confirm" : "Bestätigen";
    actions.append(cancel, accept);
    dialog.append(text, input, actions);
    return new Promise(resolve => {
      let finished = false;
      const finish = answer => {
        if (finished) return;
        finished = true;
        try { dialog.close(); } catch (_) {}
        dialog.remove();
        resolve(answer);
      };
      cancel.addEventListener("click", () => finish(null));
      accept.addEventListener("click", () => finish(input.value));
      input.addEventListener("keydown", event => {
        if (event.key === "Enter" && !event.isComposing) { event.preventDefault(); finish(input.value); }
      });
      dialog.addEventListener("cancel", event => { event.preventDefault(); finish(null); });
      dialog.addEventListener("close", () => finish(null));
      document.body.appendChild(dialog);
      try { dialog.showModal(); input.focus(); }
      catch (_) { finish(originalPrompt(dialogMessage(message), defaultValue)); }
    });
  }
  window.BibliothekarI18n = Object.freeze({
    t: (value) => locale === "en" ? tr(String(value)) : restoreGerman(String(value)),
    getLocale: () => locale,
    setLocale,
    confirmAsync,
    promptAsync,
    previewText,
  });
  document.documentElement.lang = locale;
  document.documentElement.dataset.bkLocale = locale;
  updateDocumentTitle();
  function init() {
    document.querySelectorAll("[data-bk-language-choice]").forEach(button => {
      button.addEventListener("click", () => setLocale(button.dataset.bkLanguageChoice));
    });
    updateChoiceButtons();
    walk(document.body);
    // The shell is already translated at this point. Keep only the not-yet-parsed
    // main content hidden until DOMContentLoaded, then translate and reveal it
    // in the same task. API fetching never gates the shell or the main content.
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", () => {
        walk(document.body);
        delete document.documentElement.dataset.bkI18nPending;
      }, {once: true});
    } else {
      delete document.documentElement.dataset.bkI18nPending;
    }
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
  // On normal PWA pages the shell is present before <main>. Translate it
  // immediately so the dock, subnav and title are usable during HTML parsing.
  // Sign-in/first-run pages keep their existing DOM-ready initialization.
  if (document.readyState === "loading" && !document.querySelector?.(".bk-shell")) {
    document.addEventListener("DOMContentLoaded", init, {once: true});
  } else {
    init();
  }
})();
""".replace("__DICTIONARY__", json.dumps(UI_TRANSLATIONS, ensure_ascii=False)).replace(
    "__PATTERNS__", json.dumps(UI_PATTERNS, ensure_ascii=False)
)
