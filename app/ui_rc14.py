"""RC14 presentation catalogue. Dynamic names and physical paths are opaque."""
ERRORS={
 'library_remove_main_forbidden':'Die Hauptbibliothek kann nicht entfernt werden.',
 'library_remove_confirmation_required':'Die Entfernung muss ausdrücklich bestätigt werden.',
 'library_remove_workspace_not_empty':'Der Arbeitsordner ist nicht leer. Ungesicherte Dateien bleiben geschützt.',
 'library_remove_archive_not_readonly':'Das externe Archiv muss schreibgeschützt eingebunden sein.',
 'library_remove_open_events':'Offene Ereignisse müssen vor der Entfernung abgeschlossen werden.',
 'library_remove_unsecured_inventory':'Der Katalog enthält noch nicht archivierte Dateien.',
 'library_remove_unsecured_claims':'Besitzansprüche enthalten noch nicht gesicherte Dateien.',
 'library_remove_reserved_claims':'Eine laufende Reservierung verhindert die Entfernung.',
 'import_recovery_ownership_ambiguous':'Die Dateiidentität ist nicht eindeutig. Staging und Nachweise bleiben erhalten.',
 'import_recovery_origin_missing':'Der ursprüngliche Herkunftsnachweis ist unvollständig. Der Import bleibt gesperrt.',
 'import_recovery_journal_missing':'Das Veröffentlichungsjournal fehlt. Die Kopien bleiben zur Prüfung erhalten.',
}


def error_text(error):
    raw=str(error);code,separator,path=raw.partition(': ')
    return ERRORS.get(code,raw)+((': '+path) if separator and code in ERRORS else '')


TRANSLATIONS={
 'Die Hauptbibliothek kann nicht entfernt werden.':'The main library cannot be removed.',
 'Die Entfernung muss ausdrücklich bestätigt werden.':'Explicit confirmation is required to remove the library.',
 'Der Arbeitsordner ist nicht leer. Ungesicherte Dateien bleiben geschützt.':'The workspace is not empty. Unsecured files remain protected.',
 'Das externe Archiv muss schreibgeschützt eingebunden sein.':'The external archive must be mounted read only.',
 'Offene Ereignisse müssen vor der Entfernung abgeschlossen werden.':'Open events must be completed before removing the library.',
 'Der Katalog enthält noch nicht archivierte Dateien.':'The catalogue still contains files that have not been archived.',
 'Besitzansprüche enthalten noch nicht gesicherte Dateien.':'Ownership claims still contain unsecured files.',
 'Eine laufende Reservierung verhindert die Entfernung.':'An active reservation prevents removing the library.',
 'Die Dateiidentität ist nicht eindeutig. Staging und Nachweise bleiben erhalten.':'File identity is ambiguous. Staged copies and evidence remain intact.',
 'Der ursprüngliche Herkunftsnachweis ist unvollständig. Der Import bleibt gesperrt.':'Original provenance is incomplete. The import remains blocked.',
 'Das Veröffentlichungsjournal fehlt. Die Kopien bleiben zur Prüfung erhalten.':'The publication journal is missing. Copies are retained for review.',
 'Auftrag ist fehlgeschlagen.':'Job failed.',
 'Direkter IST→SOLL-Abgleich im Arbeitsbereich':'Verifying current versus planned workspace state',
 'Direkter IST→SOLL-Abgleich im SSD-Arbeitsbereich':'Verifying current versus planned workspace state',
 'Technische ID':'Technical ID', 'z. B. Business':'e.g. Business',
 'Prüfung PASS · Hardlinks zum Zentralbestand möglich.':'Verification passed · hard links to central inventory are possible.',
 'Prüfung PASS · Hardlinks zum Zentralbestand nicht möglich.':'Verification passed · hard links to central inventory are not possible.',
 'Der Arbeitsbereich muss ein absoluter Containerpfad sein.':'Workspace must be an absolute container path.',
 'Das Archiv muss ein absoluter Containerpfad sein.':'Archive must be an absolute container path.',
 'Verwaltungsordner fehlen oder sind nicht eindeutig verfügbar. Vorgänge sind gesperrt.':'Managed storage folders are missing or ambiguous. Operations are paused.',
 'Ungeklärtes Import-Staging verhindert den Stammordnerwechsel.':'Unresolved import staging prevents changing the library root.',
 'Wiederherstellung abgeschlossen':'Restoration completed.',
 'im Arbeitsbereich erhalten.':'in the workspace.',
 'Bibliothek entfernen':'Remove library',
 'Bibliothek entfernen? Archiv, Datenbank und Arbeitsordner bleiben erhalten. Historische Besitznachweise werden aufbewahrt. Späterer Wiedereinzug nur über Folder Import.':'Remove library? The archive, database and workspace remain intact. Historical ownership evidence is retained. Reimport later using Folder Import only.',
 'Import prüfen und fortsetzen':'Review and resume import',
 'Staging behalten und Auftrag schließen':'Keep staged backup and close job',
 'Geprüften ursprünglichen Import fortsetzen? Es wird dieselbe Auftrags- und Quellenidentität verwendet.':'Resume the verified original import? The same job and source identities will be used.',
 'Staging bleibt erhalten. Es wird kein freier Bestand freigegeben.':'Staged backup retained. No unassigned inventory was published.',
 'Import wurde zur sicheren Fortsetzung vorgemerkt.':'Import queued for verified continuation.',
}
PATTERNS=[
 [r'^([0-9]+) freie Familie$','$1 unassigned family'],
 [r'^([0-9]+) freie Familien$','$1 unassigned families'],
 [r'^([0-9]+) Familie · freier Tagesbestand$','$1 family · unassigned daily inventory'],
 [r'^([0-9]+) Familien · freier Tagesbestand$','$1 families · unassigned daily inventory'],
 [r'^Ereignis gelöscht: (.+) · ([0-9]+) Familie wieder frei\.$','Event deleted: $1 · $2 family returned to unassigned inventory.'],
 [r'^Ereignis gelöscht: (.+) · ([0-9]+) Familien wieder frei\.$','Event deleted: $1 · $2 families returned to unassigned inventory.'],
 [r'^Technische ID: (.+)$','Technical ID: $1'],
 [r'^Bibliothek „(.+)“ wurde erstellt\.$','Library “$1” created successfully.'],
 [r'^Der gespeicherte Bibliotheks-Arbeitsbereich ist nicht verfügbar: (.+)$','The registered library workspace is unavailable: $1'],
 [r'^Das Archiv überschneidet sich mit (.+)\.$','The archive overlaps with $1.'],
 [r'^Der Arbeitsbereich überschneidet sich mit (.+)\.$','The workspace overlaps with $1.'],
 [r'^library_workspace_name_collision: (.+)$','A workspace with this name already exists. Choose a different name: $1'],
 [r'^Importprüfung: ([0-9]+) Dateien im Staging, ([0-9]+) Dateien veröffentlicht\.$','Import verification: $1 staged files, $2 published files.'],
]
for message in ERRORS.values():
    import re
    if message in TRANSLATIONS:
        PATTERNS.insert(0,[r'^'+re.escape(message)+r': (.+)$',TRANSLATIONS[message]+': $1'])
