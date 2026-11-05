# T080–T088: isolierte archived-E2E-QA

Diese Tests dürfen **nicht** gegen die normale TrueNAS-Custom-App laufen. Deren `/camera-library:ro` zeigt auf die reale Kamerabibliothek und ist deshalb weder ein gültiges Archiv-QA-Ziel noch ein Grund, T080–T088 als ausführbar anzusehen.

## Verbindlicher Produktstand

Für T080–T088 wird das unveränderliche Image verwendet:

`ghcr.io/heller-adrian/bibliothekar@sha256:27554d9f6cc2b8a67f77cf01e856b837423974dca0cb6d6e03e8bc5cdb5dddb6`

Dieses Image muss das OCI-Label

`org.opencontainers.image.revision=627c5515e533e167e45354ccaa71f988f104ae08`

tragen. Der Start-Harness prüft das und blockiert andernfalls.

## Verbindliche Isolation

Der Archiv-E2E-Lauf verwendet ausschließlich:

- QA-Wurzel: `/mnt/storage/ki-workspace/hermes/bibliothekar-qa`
- QA-Archiv: `/mnt/storage/ki-workspace/hermes/bibliothekar-qa/archive-test-library`
- laufbezogene DB: `<QA-Wurzel>/runs/<RUN>/database/kamera.sqlite3`
- laufbezogenen Workspace, Logs, Konfiguration und Importquellen unter `<QA-Wurzel>/runs/<RUN>/`
- Testkopien aus einer freigegebenen SD-Sicherung

Nicht gemountet und nicht als Ziel erlaubt sind insbesondere:

- `/mnt/storage/fotos/Kamerabibliothek`
- `/mnt/apps/appdata/kamera-automatisierung/database`

Die isolierte Instanz wird nur an `127.0.0.1:31044` veröffentlicht. Sie ist keine neue produktive TrueNAS-App.

## Start durch nas-agent

Vom Checkout des zu prüfenden Branches aus:

```bash
bash qa/archive_e2e/start_isolated_archive_qa.sh \
  /mnt/storage/backup/kamera-sd-karten/DEEPTEST_SD_02
```

Eine andere Quelle ist nur erlaubt, wenn sie ausdrücklich freigegeben wurde und unter einer freigegebenen SD-Sicherungswurzel liegt. Die Quelle selbst wird niemals in den Container gemountet. Der Harness kopiert sie zuerst in den laufbezogenen QA-Bereich und erzeugt dort `source-files.sha256`.

Nur wenn der Harness mit

`PASS: isolierte Archiv-QA ist bereit`

endet, dürfen T080–T088 gegen diese Instanz beginnen. Bei `BLOCKED` oder `FAIL` werden T080–T088 nicht gestartet; sie werden entsprechend dokumentiert und unabhängige Tests außerhalb dieses Pfads laufen weiter.

Der Harness erzeugt insbesondere:

- `isolation.json`
- `container-inspect.json`
- `mounts.txt`
- `environment.txt`
- `source-files.sha256`
- `app.log`
- die eigene `database/kamera.sqlite3`

`isolation.json` ist der maschinenprüfbare Nachweis dafür, dass Produktiv-DB und reale Kamerabibliothek nicht gemountet wurden.

## T080–T088 wirklich als E2E ausführen

Ein bestandener Start-Harness ist **noch kein PASS für T080–T088**. Danach führt `nas-agent` die Testfälle aus `TEST_MATRIX.md` tatsächlich über die isolierte Bibliothekar-Instanz aus.

Die verbindliche Reihenfolge und Bedeutung der Archivtests ist:

- T080: applied Ereignis mit echten QA-Testkopien in `archive-test-library` archivieren und den realen Zielbestand vollständig prüfen.
- T081: Archivprüfung gegen den realen QA-Dateibestand; API/DB und Dateisystem müssen denselben Zustand beschreiben.
- T082: archived Ereignis umbenennen, konkreten IST→SOLL-Plan erzeugen, Änderung umsetzen und realen SOLL-Bestand prüfen.
- T083: archived Zeitraum verändern, freigewordene Segmente exakt erkennen und verbleibenden/herausfallenden Bestand im Dateisystem belegen.
- T084: archived einfaches Ereignis nachträglich in Oberereignis + Unterereignisse umbauen und die reale Unterereignisordnerstruktur prüfen.
- T085: herausfallende Segmente einem bestehenden oder neuen Unterereignis zuordnen und die vollständigen Dateifamilien am korrekten Ziel prüfen.
- T086: manuellen Änderungsauftrag mit konkreten alten/neuen Pfaden erzeugen; jeder relevante Pfad muss im Dateisystemnachweis nachvollziehbar sein.
- T087: manuelle IST→SOLL-Verschiebung im QA-Archiv ausführen und danach vollständig prüfen: keine Restdateien, keine veralteten Restordner, keine Duplikate.
- T088: nachweisen, dass die Produktivbibliothek niemals gemountet oder beschrieben wurde; zusätzlich den Endzustand des QA-Archivs dokumentieren.

Nach einem FAIL werden fachlich unabhängige Tests weiter ausgeführt. Nur echte Folgeabhängigkeiten dürfen BLOCKED werden; sie müssen einzeln begründet werden.

## Verbindlicher Dateisystem-Abgleich nach jedem relevanten Archivschritt

API-Antworten, UI-Zustand und SQLite-Einträge sind **notwendig, aber nicht hinreichend**. Nach jedem Schritt, der Dateien oder Archivstruktur erzeugt, verschiebt, umbenennt, neu zuordnet oder strukturell verändert, ist zusätzlich ein realer Dateisystem-Abgleich erforderlich.

Für jeden solchen Schritt legt `nas-agent` unter dem Laufordner beispielsweise an:

```text
filesystem/
  T082-step01-plan.json
  T082-step01-expected.json
  T082-step01-evidence.json
  T084-step02-plan.json
  T084-step02-expected.json
  T084-step02-evidence.json
```

Der Ablauf ist:

1. tatsächlichen IST-Zustand und den von der App erzeugten IST→SOLL-Plan sichern
2. daraus einen expliziten erwarteten Dateisystem-SOLL-Zustand erstellen
3. Archivschritt bzw. manuelle Verschiebung ausführen
4. den tatsächlichen Zustand von `archive-test-library` mit dem SOLL-Manifest vergleichen
5. Evidence-Datei im Laufordner sichern und in `results.json` referenzieren

Der Vergleich wird mit folgendem Helfer ausgeführt:

```bash
python3 qa/archive_e2e/verify_filesystem_state.py \
  /mnt/storage/ki-workspace/hermes/bibliothekar-qa/runs/<RUN>/filesystem/T082-step01-expected.json \
  --archive-root /mnt/storage/ki-workspace/hermes/bibliothekar-qa/archive-test-library \
  --evidence /mnt/storage/ki-workspace/hermes/bibliothekar-qa/runs/<RUN>/filesystem/T082-step01-evidence.json
```

Das SOLL-Manifest enthält mindestens:

```json
{
  "archive_root": "/mnt/storage/ki-workspace/hermes/bibliothekar-qa/archive-test-library",
  "directories": [
    "2026/07.15 - Beispiel",
    "2026/07.15 - Beispiel/08-00 - 12-00 - Vormittag",
    "2026/07.15 - Beispiel/08-00 - 12-00 - Vormittag/Alle"
  ],
  "files": [
    {
      "path": "2026/07.15 - Beispiel/08-00 - 12-00 - Vormittag/Alle/20260715_091500_Kamera.RAF",
      "family_id": "42",
      "size_bytes": 123456,
      "sha256": "..."
    }
  ]
}
```

`verify_filesystem_state.py` prüft den gesamten nicht-metadatenbezogenen QA-Archivbestand exakt gegen dieses Manifest. Geprüft werden:

- exakte relative Datei- und Ordnerpfade
- erwartete/tatsächliche Anzahl von Dateien und Ordnern
- Größe und SHA-256 jeder erwarteten Testdatei, sofern im Manifest angegeben
- dass alle Dateien einer Familie in genau demselben vorgesehenen Zielordner liegen
- fehlende Dateien
- unerwartete/verbliebene Dateien
- unerwartete/verbliebene Ordner
- gleiche Dateiinhalte an mehreren Pfaden als ungewollte Duplikate
- Symlinks

`event.json`, `.DS_Store` und AppleDouble-Dateien `._*` werden separat als bekannte Metadaten protokolliert und nicht als Kamera-Mediendateien gezählt. Andere unbekannte Dateien bleiben prüfpflichtig.

Ein Archivtest T080–T088 darf nur `PASS` erhalten, wenn **alle für ihn relevanten `filesystem_checks` PASS** sind. Ein optisch plausibler Ordner oder ein passender DB-Zustand ersetzt diesen Nachweis nicht.

Beispiel für `results.json`:

```json
{
  "id": "T082",
  "status": "PASS",
  "filesystem_checks": [
    {
      "step": "rename-apply",
      "status": "PASS",
      "plan": "filesystem/T082-step01-plan.json",
      "expected": "filesystem/T082-step01-expected.json",
      "evidence": "filesystem/T082-step01-evidence.json"
    }
  ]
}
```

## Ende des isolierten Prozesses

Nach vollständiger Beweissicherung:

```bash
bash qa/archive_e2e/stop_isolated_archive_qa.sh
```

Der Stop-Harness löscht absichtlich weder QA-DB noch QA-Archivdaten. Erst nach Auswertung darf `nas-agent` innerhalb des QA-Bereichs aufräumen. Produktionspfade bleiben tabu.

## Vollständigkeits-Gate

Am Ende des gesamten aktueller geprüfter Commit-QA-Laufs muss für **jede** Test-ID aus `TEST_MATRIX.md` genau ein Status `PASS`, `FAIL`, `BLOCKED` oder `SKIPPED` in `results.json` vorliegen.

Beispielprüfung:

```bash
python qa/validate_results.py \
  /mnt/storage/ki-workspace/hermes/bibliothekar-qa/runs/<RUN>/results.json \
  --archive-isolation /mnt/storage/ki-workspace/hermes/bibliothekar-qa/runs/<ARCHIVE_RUN>/isolation.json
```

Der Validator schlägt fehl, sobald eine Test-ID fehlt, eine unbekannte ID vorkommt, T080–T088 als tatsächlich ausgeführt gemeldet werden ohne bestandenes Isolations-Gate oder ein als PASS gemeldeter Archivtest keinen vollständigen bestandenen Dateisystemnachweis besitzt.


### Revision des Testcontainers (ab Audit-Branch 0.50.0)

Der Start benötigt `QA_IMAGE` (zuvor aus genau dem zu prüfenden Git-Commit gebaut) und `QA_EXPECTED_REVISION` (Commit-SHA). Ohne beide Variablen bricht der Test ab. Damit wird kein historisches 0.21.2-Image mehr stillschweigend geprüft. Für einen lokalen Test das Image mit `--build-arg SOURCE_REVISION=<SHA>` bauen und den Digest/Revision-Label kontrollieren.
