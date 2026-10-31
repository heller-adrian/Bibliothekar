# Bibliothekar pre.5 – Fortsetzung, 31.10.2026

## Sofortiger Einstieg

Branch `codex/pre5-operation-recovery`.
Letzter Anwendungscode: **99d0f2bd0ce7e7dbd9c4032bbfda5e8dd67f5170**.
QA-/Dokumentationsstand: **aeaa7c5ddd6973d3744c6057ed694e3bdc4c117a**;
Appdateien dazu identisch. Zuerst **41217778080** auswerten (zuletzt pending).
Vorgänger **41216774058** aufa4edf56e lief noch; sein Ergebnis ist nützlich,
gilt aber ausdrücklich NICHT als Abnahme der späteren SQL-/Live-Recovery-Fixes.
Nie gestartete Zwischenläufe41217275546/41217482164/41217630423 wurden durch
GitHubs einzigen wartenden Concurrency-Platz ersetzt. Keine parallele Matrix.

Wochenanzeige53%, Fünf-Stunden-Anzeige68%; geplante sechs zusätzliche
Wochenprozentpunkte dieses Fortsetzungsschritts erreicht. Geordnet sichern,
keine aktive Warteschleife. Der gestartete Workflow läuft unabhängig weiter.
Keine Veröffentlichung vor vollständigem Grün; Freigabe danach besteht fort.

## Gesicherte Ergebnisse

Vollständige Ausgangsmatrix41194643144 auf2908eacbf73e891ebd46078cb9ae4af43e0dd454:
2444 Nodes,2204 PASS/240 FAIL/0 ERROR/SKIP in acht disjunkten Partitionen.
Neue Zieltests60+82, Frontend44+147 und reale Containerabnahme damals PASS:
90 Dateien/47 Familien/8 Tage, General-API-Übernahme, Hash-/Registry-Prüfung,
zwei Neustarts,4000 Familien/zwei Bibliotheken,14 iPhone-JPEGs+13:00,
RO-Archive/Herkunft erhalten. Auf neuem Anwendungscode erneut erforderlich.

Alle240 ursprünglichen Fehler: `docs/pre5/BACKEND-FAILURES.{md,json}`.
Einzelner fokussierter Nachweis je Originalnode: `BACKEND-FIX-STATUS.json`:
56 ursprüngliche Fehler inzwischen PASS,14 noch FAIL im zuletzt ausgeführten
passenden Subset,170 noch nicht erneut geprüft. KEIN Ersatz der Schlussmatrix.

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

## Nächste konkrete Schritte

1. Run41217778080 inklusive vollständiger Fokus-XML/Guardlogs auswerten, Digest
 prüfen. Der altea4edf56e-Lauf enthält noch die normale LIVE-Recovery-Kollision;
 keine spätere Korrektur als bereits getestet erklären. `backend_focus.json`
 enthält SQL-/Domain-Verträge, RC11, RC4-SIGKILL/Retentionnegative,25 Registry-
 Nodes, O2, Trash-Recovery/-Fremdbytes/-SQL-FK-Fälle, Legacy-Setup, Auth und Wave1.
 Jobrahmen45min wegen erweitertem Umfang; einzelne Testgrenzen90/300s unverändert.
2. Gemeinsame Ursachen der verbleibenden roten Fälle beheben, einschließlich
 Restore-Konfliktisolierung, originaler Backup-/Sort-/Import-/Recheck-Leases,
 vorhandener mehrfacher Intents, alter Startup-/Source-Text-Verträge. Kein
 generisches _RECOVERING-Bypass, kein Status-only-Abschluss, keine SQL-Handreparatur.
 Neue variant-rescue-/deletion-Protokolle zunächst negativ und realen SIGKILL prüfen.
3. Nach grünen SQL-Negativverträgen die zwei Laufzeitfälle gezielt erneut
 ausführen. Vorhandener Marker[pre5-profile] führt ausschließlich diese beiden
 mit Profiling und bestehenden Deadlines aus; kein voller Testlauf. FAIL wegen
 Profiling ist weiterhin kein PASS; gegebenenfalls normale instrumentfreie
 Zweifall-Stufe vorbereiten, niemals pauschal Deadlines erhöhen.
4. Erst nach weitgehend grünen Ursachen-Gruppen die vollständige Backendmatrix
 und neue Ziel-/Frontend-/Browser-/Supervisor-/90-Dateien-/4000-Familien-/14-iPhone-
 Abnahme auf finalem Anwendungscode wiederholen. Keine parallelen Vollläufe.
5. Erst dann pre.5 veröffentlichen. Publisher unter docs/pre5/release PENDING,
 kein Releaseworkflow aktiv. Großes Backend-ZIP verlangt begrenzte Whitelist-
 Extraktion der Pflichtnachweise, keine blind aufgehobene300MB-Extraktionsgrenze.

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
