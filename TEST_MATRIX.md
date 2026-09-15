# Testmatrix

Die Testmatrix verhindert, dass dieselben Funktionen immer wieder manuell und unsystematisch geprüft werden.

Jeder Test besitzt eine eindeutige ID.

Statuswerte:

- `PASS`
- `FAIL`
- `BLOCKED`
- `SKIPPED`
- `NOT_RUN`

## SD-Import

| ID | Test |
|---|---|
| T001 | SD-Karte erstmals erkennen und read-only einbinden |
| T002 | Erstimport einer neuen SD-Karte |
| T003 | dieselbe SD unverändert erneut einstecken |
| T004 | dieselbe SD mit neuen Medien erneut einstecken |
| T005 | Kamera-/Systemdateien korrekt ignorieren |
| T006 | stale Mount nach Auswerfen/Wiedereinstecken bereinigen |
| T007 | gleicher Dateiname, anderer Inhalt |
| T008 | Sicherungslauf nach Neustart weiterhin nachvollziehbar |

## Ereignisse – normal

| ID | Test |
|---|---|
| T020 | einfaches Ereignis ganzer Tag |
| T021 | einfaches Ereignis mit Uhrzeit |
| T022 | Ereignis mit zwei Unterereignissen |
| T023 | Überlappung von Zeitsegmenten verhindern |
| T024 | applied Ereignis verkleinern |
| T025 | applied Ereignis erweitern |
| T026 | Zeitsegment bearbeiten |
| T027 | Zeitsegment vollständig löschen |
| T028 | applied Ereignis löschen |
| T029 | freien Restzeitraum nach Löschen korrekt berechnen |

## Ohne Ereignis

| ID | Test |
|---|---|
| T040 | neue Monats-Sammlung anlegen |
| T041 | Monats-Sammlung erweitern |
| T042 | bestehende Zeitsegmente korrekt anzeigen |
| T043 | Segment verkleinern |
| T044 | herausfallende Familien neu zuordnen |
| T045 | keine zweite Monats-Sammlung desselben Monats erzeugen |
| T046 | applied Erweiterung sichtbar als pending/Nachsortierung kennzeichnen |

## Reassignment

| ID | Test |
|---|---|
| T060 | herausfallende Tages-/Zeitsegmente zu bestehendem Ereignis |
| T061 | herausfallende Tages-/Zeitsegmente zu neuem Ereignis |
| T062 | herausfallende Tages-/Zeitsegmente zu Ohne Ereignis |
| T063 | neues Unterereignis eines bestehenden Oberereignisses |
| T064 | Änderung verwerfen |
| T065 | Reassignment-Zustand nach Neustart erhalten |
| T066 | keine Einzeldatei-/Familienabwahl im Tagesdialog |

## Archiv

Archivtests T080–T088 werden ausschließlich gegen die beschreibbare QA-Testbibliothek
`/mnt/storage/ki-workspace/hermes/bibliothekar-qa/archive-test-library` ausgeführt. Die reale
Kamerabibliothek `/mnt/storage/fotos/Kamerabibliothek` bleibt read-only und ist niemals Testziel.

### Verbindlicher Dateisystem-Nachweis für T080–T088

API-, UI- und SQLite-Zustände reichen für diese Tests **nicht** als PASS aus. Nach jedem relevanten
Archiv-, Reassignment- oder manuellen IST→SOLL-Schritt muss `nas-agent` den tatsächlichen Bestand
unter `archive-test-library` gegen den zu diesem Schritt erwarteten SOLL-Zustand prüfen.

Der Vergleich umfasst mindestens:

- exakte relative Datei- und Ordnerpfade
- erwartete und tatsächliche Dateianzahl
- Dateigröße und, für die verwendeten Testkopien, SHA-256
- vollständigen Zusammenhalt jeder Dateifamilie in genau dem vorgesehenen Zielordner
- korrekte Ober-/Unterereignis- und `Alle`-Ordnerstruktur
- keine fehlenden Dateien
- keine verbliebenen Dateien oder veralteten Restordner
- keine ungewollten Duplikate desselben Dateiinhalts an mehreren Archivpfaden
- keine Symlinks als Ersatz für erwartete Archivdateien

Vor dem Schritt werden IST und konkreter IST→SOLL-Plan gesichert; nach dem Schritt wird ein
SOLL-Manifest erzeugt und mit `qa/archive_e2e/verify_filesystem_state.py` gegen den realen
QA-Archivbestand geprüft. Der maschinenlesbare Nachweis gehört in den Laufordner und wird in
`results.json` unter `filesystem_checks` referenziert. Ein T080–T088-Test darf nur dann `PASS`
erhalten, wenn alle für ihn relevanten Dateisystemprüfungen `PASS` sind.

| ID | Test |
|---|---|
| T080 | applied Ereignis in QA-Testbibliothek archivieren; realen Zielbestand vollständig gegen SOLL prüfen |
| T081 | Archivprüfung gegen realen QA-Dateibestand einschließlich Pfade, Zählung, Familien und Duplikate |
| T082 | archived Ereignis umbenennen, IST→SOLL prüfen und realen Dateisystemzustand nach Umsetzung vergleichen |
| T083 | archived Zeitraum ändern; herausfallende Segmente erkennen und verbleibenden/herausfallenden Dateibestand prüfen |
| T084 | archived einfaches Ereignis zu Oberereignis mit Unterereignissen umbauen und Unterereignisordner real prüfen |
| T085 | herausfallende Dateien einem neuen oder bestehenden Unterereignis zuordnen und Familienzusammenhalt am Ziel prüfen |
| T086 | manuellen Änderungsauftrag mit konkreten Pfaden erzeugen und jeden geplanten alten/neuen Pfad gegen IST/SOLL belegen |
| T087 | manuelle Verschiebung in QA-Testbibliothek anschließend vollständig prüfen; keine Restdateien, Restordner oder Duplikate |
| T088 | reale Kamerabibliothek niemals verändern; Schreibzugriff muss ausgeschlossen bleiben und QA-Archiv-Endzustand dokumentiert sein |

## Sicherheits- und Wiederanlauf

| ID | Test |
|---|---|
| T100 | Abschluss bei offenem Reassignment blockieren |
| T101 | Abschluss nach Reassignment wieder erlauben |
| T102 | Browser-Reload bei offenem Zustand |
| T103 | App-Neustart bei offenem Zustand |
| T104 | keine Duplikate nach wiederholter Aktion |
| T105 | DB-/Dateisystem-Konsistenzprüfung |

## UI / Skalierung

Diese Tests bleiben überwiegend manuell.

| ID | Test |
|---|---|
| U001 | mobile Darstellung |
| U002 | keine überlappenden Aktionsboxen |
| U003 | lange Ereignislisten einklappbar |
| U004 | Pagination Ereignisse |
| U005 | Pagination Archiv |
| U006 | klare pending/applied-Darstellung |
