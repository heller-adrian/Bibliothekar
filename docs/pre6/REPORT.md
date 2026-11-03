# Pre.5-TrueNAS-Abnahme – Entwicklungsbericht für einen Pre.6-Kandidaten

Datum03.11.2026. Basis unverändert veröffentlichter Commit b4c3a397843567bfe09b35e82c51d0009d0a71bf. Entwicklungsbranch codex/pre6-truenas-acceptance. Vollständiger Anwendungscode d64bfba83af80bfe79dfce80ccfc017cf49aad12; nachfolgende Dokumentationscommits ändern ihn nicht. **Keine Veröffentlichung freigegeben oder vorgenommen.**

## Befund je Originalbild

| Bild | Ursache/Bewertung | Bearbeitung und Nachweis |
|---|---|---|
|1|RenderBackupFilter bot sämtliche nicht archivierten Herkunftsaufträge an, auch abgeschlossene0-Familien-Aufträge.|Nur completed+planned+aktive0+gesamt0+kein Fehler werden aus der normalen Auswahl ausgeblendet; History/SQLite/Provenienz bleiben unverändert. Browsergegenproben behalten queued/verifying/failed/interrupted/blocked und archivierte Einträge. |
|2|Vier Blocker sind keine vier bewiesenen Byte-Dubletten. Ein Ziel kann gleichzeitig als vorhanden und mehrfach geplant gemeldet werden.|Reale Plan-Reproduktionen für gleichen Namen mit fremden Bytes und Case-Folding bleiben gesperrt, alle Bytes/Katalogzeilen unverändert. Neue strukturierte Quellpfad-/File-/Familien-/Hashdaten; keine Umbenennung, kein Überschreiben, kein Hash-basierter Eigentumswechsel. Früher Hinweis erklärt Import-/Sortierphasen. Tatsächliche NAS-Inhalte weiterhin ungeklärt. |
|3|assign-existing speichert neue Assignments zu einem weiterhin applied Ereignis; dessen neue Segmente sind zunächst nur SOLL.|Qualifizierter Original-Snapshot der Mutation bestimmt weiter die physische Tagesablage. Separater Apply-Schritt bleibt erforderlich. |
|4|_free_rows schloss alle applied Assignments aus. Die16 neuen, noch nicht verschobenen Tagesdateien landeten deshalb im unmatched-Zweig und wurden als externe Ereignis-Rückverschiebung gemeldet.|Exakt16 falsche Warnungen vor Patch reproduziert. Neue Assignments werden nur mittels Original-Snapshot als noch physisch frei erkannt. Alte Mitglieder und echte externe Moves bleiben Konflikte; falsche Alt-Hinweise erst nach erneuter physischer Prüfung auflösen. |
|5|Workspace behandelte nur change_request_id als direkten Folgeschritt; resort_required/event_id wurden nicht weitergeleitet.|Echte saveEvent-Funktion navigiert zu task=resort des kanonischen Ziel-Jobs. Keine physische Aktualisierung/Anwendung beim Speichern. Browser prüft abweichenden Quell-/Ziel-Job. |
|6|DNG1.7-Schreiben wird durch ExifTool verweigert; „Metadaten sicher“ war als Zeitvertrauen gemeint.|Badge heißt „Aufnahmezeit belastbar“. Verständlicher Fehler, technische Originalmeldung aufklappbar; exakt bereits als inkompatibel abgewiesener Auftrag wird nicht erneut angeboten. Verwerfen bleibt möglich. Backendwriter/-m/ExifTool unverändert; tatsächliches DNG1.7-Schreiben weiterhin nicht bestätigt. |
|7|Rücksprung wurde vor der Abschlussprüfung immer oben angezeigt.|Nur Darstellung geändert: unten neben Abschluss; nach erfolgreicher Prüfung verborgen, nach Prüfungsfehler sichtbar. Schrittkarten1/2/3 und ausdrücklicher Abschluss bleiben. Backendarchivprüfung unverändert. |

Alle drei Dokumente wurden vollständig einschließlich Originalhäkchen gelesen.37/44 sind Nutzer-PASS, D2/D7/E4/E6/G3/G4/UX-01 bleiben im ursprünglichen Häkchenstand offen. Neue synthetische Tests ersetzen diese noch ausstehende manuelle Nachabnahme nicht. Das Paket und alle sieben Bilder sind über INPUT-SHA256.json eindeutig identifiziert.

## Fachlich kritische Korrektur

`central_stock_reconcile._pending_no_event_family_ids()` unterscheidet neue SOLL-Zuordnung von zuvor physisch angewendeten Familien anhand event_mutations.original_state_json. Fehlende/widersprüchliche Snapshotdaten werden nicht als Freigabe behandelt. `free_stock_layout.occupied_ranges_for_day(physical=True)` nutzt für eine offene Applied-No-Event-Erweiterung die alten Zeitsegmente. Explizit einbezogene Ereignisse können weiterhin für den tatsächlichen Apply-Zielplan bewertet werden. Ein aktueller möglicherweise bereits durch eine Drift-Beobachtung aktualisierter Pfad ersetzt keinen fachlichen Erwartungsnachweis. Deshalb bleiben wiederholte echte Verschiebungen auch nach erneuter Inventur sichtbar.

Der Test legt zuerst eine Sammlung über echte Programmfunktionen an und wendet sie physisch an. Danach werden16 neue Testdateien über assign_free_families_to_existing_no_event zugeordnet; Speichern darf keine Bytes bewegen. Reapply erfolgt über build/prepare/execute_workspace_reconcile_run. Nach zwei erneuten Katalogzugriffen: korrekte Hashes, Originalpfade regulär geleert, Mutation completed, SQLite integrity_check=ok. Zwei echte externe Moves vor/nach Speichern sowie ein extern verschobenes altes Mitglied bleiben gesperrt. Ein historischer falscher16er-Hinweisbestand wird durch erneute verifizierte Inventur aufgelöst. Malformed-Snapshot bleibt verweigert.

Die synthetische16-Dateien-Tabelle wird als pre6-sixteen-unmoved-files.json im Linux-Ergebnisarchiv ausgegeben. Sie ist ausdrücklich keine Tabelle der realen NAS-Dateien. Für die reale16er-Dateiliste und die beiden Fuji-Zielnamen fehlen noch die unabhängigen Katalog-/Hash-/Ursprungsdaten; READ-ONLY-DIAGNOSIS.md beschreibt die erforderliche lesende Abfrage. Es wurde nichts am NAS ausgeführt.

## Sicherheit und Grenzen

Root-/Mountidentitäten, Symlink-/Hardlinkgrenzen, F14-Originalreservationen, SQLite-Autorisierung, Journale, Hashprüfung und Archiv-RO bleiben verbindlich. Keine Änderungen an root_operations.py, sqlite_authorization.py, appdata.py, storage_anchors.py, metadata_abort_recovery.py, SafeTransfer, SortApply, Archiv-Change-Request-Backend, SQL-Migrationen oder historischen QA-Originalen. Neue Quellangaben dienen Diagnose, nicht Eigentumsautorisierung. Eine blockierte Sortierplanung verändert keine Katalogzeilen und keine Medien. Kein neues Bereinigungs-/DB-Reparaturverfahren.

F-02 ist für die vier echten Dateien noch nicht abschließend ursächlich geklärt: gleicher Name kann aus einer anderen Aufnahme, nachträglichen Metadatenbytes oder einer anders erfassten Herkunft stammen. Ohne Nachweise wird kein Import als fehlerhafte Dublette umgedeutet. F-03: Bild6 zeigt General/DNG, keinen globalen Medienverlust. Die synthetischen abgewiesenen Pläne bewahren Katalog und Dateien; der tatsächliche Filter-/Browserzustand beim NAS-Vorfall ist nicht verfügbar.

Neue UI-Fälle werden mit tatsächlichen Render-/Handlerfunktionen und synthetischen Antworten in Offline-Chromium geprüft. Das ist kein Ersatz für eine native TrueNAS-Abnahme. Die neue No-Event-Kette ist zunächst über reale Programmfunktionen geprüft; ein vollständiger zusätzlicher HTTP-/Containerablauf genau dieser Erweiterung ist separat nachzuholen. Die vorhandene unveränderte Pre.5-Containerabnahme prüft den allgemeinen HTTP-/General-/Restart-/F14-Betrieb auf dem neuen Image.

## Testergebnisse und Commitzuordnung

Lokal macOS:3 ursprüngliche Reproduktionen vor Produktpatch FAIL (jeweils16 statt0/1), danach10 neue Backendfälle PASS;13 Chromiumfälle PASS (Deutsch/Englisch,390/1280px und tatsächlicher Save-Handler). AST/JS-Syntaxprüfung PASS. LOCAL-EVIDENCE.json enthält die Ergebnisprüfsummen. Diese Angaben sind keine Linux-PASS-Zahlen.

Linux: erster Lauf41562116273 auf687f1786153b1834204819c2e8031dc36df393a6 enthält noch nicht die lokal geprüften Zusatzfelder in sort_plan.py; dessen Ergebnis ist deshalb kein Finalnachweis. Folgelauf41562234548 auf vollständigem Code d64bfba83af80bfe79dfce80ccfc017cf49aad12 ist der relevante gezielte Abnahmelauf. Der Backendblock dieses Laufs besteht98/98; der Lauf scheiterte erst am fehlenden System-lib prebuilt Chromium. Der erfolgreiche Abschlusslauf ist unten dokumentiert. Keine vollständige mehrstündige Backendmatrix gestartet.

## Gesonderte Entscheidung

PRIVILEGES-DECISION.md untersucht ausschließlich Standardprofil/optionale Geräteerweiterung, effektive UID, Geräte-/Mount-Namespaces, Capabilities und Katalogrichtlinien anhand tatsächlichen Quellcodes und offizieller Quellen. Keine Hardware-/Deployment-Implementierung. Native ACLs und reduzierte Geräte-Capabilities NOT_RUN; SD/USB und echte RAF sind im Nutzerprotokoll positiv, aber hier nicht erneut hardwareseitig geprüft.

Empfehlung: nach erfolgreicher gezielter Linux-/Browser-/Containerprüfung als Pre.6-Kandidat weiterführen; reale Kollisionsnachweise und E6 prüfen, anschließend ausdrücklich freigegebene praktische Abnahme. Keine Behauptung einer stabilen1.0.0 oder vollständigen DNG-/ACL-/Katalogzulassung.


## Abschließende Linux-Abnahme

**41564118139 SUCCESS** auf `bc997133254ff60ec6151c9023f8e6d5dbde6c32`. Anwendungscode gegenüber `d64bfba83af80bfe79dfce80ccfc017cf49aad12` unverändert.98/98 Backendfälle,0FAIL/ERROR/SKIP aus41562234548 werden anhand des gepinnten ZIP-Digests, JUnit-Einzelfällen und identischen Git-Trees für app/tests/Dockerfile/Abhängigkeiten/F14-QA/Manifest ausdrücklich wiederverwendet. Keine fiktive Neuausführung.

13/13 neue Offline-Chromiumfälle plus8/8 authentifizierte Browserfälle in der echten Anwendung PASS. Alle sechs realen Containerprüfbereiche PASS: General-Korrektur/Übernahme und zwei Neustarts; historische Pre.4-Inventory-Reservation; isolierter Konflikt mit echtem unabhängigem Import/Ereignis/Sortierung und zwei Neustarts; authentifizierte Diagnosen; unveränderte Archive; normale Seiten bei weiterhin wirksamen Schreibsperren. SIGTERM241 war mit nachgewiesenem geordnetem Webshutdown vereinbar. Das Testimage wurde nur lokal auf dem Runner gebaut, nicht nach GHCR gepusht.

Original-Prüfdatei qa/pre5/browser.cjs behält alle DB-/Authentifizierungs-/Operations-/Archivassertions. Nur Navigation über neue Statuskarte und Lesen eingeklappter technischer Daten wurden an die beauftragte UI angepasst. Historische unveränderliche QA-Fix­tures wurden nicht geändert.

Artefakt13197748512, SHA256 `aaac1c8b9ca0fce75553514929b8260e60b7fe83dd558bf192b468c2e10cafcc`, unabhängig heruntergeladen und geprüft. JUnit98Nodes,13+8 Browserfälle, sechs Containerchecks und34 hochgeladene Manifestdateien unabhängig gegengeprüft. Backend-Originalartefakt13197717109 ebenfalls unabhängig SHA256-geprüft. Maschinenlesbar: LINUX-EVIDENCE.json. Lokale Downloads `/private/tmp/bibliothekar-pre6-local/accepted.zip` und `second-linux.zip`.

Die vorangehenden roten Läufe bleiben als solche erhalten. Nach zwei anfänglichen fehlenden Diagnosefeldern waren weitere Abbrüche ausschließlich QA-Einbindung: fehlende libatk auf dem Runner (durch vorhandenen isolierten Playwright-Container ersetzt), fehlender PRE4_IMAGE-Eingang und veralteter Summary-Selektor. Keine Sicherheitsbedingungen entfernt. Keine Änderung am Runner-System oder seinen Rechten.

**Ergebnis: gezielte Linux-Abnahme erfolgreich; noch keine vollständige Freigabe einer neuen Version.** Ausstehend sind ein vollständiger zusätzlicher HTTP-/Containerablauf genau für die neue No-Event-Erweiterung (inklusive JPEG/RAF/XMP-Familien), die vier realen NAS-Kollisionsinhalte und die native manuelle Nachabnahme von D7/E4/E6/UX. Die gesamte Backendmatrix sowie4000-Dateien-/14-iPhone-Gesamtmigration wurden für diese begrenzte Korrektur nicht erneut ausgeführt. Das ist keine Behauptung eines stabilen1.0.0-Standes. Empfehlung: Entwicklungskandidat Pre.6, Veröffentlichung nur nach gesonderter Freigabe.


## Ergänzung 03.11.2026 – vollständige authentifizierte No-Event-HTTP-/Container-Abnahme

**Ergebnis: PASS** – GitHub Actions [41612018382](https://github.com/heller-adrian/Bibliothekar/actions/runs/41612018382), Commit `cbb80e5a288052cfcff1da655e43d1e264f50fdb`. Der Anwendungscode ist unverändert gegenüber dem bereits gezielt abgenommenen Pre.6-Kandidaten; hinzugekommen sind ausschließlich `qa/pre6/no_event_http_container.py` und die isolierte Workflow-Einbindung mit Commitmarker `[pre6-http]`. Das Release-/Produktivimage wurde nicht verändert oder veröffentlicht.

Der isolierte Container baut das tatsächliche Anwendungsimage lokal und startet das vollständige Supervisor-/HTTP-System mit Anmeldung, CSRF und einem ausschließlich internen Docker-Netz. Aus synthetischen NAS-Ordnerquellen werden zunächst **8 JPG-Familien** über die echte Folder-Import-API importiert, als No-Event-Ereignis angelegt und ausdrücklich angewendet. Anschließend werden **16 neue Familien mit 18 Medien** aus einem zweiten Herkunftsauftrag importiert: 16 echte, mit ExifTool datierte JPEGs, ein TIFF-basiertes synthetisches RAF und eine XMP-Begleitdatei zur letzten Familie. Eine native echte Fujifilm-RAF wird **nicht** behauptet.

Die Erweiterung erfolgt ausschließlich über den authentifizierten `/api/jobs/{job_id}/no-event/assign-existing`-POST. Erfolgsnachweise:

- Gespeicherte geplante Erweiterung ohne physische Dateiverschiebung
- Zwei unabhängige vollständige `/api/workspace/summary?physical_refresh=true`-Prüfungen: keine falschen externen Verschiebungswarnungen; dieselben Quellen-/Katalog-/SHA256-Werte
- `/api/events/{event_id}/reconcile-plan?verify_sha256=true` bereit und blockerfrei; ausdrücklich bestätigter `/api/events/{event_id}/reconcile`-POST
- 18 von 18 Medien korrekt verschoben, vollständige Hashprüfung im tatsächlichen Zielbestand, erfolgreiches SQLite-Integrity-Check und abgeschlossenes Mutationsjournal
- Zwei echte Container-Neustarts nach dem Anwenden, anschließend erneute vollständige physische Inventur und Hashprüfung
- Beide gemounteten readonly-Testarchive byteidentisch
- Keine Manipulation historischer QA-Fixtures, Pre.5-Tag, GHCR oder produktiver NAS-Daten

Im Joblog: `{"status":"PASS","checks":{"old_no_event_applied_via_authenticated_http":"PASS","save_is_plan_not_physical_move":"PASS","two_physical_inventories_no_false_external_moves":"PASS","apply_18_files_16_families_two_restarts_hashes_archive_ro":"PASS"}}`.

Nachweisartefakt `pre6-targeted-evidence`, ID `13219526702`, von GitHub ausgewiesener Digest `sha256:b9e4df508c2e09f5adfd42f5d87d6266b6a98b5b0c737f6fd687fee11740e15b` (Download-/ZIP-Unabhängigkeitsprüfung in diesem Durchlauf **nicht separat behauptet**).

**Aktuelle Restpunkte:** Die vier tatsächlichen NAS-Zielkonflikte sind noch nicht anhand ihrer realen Bytes und Herkunftsbelege aufgelöst; native E6-Umbenennung, D7-/E4-/UX-Nachabnahme auf einem künftig installierten Pre.6-Image und die optionalen NFSv4-/Privilege-Tests bleiben offen. Das ist kein automatischer Release- oder Stable-1.0.0-Freigabebeschluss.
