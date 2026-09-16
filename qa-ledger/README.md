# Bibliothekar QA Ledger

Dieser Bereich ist das dauerhafte, cloudseitige Projektgedächtnis zwischen der lokalen Hermes-QA und ChatGPT.

## Sicherheitsgrenze

Der Ledger ist **kein Zugriff auf Hermes, TrueNAS, Docker, SQLite oder lokale Dateien**. Er enthält nur bewusst exportierte, reduzierte QA-Informationen. Keine Fotos, keine privaten NAS-Dateien, keine Schlüssel/Tokens, keine Shell-Historie und keine beliebigen Verzeichnisinhalte werden übernommen.

## Vertrauensmodell

Ein QA-Ergebnis ist im Ledger nur dann **autoritativer Befund**, wenn es durch `qa-thinker` geprüft wurde.

Verbindlicher Ablauf:

`PLAN (qa-thinker) -> EXECUTE (nas-agent) -> REVIEW (qa-thinker) -> Ledger`

Ein `PASS` des Executors allein ist niemals ausreichend. Der Export darf einen Test erst unter `verified/` ablegen, wenn ein abgeschlossener Thinker-Review vorliegt.

Zulässige Review-Urteile:

- `ACCEPT_PASS`
- `ACCEPT_FAIL`
- `ACCEPT_BLOCKED`
- `RETEST_REQUIRED`

Jeder autoritative Datensatz muss mindestens enthalten:

- Test-ID
- Task-ID und Run-ID des Executors
- Task-ID und Run-ID des Thinker-Reviews
- Review-Urteil
- strukturierte Evidence
- kurze Begründung
- Produkt-Commit / QA-Stand
- Zeitstempel

## Verzeichnisse

- `CURRENT_STATE.md` – komprimierter, aktueller Projektzustand
- `OPEN_ISSUES.md` – bestätigte offene Punkte und noch ausstehende QA
- `HISTORY.md` – wichtige historische Meilensteine und Regressionsthemen
- `EXPORT_CONTRACT.md` – Regeln für den späteren lokalen Sanitizer/Exporter
- `bootstrap/` – aus früheren Chats übernommener Kontext; **nicht automatisch autoritativ**
- `verified/` – ausschließlich Thinker-geprüfte QA-Ergebnisse

## Nutzung in neuen Chats

Ein neuer Chat soll zuerst diesen Branch `qa-ledger` lesen, insbesondere `CURRENT_STATE.md`, `OPEN_ISSUES.md` und die relevanten Dateien unter `verified/`. Der Ledger ersetzt nicht den Quellcode oder `TEST_MATRIX.md`, sondern ergänzt sie um den tatsächlichen Testverlauf und offene Befunde.
