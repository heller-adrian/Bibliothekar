# Historischer 0770-Protokollrest – BLOCKED

Basis: aebb88835c0bafb4f49794a149f527654d7113d6.

## Reproduktion und Status

Der vom Benutzer gemeldete `.incoming/<job>/Protocol/status.json`-Inhalt passt
inhaltlich zum engen Status-only-Schema. UID568/GID0 und Dateigröße808 ändern
jedoch nichts an der aktuellen Ablehnung: **0770 & 0022 = 0020**.

- `Protocol` wird an der Verzeichnisprüfung zurückgewiesen, bevor die
  Statusdatei geöffnet wird. Falls `.incoming/<job>` selbst ebenfalls unsicher
  beschreibbar ist, greift schon die davor liegende Prüfung.
- Bei sicherem Verzeichnismodus und Datei0770 greift die Dateiprüfung.
- Verzeichnis-nlink2 ist normal und kein Ablehnungsgrund. Datei-nlink1 und
  UID568 bei App-EUID568 erfüllen diese beiden separaten Bedingungen.
- Die numerische GID0 wird bisher nicht als Vertrauensbeweis ausgewertet.

Neue Tests verwenden echte0770-Modi, eine echte808-Byte-Datei und die gemeldete
Job-ID samt NAS-Pfaden im Dokument. UID/GID568:0 werden ausdrücklich im fstat
modelliert. Lokal läuft macOS mit502:20; Docker/Podman/QEMU sind nicht vorhanden.
**Kein nativer Linux568:0- oder NFSv4-ACL-Nachweis wurde erreicht.**

25 unterschiedliche gezielte Tests zuletzt PASS: acht neue Prüfungen sowie
13 bestehende Unsicherheitsfälle und vier bestehende automatische SIGKILL-
Grenzen mit je drei vollständigen Anwendungsneustarts. Die neue negative
SIGKILL-Probe unterbricht eine FD-gebundene Lesebeweisprüfung; drei neue Prozesse
bestätigen danach weiterhin Sperre, unveränderte Journale/Protokollbytes,
Original-/Kopienhashes, SQLite-Integrität und Fremdschlüssel. Diese negative Probe
ist kein zusätzlicher vollständiger Anwendungsstarttest.

Ein bestehender lokaler0700/0600-Protokollfall finalisiert automatisch und
ermöglicht reguläres vollständiges Leeren; unabhängige Rückfallkopien,
Protokoll, Journal und failed-Status bleiben erhalten. Das ist ausdrücklich
**kein positiver0770-/TrueNAS-Nachweis**. Die echten gruppenschreibbaren Fälle
bleiben einschließlich regulärem Leeraufruf409 gesperrt.

## Warum weder chmod noch bloßes Kopieren genügt

TrueNAS unterstützt eigene NFSv4-ACLs mit benannten Identitäten und
Vererbungsregeln. Neben WRITE_DATA/APPEND_DATA können insbesondere DELETE,
DELETE_CHILD, WRITE_ACL und WRITE_OWNER die Bindung beeinflussen. Daher belegen
weder GID0 noch eine vermutete Rootgruppenbelegung im Container die tatsächliche
Host-/SMB-Schreibgrenze. Ebenso wenig beweist ein neu angeforderter0600/0700-
Modus, dass eine geerbte NFSv4-ACL keine zusätzlichen Rechte einräumt.

Eine Protokollkopie bewahrt zunächst nur die gelesenen Bytes. Ohne geprüften
Zielnamensraum/ACL sowie konsistente Quell-, Job- und Katalogbelege beweist sie
keinen sicheren Abschluss. Ein bloßes `chmod` kann ACLs verändern, an einem
restricted-Dataset scheitern oder vorhandene andere Berechtigungen bestehen
lassen. Es gibt hier keine Anweisung zur produktiven Rechteänderung.

Quellen: [TrueNAS ACL-Typen/Vererbung](https://www.truenas.com/docs/scale/24.10/scaleuireference/datasets/editaclscreens/),
[filesystem.getacl – vollständige ACL-Rechte](https://api.truenas.com/v25.04.0/api_methods_filesystem.getacl.html),
[filesystem.setacl – ACL-/Modusbezug](https://api.truenas.com/v25.04.2/api_methods_filesystem.setacl.html).
Upstream-OpenZFS-Angaben zu Linux-NFSv4 sind kein Ersatz für die
TrueNAS-spezifische Implementierung und wurden nicht zur Qualifikation benutzt.

## Kleinster weiterer Schritt

Zuerst vollständige, aufgelöste NFSv4-ACLs für das gemeldete Artefakt **und den
Namensraum seiner Eltern** lesen. Für eine Sicherungs-/Normalisierungsvariante
zusätzlich den vorgesehenen bestehenden privaten Verwaltungs-/Rückfallbereich
qualifizieren. Benannte Benutzer/Gruppen, Rechte, ACE-Reihenfolge, Vererbung
und tatsächliche Host-/Container-Identitätszuordnung sind nötig. Aktuell
fehlen diese Tatsachen; tatsächliche Fremdschreibbarkeit wird weder behauptet
noch ausgeschlossen.

Falls ein bereits vorhandener Verwaltungsbereich nachweislich geeignet ist,
ist die kleinste zu bewertende Korrektur ein **jobgebundener, dauerhaft
verifizierter Protokollbeleg dort**, bei Erhalt des Originalprotokolls. Quelle
per No-follow-FDs binden, bounded lesen, Identität/Hash/Inhalt erneut prüfen;
Beleg exklusiv/fsync-dauerhaft veröffentlichen und über bestehendes
Journal/SQLite abgleichen. Mutable Quellen dürfen nicht durch den Kopiervorgang
als vertrauenswürdig etikettiert werden; Konflikte bleiben gesperrt. Der
konkrete Algorithmus ist erst mit bekanntem ACL-/Namensraumvertrag festlegbar.
Keine automatische Normalisierung oder produktive Kopie ist implementiert.

**Fehlender Sicherheitsnachweis:** Wer darf das Protokoll bzw. seine Einträge
ändern/ersetzen, und wo kann ein neuer Beleg tatsächlich gegen diese Schreiber
geschützt werden? Ohne diese Antwort ist eine Freigabe des realen NAS-Falls
nicht nachweislich sicher. Keine pauschale Modusausnahme und keine neue
allgemeine ACL-/Speicherarchitektur auf Verdacht.

## Minimale lesende NAS-Zusatzdiagnose

Auf dem **TrueNAS-Host**, nicht im Webcontainer, zunächst die vorhandenen
Mountzuordnungen lesen (Webcontainername einsetzen):

```sh
docker inspect '<Webcontainername>' --format '{{json .Mounts}}'
```

Dann aus der tatsächlichen Source-Zuordnung für `/workspace` den Hostpfad
übernehmen und ausschließlich die relevanten ACLs lesen. Keine Beispielpfade
als tatsächliche Datasetpfade übernehmen:

```sh
ROOT='<tatsächlicher Hostpfad des /workspace-Mounts>'
JOB='TRASH_IMPORT_20261023_205446_538D89094806'
for REL in '' 'SD Card Backups' 'SD Card Backups/.incoming' "SD Card Backups/.incoming/$JOB" "SD Card Backups/.incoming/$JOB/Protocol" "SD Card Backups/.incoming/$JOB/Protocol/status.json" 'Metadata Correction' 'Metadata Correction/.trash-import' "Metadata Correction/.trash-import/$JOB"; do
  midclt call filesystem.getacl "$ROOT${REL:+/$REL}" false true
done
```

`false` fordert die erweiterten Rechte an; `true` löst IDs auf. Bei fehlender
Leseberechtigung/API-Abweichung stoppen und die Fehlermeldung liefern; keine
Rechte reparieren. Der Aufruf ist anhand der dokumentierten API25.04 angegeben,
installierte TrueNAS-Version mitliefern. Zusätzlich nötig: bekannte Zuordnung
benannter ACL-Identitäten zu den zulässigen Schreibern; Container-Gruppennamen
allein reichen nicht. Keine NAS-Diagnose wurde durch den Agenten ausgeführt.

## Umfang dieses Commits

Nur Test-/QA-Dateien. Alle174 App-Dateien und der übrige Produktstand bleiben
byteidentisch zur Basis; keine UI-/Sprach-/SD-/Archivänderung. F11/F14/F24,
No-follow, unabhängige Kopien und bestehende Abschluss-/Recoveryregeln bleiben
unverändert. Der reale Fall bleibt ausdrücklich BLOCKED. Kein Gesamtlauf,
GitHub-Actions-Lauf, Release, Containerbuild oder NAS-Eingriff.
