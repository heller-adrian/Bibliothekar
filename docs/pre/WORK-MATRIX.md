# 1.0.0-pre – Arbeitsmatrix vor Implementierung

Basis v1.0.0-rc.14 = 405bcce0593b4e82d13e656c110ec0bd06d59607,
Anwendung b43d9fb9d957cb817f74e6fee303b6413d91cd38. Lokales HEAD war
ab22854b; Remote-Nacharbeiten wurden gelesen, neuer Zweig codex/1.0.0-pre
exakt vom Tag angelegt. Unversioniertes qa/rc14.zip bleibt erhalten.
Alle sechs Textunterlagen und 19 Bilder einzeln vollständig gelesen; Paket-SHA
vollständig geprüft. Benutzerauftrag untersagt Tag, Release und Registry-Push.

| Prio/Anforderung | Tatsächlicher Pfad | Ursache/Hypothese vor Test | Test vor Änderung / Änderung / Risiko |
|---|---|---|---|
| P0 N1–N3,N6 Zeitzone | main.api Batch → create_metadata_correction → _apply_library_metadata_correction → reintegrate_library_metadata_family | Kandidatenoffset wird beim Erstellen wiederhergestellt; _apply schreibt +13 korrekt, persistiert jedoch [:19]. Reintegration erwartet naive Berlinzeit. | Echtes JPEG EXIF/XMP +13, kompletter Lauf; Offset durchgehend erhalten, Legacy nur aus passendem abgeschlossenem Tasknachweis qualifizieren; hohes Datenrisiko |
| P1 N4 Cache | workspace_ui.loadJobs/loadWorkspace; view_cache | >1.8M ersetzt alten kleinen Snapshot nicht; mehrere Antworten können rückwärts eintreffen. Backendcache stempelt Ergebnis erst nach Berechnung. | DOM große Antwort/Reentry/überholte Antwort; WAL-Wechsel zwischen Lesen und Publikation; keine Vollscans hinzufügen |
| P1 N5 Zähler | workspace_ui.renderDays/renderSummary, Metadata scan | korrigierte undatierte Familie ist nicht mehr review_required, bleibt aber im Ohne-Datum-Pfad | reale corrected/required Fixtures, kurze getrennte Statusanzeige; Datenmodell unverändert |
| P1 Quelle/Installation | main.SOURCE_HELPER_URL, container_supervisor, Dockerfile/Compose, removable_runtime/source_helper | DNS-Default passt nicht zum Loopback; Enabled-Defaults divergieren | Default-/Supervisor-/Mountguards, echter Linuxcontainer; native Hardware/NFSv4 bleibt NOT RUN |
| P1 alt01–04,09–11,13 + neu01–06 i18n | UI-I18n-Kataloge, Fehler- und Taskrenderer | fehlende genaue/dynamische Meldungen | tatsächliche Renderer EN/DE, mobile/desktop, technische Pfade/Tags unverändert; kein Verifikationsbypass |
| P1 alt04 General Feedback | metadata_correction_ui → POST General-Reintegrationsjob | 202 wird nur als kleiner Text sichtbar; bestehende Jobinfrastruktur vorhanden | zweifacher Klick, laufender Backendjob, Reload und Ende/Fehler; UI aus echten Backendzuständen |
| P1 Desktop Doppelklick | workspace_ui.renderDays, Eventkarte | Undated-Doppelklick vorhanden; Event-Doppelklick/Navigation prüfen | echte DOM-Clicks, Keyboard und Mobile-Handler unverändert |
| P1 alt05–06 Rename-only | archive_change_assistant / archive_reversal / events_ui | generische Schritte trotz reiner Pfadpräfixänderung | vollständiges Live-Inventar+Hashes+Konflikte qualifizieren; kompakte reine Anleitung, RO und Abschlussprüfung bleiben |
| P1 alt08–12 zurück zu Arbeit | events_ui Verify/Manual, Assistent scan_live | keine klare Rücknavigation; bereits vorhandene Live-Prüfung nutzen | fehlgeschlagene Prüfung → frisch geprüfte manuelle Ansicht → restaurieren → Erfolg; kein alter PASS |
| Sicherheitsentscheidung Verlustabschluss | archive_reversal force_cancel, Claims/Journale | heutiger Manual-resolution-Status ist kein erfolgreicher Archivabschluss | dokumentiertes Verlustmodell+Negativtests; bei fehlender sicherer Endsemantik bewusst DEFERRED |
| Kompatibilität alt03 DNG1.7 | write_metadata_datetime/ExifTool | konkrete Formatwarnung; Originaldatei nicht im Paket | synthetische Kopie, Toolversion und Rollback; keine Warnungsunterdrückung, native Originaldatei NOT RUN |
| alt07 Evidenzstruktur | Reversal/.../Restoration + baseline/request/Original | kein Fehler, ausdrücklich unverändert | vorhandene Crash-/Reversaltests |
| alt12,13 Erfolg/Sperre | Reversal-Verifikation, library_retirement/F14 | korrektes Verhalten bewahren | SHA/Original-JSON-Gegenproben, Importbusy, keine erzwungene Entfernung |

Budget ab 29 %: Ziel +6, harte Grenze +10 Prozentpunkte (=39 %), kein Verbrauchsziel.
Nächster Schritt: P0 deterministisch reproduzieren; dann begrenzte Korrekturen,
gezielte Tests und ein gebündeltes vollständiges Linux-/Browser-/Containergate.

## Fortschritt

Offsetfehler vor Änderung mit echtem ExifTool reproduziert; vollständiger Offset
bleibt jetzt erhalten. RC14-Recovery verlangt passende Task-/Mitgliedsbelege;
Negativfälle und DST-Lücken werden gesperrt. Cache-Reentry reproduziert und
korrigiert. 44 historische RC13- und 147 RC14-Chromiumfälle sowie vier neue
EN/DE-/Mobile-/General-Reload-Fälle lokal bestanden. Rename-Negativfälle und
bestehende Archive-/Reversaltests: 23 PASS. Vollständiges read-only CI-Gate
vorbereitet, noch nicht abgeschlossen. Nächster Schritt: gezieltes Gate bereinigen,
CI auf dem Prüfcommit ausführen, alle Artefakte prüfen. Keine Veröffentlichung.

## Budget-/Übergabestand

Wochenanzeige 39 % (Start29 %): genehmigungsfreie Auftragsgrenze erreicht;
Erweiterung bis42 % angefragt. Bis Antwort keine weitere Entwicklung/CI starten.
Remote-Prüfstand4ae0e231, Lauf40786897485: Browser195PASS,
Targeted148PASS. Backend3 und4 jeweils283PASS;5 und7 jeweils281PASS,
je ein README-Versionsfehler, lokal behoben (2PASS). Restpartitionen laufen.
Lokaler zusätzlicher Commit1c0b3033: tatsächliche RC14-Belegtrunkierung
berücksichtigt (Metadatengruppe13PASS), General-Admission gegen Quellwechsel
gepinnt (2PASS). Noch nicht gepusht. README-Version, QA-ExifTool-Versionsnachweis
und aktualisierter Prüfbericht liegen zusätzlich uncommitted vor.
Nächster Schritt nach Budgetfreigabe: übrige Backendfehler bündeln; lokale
Nachträge committen/pushen; vollständiges Gate auf endgültigem Commit,
reale RC14→pre-Containerreproduktion und bestehende RC10–RC14-QA prüfen;
alle Artefakte/Partitionen/SKIPs nachweisen und Abschlussbericht fertigstellen.
Keine Veröffentlichung/Tags/GHCR-Push, keine NAS-Änderung.

Budgeterweiterung bis42 % ausdrücklich vom Benutzer genehmigt. Vorlauf40786897485
vollständig ausgewertet:2256PASS/5FAIL, keine SKIPs. Fehler: README-Version2,
alte Quellen-Erwartungen für Helper-Opt-in, Undated-Status und Autoscan3.
Erwartungen passend zur beauftragten Funktion aktualisiert; Schutzassertions
bleiben erhalten. Reale RC14-Beleg-/Admission-Korrektur in1c0b3033 gesichert.
Gebündelter Nachlauf folgt auf dem abschließenden Prüfstand.
