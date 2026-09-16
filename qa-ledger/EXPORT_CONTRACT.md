# Export Contract

## Ziel

Der lokale Exporter veröffentlicht nur die für Bibliothekar-QA nötigen, bereits geprüften Informationen nach GitHub. Er ist eine Einbahnstraße vom lokalen QA-System in diesen Ledger und darf keinerlei Fernzugriff auf Hermes oder das NAS ermöglichen.

## Thinker-Gate

Ein Testresultat darf **nur** exportiert werden, wenn alle folgenden Bedingungen erfüllt sind:

1. Es gibt eine abgeschlossene `qa-thinker`-REVIEW-Task.
2. Der Review referenziert eindeutig die Test-ID und den zugehörigen Executor-Run.
3. Der Review enthält genau eines der zulässigen Urteile: `ACCEPT_PASS`, `ACCEPT_FAIL`, `ACCEPT_BLOCKED`, `RETEST_REQUIRED`.
4. Evidence und Begründung sind vorhanden.
5. Der Review ist abgeschlossen (`kanban_complete` / Run outcome completed).

Fehlt eine Bedingung, darf kein autoritativer Eintrag unter `verified/` entstehen.

## Was exportiert werden darf

- Test-ID / Phase
- Task-ID und Run-ID
- Profil (`qa-thinker`, `nas-agent`)
- Modus (`PLAN`, `EXECUTE`, `REVIEW`)
- Produkt-Commit und QA-Harness-Commit
- strukturierte, testbezogene Evidence
- Review-Urteil und Begründung
- Parent/Child-Bezüge zwischen PLAN/EXECUTE/REVIEW
- Zeitstempel
- neutraler Workflow-Status wie `awaiting_review`, sofern ausdrücklich als nicht autoritativ gekennzeichnet

## Was nie exportiert werden darf

- Fotos oder andere Nutzerdateien
- Dateiinhalte aus NAS-Verzeichnissen
- private Verzeichnislisten ohne direkten Testbezug
- SQLite-Dumps oder freie SQL-Ausgaben
- SSH-Schlüssel, Tokens, Passwörter, Cookies
- Shell-Historien
- beliebige Hermes-Logs
- Docker-/TrueNAS-Konfiguration außerhalb ausdrücklich notwendiger, sanitizierter QA-Metadaten
- Zugriffsmöglichkeiten oder Befehle, die einen Rückkanal ins NAS schaffen

## Executor-Evidence

Executor-Evidence darf nicht allein als Resultat veröffentlicht werden. Sie darf nur Bestandteil eines Thinker-geprüften Datensatzes sein. Ein Executor-`PASS` wird bis zum Review als unbestätigt behandelt.

## Bootstrap-Daten

Historische Informationen aus früheren Chats werden unter `bootstrap/` abgelegt. Sie dienen der Kontextrekonstruktion, sind aber nicht automatisch gleichwertig mit Thinker-geprüften Ergebnissen. Relevante alte Befunde können später durch einen Thinker-Migrationsreview in `verified/` übernommen werden.
