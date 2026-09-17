# Deterministische Evidence- und Export-Pipeline

## Ziel

Die QA soll Rohdaten nicht mehr minutenlang durch ein Sprachmodell interpretieren lassen. Stattdessen entstehen maschinenlesbare Snapshots, Deltas und erst nach einem abgeschlossenen `qa-thinker`-Review ein sanitizierter Exportdatensatz.

Verbindlicher Ablauf:

`CLEAN -> SETUP -> EXECUTE -> SNAPSHOT/DELTA -> REVIEW -> VERIFIED EXPORT`

Ein Executor-Ergebnis ist nie autoritativ. Ein Eintrag für den GitHub-QA-Ledger darf erst nach einem abgeschlossenen `qa-thinker`-Review erzeugt werden.

## 1. Evidence Snapshot

`qa/evidence_snapshot.py` arbeitet read-only gegen eine SQLite-QA-Datenbank und optional gegen eine Fixture innerhalb des QA-Wurzelpfads.

Erfasst werden nur strukturierte Prüfdaten:

- SHA256 der QA-Datenbank
- `PRAGMA integrity_check`
- Schema-Versionen
- Anzahl aller fachlichen Tabellen
- Job-Zähler nach State und Kind
- optional Dateiliste der ausdrücklich angegebenen QA-Fixture mit relativem Pfad, Größe und SHA256

Produktionspfade werden abgewiesen. Die Datenbank wird im SQLite-Read-only-Modus geöffnet.

Beispiel:

```bash
python3 qa/evidence_snapshot.py \
  --database "$RUN_ROOT/database/kamera.sqlite3" \
  --fixture-root "$RUN_ROOT/removable-sources/QA_SD_T004" \
  --test-id T004 \
  --phase A \
  --executor-task-id t_... \
  --executor-run-id 32 \
  --output "$RUN_ROOT/evidence/T004/baseline.json"
```

## 2. Evidence Delta

`qa/evidence_delta.py` vergleicht zwei Snapshots deterministisch.

Es erzeugt:

- Tabellen-Zählerdeltas
- Job-State-/Kind-Deltas
- Integritätszustand vorher/nachher
- Gleichheit der Schema-Versionen
- hinzugefügte, entfernte und inhaltlich geänderte Fixture-Dateien

```bash
python3 qa/evidence_delta.py \
  --before "$RUN_ROOT/evidence/T004/baseline.json" \
  --after "$RUN_ROOT/evidence/T004/post.json" \
  --output "$RUN_ROOT/evidence/T004/delta.json"
```

Damit muss der Executor keine eigenen SQL-Hilfsskripte schreiben und keine Zähler manuell auswerten.

## 3. Thinker-Gate

Nach EXECUTE erhält `qa-thinker` nur:

- Testvertrag
- deterministisches Evidence-JSON
- gezielt notwendige API-/Jobbelege

Der Thinker entscheidet ausschließlich:

- `ACCEPT_PASS`
- `ACCEPT_FAIL`
- `ACCEPT_BLOCKED`
- `RETEST_REQUIRED`

Der abgeschlossene Review wird anschließend in ein kleines lokales, sanitiziertes Review-JSON überführt. Dieses JSON muss mindestens enthalten:

```json
{
  "task_id": "t_review",
  "run_id": "33",
  "profile": "qa-thinker",
  "mode": "REVIEW",
  "completed": true,
  "verdict": "RETEST_REQUIRED",
  "reason": "...",
  "test_id": "T004",
  "executor_task_id": "t_exec",
  "executor_run_id": "32"
}
```

## 4. Verified Export Builder

`qa/build_verified_export.py` akzeptiert nur einen abgeschlossenen, passenden `qa-thinker`-Review. Test-ID und Executor-Task/Run müssen exakt mit der Evidence übereinstimmen.

Der Builder übernimmt nur eine Whitelist strukturierter Daten. Absolute NAS-/Home-Pfade und typische Secret-Muster führen zu `BLOCKED`.

```bash
python3 qa/build_verified_export.py \
  --evidence "$RUN_ROOT/evidence/T004/delta.json" \
  --review "$RUN_ROOT/evidence/T004/review.json" \
  --product-commit 627c5515e533e167e45354ccaa71f988f104ae08 \
  --qa-commit <QA_COMMIT> \
  --output "$EXPORT_STAGING/verified/0.21.2/phase-a/T004.json"
```

## 5. GitHub Exporter – Sicherheitsgrenze

Der GitHub-Schreibzugriff gehört **nicht** zu `nas-agent` und nicht zu `qa-thinker`.

Empfohlene Zielarchitektur:

1. Eigener lokaler Benutzer/Prozess `qa-exporter` auf GX10.
2. Dieser Benutzer hat **keinen** SSH-/Docker-/NAS-Zugriff und keinen Zugriff auf Hermes-Profile.
3. Er darf ausschließlich ein sanitiziertes `EXPORT_STAGING` lesen.
4. Er besitzt einen eigenen GitHub Deploy Key mit Schreibrecht ausschließlich auf ein separates privates QA-Ledger-Repository.
5. Das Ledger-Repository enthält keinen Produktcode und keine NAS-Dateien.
6. Der Exporter kopiert nur bereits durch `build_verified_export.py` erzeugte JSON-Dateien in `verified/...` und pusht diese.

Damit bleibt die Sicherheitsrichtung strikt:

`Hermes/NAS -> sanitizierte Evidence -> separater Exporter -> privates GitHub QA-Ledger -> ChatGPT liest GitHub`

Es entsteht kein Rückkanal von GitHub/ChatGPT zum NAS.

## 6. Zustand bis zur Einrichtung des separaten Ledger-Repositories

Die Evidence-Werkzeuge können sofort lokal verwendet werden. Der eigentliche GitHub-Push bleibt deaktiviert, bis das separate private Ledger-Repository und sein eigener eingeschränkter Schreibschlüssel eingerichtet sind.
