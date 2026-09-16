# Clean-Slate-QA

## Grundsatz

Unabhaengige QA-Tests starten standardmaessig aus einem definierten Nullzustand.

Der Normalfall ist:

1. `CLEAN`
2. `SETUP`
3. `EXECUTE`
4. `REVIEW`

Zufallszustand aus einem frueheren Testlauf ist kein gueltiger Testaufbau.

Persistenz ueber mehrere Schritte wird nur dann beibehalten, wenn der Testvertrag sie ausdruecklich verlangt, z. B. bei einem Restart-Test oder einer bewusst zusammenhaengenden Archiv-E2E-Sequenz.

## Warum

Ein Clean Slate verhindert insbesondere:

- Kollisionen mit Import-Signaturen aus frueheren Tests
- zufaellig bereits vorhandene Jobs, Dateien, Familien oder Ereignisse
- falsch positive Deduplizierungs- oder Change-Ergebnisse
- Abhaengigkeiten zwischen fachlich unabhaengigen Test-IDs
- schwer reproduzierbare Fehler durch Altzustand

Dadurch kann ein Test bei Bedarf den kompletten Produktweg erneut durchlaufen: Sicherungsquelle einlesen, Backup/Pruefung, Metadaten, Ereignisse anlegen, bearbeiten, sortieren, archivieren und erneut bearbeiten.

## Reset-Harness

`qa/reset_test_state.py` setzt ausschliesslich den isolierten Hermes-QA-Zustand zurueck.

Beispiel:

```bash
python3 qa/reset_test_state.py \
  --run-root /mnt/storage/ki-workspace/hermes/bibliothekar-qa/runs/<RUN_ID>
```

Das Skript:

- verweigert Pfade ausserhalb des Hermes-QA-Bereichs
- verweigert Ueberschneidungen mit Produktiv-DB und realer Kamerabibliothek
- verweigert einen Reset, solange ein nicht-terminaler QA-Job existiert
- behaelt SQLite-Schema und `schema_versions`
- loescht alle fachlichen Testdaten aus der QA-DB
- leert QA-Workspace, Logs, Removable-/NAS-Testquellen und Pool-Probe
- leert standardmaessig die beschreibbare `archive-test-library`
- behaelt standardmaessig die kanonische Testkopie `import-sources/DEEPTEST_SD_02`
- laesst Evidence und Reports ausserhalb der mutablen Verzeichnisse unangetastet
- schreibt einen maschinenlesbaren Reset-Beleg unter `evidence/resets/`

Vor dem ersten produktiven Einsatz sollte einmal ein Dry-Run erfolgen:

```bash
python3 qa/reset_test_state.py \
  --run-root /mnt/storage/ki-workspace/hermes/bibliothekar-qa/runs/<RUN_ID> \
  --dry-run
```

## Persistenz-Szenarien

Ein Reset findet **nicht** zwischen Schritten statt, deren Sinn gerade in der Persistenz liegt.

Beispiele:

### T008 Neustart

```text
CLEAN
→ Setup / Importjobs erzeugen
→ PRE-Evidence
→ echter App-/Container-Neustart
→ gleiche QA-DB
→ POST-Evidence
→ REVIEW
```

Kein Reset zwischen PRE und POST.

### Archiv-E2E

Wenn T082–T087 als zusammenhaengende Zustandsfolge getestet werden, wird innerhalb dieser explizit gekennzeichneten Sequenz kein Reset ausgefuehrt. Vor Beginn der Sequenz wird dagegen ein Clean Slate hergestellt.

`--keep-archive` ist nur fuer einen solchen ausdruecklich geplanten Persistenzfall zulaessig.

## Evidence und Review-Gate

Ein Reset-Beleg ist Evidence, aber kein fachliches Testurteil.

Der verbindliche QA-Ablauf bleibt:

```text
qa-thinker PLAN
→ nas-agent EXECUTE
→ qa-thinker REVIEW
```

Ein Executor-PASS allein ist nicht autoritativ. Fuer den spaeteren QA-Ledger werden nur Ergebnisse nach abgeschlossenem `qa-thinker`-Review als verifiziert behandelt.

## Rechte des nas-agent

Der `nas-agent` darf innerhalb des isolierten QA-Bereichs den Testzustand radikal zuruecksetzen und Testfixtures neu erzeugen. Er darf weiterhin nicht:

- Produktiv-DB oder reale Kamerabibliothek veraendern
- Produktivcode reparieren
- Commits/Deployments ausfuehren
- Dockerrechte improvisieren
- einen Persistenztest durch einen Reset methodisch entwerten

Der Reset soll nicht durch ad-hoc SQL ersetzt werden. Fuer Clean-Slate-Zwecke ist ausschliesslich der deterministische Harness zu verwenden.
