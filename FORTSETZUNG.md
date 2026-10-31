# Bibliothekar pre.5 – Fortsetzung, 31.10.2026

## Sofortiger Einstieg – ausschließlich Legacy-Setupfehler

Branch `codex/pre5-operation-recovery`.
Anwendungscode: **bd9451206c6ac447e0d1d71f07fa4ee4263e25c2**.
**Zuerst41221622586 auswerten** (zuletzt in_progress). Ausschließlich:
13 neue technische Receiptfälle, ursprünglicher Live-Wipe-/Restart-/Onboarding-
Fall und17 vorhandene negative Legacy-Resetfälle. Kein vollständiger Workflow,
keine Performance-/Container-/Standardzieltestwiederholung. Die Auswahldatei
qa/pre5/backend_contracts.json ist für diese Runde auf diese31 Fälle begrenzt;
alle übrigen Testdateien und die volle Matrix bleiben vollständig vorhanden.

Aktueller Benutzerauftrag ausschließlich unknown_control_evidence klären.
KEINE Veröffentlichung, Tags, Images/latest/main oder TrueNAS verändern.
Gesamtabnahme folgt später in eigener Runde; danach Benutzerentscheidung zur
Veröffentlichung. Frühere automatische Freigabe für diese Runde NICHT verwenden.
Fünf-Stunden-Anzeige90%, Woche57%: jetzt geordnet gesichert stoppen.
Diese Runde bei83% begonnen, etwa acht Punkte als Arbeitsbudget gewählt;
Reserve erhalten. Keine aktive Warteschleife oder weitere CI-Läufe starten.

### Nachgewiesener Befund / gezielte Korrektur

41219852833 auf f0e69247:65/66 PASS, ein Fehler in
 test_incomplete_live_wipe_then_process_restart_and_confirmed_onboarding.
setup_blocker=unknown_control_evidence nach erfolgreichem realem ersten Startup.
Der F14-Produzent schreibt nach rein technischer Vorbereitung dauerhaft
technical-startup-<Nonce>.json (root_operations.reserve); die spätere private
Setup-Whitelist in managed_storage_health.setup_again_evidence kannte diesen
selbst erzeugten technischen Abschlussbeleg nicht. Produktlogiklücke, keine
weitere pauschale Fixture-Ausnahme.

_technical_startup_evidence qualifiziert nur exakte Receipt-/Reservationsfelder,
Nonce/Dateiname, kind=startup, _TECHNICAL_STARTUP_IDS, library=main, DB-Pfad,
Workspace und genau Workspace+vier EN-Rollenbindungen. Generation/Identitäten
müssen zum aktuellen State passen. Alte Generationen nur über vollständig
SHA256-verknüpfte explizite SET-UP-AGAIN-Historie; Zyklen/mehr als64 Links gesperrt.
Erkennung bleibt read-only, Originalbelege werden nicht gelöscht/umgeschrieben.
Alle bisherigen Medien-/Katalog-/Registry-/Retention-, Token-, Kernel-Lock-,
ACL-/F14- und Pending-Operation-Prüfungen bleiben aktiv. Keine Änderungen an
SQLite-Optimierung, F14-Produzent, Root-Locks oder Read-only-/Recoverycapabilities.

Neue Regression erzeugt Receipt mit echtem ro.reserve und reproduziert die
alte Ablehnung bei fehlender Erkennung. Danach zwei explizite Resets, Original-
receipt bytegleich. Negative Varianten: falsche Art/IDs/DB/Bindung/Generation/
Nonce, zusätzlicher Wirkungsbereich, kaputtes JSON-Format, Fremd-JSON, offene
Operation, Medienbestand und manipulierte Historien-Digests. Ergebnis PENDING.
Originaltest muss bis bewusster Wiederaufnahme UND erster Bibliothek bestehen.

### Bereits verifizierte neue Ergebnisse

41219852833: beide bisherigen Laufzeitfälle OHNE Profiling PASS unter den
unveränderten90/300s-Fristen:3892 Dateien213,948s,100 Dateien80,796s.
Sieben neue SQL-Statement-Sicherheitsverträge und acht vorherige SQL-Verträge
bestehen. Artefakt13050100813 SHA256
efa22efebbd5b972d7fda4979e350f5ea7ed118309373f9758b83a30534a0b25 verifiziert.
41220098240 SUCCESS:17/17 Vertragsfälle,0 ERROR/SKIP; Artefakt13049483491,
SHA256 fd574cf0f4af6709218f426cb42729f49ab52dc97f37c8a5503a9f61e9372ef6
verifiziert. Keine großen Altartefakte erneut heruntergeladen.

### Nächster konkreter Schritt / enge Grenze

1. Run41221622586 samt Artefakt-Digest/XML vollständig auswerten. Keine neue
 Vollmatrix und keine parallelen umfangreichen Tests in dieser Runde.
2. Falls Rot: zunächst klären, ob technische Receiptfelder mit dem echten
 Produzenten übereinstimmen. Keine Namenspräfix-Ausnahme und kein Entfernen von
 Belegen. Der vollständige Live-Wipe-Test kann hinter der bisherigen frühen
 Sperre weitere Verbraucher freilegen. Insbesondere storage_bootstrap.evidence
 hat ebenfalls eine private JSON-Whitelist; falls der Test später DORT scheitert,
 konkrete Datei/Phase belegen und dieselbe enge Qualifikation prüfen, niemals
 pauschal alle technical-startup-Dateien ignorieren. Dort bislang NICHT geändert.
3. Falls Grün: nur diese gezielte Fehlergruppe als bestanden dokumentieren.
 Die vollständige Endabnahme auf finalem Code ist weiterhin Aufgabe einer
 weiteren Runde.147 ursprüngliche Backendfehler noch nicht erneut ausgeführt.

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
