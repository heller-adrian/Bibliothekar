
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
