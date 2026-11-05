## Aktualisierung 01.11.2026 – neueste Patches noch PENDING

Für die aktuelle Arbeit nach dem Codex-Abschluss gilt die eindeutige neue Spitze in `FORTSETZUNG.md`. Die Linux-Läufe 41306238349 und 41307568578 sind nicht als PASS gewertet, solange JUnit und SHA nicht vorliegen. Implementiert wurden ausschließlich eng gebundene, prospective Multiple-/Reintegration-Rollbacks und ein historisch nötiger Negativtest für unqualifizierten Import-Retry. Alte Eigentumsbeweise werden nicht erfunden. Pre.5 bleibt gesperrt.

# Pre.5 Backend-Reparatur – 01.11.2026

**BACKEND NOT ACCEPTED**

Basis: Run41231600475, Source7838a7062565b712a4f24fa481967d46df173d45. Alle147 JUnit-Nodes und15 kritischen Fälle vollständig ausgewertet. Paket250/250 Dateien bytegleich mit kryptografisch verifiziertem GitHub-Artefakt13055435531. Vollständige Logs/XML/JSON liegen lokal und im unveränderten Artefakt.

Die maschinenlesbare Begleitdatei enthält jeden der58 exakten Nodes, Trace-Digest, Phase, Komponente, Ursache/Hypothese und Status. REQUIRES_QUALIFICATION ist ausdrücklich keine nachgewiesene Diagnose.

## Phase A – erster gemeinsamer Produktfehler

Restore-Recovery prüft bestehende Konflikte durch _conflict_invariants und bewahrt das Konfliktjournal als Quellen-/Zielreservierung. domain_recovery.replay verlangte danach dennoch ein leeres Journalverzeichnis. Korrektur prüft sämtliche verbliebenen Konflikte nochmals unter durchgehendem Trash-Lock, erhält Journal und Fehler und schreibt nur einen Isolation-Abschluss mit Originalreservation. Keine Umdeutung als erfolgreiche Wiederherstellung. Unvollständige/inkonsistente Zustände bleiben gesperrt.

Linux Run [41260071820](https://github.com/heller-adrian/Bibliothekar/actions/runs/41260071820) auf `4682b22a3377b57fdc24355ee20fdce11366c41e`: **24 PASS, 0 FAIL/ERROR/SKIP**. Alle15 ursprünglichen kritischen Node-IDs sind enthalten; fünf ursprünglich rote Kollisionsfälle sind gezielt grün. Artefakt13064419670, ZIP SHA256 `b40faee8dd967452de7221d03a30cc1bdf536a157db650e2bd64675d896c7ba3`, unabhängig heruntergeladen/geprüft; vollständiges XML und Prozesslogs gesichert.

## Weitere gemeinsame Ursachen und gezielte Änderungen

- `bd168d53`: F15/F18 – abgelehnte konkurrierende Korrekturen erzeugten bereits vor physischer Schreibsperre/Projektionsprüfung dauerhafte F14-Intents. Physische Sperre und read-only Zulassung liegen jetzt davor; executorinterne Prüfungen bleiben. Zwei neue echte Batch-/ExifTool-Gegenproben vergleichen die lebende Originalreservation bytegenau vor/nach Ablehnung und starten zweimal neu. Kein Zurücksetzen einer bestehenden Reservation.
- `efd1dbdf`: Phase A – ein ursprünglicher Sortierlauf konnte den vorhandenen Rückbau nicht unter seiner eigenen Lease erreichen. Einzelne camera-only Pre-Commit-Pläne können jetzt nur nach Registry-/DB-/Generations-/Bindings-/Job-/Event-/Hash-/Pfadnachweis fortgesetzt werden. Neue `sort_recovery_proof.py`; vorhandener Rückbau auf exakten run_id begrenzbar. Alle Quellen und Ziele vorab geprüft. Doppelte Endpunkte, Hardlinks, unbekannte Bytes, Assets, ungebundene Wurzeln und bereits committete Ergebnisse werden nicht geraten. Sechs neue negative Fälle prüfen Originalnonce, unveränderte Bytes und bleibende Schreibsperre über zwei Starts. Diese Implementierung ist noch **NICHT** Linux-abgenommen.
- `68364546`: Phase B – die bestehende Trash-Sperre umfasst nun auch die F14-Zulassung; ein passender originaler Restore darf nur durch den vollständigen vorhandenen Domain-Qualifier abgeschlossen werden, bevor eine neue unabhängige Operation beginnt. Konfliktjournal und A-Pfade bleiben reserviert. Keine Freigabe aus Jobstatus allein. Fixture-Registry wird bei fünf Fällen vor dem Seed festgelegt, statt nachher den Kontrollbereich zu wechseln.
- `5ffa9175`: physische Metadata-Lock-Reentranz an Workspace, PID und Thread-ID gebunden. Kopierte ContextVars dürfen keinen fremden Thread zum Lock-Eigentümer erklären. Neue Gegenprobe und sieben Statement-Authorization-, acht Schema-Authorization- sowie volle B01-Verträge im gezielten Manifest.
- `969e591d`: sechs RC4-Fälle – die erste absichtlich abgewiesene DELETE-Auswahl erzeugte den verwaisten F14-Record selbst. Auswahl-/Aktivitätsprüfungen erfolgen vor dem neuen Intent unter derselben Sperre; die wiederholte Kontrolle nach Journalanlage bleibt unverändert. Negative aktive Restore- und Journaländerungsfälle mitselektiert.
- Technische General/Batch-Fixtures wurden vor der simulierten Unterbrechung vollständig angelegt. Produktive fehlende Verwaltungsanker werden weiterhin weder ersetzt noch stillschweigend angelegt.

Lokale Python-Syntaxprüfung, `git diff --check` und Actionlint PASS. Das sind keine Linux-Funktionsnachweise. Alle späteren Änderungen sind bis zum vollständigen gezielten Linux-Ergebnis PENDING.

## Vollständiges ursprüngliches Fehlerinventar

- `tests/backend/test_0561_audit_regressions.py::test_P202b_F1_journal_write_error_must_leave_recovery_evidence` — Phase E; FIX_IMPLEMENTED_TARGET_PENDING. Synchronous audited rollback removes its delete journal before the original F14 exception exits. No completion receipt remains. Retain that journal in the exception recovery path until exact-original domain replay qualifies and closes it; never infer completion from absence.
- `tests/backend/test_0561_recovery.py::test_startup_recovers_general_swap_before_onboarding_worker` — Phase C; LATEST_FOCUSED_FAIL_FIXTURE_CORRECTION_PENDING. The fixture creates only the four top-level administrative roles before its crash. General/Batch are required structural anchors; both are now provisioned before the operation, never synthesized in production recovery.
- `tests/backend/test_0562_process_recovery.py::test_0562_metadata_preparation_keeps_unknown_file` — Phase A; OPEN. Old nonzero-start expectation may conflict with protected READ availability; original F14 writer fence and bytes must be demonstrated before updating the test.
- `tests/backend/test_0562_process_recovery.py::test_multilibrary_projection_sigkill[multi.source_family1]` — Phase A; OPEN. Pre-publication abandoned import retains active SQL status; current qualification requires media-publication evidence not yet available at this crash boundary.
- `tests/backend/test_0562_process_recovery.py::test_other_metadata_modes_sigkill[library_metadata]` — Phase A; OPEN. Test hashes the original fixture path after startup; determine actual catalogue-authorized relocation before treating absent path as lost media.
- `tests/backend/test_0562_process_recovery.py::test_other_metadata_modes_sigkill[multiple_metadata]` — Phase A; OPEN. Test hashes the original fixture path after startup; determine actual catalogue-authorized relocation before treating absent path as lost media.
- `tests/backend/test_0562_process_recovery.py::test_other_metadata_modes_sigkill[reintegrate]` — Phase A; OPEN. Test hashes the original fixture path after startup; determine actual catalogue-authorized relocation before treating absent path as lost media.
- `tests/backend/test_0562_process_recovery.py::test_recovery_keeps_foreign_bytes_after_sigkill[metadata-meta.swap]` — Phase A; OPEN. Old nonzero-start expectation may conflict with protected READ availability; original F14 writer fence and bytes must be demonstrated before updating the test.
- `tests/backend/test_0562_process_recovery.py::test_recovery_keeps_foreign_bytes_after_sigkill[trash-trash.db1]` — Phase A; OPEN. Old nonzero-start expectation may conflict with protected READ availability; original F14 writer fence and bytes must be demonstrated before updating the test.
- `tests/backend/test_0562_process_recovery.py::test_sd_import_sigkill[import.before_copy]` — Phase A; OPEN. Pre-publication abandoned import retains active SQL status; current qualification requires media-publication evidence not yet available at this crash boundary.
- `tests/backend/test_0562_process_recovery.py::test_sd_import_sigkill[import.copy_chunk]` — Phase A; OPEN. Pre-publication abandoned import retains active SQL status; current qualification requires media-publication evidence not yet available at this crash boundary.
- `tests/backend/test_0562_process_recovery.py::test_sd_import_sigkill[import.copy_verify]` — Phase A; OPEN. Pre-publication abandoned import retains active SQL status; current qualification requires media-publication evidence not yet available at this crash boundary.
- `tests/backend/test_0562_process_recovery.py::test_sd_import_sigkill[import.hash_chunk]` — Phase A; OPEN. Pre-publication abandoned import retains active SQL status; current qualification requires media-publication evidence not yet available at this crash boundary.
- `tests/backend/test_0562_process_recovery.py::test_sort_reconcile_sigkill[reconcile-reconcile.before_db]` — Phase A; FIX_IMPLEMENTED_TARGET_PENDING. Original sort/reconcile leases have no qualified startup handoff to the existing rollback. Narrow original-lease replay now qualifies a single registered camera-only pre-commit plan. Committed runs and unsupported assets remain fenced pending separate proof.
- `tests/backend/test_0562_process_recovery.py::test_sort_reconcile_sigkill[reconcile-reconcile.db]` — Phase A; FIX_IMPLEMENTED_TARGET_PENDING. Original sort/reconcile leases have no qualified startup handoff to the existing rollback. Narrow original-lease replay now qualifies a single registered camera-only pre-commit plan. Committed runs and unsupported assets remain fenced pending separate proof.
- `tests/backend/test_0562_process_recovery.py::test_sort_reconcile_sigkill[reconcile-reconcile.move1]` — Phase A; FIX_IMPLEMENTED_TARGET_PENDING. Original sort/reconcile leases have no qualified startup handoff to the existing rollback. Narrow original-lease replay now qualifies a single registered camera-only pre-commit plan. Committed runs and unsupported assets remain fenced pending separate proof.
- `tests/backend/test_0562_process_recovery.py::test_sort_reconcile_sigkill[reconcile-reconcile.move2]` — Phase A; FIX_IMPLEMENTED_TARGET_PENDING. Original sort/reconcile leases have no qualified startup handoff to the existing rollback. Narrow original-lease replay now qualifies a single registered camera-only pre-commit plan. Committed runs and unsupported assets remain fenced pending separate proof.
- `tests/backend/test_0562_process_recovery.py::test_sort_reconcile_sigkill[sort-sort.before_db]` — Phase A; FIX_IMPLEMENTED_TARGET_PENDING. Original sort/reconcile leases have no qualified startup handoff to the existing rollback. Narrow original-lease replay now qualifies a single registered camera-only pre-commit plan. Committed runs and unsupported assets remain fenced pending separate proof.
- `tests/backend/test_0562_process_recovery.py::test_sort_reconcile_sigkill[sort-sort.move1]` — Phase A; FIX_IMPLEMENTED_TARGET_PENDING. Original sort/reconcile leases have no qualified startup handoff to the existing rollback. Narrow original-lease replay now qualifies a single registered camera-only pre-commit plan. Committed runs and unsupported assets remain fenced pending separate proof.
- `tests/backend/test_0562_process_recovery.py::test_sort_reconcile_sigkill[sort-sort.move2]` — Phase A; FIX_IMPLEMENTED_TARGET_PENDING. Original sort/reconcile leases have no qualified startup handoff to the existing rollback. Narrow original-lease replay now qualifies a single registered camera-only pre-commit plan. Committed runs and unsupported assets remain fenced pending separate proof.
- `tests/backend/test_0562_process_recovery.py::test_sort_recovery_sigkill[reconcile-reconcile.move2]` — Phase A; FIX_IMPLEMENTED_TARGET_PENDING. Original sort/reconcile leases have no qualified startup handoff to the existing rollback. Narrow original-lease replay now qualifies a single registered camera-only pre-commit plan. Committed runs and unsupported assets remain fenced pending separate proof.
- `tests/backend/test_0562_process_recovery.py::test_sort_recovery_sigkill[sort-sort.move2]` — Phase A; FIX_IMPLEMENTED_TARGET_PENDING. Original sort/reconcile leases have no qualified startup handoff to the existing rollback. Narrow original-lease replay now qualifies a single registered camera-only pre-commit plan. Committed runs and unsupported assets remain fenced pending separate proof.
- `tests/backend/test_0562_recovery_guards.py::test_startup_recovers_registered_databases_only[False]` — Phase E; FIX_IMPLEMENTED_TARGET_PENDING. Configured registry is switched after initial layout/F14 seed, relocating control authority in the child. Fix explicit test namespace before initial seed; missing-control guard remains active.
- `tests/backend/test_0562_recovery_guards.py::test_startup_recovers_registered_databases_only[True]` — Phase E; FIX_IMPLEMENTED_TARGET_PENDING. Configured registry is switched after initial layout/F14 seed, relocating control authority in the child. Fix explicit test namespace before initial seed; missing-control guard remains active.
- `tests/backend/test_f11_trash_reservation.py::test_f11_legacy_delete_reservation_conflict_preserves_evidence` — Phase B; OPEN. Old nonzero-start expectation may conflict with protected READ availability; original F14 writer fence and bytes must be demonstrated before updating the test.
- `tests/backend/test_f11_trash_reservation.py::test_f11_original_boundary_and_restore` — Phase B; OPEN. Inspect complete trace and registered scope; no independent root cause accepted yet.
- `tests/backend/test_f14_backup_completion.py::test_f14_backup_rollback_receipt_survives_real_sigkill[before-receipt]` — Phase D; FIX_IMPLEMENTED_TARGET_PENDING. Configured registry is switched after initial layout/F14 seed, relocating control authority in the child. Fix explicit test namespace before initial seed; missing-control guard remains active.
- `tests/backend/test_f14_backup_completion.py::test_f14_backup_rollback_receipt_survives_real_sigkill[journal-removed]` — Phase D; FIX_IMPLEMENTED_TARGET_PENDING. Configured registry is switched after initial layout/F14 seed, relocating control authority in the child. Fix explicit test namespace before initial seed; missing-control guard remains active.
- `tests/backend/test_f14_backup_completion.py::test_f14_backup_rollback_receipt_survives_real_sigkill[receipt]` — Phase D; FIX_IMPLEMENTED_TARGET_PENDING. Configured registry is switched after initial layout/F14 seed, relocating control authority in the child. Fix explicit test namespace before initial seed; missing-control guard remains active.
- `tests/backend/test_f14_continuation.py::test_f14_finished_receipt_survives_repeated_sigkill` — Phase E; OPEN. Requested receipt/SIGKILL boundary is never reached; inspect original durable receipt and admission ordering, not just process exit status.
- `tests/backend/test_f14_fixed_storage.py::test_f14_four_empty_directories_are_not_a_startup_mount_certificate` — Phase C; OPEN. Historical four-role expectation must include new mandatory General/Batch roles; no empty mount may be certified by directory names alone.
- `tests/backend/test_f14_fixed_storage.py::test_f14_metadata_recovery_existing_assertions_with_complete_storage_fixture` — Phase C; LATEST_FOCUSED_FAIL_FIXTURE_CORRECTION_PENDING. The fixture creates only the four top-level administrative roles before its crash. General/Batch are required structural anchors; both are now provisioned before the operation, never synthesized in production recovery.
- `tests/backend/test_f14_runtime.py::test_f14_real_worker_rejects_rename_then_allows_completion[reconcile-reconcile.move1]` — Phase E; FIX_IMPLEMENTED_TARGET_PENDING. Original sort/reconcile leases have no qualified startup handoff to the existing rollback. Narrow original-lease replay now qualifies a single registered camera-only pre-commit plan. Committed runs and unsupported assets remain fenced pending separate proof.
- `tests/backend/test_metadata_consistency_f15_f17_f18.py::test_metadata_safety_contract[f15_active]` — Phase C; LATEST_FOCUSED_FAIL_FIXTURE_CORRECTION_PENDING. Rejected concurrent metadata writer / pending projection creates a new durable F14 reservation before read-only admission. The abandoned new record then fences the original live writer or its projection.
- `tests/backend/test_metadata_consistency_f15_f17_f18.py::test_metadata_safety_contract[f15_pending]` — Phase C; LATEST_FOCUSED_FAIL_FIXTURE_CORRECTION_PENDING. Rejected concurrent metadata writer / pending projection creates a new durable F14 reservation before read-only admission. The abandoned new record then fences the original live writer or its projection.
- `tests/backend/test_metadata_consistency_f15_f17_f18.py::test_metadata_safety_contract[f17_current]` — Phase C; LATEST_FOCUSED_FAIL_FIXTURE_CORRECTION_PENDING. Nested historical metadata fixture or recovery contract fails; missing administration roots, propagation ownership and exact orphan must be separated.
- `tests/backend/test_metadata_consistency_f15_f17_f18.py::test_metadata_safety_contract[f18_false]` — Phase C; FOCUSED_PASS. Rejected concurrent metadata writer / pending projection creates a new durable F14 reservation before read-only admission. The abandoned new record then fences the original live writer or its projection.
- `tests/backend/test_metadata_consistency_f15_f17_f18.py::test_metadata_safety_contract[f18_true]` — Phase C; FOCUSED_PASS. Rejected concurrent metadata writer / pending projection creates a new durable F14 reservation before read-only admission. The abandoned new record then fences the original live writer or its projection.
- `tests/backend/test_r1_restore_recovery.py::test_r1_collision_and_three_full_starts[different]` — Phase A; FOCUSED_PASS. Retained restore conflict journal is rejected by generic no-pending-journal completion, or its broad original lease blocks an independent request before qualification.
- `tests/backend/test_r1_restore_recovery.py::test_r1_collision_and_three_full_starts[directory]` — Phase A; FOCUSED_PASS. Retained restore conflict journal is rejected by generic no-pending-journal completion, or its broad original lease blocks an independent request before qualification.
- `tests/backend/test_r1_restore_recovery.py::test_r1_collision_and_three_full_starts[hardlink]` — Phase A; FOCUSED_PASS. Retained restore conflict journal is rejected by generic no-pending-journal completion, or its broad original lease blocks an independent request before qualification.
- `tests/backend/test_r1_restore_recovery.py::test_r1_collision_and_three_full_starts[same]` — Phase A; FOCUSED_PASS. Retained restore conflict journal is rejected by generic no-pending-journal completion, or its broad original lease blocks an independent request before qualification.
- `tests/backend/test_r1_restore_recovery.py::test_r1_collision_and_three_full_starts[symlink]` — Phase A; FOCUSED_PASS. Retained restore conflict journal is rejected by generic no-pending-journal completion, or its broad original lease blocks an independent request before qualification.
- `tests/backend/test_r1_restore_recovery.py::test_r1_identical_foreign_target_excluded_from_reconcile` — Phase A; OPEN. Retained restore conflict journal is rejected by generic no-pending-journal completion, or its broad original lease blocks an independent request before qualification.
- `tests/backend/test_r1_restore_recovery.py::test_r1_independent_file_remains_usable[delete]` — Phase A; OPEN. Retained restore conflict journal is rejected by generic no-pending-journal completion, or its broad original lease blocks an independent request before qualification.
- `tests/backend/test_r1_restore_recovery.py::test_r1_independent_file_remains_usable[restore]` — Phase A; OPEN. Retained restore conflict journal is rejected by generic no-pending-journal completion, or its broad original lease blocks an independent request before qualification.
- `tests/backend/test_r1_restore_recovery.py::test_r1_independent_library_and_provenance` — Phase A; OPEN. Retained restore conflict journal is rejected by generic no-pending-journal completion, or its broad original lease blocks an independent request before qualification.
- `tests/backend/test_r1_restore_recovery.py::test_r1_parallel_operation_boundary[restore_B]` — Phase A; OPEN. Retained restore conflict journal is rejected by generic no-pending-journal completion, or its broad original lease blocks an independent request before qualification.
- `tests/backend/test_r1_restore_recovery.py::test_r1_two_restore_processes_after_owner_sigkill` — Phase A; OPEN. Retained restore conflict journal is rejected by generic no-pending-journal completion, or its broad original lease blocks an independent request before qualification.
- `tests/backend/test_r1_restore_recovery.py::test_r1_unsafe_invariant_blocks_global_start[new_library_origin]` — Phase A; OPEN. Retained restore conflict journal is rejected by generic no-pending-journal completion, or its broad original lease blocks an independent request before qualification.
- `tests/backend/test_rc1_sd_reimport.py::test_cancelled_import_can_retry_without_source_loss` — Phase B; OPEN. Inspect complete trace and registered scope; no independent root cause accepted yet.
- `tests/backend/test_rc4_acceptance_regressions.py::test_inactive_reservation_only_blocks_its_own_selection[direct-failed]` — Phase B; FIX_IMPLEMENTED_TARGET_PENDING. The first intentionally rejected delete selection creates a new shared trash F14 intent before checking the queued restore reservation. That declined DELETE, not the restore job state, then blocks independent B. Recheck admission under the same physical lock before F14; keep inner before-staging checks.
- `tests/backend/test_rc4_acceptance_regressions.py::test_inactive_reservation_only_blocks_its_own_selection[direct-interrupted]` — Phase B; FIX_IMPLEMENTED_TARGET_PENDING. The first intentionally rejected delete selection creates a new shared trash F14 intent before checking the queued restore reservation. That declined DELETE, not the restore job state, then blocks independent B. Recheck admission under the same physical lock before F14; keep inner before-staging checks.
- `tests/backend/test_rc4_acceptance_regressions.py::test_inactive_reservation_only_blocks_its_own_selection[direct-missing-job]` — Phase B; FIX_IMPLEMENTED_TARGET_PENDING. The first intentionally rejected delete selection creates a new shared trash F14 intent before checking the queued restore reservation. That declined DELETE, not the restore job state, then blocks independent B. Recheck admission under the same physical lock before F14; keep inner before-staging checks.
- `tests/backend/test_rc4_acceptance_regressions.py::test_inactive_reservation_only_blocks_its_own_selection[http-failed]` — Phase B; FIX_IMPLEMENTED_TARGET_PENDING. The first intentionally rejected delete selection creates a new shared trash F14 intent before checking the queued restore reservation. That declined DELETE, not the restore job state, then blocks independent B. Recheck admission under the same physical lock before F14; keep inner before-staging checks.
- `tests/backend/test_rc4_acceptance_regressions.py::test_inactive_reservation_only_blocks_its_own_selection[http-interrupted]` — Phase B; FIX_IMPLEMENTED_TARGET_PENDING. The first intentionally rejected delete selection creates a new shared trash F14 intent before checking the queued restore reservation. That declined DELETE, not the restore job state, then blocks independent B. Recheck admission under the same physical lock before F14; keep inner before-staging checks.
- `tests/backend/test_rc4_acceptance_regressions.py::test_inactive_reservation_only_blocks_its_own_selection[http-missing-job]` — Phase B; FIX_IMPLEMENTED_TARGET_PENDING. The first intentionally rejected delete selection creates a new shared trash F14 intent before checking the queued restore reservation. That declined DELETE, not the restore job state, then blocks independent B. Recheck admission under the same physical lock before F14; keep inner before-staging checks.
- `tests/backend/test_rc6_handoff.py::test_two_real_process_checks_sigkill_and_three_restarts[True]` — Phase E; OPEN. Inspect complete trace and registered scope; no independent root cause accepted yet.

## Noch offene Pflichtabnahme

147/147,15/15 auf finalem Source, volle BA-02/B01, acht disjunkte Backendpartitionen, Frontend/Browser und reale Container-/Supervisorabnahme: noch nicht vollständig abgenommen. Keine Veröffentlichung.

## Grenzen / Fortsetzung

Der aktuelle Gesamtstatus der ursprünglichen240 Fehlschläge lautet über die jeweils letzten, ausdrücklich quellgebundenen Einzelprüfungen: **189 PASS,51 FAIL**. Diese Werte stammen aus verschiedenen Commits und sind KEINE Endabnahme. Für den späteren Quellstand fehlen noch die vollständigen147, BA-02/B01, acht Partitionen, Frontend/Browser/Container.

Ungeklärte Bereiche insbesondere: Metadata library/multiple/reintegration-Recovery, frühe Import-Abbrüche ohne Publikationsbeleg, historische abgelehnte Operationen ohne verbleibendes Journal/Receipt, sichere Behandlung committeter Sortier-Nacharbeiten, einzelne alte Read-only-Startannahmen und noch nicht passend qualifizierte Legacy-Fixtures. Keine Abwesenheit eines Journals und kein terminaler SQL-Status allein darf als Abschluss gelten.

**BACKEND NOT ACCEPTED – Pre.5 noch nicht abnahmefähig – Veröffentlichung gesperrt.**

## Zweiter unabhängig verifizierter Lauf

[41260399276](https://github.com/heller-adrian/Bibliothekar/actions/runs/41260399276), Source `bd168d53c1b0431bcdac5fd6e8606aacbb18fed1`: **26 PASS /7 FAIL /0 ERROR /0 SKIP**,33 eindeutige Nodes. Artefakt13065735420, ZIP SHA256 `8857f69740ff2017992562bc97dac56d9ae1ebe8735a851500687ff85be0ca9c` unabhängig nach Download geprüft. Vollständige Restart-Logs belegen:

- F15 active/pending: vorheriges `not authorized` behoben, Ablehnung erzeugt keinen neuen F14-Record und alle Projektionen/Hashes stimmen; erst der Neustart scheitert an fehlenden General/Batch-Unterordnern der historischen Fixture.
- F17: Korrektur ist completed und konkurrierender Schreiber korrekt abgelehnt; dieselben fehlenden Fixture-Anker blockieren Neustart.
- F18 false/true: ursprüngliche unveränderte Parallelitätsassertionen jetzt PASS.
- Zwei neue Batch-Gegenproben: echte Ausführung, F14-Vergleich und Writerabschluss bestehen. Die anschließende neue Zeitprüfung erwartete fälschlich identische Zeiten; echte Batchfunktion bewahrt korrekt den ursprünglichen Ein-Sekunden-Abstand. Diese Erwartung wurde ausdrücklich anhand des Algorithmus und ExifTool-Ausgabe korrigiert.
- Zwei General-Recovery-Fixtures: nach vollständiger Ankeranlage erstmals bis zur Worker-Quieszenz gelangt; ein Fake `SimpleNamespace(is_alive=True)` implementiert `Thread.join` nicht. Jetzt kein vorbestehender echter Worker und ein interfacevollständiger Start-Probe; Recovery-/Byte-/Workerreihenfolge-Assertions bleiben.

`f91865d2` enthält diese eng begrenzten Fixture-/Testkorrekturen; kein historisches Original unter `qa/f16_f20/original/` wurde geändert.

## Kontrollierter Löschfehlerabschluss

`c06294e5`: Exception-Rückbau in `trash_selective` behält sein vollständig geprüftes vorbereitetes/committetes Journal, auch wenn die Bytes bereits sicher zurückgebaut sind. Die äußere Originalreservation meldet weiterhin Fehler. Erst der nächste qualifizierte Original-Replay überprüft das Journal erneut, schreibt den dauerhaften Original-F14-Abschluss und entfernt das Journal regulär. Kein Ersetzen eines fehlenden Journals durch eine Erfolgsschätzung. Verstärkte F1-Gegenprobe verlangt Originalnonce im Abschlussreceipt und erhaltene Bytes. Noch PENDING.

## Aktueller Quellstand / laufende gezielte Abnahme

- Anwendung: `c06294e581e7c2e0a1721a637bc69f3924d10bcb`.
- Letzter QA-Commit: `e9061f41376519a63e429440a78df8e8de5cf387` (nur präzisere Diagnose eines bislang ungeklärten Vier-Ordner-Tests).
- [41261174452](https://github.com/heller-adrian/Bibliothekar/actions/runs/41261174452): älterer Zwischenstand `5ffa9175`, zum letzten Abruf RUNNING.
- [41261700576](https://github.com/heller-adrian/Bibliothekar/actions/runs/41261700576): kumulierter aktueller Stand `e9061f41`, zum letzten Abruf PENDING.47 Selektoren umfassen die ursprünglichen15 kritischen Nodes, Reparaturfälle und Gegenproben, volle BA-02/B01 sowie SQLite-Authorization. Kein Frontend/Container/volle Backendmatrix in diesem `[pre5-contracts]`-Lauf.
- Zwischenzeitliche pending Runs41260654482,41261007598,41261239346,41261424529,41261532863 wurden durch GitHubs Ein-Pending-Concurrencyregel zugunsten des neueren Standes ersetzt. Keine Abnahmen; kein Erfolg daraus abgeleitet.
- Die Workflows arbeiten ausschließlich auf dem dedizierten Self-Hosted-Safe-Runner und synthetischen Scratch-Pfaden. Kein neuer vollständiger QA-Lauf wurde gestartet.

## Geänderte Dateien und Reparaturcommits

- `.github/workflows/qa-pre5-operation-recovery.yml`
- `app/domain_recovery.py`
- `app/metadata_correction.py`
- `app/sort_apply.py`
- `app/sort_recovery_proof.py`
- `app/trash.py`
- `app/trash_restore.py`
- `app/trash_selective.py`
- `docs/pre5/BACKEND-REPAIR-58-20261101.json`
- `docs/pre5/BACKEND-REPAIR-58-20261101.md`
- `qa/metadata_consistency/fixtures.py`
- `qa/metadata_consistency/test_current.py`
- `qa/pre5/backend_contracts.json`
- `tests/backend/recovery_0562/worker.py`
- `tests/backend/test_0561_audit_regressions.py`
- `tests/backend/test_0561_recovery.py`
- `tests/backend/test_0562_process_recovery.py`
- `tests/backend/test_0562_recovery_guards.py`
- `tests/backend/test_f14_backup_completion.py`
- `tests/backend/test_f14_fixed_storage.py`
- `tests/backend/test_metadata_consistency_f15_f17_f18.py`
- `tests/backend/test_r1_restore_recovery.py`

- `e9061f41376519a63e429440a78df8e8de5cf387` test(pre5): retain complete fresh-layout failure diagnosis [pre5-contracts]
- `c06294e581e7c2e0a1721a637bc69f3924d10bcb` fix(pre5): retain failed deletion journals until original lease recovery completes [pre5-contracts]
- `f91865d24ae03b4bb2d7d899258f7611e4b5c7de` test(pre5): complete historical metadata anchors and worker lifecycle fixtures [pre5-contracts]
- `969e591d7fec551a5e399a1992ff1e89f48fbcab` fix(pre5): reject reserved deletion selections before creating write intent [pre5-contracts]
- `5ffa9175f737a1781e399d47988eca3cb6dfcc1f` test(pre5): bind metadata reentry to thread and verify SQL and B01 fences [pre5-contracts]
- `683645462c1dcc3ed2727b6111f11751c2bd916f` fix(pre5): qualify retained restore leases before independent trash admission [pre5-contracts]
- `efd1dbdfe7fb48b7337d04a47563def13cc652f8` fix(pre5): qualify original sort journals before scoped rollback [pre5-contracts]
- `bd168d53c1b0431bcdac5fd6e8606aacbb18fed1` fix(pre5): reject competing metadata writers before durable F14 admission [pre5-contracts]
- `4682b22a3377b57fdc24355ee20fdce11366c41e` fix(pre5): complete only fully verified restore conflict isolation [pre5-contracts]


Nächste verbindliche Schritte: zunächst beide laufenden gezielten Ergebnisse einschließlich vollständiger XML-/Childlogs kryptografisch sichern und alle roten Fälle bewerten. Den noch offenen Vier-Ordner-Setupfall nicht allein auf eine neue Erwartung umstellen. Erst nach abgearbeiteten Zielgruppen die vollständigen147 und15 sowie BA-02/B01 auf festem Commit; danach volle acht Partitionen, Frontend/Browser und Supervisor-Container. Native TrueNAS-, SD-/USB- und echte DNG1.7-Abnahme nicht durchgeführt. Veröffentlichung weiterhin gesperrt.

## 01.11.2026 – aktuelle Fortsetzung: neun Originalfehler bestanden

- Ausgangslauf 41261700576 auf e9061f41 vollständig ausgewertet: 115/124 PASS, neun FAIL, kein ERROR/SKIP. Artefakt13066567306 SHA256 35192296609f1f83c5f99e887b3ccef2ecd82efef9412b9e885a8bd38bdccb8f. Der ältere Lauf41261174452 ist abgeschlossen (90 PASS/13 FAIL), kein aktiver Lauf mehr.
- a554f3190c385c1245ff6fa0c9fdb92a687b653c: sieben belegte Config-Fixtures korrigiert, Restore-Konflikt vor Bestandsabgleich über originale Domain-Recovery qualifiziert, Vier-Ordner-Test mit realem Bootstrap und zwei Starts abgesichert. Produktiv-Konfiguration wird weiterhin niemals stillschweigend ersetzt.
- Linux41298781380 SUCCESS: exakt neun Originalfälle PASS, keine FAIL/ERROR/SKIP. Artefakt13080103179 SHA256 74d81033faef54571be199dd602d55bce2443f735a415c1f22518b82db252be1.
- d09550b9a9cc5291789e3f6e150737abf564a9a3: General-Fixture bindet Registry vor der originalen Crash-Operation und prüft deren originalen F14-Abschluss. 15 zusätzliche negative/positive Config-, Restore- und Read-only-Verträge. Lauf41299144678 prüft diesen Stand mit bisheriger124er-Nachbargruppe; Ergebnis noch auszuwerten.
- Uncommittierter nächster Schritt: originale finished-Receipts vor dem Admission-Fence unter vollständigem Workspace-Ausschluss prüfen und crashfest archivieren; acht Gegenproben einschließlich SQL-Status ohne Proof und noch vorhandenem Backup-Journal. Noch KEIN Linuxnachweis für diese Änderung.
- Kumulierte individuelle Nachweise aus verschiedenen Commits: 221/240 PASS,19 offen; dies ist KEINE Gesamt-Abnahme. Ursprüngliche58:39 inzwischen gezielt PASS,19 noch frisch zu prüfen.
- Nächster Schritt: Ergebnis41299144678 auswerten; dann eng begrenzten Receipt-Fix sowie exakte58 Originalnodes prüfen. Keine Veröffentlichung. BACKEND NOT ACCEPTED.

## 01.11.2026 – Nine-Gate und Nachbarn unabhängig grün; Original58 erneut geprüft

- a554f319:9/9 PASS, Run41298781380, Artefakt13080103179 SHA256 `74d81033faef54571be199dd602d55bce2443f735a415c1f22518b82db252be1`.
- d09550b9:139/139 PASS, Run41299144678, Artefakt13081018854 SHA256 `96fda1bf4e42be129d3ef9f859ff5ad42ff82f280ec60e2b93ebdf1aa568c39b`. Enthält komplette BA-02/B01 und7+8 SQLite-Verträge.
- 077ded86:49/66 PASS,17 FAIL,0 ERROR/SKIP; Run41300378200. Original58:41 PASS/17 FAIL; neue8 Finished-Receipt-Fälle vollständig PASS. Artefakt13082250797 SHA256 `1e30759c9888b42d6dc0958931dcfe15293fd84c68c15376d0b8da0a4d9fd757`.
- Alle genannten ZIPs unabhängig heruntergeladen/gehasht, eindeutige JUnit-Nodes und komplette rote Childlogs ausgewertet.
- bcf729e1 /41301247703 läuft mit frühen Import-/SD-/Sperr-Korrekturen. Neuer kumulierter QA-Stand fb2412c0 bereits eingereiht; Ergebnis noch nicht nachgewiesen.
- Neue Library-Recovery ausschließlich mit vor dem Austausch erhobener Originalnonce-/Inodeautorität. Keine nachträgliche Zertifizierung historischer unbekannter Kopien.
- Nachgewiesener neuer Restore-Orphan nach erfolgreichem Vorgänger-Replay durch Auswahlpreflight vor F14 behoben; Executorprüfungen bleiben. Neue Fälle PENDING.
- Die17 jüngsten roten Fälle sind im JSON einzeln dokumentiert; implementiert/ungetestet bleibt getrennt von tatsächlich bestanden.
- Bekannte unimplementierte Restursachen: Multiple-/Reintegration-Originalreplay und unregistrierter Low-Level-Cancel/Retry mit unbekanntem Callback. Keine generische Freigabe.
- Vollständige147er-/8-Partitions-/Frontend-/Containerabnahme auf finalem Source noch ausstehend. **BACKEND NOT ACCEPTED.**
- Vollständig reproduzierbare aktuelle Fortsetzungsanleitung steht am Anfang der FORTSETZUNG.md.

### Aktuelle58 Einzelresultate auf077ded86 (Run41300378200)

| Originalnode | Linuxresultat | Aktueller Umsetzungsnachweis |
|---|---|---|
| `tests/backend/test_0561_audit_regressions.py::test_P202b_F1_journal_write_error_must_leave_recovery_evidence` | PASS | Quellstand 077ded86 |
| `tests/backend/test_0561_recovery.py::test_startup_recovers_general_swap_before_onboarding_worker` | PASS | Quellstand 077ded86 |
| `tests/backend/test_0562_process_recovery.py::test_0562_metadata_preparation_keeps_unknown_file` | FAIL | PENDING_41301247703 |
| `tests/backend/test_0562_process_recovery.py::test_multilibrary_projection_sigkill[multi.source_family1]` | FAIL | PENDING_41301247703 |
| `tests/backend/test_0562_process_recovery.py::test_other_metadata_modes_sigkill[library_metadata]` | FAIL | PENDING |
| `tests/backend/test_0562_process_recovery.py::test_other_metadata_modes_sigkill[multiple_metadata]` | FAIL | Quellstand 077ded86 |
| `tests/backend/test_0562_process_recovery.py::test_other_metadata_modes_sigkill[reintegrate]` | FAIL | Quellstand 077ded86 |
| `tests/backend/test_0562_process_recovery.py::test_recovery_keeps_foreign_bytes_after_sigkill[metadata-meta.swap]` | FAIL | PENDING_41301247703 |
| `tests/backend/test_0562_process_recovery.py::test_recovery_keeps_foreign_bytes_after_sigkill[trash-trash.db1]` | FAIL | PENDING_41301247703 |
| `tests/backend/test_0562_process_recovery.py::test_sd_import_sigkill[import.before_copy]` | FAIL | PENDING_41301247703 |
| `tests/backend/test_0562_process_recovery.py::test_sd_import_sigkill[import.copy_chunk]` | FAIL | PENDING_41301247703 |
| `tests/backend/test_0562_process_recovery.py::test_sd_import_sigkill[import.copy_verify]` | FAIL | PENDING_41301247703 |
| `tests/backend/test_0562_process_recovery.py::test_sd_import_sigkill[import.hash_chunk]` | FAIL | PENDING_41301247703 |
| `tests/backend/test_0562_process_recovery.py::test_sort_reconcile_sigkill[reconcile-reconcile.before_db]` | PASS | Quellstand 077ded86 |
| `tests/backend/test_0562_process_recovery.py::test_sort_reconcile_sigkill[reconcile-reconcile.db]` | PASS | Quellstand 077ded86 |
| `tests/backend/test_0562_process_recovery.py::test_sort_reconcile_sigkill[reconcile-reconcile.move1]` | PASS | Quellstand 077ded86 |
| `tests/backend/test_0562_process_recovery.py::test_sort_reconcile_sigkill[reconcile-reconcile.move2]` | PASS | Quellstand 077ded86 |
| `tests/backend/test_0562_process_recovery.py::test_sort_reconcile_sigkill[sort-sort.before_db]` | PASS | Quellstand 077ded86 |
| `tests/backend/test_0562_process_recovery.py::test_sort_reconcile_sigkill[sort-sort.move1]` | PASS | Quellstand 077ded86 |
| `tests/backend/test_0562_process_recovery.py::test_sort_reconcile_sigkill[sort-sort.move2]` | PASS | Quellstand 077ded86 |
| `tests/backend/test_0562_process_recovery.py::test_sort_recovery_sigkill[reconcile-reconcile.move2]` | PASS | Quellstand 077ded86 |
| `tests/backend/test_0562_process_recovery.py::test_sort_recovery_sigkill[sort-sort.move2]` | PASS | Quellstand 077ded86 |
| `tests/backend/test_0562_recovery_guards.py::test_startup_recovers_registered_databases_only[False]` | PASS | Quellstand 077ded86 |
| `tests/backend/test_0562_recovery_guards.py::test_startup_recovers_registered_databases_only[True]` | PASS | Quellstand 077ded86 |
| `tests/backend/test_f11_trash_reservation.py::test_f11_legacy_delete_reservation_conflict_preserves_evidence` | FAIL | PENDING_41301247703 |
| `tests/backend/test_f11_trash_reservation.py::test_f11_original_boundary_and_restore` | FAIL | PENDING |
| `tests/backend/test_f14_backup_completion.py::test_f14_backup_rollback_receipt_survives_real_sigkill[before-receipt]` | PASS | Quellstand 077ded86 |
| `tests/backend/test_f14_backup_completion.py::test_f14_backup_rollback_receipt_survives_real_sigkill[journal-removed]` | PASS | Quellstand 077ded86 |
| `tests/backend/test_f14_backup_completion.py::test_f14_backup_rollback_receipt_survives_real_sigkill[receipt]` | PASS | Quellstand 077ded86 |
| `tests/backend/test_f14_continuation.py::test_f14_finished_receipt_survives_repeated_sigkill` | PASS | Quellstand 077ded86 |
| `tests/backend/test_f14_fixed_storage.py::test_f14_four_empty_directories_are_not_a_startup_mount_certificate` | PASS | Quellstand 077ded86 |
| `tests/backend/test_f14_fixed_storage.py::test_f14_metadata_recovery_existing_assertions_with_complete_storage_fixture` | PASS | Quellstand 077ded86 |
| `tests/backend/test_f14_runtime.py::test_f14_real_worker_rejects_rename_then_allows_completion[reconcile-reconcile.move1]` | PASS | Quellstand 077ded86 |
| `tests/backend/test_metadata_consistency_f15_f17_f18.py::test_metadata_safety_contract[f15_active]` | PASS | Quellstand 077ded86 |
| `tests/backend/test_metadata_consistency_f15_f17_f18.py::test_metadata_safety_contract[f15_pending]` | PASS | Quellstand 077ded86 |
| `tests/backend/test_metadata_consistency_f15_f17_f18.py::test_metadata_safety_contract[f17_current]` | PASS | Quellstand 077ded86 |
| `tests/backend/test_metadata_consistency_f15_f17_f18.py::test_metadata_safety_contract[f18_false]` | PASS | Quellstand 077ded86 |
| `tests/backend/test_metadata_consistency_f15_f17_f18.py::test_metadata_safety_contract[f18_true]` | PASS | Quellstand 077ded86 |
| `tests/backend/test_r1_restore_recovery.py::test_r1_collision_and_three_full_starts[different]` | PASS | Quellstand 077ded86 |
| `tests/backend/test_r1_restore_recovery.py::test_r1_collision_and_three_full_starts[directory]` | PASS | Quellstand 077ded86 |
| `tests/backend/test_r1_restore_recovery.py::test_r1_collision_and_three_full_starts[hardlink]` | PASS | Quellstand 077ded86 |
| `tests/backend/test_r1_restore_recovery.py::test_r1_collision_and_three_full_starts[same]` | PASS | Quellstand 077ded86 |
| `tests/backend/test_r1_restore_recovery.py::test_r1_collision_and_three_full_starts[symlink]` | PASS | Quellstand 077ded86 |
| `tests/backend/test_r1_restore_recovery.py::test_r1_identical_foreign_target_excluded_from_reconcile` | PASS | Quellstand 077ded86 |
| `tests/backend/test_r1_restore_recovery.py::test_r1_independent_file_remains_usable[delete]` | PASS | Quellstand 077ded86 |
| `tests/backend/test_r1_restore_recovery.py::test_r1_independent_file_remains_usable[restore]` | PASS | Quellstand 077ded86 |
| `tests/backend/test_r1_restore_recovery.py::test_r1_independent_library_and_provenance` | PASS | Quellstand 077ded86 |
| `tests/backend/test_r1_restore_recovery.py::test_r1_parallel_operation_boundary[restore_B]` | PASS | Quellstand 077ded86 |
| `tests/backend/test_r1_restore_recovery.py::test_r1_two_restore_processes_after_owner_sigkill` | FAIL | PENDING |
| `tests/backend/test_r1_restore_recovery.py::test_r1_unsafe_invariant_blocks_global_start[new_library_origin]` | FAIL | PENDING |
| `tests/backend/test_rc1_sd_reimport.py::test_cancelled_import_can_retry_without_source_loss` | FAIL | Quellstand 077ded86 |
| `tests/backend/test_rc4_acceptance_regressions.py::test_inactive_reservation_only_blocks_its_own_selection[direct-failed]` | PASS | Quellstand 077ded86 |
| `tests/backend/test_rc4_acceptance_regressions.py::test_inactive_reservation_only_blocks_its_own_selection[direct-interrupted]` | PASS | Quellstand 077ded86 |
| `tests/backend/test_rc4_acceptance_regressions.py::test_inactive_reservation_only_blocks_its_own_selection[direct-missing-job]` | PASS | Quellstand 077ded86 |
| `tests/backend/test_rc4_acceptance_regressions.py::test_inactive_reservation_only_blocks_its_own_selection[http-failed]` | PASS | Quellstand 077ded86 |
| `tests/backend/test_rc4_acceptance_regressions.py::test_inactive_reservation_only_blocks_its_own_selection[http-interrupted]` | PASS | Quellstand 077ded86 |
| `tests/backend/test_rc4_acceptance_regressions.py::test_inactive_reservation_only_blocks_its_own_selection[http-missing-job]` | PASS | Quellstand 077ded86 |
| `tests/backend/test_rc6_handoff.py::test_two_real_process_checks_sigkill_and_three_restarts[True]` | FAIL | PENDING_41301247703 |

## 01.11.2026 – Nachlauf41301247703 vollständig ausgewertet

Source `bcf729e163665772a5ccfb79448bf8820011336d`: **74 PASS /15 FAIL /0 ERROR/SKIP von89**. Artefakt13081824373 SHA256 `dde02d89ec8c5899b57e0d3fe47f55f6eb0bb127e0f09373d81b91a31fe1d0bd`, unabhängig heruntergeladen/verifiziert. Alle15 exakten kritischen Originalnodes PASS; vollständige BA-02(11), B01(10), Statement-Authorization(7), SQLite-Authorization(8), F14-Backup-Abschluss(4), neue8 Finished-Receipt- und5 SD-Gegenproben PASS. Vier frühere Prozess-Exit-Negativfälle bestehen mit tatsächlicher SQL/F14-Schreibablehnung.

Die15 roten Fälle enthalten12 alte Nodes und3 neue Import-Statusfälle. Quelle des neuen Produktfehlers: `root_operations._identity` akzeptiert ausschließlich Verzeichnisse, wurde aber für die SQLite-Datei verwendet. `5025a5ba` ersetzt dies durch eine eigenständige reguläre Datei-/O_NOFOLLOW-/nlink1-/Inode-Qualifikation mit erneutem Check vor SQL-Commit; fünf zusätzliche Dateityp-Gegenproben. Noch kein Linux-PASS für diesen Fix.

`40f7bba8` bindet den prospektiven Library-Swap-Proof zusätzlich an DB-Inode und interne Bibliotheksidentität. Identische fremde Ersatzinodes und ein ersetzter Katalog können nicht nachträglich als eigener Bestand übernommen werden. Zwei zusätzliche negative Fälle. Alle neuen Library-Fälle bleiben bis zu ihren Linuxartefakten PENDING. Historische Library-Zustände ohne vorher vorhandenen Ownershipbeleg bleiben ausdrücklich geschützt.

Kumulierte Einzelwerte der ursprünglichen240:228 PASS/12 FAIL; ursprüngliche58:46 PASS/12 FAIL, über verschiedene Commits. KEINE finale Abnahme.41303055310 auf fb2412c0 läuft bereits; keine Vollmatrix/Veröffentlichung.

## Gesicherter Fortsetzungsstand / gezielte Nachläufe

Aktueller QA-Source `7045766e1a94d4b053c1867dbd613cb8177176c9`, letzter Anwendungscode `4e0e35527d95e58fafd77f13fc209105396c40fe`. Zusätzliche native Library-Autorität verlangt den tatsächlich gehaltenen PID-/Thread-Schreibkontext; kopierte Kontexte liefern keine Autorität. Alle Änderungen sind auf dem Entwicklungsbranch gesichert.

Zuerst41303055310 (fb2412c0; zuletzt RUNNING), danach41303789143 (7045766e; zuletzt PENDING) auswerten. Der zweite prüft den korrigierten DB-Dateihelfer und neue prospektive Library-/DB-/Inode-Grenzen samt F15/F17/F18. Keine weiteren Läufe anstoßen, solange diese ausstehen. Noch keine vollständige Backend-/Browser-/Containerabnahme auf finalem Anwendungscode. **BACKEND NOT ACCEPTED – Veröffentlichung gesperrt.**
