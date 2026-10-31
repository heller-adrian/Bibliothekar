# Bibliothekar pre.5 – Fortsetzung, 31.10.2026

## Sofortiger Einstieg

Branch `codex/pre5-operation-recovery`.
Letzter Anwendungscode: **f0e692473c4dd9bc24db1114a94068b3c87c9bea**.
QA-Vertragsstand: **1004e846805d160f02c8a7a919a79515e3a95f42**; Appdateien
bytegleich zuf0e69247 (git diff für app/Dockerfile/Requirements leer).

**Zuerst41219852833 auswerten** (zuletzt in_progress): kleine Schlussgruppe
mit SQL-/F14-Sicherheitsverträgen, den vier konkret behobenen Fehlern und den
beiden realen Laufzeitfällen OHNE Profiling unter unveränderten90/300s-Grenzen.
Erst nach grüner Fokusstufe folgen die normalen60/82 Zieltests.
**Danach41220098240 auswerten** (zuletzt pending): ausschließlich zwei kleine
historische Vertragsmodule; keine Wiederholung von Performance/Container/142Zielen.
Keine parallele Vollmatrix; beide laufen ohne aktive Codex-Warteschleife weiter.

41217778080 ist vollständig ausgewertet:264 Tests,260 PASS/4 FAIL/0 ERROR/SKIP,
1014,825s. Alle sieben neuen Statement-Sicherheitsverträge PASS; auch die acht
vorherigen SQLite-Autorisierungsverträge, Domain-/Retentions-/SIGKILL-Nachweise
im gewählten Subset bestehen. Kein Deadlineübertritt in dieser264er-Stufe.
Die beiden großen Laufzeitfälle waren dort NICHT enthalten.

Vier konkrete Ursachen und Korrekturen:
- Bestätigung[]/{}: TypeError im neuen Setcheck. Expliziter Stringtyp-Check in
 API-Gate UND Domainhelper, ungültige Werte bleiben422/gesperrt. Fünf zusätzliche
 direkte Negativverträge vor jeglicher Recovery, ursprüngliche Belege unverändert.
- Legacy-Live-Wipe-Fixture fehlten General/Batch-Verwaltungsanker. Behauptete
 vollständige Struktur jetzt vor dem historischen Startup angelegt. Produktive
 Missing-Anchor-Prüfung unverändert. Nachfolgende Live-Wipe-/Reset-Assertions
 laufen weiterhin echt und könnten weitere bisher verdeckte Fehler zeigen.
- Gezielt ausgeführtem Job fehlte tinycss2; gepinntes Testwerkzeug1.4.0 ergänzt.
 In der bisherigen vollen Matrix war es bereits vorhanden. Keine Appabhängigkeit.

Originalfehler-Inventar jetzt im gezielten Nachlauf:92 ursprüngliche Fehler PASS,
1 weiterhin FAIL,147 noch nicht erneut geprüft. Kein Ersatz der Schlussmatrix.
Die vier Fehler sind implementiert korrigiert, erneuter Linuxbeweis noch PENDING.

Wochenanzeige55%, Fünf-Stunden-Anzeige81%. Diese begrenzte Runde bei70/53 begonnen;
jetzt geordnet gesichert stoppen. Keine weiteren Polls oder neue Testläufe.
Keine Veröffentlichung vor kompletter erfolgreicher Gesamtabnahme.

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

## Nächste konkrete Schritte

1.41219852833 vollständig anhand XML/guarded Logs bewerten und Artefaktdigest
 prüfen. Vorrang: sieben Statement-Verträge bleiben grün,3892-Dateien-/100-Dateien-
 Tests bestehen unter normalen unveränderten Fristen. Keine pauschale Deadline-
 Erhöhung bei Rot. Bestätigung[]/{} muss422 liefern, alle fünf direkten ungültigen
 Bestätigungen dürfen keine Recovery-Belege erzeugen. Legacy-Live-Wipe bis echter
 bestätigter Neuaufnahme und erster Bibliothek prüfen, nicht nur ersten Start.
2.41220098240 prüfen: zwei frühere Source-Substring-Verträge wurden durch
 Verhaltenstests ersetzt. _prepare_technical_storage erstellt echte Config/
 Katalog-/Registryschemata in Reihenfolge und bewahrt bestehende Einstellungen.
 Sieben reale Ereignissuche-Varianten: read_session bleibt bei physical_refresh/
 first_check rein lesend; erlaubte normale Refresh-Aufrufe bleiben funktional.
 UI-Textverträge und übrige Tests beider Module bleiben erhalten. Appcode gleich.
3. Bei Rot nur diese klaren Ursachen zuerst korrigieren. Keine volle Matrix
 starten, solange relevante Gruppen rot/offen sind. Falls diese kleinen Gruppen
 vollständig grün sind, die bisherigen264 ggf. gebündelt auf gleichem Appcode
 bestätigen und nächste gemeinsame Recovery-Ursache auswählen. Für Backup-/
 Sort-/Import-/Recheck-/Restore-Leases sind weiterhin viele ursprüngliche Fälle
 offen; kein pauschales _RECOVERING-Bypass, kein SQL-Status-only-Abschluss.
4. Erst nach weitgehend grünen Ursachen-Gruppen komplette Backendmatrix und
 Ziel-/Frontend-/Browser-/Supervisor-/90-Dateien-/4000-Familien-/14-iPhone-
 Abnahme auf finalem Code. Nicht alte Container-/Frontend-PASS dem neuen Code
 zuschreiben. Keine parallelen Volltests, keine aktive Warteschleife.
5. Erst danach pre.5 veröffentlichen. Publisher unter docs/pre5/release PENDING;
 große Backend-ZIPs erfordern begrenzte Extraktion der Pflichtnachweise. Keine
 blinde Aufhebung der300MB-Grenze und keine Veröffentlichung mit ungeklärtem Rot.

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
