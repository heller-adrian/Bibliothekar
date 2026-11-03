# 03.11.2026 – TrueNAS-Abnahme Pre.5 bearbeitet, Pre.6-Entwicklungsbranch

Branch `codex/pre6-truenas-acceptance`, Basis veröffentlichtes Pre.5/b4c3a397843567bfe09b35e82c51d0009d0a71bf. Anwendungscode `d64bfba83af80bfe79dfce80ccfc017cf49aad12`; erfolgreicher vollständiger gezielter QA-Commit `bc997133254ff60ec6151c9023f8e6d5dbde6c32`, Lauf41564118139 SUCCESS.98 ursprüngliche/gezielte Backendtests PASS (gepinnt aus41562234548 mit verifizierter Quellgleichheit),13 Offline- und8 Live-Browserfälle, sechs reale Supervisor-/Recovery-/Archivsicherheitsprüfbereiche PASS. Artefakt13197748512 SHA256aaac1c8b9ca0fce75553514929b8260e60b7fe83dd558bf192b468c2e10cafcc unabhängig heruntergeladen und ausgewertet.

Alle Unterlagen und sieben Bilder gelesen.16 falsche Dateizuordnungswarnungen bei angewendeter No-Event-Erweiterung vor Patch reproduziert; Original-Snapshot trennt nun physische Ablage von neuer Planung. Echte externe Moves bleiben Konflikte. Direktlink zum bestätigungspflichtigen Apply-Plan, leere abgeschlossene geplante0-Familien-Sicherungen aus Auswahl, Diagnose per Statuskarte/Fehler-Autoöffnung, Archiv-Rücksprung unten nur nach Prüfungsfehler, klare DNG-Fehler-/Zeitlabels. Kollisionen bleiben blockiert; Quellidentitäten ergänzt. Vollständiger Bericht und Bildmatrix: docs/pre6/REPORT.md; maschinenlesbare Nachweise LINUX-EVIDENCE.json. Privilegienfrage ausschließlich analysiert: PRIVILEGES-DECISION.md; Compose/Helper unverändert.

Keine Veröffentlichung beauftragt. Keine Tags/Releases/GHCR/main/NAS verändert. Reale vier Kollisionsdateien und16 vollständige NAS-Zeilen weiterhin nicht unabhängig belegt; rein lesende Diagnose in docs/pre6/READ-ONLY-DIAGNOSIS.md. Noch ausstehend: vollständige zusätzliche No-Event-HTTP-/Containerkette mit JPEG/RAF/XMP und nativer manueller D7/E4/E6/UX-Nachtest. Keine Vollmatrix/4000-/14-iPhone-Prüfung neu behaupten. Alle vorherigen roten QA-Runs dokumentiert. Unversionierte qa/rc14.zip weiterhin nicht anfassen/committen. Aktueller Dokumentationscommit folgt diesem QA-Commit ohne Anwendungscodeänderung.

---

# Fortsetzung 02.11.2026 – vollständiger Lauf 41363591064: Original-147er grün, Container-RC14 und Backendmatrix weiter rot

**PRE.5 BLOCKED; KEINE FREIGABE, KEIN RELEASE.** Nur `codex/pre5-operation-recovery`; keine Änderung an main, Tags, Releases, GHCR/latest, TrueNAS oder Produktivdaten.

- **Neuer vollständiger GitHub-Actions-Lauf [41363591064](https://github.com/heller-adrian/Bibliothekar/actions/runs/41363591064)** auf exakt `da042bc96eb40a383c6ecae2b9ab70fe87e4b1c6`: **FAILURE**, abgeschlossen 02.11.2026 03:28:04Z. `reproductions` SUCCESS mit 15/15 Crash-Verträgen, 7/7 RC14-Negativfällen, 19/19 zuvor roten Backendnodes, 7/7 historisch erneut fokussierten Fällen, **147/147 Originalhistorie**, 62/62 Pre.5 und 82/82 weiterer fokussierter Backendprüfungen (Runnerausgaben). `frontend` SUCCESS einschließlich RC13/RC14-Browser. Das ist ein echter Fortschritt, aber keine Gesamtfreigabe.
- **Container FAILURE:** `qa/pre5/container.py` meldete einen eigenen PASS (u. a. prospektiv belegter RC14-Transfer und zwei Neustarts); auch weitere Pre.4-/manuelle-/Startup- und 4000-Familien-Schritte bestanden. Der getrennte unveränderte historische 14-iPhone-Vertrag `qa/pre/container.py` scheiterte beim echten `/api/metadata-correction/reintegrate` mit **HTTP 409 `retry_original_reservation_identity_required`** statt 200. Der Original-RC14-Intent besitzt weiterhin keinen vor dem Crash erstellten prospektiven F14-/Inode-Eigentumsbeleg. `scoped_metadata_recovery_original_prospective_proof_missing` und die originale Reservation wurden im Containerlog bestätigt. Das ist eine Sicherheitsblockade; keine nachträgliche Eigentumsbehauptung, kein F14-/SQLite-/Inode-/Root-/Journal-Bypass und keine abgeschwächte Erfolgserwartung.
- **Backend sieben von acht Partitionen tatsächlich beendet:** 0: 323/323 PASS; 1: 322 PASS / 1 FAIL; 2: 321 PASS / 2 FAIL; 3: 320 PASS / 2 FAIL; 4: 321 PASS / 1 FAIL; 5: 320 PASS / 2 FAIL; 6: 322/322 PASS. **In Summe 2249 PASS, 8 FAIL bei 2257 abgeschlossenen Testnodes, 0 ERROR/SKIP**; Partition 7 vor Abschluss **CANCELLED**, also keine vollständige Achtfachabdeckung. Exakte rote Nodes: fünf Varianten von `test_0500_library_swap_restart_is_safe_at_three_crash_boundaries` (after_backup, after_first_replacement, after_second_backup, after_db_commit, after_journal_commit), `test_0500_unauthorized_db_in_journal_is_blocked`, `test_f11_reservation_wins[direct-restore]`, `test_missing_other_registered_catalog_never_means_no_duplicates`.
- **Diagnose aus Quellcode und Runner:** Die sechs BA12-Fälle erwarten noch direkte Journal-Wiederherstellung mit `recover_metadata_swaps(...,allowed_databases={db})`; der registrierte F14-Bestand verweigert diesen nicht als ursprüngliche Reservation qualifizierten Weg mit `not authorized`. Eine bloße Liste erlaubter SQLite-Dateien ersetzt den ursprünglichen F14-/Inode-Nachweis nicht. Der F11-Fall endet beim echten Neustartkind mit Child-`returncode=1`, dessen genauer Child-Fehler ohne vollständiges Childlog noch offen ist. Der RC5-Fall trifft nach Entfernen der zweiten registrierten SQLite bereits die frühere sichere Sperre `catalog_unavailable: second.sqlite3` in `root_operations.py`; prüfen, wie die originale Negativbehauptung (kein doppelter Import, keine Dateiveränderung) bei diesem früheren Block vollständig nachgewiesen wird, ohne die Schutzgrenze zu lockern. Noch **keine** sichere Produkt-/Fixture-Reparatur für diese acht Fälle nachgewiesen.
- **CI-Evidenzproblem:** `backend` hat `timeout-minutes: 150`, während die acht Partitionen sequentiell laufen (bereits sieben benötigen fast die ganze Frist). Partition 7 wurde durch Jobabbruch gestoppt. Danach scheiterte der Artefakt-Upload erneut an veränderlicher Scratchdatei `.../library.sqlite3-shm` (ENOENT). Vor der nächsten Vollmatrix Backend-Zeitbudget angemessen erhöhen und nur abgeschlossene/stabile JUnit-, Partitionmanifest-, Zusammenfassungs- und Childlog-Kopien hochladen; niemals fehlende Tests oder Artefakte als PASS auslegen.
- **Artefakte auf Source `da042bc9`:** `pre5-reproductions-1` ID 13108736213, GitHub-API/Upload-SHA256 `e63dca9cb307d48bef4caba98a7b10053bb1f9c9d8a9e49cc86461d81d0fee2b`; `pre5-container-1` ID 13108747735, `94a8ec3fd86c4e43486e6e09c38dab886b27d2b4bb8a57cf0bf096864d1d2f03`; `pre5-full-frontend-1` ID 13114371602, `8923c9e77123af5a85f294fac44147f140713852977b3d85733d7d1580dfdeec`. API-Digests mit Runner-Uploadprotokollen abgeglichen. **Kein Backend-ZIP**. Unabhängige ZIP-Hashes, JUnit-XML-Einzeldateien und vollständige Childlogs konnten wegen ClientError der lokalen Datei-/Containerlaufzeit nicht geprüft werden; GitHub-Runnerangaben sind nicht als unabhängige Prüfung auszugeben.
- **Fortsetzung:** Zuerst die acht roten Nodes gegen tatsächliche F14-Reservationen, ursprüngliche Journale und registrierte Root-/SQLite-Bindungen isoliert auf Linux prüfen. Für BA12 keine pauschale Freigabe direkter Recovery, sondern original autorisierte Domain-Recovery oder nachweislich korrekte Fixture-Initialisierung untersuchen. F11-Childlog sichern, RC5-Frühblock und unveränderte Medien prüfen. RC14-Historienvertrag bleibt bis zu einer beweisbaren, nicht rückwirkend fingierten Lösung gesperrt. Danach eng begrenzte Linux-Nachtests, anschließend neue **vollständige** `[pre5-full]`-Matrix auf einer SHA mit acht Partitionen, Container, Frontend, Medien und unabhängigen Artefakt-/JUnit-/Childlog-Prüfsummen. Kein Release ohne ausdrückliche Nutzerfreigabe.
- Dieser Eintrag dokumentiert die neue Abnahme; **keine Anwendungscode-/Fixture-/Workflowänderung und kein neuer Testlauf** in dieser Prüfung.

---

# Fortsetzung 01.11.2026 – Backendpartitionen erstmals sichtbar, aber rot; RC14-Negativprüfung grün

**PRE.5 BLOCKED; KEINE FREIGABE, KEIN RELEASE.** Ausschließlich `codex/pre5-operation-recovery`. Keine Änderung an main, Tags, Releases, GHCR/latest, TrueNAS oder Produktivdaten.

- Der ursprüngliche vollständige Lauf **41324273937** auf `537c735030be53a92ab6868d4d8f97f61b736368` bleibt FAILURE: 15/15 Crash-Verträge, 147/147 Originalhistorie, weitere Reproduktionsgruppen und Frontend/Browser PASS; RC14→Pre.5-Container-Reintegration HTTP 409 `retry_has_unresolved_reservations`; acht Backendpartitionen in diesem Lauf SKIPPED. Das ist keine Abnahme.
- Nach CI-Entkopplung lief **41331175415** auf `16e94fec65ba4b8550d466e1af4e38a56a9a0574`: `reproductions` SUCCESS mit **62/62** und **82/82** laut Runner. Die Backendpartitionen wurden tatsächlich begonnen: Partitionen **0–6** lieferten jeweils vollständige 323/322 Testresultate, insgesamt **2236 PASS / 19 FAIL / 0 ERROR / 0 SKIP** bei **2255** ausgeführten Nodes. Partition **7** wurde vor Abschluss abgebrochen; der Backendjob ist **CANCELLED**, also ausdrücklich **keine achtfache vollständige Abnahme**. Die rote Gruppe umfasst vor allem `scoped_metadata_recovery_registered_owner_missing` bei Reintegration, `NoneType`-Pfadfehler bei Multiple-Metadaten, daneben F14-Worker-/RC6-Neustart- und Papierkorb-Control-State-Fälle. Die Einzelfehler stammen aus den originalen Runner-Logs, nicht aus vermuteten Testerwartungen.
- Die Backend-Artefaktsicherung dieses Laufs ist **selbst fehlgeschlagen**: `upload-artifact` meldete `ENOENT` für eine inzwischen verschwundene Testdatei unter `scratch/pytest/.../Papierkorb/B.JPG`. Dadurch liegt für den Backendjob **kein vollständiges ZIP/JUnit-Archiv** vor. Ursache der einzelnen roten Tests und der veränderlichen Upload-Quelle müssen getrennt, ohne Umgehung von Schutzmechanismen, aufgeklärt werden. Kein PASS aus unvollständiger Abdeckung ableiten.
- Neuer gezielter Sicherheitslauf **41331460438** auf `fb0e328df0d17b7c92c0d4cc9958afb69f0449df`: `reproductions` SUCCESS, **15/15** ursprüngliche Recovery-Verträge und **7/7** RC14-Intent-/abweichende-ID-Negativfälle PASS laut Runner; Frontend, Container und Backend absichtlich SKIPPED. GitHub-Artefakt `pre5-reproductions-1` ID **13098458271**, Upload- und API-SHA256 **`6d274fa620ac4fef59ef035d0fb71f5018a8fe8aa9b449ade6f24ba9db8f2cf3`**. ZIP über GitHub-Connector heruntergeladen; **unabhängiger ZIP-Hash, JUnit-Nodeabgleich und Childlogs weiterhin nicht bestätigt**, da die lokale Datei-/Python-Laufzeit mit ClientError ausfällt. Diese 22 PASS lösen den historischen RC14-Erfolgsvertrag nicht.
- Der ältere `reproductions`-Artefaktlauf **41331175415**: ID **13093297730**, API-/Upload-SHA256 **`d5262c68384fd8887f28d70836a6c7864bb94f76217dce4ff11efe8af68aa79b`**; nur die 62+82 fokussierten Ergebnisse, keine Backendvollmatrix.
- **Nächste sichere Arbeit:** Vor Produkt- oder Fixtureänderungen die tatsächlich registrierte SQLite-Bibliotheksidentität in den historischen Metadaten-Tests gegen `app.metadata_scoped_recovery.bind_prepared_swap` und `app.metadata_abort_recovery._owner` prüfen. Ein vorab fehlender Eigentumsbeleg darf weder fingiert noch durch neue F14-IDs ersetzt werden. `NoneType`-Pfad und Papierkorb-Testinitialisierung separat anhand echter Fixture-/Prozesslogs untersuchen; F14-/Inode-/Root-/SQLite-/Journal-Sperren unverändert lassen. Erst nach nachgewiesener sicherer Reparatur gezielte Linux-Tests, anschließend eine neue vollständig grüne `[pre5-full]`-Matrix auf **einer** finalen SHA einschließlich Container, Frontend und acht Partitionen. Für Backend-Artefakte nur stabile Resultate/JUnit/Childlogs sichern, nicht während des Tests veränderliche Medien-Scratchdateien. Keine Testabschwächung, keine Veröffentlichung.
- In dieser Runde **keine Produktcode-, Test-, Fixture- oder Workflowänderung**, nur dieser dokumentarische Fortsetzungseintrag. Die abgeschlossenen Läufe wurden nicht erneut ausgelöst.

---

# Fortsetzung 01.11.2026 – neuer Chat: CI-Entkopplung und vorgezogener Sicherheitsabbruch

**Pre.5 weiterhin BLOCKED; KEIN RELEASE.** Root-Verzeichnis, App-Daten, Produktiv-NAS, main, Tags und GHCR unverändert.

- Die historische Containerabnahme **41324273937** scheiterte beim RC14→Pre.5-Reintegrations-Upgrade mit HTTP 409 `retry_has_unresolved_reservations`. Die 4000-Familien-Prüfung war vorher erfolgreich. `reproductions` und `frontend` waren grün; `backend` wurde bislang wegen des Container-Fehlers übersprungen.
- Der RC14-F14-Intent besitzt nur `ids.function`, aber keinen `family_id` und keinen vor dem Crash erzeugten `metadata-scoped-ownership`-Beleg. Deshalb **nicht** die originale Reservierung löschen, nicht als abgeschlossen fingieren und nicht nachträglich Inode-Eigentumsbeweise erzeugen.
- **CI-Patch** Commit `16e94fec65ba4b8550d466e1af4e38a56a9a0574`: Backend-Abnahme hängt nur noch von `reproductions` ab, nicht mehr vom Container; neuer Tag `[pre5-backend]` für unabhängige, isolierte Backend-Prüfung. Lauf **41331175415** wurde gestartet und war beim Schreiben dieser Zeilen noch nicht abgeschlossen. Ein Container-Fail bleibt ein Workflow-Fail, wird nicht ignoriert.
- **Sicherheits-Patch** Commit `16474d93db2e79b58f4d046e1792f21c716b882e`: `operation_health._require_write` erlaubt einer qualifizierten alten Reservation nicht länger, unter diesem Retry-Kontext **eine neue, anders identifizierte F14-Reservation** anzulegen. Das verhindert, dass 14 moderne Familienoperationen vor der erst am API-Ende stattfindenden Alt-Intent-Prüfung durchgeführt werden. Legacy-Reintegrations-Funktionalität bleibt bewusst nicht freigegeben, solange der ursprüngliche Eigentumsbeleg fehlt.
- **Testintegration** Commit `fb0e328df0d17b7c92c0d4cc9958afb69f0449df`: negativer Regressionstest für die abweichende F14-ID, plus CI-Integration `tests/backend/test_pre_metadata_retry.py` im isolierten Recovery-Lauf. GitHub Actions **41331460438** ausgelöst, Ergebnis beim Eintrag noch offen.
- **WICHTIG:** Weder die rote RC14-Upgrade-Erwartung `HTTP 200` noch Sicherheitsbelege wurden weichgezeichnet. Der Legacy-Retry ist **weiter ungelöst**. Die bisherigen Änderungen verhindern einen gefährlichen partiellen Schreibversuch und ermöglichen unabhängige Backend-Evidenz; sie sind noch kein funktionaler Abschluss. Vor einer Freigabe sind eine tatsächlich beweisbare Lösung des historischen Falls, die erfolgreiche 14-JPEG-Containerabnahme und ein kompletter `[pre5-full]`-Lauf einschließlich aller Backendpartitionen erforderlich.

---

# Fortsetzung 01.11.2026 – Vollabnahme 41324273937 rot: unbelegter RC14-Metadaten-Retry bleibt F14-gesperrt

**PRE.5 NICHT FREIGEGEBEN. KEIN RELEASE.** Ausschließlich `codex/pre5-operation-recovery`; main, Tags, Releases, GHCR/latest, TrueNAS und Produktivdaten unverändert.

- **Vollabnahme [41324273937](https://github.com/heller-adrian/Bibliothekar/actions/runs/41324273937)**, exakt Source `537c735030be53a92ab6868d4d8f97f61b736368`, **FAILURE** (abgeschlossen 17:12:14Z). `reproductions` SUCCESS: 15/15 Crash-/Recovery-Tests, 147/147 historische Originaltests, weitere 62/62 und 82/82 zielgerichtete Backend-/Provenance-Tests laut Runner-JUnit-Ausgaben. `frontend` SUCCESS, reale RC13-/RC14-Browser-/Sprach-/Responsive-Prüfung ausgeführt. `container` FAILURE im letzten Teil; vorherige Container-/Supervisor-, 90-Medien- und 4000-Familien-Schritte SUCCESS. **Die 14-iPhone-RC14-Upgrade-/Metadaten-Reintegration scheiterte. `backend` (acht vollständige Partitionen) wurde deshalb SKIPPED: kein vollständiges Pre.5-Gate.** Die früheren 60er-Verträge sind durch den hier erfolgreichen Pre.5-Fokus abgedeckt, ersetzen aber keine vollständig abgeschlossene Gesamtmatrix.
- **Exakte rote Stelle:** `qa/pre/container.py`, Aufruf `/api/metadata-correction/reintegrate` nach Upgrade eines echten RC14-F14-Intents, erwartetes HTTP 200, tatsächlich **HTTP 409 `retry_has_unresolved_reservations`**. Der Kandidatenstart protokolliert `scoped_metadata_recovery_original_prospective_proof_missing`; Originalreservation `376d5170df9a486ba5d009e1a112ef18` für `app.metadata_correction.reintegrate_library_metadata_family` bleibt bestehen. Dies ist kein 4000-Familien-Fehler; dieser Schritt hatte zuvor PASS gemeldet.
- **Quellcodebefund:** `app/metadata_scoped_recovery.py::_qualify` verlangt einen vor dem ersten Rename unter dem originalen F14-Writer geschriebenen privaten `metadata-scoped-ownership-<reservation_id>.json`-Beleg mit ursprünglichem Journal, SQL-Katalogidentität und **vorher attestierten Datei-Inodes**. Das RC14-Image erzeugte den historischen Pending-Intent ohne diesen neu eingeführten prospektiven Beleg. Nachträgliches Erraten oder Ausstellen wäre keine beweiskräftige Identitätsprüfung (auch bytegleiche fremde Inodes sind möglich). Die vorhandene **Schreibsperre ist daher korrekt fail-closed**. Keine Lockerung von F14, SQLite, Datei-/Inode-, Root- oder Journalsperren; keine Fixture-Umdeutung von erwarteter erfolgreicher Reintegration zu PASS.
- **GitHub-Artefakte auf identischer SHA:** `pre5-reproductions-1` ID **13092372200**, API/Upload-SHA256 `95fed9efe0e2cb7f2e482812833ab98a27f8f03278971d44f15e83381961cfa2`; `pre5-container-1` ID **13092464632**, `c6000804d7c0e95a927a099f778c0edeab2df9a494b01e0017810b542b813575`; `pre5-full-frontend-1` ID **13092539447**, `49933ae7f7df50273a45fcafc07ff0c36f8535dafe794c16e9a93f6c2c05ddf0`. Alle drei ZIP-Downloads über GitHub-Connector angefordert; **unabhängiger ZIP-SHA256, Einzel-JUnit-Nodeabgleich und Childlog-Inhaltsprüfung nicht abgeschlossen**, da lokale Python-/Container-Dateilaufzeit mit ClientError ausfällt. Runner-Logs, Workflow-Jobs und API-Artefaktmetadaten hingegen direkt geprüft. Die genannten Digests sind GitHub-Upload-/API-Nachweise, **keine unabhängig verifizierten ZIP-Hashes**.
- **Fortsetzung:** Zuerst eine nachweisbar sichere Behandlung historischer RC14-F14-Intents klären, ohne rückwirkende Inode-/Eigentumszertifizierung. Falls für den unveränderten historischen Pending-Fall kein vor dem Crash existierender Eigentumsbeleg auffindbar ist, bleibt dieser Upgrade-Vertrag ausdrücklich **BLOCKED**; kein automatisches Retry, kein manueller Sicherheits-Bypass und keine Abschwächung der historischen Erfolgserwartung. Erst nach sicher belegter Lösung eng begrenzten isolierten Linux-Container-Nachtest und dann neuen `[pre5-full]`-Gesamtlauf auf einer finalen SHA auslösen, inklusive aller acht Backendpartitionen. Unabhängige ZIP-/JUnit-/Childlog-Prüfung nachholen. Kein Release ohne alle grünen Gates und ausdrückliche Nutzerfreigabe.
- In dieser Prüfung **keine Produktcode-, Fixture- oder Workflowänderung**; nur dieses `FORTSETZUNG.md`-Update. Workflow `paths-ignore` für `FORTSETZUNG.md`, daher kein neuer QA-Lauf.

---

# Fortsetzung 01.11.2026 – 6/6 F14-Control-State-Fokus grün; erneute Vollabnahme ausgelöst

**PRE.5 NICHT FREIGEGEBEN.** Ausschließlich Branch `codex/pre5-operation-recovery`; keine Veröffentlichung und keine Änderungen an main, Tags, Releases, GHCR/latest, TrueNAS oder Produktivdaten.

- **Gezielter GitHub-Lauf [41324096651](https://github.com/heller-adrian/Bibliothekar/actions/runs/41324096651)** auf `7d8e31ead36d27f3e70e3e0a7b0c38185c52c6f1`: `reproductions` SUCCESS, Runner meldet **6 passed / 0 failed / 0 skipped**, Laufzeit 43.53 Sekunden. Das sechs IDs umfassende `qa/pre5/backend_fixture.json` enthält zwei originale Setup-Fälle, einen 0562-Metadaten-SIGKILL-Fall und drei F14-State-Loss-/unregistrierter-Workspace-Verträge. Container, Frontend und Backend sind in diesem fokussierten Lauf absichtlich SKIPPED und damit **nicht** abgenommen.
- **Artefakt 13090312050** (`pre5-reproductions-1`), API-Digest und Upload-Log übereinstimmend `sha256:4cf8f4ffa1fb471d25a1d6bb4502c5926378db3308332e143b87568aa3100713`. Download erfolgreich angefordert. **Unabhängiger lokaler ZIP-SHA256-Vergleich, vollständige JUnit-Node-Auswertung und einzelne Child-/Restartlogs noch nicht nachgeprüft:** Container-/Python-Laufzeit wiederholt nicht verfügbar. Dies ist eine offene **Beleggrenze**, kein behaupteter unabhängiger Audit-PASS. Vor endgültiger Freigabe zwingend nachholen.
- **Letzter Sicherheitsfix:** `app.trash_selective._operation_lock` kontrolliert vor dem Neuanlegen verlorener `state.json` unter bestehenden F14-Locks die registrierte Workspace-Zuordnung aus SQLite nur lesend. Registrierte Installation mit fehlendem Kontrollzustand bleibt blockiert; eine fremde Registrierung ist kein Besitzbeleg. Die ursprünglichen Datei-/F14-/DB-/Journal- und Inode-Sperren dürfen nicht gelockert werden.
- **Vollabnahme bereits von anderem parallelen QA-Akteur ausgelöst:** QA-only Trigger-Commit [`537c7350`](https://github.com/heller-adrian/Bibliothekar/commit/537c735030be53a92ab6868d4d8f97f61b736368) mit `[pre5-full]`, nur `qa/pre5/full_acceptance_20261101.json` verändert; Anwendungscode seit `7d8e31ea` unverändert. **Keinen zweiten Trigger-Commit erzeugen.** GitHub-Run-ID der neuen Vollmatrix ist in diesem Zugriff noch nicht bestätigt. Die Original-147er-, 15er-Recovery-, 60er-Pre.5-, acht Backendpartitions-, Frontend/Browser-, Container/Supervisor-, 90-Medien-, 4000-Familien- und 14-iPhone-Fälle müssen auf exakt dem Trigger-Quellstand anhand vollständiger XML, Childlogs, ZIP-Digests und eindeutiger Node-Abdeckung unabhängig geprüft werden.
- Fehlende Artefakte, Skips, Timeouts, unvollständige Nodeabdeckung oder rote Tests bleiben Release-Blocker. Kein automatisches Entsperren und keine abgeschwächten Testerwartungen. Dokumentation wird als `FORTSETZUNG.md`-only-Commit geführt; der Workflow ignoriert diesen Pfad, damit der bereits ausgelöste Quellstand unverändert geprüft wird.

---

# Fortsetzung 01.11.2026 – 147er-Originalgate: Runner-Timeout statt rotem Test

**PRE.5 WEITERHIN NICHT FREIGEGEBEN.** Entwicklungsbranch `codex/pre5-operation-recovery`.

- **GitHub 41310767537**, Source `098243f6`: **94/94 PASS**. Alle 58 ursprünglich roten exakten Testnodes und 36 zusätzliche Sicherheitsverträge bestanden, inklusive originaler Multiple-/Reintegration-Crash-Rollbacks und bytegleicher fremder Inodes.
- **GitHub 41314670549**, Source `e7dae42d`, [pre5-full]: 15/15 Crash-/Restore-Gate PASS, anschließend 147er Originalgate nach **2400s Subprozess-Timeout** abgebrochen, kein Final-JUnit. Archiv 13088047945, unabhängig geprüfter SHA256 `eabab11507f50be5c78b612d105fb6395ca18a1d9d540f06650659ba2599edee`. Aus originalem `stdout.log`: **116/147 bis zum Abbruch durchlaufen, keine bis dahin gemeldeten FAIL**; die restlichen 31 waren noch nicht geprüft. Dies ist ein Infrastruktur-Timeout, kein 147/147-PASS und kein nachgewiesener Anwendungsfehler.
- **QA-only Commit `0c6be7c9c77d27fa2c912f5bf32c983beb11ffe0`**: `qa/f14/linux/run_linux.py` verlängert ausschließlich bei exakt `backend_unretested.json` die Subprozessfrist von 2400 auf **5400 Sekunden**, alle anderen Modi und einzelne Testwatchdogs unverändert. `.github/workflows/qa-pre5-operation-recovery.yml`: Reproductions-Job-Timeout von 45 auf **105 Minuten** verlängert. Bei erneutem Timeout explizit unvollständiges `exit.json`, niemals PASS. Keine Anwendungscode-/Fixture-/Testerwartungsänderung.
- **Aktueller Voll-Abnahmelauf [41318676170](https://github.com/heller-adrian/Bibliothekar/actions/runs/41318676170)** auf `0c6be7c9` wurde gestartet und beim letzten Abruf ausgeführt. Währenddessen **keine erneute Workflow-/Codeänderung**. Er muss das vollständige 147er-Gate (147/147), danach die isolierten Container-/Frontend-/Browser-Verträge und alle acht disjunkten Backendpartitionen auf genau dieser SHA prüfen. Alle Artefakte/JUnit- und Node-Coverage unabhängig auswerten. Bei echtem Rot nur den belegten Fehler reparieren, niemals F14-/SQLite-/Dateieigentumsmechanismen lockern.
- Alte `docs/pre5/release/ACCEPTANCE.json` bleibt PENDING, Build SHA historisch. Kein Tag, Release, GHCR, `latest`, `main` oder TrueNAS / NAS verändern. Release erst nach vollständiger Abnahme und gesonderter Benutzerfreigabe.

---

# Fortsetzung 01.11.2026 – 94/94 fokussierte Linux-Verträge grün, vollständige PRE.5-Abnahme gestartet

**PRE.5 WEITERHIN GESPERRT. KEIN RELEASE.** Branch `codex/pre5-operation-recovery`; Anwendungscode seit `098243f642de7559a4983857affde3f1c17875c9` unverändert.

**Unabhängig geprüfter GitHub-Actions-Lauf [41310767537](https://github.com/heller-adrian/Bibliothekar/actions/runs/41310767537)** auf Source `098243f642de7559a4983857affde3f1c17875c9`: **94/94 PASS, 0 FAIL, 0 ERROR, 0 SKIP**, JUnit `backend-focus.xml` und Original `authorization/f14-qa/targets/results/result.xml` jeweils 94 eindeutige Nodes. Die **58/58 ursprünglichen IDs** aus `docs/pre5/BACKEND-REPAIR-58-20261101.json` sind per exaktem Pfad/Testnamen-Abgleich vollständig enthalten und PASS; weitere 36 eigenständige Nodes inklusive der beiden bytegleichen Fremdinode-Manipulations-Gegenproben. GitHub-Artefakt **13085628338** mit API-Digest und unabhängig berechnetem ZIP-SHA256 **`0ce6089b91259152a22b2f5126b55e9e86764a8a3422f79d31cf94a26718652d`** (identisch), 1373 Archiv-Einträge. Originale Prozess-/Restartlogs und Result-JSON geprüft: beide vormals roten SIGKILL-Metadatenfälle `multiple_metadata` und `reintegrate` haben drei saubere Starts mit `writes_allowed=true`, ohne verbliebene F14-Reservation, und erfolgreiche Original-Retry-Nachweise. Die beiden Fremdinode-Szenarien behalten über drei Starts `writes_allowed=false`, `scoped_metadata_recovery_foreign_inode_at_original_endpoint`, unveränderte Originalreservation und jeweils echte abgewiesene Datei- und SQLite-Schreibprobe. Der ursprüngliche Import-Cancel-Vertrag bleibt PASS, keine Lockerung seiner unbekannten F14-Wirkung.

**Nächster Schritt: vollständiger `[pre5-full]`-Lauf auf festgepinntem QA-Quellstand.** Die bestehende Workflowdefinition hat `paths-ignore` für `FORTSETZUNG.md` und `docs/**`; deshalb wird ausschließlich ein deklaratives, funktionsloses QA-Nachweismarkerfile `qa/pre5/full_acceptance_20261101.json` mitcommitted. Kein Anwendungscode und keine Workflowdefinition geändert. Dieser Marker-Commit startet den bestehenden Workflow mit [pre5-full]: historische 147er-Gruppe, 15er-Crash-Gate, Pre.5-Focused-/Provenance-Verträge, isolierter Container/Supervisor/90-/4000-/iPhone-Test, Frontend/Browser und acht disjunkte vollständige Backendpartitionen. **Bei FAIL ausschließlich nach tatsächlichen Logs reparieren, nie F14/SQLite/Root/Ownership/Journals lockern.** Erst nach vollständig grünen Nachweisen Acceptance/Publisher vorbereiten, aber nichts veröffentlichen ohne ausdrückliche Nutzerfreigabe.

---

# Fortschritt 01.11.2026 – 92/94 gezielte Tests, exakter F14-Replay-Eintritt repariert

**PRE.5 NICHT FREIGEGEBEN.** Working branch `codex/pre5-operation-recovery`. Alle neuen Änderungen ausschließlich im Entwicklungsbranch, nicht in `main`, Tags, GHCR, TrueNAS, NAS oder Produktivmedien.

**Unabhängig verifizierter Linux-Lauf [41307568578](https://github.com/heller-adrian/Bibliothekar/actions/runs/41307568578)** auf Source `9b8a28772f2f638557032d5962ae7d5ee658b347`:
- **92 PASS, 2 FAIL, 0 ERROR/SKIP**, alle ausgewählten 94 eindeutigen Nodes; originale Import-Retry-Negativprobe und zwei neue SIGKILL-/bytegleiche-Fremdinode-Kollisionstests **PASS**.
- Rote Originalnodes: `test_other_metadata_modes_sigkill[multiple_metadata]`, `test_other_metadata_modes_sigkill[reintegrate]`.
- Artefakt 13084941902, GitHub SHA256 `9a221c714a57fa19d581fe0d910d24fc10aa0d10fbf0d88397b715a8f5e3087d`; ZIP lokal heruntergeladen, SHA256 unabhängig gleich, Original-JUnit und drei vollständige Child-Neustartprotokolle ausgewertet.
- Beide roten Fälle sind derselbe konkrete Produktfehler: Exakter, prospektiv nachgewiesener neuer Metadaten-Recovery-Handler erreicht `ro.reserve(...,_recovery_record=original)`, dessen F14-Zulassung jedoch nur bisherige General-/Technical-/Domain-Handler kennt; `Fachliche Wiederaufnahme ist nicht für diesen Auftrag freigegeben.` Alle drei Neustarts behalten daher Original-F14-Fence und Bytes, aber Original wird nicht zurückgerollt.
- Vorläufer [41306238349](https://github.com/heller-adrian/Bibliothekar/actions/runs/41306238349) auf `f57b89bd`: 89 PASS, 3 FAIL (die beiden Metadatenfälle und der zu diesem Zeitpunkt noch nicht korrigierte unregistrierte Import-Retry).

**Gezielter Fix [098243f6](https://github.com/heller-adrian/Bibliothekar/commit/098243f642de7559a4983857affde3f1c17875c9) [pre5-contracts]**: fügt ausschließlich für die beiden erwarteten Originalfunktionen `apply_multiple_metadata_correction` und `reintegrate_library_metadata_family` einen synchronen ContextVar-Capability-Eintritt hinzu; Vergleich des unveränderten gesamten F14-Records, während `qualified_retry` genau dessen alte Reservation bindet. Die Capabilities werden `finally` zurückgesetzt. Keine anderen F14-Handler, kein generelles Freischalten von Schreiboperationen. **LINUX-NACHWEIS PENDING: Workflow 41310767537**, Source `098243f6`; bei Rot exakte JUnit-/Restartlogs auswerten, nicht Behauptungen über Recovery anpassen.

**Unmittelbar danach** (nur bei grünem 94er-Lauf): vollständige Altgruppe147, kritische15, BA-02/B01/Authorization und abschließend acht disjunkte Backendpartitionen, Frontend/Browser, isolierter Container-/Supervisor-/90-/4000-/iPhone-Nachweis auf identischem Source mit `[pre5-full]`. Bis zu sämtlichen grünen Release-Gates kein Pre.5-Publish. Publisher/ACCEPTANCE.json noch nicht aktuell.

---

# Fortsetzung 01.11.2026 – aktualisierter Reparaturstand nach den grünen 45 Fällen

**PRE.5 NICHT ABGENOMMEN. KEIN RELEASE.** Arbeitsbranch `codex/pre5-operation-recovery`.

Unabhängig geprüft: GitHub Actions **41303789143** auf `7045766e1a94d4b053c1867dbd613cb8177176c9`: **45 PASS / 0 FAIL**, ausschließlich gezielte Verträge. Artifact 13082652653, API SHA256 `c720d453004e32ed2eab88e6384b625f96f9b05574d236d9a7d71e805ec71fec`. Der vorherige größere Lauf **41303055310** auf `fb2412c0` ist **121 PASS / 11 FAIL** (acht historische und drei neue Fälle, noch vor dem regulären DB-Datei-Identitätsfix). Der neuere 45er-Nachlauf hat u.a. die vier Original-SD-Import-Crashgrenzen, den Multilibrary-Projektionsfall und drei neue Statusverträge grün qualifiziert. Dies ist keine vollständige Backendabnahme.

Auf dem Entwicklungsbranch seitdem **implementiert, NICHT Linux-verifiziert**:
- `9e6bbd4` und `1e464e9`: historischer unregistrierter Low-Level-Cancel mit beliebigem Callback darf unter neuer Job-ID die originale F14-Reservation gerade NICHT umgehen. Originalnonce, Originalbeleg, Quellbytes und echte verweigerte neue Schreiboperation werden geprüft; regulär registrierte API-Import- und Recheckwege haben eigene Positivverträge. Original-Test-ID beibehalten.
- `f59d7405`: `app/metadata_scoped_recovery.py` (neu) sowie `root_operations.py`, `metadata_swap_recovery.py` und `operation_health.py`: für exakt eine ursprünglich F14-gebundene Multiple- oder Reintegration-Precommit-Operation wird vor der ersten Umbenennung ein privater Eigentumsbeleg mit vollständigem Journal, Originalreservation, DB-Inode, Dateiinodes, Hashes und bei Reintegration originaler Dateifamilien-/SQL-Mitgliedschaft geschrieben. Ein Rollback darf nur den ursprünglichen validierten F14-Schlüssel fortsetzen. Keine generische Freigabe und keine nachträgliche Zertifizierung historisch beweisloser Fälle.
- `76c355bd`: zwei neue echte SIGKILL-/Mehrfachneustart-Gegenproben. Sie ersetzen exakt eine Original-Sicherheitskopie durch bytegleichen **fremden Inode** und verlangen drei Starts lang Original-F14-Schreibsperre, erhaltene Bytes sowie abgewiesene SQL-/Dateischreibversuche.
- `9b8a2877`: Reintegration speichert rohe `sha256_current`- und `sha256_original`-SQL-Werte und nutzt zur Bindung denselben wirksamen Fallback wie der originale Reintegrations-Executor.
Diese Änderungen sind sicherheitskritisch. **Vor bestandenem Linux-Test keinerlei Annahme über ihre Korrektheit.**

Nachprüfungen: **41306238349** (älterer HEAD `f57b89bd`, alle58 ursprünglichen Nodes) lief beim letzten Abruf noch; der auf dem aktuellen Anwendungscode wartende **41307568578** (Quellstand `9b8a2877`, positive und negative neue Fälle + ursprüngliche 58) ist das entscheidende nächste Gate. GitHub-Concurrency ersetzt ältere wartende Runs; deren `cancelled` ist kein Testergebnis. Bei Rot aus XML/Childlogs konkret beheben; insbesondere F14-Origin, physische Metadaten-Sperre, Datenbankidentität, vorab gespeicherte Proofs, fehlende Journalzustände und identische Fremdinodes prüfen. Kein Safety-Bypass.

Erst wenn diese 58 Originalfälle plus Gegenproben grün sind: ursprüngliche147er-Gruppe und15er-Crash-Verträge, vollständige BA-02/B01 und SQLite-Verträge, anschließend acht disjunkte Backendpartitionen, Frontend/Browser und isolierte Container-/Supervisor-Tests auf **derselben finalen Commit-SHA**. Danach `docs/pre5/release/ACCEPTANCE.json` und den vorbereiteten Publisher nur anhand der aktuellen Belege aktualisieren. Keinerlei Main-/Tag-/GHCR-/latest-/TrueNAS-/Produktivänderung vor vollständiger Abnahme und expliziter Freigabe.

---

# Aktueller Fortsetzungsstand – 01.11.2026, neue gezielte Backend-Reparatur

**PRE.5 NOCH NICHT ABNAHMEFÄHIG – VERÖFFENTLICHUNG GESPERRT.**
Branch `codex/pre5-operation-recovery`. Neuer enger QA-Stand `7045766e1a94d4b053c1867dbd613cb8177176c9`; vorheriger58er-/Nachbarstand `fb2412c03be2dc5f88dd715695ad8b98206618a0`.
Letzter Anwendungscode-Commit `4e0e35527d95e58fafd77f13fc209105396c40fe` (enthält `5025a5ba`, `40f7bba8` sowie Bindung an echten PID/Thread der physischen Metadatensperre).
Nachfolgende Dokumentationscommits ändern keinen Anwendungscode.
Keine Tags/Releases/GHCR/latest/main/TrueNAS geändert. Untracked `qa/rc14.zip` niemals stagen.

## Unmittelbarer nächster Schritt

1. Lauf **41301247703** auf `bcf729e163665772a5ccfb79448bf8820011336d` ist FAILURE und bereits vollständig ausgewertet:74 PASS/15 FAIL/0 ERROR/SKIP von89.
   Alle15 kritischen Originalnodes,8 Finish-Proofs,5 SD-Gegenproben,7+8 Authorization,10 B01,11 BA-02,4 Backup-Abschlüsse PASS.
   Von15 FAIL sind12 historische Originalfälle und3 neue Import-Statusfälle. Gemeinsamer nachgewiesener Produktfehler: directory-only `ro._identity` für reguläre SQLite-Datei; in5025a5ba korrigiert, noch PENDING.
   Artefakt13081824373 SHA256 `dde02d89ec8c5899b57e0d3fe47f55f6eb0bb127e0f09373d81b91a31fe1d0bd`.
2. ZUERST den laufenden **41303055310** auf **fb2412c03be2dc5f88dd715695ad8b98206618a0** auswerten.
   Er enthält alle58 Original-Nodes plus neue Finish-/SD-/Import-/Library-/Restore-Gegenproben, volle BA-02/B01 und beide Authorization-Dateien.
   Nicht durch einen neuen Push ersetzen, solange er PENDING ist. Keine parallele Vollmatrix.
3. Danach **41303789143** auf **7045766e1a94d4b053c1867dbd613cb8177176c9**, zuletzt PENDING hinter41303055310. Er prüft den korrigierten regulären DB-Dateihelfer, fünf echte frühe SIGKILL-Nodes, Original-Library-Rollback, die aktuellen17 Library-/Ownership-Fälle und volle F15/F17/F18.
   Artefakt jeweils einmal herunterladen, API-SHA256 prüfen, XML/alle roten Child-/Restart-Logs unabhängig lesen.
4. Erst nach sicheren gezielten Reparaturen alle58, dann147, dann vollständige Matrix auf fester SHA starten.

## In dieser Runde unabhängig verifizierte Linuxnachweise

- **41261700576** / e9061f41:115 PASS /9 FAIL /0 ERROR/SKIP. Artefakt13066567306,
  SHA256 `35192296609f1f83c5f99e887b3ccef2ecd82efef9412b9e885a8bd38bdccb8f`.
- **41298781380** / a554f319:9/9 ursprüngliche aktuelle Fehler PASS,0 FAIL/ERROR/SKIP. Artefakt13080103179,
  SHA256 `74d81033faef54571be199dd602d55bce2443f735a415c1f22518b82db252be1`.
- **41299144678** / d09550b9:139/139 PASS,0 FAIL/ERROR/SKIP. Artefakt13081018854,
  SHA256 `96fda1bf4e42be129d3ef9f859ff5ad42ff82f280ec60e2b93ebdf1aa568c39b`.
  Enthält ursprüngliche124 Nachbarn und15 neue Config-/Anker-/Restore-/Read-only-Verträge.
  Darin7 Statement-Authorization,8 SQLite-Authorization,10 B01,11 BA-02 und4 F14-Backup-Abschlussfälle PASS.
  Stärkerer General-Test prüft die ursprüngliche Kontrollautorität/Nonce; Registry existiert vor dem ursprünglichen Crash.
- **41300378200** / 077ded86:49 PASS /17 FAIL /0 ERROR/SKIP von66.
  Exakte58 Originalfehler:41 PASS /17 FAIL. Alle8 neuen Finished-Receipt-Gegenproben PASS,
  einschließlich fehlender/falscher Proofs, geänderter Generation/Bindings, SQL-Endstatus ohne Receipt und noch vorhandenem Backup-Journal.
  Auch ursprünglicher Finished-Receipt-SIGKILL-Fall und F14-Runtime-Reconcile jetzt PASS.
  Artefakt13082250797, SHA256 `1e30759c9888b42d6dc0958931dcfe15293fd84c68c15376d0b8da0a4d9fd757`.
- Kumulierte letzte Einzelwerte der ursprünglichen240 Nodes:228 PASS /12 FAIL über verschiedene Commits. Original58 nun kumuliert46 PASS/12 FAIL.
  KEINE finale Gesamtabnahme. Alle ZIPs/XML/Childlogs unter `/private/tmp/bibliothekar-pre5-evidence/<RUN>-targets*`.

## Änderungen und Beweisgrenzen

- a554f319/d09550b9: sieben nachgewiesene Config-/Namespace-Fixtures korrekt vor ursprünglicher Operation bereitstellen;
  fehlende echte Konfiguration bleibt gesperrt. Vier-Ordner-Erwartung mit echtem Bootstrap/zwei Starts und negativen Root-Gegenproben abgesichert.
  Restore-Konflikt unter derselben physischen Sperre vor Inventory-Zulassung durch Original-Replay qualifizieren; Journal und fremdes Ziel bleiben erhalten.
- 077ded86/fd6bdcd8: dauerhaft vorhandenen originalen Finished-Receipt vor Mutationszulassung prüfen,
  Originalnonce/Generation/Bindings und Typed-Receipt unter exklusivem Workspace-Lock; Originalproof plus permanentes Receipt erhalten.
  Später zusätzliche Mount-/Anker-Revalidierung. Kein SQL-Status-/Journal-Abwesenheitsabschluss.
- fc459bc9: nur nachgewiesene abgestürzte **read-only SD-Checks** vor erneuter Rootvalidierung neben lebendem Check qualifizieren;
  normale Importe, falsche Quellen/Generationen/SQL-Handoffs bleiben gesperrt. Linuxnachweis in41301247703: SD-Check und5 Gegenproben PASS.
- 0aeccead: frühe Folder-Import-Abbrüche ohne Move-Journal ausschließlich im historischen SQL-Status dokumentieren.
  Private Originalnonce-/DB-Identitäts-Statusreceipt und Audit; keine Dateiänderung, kein F14-Abschluss, keine Retry-Freigabe.
  Originale Teilkopien/Quellen/Claims bleiben erhalten.41301247703 zeigt den Fehler im dafür neu verwendeten Datei-Identitätshelfer; in5025a5ba durch O_NOFOLLOW-Regular-File-/nlink1-/Inode-Prüfung ersetzt. Positive/negative Wiederholung ausstehend.
- fd6bdcd8: vier alte Negativtests verlangen jetzt sicheren lesbaren Start **plus echte abgewiesene SQLite- und F14-Schreibprobe**
  in frischem Prozess; Originalrecord/Fremdbytes bleiben unverändert. Alle vier Originalfälle in41301247703 PASS. Kein bloßer HTTP-/Exitcode-Tausch.
- 43d240e1/6de941e3: genau ein pre-commit Library-Swap kann den vorhandenen Rollback unter Originalnonce ausführen,
  nur mit vor dem ersten Originalaustausch geschriebenem `metadata-swap-ownership-<journal>.json`:
  vollständiger Originalrecord, Journal, Quell-/Incoming-/Work-Inodes. Private Wiederaufnahmeplanung überlebt Journalcleanup.
  Zusätzliche Inodeprüfung innerhalb des Rückbaus vor jedem relevanten Austausch/Unlink.
  Identische fremde Ersatzinodes, Hardlinks/Symlinks, fremde Workbytes, falsche Task-/DB-/Rootbelege und fehlender alter Ownershipproof bleiben gesperrt.
  Alte Library-Zustände ohne diesen **prospektiven** Nachweis werden nicht nachträglich zertifiziert. Keine native TrueNAS-Freigabe.
  Neue15 Fälle mit echten SIGKILLs/Negativproben auf fb2412c0 PENDING. Danach zusätzliche DB-Inode-/interne Owner-Gegenproben und aktuelle17 Library-Fälle auf40f7bba8 noch zu prüfen.
- ba50824d: Test-Lifespan wartet nur bei tatsächlich zugelassenem asynchronem Trash-Import auf Terminalstatus.
  300ms allein stoppten den normalen Worker vor dessen2s-Retry am temporären Startup-Fence. Ungeklärte Vorgänge werden nicht disponiert.
  Neue externe Bibliotheks-Fixture: fremde DB vor dem Konflikt erzeugen, normale Registrierung weiterhin abweisen,
  tatsächliche externe Registry-Manipulation nur über isoliertes `external_edit` nachbilden.
- 10b1c252: aus vollständigem zweiten Prozesslog nachgewiesen: wartender Restore beendet Originalowner korrekt,
  danach fehlt A zu Recht; die neue abgewiesene Auswahl erzeugte aber einen neuen F14-Orphan.
  Jetzt vollständige neue Auswahlprüfung unter Trash-Lock vor F14; Executor wiederholt die Prüfung.
  Test prüft Originalreceipt, eindeutigen katalogbelegten Zielort/Hash, genau ein Audit je DB, drei Neustarts und KEINEN neuen Record.
  Fünf neue Negativ-/Iteratorfälle; noch PENDING.

## Noch nicht gelöste Ursachen / keine Vorwegnahme der nächsten Ergebnisse

1. `test_other_metadata_modes_sigkill[multiple_metadata]`: originaler Multiple-Swap bisher ohne eindeutig an F14 gebundenen prospektiven Mitgliedschafts-/Inodebeleg.
2. `...[reintegrate]`: alter F14-Schlüssel enthält keine family_id; bestehender Retry-Qualifier erlaubt bewusst keinen geratenen automatischen Replay.
3. `test_cancelled_import_can_retry_without_source_loss`: unregistrierter Low-Level-Aufruf mit beliebigem Metadata-Callback und database=None
   hält nach Abbruch seinen unbekannten gemeinsamen F14-Wirkungsbereich. Eine neue Job-ID ist keine Fortsetzung.
   Kein pauschales Freigeben implementiert. Tatsächlichen registrierten API-Abbruch/Review/Retry zuerst nachweisen,
   dann historischen Test begründet berichtigen oder originalen qualifizierten Staging-Abschluss ergänzen.
4. Alle aktuellen neuen Reparaturen zunächst anhand ausstehender Artefakte prüfen. Nicht voraussetzen, dass sie PASS sind. Insbesondere neue Library-Recovery und tatsächliche asynchrone Restore-Wiederaufnahme in41303055310.
5. Enger Folgelauf41303789143 auf7045766e muss den regulären DB-Dateihelfer, fünf echte frühe SIGKILL-Originale, native Library-Inode-/DB-Autorität sowie F15/F17/F18 nachweisen. Kein Vollmatrixlauf.
6. Pflichtabnahme147/147,15/15 auf FINALER SHA, acht disjunkte Backendpartitionen, Frontend/Browser, reale Supervisor-/Containerabnahme,
   90 Dateien,4000 Familien,14 iPhone-JPEGs und Archiv-Bytegleichheit auf finalem Source fehlen weiterhin.

Lokale py_compile-/AST-Importprüfung, Actionlint und diff-check PASS; dies sind KEINE Linux-Funktionstests.
Lokales Docker ist nicht vorhanden. Native TrueNAS/NFSv4, physische SD/USB, echte DNG1.7-Schreibprüfung NOT_RUN.
Keine ExifTool-Abschwächung; kein `-m`, kein DNG-Upgrade.


## Geordneter Budget-Checkpoint dieser Runde

- Letzte Limitanzeige83% des Fünfstundenfensters,78% Woche. Keine weitere größere Implementierung begonnen.
- Sämtlicher Source liegt committet/gepusht auf dem Entwicklungsbranch; Dokumentationsnachtrag enthält keine Laufzeitänderung.
-41303055310 läuft und41303789143 wartet bereits dahinter. Keine weiteren Runs starten/ersetzen, keine Polling-Schleife.
-41303055310 verwendet noch den fehlerhaften alten DB-Dateihelfer. Dessen roten Importstatusfälle sind durch5025a5ba korrigiert, aber erst41303789143 kann sie nachweisen.
- Nach neuen Ergebnissen zuerst echte Regressionen/neue Fixturefehler stabilisieren. Multiple/Reintegration und unregistrierter Callback-Cancel bleiben bekannte unimplementierte Ursachen; keine Freigabe aus fehlendem Journal/SQL-Endstatus.
- Original58 Node-IDs und Baseline-Trace-Digests exakt unverändert gegen20b56a97 geprüft; qa/f16_f20/original unverändert; qa/rc14.zip nicht versioniert.
- Lokale py_compile-/Import-AST-/Actionlint-/diff-Prüfungen PASS. KEINE macOS-Funktionsprüfung und keine Behauptung einer finalen Linux-/Container-Abnahme.

---

## Frühere chronologische Aufzeichnungen (Statusangaben darin sind historisch)

# Aktueller Fortsetzungsstand – 01.11.2026, Reparatur der letzten58 Backendfälle

**BACKEND NOT ACCEPTED. Pre.5 noch nicht abnahmefähig – Veröffentlichung gesperrt.**
Branch: `codex/pre5-operation-recovery`.
Letzter QA-/Source-Commit: `e9061f41376519a63e429440a78df8e8de5cf387`.
Letzter Anwendungscode-Commit: `c06294e581e7c2e0a1721a637bc69f3924d10bcb`.
Nachfolgender Sicherungscommit ändert ausschließlich diese QA-Dokumentation.
Keine Tags/Releases/GHCR/latest/main/TrueNAS geändert. `qa/rc14.zip` ist ein
vorbestehendes untracked Benutzerartefakt und darf nicht mitcommittet werden.

## Zuerst die bereits gestarteten Läufe auswerten

1. **41261174452** auf `5ffa9175f737a1781e399d47988eca3cb6dfcc1f` war zuletzt RUNNING.
2. **41261700576** auf `e9061f41376519a63e429440a78df8e8de5cf387` war zuletzt PENDING.
   Er enthält kumulierte Reparaturen,47 Selektoren mit ursprünglichen15
   Crash-/Manipulations-Nodes, Restore-/Sort-/Metadatenfällen, voller BA-02,
   voller B01 und SQLite-Statement-/Schema-Authorization.
   Dieser `[pre5-contracts]`-Lauf führt keine Vollmatrix/Frontend/Container aus.
   Nicht parallel weitere umfangreiche Läufe starten; keine aktive Warteschleife.
   GitHub ersetzt ältere pending Runs automatisch; cancelled Zwischenläufe sind
   KEINE Testnachweise. Falls der neueste Run noch wartet, laufenden Job beachten.

GitHub-CLI:
`GH_CONFIG_DIR=/private/tmp/bibliothekar-gh-device GH_BROWSER=true GH_DEBUG= GODEBUG=http2client=0 /private/tmp/bibliothekar-gh-cli/gh`
Direkte `api repos/heller-adrian/Bibliothekar/actions/runs/<ID>` mit
`-H 'Cache-Control: no-cache'` verwenden; ältere `gh run view`-Caches waren stale.
Token nie ausgeben. Neue Artefakte einmal laden, SHA256 gegen API-Digest prüfen,
XML und alle Child-/Restart-Logs bewerten; bereits gesicherte ZIPs nicht neu laden.

## Nachgewiesene Ergebnisse und verfügbare Belege

- Voller Original147-Check auf7838a706, Run41231600475:89 PASS /58 FAIL.
  Alle58 exakten Nodes vollständig in `docs/pre5/BACKEND-REPAIR-58-20261101.json`,
  Bericht `.md`; Originaltrace-Digests bleiben erhalten.
  Artefakt13055435531 SHA256
  `9a0b633c2e7650265419f683f1a32aba4280113118e9ced51e173b91cce23260`.
  Benutzer-ZIP250/250 Dateien bytegleich damit.
- **41260071820**, Source4682b22a: **24 PASS /0 FAIL/ERROR/SKIP**.
  Alle15 ursprünglichen kritischen Nodes plus Restore-Kollisions-/Negativfälle.
  Artefakt13064419670 SHA256
  `b40faee8dd967452de7221d03a30cc1bdf536a157db650e2bd64675d896c7ba3`.
- **41260399276**, Sourcebd168d53: **26 PASS /7 FAIL /0 ERROR/SKIP**.
  F18 false/true PASS. F15 SQL-/Projektionsablauf und F14-Ablehnungsassertionen
  bestehen; Neustart scheitert an fehlenden General/Batch-Fixture-Unterordnern.
  F17 gleicher Fixture-Grund. Zwei General-Fixtures erreichen jetzt Worker-
  Quieszenz, ihr bisheriger Fake hatte keine join-Methode. Zwei NEUE Batchtests
  erwarteten fälschlich gleiche Zeit für A/B; echte Korrektur hält1s-Abstand.
  Diese belegten Test-/Fixture-Probleme sind inf91865d2 korrigiert, noch pending.
  Artefakt13065735420 SHA256
  `8857f69740ff2017992562bc97dac56d9ae1ebe8735a851500687ff85be0ca9c`.
- Lokale Syntaxprüfung aller geänderten Pythondateien, Actionlint und
  `git diff --check` PASS. Lokale macOS-Syntax ist KEIN Linux-Funktionsnachweis.
- Quelleübergreifende letzte Einzelwerte der ursprünglichen240 roten Nodes:
  **189 PASS /51 FAIL**,0 unbekannt. Verschiedene Commits: NICHT final akzeptiert.
  Unter den Original58 sind7 gezielt PASS,27 Fix/Fixture-Korrekturen pending,
  24 noch OPEN. Die spätere Linuxauswertung muss diese Angaben aktualisieren.

Alle ZIPs/extrahierten Original- und Childlogs:
`/private/tmp/bibliothekar-pre5-evidence/41231600475-targets*`
`/private/tmp/bibliothekar-pre5-evidence/41260071820-targets*`
`/private/tmp/bibliothekar-pre5-evidence/41260399276-targets*`
Lokale `failures.json` im letzten Ordner enthält alle sieben vollständigen
Fehler; Baseline `failures-58.json` im ersten Ordner alle Originaltraces.

## Implementierte gemeinsame Reparaturen, noch nicht alle abgenommen

- 4682b22a: bestehende Restore-Konflikte erneut vollständig unter Trash-Lock
  qualifizieren; Original-F14-Abschluss/Receipt, Journal/Fehler/A-Pfade behalten.
- bd168d53: physische Metadatensperre und read-only Task-/Projektionszulassung
  vor neuer F14-Reservation; executorinterne Sicherheitsprüfungen bleiben.
- efd1dbdf: genau ein originaler camera-only Pre-Commit-Sortierlauf kann
  bestehende Rollback-Recovery unter ORIGINALnonce verwenden. Neue
  `app/sort_recovery_proof.py` prüft Registry, Bibliotheksidentität, DBschema,
  Generationen, alle Bindings, Run/Job/Event, Pfade, Hash/Größe und Endpunkte.
  Exakter run_id statt beliebiger anderer Runs; dauerhafter Originalbeleg.
  Assets, bereits committete Ergebnisse, doppelte Endpunkte, Fremdbytes,
  Hardlinks und ungebundene Wurzeln bleiben gesperrt. Sechs negative neue Fälle.
- 68364546/969e591d: Trash-Lock umfasst auch F14-Zulassung. Passender originaler
  Restore darf nur über den vollständigen Qualifier abgeschlossen werden.
  Erst danach unabhängige Auswahl zulassen; reservierte/aktive Auswahl schon
  VOR neuem Intent ablehnen. Wiederholte Prüfung nach Journalanlage bleibt.
  RC4-sechs-Fall-Ursache war ein vom ersten abgewiesenen DELETE selbst erzeugter
  F14-Record, nicht pauschal ein terminaler Restore-Job.
- 5ffa9175: reentrante Metadata-Sperre an Workspace+PID+Thread binden; kopierte
  ContextVars verleihen keinem anderen Thread die physische Sperre.
- f91865d2: General/Batch-Voraussetzungen der historischen Fixtures vor Operation,
  vollständiger Fake-Thread und korrekte1s-Batch-Erwartung. Immutable Original-
  QA-Sources/Integritätsmanifeste unterqa/f16_f20/original unverändert.
- c06294e5: Exception-Rückbau einer Trash-Löschung behält sein geprüftes Journal
  bis zum regulären Abschluss der originalen F14-Lease; verstärkter F1-Test.
- e9061f41: ungeklärter Vier-Ordner-Test gibt vollständigen inspect_storage-
  Befund aus. Noch KEINE geänderte Erwartung/pauschale Produktlockerung.

## Nächste Fehlergruppen nach tatsächlichen neuen Resultaten

Zuerst alle roten neuen Sort-/Restore-/Sperr-Gegenproben aus den zwei Läufen
abgleichen. Bereits abgenommene Backup/Restore/SD-Checks dürfen nicht regressieren.
Insbesondere prüfen: neue `_sort_recovery_proof`-Bedingungen gegen tatsächliche
Run-Daten und Eigentumsrollen; keine Lockerung nur wegen eines roten Tests.

Danach übrige OPEN-Nodes aus dem58er-Inventar:
- frühe Imports ohne gültigen Publikationsbeleg haben noch aktiven SQLstatus;
  Medien und ursprüngliche F14-Lease bleiben geschützt. Statuskorrektur ist
  keine Freigabe/Resume-Autorität und braucht eine eigene genaue Qualifikation.
- Originale Library-/Multiple-/Reintegration-Metadata-Journale sind noch nicht
  durchgängig mit ihrem originalen F14-Key verbunden; keinen Pfad raten.
- historische Exception-Leases ohne Journal/Receipt nicht aus Abwesenheit
  freigeben. Neue Korrektur verhindert weitere Belegverluste, qualifiziert
  einen tatsächlich beleglosen Altfall nicht rückwirkend.
- F14-Continuation mit vorhandenem finished-Receipt trifft noch auf frühe
  Write-Admission; nur unveränderliche exakte Receipts, niemals SQLstatus allein.
- R1 zwei Prozesse nach owner-SIGKILL sowie malicious new_library_origin-Fixture
  noch nicht abschließend qualifiziert. Fremde Herkunft darf nur als explizite
  isolierte Angriff-Fixture erzeugt werden; produktive SQL-Guards bleiben aktiv.
- F11/0562 alte nonzero-Startup-Annahmen nur dann ändern, wenn echte F14-
  Schreibsperre und unveränderte Original-/Fremdbytes vollständig bewiesen sind.
- Vier-Ordner-/Setupfall: vollständige neue Diagnose lesen, keine voreilige
  Annahme über Fixture vs Produkt. Echte neue Installation muss funktionieren.
- RC6 parallele SD-Rechecks: vom anderen abgestürzten READ-Recheck stammender
  Record kann die lebende Operation fencing; zuerst echte Originalprovenienz
  qualifizieren, niemals generisch live/dead ignorieren.

## Noch ausstehende Pflichtabnahme / Kontingent

Erst nach grünen Gruppen147/147 +15/15 + volle BA-02/B01 auf festem Commit,
dann acht disjunkte Backendpartitionen und Frontend/Browser/realer Supervisor-
Container. Testzahlen, Node-IDs, Commit-SHAs und Artefakte unabhängig prüfen.
Kein solcher vollständiger Nachlauf ist jetzt gestartet; keine Veröffentlichung.

Kontingent diese Runde: Start0%/57% (5h/Woche), letzter Abruf49%/65%.
Geplante8 weitere Wochenpunkte erreicht; Zwischenstand geordnet sichern.
Bei Fortsetzung neue Limits lesen, nur nötige targeted Korrekturen, keine
Warteschleifen. Alte Veröffentlichungen/Produktivdaten bleiben unangetastet.

---

# Bibliothekar pre.5 – Fortsetzung, 31.10.2026

## Aktueller Stand – gezielter Legacy-Setupfehler behoben

Branch `codex/pre5-operation-recovery`.
**Letzter geprüfter Anwendungscode:** `ff11f88b8116bae5b0d39f824b1eef828d39e659`.
Dazugehöriger isolierter Linux-Workflow **41222109431: SUCCESS, 31/31 PASS,
0 FAIL/ERROR/SKIP, 40,11 s**. GitHub-Artefakt **13050372420**, von GitHub
gemeldeter ZIP-SHA256:
`0df7bbe15f1d5e3f9ba0300f7ab8e8f46de42f560263deb5341223e6d054cd33`.
Workflowlogs vollständig ausgewertet; Artefakt nicht zusätzlich lokal heruntergeladen.
Fünf nicht testblockierende Python-Warnungen.

### Ursache und Korrektur

- Frühere Stufe 41219852833 (65/66 PASS) meldete nach Live-Wipe
  `unknown_control_evidence`. Codex ergänzte in
  `managed_storage_health._technical_startup_evidence` die streng begrenzte
  Qualifikation des selbst erzeugten `technical-startup-<Nonce>.json`-Belegs.
- Nachlauf **41221622586 (30/31 PASS, 1 FAIL)** kam über diese erste Schranke
  hinaus. Der Originaltest scheiterte nun beim folgenden tatsächlichen Bootstrap
  an `bootstrap_additional_operation` für exakt denselben technischen Beleg.
  Der zweite private JSON-Whitelist-Verbraucher lag in
  `app/storage_bootstrap.py::evidence`.
- Commit **ff11f88b** ergänzt ausschließlich dort die Wiederverwendung
  von `managed_storage_health._technical_startup_evidence` vor der
  privaten JSON-Inventur. Nur strukturell, nach Nonce, reserviertem Kontext,
  Datenbank, Rollen, Identitäten, Generation und vollständig digestverketteter
  bestätigter Setup-Historie qualifizierte Receipts gelangen auf die Allowlist.
  Unbekannte, beschädigte oder zusätzliche Operationen bleiben gesperrt.
  Keine pauschale Präfixausnahme; keine Änderung an SQLite-Guards, F14-Produzent,
  Locking, Archiv-Read-only-Regeln oder Medienoperationen.
- **41222109431** führt dieselben 31 Kontrakttests erfolgreich aus:
  13 neuere Beleg-/Negativfälle, 17 bestehende negative Resetvarianten und
  den echten alten Live-Wipe/Neustart/Ersteinrichtung-End-to-End-Fall.
  Backend-, Container- und Frontend-Volljobs waren ausdrücklich nicht Teil
  dieses kleinen Prüflaufs.

### Weitere verifizierte Teilnachweise

- 41219852833: 3.892 Dateien **213,948 s** (Grenze 300 s),
  100 Dateien **80,796 s** (Grenze 90 s), ohne Profiling PASS;
  sieben neue und acht ältere SQL-Autorisierungsverträge PASS.
- 41220098240: **17/17 PASS** für historische Verhaltensverträge.
- Der alte vollständige Ausgangslauf **41194643144** bleibt historisch rot
  (2204/2444 PASS, 240 FAIL). Sein Inventar
  `docs/pre5/BACKEND-FIX-STATUS.json` ist noch nicht auf den nun erfolgreichen
  Live-Wipe-Nachlauf synchronisiert; dort stehen zuletzt 92 PASS/1 FAIL/
  147 nicht erneut geprüfte Originalfehler.

### Nächste Schritte und Grenzen

1. Nicht noch einmal den behobenen Live-Wipe-Fehler bearbeiten. Erst die
   übrigen fachlichen Ursachen-Gruppen (Backup/Sort/Import/Recheck/Restore)
   gezielt nachweisen und das Originalfehler-Inventar abgleichen.
2. Erst danach auf *einem finalen Anwendungscode* alle Backendpartitionen,
   Zieltests, Frontend/Browser und reale isolierte Container-/Supervisor-/
   90-Dateien-/4000-Familien-/iPhone-Abnahmen laufen lassen. Alte grüne
   Teiltests nicht als vollständige Release-Freigabe ausgeben.
3. **Keine Veröffentlichung**: kein `v1.0.0-pre.5`-Tag, kein Image,
   kein `latest`, kein `main`-Merge, kein Eingriff in TrueNAS/NAS oder
   Produktivdaten. Release erst nach vollständig grüner Endabnahme und
   erneuter Benutzerentscheidung.

## Gesicherte Ergebnisse

Vollständige Ausgangsmatrix41194643144 auf2908eacbf73e891ebd46078cb9ae4af43e0dd454:
2444 Nodes,2204 PASS/240 FAIL/0 ERROR/SKIP in acht disjunkten Partitionen.
Neue Zieltests60+82, Frontend44+147 und reale Containerabnahme damals PASS:
90 Dateien/47 Familien/8 Tage, General-API-Übernahme, Hash-/Registry-Prüfung,
zwei Neustarts,4000 Familien/zwei Bibliotheken,14 iPhone-JPEGs+13:00,
RO-Archive/Herkunft erhalten. Auf neuem Anwendungscode erneut erforderlich.

Alle240 ursprünglichen Fehler: `docs/pre5/BACKEND-FAILURES.{md,json}`.
Einzelner fokussierter Nachweis je Originalnode: `BACKEND-FIX-STATUS.json`:
92 ursprüngliche Fehler inzwischen PASS,1 noch FAIL im zuletzt ausgeführten
passenden Subset,147 noch nicht erneut geprüft. KEIN Ersatz der Schlussmatrix.

-41207207207:62/66 PASS. Acht neue SQLite-Autorisierungsverträge bestehen.
-41214162298/efb50027:73/75 PASS. Beide RC11-Recovery-/Private-Lock-SIGKILL-
 Fälle und neun neue Domain-Recovery-Verträge PASS; Konfigdiagnose und RC4 offen.
-41215262628/4a24b257:76/89 PASS. Konfigdiagnose korrekt. Acht RC4-Prozesse
 starten samt verifiziertem Fehlerabschluss, danach JSON-Parserfehler durch
 Startup-stdout. Vier Retention-Fixtures fehlen feste General/Batch-Anker;
 ein neuer Test verglich irrtümlich das fortzuschreibende Journal als Medium.
-41215645263/a292b916:164/179 PASS. Alle25 Ambient-Registry-Nodes und alle
 O2-Verträge PASS. Dieselben13 QA-Folgefehler plus zwei echte Planungsbarrieren
 vor ausdrücklich bestätigter Variantenrettung. Korrekturen inzwischen im Code,
 vollständiger neuer Linuxbeweis noch PENDING.
-41215816086/2ad5023e: diagnostischer Zweifall-Profillauf FAIL, kein PASS.
 3892-Dateien:31574 Operationsprüfungen/174,778s; Gesamtdauer376,810s inklusive
 Rollback nach Deadline.100-Dateien:5469 Prüfungen/62,497s bei88,750s Profilzeit.
 Dominant sind wiederholte volle private F14-/ACL-/Registryprüfungen pro SQL-
 Opcode. Profiling verändert Zeiten; alte90/300s-Deadlines bleiben bestehen.

ZIP-Digests/IDs und Quellstände in `docs/pre5/EVIDENCE.json`/`PROGRESS.md`.
Alle angeführten ZIP-Digests nach Download verifiziert. Vollständiges altes
Backend-ZIP:248983932 Bytes, SHA256
7838e1590c892d24deb7a071276353ec35447e985c98b42da050806eacf6b996.
51527 Einträge/16,46GB unkomprimiert: NICHT vollständig erneut entpacken.

## Implementierte gemeinsame Korrekturen

1. Bestehende Schema-Versionstabellen rein lesend prüfen; fehlende Tabellen/
 echte Migrationen bleiben schreibgeschützt. RC11-Snapshots erstellen ihr
 angeblich vorbestehendes Schema vor dem synthetischen Orphan.
2. `domain_recovery.py`: exakte alte Reservation/Nonce/Key, Generation, Rollen,
 registrierte Kataloge, aktuelle Schemas/Integrität und Domänenbeweise prüfen.
 Recovery-Eintritt nutzt die ursprüngliche Lease. Unterstützt auditierte
 Trash-Recoveries, selektive/vollständige Löschung mit passendem Journal oder
 unveränderlichem F14-Fertigbeleg und qualifizierten failed-restore-Finalizer.
 Unbekannte/weitere Intents, fehlende Journale, veränderte Bytes bleiben gesperrt.
 Alle ursprünglichen Nachweise stehen im dauerhaften Abschlussreceipt.
3. Bestätigte Variantenrettung ist ausschließlich über die bestehende explizite
 API-Bestätigung erlaubt. Exakt ein passender alter Finalizer, kein anderer
 Orphan; privater Retentioncode prüft/bewahrt ALLE aktuellen Varianten. Vorher
 dauerhafter Entscheid mit Originalreservation. Kein neuer Herkunftsanspruch;
 Job bleibt failed mit seinem Fehler. Erneute Rescue-Bestätigung nie automatisch
 aus einer alten Rescue-Reservation ableiten. Startup nur erneut aufrufen, wenn
 nach erfolgreichem Abschluss eine alte Startupdiagnose zurückgesetzt werden muss.
4. Private Wiederaufnahmeabsicht wird vor Erwerb der alten Kernel-Lease persistiert.
 Andere Threads/Prozesse bleiben damit auch bei LIVE-Resume über SQL und F14
 im betroffenen Scope gesperrt. Frisch gestartete normale Recovery, die noch auf
 den Lock eines laufenden Trash-Schreibers wartet, darf diesen Besitzer nicht
 selbst unterbrechen: zusätzliche Sperre nur bei persistiertem Replay-Intent.
 Vorhandene Trash-/Root-Locks und Startup-Writer-Barriere bleiben aktiv.
5. `sqlite_authorization.py`: Evidence-Snapshot nur während EINES execute/
 cursor.execute teilen. Jeder neue Aufruf frisch; executescript/executemany
 behalten ungekürzte Prüfungen. Jede Tabelle/Triggeraktion erhält weiterhin
 ihren eigenen Scope-Entscheid, Read-only/Recovery-Kontext wird jedes Mal geprüft.
 Sieben neue Verträge: frischer Orphan zwischen Statements, zwei Verbindungstypen,
 Cursor, Skript-UDF erzeugt Orphan, Metadaten-Trigger trotz erlaubter Basistabelle.
 Nach-Fix-Laufzeitnachweis ist noch OFFEN.
6. Guarded QA-Harness legt seine deklarierte leere Bootstrap-Registry/Katalog/
 Config vorher unter AUDIT_SCRATCH an (null Jobs/Dateien/Bibliotheken). Keine
 produktive Missing-DB-Prüfung geändert. Startupdiagnosen der alten JSON-Adapter
 gehen nach stderr; beide Streams bleiben als Belege erhalten. Historische
 vollständige Fixtures enthalten alle sechs festen Verwaltungsrollen. Externe
 SQL-Beschädigung ausdrücklich nur in synthetischen Fixtures über external_sql.
 Zweite an shared recovery beteiligte Fixturebibliothek wird vorher registriert.
7. Konkreter configuration_invalid-Fehler wird nicht durch zweites Parsen verdeckt.
 Doppelte Strukturdiagnosen dedupliziert. Abgeleitete Rollen unterscheiden
 previously_observed/not_observed ehrlich. Auth-only prüft503 ohne initialisierten
 Storage bei weiterhin401 für geschützte Routen und keinerlei angelegten Dateien.

## Weitere Abnahme ausschließlich in späterer Runde

Die aktuellen nächsten Schritte stehen oben. Die offenen Backup-/Sort-/Import-/
Recheck-/Restore-Gruppen und finale Backend-/Frontend-/Container-/Browsermatrix
hier NICHT neu starten. Alte PASS nicht dem endgültigen Code zuschreiben.
Keine Veröffentlichung vor späterer vollständiger Endabnahme und Entscheidung.

## Aktuelle Nachweise und Grenzen

41217778080: Artefakt13049571446 SHA256
63302fc2692d83a237acfba303051098df85152ddffed06b07aacfcf0016184e,
nach Download verifiziert. Vollständige Logs/XML unter
/private/tmp/bibliothekar-pre5-evidence/41217778080-targets/.
Zusätzlich alle neun Workflowlogs/1022Zeilen gelesen; keine weitere verborgene
Infrastrukturfehlermeldung neben dem normalen Exit1. ZIP-SHA256
013a4b7dc2bb7f8a7b0333b883c428b9506f4cac4eaddb9d15b867f02c82f06f,
Datei41217778080-job-logs.zip. Keine großen Altartefakte erneut heruntergeladen.
Der letzte sichere vollständige Backendnachweis bleibt41194643144 rot.
Neuere gezielte PASS sind echte Teilnachweise, nicht globale Freigabe.

## Werkzeuge / Arbeitsgrenzen

Scratch `/private/tmp/bibliothekar-pre5-evidence/`; ZIPs und selektiv extrahierte
vollständige Logs/XML vorhanden. Baselinezusatz `41194643144-backend/failures.json`.
GH_CONFIG_DIR=/private/tmp/bibliothekar-gh-device GH_BROWSER=true GH_DEBUG=
GODEBUG=http2client=0; CLI=/private/tmp/bibliothekar-gh-cli/gh. Direkte gh api mit
Cache-Control:no-cache; gh run view/list kann veraltet sein. ZIP/Logs mit
--allow-escape-sequences in Datei, Tokens niemals ausgeben.
Actionlint /private/tmp/pre-actionlint/actionlint mit docs/pre/release/actionlint.yaml.
Alle Jobs[self-hosted,Linux,X64,bibliothekar-safe], keine Subagents. Nur lokale
Syntax-/Quell-/Evidenzanalyse, eigentliche App-QA auf isoliertem Linuxrunner.
Unversioniertes qa/rc14.zip ist Benutzerartefakt, niemals stage'n.
Kein NAS-Zugriff, keine produktive SQL-/F14-Bereinigung, keine alten Tags/Images/
Releases/latest oder Rechte ändern. Native TrueNAS/NFSv4, physische SD/USB und
echtes DNG1.7-/RAF-Schreiben NOT_RUN. VarianteA und Verlustabschluss DEFERRED.

## 31.10.2026 – Benutzerfreigabe zur vollständigen Endabnahme (noch KEIN Release)

Der Benutzer hat ausdrücklich die vollständige erneute Abnahme und eine **nur bei
vollständig grünen Nachweisen** zulässige pre.5-Veröffentlichung freigegeben;
bei jedem roten/unklaren Test ist vor Veröffentlichung zu stoppen und der Befund
mit Handlungsvorschlag mitzuteilen. Kein Freibrief für Safety-Bypasses.

Der alte Zweistundenlauf **41194643144** war: reproductions SUCCESS,
container SUCCESS, frontend SUCCESS, backend FAILURE (2204/2444 PASS,
240 FAIL). Er lief auf Anwendungscode 2908eacb, nicht auf dem nun finalen
ff11f88b; die grünen Container-/Frontend-Ergebnisse sind kein neuer Nachweis.

QA-only Commit **ffe05f61c83d9d990d0c4b834ff8a76f685aba40** ergänzt
`qa/pre5/backend_unretested.json` mit exakt den 147 ursprünglichen Fehlernodes,
die in `BACKEND-FIX-STATUS.json` keinen jüngeren gerichteten Status hatten,
sowie ein vorgelagertes, isoliertes Linux-Gate in
`.github/workflows/qa-pre5-operation-recovery.yml` nur bei `[pre5-full]`.
Keine Anwendungscodeänderung. **GitHub Actions 41222826726** ist die
beauftragte vollständige Freigabeprüfung; das erste aktive Gate prüft die
147 Nodes. Bei Rot wird die abhängige Container-/Frontend-/Backend-Matrix
nicht ausgeführt. Bei Grün folgen die bisherigen reproductions, echte Container-
/Frontend-Abnahme und 8 disjunkte Backendpartitionen mit vollständigem
Node-Manifest; Veröffentlichung folgt erst nach tatsächlicher Auswertung.

Der bestehende vorbereitete Publisher in `docs/pre5/release` ist derzeit
**NICHT einsatzbereit**: `ACCEPTANCE.json` steht auf PENDING und Source 2908eacb,
`PUBLISH-WORKFLOW.yml` hat noch den alten `BUILD_SHA=2908eacb`. Ohne
vollständig verifizierte, an die neue Quelle gebundene Akzeptanz darf daraus
kein Tag/Registry-Image/Release erstellt werden. Bis dahin keinerlei Änderung an
main, bisherigen Tags, latest oder TrueNAS.


## Diagnose 31.10.2026 – vollständige Belege gesichert

[41226158077](https://github.com/heller-adrian/Bibliothekar/actions/runs/41226158077)
auf QA-Commit `a00c51a7` (Anwendungscode unverändert `ff11f88b`):
24 gezielt ausgewählte Originalnodes aus zwölf offenen Fehlergruppen,
**4 PASS/20 FAIL/0 ERROR/0 SKIP**; JUnit-Abdeckung exakt 24/24.
Komplettarchiv **13051308412** inklusive vollständigem `stdout.log` und
`result.xml` pro Gruppe; SHA256
`98cc15f4a128b2edf1e3723e7d1c0974f23cc0d9998ce9065f13c6459131ad9b`
nach Download verifiziert. Vorheriger fehlgeschlagener 147er-Lauf
41222826726 bleibt 30/147 PASS und hatte unvollständigen Artefaktpfad.
Detaillierter Bericht jetzt `docs/pre5/DIAGNOSTIC-20261031.md`.

**Weiterer Auftrag nötig für Anwendungsreparaturen.** Keine Änderungen an
Produktcode, Branch `main`, Tags, GHCR, `latest` oder TrueNAS. Release blockiert.
Nicht ungezielt die 147 oder Vollmatrix wiederholen, bevor Ursachen gruppiert
und mit positiven/negativen Gegenbeweisen korrigiert wurden.

## 31.10.2026 – nachgewiesene Fixture-/Erwartungskorrekturen, keine App-Änderung

Zielgerichtete Linux-Nachprüfung auf **cc4cbe47b35e1f5d59eb231796e7e4f82bb37f31**:
GitHub Actions **41226912195 SUCCESS, 3/3 PASS, 0 FAIL/ERROR/SKIP**.
`test_rc9_setup_separation` prüft beide Varianten der ersten Bibliothek:
`technical_registry` legt nur die Registry an, nicht die Hauptdatenbank.
Daher ist `catalog_unavailable` in beiden synthetischen Zuständen korrekt,
`can_setup_again` bleibt wahr, der Archiveintrag bleibt unberührt.
`recovery_0562/worker.py` legt für die zweite historische Fixturebibliothek
vor dem Crash auch `General` und `Batch Correction` an. Der reale
Metadatenprojektionstest mit zwei SIGKILLs besteht bis zum Ende.
Artefakt **13050924946**, GitHub- und unabhängig geprüfter SHA256
`861f500dc3d1f98568ac6a46e798a291a92e6322d5589d930f93046d6f1bc7d0`.

Zielgerichtete Linux-Nachprüfung auf **9d934a2dac883f2f39c81aed74ce9e182c7a19b0**:
GitHub Actions **41227115670 SUCCESS, 2/2 PASS, 0 FAIL/ERROR/SKIP**.
Zwei B01-Verhaltensverträge prüfen jetzt statt veralteter mutierender GET-Hooks
einen aktiven Inventory-Writer gegenüber rein lesenden GETs sowie zwei
parallele Ereignis-Leseabfragen. Erwartet wird HTTP 200 bei überprüften,
unveränderten Medienbytes, Schlüssel-Datenbankzuständen und privaten
F14-JSON-Belegen. Kein Produktionscode geändert. Artefakt **13052108489**,
GitHub- und unabhängig geprüfter SHA256
`1d75aaad3cee8dabf877b66c051f94b0801e1e9601fec22e0cf2e0b075370184`.

**Vier zuvor rote Originalnodes** (RC9 technical_control, 0562 metadata
projection, zwei B01-Fälle) sind jetzt gezielt grün, zusätzlich der positive
RC9-legacy_roots-Kontrollfall. Dies ist KEINE vollständige Backendabnahme;
`BACKEND-FIX-STATUS.json` bleibt zunächst das historische Inventar, dessen
breite Statussynchronisierung noch aussteht. Die restlichen Recovery-/Restore-/
Recheck-Fehler sind separat zu untersuchen. Die weiteren B01-Altverträge wurden
hier nicht als erfolgreich nachgewiesen. Keine Tags, Images, main oder TrueNAS
verändert; **Pre.5 nicht veröffentlichen**.

## 31.10.2026 – B01 vollständig grün; Wiederherstellung eindeutig rot

- **B01 complete test file**, Run [41227607033](https://github.com/heller-adrian/Bibliothekar/actions/runs/41227607033), commit `df1c1f43529c5a174c3bf6386906a182cf2653c7`: **10 PASS, 0 FAIL/ERROR/SKIP**. Zwei zuvor rote historische Fälle (`test_b01_parallel_edit_structure`, `test_b01_live_trash_operation_is_not_waited_on_indefinitely`) durch echte parallele lesende GET-Verträge mit überprüft unveränderten F14-JSON, Medien und Schlüsseldatenbankwerten ersetzt. Kein Anwendungscode geändert.
- **Backup/Restore/SD-Recheck/Import original contracts**, Run [41227720942](https://github.com/heller-adrian/Bibliothekar/actions/runs/41227720942), QA commit `f52d1c4318f0aaf1dc588e7daf34cbf330e78acd`: **0 PASS, 10 FAIL, 0 ERROR/SKIP**. Vollständig gesicherte JUnit-/stdout-ZIP **13052616493**, SHA-256 nach eigenem Download überprüft: `f3fa99af869a5163864a72182738f7bafe235202ac724bcbed5d8837aa7e5066`.
  - Backup 3/3 FAIL: `operation_recovery_required` vor ursprünglicher `recover_backup_deletions`-Journalprüfung; auch Tamper-Gegenfall kommt nicht durch den F14-Eintritt.
  - R1 2/2 FAIL: unsicherer Kollisionstest erlebt Start mit RC 0, anderes Szenario behält `.trash-restores`-JSON trotz DB-/Audit-Abschluss.
  - 0562 Restore 1/1 FAIL: zweiter echter SIGKILL-Hook wird durch belegte Recovery-Sperre nicht erreicht.
  - SD-Recheck 3/3 FAIL: `verifying` statt `completed` am Hash-Handoff bzw. Kindauftrag bleibt `queued` statt `completed`.
  - 0562 Import-Discard 1/1 FAIL: Auftrag bleibt `organizing` statt `interrupted` nach schützend abgelehnter fremder Byte-Manipulation.
- Die 10 Fehlerfälle sind echte **Release-Blocker**, nicht zehn unabhängig bewiesene Ursachen. Nicht mit angepassten Erwartungen schönfärben. Insbesondere `app/domain_recovery.py` hat für Backup kein dem ursprünglichen `delete_backup`-Record entsprechendes qualifiziertes F14-Reentry. Änderungen hier erfordern neue positive und negative Byte-/Registry-/Root-/Reservationstests und eigenen freigegebenen Sicherheits-Patch.
- **Full backend wurde absichtlich nicht gestartet**, weil die vorgeschalteten Original-Crash-Verträge ROT sind. Frontend-/Container-Neuabnahme ebenfalls ausstehend. Kein Release, keine Images/Tags und keinerlei Änderung an `main` oder TrueNAS. **App-Code weiterhin ff11f88b**.

## 31.10.2026 – Freigegebene BA-02-Reparatur: vollstaendige Backup-Testdatei GRUEN

Anwendungscode auf Entwicklungsbranch repariert: d89a32d5 (app/domain_recovery.py)
und d77a8f11 (app/root_operations.py), anschliessend QA/Negativtests
c1115ac7. try_backup_entry verwendet nur die urspruengliche orphaned
F14-Reservation von app.backup_management.delete_backup und prueft
Bibliotheksregistrierung, Hauptdatenbank, Journalzuordnung, Job-ID,
Generation, Root-Identitaeten und Original-Reservationsinhalt. Der
eigentliche Recovery-Handler arbeitet innerhalb dieser Original-Reservation.
Ein blockierter Recovery-Versuch loescht weder Journal noch F14-Nachweis;
neue oder fremde Journalbelege autorisieren nie eine Loeschung.

PRUEFUNG: GitHub Actions 41228704454 auf c1115ac7: 11 von 11 PASS,
0 FAIL/ERROR/SKIP in gesamter tests/backend/test_0500_backup_delete_recovery.py.
Dies beinhaltet alle acht urspruenglich roten BA-02-Faelle, Multi-Library,
staged foreign file, unknown empty subdirectory, tampered bytes,
Crash vor/nach DB-Commit sowie zwei neue Negativtests (gefaelschte
Reservation-ID und zusaetzliches fremdes Journal) mit nachfolgender
positiver Wiederaufnahme bei unveraenderten Originalbelegen.
Unabhaengig heruntergeladenes ZIP-Artefakt 13052677866:
SHA256 c0ad58ad281568871a6c34058e18986f68c5a069250d93be49385ca2d732dafa.
JUnit 11 Faelle vollstaendig geprueft.

Zusaetzlicher gezielter 10er-Run 41228354107 auf d77a8f11:
3 Backup PASS, 7 andere Originalfaelle FAIL. Diese sieben verbleiben
als konkrete Release-Blocker: 3 Restore, 3 SD-Recheck, 1 Import-Discard.
BACKEND-FIX-STATUS.json aktuell 107 PASS / 7 FAIL / 126 ohne einzeln
katalogisierten neueren Nachweis (von urspruenglich 240 FAIL-Nodes).
BA-02-Pruefung ist ein Teilnachweis, KEINE komplette Backend-Abnahme.
Vollmatrix, Frontend und Container wurden NICHT auf aktuellem Code
abgenommen. Keine Veroeffentlichung; main, Tags, GHCR und TrueNAS unberuehrt.

Naechste sicherheitskritische Phase: Restore-F14- und Journal-Recovery
isoliert pruefen/reparieren; danach SD-Recheck-Worker/Queue und Import.
Erst dann aktueller voller Backend-Test und weitere Release-Gates.

## 31.10.2026 – fortgesetzte Pre.5-Crash-Recovery, Abnahme noch ausstehend

Auf Nutzerfreigabe wurden nacheinander Restore, SD-Recheck und Import
unter unveraenderten F14-Schutzprinzipien repariert. Anwendungspatches:
- ec476e06 / 5b2ac06 / 26c5cf49 / 12e9a1e6: abgesicherter Abschluss
  eines direkten bzw. bereits SQL-/Audit-verifizierten Restore-Journals,
  exakte bekannte Quellmenge und keine fremden Staging-Dateien.
- ed8845ab / 5b2ac06: originale F14-trash-Restore-Reservation wird
  bei exakt passendem, registriertem, unveraendertem Journal unter
  qualifizierter Recovery-Freigabe fortgesetzt; kein allg. Bypass.
- ad39ce07 / 0582e8ca: verwaiste *lesende* SD-Pruefung nur nach
  tatsaechlichem jobs.operation='sd_recheck', Source-/Root-/DB-
  Identitaetskontrolle und atomarem Child-Handoff sicher als
  neu zu hashender Check qualifiziert; echter folder_import behält F14.
- fe82b6f0: urspruenglicher verwaister, mit import_recovery.qualify
  nachgewiesener folder_import wird bei Startup ausschliesslich in
  state='interrupted' markiert, ohne Dateien, Herkunftsjournal oder
  F14-Reservation zu entfernen. Aufruf in operation_health.
- 7565ab06 / dc00ddc1: historische negative Restore-Tests duerfen
  zwar einen lebenden READ-Server sehen, verlangen bei offenem
  ungeklaertem Restore jedoch nachweislich writes_allowed=False
  und unveraenderte originale F14-trash-Reservation samt Bytes.

Nachweise:
- 41230227562 auf 12e9a1e6: 9 PASS / 1 FAIL (Import-Status).
- 41230840038 auf 0582e8ca: letzter Import-Crashtest 1 PASS.
- 41230912187 auf c080e9a2: 12 PASS / 3 FAIL, dabei alle
  zehn urspruenglich roten Crash-Faelle PASS; die drei roten
  Sicherheitsgegenproben hatten nur einen veralteten erwarteten
  Prozess-Exitcode. Echte F14-Schreibsperren und unveraenderte
  Fremdbytes sind aus vollstaendigen Restart-Logs nachgewiesen.
- JETZT PENDING: 41231315552 auf dc00ddc1: zehn Originalfaelle
  plus fuenf Manipulations-/Kollisions-Gegenproben, alle mit
  expliziter Pruefung der echten F14-Schreibsperre.
- Redundanter historischer QA-Run 41231036891 belegt aktuell
  denselben selbstgehosteten Linux-Runner. Er ist KEINE
  Release-Abnahme. Neuer Run startet nach Freigabe des Runners.
- Artefaktsicherung repariert: vollstaendige original-unretested
  JUnit-Resultate werden beim nachfolgenden pre5-full-Lauf archiviert.

Release-Gate: PRE.5 NICHT FREIGEGEBEN. Die 15er-Sicherheitsabnahme
steht noch aus; der neue 147er-Originalcheck, alle 8 Backendpartitionen,
Frontend und Container wurden auf dem neuen Source-Stand nicht abgenommen.
Kein main/tag/GHCR/TrueNAS veraendert. Bei roten Resultaten nicht publishen.

## 31.10.2026 – 15/15 Crash-/Tamper-Gate unabhaengig PASS; Vollabnahme gestartet

- QA-Commit dc00ddc1: `tests/backend/test_r1_restore_recovery.py` und `test_0562_process_recovery.py`
  pruefen jetzt bei einem absichtlich blockierten Restore nicht mehr bloss einen
  nonzero Prozess-Exitcode, sondern durch `operation_health.inspect`
  die nachweislich bestehende F14-Schreibsperre, einen qualifizierten
  orphaned Trash-Record und weiterhin unveraenderte Medien-/Fremdbytes.
  RC14 darf geschuetzte Leseanfragen im Prozess weiter beantworten.
- GitHub Actions [41231315552](https://github.com/heller-adrian/Bibliothekar/actions/runs/41231315552):
  **15 von 15 PASS, 0 FAIL/ERROR/SKIP** auf Commit dc00ddc1.
  Darunter alle zehn zuerst roten Backup-, Restore-, SD-Recheck-
  und Import-Crash-Tests sowie fuenf Tamper-/Kollision-Gegenproben.
- Artefakt 13054435099: vollstaendiges XML + Restart-/Subprozesslogs.
  ZIP unabhaengig heruntergeladen und SHA256 verifiziert:
  `3be575a58f2c708f6302ca7ea37787193767b27920770f96d538791e42461694`.
  Das XML enthaelt exakt 15 eindeutige Testcases und keinen Fail/Skip.
- docs/pre5/BACKEND-FIX-STATUS.json nun **119 zuletzt gezielt PASS,
  0 zuletzt gezielt FAIL und 121 ohne einzeln katalogisierte neue Nachpruefung**
  der urspruenglichen 240 roten Nodes. Nicht als volle Suite missverstehen.
- GitHub Actions **[41231600475](https://github.com/heller-adrian/Bibliothekar/actions/runs/41231600475)**
  auf **7838a7062565b712a4f24fa481967d46df173d45** wurde gestartet:
  die 15er-Gate-Pruefung steht vor der exakten 147er-Originalfehlerpruefung.
  Erst wenn beide gruen, werden container/frontend und danach die acht
  vollstaendigen disjunkten Backendpartitionen ausgefuehrt.
- Standardlauf 41231036891 SUCCESS wurde separat ausgefuehrt; er
  ersetzt nicht die vollstaendige neue Abnahme.
- **Freigabestatus: NICHT ABGENOMMEN, PRE.5 NICHT RELEASED.**
  Bis zum endgueltigen Resultat der vollständigen Matrix weder Publish
  noch main/TrueNAS/GHCR/Tag veraendern.

## 01.11.2026 – aktuelle Fortsetzung: neun Originalfehler bestanden

- Ausgangslauf 41261700576 auf e9061f41 vollständig ausgewertet: 115/124 PASS, neun FAIL, kein ERROR/SKIP. Artefakt13066567306 SHA256 35192296609f1f83c5f99e887b3ccef2ecd82efef9412b9e885a8bd38bdccb8f. Der ältere Lauf41261174452 ist abgeschlossen (90 PASS/13 FAIL), kein aktiver Lauf mehr.
- a554f3190c385c1245ff6fa0c9fdb92a687b653c: sieben belegte Config-Fixtures korrigiert, Restore-Konflikt vor Bestandsabgleich über originale Domain-Recovery qualifiziert, Vier-Ordner-Test mit realem Bootstrap und zwei Starts abgesichert. Produktiv-Konfiguration wird weiterhin niemals stillschweigend ersetzt.
- Linux41298781380 SUCCESS: exakt neun Originalfälle PASS, keine FAIL/ERROR/SKIP. Artefakt13080103179 SHA256 74d81033faef54571be199dd602d55bce2443f735a415c1f22518b82db252be1.
- d09550b9a9cc5291789e3f6e150737abf564a9a3: General-Fixture bindet Registry vor der originalen Crash-Operation und prüft deren originalen F14-Abschluss. 15 zusätzliche negative/positive Config-, Restore- und Read-only-Verträge. Lauf41299144678 prüft diesen Stand mit bisheriger124er-Nachbargruppe; Ergebnis noch auszuwerten.
- Uncommittierter nächster Schritt: originale finished-Receipts vor dem Admission-Fence unter vollständigem Workspace-Ausschluss prüfen und crashfest archivieren; acht Gegenproben einschließlich SQL-Status ohne Proof und noch vorhandenem Backup-Journal. Noch KEIN Linuxnachweis für diese Änderung.
- Kumulierte individuelle Nachweise aus verschiedenen Commits: 221/240 PASS,19 offen; dies ist KEINE Gesamt-Abnahme. Ursprüngliche58:39 inzwischen gezielt PASS,19 noch frisch zu prüfen.
- Nächster Schritt: Ergebnis41299144678 auswerten; dann eng begrenzten Receipt-Fix sowie exakte58 Originalnodes prüfen. Keine Veröffentlichung. BACKEND NOT ACCEPTED.
