# Bibliothekar pre.5 – Fortsetzung

Stand: 2026-10-30. Branch `codex/pre5-operation-recovery`.
Ausgangspunkt: veröffentlichtes `v1.0.0-pre.4`, Commit
`adcc2aa9a444042440ff764be10fe1e42191904d`.

Beide vollständigen Auftragsunterlagen vom 30.10. gelesen. Keine NAS-Zugriffe.
Budget zunächst ungefähr 10–15 Wochenprozentpunkte; spätestens bei 80 % des
Fünf-Stunden-Fensters reproduzierbaren Zwischenstand sichern. Anfang: beide
Anzeigen 0 %, nächster Check: fünf Stunden 6 %, Woche 1 %.

## Befund / nächste Schritte

- GET Workspace ruft schreibende `compatibility_workspace_root()` auf.
- `operation_health` sperrt nach jeder verwaisten Reservation den gesamten
  Workspace. Unbekannte Wirkungen müssen weiter geschützt bleiben, bekannte
  unabhängige Bereiche benötigen eine belastbare Freigabe.
- Erster Inventory-Abbruch auf TrueNAS bislang nicht bewiesen. Zuerst drei
  Dateiwege getrennt und kombiniert gegen unveränderten Release-Code testen.
- Noch keine pre.5-Anwendungsänderung oder Veröffentlichung. Vorhandene
  unversionierte Datei `qa/rc14.zip` gehört nicht zu diesem Auftrag.

Nächster Schritt: Linux-Reproduktion mit eng begrenztem Self-Hosted-Workflow;
danach Architekturkorrektur, gezielte und vollständige fachliche Abnahme.
Veröffentlichung erst nach allen verbindlichen bestandenen Prüfungen.

## Erster Reproduktionsstand

`724a683f` / Lauf `41069647270`: GET false/true jeweils HTTP 500; unabhängige
Bibliothek durch Inventory-Intent gesperrt. Ereignisfixture zunächst fehlerhaft
(fehlender synthetischer Job); korrigiert in `a95415b2`, Lauf `41070150506`.
Dort Applied-Verschiebung, Archivkopie und deren Kombination ohne Scan-Absturz.
Tagesbestand-Test benötigte vorherigen initialen Inventarscan (Sentinel);
dieser wurde ergänzt. Ursprünglicher NAS-Auslöser weiterhin nicht bewiesen.

In Arbeit, noch nicht abgenommen: private prozesslokale Pfadansicht ohne
F14-Schreibreservation; transiente, streng auf drei geprüfte Medien-Lesescanner
begrenzte Reservationsart; qualifizierter historischer Inventory-Abschluss mit
vollständigem Originalrecord im dauerhaften Unterbrechungsnachweis.
Syntaxprüfung erfolgreich; vorhandene JS-Escape-SyntaxWarning in main.py.

Weiter offen: scoped Schreibzulassung für echte Fachkonflikte, Startup/DB-
Diagnose, vollständige GET-Prüfung, Metadaten-Variante A, echte Container-/API-
Reproduktion und sämtliche Freigabetests. Noch keine Release-Eignung.

## Architekturintegration (noch nicht abgenommen)

Lauf `41070853477` zu `f63eadd4`: 15/16 erfolgreich. GET false/true und alle
sieben Kombinationen bestanden. Verbleibender Testfehler: falscher Tabellenname
`settings`; auf echte Spalten von `app_settings` korrigiert.

Neue zentrale Ressourcenklassifikation: ausschließlich registrierte geschützte
Fachfunktionen erhalten begrenzte Bereiche. Unbekannte Wirkungen sperren weiter
Workspace-Schreibzugriffe. General-Konflikte sichern den Metadatenbereich;
unabhängige Katalog-/Importaktionen erhalten eigene Zulassung. SQLite-
Authorizer und Queue-Claim prüfen dieselbe Zulassung. Ein gesperrter Job bleibt
queued. Keine fingierte Fertigstellung.

Read-only-Datenbankdiagnose und begrenzter Workerstart nach fachlich
unterbrochenem Startup integriert. Ungeprüfte Domain-Recovery wird dabei nicht
fortgesetzt. Zieltests und anschließend historische Tests laufen erst nach
dem nächsten Push. Letzter Budgetcheck: fünf Stunden 18 %, Woche 3 %.

## Lesepfade und engere Metadatensperren

`77b081b0` / Lauf `41071741377`: 22/23 Zieltests bestanden; fehlendes Release-
Tag im flachen Actions-Checkout verhinderte ausschließlich den Originalcode-
Subprozesstest. `fetch-depth: 0` ergänzt. Lauf `41073034252` auf `ec4035c4`:
alle gezielten Tests bestanden; historische Tests bei letzter Abfrage laufend.

Danach (noch nicht getestet) integriert: Normal-GETs verwenden `read_session`,
beobachtende Scanner besitzen reine Snapshot-Pfade; expliziter POST
`/api/workspace/refresh` für Reconciliation mit UI-Aufruf. Datenbankdiagnose im
vorhandenen Dashboard eingebunden. Attestierte private Kompatibilitätsansicht
statt Erkennung nach festem /tmp-Pfad, einschließlich echtem Trash-Ziel.
Einzel-General-Konflikte können dateibezogen begrenzt werden; ein unqualifiziertes
Swap-Journal schützt weiterhin den gemeinsamen Metadatenbereich. Eigene aktive
Journale benötigen exakt passenden privaten Task-/Reservationsnachweis.

Nächste Pushes führen zunächst nur die kurzen Zieltests aus. Historische Stufe
wird mit `[pre5-historical]` in der Commitnachricht aktiviert. Keine vollständige
Container-/Browserabnahme und keine Veröffentlichung erfolgt. Budget zuletzt:
fünf Stunden 34 %, Woche 5 %.

## Breitere Abnahme / aktuelle Korrekturen

`41073034252` (auf `ec4035c4`): Zieltests bestanden; historische Stufe
**204 PASS / 33 FAIL**. 32 Fehler: bei unregistrierten Legacy-Servicefixtures
persistierte der transiente Scanner keinen initialen technischen State, während
`check_active()` dessen Vorhandensein korrekt verlangte. Korrektur: erstmalige
technische Bindung persistieren, keine Operationsreservation. Verlorener State
einer registrierten Installation bleibt ausdrücklich gesperrt (neuer Negativtest).
Ein weiterer Fehler: alte globale Worker-Sperrerwartung, jetzt auf unabhängige
Workerfreigabe mit weiter wirksamer Metadaten-Schreibsperre umgestellt.

`41074557116` (`687fccf0`): vier Zielfehler aus Tests: falscher Modulimport
`library_context` statt `library_runtime`; drei erwartete fachliche 409 für einen
nicht erforderlichen Nachsortierplan wurden fälschlich als 200 erwartet. Korrigiert;
die Prüfkette kontrolliert weiterhin unveränderte Kataloge/F14-Belege nach GETs.

Noch nicht gepusht/getestet: neue reine GET-Beobachtungspfade, expliziter POST-
Refresh, UI-Diagnose, korrigierte Altfixture-Kompatibilität. Nächster kurzer Lauf
enthält neue Zieltests plus die zuvor fehlgeschlagenen Provenienz-/Beobachtungstests;
erst danach wieder vollständige historische Stufe und echte Container-/Browser-QA.
