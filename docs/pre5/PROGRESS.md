
## 31.10.2026 – gezielte Backend-Stabilisierung

41214162298 auf efb500279e34847d0a2dc485422304e945f31c64: 73/75 Fokusfälle
PASS, zwei FAIL. Beide RC11-Recovery-/Private-Lock-SIGKILL-Fälle und neun neue
exakt gebundene Domain-Recovery-Verträge bestehen. Artefakt13047268858 SHA256
39f54946acf3f887e34e5a0628305fb5cfee1203737bc95cb4e37c7e3844d324 verifiziert.
Der verbleibende RC4-Fall erreicht jetzt den tatsächlich offenen Finalizer;
ursprüngliche Reservation kind=trash/function=app.trash_failure.finalize_failure.
Nächster Fokus erweitert auf alle zwölf historischen Finalizer-Crashgrenzen,
Fremd-/Fehlbytes und vorhandene negative Wiederaufnahmeverträge. Originalnonce,
Fehlerstatus, Journal, unabhängige Rückfallkopien und dauerhafte Abschlussbelege
bleiben verpflichtend. Ein vorbereiteter Wiederaufnahmebeleg hält auch während
der laufenden Wiederaufnahme fremde Schreiber aus ihrem Wirkungsbereich fern.
Konfigurationsdiagnose muss ihren konkreten Fehler vor erneuter Ankerauflösung
behalten. Keine volle Matrix und keine Veröffentlichung gestartet.

Der nächste Fokus ergänzt die25 als ambient_registry_fixture_context erfassten
Nodes und die vollständige O2-Grenzprüfung. Der guarded Linux-Harness erstellt
seine explizit konfigurierte, bisher fehlende leere technische Installation vor
pytest in einem eigenen bewachten Prozess. Beleg enthält null Bibliotheken,
Jobs/Dateien und intakte Schemas. Keine produktive Missing-DB-Prüfung geändert.
O2 vergleicht sämtliche vorbestehenden privaten JSON-Bytes vor/nach Ablehnung
und verlangt weiterhin keine neuen Operationsnachweise. Die frühere Annahme,
dass keinerlei JSON existieren dürfe, widersprach der bereits angelegten state.json.
Byte-/Inode-/Katalog-/Generations- und echte SIGKILL-Grenzen bleiben geprüft.

Optionale getrennte Profilstufe[pre5-profile] erfasst ausschließlich die beiden
belegten Laufzeitfälle mit cProfile. Vorhandene90/300s-Deadlines, Assertions und
Audit-/F14-/SQLite-Guards bleiben aktiv. Profile werden auch nach FAIL gesichert.
Keine weiteren Reproduktions-, Frontend-, Container- oder Vollmatrixwiederholungen
in diesem reinen Diagnoselauf; Ausführung ebenfalls sequenziell auf safe-Runner.

41215262628 auf4a24b2575ef85a61fdbe6b4cc3d72d40c8e8c58a:76/89 PASS,
13 FAIL,0 ERROR/SKIP; Artefakt13047866550 SHA256
c0cd0f203710fb8f0fda138e9f2ba8e4e0cf42625a4db7db98c7e407e1c1ef80 verifiziert.
Die acht Legacy-Finalizerprozesse starten jetzt erfolgreich; anschließend
scheitert ihr JSON-Parser an erhaltenen Startup-stdout-Logs. Adapter leiten nur
Startupdiagnosen nach stderr, der gesamte Log bleibt erhalten. Vier private
Retention-Fixtures fehlen General/Batch-Anker: vor Beginn der simulierten
Altoperation vollständig bereitstellen, produktive Fehlankerprüfung bleibt.
Der neue positive Medientest verglich irrtümlich auch das zu aktualisierende
Journal; Vergleich erfasst jetzt ausschließlich alle tatsächlichen Stage-Medien.
Fremd-/Fehlbytes- und laufende Recovery-Schreibbarrieren bestehen bereits.
Alle erneuten Linuxbeweise für diese QA-Korrekturen noch PENDING.

41215645263 aufa292b916c1ff6fd032f99a8e6a36dcba616819ea:164/179 PASS,
15 FAIL,0 ERROR/SKIP; Artefakt13048875357 SHA256
5e3db9376c87ba7b2375eaa73c0fd67be73f9b328d7da4da14637e075b31af19 verifiziert.
Alle25 Ambient-Registry-Nodes und sämtliche O2-Verträge bestehen.13 bereits
erklärte QA-Folgefehler; zwei echte Planungsbarrieren vor bestätigter Varianten-
rettung. Neuer Schritt erweitert das gleiche Original-Lease-Protokoll auf
selektive und vollständige Papierkorblöschung mit vorhandenem passendem Journal
oder unveränderlichem F14-Fertigbeleg. Kein Journal fehlt als Erfolgsbeweis.
Explizite Retentionrettung braucht erneut die vorhandene Bestätigung, exakt
einen ursprünglichen Finalizer, unveränderte Rollen/Generationen, alle aktuellen
Varianten und den bestehenden privaten Retentionbeweis. Dauerhafter Entscheid
und Originalreservation bleiben erhalten; historischer Fehler bleibt failed.
Unbekannte/zusätzliche Intents blockieren; ein GET darf keinerlei Replaybeleg
anlegen. Negativtests und echte Abbruchgrenzen im nächsten Fokus enthalten.
Externe synthetische SQL-Beschädigung wird nun ausdrücklich separat aufgebaut;
die produktive SQLite-Schreibbarriere bleibt bestehen. Die alte Zwei-Katalog-
Fixture registriert ihre zweite Bibliothek vor Operationsbeginn ordnungsgemäß.
Automatischer Neustart nach API-Abschluss nur bei vorhandener alter Startup-
Diagnose; normale laufende Worker erhalten keine erneute Vollinitialisierung.

41215816086 ist der absichtlich getrennte Zweifall-Profillauf auf2ad5023e
(App=4a24b257), FAIL unter unveränderten90/300s-Grenzen. Artefakt13047948572,
SHA256 f5c51c12f6e625dd165d0c83c0258abb58bbc4b7758aea081423555609d37b3c
verifiziert.3892-Dateien:31574 require_write/inspect-Aufrufe,174,778s davon;
376,810s inklusive qualifiziertem Rollback nach der Deadline.100-Dateien:
5469 require_write-Aufrufe/62,497s bei88,750s Profilzeit, initialer Import
überschreitet mit Restablauf die90s-Grenze. Profiling beeinflusst Zeiten;
Callcounts und dominante Wiederholung sind nachgewiesen, kein neuer PASS.

Gezielte SQL-Korrektur: Verbindung/Cursor teilen nur den Evidence-Snapshot
innerhalb eines execute-Aufrufs. Jeder neue execute beginnt frisch; Skripte und
executemany behalten ungekürzte Prüfungen. Jede Aktion wertet weiterhin ihren
Tabellen-/Trigger-Wirkungsbereich und aktuelle Read-only-/Recovery-Kontexte aus;
keine zwischengespeicherte pauschale Schreibfreigabe. Sieben neue Positiv-/Negativ-
Verträge prüfen Verbindung/Cursor, Katalog/Registry, frischen Orphan zwischen
Statements, Orphan innerhalb eines SQL-Skripts und zusätzlichen Metadaten-Trigger.

Weitere belegte Darstellung-/Fixturefehler: identische Katalogfehler werden auch
nach zusätzlichem Strukturcheck dedupliziert; abgeleitete General/Batch-Anker
weisen ehrlich previously_observed oder not_observed aus. Alte Fixtureasserts
unterscheiden jetzt4 historische Rollen und2 nie gebundene Pflichtkinder.
Legacy-Namens-/Wave1-Fixtures legen die behauptete vollständige technische
Struktur vor Beginn an. Auth-only ohne Storage verlangt öffentliche503-Readiness
bei weiterhin401 für private Routen und keinerlei neu angelegten Appdaten.
Zwei Wortlautasserts prüfen den tatsächlichen präzisen Recovery-Fehlercode.
Neue Linuxergebnisse für diese Änderungen weiterhin PENDING; keine Vollmatrix.

Zusätzlicher Scope-Vertrag: Domain-Recovery öffnet nur weiterhin registrierte
Kataloge, wie die bestehende Trash-Recovery selbst. Ein ausgetragener Katalog
wird nicht aus seinem historischen Registrypfad neu angelegt oder geöffnet.
Deaktivierte, aber noch registrierte Bibliotheken bleiben einbezogen. Ein Journal
mit nicht registrierten DB-Verweisen bleibt abgewiesen. Neue synthetische Prüfung
behält den ausgetragenen Katalog bytegleich unter einem Retentionspfad.

Quellabgleich des bereits im Fokus enthaltenen Live-Deletion-Vertrags zeigt eine
zusätzliche Eintrittskollision: Eine frisch gestartete Recovery kann noch auf
den Trash-Lock eines laufenden normalen Schreibers warten. Ihr bloß lebender
F14-Beleg darf diesen Besitzer nicht selbst unterbrechen. Die zusätzliche
prozessübergreifende Resume-Sperre greift deshalb ausschließlich bei dem vor
Wiederaufnahme dauerhaft geschriebenen domain-recovery-intent derselben Nonce.
Die normalen F14-/Trash-Locks, Journale und SQLite-Prüfungen gelten weiterhin;
Startup besitzt außerdem seine bestehende gemeinsame Writer-Barriere. Der Test
für laufende Orphan-Recovery verlangt unverändert gesperrte fremde SQL-/Root-
Schreiber. test_recovery_waits_for_live_deletion prüft gleichzeitig den normalen
wartenden Recovery-Fall. Beide im nächsten Linux-Fokus, Ergebnis noch PENDING.

Der gezielte Reproduktionsjob enthält inzwischen mehrere ursachenbezogene
historische Gruppen statt nur der ursprünglichen60 neuen Fälle. Jobrahmen auf
45min angepasst; die einzelnen90/300s-Testgrenzen und die40min-Harnessgrenze
bleiben unverändert. Keine Testabdeckung reduziert und keine Produktfrist erhöht.
GitHub behält nur einen wartenden Lauf: Die nie gestarteten Zwischenstände
5c109d83/f47627ee wurden durch den jeweils neueren wartenden Fokus ersetzt.
Der laufende a4edf56e-Lauf wurde nicht unterbrochen. Keine parallele Vollmatrix.

## 31.10.2026 – begrenzte Schlusskorrektur im verbleibenden Kontingent

41217778080 vollständig ausgewertet:264 Fälle/260 PASS/4 FAIL/0 ERROR/SKIP,
1014,825s. Artefakt13049571446 SHA256
63302fc2692d83a237acfba303051098df85152ddffed06b07aacfcf0016184e verifiziert;
vollständige guarded Logs/XML und Workflow-Logs lokal gesichert.
Alle sieben SQL-Statement-Sicherheitsverträge PASS: Katalog/Registry und Cursor,
frischer Orphan vor erneutem Statement, Orphan innerhalb eines Skripts sowie
Metadaten-Trigger mit eigenem Scope. Keinen alten Freigabeentscheid wiederverwenden.
Vier konkrete Ursachen: neuer Confirmation-Setcheck wirft bei[]/{} TypeError;
Legacy-Live-Wipe-Fixture behauptet vollständige Struktur ohne General/Batch;
gezieltem Job fehlt bereits in der vollen Matrix vorhandenes tinycss2-Testwerkzeug.
Typcheck vor Bestätigung, vollständige Fixture vor historischem Startup und
gepinntes QA-Tool ergänzt. Keine produktive Rechte-/Ankerprüfung geändert.
Kleine Stufe[pre5-closure] prüft nur diese Fälle, alle SQL-/Domainverträge,
negative Legacy-Resetfälle und beide Laufzeitfälle OHNE Profiling unter den
unveränderten90/300s-Fristen. Danach normale60/82 Zieltests. Keine volle Matrix.

Zwei als source_text_contract klassifizierte Erwartungen hängen noch an der
früheren Ein-Funktions-Architektur. Historischen Konfigurationsvertrag durch
wirkliche Schema-/Configanlage, Reihenfolge und unveränderte bestehende Settings
belegt; Beobachtungsfunktionen werden nicht als erfolgreich gemockt. Der alte
0414-UI-Vertrag bleibt, zusätzlich sieben Ablaufvarianten der echten Ereignis-
Suche mit SQLite: GET/read_session bleibt bei explizitem/erstmaligem Refresh
rein lesend; zugelassener normaler Refresh ruft seine vorhandenen Inventarwege.
Die ausgetauschte Quelltextzeile verlangte gerade den inzwischen verbotenen
schreibenden Refresh innerhalb eines Read-Requests. Produktcode unverändert.
Separate[pre5-contracts]-Stufe prüft ausschließlich diese zwei kleinen Module;
kein erneuter Performance-, Container- oder Standardzieltestlauf dadurch.

## 31.10.2026 – ausschließlich unknown_control_evidence

41219852833:65/66 PASS, ein Legacy-Live-Wipe-Fehler. Artefakt13050100813,
SHA256 efa22efebbd5b972d7fda4979e350f5ea7ed118309373f9758b83a30534a0b25
verifiziert. Beide tatsächlichen Laufzeitfälle ohne Profiling PASS unter den
unveränderten Fristen:3892 Dateien213,948s,100 Dateien80,796s. Alle sieben
Statement-/übrigen gewählten Sicherheitsverträge bestehen.41220098240:
17/17 PASS, Artefakt13049483491 SHA256
fd574cf0f4af6709218f426cb42729f49ab52dc97f37c8a5503a9f61e9372ef6 verifiziert.

Eigentliche Lücke: Der reale F14-Produzent schreibt nach rein technischem
Startup technical-startup-<Nonce>.json dauerhaft. Die spätere leere Setup-
Qualifikation kannte diesen Beleg nicht und meldet unknown_control_evidence.
Keine Fixture-Ausnahme: nur exakte technische Receipt-/Reservationsstruktur,
Nonce/Dateiname, Datenbank, Workspace, IDs, Generation und alle fünf Bindungen
gegen aktuellen State qualifizieren. Frühere Generationen ausschließlich über
digestverknüpfte explizite SET-UP-AGAIN-Statehistorie, zyklus-/größenbegrenzt.
Weder SQL-/F14-/Recovery-/Read-only-Regeln noch Lösch-/Resetablauf geändert.
Belege bleiben unverändert erhalten. Jede unbekannte Datei/offene Operation,
Medien-/Registry-/Katalog-/Retentionhistorie und alle alten Token-/Lockprüfungen
bleiben Sperrgründe.13 neue Fälle verwenden einen vom echten ro.reserve erzeugten
Beleg, zeigen die bisherige Ablehnung und prüfen zwei explizite Wiederholungen
sowie Fremddaten/Nonce/Generation/Scope/DB/Binding/History-Angriffe.
[pre5-contracts] wählt diesmal ausschließlich diese neue Datei, den einen echten
Live-Wipe-/Restart-/Onboardingfall und die bestehenden negativen Resetfälle.
Die vorherigen17 Vertragsfälle bleiben unverändert im Testbestand/Full-Matrix.

## 31.10.2026 – zweiter technischer Receipt-Verbraucher geschlossen (ChatGPT/GitHub)

41221622586 auf bd9451206c6ac447e0d1d71f07fa4ee4263e25c2:
30/31 PASS, 1 FAIL (echter Live-Wipe-/Restart-/Onboarding-Fall).
Nach Erfolg der strengen `managed_storage_health`-Receiptprüfung blockierte
`storage_bootstrap.evidence` den identischen technisch abgeschlossenen
F14-Startup-Receipt noch als `bootstrap_additional_operation`.
Die Logzeilen benennen den exakten
`technical-startup-<Nonce>.json`-Pfad. Es ist eine zweite, nicht synchronisierte
private Kontrollnachweis-Allowlist; die ursprüngliche fachliche Diagnose wurde
dadurch bestätigt.

Anwendungscode-Commit ff11f88b8116bae5b0d39f824b1eef828d39e659:
`storage_bootstrap.evidence` verwendet unmittelbar vor der privaten
JSON-Inventur dieselbe read-only `_technical_startup_evidence`-Qualifikation.
Nur geprüfte Nonce, vollständiger Receipt, unveränderte Wirkungsbereichs-/
Datenbank-/Workspace-/Bibliotheks-/Generation-/Rollenbindung und digestverkettete,
bestätigte Setup-Historie autorisieren die **Einordnung als technischer Beleg**,
nicht eine Medienmutation. Ungültige Historien bleiben blockiert; keine
Datei wird entfernt, keine F14-/SQLite-/Read-only-/Lock-Prüfung gelockert.
Kein Eingriff in `main`, Tags, Registry-Images oder TrueNAS.

Gezielte Linux-Abnahme **41222109431 SUCCESS: 31/31 PASS,
0 FAIL/ERROR/SKIP** in 40,11 s. Originaler Live-Wipe-/Wiederanlauf-/
Ersteinrichtungstest besteht jetzt vollständig; zusätzlich die 13
technischen Positiv-/Negativfälle und 17 negativen Legacy-Resetvarianten.
Das Reproduktionsjob-Artefakt 13050372420 wurde veröffentlicht; GitHub
meldet ZIP-SHA256
`0df7bbe15f1d5e3f9ba0300f7ab8e8f46de42f560263deb5341223e6d054cd33`.
Workflowlog vollständig gelesen; keine zusätzliche unabhängige
ZIP-Downloadprüfung. Fünf Warnungen im Pythonlauf, keine Fehler.
Container-, Frontend- und Backend-Volljobs in dieser Runde absichtlich SKIPPED.

Die **globale pre.5-Freigabe ist weiterhin NICHT erfolgt**. Der alte 2444er
Backendlauf 41194643144 enthält 240 damalige Fehler. Von den ursprünglichen
Nodes stehen 147 noch ohne erneute gezielte Abnahme; die bestehende
`BACKEND-FIX-STATUS.json`-Inventur wurde durch diese Mini-Runde nicht
automatisch aktualisiert. Vor einem Release sind aktuelle vollständige
Backend-, Frontend-, Browser- und Container-Evidenzen Pflicht.

## 31.10.2026 – vollständige Diagnoseprotokollierung (Freigabe: Diagnose, nicht Reparatur)

QA-only-Commit a00c51a7 schloss den Artefakt-Uploadpfad und ergänzte eine
sequentielle, voneinander unabhängige 24-Fall-Stichprobe über zwölf offene
Kategorien. GitHub [41226158077] komplett ausgeführt: **4 PASS, 20 FAIL,
0 ERROR/SKIP, 0 fehlende XML-Fälle**. Drei Gruppen: 3/9, 1/7, 0/8 PASS.
Vollständiges Archiv 13051308412, verifizierter ZIP-SHA256
98cc15f4a128b2edf1e3723e7d1c0974f23cc0d9998ce9065f13c6459131ad9b.
Details mit Einzelteststatus, tatsächlichen Stacktrace-Symptomen und nächsten
Prüfgrenzen in `docs/pre5/DIAGNOSTIC-20261031.md`.

Die 20 roten Stichproben zeigen: F14-Operation-Recovery-Gates, echte
Jobzustands-/Restore-Journal-Probleme, eine fehlende General/Batch-Fixture,
teilweise veraltete GET-Konflikterwartungen und F15/17-SQL-/Metadata-Verträge.
**Dies sind vorläufige Fehlergruppen, keine 20 unabhängigen Produktfehler.**
Keine Anwendungscodereparatur genehmigt oder ausgeführt. Die vollständigen 147
und die finale Backend-/Frontend-/Container-Matrix bleiben offen.
**v1.0.0-pre.5 bleibt gesperrt.**

## 31.10.2026 – gerichtete Fixture- und Read-only-Vertragsabnahme

- **41226912195 / cc4cbe47**: 3/3 PASS, 0 ERROR/SKIP. Der technische
  Registry-Seed erstellt absichtlich keinen Hauptkatalog; die bisherige RC9-
  Erwartung `catalog_unavailable==0` war deshalb falsch, obwohl
  `can_setup_again` und die unveränderten Archivbytes korrekt waren.
  Die zweite alte 0562-Fixture hatte vor SIGKILL `General` und
  `Batch Correction` nicht angelegt; Vorbelegung nun im Worker-Test,
  Original-Zwei-Abbrüche-/Recovery-Vertrag besteht. QA-/Testdateien allein.
  Artefakt13050924946 SHA256
  `861f500dc3d1f98568ac6a46e798a291a92e6322d5589d930f93046d6f1bc7d0`.
- **41227115670 / 9d934a2d**: 2/2 PASS, 0 ERROR/SKIP.
  Zwei B01-Altverträge wurden nicht einfach abgeschwächt: Sie beweisen
  lesende GETs unter aktivem Inventory-Writer bzw. bei zwei gleichzeitigen
  Leseabfragen, inklusive unveränderter privater F14-Nachweise, Medienbytes
  und geprüfter Datenbankwerte. Die alte GET-409-Annahme und der
  tote Kompatibilitäts-Link-Hook werden dadurch durch direktes Verhalten
  ersetzt. Artefakt13052108489 SHA256
  `1d75aaad3cee8dabf877b66c051f94b0801e1e9601fec22e0cf2e0b075370184`.
- Beide ZIPs nach Download unabhängig gehasht und alle fünf JUnit-Testcases
  geprüft; keine Anwendungscodeänderung. Vier ursprünglich rote Nodes bestehen
  jetzt, RC9-legacy_roots als zusätzliche positive Kontrolle.
- Weitere B01-Lock- und fachliche Recovery-Fälle sind NICHT hiermit abgenommen.
  Letzte breite Matrix bleibt rot; Pre.5-Veröffentlichung gesperrt.

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
