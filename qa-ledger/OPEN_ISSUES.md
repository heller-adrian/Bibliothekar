# Open Issues / Pending QA

Stand: 2026-09-16

## Phase A – noch offen

### T004 – dieselbe SD mit neuen Medien
Status: `RETEST_REQUIRED` durch Thinker-Review bestätigt.

Früherer Versuch war methodisch ungültig, weil ein neuer Quellpfad verwendet wurde und die Quelle dadurch komplett neu behandelt wurde.

Korrektur:
- virtuelle removable-Quelle `QA_SD_T004`
- Baseline importieren
- unter exakt derselben `source_device_id` und demselben Pfad 3 neue Medien ergänzen
- erneut importieren
- nur relative Deltas bewerten

### T007 – gleicher Dateiname, anderer Inhalt
Status: `RETEST_REQUIRED` durch Thinker-Review bestätigt.

Früherer Versuch war methodisch ungültig, weil die geänderten Dateien unter einer neuen Quelle liefen; `_002`-Kollisionsschutz bewies keine Change-Erkennung.

Korrektur:
- eigene removable-Quelle `QA_SD_T007`
- bekannte Datei F mit H1 dokumentieren
- Inhalt unter identischem Namen/Pfad ändern, H2 != H1
- zweite Erkennung unter derselben `source_device_id`
- echter `changed`-Nachweis erforderlich

### T008 – Persistenz nach echtem Neustart
Status: `RETEST_REQUIRED` durch Thinker-Review bestätigt.

Früherer Versuch führte ausdrücklich keinen echten App-Neustart aus.

Korrektur:
- nas-agent T008-PRE sammelt Pre-Evidence
- Benutzer/Admin führt echten Neustart ausschließlich der isolierten QA-App aus
- frischer nas-agent T008-POST prüft identische QA-DB und vorhandene Jobs/Artefakte
- qa-thinker REVIEW

### T001 / T006
Historischer Phase-A-Executorstatus: `BLOCKED`, weil der Host-Source-Helper nicht erreichbar war. Diese Einstufung stammt noch aus der Vor-Thinker-Gate-Phase und ist daher im Ledger zunächst nur Bootstrap-Kontext. Vor autoritativer Übernahme erneut durch Thinker prüfen.

## Nach Phase A

Phase B–F wurden im aktuellen frischen QA-Lauf noch nicht gestartet.

Geplante Gruppen gemäß TEST_MATRIX:
- Phase B: T020–T029 normale Ereignisse
- Phase C: T040–T046 Ohne Ereignis
- Phase D: T060–T066 Reassignment
- Phase E: T080–T088 Archiv-E2E
- Phase F: T100–T105 plus U001–U006

## Historische Regressionsthemen, die im Deep-Test besonders beobachtet werden müssen

Diese Punkte stammen aus früheren Appversionen und sind nicht automatisch als aktuelle 0.21.2-Fehler zu verstehen:

- Bearbeitung angewendeter/archivierter Ereignisse und saubere Reassignment-Folgen
- Umwandlung eines einfachen archivierten Ereignisses in Oberereignis + Unterereignisse/Zeitsegmente
- Herausfallende Familien müssen gezielt neu zuordenbar sein
- `Ohne Ereignis` als segmentbasierter Sonderfall
- keine Duplikate gleicher Ereignismetadaten
- keine Familien/Dateien ohne Kontextänderung aus einem Ereignis „herauswerfen“
- echte Archiv-Dateisystemwirkung bei T080–T088 mit IST→SOLL-Nachweis
- persistente Grenzen freigewordener Zeitsegmente
