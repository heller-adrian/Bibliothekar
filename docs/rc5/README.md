# RC5: technische Abnahme und anschließende NAS-Probe

Vorbereitet: `1.0.0-rc.5`, noch keine Veröffentlichung.
Produktbasis `e788208fb479aefb569cd2b46acbc65051de6bfb`, Tree
`691c335c0dce41d5c1f1fa3085822496d96fed00`. Produktänderungen dieser Vorbereitung
sind Versionssubstitutionen und die belegte Linux-Korrektur für reine POSIX-
Default-ACLs auf bereits bestehenden Vorfahren (keine Access-ACL-Freigabe); Quellvertrag in `qa/release/rc5.json`.

## Vor dem Update: konsistente Rückfallbasis

Der neue Worker/Startup kann fehlgeschlagene Restores automatisch finalisieren.
**Vor dem ersten Start** deshalb Schreibzugriffe beenden und die App vollständig
stoppen. Keine laufenden SQLite-Dateien isoliert kopieren. Bei gestoppter App den
vollständigen privaten Datenbankbereich einschließlich vorhandener `-wal`-,
`-shm`-/Journaldateien, Registry, F14-Verwaltung und
`.bibliothekar-restore-retention` zusammen sichern. Auch `/config`, die relevanten
Workspacebereiche (`Trash`, `Metadata Correction/.trash-import`,
`SD Card Backups/.incoming` sowie vorhandene historische Namen), Originale und
Journale im selben ruhenden Stand sichern. Vorhandene Retention niemals weglassen.
Sicherungen auf separaten Testpfaden auf SQLite-Integrität/Fremdschlüssel und
Medienhashes prüfen; nur an Kopien arbeiten. Kein Clean Slate/SQL-UPDATE und keine
manuelle Journalbereinigung. ACLs und Besitzerinformationen der Rückfallbasis
mitbewahren; konsistente Wiederherstellbarkeit vor dem Update nachweisen.

## Zunächst isolierte TrueNAS-Testinstallation

1. Separate Test-App mit Kopien/synthetischen Daten, separatem Port und eigenen
   privaten DB-/Config-Datasets sowie Workspace/Archiv starten. Keine produktiven
   Pfade einbinden. Compose-Vorlage erst nach Veröffentlichungsfreigabe und mit
   tatsächlich veröffentlichtem Digest einsetzen.
2. Bestehende NAS-Nachweise berücksichtigen: `/database` und `/config` sind RW-
   Bind-Mounts aus dem Appdata-Bereich, Web568:568 ohne Zusatzgruppen. Private
   Verzeichnisse und Hosteltern müssen dem [Retentionsvertrag](../../qa/rc4-practice/PRIVATE-RETENTION.md)
   entsprechen. UID568, privater Dataset-Eigentümer (hier3000), root und
   Administratorgruppen0/544 sind vertrauenswürdig; andere Prozesse mit diesen
   IDs sind nicht isoliert. Gruppenmitgliedschaft und Mountgrenzen nachweisen.
3. Native NFS4-XDR-ACL-Lesbarkeit und echte vererbte Zielrechte prüfen. Benutzer
   wie hermes3001 dürfen private DB-/Retentionsdaten weder ändern noch ersetzen
   oder löschen. Gemeinsame Fotoablagen behalten ihre legitimen SMB/NFS-Rechte.
   Keine pauschalen chmod/chown-/ACL-Anpassungen. Die spätere Katalog-Provisionierung
   privater App-Datasets ist weiterhin separat.
4. Frisches Onboarding, Login/Logout, sechs Seiten und mobile DE/EN-Darstellung
   prüfen. SD-Mount weiter tatsächlich read-only und manuelle geschützte NFS4-
   ACL-Voraussetzung des SD-Helpers beachten; kein fremdes Gerät aushängen.
5. Synthetischen fehlgeschlagenen Restore mit gültigem Fingerprint starten/
   wiederanlaufen lassen: Job bleibt failed samt Fehlertext; private Kopien und
   Auditbeleg entstehen; danach reguläres vollständiges Leeren möglich.
   Fingerprint-Mismatch, fehlende Kopien, unklare Protokolle, fremde Schreibrechte
   und echte aktive Restores müssen gesperrt bleiben. Neustart und Speicher-
   platzfehler an Testdaten gegenprüfen. Keine native NAS-Abnahme aus Linux-PASS ableiten.

## Danach gesicherter vorhandener Bestand

Erst nach bestandener isolierter Probe und geprüfter Rückfallbasis das reale
Update ausdrücklich freigeben. Beim bekannten Auftrag
`TRASH_IMPORT_20261023_205446_538D89094806` vollständigen gespeicherten Fingerprint
gegen tatsächlichen Bestand prüfen lassen. Sein Präfix `f9611220` genügt nicht.
Nur ein valider privater Abschluss darf die JPG-/RAF-Reservierung aufheben.
Originalprotokoll/Stage und Rückfallbytes bleiben erhalten. Bei Ablehnung den
konkreten Grund sichern, nichts manuell entsperren. Bei fehlendem historischem
Anker ist die getrennt ausdrücklich bestätigte Variantenrettung möglich;
sie behauptet keine historische Originalidentität und umgeht keinen gültigen
abweichenden Fingerprint.

Archivumbenennung, SD-Prüfung/Ergänzungsimport, Metadaten, Arbeitsbereich-Freigabe,
Papierkorb/Restore und Smartphone-Navigation gezielt praktisch gegenprüfen.
Akzeptierte F13/F24-Restrisiken bleiben dokumentiert; B12 bleibt zurückgestellt.
Linux-QA ersetzt keine TrueNAS-/ZFS-/NFS4-/SMB-Geräteabnahme.
