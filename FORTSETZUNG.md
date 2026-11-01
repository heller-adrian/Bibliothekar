# Aktueller Fortsetzungsstand – 01.11.2026, Reparatur der letzten58 Backendfälle

**BACKEND NOT ACCEPTED. Pre.5 noch nicht abnahmefähig – Veröffentlichung gesperrt.**
Branch: `codex/pre5-operation-recovery`.
Letzter QA-/Source-Commit: `e9061f41376519a63e429440a78df8e8de5cf387`.
Letzter Anwendungscode-Commit: `c06294e581e7c2e0a1721a637bc69f3924d10bcb`.
Nachfolgender Sicherungscommit ändert ausschließlich diese QA-Dokumentation.
Keine Tags/Releases/GHCR/latest/main/TrueNAS geändert. `qa/rc14.zip` ist ein
vorbestehendes untracked Benutzerartefakt und darf nicht mitcommittet werden.

## Zuerst die bereits gestarteten Läufe auswerten

1. **41261174452** auf `5ffa9175f737a1781e399d47988eca3cb6dfcc1f` war zuletzt RUNNING.
2. **41261700576** auf `e9061f41376519a63e429440a78df8e8de5cf387` war zuletzt PENDING.
   Er enthält kumulierte Reparaturen,47 Selektoren mit ursprünglichen15
   Crash-/Manipulations-Nodes, Restore-/Sort-/Metadatenfällen, voller BA-02,
   voller B01 und SQLite-Statement-/Schema-Authorization.
   Dieser `[pre5-contracts]`-Lauf führt keine Vollmatrix/Frontend/Container aus.
   Nicht parallel weitere umfangreiche Läufe starten; keine aktive Warteschleife.
   GitHub ersetzt ältere pending Runs automatisch; cancelled Zwischenläufe sind
   KEINE Testnachweise. Falls der neueste Run noch wartet, laufenden Job beachten.

GitHub-CLI:
`GH_CONFIG_DIR=/private/tmp/bibliothekar-gh-device GH_BROWSER=true GH_DEBUG= GODEBUG=http2client=0 /private/tmp/bibliothekar-gh-cli/gh`
Direkte `api repos/heller-adrian/Bibliothekar/actions/runs/<ID>` mit
`-H 'Cache-Control: no-cache'` verwenden; ältere `gh run view`-Caches waren stale.
Token nie ausgeben. Neue Artefakte einmal laden, SHA256 gegen API-Digest prüfen,
XML und alle Child-/Restart-Logs bewerten; bereits gesicherte ZIPs nicht neu laden.

## Nachgewiesene Ergebnisse und verfügbare Belege

- Voller Original147-Check auf7838a706, Run41231600475:89 PASS /58 FAIL.
  Alle58 exakten Nodes vollständig in `docs/pre5/BACKEND-REPAIR-58-20261101.json`,
  Bericht `.md`; Originaltrace-Digests bleiben erhalten.
  Artefakt13055435531 SHA256
  `9a0b633c2e7650265419f683f1a32aba4280113118e9ced51e173b91cce23260`.
  Benutzer-ZIP250/250 Dateien bytegleich damit.
- **41260071820**, Source4682b22a: **24 PASS /0 FAIL/ERROR/SKIP**.
  Alle15 ursprünglichen kritischen Nodes plus Restore-Kollisions-/Negativfälle.
  Artefakt13064419670 SHA256
  `b40faee8dd967452de7221d03a30cc1bdf536a157db650e2bd64675d896c7ba3`.
- **41260399276**, Sourcebd168d53: **26 PASS /7 FAIL /0 ERROR/SKIP**.
  F18 false/true PASS. F15 SQL-/Projektionsablauf und F14-Ablehnungsassertionen
  bestehen; Neustart scheitert an fehlenden General/Batch-Fixture-Unterordnern.
  F17 gleicher Fixture-Grund. Zwei General-Fixtures erreichen jetzt Worker-
  Quieszenz, ihr bisheriger Fake hatte keine join-Methode. Zwei NEUE Batchtests
  erwarteten fälschlich gleiche Zeit für A/B; echte Korrektur hält1s-Abstand.
  Diese belegten Test-/Fixture-Probleme sind inf91865d2 korrigiert, noch pending.
  Artefakt13065735420 SHA256
  `8857f69740ff2017992562bc97dac56d9ae1ebe8735a851500687ff85be0ca9c`.
- Lokale Syntaxprüfung aller geänderten Pythondateien, Actionlint und
  `git diff --check` PASS. Lokale macOS-Syntax ist KEIN Linux-Funktionsnachweis.
- Quelleübergreifende letzte Einzelwerte der ursprünglichen240 roten Nodes:
  **189 PASS /51 FAIL**,0 unbekannt. Verschiedene Commits: NICHT final akzeptiert.
  Unter den Original58 sind7 gezielt PASS,27 Fix/Fixture-Korrekturen pending,
  24 noch OPEN. Die spätere Linuxauswertung muss diese Angaben aktualisieren.

Alle ZIPs/extrahierten Original- und Childlogs:
`/private/tmp/bibliothekar-pre5-evidence/41231600475-targets*`
`/private/tmp/bibliothekar-pre5-evidence/41260071820-targets*`
`/private/tmp/bibliothekar-pre5-evidence/41260399276-targets*`
Lokale `failures.json` im letzten Ordner enthält alle sieben vollständigen
Fehler; Baseline `failures-58.json` im ersten Ordner alle Originaltraces.

## Implementierte gemeinsame Reparaturen, noch nicht alle abgenommen

- 4682b22a: bestehende Restore-Konflikte erneut vollständig unter Trash-Lock
  qualifizieren; Original-F14-Abschluss/Receipt, Journal/Fehler/A-Pfade behalten.
- bd168d53: physische Metadatensperre und read-only Task-/Projektionszulassung
  vor neuer F14-Reservation; executorinterne Sicherheitsprüfungen bleiben.
- efd1dbdf: genau ein originaler camera-only Pre-Commit-Sortierlauf kann
  bestehende Rollback-Recovery unter ORIGINALnonce verwenden. Neue
  `app/sort_recovery_proof.py` prüft Registry, Bibliotheksidentität, DBschema,
  Generationen, alle Bindings, Run/Job/Event, Pfade, Hash/Größe und Endpunkte.
  Exakter run_id statt beliebiger anderer Runs; dauerhafter Originalbeleg.
  Assets, bereits committete Ergebnisse, doppelte Endpunkte, Fremdbytes,
  Hardlinks und ungebundene Wurzeln bleiben gesperrt. Sechs negative neue Fälle.
- 68364546/969e591d: Trash-Lock umfasst auch F14-Zulassung. Passender originaler
  Restore darf nur über den vollständigen Qualifier abgeschlossen werden.
  Erst danach unabhängige Auswahl zulassen; reservierte/aktive Auswahl schon
  VOR neuem Intent ablehnen. Wiederholte Prüfung nach Journalanlage bleibt.
  RC4-sechs-Fall-Ursache war ein vom ersten abgewiesenen DELETE selbst erzeugter
  F14-Record, nicht pauschal ein terminaler Restore-Job.
- 5ffa9175: reentrante Metadata-Sperre an Workspace+PID+Thread binden; kopierte
  ContextVars verleihen keinem anderen Thread die physische Sperre.
- f91865d2: General/Batch-Voraussetzungen der historischen Fixtures vor Operation,
  vollständiger Fake-Thread und korrekte1s-Batch-Erwartung. Immutable Original-
  QA-Sources/Integritätsmanifeste unterqa/f16_f20/original unverändert.
- c06294e5: Exception-Rückbau einer Trash-Löschung behält sein geprüftes Journal
  bis zum regulären Abschluss der originalen F14-Lease; verstärkter F1-Test.
- e9061f41: ungeklärter Vier-Ordner-Test gibt vollständigen inspect_storage-
  Befund aus. Noch KEINE geänderte Erwartung/pauschale Produktlockerung.

## Nächste Fehlergruppen nach tatsächlichen neuen Resultaten

Zuerst alle roten neuen Sort-/Restore-/Sperr-Gegenproben aus den zwei Läufen
abgleichen. Bereits abgenommene Backup/Restore/SD-Checks dürfen nicht regressieren.
Insbesondere prüfen: neue `_sort_recovery_proof`-Bedingungen gegen tatsächliche
Run-Daten und Eigentumsrollen; keine Lockerung nur wegen eines roten Tests.

Danach übrige OPEN-Nodes aus dem58er-Inventar:
- frühe Imports ohne gültigen Publikationsbeleg haben noch aktiven SQLstatus;
  Medien und ursprüngliche F14-Lease bleiben geschützt. Statuskorrektur ist
  keine Freigabe/Resume-Autorität und braucht eine eigene genaue Qualifikation.
- Originale Library-/Multiple-/Reintegration-Metadata-Journale sind noch nicht
  durchgängig mit ihrem originalen F14-Key verbunden; keinen Pfad raten.
- historische Exception-Leases ohne Journal/Receipt nicht aus Abwesenheit
  freigeben. Neue Korrektur verhindert weitere Belegverluste, qualifiziert
  einen tatsächlich beleglosen Altfall nicht rückwirkend.
- F14-Continuation mit vorhandenem finished-Receipt trifft noch auf frühe
  Write-Admission; nur unveränderliche exakte Receipts, niemals SQLstatus allein.
- R1 zwei Prozesse nach owner-SIGKILL sowie malicious new_library_origin-Fixture
  noch nicht abschließend qualifiziert. Fremde Herkunft darf nur als explizite
  isolierte Angriff-Fixture erzeugt werden; produktive SQL-Guards bleiben aktiv.
- F11/0562 alte nonzero-Startup-Annahmen nur dann ändern, wenn echte F14-
  Schreibsperre und unveränderte Original-/Fremdbytes vollständig bewiesen sind.
- Vier-Ordner-/Setupfall: vollständige neue Diagnose lesen, keine voreilige
  Annahme über Fixture vs Produkt. Echte neue Installation muss funktionieren.
- RC6 parallele SD-Rechecks: vom anderen abgestürzten READ-Recheck stammender
  Record kann die lebende Operation fencing; zuerst echte Originalprovenienz
  qualifizieren, niemals generisch live/dead ignorieren.

## Noch ausstehende Pflichtabnahme / Kontingent

Erst nach grünen Gruppen147/147 +15/15 + volle BA-02/B01 auf festem Commit,
dann acht disjunkte Backendpartitionen und Frontend/Browser/realer Supervisor-
Container. Testzahlen, Node-IDs, Commit-SHAs und Artefakte unabhängig prüfen.
Kein solcher vollständiger Nachlauf ist jetzt gestartet; keine Veröffentlichung.

Kontingent diese Runde: Start0%/57% (5h/Woche), letzter Abruf49%/65%.
Geplante8 weitere Wochenpunkte erreicht; Zwischenstand geordnet sichern.
Bei Fortsetzung neue Limits lesen, nur nötige targeted Korrekturen, keine
Warteschleifen. Alte Veröffentlichungen/Produktivdaten bleiben unangetastet.

---

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

## 31.10.2026 – nachgewiesene Fixture-/Erwartungskorrekturen, keine App-Änderung

Zielgerichtete Linux-Nachprüfung auf **cc4cbe47b35e1f5d59eb231796e7e4f82bb37f31**:
GitHub Actions **41226912195 SUCCESS, 3/3 PASS, 0 FAIL/ERROR/SKIP**.
`test_rc9_setup_separation` prüft beide Varianten der ersten Bibliothek:
`technical_registry` legt nur die Registry an, nicht die Hauptdatenbank.
Daher ist `catalog_unavailable` in beiden synthetischen Zuständen korrekt,
`can_setup_again` bleibt wahr, der Archiveintrag bleibt unberührt.
`recovery_0562/worker.py` legt für die zweite historische Fixturebibliothek
vor dem Crash auch `General` und `Batch Correction` an. Der reale
Metadatenprojektionstest mit zwei SIGKILLs besteht bis zum Ende.
Artefakt **13050924946**, GitHub- und unabhängig geprüfter SHA256
`861f500dc3d1f98568ac6a46e798a291a92e6322d5589d930f93046d6f1bc7d0`.

Zielgerichtete Linux-Nachprüfung auf **9d934a2dac883f2f39c81aed74ce9e182c7a19b0**:
GitHub Actions **41227115670 SUCCESS, 2/2 PASS, 0 FAIL/ERROR/SKIP**.
Zwei B01-Verhaltensverträge prüfen jetzt statt veralteter mutierender GET-Hooks
einen aktiven Inventory-Writer gegenüber rein lesenden GETs sowie zwei
parallele Ereignis-Leseabfragen. Erwartet wird HTTP 200 bei überprüften,
unveränderten Medienbytes, Schlüssel-Datenbankzuständen und privaten
F14-JSON-Belegen. Kein Produktionscode geändert. Artefakt **13052108489**,
GitHub- und unabhängig geprüfter SHA256
`1d75aaad3cee8dabf877b66c051f94b0801e1e9601fec22e0cf2e0b075370184`.

**Vier zuvor rote Originalnodes** (RC9 technical_control, 0562 metadata
projection, zwei B01-Fälle) sind jetzt gezielt grün, zusätzlich der positive
RC9-legacy_roots-Kontrollfall. Dies ist KEINE vollständige Backendabnahme;
`BACKEND-FIX-STATUS.json` bleibt zunächst das historische Inventar, dessen
breite Statussynchronisierung noch aussteht. Die restlichen Recovery-/Restore-/
Recheck-Fehler sind separat zu untersuchen. Die weiteren B01-Altverträge wurden
hier nicht als erfolgreich nachgewiesen. Keine Tags, Images, main oder TrueNAS
verändert; **Pre.5 nicht veröffentlichen**.

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

## 31.10.2026 – fortgesetzte Pre.5-Crash-Recovery, Abnahme noch ausstehend

Auf Nutzerfreigabe wurden nacheinander Restore, SD-Recheck und Import
unter unveraenderten F14-Schutzprinzipien repariert. Anwendungspatches:
- ec476e06 / 5b2ac06 / 26c5cf49 / 12e9a1e6: abgesicherter Abschluss
  eines direkten bzw. bereits SQL-/Audit-verifizierten Restore-Journals,
  exakte bekannte Quellmenge und keine fremden Staging-Dateien.
- ed8845ab / 5b2ac06: originale F14-trash-Restore-Reservation wird
  bei exakt passendem, registriertem, unveraendertem Journal unter
  qualifizierter Recovery-Freigabe fortgesetzt; kein allg. Bypass.
- ad39ce07 / 0582e8ca: verwaiste *lesende* SD-Pruefung nur nach
  tatsaechlichem jobs.operation='sd_recheck', Source-/Root-/DB-
  Identitaetskontrolle und atomarem Child-Handoff sicher als
  neu zu hashender Check qualifiziert; echter folder_import behält F14.
- fe82b6f0: urspruenglicher verwaister, mit import_recovery.qualify
  nachgewiesener folder_import wird bei Startup ausschliesslich in
  state='interrupted' markiert, ohne Dateien, Herkunftsjournal oder
  F14-Reservation zu entfernen. Aufruf in operation_health.
- 7565ab06 / dc00ddc1: historische negative Restore-Tests duerfen
  zwar einen lebenden READ-Server sehen, verlangen bei offenem
  ungeklaertem Restore jedoch nachweislich writes_allowed=False
  und unveraenderte originale F14-trash-Reservation samt Bytes.

Nachweise:
- 41230227562 auf 12e9a1e6: 9 PASS / 1 FAIL (Import-Status).
- 41230840038 auf 0582e8ca: letzter Import-Crashtest 1 PASS.
- 41230912187 auf c080e9a2: 12 PASS / 3 FAIL, dabei alle
  zehn urspruenglich roten Crash-Faelle PASS; die drei roten
  Sicherheitsgegenproben hatten nur einen veralteten erwarteten
  Prozess-Exitcode. Echte F14-Schreibsperren und unveraenderte
  Fremdbytes sind aus vollstaendigen Restart-Logs nachgewiesen.
- JETZT PENDING: 41231315552 auf dc00ddc1: zehn Originalfaelle
  plus fuenf Manipulations-/Kollisions-Gegenproben, alle mit
  expliziter Pruefung der echten F14-Schreibsperre.
- Redundanter historischer QA-Run 41231036891 belegt aktuell
  denselben selbstgehosteten Linux-Runner. Er ist KEINE
  Release-Abnahme. Neuer Run startet nach Freigabe des Runners.
- Artefaktsicherung repariert: vollstaendige original-unretested
  JUnit-Resultate werden beim nachfolgenden pre5-full-Lauf archiviert.

Release-Gate: PRE.5 NICHT FREIGEGEBEN. Die 15er-Sicherheitsabnahme
steht noch aus; der neue 147er-Originalcheck, alle 8 Backendpartitionen,
Frontend und Container wurden auf dem neuen Source-Stand nicht abgenommen.
Kein main/tag/GHCR/TrueNAS veraendert. Bei roten Resultaten nicht publishen.

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
