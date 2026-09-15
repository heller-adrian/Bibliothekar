# QA

Dieser Bereich dient automatisierten Integrations- und Regressionstests.

## Grundregel

QA darf Fehler finden und dokumentieren, aber keinen Produktivcode selbständig reparieren.

Der QA-Agent:

1. liest Testmatrix und aktuellen Versionsstand
2. führt Tests einzeln nach Test-ID aus
3. dokumentiert Soll und Ist
4. setzt jeden Test auf PASS, FAIL, BLOCKED oder SKIPPED
5. führt unabhängige Tests nach einem Fehler weiter
6. beendet einen Testpfad nur, wenn Folgeprüfungen durch den Fehler fachlich unbrauchbar wären
7. verändert keine realen Kameraarchive oder Sicherungsbestände
8. schreibt am Ende einen vollständigen Bericht

## Vollständiger 0.21.2-Testumfang

Die jeweils aktuelle `TEST_MATRIX.md` ist die verbindliche Umfangsliste für den Hermes-QA-Lauf. Es dürfen nicht nur exemplarische oder zuletzt geänderte Fälle ausgewählt werden.

Am Ende muss für jede Test-ID aus der Matrix genau ein Ergebnis `PASS`, `FAIL`, `BLOCKED` oder `SKIPPED` vorliegen. Fehlende IDs sind ein unvollständiger QA-Lauf und werden von `qa/validate_results.py` abgelehnt.

Automatisierte Backend-QA läuft immer gegen das vollständige Verzeichnis `tests/backend`. Der GitHub-Workflow sammelt die komplette Suite vorab und führt sie ohne Fail-fast-Option aus. Ein FAIL darf fachlich unabhängige Tests nicht verhindern.

## Testlauf

Jeder Lauf erhält einen eigenen Ordner:

`/mnt/storage/ki-workspace/hermes/bibliothekar-qa/runs/YYYY-MM-DD_VERSION_RUN/`

Mindestens:

- `report.md`
- `results.json`
- `commands.log`
- `app.log`
- `environment.txt`

## Realdateien

Für realistische E2E-Tests darf `nas-agent` geeignete Kamera-Dateien aus vorhandenen Sicherungsbeständen ausschließlich lesend entnehmen und in seinen QA-Bereich kopieren. Originale bleiben unverändert.

Bevorzugte Quellen sind:

- `/mnt/storage/backup/kamera-sd-karten/DEEPTEST_SD_02`
- andere ausdrücklich freigegebene SD-Kartensicherungen unter `/mnt/storage/backup/kamera-sd-karten`

Testkopien liegen ausschließlich unter `/mnt/storage/ki-workspace/hermes/bibliothekar-qa/` oder in einem ausdrücklich freigegebenen Testbereich des Kamera-Arbeitsbereichs.

## Beschreibbare Test-Kamerabibliothek

Archivtests T080–T088 verwenden niemals die reale Kamerabibliothek `/mnt/storage/fotos/Kamerabibliothek`.

Für diese Tests existiert eine eigene beschreibbare Test-Kamerabibliothek:

`/mnt/storage/ki-workspace/hermes/bibliothekar-qa/archive-test-library`

Sie wird von QA als vollständiger Ersatz für `KAMERA_ARCHIVE_ROOT` behandelt. Innerhalb eines Archiv-E2E-Laufs darf `nas-agent` dort Ereignisse archivieren, Dateien verschieben, IST→SOLL-Pläne prüfen und den Bestand anschließend wieder entfernen.

Die reale Kamerabibliothek bleibt für Hermes read-only und darf weder als Testziel noch als temporärer Schreibbereich verwendet werden.

### Verbindliches Isolations-Gate vor T080–T088

Die Existenz oder Beschreibbarkeit von `archive-test-library` allein reicht **nicht** aus. T080–T088 dürfen nicht gegen die normale TrueNAS-App ausgeführt werden, weil deren `/camera-library:ro` weiterhin die reale Kamerabibliothek repräsentiert.

Vor T080–T088 muss `nas-agent` die isolierte QA-Instanz gemäß `qa/archive_e2e/README.md` starten. Der Harness erzwingt:

- eine eigene laufbezogene SQLite-DB unter dem Hermes-QA-Bereich
- `KAMERA_ARCHIVE_ROOT=/mnt/storage/ki-workspace/hermes/bibliothekar-qa/archive-test-library`
- Testkopien aus einer freigegebenen SD-Sicherung; die Originalquelle wird nicht in den Container gemountet
- keinerlei Mount der Produktiv-DB oder realen Kamerabibliothek
- das unveränderliche Produktimage von Commit `627c5515e533e167e45354ccaa71f988f104ae08`
- einen lokalen, nichtproduktiven QA-Prozess statt einer neuen produktiven TrueNAS-App

Nur ein `PASS` des Isolations-Harness erlaubt den Start von T080–T088. Bei `BLOCKED` oder `FAIL` werden diese Tests nicht improvisiert gegen Produktionspfade ausgeführt; unabhängige Tests laufen weiter.

Vor jedem Archiv-Testlauf muss der Agent dokumentieren:

- verwendeter QA-Archivpfad
- verwendete Test-DB
- Quellbestand der Testkopien
- SHA-256 bzw. Dateigröße der verwendeten Testdateien
- dass kein Schreibzugriff auf `/mnt/storage/fotos/Kamerabibliothek` stattgefunden hat

Nach dem Lauf muss er den Zustand der QA-Testbibliothek und der Test-DB dokumentieren. Aufräumen ist nur innerhalb des QA-Bereichs erlaubt.

## Fehlerbericht

Jeder Fehler enthält:

- Test-ID
- Version / Commit
- Ausgangszustand
- ausgeführte Schritte
- erwartetes Ergebnis
- tatsächliches Ergebnis
- relevante API-Antworten
- DB-Zustand
- Dateisystemzustand
- Logs
- Reproduzierbarkeit
- dadurch blockierte Tests

## Rollen

Hermes / nas-agent:
führt technische Tests durch.

Workspacecontroller:
plant Reihenfolge, bewertet Abhängigkeiten, lässt unabhängige Tests weiterlaufen und erstellt den Gesamtbericht.

Nutzer:
nimmt UI, Bedienbarkeit und reale End-to-End-Abläufe manuell ab.

ChatGPT:
entwickelt Patches auf Basis des QA-Berichts und der manuellen Abnahme.
