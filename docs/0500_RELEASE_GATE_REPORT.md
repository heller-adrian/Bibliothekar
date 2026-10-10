# Bibliothekar 0.50.0 – Release-Candidate-Gate, 10.10.2026

**Ergebnis: Code-/CI-Gate bestanden, produktiver Stable-Release NO-GO (noch nicht vollständig abgenommen).**

Dieser Bericht unterscheidet ausdrücklich nachweisbare automatische Tests von
Praxisabnahmen, die ohne Zugriff auf eine isolierte TrueNAS-Testinstallation und
iOS Safari/Web-App nicht bestätigt werden dürfen.

## Identität des geprüften Entwicklungsstandes

- Branch: `patch/0.50.0-audit`, Pull Request #19 (Draft).
- Anwendungsversion: `0.50.0`.
- Letzter vollständig geprüfter Code-Commit vor diesem reinen
  Dokumentationscommit: `82697bb772f690a2a28a2f46ce6aebb2e9277b83`.
- GitHub Actions: https://github.com/heller-adrian/Bibliothekar/actions/runs/38054109899
- Ergebnis: **995/995 Backendtests bestanden, 6 Warnungen**; separater
  `archive-isolation-harness` erfolgreich.
- Der Archiv-/Container-Test wurde mit einem **aus genau diesem Commit
  gebauten Image** ausgeführt. Produktionsarchiv und produktive SQLite-DB
  wurden nicht gemountet. Der synthetische Importquellenbestand bleibt
  read-only.
- Im tatsächlich gestarteten Docker-Container wurden HTTP-Zugriffe geprüft:
  API ohne Sitzung `401`; falsches Passwort `401`; Login `200`;
  danach authentifizierter Zugriff `200`; fehlender CSRF-Header
  `403`; fremder Origin `403`; legitime Anfrage mit absichtlich
  ungültiger Nutzlast erreicht erst die Fachvalidierung `422`;
  Logout `200`; danach API erneut `401`.

## Technische Abnahme

| Bereich | Ergebnis | Prüfgrenze |
| --- | --- | --- |
| BA-01 Event-Revision/`event.json` | **PASS (synthetisch)** | SQLite-Outbox, Schreibfehler, Neustarts, kein Überschreiben fremder Dokumente |
| BA-02 Backup-Löschung | **PASS (synthetisch)** | Journale, Hashprüfung, Rückbau/Abschluss, Prozessabbruch und Nebenbibliothek |
| BA-03 Authentisierung und CSRF | **PASS (CI + echter isolierter Docker-HTTP-Test)** | Keine echte iOS-/Reverse-Proxy-Abnahme |
| BA-07 Arbeitsbereich-Reconcile | **PASS (synthetische Fehlerfälle)** | Physischer TrueNAS-Mehrbibliotheks-E2E noch offen |
| BA-08 Reassignment-Atomarität | **PASS (synthetisch)** | Gemeinsame SQLite-Transaktion, Idempotenz, Crashtests |
| BA-09 HTML-Text-Escaping | **PASS (Regression)** | Gesamt-XSS-/Abhängigkeitsaudit muss vor 1.0.0 gesondert erfolgen |
| BA-10 Root-Rename-Rückbau | **TEILWEISE** | Statischer Regressionstest; vollständige dynamische Fehler-/Neustartmatrix fehlt |
| BA-11 Schema-Kompatibilität | **PASS (Regression)** | Neuere, unbekannte Migrationsversion wird abgewiesen |
| BA-12 Metadaten-Swap | **PASS (synthetisch)** | Journal, SHA-256, Mehrfachdateien, Reintegration, harte Prozessabbrüche |
| BA-13 Release-Workflow | **PASS (statische Regression)** | Kein Force-Retag; tatsächliches Stable-Publishing nicht ausgeführt |
| Synthetisches Upgrade 0.40 → 0.50 | **PASS (CI)** | 0.40-Schema mit künstlichen Jobs/Ereignissen, Migration 41–52, FK/Integrity, Idempotenz |
| Upgrade 0.51 → 0.52 | **PASS (CI)** | Outbox-Migration und Wiederholung ohne Schemaänderung |
| BA-06 direkte SD-Karte/Discover | **OFFEN (separat)** | Root-/Privilegien-Sicherheitsmodell; Direkt-SD-Import bleibt erhalten |

**Wichtig:** Synthetische Migrationen beweisen nicht, dass alle Varianten einer
bereits produktiv befüllten Mehrbibliotheksdatenbank korrekt abgedeckt sind.

## Offen vor Merge, `latest` und Stable-Release

1. **TrueNAS-Isolation und Upgrade (BLOCKER):** Eine Kopie bzw. ein
   ausschließlich synthetischer Ausgangszustand muss unter denselben
   Mount- und ACL-Bedingungen durch ein tatsächliches 0.40.3→0.50.0-Upgrade
   geführt werden. Es dürfen niemals Produktivdaten eingebunden werden.
   Beide SQLite-Datenbanken und Registry prüfen, Worker-Anlauf,
   Mehrbibliothekskontext, Event-Dokumente, Abbruch und Neustart.
2. **Echte iPhone-PWA/WebKit-Abnahme (BLOCKER):** Login, Cookies auch nach
   Schließen/Neustart, CSRF an allen Aktionen, Abmelden, HTTPS-Reverse-Proxy
   und mobile Ansichten im Home-Screen-Modus prüfen.
3. **BA-10 dynamisches Root-Rename-Recovery-Gate (BLOCKER):** Fehler
   zwischen Dateisystem- und SQLite-Änderungen im synthetischen
   Mehrbibliotheksaufbau erzwingen, einschließlich hartem Prozessabbruch,
   und die erneute Einordnung aller Dateien belegen.
4. **Ende-zu-Ende-Datei-/Importkombinationen (BLOCKER):** Direkter
   SD-Kartenimport mit nichtproduktiver Testkarte, Metadaten,
   Sortierung, Archivprüfung, Wiedereinsortierung, Backup-Löschung,
   Hash-Prüfungen und wiederholtem Neustart in **isoliertem** TrueNAS.
5. **Publikations-/Historienprüfung (BLOCKER für Repository öffentlich):**
   Sämtliche erreichbaren Commits, Tags, Branches, Issue-/PR-Texte,
   Actions-Artefakte und Containerimages auf private Informationen und
   Geheimnisse prüfen; ggf. Schlüssel rotieren. Die QA-Skripte besitzen
   aktuell noch historische/konkrete Installationspfadbezüge. Der
   HEAD-Stand allein ist **kein** vollständiger History-Scan.
6. **Unabhängiger finaler Security-Review und Freigabeentscheidung:**
   Auth-/Proxy-Konfiguration, CSRF, Helper-Privilegien, Container- und
   Dateisystemzugriff sowie neue Regressionen nach Freigabekandidat
   unabhängig prüfen. Discover-/SD-Geräterecht bleibt separat.

## Veröffentlichungsentscheidung

**NICHT MERGEN, NICHT TAGGEN, NICHT `latest` ÜBERSCHREIBEN.**
Der auf `main` reagierende Publish-Workflow kann andernfalls den
Stable-Kanal verändern. Erst nach dokumentiert grünen offenen Gates
den finalen Commit eindeutig kennzeichnen, Image-Digest und Versionstag
dokumentieren und veröffentlichen.

Bis dahin bleibt das Repository **privat**, PR #19 **Draft** und
die aktuelle stabile Veröffentlichung **v0.40.3**.

## Bedienerhinweise

BA-03 verlangt vor jeder 0.50.0-Inbetriebnahme die Administratorpasswort-
Datei `/config/admin-password` mit Leserechten für die Web-UID.
Die vollständigen Anweisungen und HTTPS-Bedingungen stehen in
[BA03_HTTP_SECURITY.md](BA03_HTTP_SECURITY.md).
Keine produktiven SQLite- und Foto-Mounts für einen Test verwenden.
