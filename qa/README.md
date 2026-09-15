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

`qa/test-runs/YYYY-MM-DD_VERSION_RUN/`

Mindestens:

- `report.md`
- `results.json`
- `commands.log`
- `app.log`
- `environment.txt`

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
