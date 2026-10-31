# Bibliothekar pre.5 – Backend-Triage, 31.10.2026

## Aktueller Einstieg

Branch `codex/pre5-operation-recovery`.
Neuer Anwendungscode: `3404ddcf020e56bd4f82aedf80cec4c69c4753ef`.
**Zuerst den gezielten Lauf41207207207 auswerten.** Keine volle Matrix starten.
Das Fünf-Stunden-Fenster stand zuletzt bei92% Verbrauch, Woche42%. Deshalb
jetzt geordnet gesicherter Stopp; Workflow unabhängig weiterlaufen lassen.
Keine aktive Warteschleife und keine wiederholten Statusabfragen.

## Vollständiges Basisergebnis

41194643144 auf2908eacbf73e891ebd46078cb9ae4af43e0dd454:
- Zieltests60+82 PASS, Frontend44+147 PASS.
- Reale Containerabnahme komplett PASS: pre5/pre4, sechs historische Recovery-
  und SIGKILL-Fälle,90 Dateien/47 Familien/8 Tage, drei korrigierte General-Kopien,
  Katalog-/Registryintegrität, zwei Neustarts,4.000 Familien/zwei Bibliotheken,
 14 iPhone-JPEGs+13:00, unveränderte Archive/Herkunft. Starts5,374/5,366s.
- Backend alle2444 Nodes in acht disjunkten Partitionen ausgeführt:
 2204 PASS,240 FAIL,0 ERROR/SKIP. Diese roten Fälle blockieren Veröffentlichung.
- Vollständiges Backend-ZIP13044081687,248983932 Bytes, SHA256
 `7838e1590c892d24deb7a071276353ec35447e985c98b42da050806eacf6b996` nach Download verifiziert.
- ZIP hat51527 Einträge/16,46GB unkomprimiert. Nur notwendige vollständige
  JUnit-/stdout-/Ergebnis-/Deadline-/Nodeprotokolle extrahiert; alle übrigen
  Snapshots weiterhin im unveränderten ZIP. Nicht unnötig16GB entpacken.

Alle240 Nodes mit Gruppe, Partition, Prüfstatus und vollständigem Trace-Digest:
`docs/pre5/BACKEND-FAILURES.{md,json}`. Reproduzierbare Klassifikation:
`python3 qa/pre5/classify_backend.py EVIDENCE_ROOT OUTPUT_DIRECTORY`.
Klassifikation ist ausdrücklich erste Triage; SUSPECT/MIXED/REQUIRES ungeklärt.
Keine alte Erwartung ohne Verhaltensbeweis als falsch erklären.

## Nachgewiesene Gruppen / erste Implementierung

- Zwölf alte Prozessfälle: schema_versions wird auch bei aktuellem Schema per
  CREATE TABLE IF NOT EXISTS angefragt. SQLite verlangt dafür Schreibautorität.
  `ensure_schema_version_table` und Registry-Pendant lesen vorhandene Tabellen
  jetzt zuerst per SELECT; echte Anlage und Migrationen bleiben geschützt.
- Neunzehn RC11-Fixtures publizierten ihren historischen Orphan VOR dem Anlegen
  der angeblich bereits vorhandenen Schemas. Fixture stellt die Schemas nun
  vorher her; kein Runtime-/ACL-/Reservationsbypass.
- Sechs negative Fixtures verändern absichtlich SQL-Zustand über App-Verbindungen,
  die dies korrekt verbieten. Externe Beschädigung muss ausschließlich in
  synthetischen Daten separat aufgebaut werden. Noch NICHT geändert.
- Zwei echte Testdeadlines.3892-Dateien-Test löst300s-SIGALRM im Authorizer aus;
  SQLite verschluckt den Callbackfehler als not authorized (Dauer374,859s).
  Zweiter Fall100 bekannte Dateien/90s. Keine pauschale Deadline-Erhöhung.
- Viele Backup-/Trash-/Restore-/Import-Recoveries werden vor ihrer eigentlichen
  Qualifikation durch die neue Eintrittssperre abgehalten. Bekanntes Problem,
  noch nicht sicher gelöst. Nicht mit globalem recovery_session() umgehen.
-25 Fälle zeigen fremden globalen Bootstrap-Registrypfad bei Ad-hoc-Workspaces;
  Fixture-/Kontextvertrag gezielt prüfen, keine schwächere Ankerprüfung.
- Source-String-/Fehlerwortlaut-/state.json-Erwartungen teilweise veraltet;
  durch positive Verhaltens- und negative Schutzbeweise ersetzen, nicht löschen.
- Andere200/409-, Startup-returncode- und Warteschlangenfälle sind NICHT pauschal
  veraltet. Safe Reads, echte Schreibsperren, Abschlussstatus und Medien prüfen.

## Gezielter neuer Nachweis

`tests/backend/test_pre5_sqlite_authorization.py`: acht Fälle für Katalog/Registry,
aktuelle Schemaabfrage mit ungelöster Reservation, reine Leseverbindung, weiterhin
verbotene DDL/UPDATE/DELETE, fehlende Versionstabelle und echte offene Migration.
Original-SQL-Dumps und F14-Records müssen unverändert bleiben.

41207207207 hat Commitmarker[pre5-db-auth]. Einziger Workflow:
`.github/workflows/qa-pre5-operation-recovery.yml`. Vor der bisherigen kurzen
Stufe läuft die neue Datei, RC11-Bootstrap und ein alter RC4-Prozessfall.
Letzterer und zwei RC11-Recoveries können die nächste bereits erkannte
Reservationsbarriere sichtbar machen; rote Ergebnisse vollständig lesen.
Bei roter Fokusstufe stoppen die nachfolgenden kurzen Tests; XML/Log bleiben
in pre5-reproductions erhalten. Ohne full/container-Marker keine teure Matrix,
keine Images, keine Veröffentlichung. Lokale Syntax/Actionlint/Diffprüfung PASS;
neue Linuxergebnisse noch PENDING. Nur Syntax/Analysen lokal, Ausführung Linux.

## Weitere Reihenfolge

1. Fokuslauf auswerten; positive8 Sicherheitsfälle und RC11-Fixture getrennt
   vom weiterhin blockierten historischen RC4-Recovery bewerten.
2. Für echte Recovery exakte ursprüngliche Reservation, Nonce, Schlüssel,
   Generation, Bindungen und Journal-/Datenbankbeweise qualifizieren. Niemals
   alle blockierten Aufträge freigeben, unbekannte Intents löschen oder mutable
   SQL-Felder allein als Scope-/Abschlussautorität verwenden.
3. Anschließend Wiederaufnahme von Backup, Papierkorb/Restore, Sortierung,
   Recheck und Import in kleinen Gruppen, einschließlich Fremdbytes/SIGKILL.
4. Fixture-/HTTP-/Setupgruppen und reale Laufzeitursachen abarbeiten. Erst danach
   alle2444+neuen Nodes erneut vollständig, anschließend erforderliche Container-
   und Browser-Abnahme auf exakt finalem Code. Keine parallelen Volltests.
5. Erst bei komplettem SUCCESS selbstständig pre.5 veröffentlichen. Vorbereiteter
   Publisher docs/pre5/release bleibt PENDING; Workflow nur Vorlage unter docs.
   Er benötigt für das große Backend-ZIP eine streng begrenzte Extraktion der
   Pflichtbelege; bisherige300MB-Gesamtgrenze nicht blind aufheben.

## Nachweise / Werkzeuge / Grenzen

`docs/pre5/EVIDENCE.json`, TEST-REPORT.md, ARCHITECTURE.md, UPGRADE-TRUENAS.md.
Scratch `/private/tmp/bibliothekar-pre5-evidence/41194643144-backend.zip` und
`41194643144-backend/`; dort zusätzlich failures.json mit vollständigen Traces.
Die übrigen drei ZIPs sind ebenfalls heruntergeladen und kryptografisch geprüft.

GH_CONFIG_DIR=/private/tmp/bibliothekar-gh-device, GH_BROWSER=true, GH_DEBUG=,
GODEBUG=http2client=0; CLI=/private/tmp/bibliothekar-gh-cli/gh. Direkte API mit
Cache-Control:no-cache statt veraltetem gh run view/list. Logs/ZIPs benötigen
--allow-escape-sequences und Umleitung in Scratchdatei. Tokens niemals ausgeben.
Actionlint /private/tmp/pre-actionlint/actionlint mit docs/pre/release/actionlint.yaml.
Alle Jobs ausschließlich[self-hosted,Linux,X64,bibliothekar-safe]. Keine Subagents.
Kein NAS-/GUI-Zugriff, kein Clean Slate, keine manuellen produktiven SQL-Änderungen.
`qa/rc14.zip` war vorher unversioniert vorhanden: niemals stage'n.
Keine bestehenden Tags, Images, Releases, latest oder Rechte verändern.
Native TrueNAS/NFSv4, physische SD/USB, echtes DNG1.7-/RAF-Schreiben NOT_RUN.
Bekannte-Aufnahme-VarianteA und eigenständiger Verlustabschluss DEFERRED.
