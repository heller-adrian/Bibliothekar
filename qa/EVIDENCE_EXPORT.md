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

## 2. Evidence Delta

`qa/evidence_delta.py` vergleicht zwei Snapshots deterministisch.

Es erzeugt:

- Tabellen-Zählerdeltas
- Job-State-/Kind-Deltas
- Integritätszustand vorher/nachher
- Gleichheit der Schema-Versionen
- hinzugefügte, entfernte und inhaltlich geänderte Fixture-Dateien

Damit muss der Executor keine eigenen SQL-Hilfsskripte schreiben und keine Zähler manuell auswerten.

## 3. Diagnostische Checks

Für funktionale Tests reicht ein DB-/Fixture-Delta allein oft nicht aus. Deshalb darf die sanitizierte Export-Evidence zusätzlich eine Liste `checks` enthalten.

Jeder Check beschreibt genau eine überprüfte Vertragspflicht und enthält nur:

```json
{
  "id": "EDIT-APPLY",
  "method": "UI",
  "action": "Ereignis bearbeiten und Anwenden auslösen",
  "expected": "Änderung wird gespeichert und bleibt nach Reload sichtbar",
  "actual": "HTTP 500; Änderung bleibt unverändert",
  "result": "FAIL",
  "status_code": 500,
  "error": "kurzer sanitizierter Fehlertext"
}
```

Pflichtfelder:

- `id`: kurze stabile Check-ID
- `method`: tatsächlicher Prüfweg, z. B. `UI`, `API`, `filesystem`, `database`
- `action`: konkret ausgeführte Aktion
- `expected`: vertraglich erwartetes Ergebnis
- `actual`: tatsächlich beobachtetes Ergebnis
- `result`: exakt `PASS`, `FAIL` oder `BLOCKED`

Optional:

- `status_code`: HTTP-Status 100–599
- `error`: kurzer sanitizierter Fehlertext

Der Export-Builder begrenzt die Liste auf 100 Checks und die Textfelder auf kompakte Längen. Unbekannte Felder werden nicht exportiert. Absolute NAS-/Home-Pfade und Secret-Muster bleiben verboten.

Wichtig: `checks` ersetzen nicht die deterministischen Snapshots/Deltas. Sie ergänzen sie um die konkrete Nutzer-/API-Beobachtung. Der Executor darf Checks nur aus tatsächlich ausgeführten Aktionen und beobachteten Ergebnissen erzeugen; keine Schätzung, keine Rekonstruktion aus Erinnerung.

Für Workflow-/UI-/API-Tests soll jede zwingende Vertragspflicht durch mindestens einen passenden Check belegt sein. Rein zustandsbasierte Infrastrukturtests dürfen ohne `checks` auskommen, wenn DB-/Fixture-Evidence den gesamten Vertrag vollständig abdeckt.

## 4. Thinker-Gate

Nach EXECUTE erhält `qa-thinker` nur:

- Testvertrag
- deterministische Evidence
- die sanitizierten diagnostischen `checks`
- gezielt notwendige API-/Jobbelege

Der Thinker entscheidet ausschließlich:

- `ACCEPT_PASS`
- `ACCEPT_FAIL`
- `ACCEPT_BLOCKED`
- `RETEST_REQUIRED`

Dabei prüft er ausdrücklich, ob `method` und `action` dem Testvertrag entsprechen. Ein technisch erfolgreicher Ersatzweg ist kein Beleg für den geforderten Nutzerweg.

Typische Einordnung:

- Produkt verhält sich auf dem vorgeschriebenen Weg falsch -> `ACCEPT_FAIL`
- notwendige technische Voraussetzung fehlt -> `ACCEPT_BLOCKED`
- falscher Prüfweg, ausgelassene Pflichtaktion oder unzureichende Evidence -> `RETEST_REQUIRED`
- alle Pflichtbedingungen auf dem vorgeschriebenen Weg belegt -> `ACCEPT_PASS`

## 5. Verified Export Builder

`qa/build_verified_export.py` akzeptiert nur einen abgeschlossenen, passenden `qa-thinker`-Review. Test-ID und Executor-Task/Run müssen exakt mit der Evidence übereinstimmen.

Der Builder übernimmt nur eine Whitelist strukturierter Daten:

- DB-/Job-/Integritätsdelta
- Fixture-Delta
- validierte diagnostische `checks`
- Thinker-Urteil und Begründung

Absolute NAS-/Home-Pfade und typische Secret-Muster führen zu `BLOCKED`.

Das verifizierte Schema bleibt rückwärtskompatibel `bibliothekar.qa.verified-result.v1`; `evidence.checks` ist eine optionale Erweiterung. Alte Infrastruktur-Smokes ohne Checks bleiben gültig.

## 6. GitHub Exporter – Sicherheitsgrenze

Der GitHub-Schreibzugriff gehört **nicht** zu `nas-agent` und nicht zu `qa-thinker`.

Aktuelle Zielarchitektur:

1. Der lokale QA-Exporter auf GX10 liest ausschließlich abgeschlossene `qa-thinker`-Review-Metadaten mit `export_contract_version=1`.
2. Er baut daraus einen sanitisierten Verified-Result-Datensatz.
3. Ein eigener GitHub Deploy Key besitzt Schreibrecht ausschließlich auf das separate private QA-Ledger-Repository.
4. Das Ledger enthält keinen Produktcode und keine NAS-Dateien.
5. ChatGPT liest das private Ledger über den GitHub-Connector.

Damit bleibt die Sicherheitsrichtung strikt:

`Hermes/NAS -> sanitizierte Evidence -> lokaler Exporter -> privates GitHub QA-Ledger -> ChatGPT liest GitHub`

Es entsteht kein Rückkanal von GitHub/ChatGPT zum NAS.

## 7. Zweck für die weitere Fehleranalyse

Ein Ledger-Eintrag soll künftig nicht nur zeigen, **dass** ein Test fehlgeschlagen ist, sondern maschinenlesbar auch:

- auf welchem Weg geprüft wurde,
- welche konkrete Aktion ausgeführt wurde,
- was erwartet war,
- was tatsächlich geschah,
- ob die einzelne Pflichtbedingung PASS/FAIL/BLOCKED war,
- und optional HTTP-Status bzw. kurzen sanitizierten Fehlertext.

Damit kann ein externer Reviewer einen echten Produktfehler von einem methodisch ungültigen Test unterscheiden, ohne Rohlogs oder private NAS-Daten zu benötigen.
