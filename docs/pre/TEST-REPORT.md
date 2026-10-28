# 1.0.0-pre – Prüfstand

Basis: veröffentlichter Tag `v1.0.0-rc.14`,
`405bcce0593b4e82d13e656c110ec0bd06d59607`.
Branch: `codex/1.0.0-pre`. Endgültiger Prüfcommit/CI werden nach Abschluss ergänzt.
Keine Veröffentlichung, kein Tag und kein Registry-Push.

## Reproduktion und Korrektur

- Echtes synthetisches JPEG mit tatsächlichem ExifTool: vor Änderung 4 Fehler /
  1 Erfolg in fünf Offsetfällen. `_apply_library_metadata_correction` schrieb den
  vollständigen Offset in EXIF/XMP, schnitt ihn im Katalog und Journal jedoch mit
  `[:19]` ab. Reintegration erwartete dadurch Berlinzeit statt `+13:00`.
- Offset bleibt jetzt in Task, Familien-/Dateikatalog, Analyse und Swapjournal.
  RC14-Altbestand wird nur anhand seines exakten abgeschlossenen Taskbelegs
  qualifiziert; Tags werden vor dem Verschieben weiter strikt geprüft.
- Cache-Reentry reproduziert: große Antwort mit 3.980 Dateien ließ den alten
  88-Dateien-Snapshot zurück. Neuer komprimierter Snapshot ersetzt ihn; asynchrone
  alte Antworten werden verworfen. Backend lehnt das Publizieren einer unterdessen
  veralteten DB-/WAL-basierten Berechnung in seinen Cache ab.
- Zähler unterscheiden echte Reviewfälle und korrigierte, noch nicht einsortierte
  Dateien anhand des gespeicherten Korrekturstatus.
- General-Import bleibt ein dauerhafter Backendjob; gleiche ausgewählte Bytes
  haben eine stabile Admission-ID. UI rekonstruiert laufenden Job nach Reload und
  wartet auf dessen echten terminalen Status. Keine neue Jobarchitektur.
- Archivrename ist ausschließlich eine optionale, live geprüfte Darstellung.
  Wiederherstellungs-/Verifyprüfungen, Reparaturfunktion und RO bleiben bestehen.

## Tatsächliche lokale Ergebnisse

macOS, Python3.13, echtes ExifTool13.30, Playwright1.62.1/Chromium, ausschließlich temporäre
synthetische Fixtures. Erste Offset-/Swap-Gruppe: **33 PASS**; erweiterte Gruppe
53 PASS mit einer veralteten Quelltext-Erwartung (`proposed[:19]`), die auf den
jetzt vollständigen Wert aktualisiert wurde. Rename-Gegenproben **8 PASS**.
Cache-Gruppe 13 PASS, ein direkter API-Test scheiterte ohne isolierte globale
Workspacekonfiguration; das vorgesehene isolierte Runnerprofil wird verwendet.
Die endgültigen Gate-Zahlen und CI-Nachweise folgen hier nach Ausführung.

Vollständiges Gate: `.github/workflows/qa-pre.yml`, read-only permissions,
keine Veröffentlichung. Enthält gezielten Gate, sämtliche acht Backendpartitionen,
bisherige Chromium-Suiten plus pre, originale RC14→pre-Metadatenreproduktion und
alle bestehenden RC10–RC14 Docker-/Supervisor-/Crash-/Reparaturfälle.

Docker lokal nicht verfügbar; reale Containerabnahme wird auf isoliertem Linux-CI
angestrebt. Native TrueNAS und physische SD-/USB-Hardware bleiben NOT RUN.
Begründete DEFERRED-Anforderungen: [OPEN-RISKS.md](OPEN-RISKS.md).

## Einzelabgleich der 19 Screenshots

Alle Bilder wurden einzeln im Original angesehen. Die Nummern beziehen sich auf
`alt_01…alt_13` und `neu_01…neu_06` des Auftragspakets.

| Bild | Befund / Umsetzung | Prüfpfad |
|---|---|---|
| alt01 | SHA-Wartehinweis übersetzen; Prüfung bleibt aktiv | pre Chromium-Meldungen, historische Sortierprüfungen |
| alt02 | Bekannter Kameraimport / Metadata safe übersetzen; keine neue Herkunft | pre Chromium, Provenienzregressionen |
| alt03 | ExifTool/DNG1.7-Fehler lokalisieren, Originaldiagnose erhalten | pre Meldungen; Original-DNG **DEFERRED** |
| alt04 | General-Job sichtbar, Busy und Reload-Wiederaufnahme | pre Chromium echte Pollhandler; deduplizierte Admission |
| alt05 | Reine Umbenennung + event.json statt fünf generischen Gruppen | kompletter Rename-Assistent-Test, negative Inventarprüfungen |
| alt06 | Dieselbe kompakte Gegenrichtung | realer Rename-/Reversal-Rundlauf |
| alt07 | Vorhandene Original-/Restoration-Struktur ist korrekt | unverändert; bestehende Archiv- und Crashtests |
| alt08 | Verify-Fehler → zurück zur neu gescannten Wiederherstellung | tatsächlicher Reversalrenderer; bestehende strenge Verifyfälle |
| alt09 | Zahl offener Punkte und fehlender Ordner lokalisieren | UI-Katalog/Chromium; ursprüngliche Ordnersperre bleibt |
| alt10 | Fehlende/abweichende Originaldatei verständlich | Meldungen + bestehende SHA-/Restoration-Negativfälle |
| alt11 | Fehlende ursprüngliche event.json übersetzen | Meldungen + Reversal-Negativfälle |
| alt12 | Erfolgreiche Wiederherstellung beibehalten | bestehende Reversaltests + neuer realer Rundlauf |
| alt13 | Bibliothek während Import gesperrt: Fehlermeldung übersetzen | UI-Meldungen + RC14-Lifecycle-/Containerfälle |
| neu01 | Mehrfachauswahl: Quelltyp, Bulk-Status, keine redundante Familienzahl | tatsächliche Metadata-UI, pre Meldungen |
| neu02 | Wie neu01, korrigiert und bereit zum Einsortieren | Real-ExifTool-Korrekturtests, UI |
| neu03 | +13-Verifikation durchgängig, keine Offsettrunkierung | Reproduktion vor Änderung; RC14→pre-Containerfall |
| neu04 | Alter 88-Dateien-Cache nach großem Import | tatsächliches loadWorkspace, >1.8M Snapshot, Antwortreihenfolge |
| neu05 | 0 Reviewfälle und 14 bereit zum Einsortieren unterscheiden; Tage EN | committed correction counters; UI-Katalog/Chromium |
| neu06 | Einzel-Reintegration mit identischem Offsetfehler | fünf reale Zeitvarianten; RC14-Beleg-Positiv-/Negativfälle |

Aktualisiert: lokale eng begrenzte Schlussgruppe **30 PASS**, zusätzliche
Rename-/Race-/Admission-Gruppe **14 PASS**. Die isolierte breite lokale Gruppe
bestand 137 Fälle; zwei beim Start noch geladene RC14-Versionserwartungen wurden
im Releasevertrag auf pre umgestellt und anschließend erfolgreich erneut geprüft.
Erster Linux-Gate und Browser im Lauf `40786248750`: PASS. Dieser Lauf wird für
den nachträglich ergänzten vollständigen Rename-Rundlauf ersetzt.
Zwischenstand: `4ae0e2314650bcea5c8fa8f46a27ad36668f1c79`.
Zusätzliche tatsächliche RC14-Belegtrunkierung in Fixture reproduziert und
behoben; auch die gekürzte Belegzeit muss exakt zum Katalog passen.
Die vollständige Taskzeit und alle Live-/Mitgliedsprüfungen bleiben zwingend.
Endgültige vollständige Abnahme: [40786897485](https://github.com/heller-adrian/Bibliothekar/actions/runs/40786897485), **noch ausstehend**.
