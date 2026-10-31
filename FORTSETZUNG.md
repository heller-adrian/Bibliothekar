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
