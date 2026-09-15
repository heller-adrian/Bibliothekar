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
