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

Ein bestandener Start-Harness ist **noch kein PASS für T080–T088**. Danach führt `nas-agent` die Testfälle aus `TEST_MATRIX.md` tatsächlich über die isolierte Bibliothekar-Instanz aus und prüft jeweils API/UI-Zustand, QA-SQLite-DB und reales Dateisystem unter `archive-test-library`.

Dabei gilt:

- T080: verwendete Realdateien sind nachweislich Kopien aus der freigegebenen Sicherung; Originalquelle bleibt unberührt.
- T081: vollständiger Archivlauf schreibt tatsächlich in `archive-test-library`, nicht nur in DB/UI.
- T082: ein dort archiviertes Ereignis wird aus demselben QA-Archiv erneut geöffnet/geprüft.
- T083: archived einfaches Ereignis wird nachträglich zu Oberereignis + Unterereignis umgebaut; IST→SOLL wird real angewendet.
- T084: herausfallendes archived Segment wird einem bestehenden normalen archived Ereignis zugeordnet.
- T085: herausfallendes archived Segment wird einem bestehenden archived Unterereignis zugeordnet.
- T086: herausfallendes archived Segment wird als neues Unterereignis eines bestehenden archived Oberereignisses angelegt.
- T087: archived `Ohne Ereignis` bleibt segmentbasiert; Erweiterung/Änderung erzeugt keine falsche kontinuierliche Zeitspanne.
- T088: nach dem Lauf ist weiterhin nachgewiesen, dass die Produktivbibliothek nie in der QA-Instanz gemountet war und kein QA-Kommando einen Produktionspfad als Schreibziel verwendet hat. Ein optionaler read-only Metadatenvergleich der Produktivbibliothek darf ergänzend verwendet werden; Inhalts-Hashes der realen 600-GB-Bibliothek sind dafür nicht erforderlich.

Nach einem FAIL werden fachlich unabhängige Tests weiter ausgeführt. Nur echte Folgeabhängigkeiten dürfen BLOCKED werden; sie müssen einzeln begründet werden.

## Ende des isolierten Prozesses

Nach vollständiger Beweissicherung:

```bash
bash qa/archive_e2e/stop_isolated_archive_qa.sh
```

Der Stop-Harness löscht absichtlich weder QA-DB noch QA-Archivdaten. Erst nach Auswertung darf `nas-agent` innerhalb des QA-Bereichs aufräumen. Produktionspfade bleiben tabu.

## Vollständigkeits-Gate

Am Ende des gesamten 0.21.2-QA-Laufs muss für **jede** Test-ID aus `TEST_MATRIX.md` genau ein Status `PASS`, `FAIL`, `BLOCKED` oder `SKIPPED` in `results.json` vorliegen.

Beispielprüfung:

```bash
python qa/validate_results.py \
  /mnt/storage/ki-workspace/hermes/bibliothekar-qa/runs/<RUN>/results.json \
  --archive-isolation /mnt/storage/ki-workspace/hermes/bibliothekar-qa/runs/<ARCHIVE_RUN>/isolation.json
```

Der Validator schlägt fehl, sobald eine Test-ID fehlt, eine unbekannte ID vorkommt oder T080–T088 als tatsächlich ausgeführt gemeldet werden, ohne dass ein bestandenes Isolations-Gate für Produktrevision `627c5515…` vorliegt.
