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
| T060 | herausfallende Familien zu bestehendem Ereignis |
| T061 | herausfallende Familien zu neuem Ereignis |
| T062 | herausfallende Familien zu Ohne Ereignis |
| T063 | neues Unterereignis eines bestehenden Oberereignisses |
| T064 | Änderung verwerfen |
| T065 | Reassignment-Zustand nach Neustart erhalten |
| T066 | keine Einzeldatei-/Familienabwahl im Tagesdialog |

## Archiv

| ID | Test |
|---|---|
| T080 | applied Ereignis archivieren |
| T081 | Archivprüfung |
| T082 | archived Ereignis umbenennen |
| T083 | archived Zeitraum ändern |
| T084 | archived einfaches Ereignis zu Oberereignis umbauen |
| T085 | herausfallende Dateien einem neuen Unterereignis zuordnen |
| T086 | manuellen Änderungsauftrag erzeugen |
| T087 | manuelle Verschiebung anschließend prüfen |
| T088 | Archivbestand niemals automatisch verändern |

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
