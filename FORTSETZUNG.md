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

## Kontrollbindung korrigiert / erste Containerstufe vorbereitet

`ad3dc60e` / `41075576005`: neue Ablehnung registrierter Installationen ohne
Kontrollstate deckte eine Provisionierungslücke auf: `register_library()` ließ
die erste Registryzeile vor ihrer technischen F14-Bindung sichtbar werden.
Korrigiert in `937299bd`: erste explizite Registrierung bindet unter den
vorhandenen Locks ihre Anker vor dem Registry-Commit. Bei bereits vorhandenen
Registryzeilen und verlorenem State wird weiterhin abgebrochen; kein Reset.

Lauf `41076413534` auf `937299bd`: alle neuen Zieltests PASS. Fokussierte
historische Stufe **45 PASS / 1 FAIL**: Fixture `test_0440_trash` fehlte eine
`settings.json`. Datei ergänzt, Schutzprüfung nicht geändert.

Weiter implementiert, nächster Lauf ausstehend: globale Papierkorboperationen
mit geprüftem Funktionsnamen besitzen einen gemeinsamen Trash-/Katalogbereich;
ein unabhängiger General-Konflikt sperrt diese nicht pauschal. Neuer Test führt
echten Import, Papierkorbaufnahme, Restore und bestätigte Löschung aus und
prüft unveränderte Herkunfts- sowie ursprüngliche Konfliktnachweise.

`qa/pre5/container.py` + `browser.cjs`: frischer Supervisor, zwei Bibliotheken,
realer General-Import und Neustarts; Original-pre.4-Inventarabbruch per
kontrolliertem Lesefehler bei gestoppter App, Upgrade-Qualifikation derselben
Reservation; echter abgeschlossener JPEG-Auftrag mit fehlgeschlagenem F14-Ack,
danach externe Entfernung seiner synthetischen Arbeitskopie. Erwartung:
unabhängiger HTTP-Import und Ereignis-Sortierung + zwei Neustarts erfolgreich,
ursprünglicher ungeklärter Auftrag bleibt erhalten. Noch NICHT ausgeführt.

Containerjob wird nur mit `[pre5-container]` in einer Commitnachricht aktiviert
und läuft erst nach bestandenen kurzen Gates. Er enthält zusätzlich pre.4-
Generalfence-/Browserfälle, historische Containerfälle, 4.000 Dateien und 14
iPhone-JPEGs. Alle Jobs auf dem dedizierten Self-Hosted-Runner; kein GHCR-Push.

Offen bleiben vollständige Backendmatrix, Containerresultate, 90/47/8-Datei-
Anwendungsablauf, weitergehende Fehlerszenarien und Releaseunterlagen. Variante A
ist noch nicht umgesetzt: unveränderte Herkunfts-/Zielkollisionsnachweise benötigen
ein ausdrücklich getrenntes Kopien-/Reimportmodell; Schutz nicht einfach entfernen.
Keine Veröffentlichung erfolgt. Nächster Budgetcheck vor dem Containerjob.

## VERBINDLICHER FORTSETZUNGSPUNKT – Ende dieses Kontingentfensters

Branch: `codex/pre5-operation-recovery`.
Letzter Anwendungscode: **`969bc49f6138a0badf0dfa0361e2a4862a08e1ef`**.
Nachfolgender Commit aktualisiert ausschließlich diese Übergabe und Nachweise.

Aktueller Nachlauf: **41080385540**, bei letzter Abfrage `in_progress`.
Er führt 34 neue Zieltests und die fokussierte historische Auswahl aus.
Nur bei deren Erfolg startet die neue Container-/Browserstufe. Der Publisher
existiert für pre.5 noch nicht; dieser Workflow kann nichts veröffentlichen.

### Letzte Ergebnisse und Korrektur

- `41078906708` / `5c6f868b`: **32 PASS / 1 FAIL**. Tatsächlicher Fehler:
  SQLite-Authorizer klassifizierte `metadata_candidates` wie offene General-
  Korrekturaufträge und blockierte dessen FK-Cascade beim bestätigten Löschen
  einer unabhängigen Papierkorbdatei. EXIF-Kandidaten sind Dateikatalogdaten;
  echte Korrektur-/Kontrolltabellen behalten ihre Metadatensperre.
- `41079916862` / `668ba136`: **33 PASS / 1 FAIL**. Der Papierkorbfall besteht.
  Neu verschärfte APPLY-Qualifikation benötigt den privaten Tasknachweis schon
  vor Eintritt in APPLY. Bisher erzeugte APPLY ihn erst nach seiner Zulassung.
  Korrigiert in `969bc49f`: EXECUTE bindet seinen gespeicherten General-Task
  unmittelbar nach dessen Anlage, vor dem verschachtelten APPLY. Dessen
  vorhandenes idempotentes `bind_task()` bleibt erhalten. Ergebnis ausstehend.
- Syntaxprüfung und `git diff --check` erfolgreich. Bestehende SyntaxWarning
  zu JS-Escape `\.` in main.py nicht als Laufzeitfehler umgedeutet.
- Letzter Budgetcheck: Fünf-Stunden-Fenster **78 %**, Woche **12 %**. Geordneter
  Stopp vor Erschöpfung gemäß Nutzerauftrag; keine weitere Freigabe erforderlich.

### Nachweise

`41076413534` / `937299bd` wurde kryptografisch nachgeprüft:
Artefakt **12988280542**, ZIP-SHA-256
`3d832596b79594a232cc17fe37269a8107aede9666b98f6c1f0e462033cfc01d`.
JUnit: **32 neue PASS / 0 FAIL / 0 SKIP**; fokussierte Auswahl 45 PASS / 1 FAIL
(fehlende settings.json der Testfixture, inzwischen ergänzt). Diese früheren
Ergebnisse sind ausdrücklich keine Abnahme des später geänderten Anwendungscodes.
Lokale heruntergeladene Logs/Artefakte: `/private/tmp/bibliothekar-pre5-evidence/`.

### Exakte nächsten Schritte

1. Aktuelle Limits lesen; beide Originalaufträge vollständig verfügbar unter
   `/Users/adi/Downloads/Codex_Auftrag_Bibliothekar_v1.0.0-pre.5.md` und
   `/Users/adi/Downloads/Bibliothekar_pre5_TrueNAS_Befunde_2026-10-30.md`.
2. Zuerst **41080385540** lesen, keine neue CI blind starten. Bei FAIL ausschließlich
   fehlgeschlagene Stufe diagnostizieren. Bei SUCCESS Artefakt-Digests prüfen.
3. Falls der Containerjob gestartet ist, besonders prüfen:
   - `qa/pre5/container.py`: tatsächlicher pre.4-Inventarabbruch und identische
     Reservation nach Upgrade; abgeschlossener General-Task mit unterbrochenem
     F14-Ack und extern entfernter synthetischer Kopie; danach tatsächlicher
     HTTP-Import, Ereignisanlage/-sortierung und zwei Neustarts trotz Konflikt.
   - Snapshot qualifiziert Dateiorte aus Katalog-/Ereigniszuordnung. Keine
     Dateinamenssuche als Recovery-Autorität.
   - `qa/pre4/container.py` / `historical_container.py`, 4.000 Familien und 14
     iPhone-JPEGs bleiben zusätzliche Gates. Browser jeweils DE/EN, 390/1440 px.
4. Vollständige historische Python-Stufe mit Commitmarker `[pre5-historical]`
   nach grünen kurzen Gates neu abnehmen. Die frühere breite Stufe war
   204 PASS / 33 FAIL und ist nicht abschließend nachgeprüft.
5. Tatsächlichen 90-Dateien-/47-Familien-/8-Tage-Anwendungsablauf mit Applied-
   Verschiebung, Archivkopie und Tagesbestandsverschiebung vollständig ergänzen.
   Bisher sieben kleinere Kombinationen über reale Fachmodule bestanden;
   ursprünglicher NAS-Auslöser bleibt ohne Erstexception nicht bewiesen.
6. Weiterer Sicherheits-Audit: negative Mount-/Anker-/DB-Fälle, mehrere offene
   Operationsarten, SIGKILL, parallele Requests; Vollständigkeit der Schema-
   Diagnose prüfen (Verbindung/Integrität/Fremdschlüssel/Version/benötigte Tabellen).
   Reale unbekannte Wirkungen dürfen weiter nicht freigegeben werden.
7. Vollständige Backend-/Frontend-/Sicherheitsmatrix erst nach Stabilisierung
   der gezielten Gates. Vorbild `qa/rc13/regression.py`; alle neuen Jobs ausschließlich
   `[self-hosted, Linux, X64, bibliothekar-safe]`, keine Hostpakete/-rechte ändern.
8. Gewünschte Metadaten-Variante A ist noch OFFEN. Bekannte Aufnahme wird beim
   General-Reimport weiterhin bewusst abgelehnt. Kein Entfernen des SHA-Guards
   ohne saubere Kopienidentität, Herkunft und Kollisionsprüfung; ggf. begründet
   deferieren, wie der Auftrag ausdrücklich zulässt.
9. Erst nach vollständig erfolgreicher Abnahme Version, Dokumentation und
   eigenständigen abgesicherten Publisher vorbereiten; Quelle/Image byteweise,
   OCI-Index/Manifest/Konfiguration, tatsächlicher Digest-Pull, Release-Anlagen
   und SHA-256 prüfen. Keine bestehenden Releases/Images/latest überschreiben.

CLI (authentifiziert, keine Tokens ausgeben):

```sh
export GH_CONFIG_DIR=/private/tmp/bibliothekar-gh-device
export GH_BROWSER=true
export GH_DEBUG=
export GODEBUG=http2client=0
/private/tmp/bibliothekar-gh-cli/gh run view 41080385540 -R heller-adrian/Bibliothekar --json status,conclusion,jobs
/private/tmp/bibliothekar-gh-cli/gh run view 41080385540 -R heller-adrian/Bibliothekar --log-failed
```

`GODEBUG=http2client=0` vermeidet beobachtete HTTP/2-Abbrüche beim Log-/ZIP-Download.
Git-Netzwerkzugriff mit bestehendem gh-Credentialhelper wie in dieser Session;
keine neuen Zugangsdaten anfordern, sofern die bestehende Anmeldung funktioniert.
Actionlint: `/private/tmp/pre-actionlint/actionlint -config-file docs/pre/release/actionlint.yaml .github/workflows/qa-pre5-operation-recovery.yml`.
Lokale Pythonaufrufe nur Syntaxprüfung, keine Mac-Abnahme; ausführende Tests laufen
isoliert auf Linux. Keine Subagents einsetzen. `qa/rc14.zip` war vorher unversioniert
vorhanden und bleibt außerhalb sämtlicher Commits.

**Freigabestatus: NICHT ERTEILT DURCH TESTERGEBNISSE / NICHT VERÖFFENTLICHT.**
Native TrueNAS-/NFSv4-, physische SD-/USB- und echte DNG-1.7-Schreibtests: NOT_RUN.
Kein Zugriff auf NAS, keine Datenbereinigung, keine Änderung früherer Releases.

## Fortsetzung: Sortierstatus im Container (2026-10-30)

Neues Kontingentfenster: fünf Stunden 0 %, Woche 15 %; Checkpoint künftig bereits
bei 70 % des Fünf-Stunden-Fensters beginnen, um rechtzeitig fertig zu sichern.
`41080385540` auf Anwendungscode `969bc49f`: Zieljob SUCCESS, Containerjob FAIL.
Nachgewiesen falsche QA-Annahme: `sort_runs.status` ist erfolgreich `applied`,
nicht `completed`. `TERMINAL_RUN_STATUSES`, der tatsächliche SQL-Abschluss in
`sort_apply.py` und API-Ausgabe stimmen überein: terminal=true, progress=100,
completed_at vorhanden, error_message=NULL, verified/moved counts vollständig.
Nur QA korrigiert: auf terminal warten, anschließend exakt applied und sämtliche
Abschluss-/Zählerbedingungen verlangen. Kein Produktstatus umgedeutet.
Nächster Lauf führt nach kurzen Gates die historische Stufe und Containerstufe aus.
