# Konkrete Speicherentscheidung für den Restoreabschluss

Basis: 717d7b8a1781dd7de63e5583320a7be7a7c347e8.
**Status: Umsetzung des Produktmechanismus wartet ausschließlich auf die unten
benannten Privatablagen-/Auftragsnachweise. Kein pauschales Entsperren.**

## Tatsächlich untersuchte vorhandene Ablagen

| Ablage | Tatsächlicher Quellvertrag | Noch fehlender NAS-Nachweis |
|---|---|---|
| `/database` | `compose.example.yaml` bindet einen konfigurierbaren Hostpfad RW ein. `Dockerfile` setzt beim Imagebau UID/GID568, jedoch keine Host-ACL. `container_supervisor.py` startet Web als568:568 ohne Zusatzgruppen. | Reale Mountquelle, Host-/Container-ID-Abbildung, ACLs des Mounts und seiner ersetzbaren Eltern. |
| SQLite/Registry | `database.connect()` und `library_registry._connect()` nutzen WAL, foreign_keys und synchronous FULL. Das schützt Transaktionen, authentifiziert aber keine fremd beschreibbaren DB-/WAL-/SHM-Dateien. | ACLs/Identitäten von `kamera.sqlite3`, globaler Registry und vorhandenen WAL-/SHM-Dateien. Alle registrierten DBs müssen vor einer späteren Abschlussentscheidung in den geprüften privaten Bereich fallen. |
| `/database/.bibliothekar-root-control/<sha256(/workspace)>` | Bereits vorhandene persistente F14-Koordination; Code prüft App-Eigentümer und0700-Verzeichnisse. | Effektive NFSv4-ACLs/Elternrechte; POSIX0700 allein qualifiziert diesen Bereich nicht. |
| `/config` | Separater Hostmount für Settings und Anmeldekonfiguration; dieselbe Bind-Mount-Grenze wie/database. | Mountquelle/ACL-Vererbung/Elternrechte. Kein Beweis allein durch die Bezeichnung „config“. |
| Workspace-Staging | Unter`Metadata Correction/.trash-import/<job>` liegen die bisherigen unabhängigen Bytekopien. | Laut neuer Nutzerauskunft fremde Schreib-/Lösch-ACEs. Andere Inodes bedeuten **keine separate Sicherheitsdomäne**. Diese Kopien dürfen nicht als exklusive Langzeitabsicherung ausgegeben werden. |
| SD-Helper-Verwaltung | Eigener privilegierter Mountledger, vor der Web-UID zu schützen. | Für Medienabschluss **nicht wiederverwenden**: anderer Eigentums-/Aufgabenvertrag; keine neue privilegierte Schnittstelle. |

Image-Rechte überdecken keine Rechte eines später darüber eingebundenen
Hostmounts. [Docker Bind-Mount-Vertrag](https://docs.docker.com/engine/storage/bind-mounts/).
Die aktuelle Compose-Datei qualifiziert die privaten Hostbereiche nicht selbst.

Der angekündigte Originalanhang `Eingefügter Text(9).txt` war in den verfügbaren
Anhängen/Downloads nicht auffindbar. Die explizite Nutzerauskunft zu allen neun
Workspacepfaden und sechs ACE-Identitäten ist Grundlage dieser Entscheidung;
keine Behauptung, die vollständige originale ACE-Reihenfolge gelesen zu haben.

## Vorhandener konkreter Vertrauensanker: source_fingerprint

`folder_import.manifest_fingerprint()` hasht sortiert **relative Namen, Größen
und SHA-256-Werte sämtlicher Manifestdateien**. Mtime allein genügt nicht.
`run_folder_import_job()` veröffentlicht diesen Wert über`identity_callback`
**vor** der Importpartition/Dateiveröffentlichung. `set_job_source_identity()`
speichert ihn mit BEGIN IMMEDIATE in`jobs.source_fingerprint`; ein danach
fehlgeschlagener Job kann ihn behalten. Die ursprüngliche`source_signature`
ist dagegen nur ein schneller Name/Größe/Mtime-Nachweis.

Dies ist eine konkrete Alternative zum Vertrauen in`Protocol/status.json`:
Falls die DB geschützt ist und der historische Auftrag einen **vollständigen,
nicht leeren** Fingerprint besitzt, kann ein frisch FD-gebunden aufgenommenes
Manifest damit verglichen werden. Ein Fingerprint des leeren Manifests,
NULL/fehlender Wert, abweichende Hashes/Namen/Größen oder unklare Vollständigkeit
berechtigen nicht zum Abschluss. Der Fingerprint des realen Auftrags liegt
hier noch nicht vor; sein Vorhandensein wird nicht vorausgesetzt.

Zusätzlicher kleiner Nachweis über die vorhandene angemeldete Web-App:
`/api/jobs/TRASH_IMPORT_20261023_205446_538D89094806` öffnen und nur`id`,
`operation`, `state`, `source_path`, `source_fingerprint`, `source_signature`
und`result.failure_finalization` liefern. Der tatsächlich vorhandene
`api_job_detail()`-Handler startet keinen Abschluss. Kein SQL-UPDATE.

## Kleinste tragfähige technische Option

**Empfehlung: geschützte SQLite-Abschlussbelege plus geschützte Rückfallbytes
im vorhandenen privaten App-Datenbereich.** Eine reine SQL-Markierung oder
Protokollkopie genügt nicht. Die bisherigen Workspacekopien dürfen zusätzlich
bestehen bleiben, sind unter den berichteten ACEs aber keine Isolationsgarantie.

Nach erfolgreicher Privatablagenqualifikation ist begrenzt umzusetzen:

1. Unter bestehender F14-/F11-Koordination DB-/Registryidentitäten, Auftrags-
   eigentum, aktiven Zustand, alle Kataloge und vollständige Dateipartition prüfen.
2. Vollständiges Medienmanifest per No-follow-FDs aufnehmen und mit dem **bereits
   privat persistierten** Quellenfingerprint bzw. vollständigen vertrauenswürdigen
   Datei-Hashbelegen vergleichen. Protokoll aus dem Workspace nur als
   unveränderte diagnostische Beilage lesen, nicht als Abschlussautorität.
3. Verifizierte Bytes exklusiv in einen kleinen jobgebundenen Retentionsbereich
   unter dem qualifizierten`/database`-App-Datenmount kopieren. **Keine Hardlinks
   zur offenen Domäne**, keine Quelllöschung; vollständige Hash-/Identitätsprüfung,
   fsync, Kapazitätsprüfung samt Reserve für SQLite/WAL. Keine Überschreibung
   vorhandener fremder Einträge. Ziel-ACLs und Elternbindung müssen tatsächlich
   passen, nicht nur die angeforderte0700/0600-Maske.
4. Vor Freigabe einen kanonischen Beleg mit Bibliotheks-/Workspace-/DB-Bindungen,
   erwartetem Quellenfingerprint, vollständigen Medienhashes und privaten
   Kopienidentitäten über **bestehendes**`jobs.result_json` und`audit_log`
   transaktional persistieren. Status und ursprünglicher Fehler bleiben failed.
   Kein neues allgemeines Journalsystem/Service erforderlich.
5. `protected_trash_paths()` darf erst anhand dieses privaten Belegs und frisch
   revalidierter privater Medienkopien freigeben. Mutable Workspacejournale
   können die Freigabe nicht selbst behaupten. Vor DB-Abschluss führt jeder
   Crash zur Sperre; nach Commit müssen wiederholte Starts denselben Beleg
   idempotent prüfen. Parallele Lösch-/Restoreoperationen bleiben koordiniert.

Das ist ein begrenzter Folgepatch an Abschluss-/Reservationscode plus
zweckgebundener Kopiensicherung. Er wird **nicht vorgetäuscht implementiert**,
solange der gewählte Zielbereich nicht als geschützt nachgewiesen ist.

### Falls der historische Fingerprint fehlt

Dann lässt sich die historische Originalidentität nicht aus ebenfalls
veränderbaren Workspacejournalen oder zwei gleichen Kopien rekonstruieren.
Vorgesehene Alternative: **ausdrücklich bestätigter Einzel-Recoveryauftrag**, der
alle noch vorhandenen Varianten unverändert in die qualifizierte private
Retention kopiert und verifiziert. Abweichende Original-/Stagevarianten getrennt
aufbewahren. Neu bestätigte aktuelle Bytes klar von historisch authentifizierten
Bytes unterscheiden. Keine stille Annahme „alles bereits gesichert“, keine
Änderung alter Journalzustände, keine automatische Übernahme in den Fotokatalog.
Ohne geschützte Retention bzw. bei fehlender letzter Kopie bleibt die Sperre.
Ein solcher Dialog ersetzt keine technische Zielprüfung.

## Genau benötigte neue NAS-Diagnose

Nur `/database`, `/config`, deren Eltern sowie die vorhandenen Verwaltungs-
und DB-Seitendateien untersuchen; die neun Workspace-ACLs nicht erneut sammeln.
Das beiliegende geprüfte Skript `private_store_diagnose.py` ermittelt die
**tatsächlichen** Mountquellen mit docker inspect, liest die Webprozess-UID/GID,
Zusatzgruppen und UID/GID-Maps und ruft ausschließlich`filesystem.getacl` mit
erweiterten Rechten/aufgelösten IDs auf. Es liest **keine** DB-, Medien-, Passwort-
oder Konfigurationsinhalte, öffnet keine SQLite-Verbindung, erzeugt keine
Dateien und ändert keine ACLs. Fehlende oder symlinkgebundene Pfade werden als
ungeklärt ausgegeben, nicht angelegt/aufgelöst. Es behauptet nie Isolation.

Einmal auf dem **TrueNAS-Host**, mit der beigefügten Datei im aktuellen Ordner:

```sh
python3 private_store_diagnose.py --container ix-bibliothekar-bibliothekar-1
```

Ausgabe und installierte TrueNAS-Version liefern. Bei verweigertem Lesezugriff
keine Rechte ändern. API-Signatur bei Versionsabweichung prüfen. Dokumentation:
[filesystem.getacl](https://api.truenas.com/v27.0/api_methods_filesystem.getacl.html).
Dies ist eine einmalige Diagnose des Altfalls, **kein künftiger Installations-
Pflichtschritt**. Root-/Namensraum-, NFS4-Deny/Allow-/Identitätsauswertung muss
anhand der echten Ausgabe erfolgen; ein ACL-JSON allein ist kein Kerneltest.

## Installations-/Katalogvertrag

Für neue Installationen über die TrueNAS-App-Oberfläche private persistente
App-Datasets/Volumes für DB/Config und Retention bereitstellen; keine Vererbung
breiter Foto-/SMB-Schreibrechte. Parent-Einträge, Benennungen, DB/WAL/SHM und
Retention müssen gegen nicht autorisierte Host-/SMB-/andere App-Schreiber
gebunden sein. Gemeinsame UID568 darf nicht als alleinige Prozessisolation
behauptet werden. Privilegierte Administratoren sind ausdrücklich festzulegen.
Schreibbare Fotodatasets und ihre legitimen Freigaben bleiben separat.

Installationsoberfläche/Paket muss Eigentümer/ACLs/Mounts korrekt provisionieren
und die Voraussetzungen nachprüfbar ausweisen. Die App darf bestehende NAS-ACLs
nicht heimlich reparieren. Kein manueller chmod/chown-Regelbetrieb, keine
Nutzung des Quellenhelpers als neuer Dateirechte- oder Recoverydienst.
Vollständige Katalogintegration bleibt separat; hier keine Deploymentänderung.

## Testergebnis und Abgrenzung

28 unterschiedliche gezielte Tests zuletzt PASS. Darunter:
- sechs berichtete ACE-Identitäten als **partielles Modell** (nicht vollständige
  Original-ACL); Diagnose bleibt auch dann `NOT_PERFORMED` statt „qualified“;
- echte0770-Dateimodi mit explizitem UID568/GID0-fstat-Modell;
- fremd beschreibbare Rückfall-Stages bleiben gesperrt; separate Prozesse
  modellieren durch ACEs zugelassene Schreiber und verändern/entfernen Kopien,
  setzen Symlinks/Hardlinks bzw. ersetzen den Elternordner: keine Freigabe;
- bestehende positive lokale Finalisierung und vollständiges Leeren mit
  behaltenen Rückfallbytes; manipulierter Zustand bleibt geschützt;
- vier echte SIGKILL-Grenzen mit je drei vollständigen Anwendungsstarts,
  zusätzliche negative Prozess-/Hash-/SQLite-Gegenproben, paralleler Abschluss;
- Quellenfingerprint bleibt bei failed nach drei unabhängigen SQLite-Lese-
  prozessen erhalten und bindet Pfad, Größe, Hash; schnelle Signatur kann
  bei byteveränderter Datei gleich bleiben und wird nicht als Ersatz verwendet.

Kein echtes NFSv4-/Linux-UID3000/3001-Experiment, kein neuer Container-/NAS-
Nachweis. Die simulierten Fremdschreiber verwenden die lokale Host-UID; ihre
Berechtigung wird modelliert, nicht aus einem NFSv4-Kernel abgeleitet.

**Produktdateien bleiben unverändert.** UI, SD, Namen, Archiv, F11/F14/F24 und
alte Tests bleiben erhalten. Kein Gesamtlauf, CI, Release oder NAS-Eingriff.
Konkrete Restgrenze: **Privatablagenqualifikation plus realer gespeicherter
Quellenfingerprint**. Nach deren Vorlage steht die obige kleine technische
Option fest; keine Wiederholung des gesamten Audits notwendig.
