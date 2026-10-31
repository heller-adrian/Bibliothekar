# Bibliothekar pre.5 – reproduzierbare Fortsetzung, 31.10.2026

## Zuerst prüfen

- Branch: `codex/pre5-operation-recovery`.
- Aktueller Anwendungscode/QA-Kandidat: `2908eacbf73e891ebd46078cb9ae4af43e0dd454`.
- **Lauf 41194643144 über direkte GitHub-API prüfen.** Containerjob
  124519051403 SUCCESS. Backendjob124521156657 führt die acht Partitionen aus.
- Ziele: 60 neue +82 fokussierte PASS, jeweils 0 FAIL/SKIP. Frontend: 44 RC13
  +147 RC14 PASS. Container einschließlich90 Dateien/4.000 Familien/14 iPhones ebenfalls PASS;
  vollständige Backendmatrix bleibt offen.
- Erneut heruntergeladene, kryptografisch verifizierte ZIPs:
  Ziele13040405805: `88a4098ba8118817918b9417c880f134fc7ba9259b28dd3e098ea00c7d7b858f`;
  Frontend13040415276: `bf0f6991e222259c51be5e2148d4985b68a835bfddf16cf93947f04d09c137a4`.
- Scratch: `/private/tmp/bibliothekar-pre5-evidence/41194643144-{targets,frontend}`.
  Alle früheren Logs/ZIPs liegen ebenfalls unter diesem Evidence-Stamm.
- Container13040432071: `d656fc55af18966b4a244df052ad57b2f215beb69c773ccb9aa8ba3a05547a20`,
  ZIP erneut verifiziert. Starts5,374/5,366s; unveränderte Archive/Herkunft/General-Kopien.
- Letztes Kontingent: fünf Stunden68%, Woche39%. Ab70% Handoff sichern,
  deutlich vor Erschöpfung geordnet stoppen. Nutzerauftrag erlaubt Fortsetzung
  im nächsten Fenster; Veröffentlichung nur nach sämtlichen bestandenen Gates.

## Gegenwärtige Ursachen und Fixes

Details: docs/pre5/ARCHITECTURE.md, TEST-REPORT.md, EVIDENCE.json. Originalaufträge:
`/Users/adi/Downloads/Codex_Auftrag_Bibliothekar_v1.0.0-pre.5.md` und
`/Users/adi/Downloads/Bibliothekar_pre5_TrueNAS_Befunde_2026-10-30.md`.
Ausgangspunkt pre.4: `adcc2aa9a444042440ff764be10fe1e42191904d`.

1. GET-Kompatibilitätsansicht verlangte F14-Schreibreservation. Jetzt private
   prozesslokale temporäre View mit qualifizierter echter Rootbindung.
2. Exakt auditierte medienlesende Inventory-/Archivprüfungen und SQL-Planer
   sind transient. Historische Belege werden ausschließlich nach kompletter
   Qualifikation mit vollständigem Originalrecord im dauerhaften Unterbrechungs-
   nachweis behandelt. Echte unbekannte Schreibwirkungen bleiben geschützt.
3. Scope-Admission, SQL-Authorizer und Queueclaim sichern konkrete Ressourcen.
   Verschachtelte Wirkungen werden dauerhaft erweitert, nie verengt. General-
   APPLY benötigt privaten Tasknachweis; mutable SQL alleine ist keine Autorität.
4. Bereits zentral geroutete Jobs werden nicht erneut als alte Main→Zentral-
   Migration ausgeführt. Drei echte Migrationstests bestanden. Echte Altfälle
   mit fehlender Quelle/fremden Zielbytes bleiben blockiert.
5. General-202 wurde bis completed/organized_verified + Neustart untersucht
   (41190356694). Datei/Hash/Archive korrekt, dennoch neue Herkunft47→48 Familien,
   90→91 Medien/Mitgliedschaften nach bestätigtem Katalogverlust. Korrektur liest
   unveränderliche Mitgliedschaften und abgeschlossene Korrekturketten aller
   registrierten Bibliotheken linear. Keine historischen Belege werden verändert.
   Echte neue General-Dateien bleiben asynchron importierbar; bekannte Kopien-
   Variante A ist ausdrücklich DEFERRED, kein Entfernen der Herkunftsprüfung.
6. Thumbnail-GET erzeugte operation_read_only_request/500. Jetzt vorhandener
   regulärer Cache oder BytesIO ohne persistente Wirkung; gepinnte Struktur vor/
   nach Rendern qualifiziert. Worker-Cache behält volle Schreibadmission. Neuer
   realer JPEG-Test bestätigt Ausgabe320x200, gleiche Originalbytes, komplette
   SQL-Dumps und F14-JSONs sowie kein angelegtes Cacheverzeichnis. PASS.

Der erste Inventory-Abbruch auf dem tatsächlichen NAS bleibt nicht bewiesen.
Keine konkrete historische NAS-Operation ungeprüft als sicher behandeln.

## Letzte CI-Hindernisse / mögliche nächste Diagnose

- 41191231150: Ziele56+80, Frontend, pre5/pre4-Live und vier historische Fälle
  PASS. Historischer pre.2-Seed pollte Job-GET im SQL-/F14-Abschlussfenster; alte
  Middleware fordert dabei Schreibschemafreigabe. Seed wartet jetzt read-only
  auf completed und Release exakt seiner Importreservation, verlangt danach
  weiterhin HTTP200/completed. Originale Metadata-Orphan bleibt Recoveryziel.
- 41192396662: 59+80 PASS, historisch236 PASS/1 FAIL/0 SKIP. Ein alter Unit-Test
  hatte keine eigene Registry. Echte isolierte Registry ergänzt, Race-Gegenprobe
  verlangt genau den Staging-Hashfehler. Beide Fälle im kurzen Gate: jetzt PASS.
- 41193453760 und41193996176: 59+82/Frontend PASS, alle fünf pre5-Live-API-/
  Recovery-/Archivprüfungen PASS. Neuer Browsercheck sah den absichtlich
  deaktivierten optionalen Gerätehelfer: source-devices503 mit genau belegtem
  JSON. Dieser konkrete Fall wird qualifiziert, andere5xx bleiben Fehler.
  Danach verlor Navigation asynchrone Response-Bodys. Test wartet nun
  networkidle; falls es erneut scheitert, `read_error` im tatsächlichen Log
  untersuchen, nicht pauschal HTTP500/503 erlauben.
- Der90er Ablauf verlangt nach beiden Neustarts alle aktuellen Katalog-SHAs,
  genau drei erhaltene korrigierte General-Kopien, SQLite quick_check und
  Fremdschlüsselprüfung beider Datenbanken. Nie nur202/409 austauschen.

## Vollständiger nächster Prüfpfad

1. Fehlgeschlagene aktuelle Stufe untersuchen, falls41194643144 nicht SUCCESS.
   Keine zweite CI blind starten. Bei reinem QA-Fix App-Quellgleichheit belegen.
2. Container: pre5/pre4-Livebrowser DE/EN390/1440, sechs historische Recovery-
   Fälle samt echten SIGKILLs, echter90-Dateien-/47-Familien-/8-Tage-Ablauf,
   4.000 Familien/zwei Bibliotheken und14 iPhone-JPEGs mit+13:00.
3. Backend: qa/pre5/full_backend.py führt acht disjunkte Partitionsläufe aus.
   Auswahl allein ist kein Testnachweis: passende JUnit-Zahlen, vollständige
   Nodes,0 FAIL/ERROR/SKIP zwingend. QA-Scratch privat unter /tmp; gruppen-
   beschreibbare Runner-Eltern dürfen nicht chmod'ed werden. Collectionfehler
   stoppt statt acht Wiederholungen. Originale signierte QA-Dateien unverändert.
   Deadlines90s, bekannter3-Lifecycle-Test240s, RC14-3892-Fixture300s.
4. ZIP-Digests aller vier finalen Artefakte erneut prüfen; Bericht/EVIDENCE.json
   mit tatsächlichem finalem SHA, Run, Zahlen und Grenzen abschließen.
5. Erst bei vollem SUCCESS Publisher binden und eigenständig veröffentlichen.

## Publisher – vorbereitet, gesperrt, noch nicht Linux-getestet

`docs/pre5/release/`: core/oci/graph_fixture aus erfolgreichem pre.4-Publisher;
pre5-spezifische Quell-, QA-, Runtime-, Tag-/Image-/Release- und Download-Gates.
ACCEPTANCE.json=PENDING; source_audit verweigert dies vor externen Schreibvorgängen.
PUBLISH-WORKFLOW.yml liegt nur unter docs, ist kein aktiver GitHub-Workflow.

Vor Verwendung finalen geprüften Quellcommit, erfolgreiche Run-ID, vier ZIP-IDs/
Digests, genaue pytest-/Frontendzahlen und vollständige Backend-Nodes binden.
Finaler reiner Dokumentationscommit muss EVIDENCE.json im akzeptierten Schema
enthalten; app-Baum unverändert. Publisherbranch `codex/publish-1.0.0-pre.5`,
Workflowvorlage erst dort nach `.github/workflows/publish-pre5.yml` kopieren.
Alle Jobs self-hosted/Linux/X64/bibliothekar-safe. Source-Audit/Unittests/Actionlint,
Bytevergleich aller eingebetteten App-Dateien, tatsächliche Release-Container-QA,
OCI-Index/Plattformmanifest/Konfiguration/Docker-ID, Digest-Pull, erneuter Download
aller Release-Anlagen zwingend. Alte pre bis pre.4, latest, Stable und bestehende
Privatsphäre/Paketrechte schützen. Unklarer Teilzustand: stoppen, nichts überschreiben.
README/REPORT/Release Notes sind noch Entwürfe und müssen Abnahmeergebnis erhalten.

## Werkzeuge und Grenzen

```sh
export GH_CONFIG_DIR=/private/tmp/bibliothekar-gh-device
export GH_BROWSER=true GH_DEBUG= GODEBUG=http2client=0
/private/tmp/bibliothekar-gh-cli/gh api repos/heller-adrian/Bibliothekar/actions/runs/41194643144/jobs -H 'Cache-Control: no-cache'
```

`gh run view/list` kann veraltet sein; direkte API nutzen. Rohlogs/ZIPs benötigen
`--allow-escape-sequences` und Ausgabe in Scratchdatei. Token niemals ausgeben.
Push mit bestehendem gh-Credentialhelper wie bisher. Actionlint:
`/private/tmp/pre-actionlint/actionlint -config-file docs/pre/release/actionlint.yaml FILE`.
Lokale Prüfung nur Syntax/Quellen; ausführende Abnahme ausschließlich isoliertes
Linux/Docker. Kein Docker lokal, keine Subagents. Keine NAS-/GUI-Zugriffe.
`qa/rc14.zip` war vorher unversioniert vorhanden: niemals stage'n.

Native TrueNAS/NFSv4, physische SD/USB, echtes DNG1.7-/natives RAF-Schreiben:
NOT_RUN. Verlustabschlussmodell und bekannte-Aufnahme-Variante A: DEFERRED.
Keine Veröffentlichung mit offenen Pflicht-/Sicherheitstests. Noch kein pre.5-
Tag/Release/GHCR-Push ausgeführt. Frühere Chronologie bleibt in Git erhalten.
