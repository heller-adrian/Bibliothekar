# Bibliothekar Pre.5 – begrenzte Fehlerdiagnose vom 31.10.2026

**Status:** Abnahme ROT. **Keine Veröffentlichung.** Diese Datei ist eine Ursachen-Triage,
kein bestandener Release-Audit und keine Freigabe zur Änderung produktiver Sicherheitsprüfungen.

## Unveränderliche Quellen und Prüfabdeckung

- Repository: `heller-adrian/Bibliothekar`, Branch `codex/pre5-operation-recovery`.
- **Anwendungscode:** `ff11f88b8116bae5b0d39f824b1eef828d39e659`.
- **Diagnose-/QA-Commit:** `a00c51a7adc82b44409d69741e3690a6660f557e` (nur QA; keine App-Codeänderung).
- Neue isolierte GitHub-Actions-Ausführung:
  [41226158077](https://github.com/heller-adrian/Bibliothekar/actions/runs/41226158077)
  – `reproductions=FAIL`, Frontend/Container/Backend-Volljobs nicht gestartet.
- **24 eindeutig ausgewählte Original-Fehlernodes** aus 12 der 13 noch offenen
  Klassifikationsgruppen. Drei unabhängige Linux-Scratch-Umgebungen; gleiche
  Quelltests, echte Prozesse, Originalfristen und F14-/SQLite-Prüfungen.
- **4 PASS, 20 FAIL, 0 ERROR, 0 SKIP, 0 fehlende oder doppelte JUnit-Fälle.**
  Gruppen: Setup/Backup/Scope 3 PASS/6 FAIL; Recovery/Restore 1 PASS/6 FAIL;
  Worker/SQL 0 PASS/8 FAIL.
- Vorheriger breiter, aber schlecht archivierter Lauf:
  [41222826726](https://github.com/heller-adrian/Bibliothekar/actions/runs/41222826726),
  147 Originalfälle: 30 PASS, 117 FAIL, 0 ERROR/SKIP, ca. 34 Minuten.
  Dort wurde aufgrund eines Upload-Pfadfehlers nur das gekürzte Launcher-Log gesichert.
  Diese 117 FAIL dürfen **nicht** als 117 nachweislich unabhängige Produktfehler gelten.
- **Vollständig gesichertes Diagnoseartefakt:**
  [13051308412](https://github.com/heller-adrian/Bibliothekar/actions/runs/41226158077/artifacts/13051308412).
  GitHub ZIP-SHA256 und unabhängig nach Download geprüfter SHA256:
  `98cc15f4a128b2edf1e3723e7d1c0974f23cc0d9998ce9065f13c6459131ad9b`.
  Inhalt: vollständige 3× JUnit-XML, 3× ungekürztes Pytest-stdout,
  Bootstrap-/Runner-Logs, Auswahl, Exitstatus, Deadline-Metadaten,
  strukturierte `summary.json` mit 20 individuellen Trace-Auszügen.
  Einzelergebnisse in dieser Datei sind auf das vollständige Artefakt rückführbar.

## Auswertung: beobachtete Symptome, nicht gleichgesetzte Ursachen

1. **Preflight/Fixtures:** Ein RC9-Setup-Test meldet `catalog_unavailable`
   trotz zulässiger expliziter Neueinrichtung. Ein 0562-Test erstellt die
   vorausgesetzten Unterordner `General`/`Batch Correction` nicht; die
   Schutzprüfung stoppt den Worker vor der erwarteten SIGKILL-Grenze.
   **Hypothese:** Fixture- oder historische Erwartungsdifferenz; noch kein
   Beleg für einen zu lockernden Storage-Guard.
2. **Verwaiste Reservations-/Domain-Recovery-Grenzen:** Mehrere Backup-,
   Papierkorb-, Restore- und Recheck-Fälle stoßen an
   `operation_recovery_required` *vor* dem vertraglich geforderten,
   exakt qualifizierten Wiederanlauf. **Hypothese:** Übergang von
   ursprünglicher F14-Reservation zu fachlich geprüfter Wiederaufnahme
   muss pro Operation/Scope untersucht werden; keinesfalls globale Ausnahme.
3. **Fehlende oder fortbestehende Journale:** Ein Lösch-Recoveryfall meldet
   `domain_recovery_missing_delete_journal_or_receipt`, ein R1-Fall
   bewahrt `.trash-restores/*.json` auch nach korrekt erscheinender
   DB-/Audit-Rückkehr. Ob Originalbelege fehlen oder Abschluss/Cleanup
   unterbleibt, muss am sicheren Originalprotokoll geklärt werden.
4. **Handoff/Jobzustände:** Zweimal bleibt der Folgerecheck nach drei
   Neustarts `queued` statt `completed`. Ein Import-Verwerfungsfall
   bleibt `organizing` statt `interrupted`. Mehrfach ist die
   spätere Zustandsaktualisierung wegen einer Sperre nicht erreichbar.
5. **SQL-/Metadata-Autorisierung:** Im F15-Originalvertrag wird
   `DatabaseError('not authorized')` protokolliert und der erwartete
   Thread stirbt. F17 weist ebenfalls eine fehlgeschlagene
   Sicherheits-Assertion auf. Der RC6-Recheck zeigt zusätzlich
   `not authorized` beim Speichern des Jobfehlers. Nur exakte
   Verbindung, Zeitpunkt, Scope und Statement prüfen.
6. **API-Lesekontrakte:** Bei aktivem Inventar-Writer liefert ein
   Leserequest `200` statt historisch erwartetem `409`.
   Ein zweiter B01-Test erreicht die alte Hook-/Wartebedingung nicht.
   Möglicherweise ist die alte Annahme über schreibende GETs obsolet;
   stattdessen tatsächliche Read-only-/Snapshot-Sicherheit nachweisen.
7. **R1-Kollision und Restdateien:** Eine erwartete Sperrung bzw.
   ursprüngliche Dateiverschiebung wird nicht erreicht. Die
   bestehenden Erhaltungsregeln (auch bei identischen fremden Bytes
   oder neuer Inode) dürfen nicht durch bloße Testgrünung entfernt werden.

**Wichtige Gegenbelege (4 PASS):** Beide angepassten historischen
Verhaltensverträge (0414/0554), ein abgeschlossener Papierkorb-Journal-Retry
und ein Restore-Konflikt, der nicht automatisch neu eingeplant wird.
Damit sind pauschale Aussagen, dass jede Recoverysperre defekt sei, widerlegt.

## Alle 24 getesteten Originalfälle

### Setup, Backup, Papierkorb und Lesekonflikte (9 Fälle)

| Test | Ergebnis | Konkreter Befund |
|---|---|---|
| `test_0414_planned_save_uses_fast_post_write_refresh_only` | PASS | Historischer Verhaltensvertrag zur Aktualisierung erfüllt |
| `test_0554_startup_calls_bootstrap_before_database` | PASS | Historischer Bootstrap-Reihenfolgevertrag erfüllt |
| `test_populated_unregistered_archive_allows_first_library_setup[technical_control]` | FAIL | can_setup_again=true, aber zusätzlich catalog_unavailable bei fehlender Hauptdatenbank; Diagnose-/Fixture-Abgleich |
| `test_0500_after_main_commit_crash_completes_purge` | FAIL | Backup-Löschung bei Wiederanlauf durch operation_recovery_required vor Abschluss blockiert |
| `test_0500_unknown_stage_file_blocks_destructive_purge` | FAIL | Auch negativer Staging-Fall wird bereits durch operation_recovery_required blockiert |
| `test_P202b_F1_journal_write_error_must_leave_recovery_evidence` | FAIL | domain_recovery_missing_delete_journal_or_receipt; Fehlen des Originalbelegs muss geklärt werden |
| `test_committed_journal_sync_failure_retains_original_until_retry` | PASS | Commit-Journal-Syncfehler behält Original und erfüllt Retry-Vertrag |
| `test_inactive_reservation_only_blocks_its_own_selection[direct-failed]` | FAIL | Unabhängige Papierkorb-Auswahl wird durch ältere Scope-/Leasesperre blockiert |
| `test_b01_live_inventory_conflict_is_bounded_and_visible` | FAIL | Lesendes GET liefert 200, alter Test fordert 409; Lesekonsistenz separat nachweisen |

### Prozess-Wiederherstellung, Restore und Metadaten (7 Fälle)

| Test | Ergebnis | Konkreter Befund |
|---|---|---|
| `test_0562_import_discard_keeps_unowned_files[bytes]` | FAIL | Import-Job bleibt organizing statt interrupted nach Abbruch mit fremden Bytes |
| `test_0562_metadata_projection_recovery_two_sigkills` | FAIL | Historische Recovery-Fixture ohne General/Batch Correction; technischer Startup verweigert bewusst den Start |
| `test_0562_restore_recovery_two_progressive_sigkills` | FAIL | Erwarteter zweiter SIGKILL-Punkt nicht erreicht; unresolved_operation_scope, Prozess endet 0 |
| `test_r1_batch_collision_after_first_move_stays_blocked` | FAIL | Restore-Kollision führt zu Prozess-Exit 0 statt erwarteter Sperre; Fallanalyse nötig |
| `test_r1_direct_restore_commits_resume_once[r1.completed]` | FAIL | DB/Audit korrekt, aber privates .trash-restores-Journal nach Abschluss weiter vorhanden |
| `test_r1_conflict_job_is_not_automatically_requeued` | PASS | Konfliktjob wird nicht ungeprüft automatisch erneut eingeplant |
| `test_metadata_safety_contract[f17_current]` | FAIL | Historischer F17-Vertrag zur abgewiesenen Metadata-Schreibanfrage schlägt fehl; Sub-Assertion prüfen |

### SD-Recheck, Worker und Autorisierung (8 Fälle)

| Test | Ergebnis | Konkreter Befund |
|---|---|---|
| `test_metadata_safety_contract[f15_active]` | FAIL | Historischer F15-Vertrag: SQLite not authorized, erwarteter Worker bleibt nicht aktiv |
| `test_two_real_process_checks_sigkill_and_three_restarts[True]` | FAIL | RC6-SD-Recheck: operation_recovery_required, Fehlerstatus nicht in SQLite schreibbar (not authorized) |
| `test_sigkill_real_startup_and_three_independent_restarts[after_handoff]` | FAIL | SD-Recheck-Kindauftrag nach drei Neustarts queued statt completed |
| `test_folder_actual_sigkill_atomic_handoff_and_three_restarts[after_handoff]` | FAIL | SD-Recheck-Kindauftrag nach drei Neustarts queued statt completed |
| `test_b01_compatibility_request_collision` | FAIL | Kompatibilitäts-GET erreicht erwarteten synchronisierenden Eingriff nicht innerhalb 5 s |
| `test_inactive_reservation_only_blocks_its_own_selection[http-failed]` | FAIL | HTTP-Scopeversuch durch operation_recovery_required abgewiesen |
| `test_r1_collision_sigkill[r1.prepared]` | FAIL | R1-Kollisionsfall: Originaldatei bleibt am Ausgangsort, obwohl Test Entfernen erwartet |
| `test_f14_finished_receipt_survives_repeated_sigkill` | FAIL | Historische F14-Fertigstellungs-SIGKILL-Grenze: Writer startet wegen operation_recovery_required nicht |

## Vorgehen für die nächste, getrennt freizugebende Entwicklungsrunde

1. **Zuerst Testaufbau und Verhalten trennen:** RC9, fehlende General-/Batch-Anker
   und beide B01-GET-Verträge gegen die tatsächlich vorgesehene
   Ersteinrichtungs-/Read-only-Semantik abgleichen. Nur belegbar veraltete
   Erwartungen/Fixtures ändern, nie einen Sicherheitsfehler maskieren.
2. **Dann echte fachliche Recovery-Defekte einzeln:** Originalreservation,
   Nonce, Generation, Datenbank, vollständige Rollen-/Inodebindung,
   Domainjournal und bestehende negative Sicherheitsverträge müssen
   übereinstimmen; Backup/Trash/R1/Import/SD-Recheck pro Scope und echter
   Prozessabbruchgrenze wiederholen.
3. **Jede Korrektur klein und beweisbar:** erst reproduzierbarer roter
   Originaltest + Gegenprobe mit manipulierten Bytes/Journal,
   danach gerichteter Test. Keine umfassende Matrix zwischen jeder
   Einzelkorrektur.
4. **Schlussabnahme erst danach:** alle ursprünglich 240 roten Nodes und
   alle übrigen Backendfälle in acht disjunkten Partitionen, Frontend,
   Browser und echte isolierte Containerläufe *auf identischem finalem
   Anwendungscode*. Bereits grüne Altartefakte ersetzen das nicht.
5. Release-Automation erst nach grüner aktueller Matrix und gepinntem
   Abnahmeprotokoll neu auf den geprüften Commit binden. Bis dahin
   **kein** `v1.0.0-pre.5`, GHCR-Image, `latest`, `main` oder TrueNAS-Eingriff.

## Diagnose-Grenzen

- Die 24 Fälle sind **gezielt ausgewählte Stichproben**, keine Wiederholung
  aller 147 oder aller 2444+ Backendtests. Aus 20/24 darf man nicht
  rechnerisch auf 117 verschiedene Ursachen schließen.
- Frontend, Container und Gesamtbackend wurden im Diagnoselauf absichtlich
  nicht wiederholt; ihr Status auf dem neuen Code bleibt unbekannt.
- Die zwei sehr langsamen Performancefälle waren zuvor ohne Profiling
  unter unveränderten 90-/300-s-Fristen nachgewiesen. In dieser Runde
  absichtlich nicht wiederholt.
- Linux-QA findet ausschließlich in synthetischem Scratch statt; Native
  TrueNAS/NFSv4-ACL, reale SD/USB, echtes DNG1.7-/RAF-Schreiben sind
  damit nicht als zusätzlich bestanden behauptet.

