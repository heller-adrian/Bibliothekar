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

macOS, Python3.13, echtes ExifTool, Chromium1.62.1, ausschließlich temporäre
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
