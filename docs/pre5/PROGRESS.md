
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

## 01.11.2026 – vollständiges 58er-Inventar und gemeinsame Ursachen

Alle58 Original-Nodes aus dem verifizierten Run41231600475 einzeln erfasst;
Benutzerpaket250/250 Dateien bytegleich zum GitHub-Artefakt13055435531.
Vollständiger Bericht: BACKEND-REPAIR-58-20261101.md/.json.

- 4682b22a: verifizierter Restore-Konflikt darf Originallease abschließen,
  während sein Konfliktjournal Auswahl und Ziel weiterhin reserviert.
  Run41260071820:24/24 PASS, inkl. aller15 kritischen Original-Nodes.
  Artefakt13064419670 SHA256 b40faee8dd967452de7221d03a30cc1bdf536a157db650e2bd64675d896c7ba3.
- bd168d53: Metadaten-Ablehnung vor dauerhafter F14-Zulassung.
  Run41260399276:26/33 PASS. F18 beide PASS; F15 SQL-/Projektion behoben,
  sieben Testfehler verbleiben (belegte Fixture-Anker, Worker-Interface,
  Ein-Sekunden-Delta neuer Batch-Gegenprobe). Artefakt13065735420 SHA256
  8857f69740ff2017992562bc97dac56d9ae1ebe8735a851500687ff85be0ca9c.
- efd1dbdf: begrenzter Original-Sortier-Replay mit eigenem vollständigen
  Registry-/Run-/Root-/Hashnachweis. Assets/committete/mehrdeutige Zustände
  bleiben gesperrt. Sechs neue Negativfälle; Linuxnachweis noch PENDING.
- 68364546/969e591d: bekannte Restore-Konflikte kontrolliert vor unabhängiger
  neuer Trash-Operation qualifizieren; reservierte DELETE-Auswahl vor
  Intent-Publikation ablehnen; Prüfung vor tatsächlichem Staging bleibt.
- 5ffa9175: reentranten Metadaten-Lock zusätzlich an PID/Thread binden;
  kopierter Context darf keinen fremden Eigentümer simulieren. SQLite-
  Statement-/Schema-Authorization und B01 im gezielten Folgemanifest.
- f91865d2: ausschließlich belegte Fixture-/Batch-Erwartungen korrigiert.
- c06294e5: geprüfter Exception-Rückbau behält Löschjournal bis zum Abschluss
  der originalen F14-Lease. Keine Freigabe aus Journal-Abwesenheit.
- e9061f41: vollständige Diagnose des ungeklärten leeren Vier-Ordner-Falls.

Letzte Einzelwerte der ursprünglichen240 Fehler über verschiedene Commits:
189 PASS /51 FAIL. KEINE finale Abnahme. Aktuell41261174452 läuft auf5ffa9175;
41261700576 aufe9061f41 wartet als kumulierter nächster Fokuslauf.
Noch keine volle147er-Wiederholung, keine Backendmatrix/Frontend/Container auf
finalem Quellstand. BACKEND NOT ACCEPTED; keine Veröffentlichung.

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

## 01.11.2026 – Nachlauf41301247703 vollständig ausgewertet

Source `bcf729e163665772a5ccfb79448bf8820011336d`: **74 PASS /15 FAIL /0 ERROR/SKIP von89**. Artefakt13081824373 SHA256 `dde02d89ec8c5899b57e0d3fe47f55f6eb0bb127e0f09373d81b91a31fe1d0bd`, unabhängig heruntergeladen/verifiziert. Alle15 exakten kritischen Originalnodes PASS; vollständige BA-02(11), B01(10), Statement-Authorization(7), SQLite-Authorization(8), F14-Backup-Abschluss(4), neue8 Finished-Receipt- und5 SD-Gegenproben PASS. Vier frühere Prozess-Exit-Negativfälle bestehen mit tatsächlicher SQL/F14-Schreibablehnung.

Die15 roten Fälle enthalten12 alte Nodes und3 neue Import-Statusfälle. Quelle des neuen Produktfehlers: `root_operations._identity` akzeptiert ausschließlich Verzeichnisse, wurde aber für die SQLite-Datei verwendet. `5025a5ba` ersetzt dies durch eine eigenständige reguläre Datei-/O_NOFOLLOW-/nlink1-/Inode-Qualifikation mit erneutem Check vor SQL-Commit; fünf zusätzliche Dateityp-Gegenproben. Noch kein Linux-PASS für diesen Fix.

`40f7bba8` bindet den prospektiven Library-Swap-Proof zusätzlich an DB-Inode und interne Bibliotheksidentität. Identische fremde Ersatzinodes und ein ersetzter Katalog können nicht nachträglich als eigener Bestand übernommen werden. Zwei zusätzliche negative Fälle. Alle neuen Library-Fälle bleiben bis zu ihren Linuxartefakten PENDING. Historische Library-Zustände ohne vorher vorhandenen Ownershipbeleg bleiben ausdrücklich geschützt.

Kumulierte Einzelwerte der ursprünglichen240:228 PASS/12 FAIL; ursprüngliche58:46 PASS/12 FAIL, über verschiedene Commits. KEINE finale Abnahme.41303055310 auf fb2412c0 läuft bereits; keine Vollmatrix/Veröffentlichung.

## Gesicherter Fortsetzungsstand / gezielte Nachläufe

Aktueller QA-Source `7045766e1a94d4b053c1867dbd613cb8177176c9`, letzter Anwendungscode `4e0e35527d95e58fafd77f13fc209105396c40fe`. Zusätzliche native Library-Autorität verlangt den tatsächlich gehaltenen PID-/Thread-Schreibkontext; kopierte Kontexte liefern keine Autorität. Alle Änderungen sind auf dem Entwicklungsbranch gesichert.

Zuerst41303055310 (fb2412c0; zuletzt RUNNING), danach41303789143 (7045766e; zuletzt PENDING) auswerten. Der zweite prüft den korrigierten DB-Dateihelfer und neue prospektive Library-/DB-/Inode-Grenzen samt F15/F17/F18. Keine weiteren Läufe anstoßen, solange diese ausstehen. Noch keine vollständige Backend-/Browser-/Containerabnahme auf finalem Anwendungscode. **BACKEND NOT ACCEPTED – Veröffentlichung gesperrt.**


## 02.11.2026 – Veröffentlichung: kontrollierter Teilzustand

Run41515697003: Source/QA, 21 Delta-Verträge, finale Container-/Browser-/90-/4000-/14-iPhone-Abnahme und echter Digest-Pull/OCI PASS. Git-Tag b4c3 und GHCR-Digest3c36813f… bestehen. GitHub-Anlagenupload scheiterte an leerer QA-SOURCE-DIFF.patch HTTP400; Release anschließend per Tag/ID404. Kein Retry oder Überschreiben. Details und unabhängige Artefakt-Prüfsummen in release/PARTIAL-PUBLICATION-20261102.md/.json. Native TrueNAS-Abnahme weiter offen.
