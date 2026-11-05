# RC10 ohne Clean Slate übernehmen

Noch keine produktive Upgradefreigabe. Diese Schritte sind für eine spätere kontrollierte Abnahme vorgesehen.

## Voraussetzungen

1. Alte Containerinstanz vollständig anhalten. Kein paralleles RC10/RC11, keine aktiven externen Bearbeitungen der betroffenen technischen Bereiche.
2. Konsistente Sicherung von Config, allen Katalogen und Registry **zusammen mit** WAL/SHM, F14-Bereich und Retention erstellen. Eine unkoordinierte Kopie allein der Haupt-SQLite-Dateien ist unzureichend. Backup-/Snapshotreferenz dokumentieren.
3. Tatsächliche private ACLs und deren Eltern gemäß [Sicherheitsmodell](SECURITY.md) administrativ qualifizieren. Workspace-ACL nicht pauschal verändern.
4. Herkunft der zuvor potenziell fremdbeschreibbaren RC10-Nachweise prüfen. Nachträgliches Härtung und Hashgleichheit beweisen keine frühere Unverändertheit. Bei ungeklärter Herkunft oder widersprüchlicher Historie nicht übernehmen.

## Bereits begonnener Erststart

Mit dem noch freizugebenden RC11-Image, unveränderten Mountpfaden und ohne laufenden Webprozess, als UID/GID 568:568 ausführen:

```sh
python -m app.storage_admin inspect
```

Dies prüft die aktuelle private Autorität, die exakte Startupreservation, Schlüssel/ID/Generation/Bindings, alle Kataloge und Registryhistorie sowie Retention und technische Struktur. Es gibt einen Token für genau den beobachteten Bestand aus. SQLite wird im Read-only-Modus mit WAL-sichtbarem Snapshot geprüft; SQLite kann dabei technische SHM-Dateien anlegen. Die Prüfung ist deshalb keine immutable Offlineforensik eines ungesicherten Originals.

Erst nach Prüfung der Ausgabe und der konsistenten Sicherung ausdrücklich entscheiden:

```sh
python -m app.storage_admin adopt \
  --token '<Token aus inspect>' \
  --confirmation 'ADOPT RC10 BOOTSTRAP' \
  --backup-reference '<dokumentierter konsistenter Snapshot oder Backup>'
```

Die Backupreferenz ist eine ausdrückliche Betreiberbestätigung, kein automatisch verifiziertes Backupzertifikat. Der Übernahmebeleg speichert Originalbytes von State und eigener Operation, logische Katalogfingerprints und das alte Lock. Die Bestätigung überstimmt keine Medienhistorie, fremde Operation, Retention, falsche Identität oder unsichere ACL.

Danach RC11 mit dem originalen Supervisor starten. Es übernimmt die bisherige Reservation-ID und die echten Bindings, führt technische Schritte idempotent fort und schreibt Abschlussbelege. Der alte Lock bleibt unverändert erhalten. Nach Anmeldung müssen erste Bibliothekserstellung und mehrere Neustarts erfolgreich sein.

Bei jeder fertigen Format-1-Bestandsinstallation wird entsprechend `inspect --scope control` und `adopt --scope control` verwendet. Dieser Pfad setzt weder Nutzungsdaten zurück noch erklärt er eine vorhandene Bibliothek zur Neuinstallation. Offene fachliche Operationen oder fehlende/andere gebundene Ordner müssen zuerst nach dem bestehenden Recoveryvertrag geklärt werden.

Bei abweichenden Pfaden sind `--workspace` und `--database` sowie die tatsächlichen `KAMERA_*`-Konfigurationswerte konsistent zu setzen. Keine Inodes, IDs oder Hashverzeichnisse von einem anderen NAS kopieren. Die reale Vorlage in den Tests enthält die gemeldete Reservation; die Produktlogik enthält keine feste NAS-ID.

## Nachprüfung

- `storage-health` bereit, keine aktive Bootstrapoperation und keine ursprünglichen Fehler.
- Reservation-ID und vorherige Rollenidentitäten gleich.
- Ursprüngliche Nachweise im Übernahmebeleg erhalten; keine SQLite-/Retentionbereinigung.
- Private `trash-recovery.lock` vorhanden; kein neues aktives Workspace-Lock.
- Erstbibliothek über Web anlegbar, nach Neustart vorhanden und weitere geschützte Mutation erfolgreich.
- Archiv bytegleich und weiterhin RO gemountet.

Bei jeder Ablehnung Nachweise sichern und die konkrete Ursache bearbeiten. Kein manuelles Setzen von `completed`, kein Löschen von Operationsdateien und kein Clean Slate.
