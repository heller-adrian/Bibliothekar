# Pre.5 – Backend-Gesamtabnahme noch blockiert (31.10.2026)

**Entscheidung: NOT ACCEPTED / NO RELEASE.** Der Benutzer wünscht vollständige Backendabnahme **nur wenn** zuvor B01, Backup, Restore und SD-Recheck grün sind. Diese Bedingung ist NICHT erfüllt.

## Nachweise

| Lauf | Scope | Ergebnis | Source |
|---|---|---|---|
| [41227607033](https://github.com/heller-adrian/Bibliothekar/actions/runs/41227607033) | gesamte B01-Datei, 10 Fälle | **10 PASS / 0 FAIL** | `df1c1f43529c5a174c3bf6386906a182cf2653c7` |
| [41227720942](https://github.com/heller-adrian/Bibliothekar/actions/runs/41227720942) | 10 explizite originale Backup-/Restore-/Recheck-/Import-SIGKILL-Verträge | **0 PASS / 10 FAIL** | `f52d1c4318f0aaf1dc588e7daf34cbf330e78acd` |
| [41222826726](https://github.com/heller-adrian/Bibliothekar/actions/runs/41222826726) | 147 Originalfehler-Nodes auf älterem QA-Baum | **30 PASS / 117 FAIL** | `ffe05f61c83d9d990d0c4b834ff8a76f685aba40` |

**Artefakt Recovery:** [13052616493](https://github.com/heller-adrian/Bibliothekar/actions/runs/41227720942/artifacts/13052616493), vollständige `result.xml`, `stdout.log`, Command-/Exit- und Deadline-Metadaten. Der selbst ermittelte SHA-256 des heruntergeladenen ZIP stimmt mit GitHub überein: `f3fa99af869a5163864a72182738f7bafe235202ac724bcbed5d8837aa7e5066`.

## Die zehn originalen Blocker (jeweils FAIL)

| Gruppe | Node | Beobachtung |
|---|---|---|
| Backup | `test_0500_staging_crash_before_main_commit_rolls_back` | Neue Backup-Recovery-Reservation durch F14-Orphan des ursprünglichen Löschauftrags blockiert |
| Backup | `test_0500_after_main_commit_crash_completes_purge` | Gleiches Eintrittsproblem vor gesichertem Löschabschluss |
| Backup negative | `test_0500_tampered_staged_file_is_never_deleted` | Schutzfall erreicht eigene Byte-Integritätsprüfung nicht, weil Admission zuerst blockiert |
| R1 negative | `test_r1_batch_collision_after_first_move_stays_blocked` | Erwartete Startup-Sperre bleibt aus; Restart liefert Exit 0 |
| R1 positive | `test_r1_direct_restore_commits_resume_once[r1.completed]` | `.trash-restores/*.json` besteht nach sonst korrekter Datenbankrückkehr fort |
| 0562 Restore | `test_0562_restore_recovery_two_progressive_sigkills` | erwarteter zweiter Recovery-SIGKILL-Hook nicht erreicht |
| SD-Recheck | `test_sigkill_real_startup_and_three_independent_restarts[after_handoff]` | Folgeimport bleibt `queued` |
| SD-Recheck | `test_sigkill_real_startup_and_three_independent_restarts[hash]` | Hauptprüfung bleibt `verifying` |
| SD-Recheck | `test_folder_actual_sigkill_atomic_handoff_and_three_restarts[after_handoff]` | Folgeimport bleibt `queued` |
| Import negative | `test_0562_import_discard_keeps_unowned_files[bytes]` | Job bleibt `organizing` statt `interrupted` nach Schutzabweisung |

## Architekturgrenze und sicherer Reparaturvorschlag

1. **Backup-Admission separat prüfen**: `app/backup_management.py::recover_backup_deletions` und `app/root_operations.py::protect/reserve` sowie `app/operation_health.py::_require_write`. Die erste Reservation enthält `ids.function=app.backup_management.delete_backup` und Job-ID; der Recovery-Einstieg besitzt einen anderen Funktionsnamen. `app/domain_recovery.py::handlers/replay` qualifiziert derzeit nur spezifische Trash-/Restore-/Finalizer-Handler; eine sichere Backup-Resume-Vertragsprüfung fehlt. Lösung nur mit exakter ursprünglicher Reservation, registrierten Bibliotheken, DB-Integrität, verifiziertem Journal-/Datei-/Generationsstatus, eindeutiger Recovery-Receipt und negativen Tamper-Prüfungen. **Kein globales `_RECOVERING` oder Autorisierungs-Bypass.**
2. **Restore getrennt**: differenzieren zwischen echter unsicherer Kollision, fehlendem Journal-Cleanup und zweitem Recovery-SIGKILL. Fremde Bytes und unzuordenbare Dateien müssen erhalten und weitere Schreibvorgänge gesperrt bleiben.
3. **SD-Recheck getrennt**: ursprünglichen persistenten Job und seinen Kindauftrag nach realem SIGKILL mit identischer Source-/Scope-Identität verfolgen. `verifying/queued` darf nur nach gesicherter Wiederaufnahme in `completed` übergehen, nicht über unqualifiziertes erneutes Enqueue.
4. **Abbruch/Import**: keine Umetikettierung `organizing -> interrupted`, bevor Dateifamilie, Fremdbytes und Persistenz des Original-Journals sauber gegengeprüft sind.
5. Danach je Gruppe gerichtete positive und negative Tests, erst bei Grün aktueller vollständiger Backend-F8-Partitionslauf einschließlich aller neu und historisch bestehenden Nodes, Frontend und Container, vollständige Artefaktprüfung und gesonderte Release-Freigabe.

**Nur Test-/QA-/Dokumentationsänderungen in dieser Gesprächsphase; Anwendungscode blieb auf `ff11f88b8116bae5b0d39f824b1eef828d39e659`. Keine Veröffentlichung.**

### Nachtrag: BA-02-F14-Backup-Problem geschlossen

Mit Commits d89a32d5, d77a8f11 und c1115ac7 wurde der originale
Backup-Loesch-Retry streng an die vorherige F14-Reservation gebunden.
Die komplette BA-02-Testdatei: 11/11 PASS (GitHub 41228704454).
Artefakt 13052677866, SHA256:
c0ad58ad281568871a6c34058e18986f68c5a069250d93be49385ca2d732dafa.
Die acht BA-02-Nodes des urspruenglichen Fehler-Inventars sind gruen.
Alle nicht zu Backup gehoerenden sieben Fehler aus dem 10er-Run
41228354107 bleiben rot. Volle Backendabnahme und Release weiter GESPERRT.
