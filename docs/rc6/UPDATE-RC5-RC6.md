# RC5 → RC6 auf der bestehenden TrueNAS-Testinstallation

1. Vor dem Update alle Datei-/Import-/Restoreaufträge prüfen, App und sämtliche weiteren Schreiber stoppen. Konsistente Rückfallbasis anlegen: vollständiger /database-Bereich inklusive vorhandener SQLite-WAL/SHM-/Journaldateien, Registry, F14-Verwaltung und .bibliothekar-restore-retention; /config; relevante Workspace-Originale, Trash, Metadata Correction/.trash-import, SD Card Backups/.incoming samtProtokollen/Journals und historischen Verzeichnisnamen. ACLs/Besitzer mitbewahren. Keine einzelne laufende DB kopieren. Kopien auf isolierten Pfaden durch SQLite-Integrität/Fremdschlüssel und Medienhashes prüfen.
2. Zunächst eine isolierte Test-App mit eigenen Datasets, Port und synthetischen Daten verwenden. Keine zweite Instanz an dieselben schreibbaren Pfade anschließen. Neue private Retention und tatsächliche NFSv4-ACL-/Parent-/UID-Grenze prüfen; keine vorhandenen ACLs pauschal lockern. Keine neuen Snapshots oder Rechteumbauten erforderlich.
3. Release-Assets und SHA256SUMS prüfen. In der bestehenden App nur das Image auf die vollständige Referenz aus IMAGE-DIGEST.txt setzen: ghcr.io/heller-adrian/bibliothekar@sha256:… . Der feste Tag1.0.0-rc.6 ist ebenfalls verfügbar. Das ausgelieferte compose.truenas.yaml ist digestgebunden, enthält aber Beispielpfade; nicht über die funktionierende App-Konfiguration kopieren.
4. Bestehende Mounts, Hostpfade, Ports, Registry-Datenbankpfad, Passwortdatei und Umgebungsvariablen erhalten. Webprozess568:568, Helper intern. Die funktionierende manuelle NFSv4-ACL des SD-Mountbereichs und seiner Eltern erhalten: Web-UID/GID568:568 liest/durchquert, schreibt dort nicht. Keine rekursive chmod/chown-/ACL-Anweisung und keine Helperumgehung. Die spätere automatische Katalogbereitstellung bleibt offen.
5. Starten, Browser neu laden, anmelden und Version1.0.0-rc.6 prüfen. Vorhandene Bibliotheken müssen erscheinen. Bei unerwartetem Onboarding/Storage-/ACL-/DB-Fehler stoppen, konkrete Logs sichern. Kein Clean Slate, keine Ersatzbibliothek, keine Journalbereinigung.
6. Achtung: Der Worker kann beim Startup Failed-Restores automatisch finalisieren. Im isolierten Test gültigen Fingerprint, private Rückfallbytes/Auditbeleg, fortbestehenden Failed-Status und Originalfehler kontrollieren; danach reguläres Leeren testen. Fingerprint-Mismatch, fehlende Kopien, unklare Fremdschreibrechte oder aktive Restores müssen weiterhin sperren. Drei Neustarts und freie Speichergrenze an Testdaten prüfen. Erst nach dieser Probe den konsistent gesicherten Bestand weiter testen.
7. Beim bekannten TRASH_IMPORT_20261023_205446_538D89094806 muss der vollständige gespeicherte Fingerprint mit dem aktuellen Manifest übereinstimmen; das bekannte Präfix f9611220 genügt nicht. Bei Ablehnung nichts manuell entsperren. Die gesondert bestätigte Variantenrettung ist kein Nachweis historischer Originalidentität und darf keinen gültigen abweichenden Fingerprint umgehen.
8. SD-Hintergrundprüfung, Ergänzungsimport/Duplikate, EN/DE/Mobilvorschau, Metadaten, Archivumbenennung, Arbeitsbereich-Freigabe und Papierkorb/Restore mit synthetischen Daten nachtesten. Bildhashes und Journale erhalten. Akzeptierte F13/F24-Risiken bleiben unverändert. Downgrade allein ist kein Datenbankrollback; gegebenenfalls gesamte geprüfte Rückfallbasis verwenden.

Keine automatische Installation oder Migration durch den Veröffentlichungsauftrag. Native TrueNAS-/ZFS-/NFSv4-/SMB-/Gerätequalifikation steht aus.


RC6 unterscheidet ausdrücklich echte neue Installationen, bestätigte vollständig
leere Altzustände und beschädigte vorhandene Installationen. Beim Update mit
vorhandenen Bibliotheken keine neue Initialisierung bestätigen; unerwartetes
Onboarding oder Identity-/Mountfehler untersuchen lassen. RC6-Ordner-/Laufwerksimporte
verwenden eine persistente vollständige Hintergrundprüfung. Bereits gesicherte
Quellen erzeugen keinen Null-Dateien-Import. Zwei gleiche Quellen dürfen überlappen,
aber erst nach frischer Katalogprüfung einen erforderlichen Import übergeben.

Abnahmegrundlage:1993 PASS/17 Fixture-FAIL im Originalgesamtlauf;17 Fehler gezielt
unter Linux behoben,2010 verschiedene Fälle mit PASS belegt; Containerabschluss PASS.
Kein einzelner grüner Gesamtlauf. Native TrueNAS-/ZFS-/NFSv4-Prüfung weiter offen.
