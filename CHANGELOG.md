# Changelog

## [Unreleased]

### 0.22.0 – Redesign / Produktschale

- gemeinsamer Bibliothekar-App-Rahmen für Import, Arbeitsbereich und Archiv
- drei überlappende Hauptreiter im Bauhaus-inspirierten Design
- Arbeitsbereich bündelt Aufnahmen und Ereignisse als Unterbereiche
- Aufgaben wandern aus dem Floating-Button in den Header
- Menü mit Einstellungen, Bibliothek wechseln und Über Bibliothekar
- Hell-, Dunkel- und Systemdarstellung
- vorbereiteter, noch inaktiver Bibliothekar-Assistent unten rechts
- Importquellen als kompakte Auswahl für SD-Karte, Laufwerk und Ordner/Sicherung
- Import- und Prüfverlauf mit komprimiertem Vorschaubild aus dem frühesten JPEG
- dateiweise Fortschrittsmeldungen beim Inventarisieren, Kopieren und Verifizieren
- deutsche Statusbegriffe bleiben fachlich nah an geplant / angewendet / archiviert
- bestehende Importwege und Kernfunktionen bleiben erhalten

### 0.21.2 – Patch in Arbeit

- normale Zeitsegmente können ergänzt und vollständig entfernt werden
- Neu-Zuordnung arbeitet auf Tages-/Zeitsegmentebene statt Familien-Drilldown
- bestehende Ereignisse und neue Unterereignisse sind Neu-Zuordnungsziele
- gespeicherte „Ohne Ereignis“-Segmente bleiben kanonische Zeitdefinition
- pending/Nachsortierung wird deutlich als noch nicht angewendet markiert
- freie Restzeiten werden sekundengenau berechnet
- archivierte Ereignisse können mehrere Unterereignisse im manuellen IST→SOLL-Auftrag abbilden
- SD-Wiederverwendung ignoriert Verwaltungsdateien und zeigt 0 neu / 0 verändert als normalen Zustand
- Archiv-E2E-Tests verwenden eine getrennte beschreibbare QA-Testbibliothek

### Weiter geplant / offen

- Zeitsegmente beim Bearbeiten vollständig löschen können
- Reassignment-Dialog ohne Familien-/Datei-Drilldown
- gespeicherte Zeitsegmente von `Ohne Ereignis` korrekt anzeigen
- applied-Erweiterungen klar als noch anzuwendende Änderung kennzeichnen
- freie Restzeit eines Tages nach Löschen eines Ereignisses korrekt berechnen
- archived einfaches Ereignis nachträglich sauber in Ober-/Unterereignisse überführen
- herausfallende Familien auch als Unterereignis eines bestehenden Ereignisses neu zuordnen
- SD-UX bei `0 neu / 0 verändert` verbessern
- Kamera-Verwaltungsdateien nicht dauerhaft als `neu` ausweisen
- skalierbare Listen mit Einklappen und Pagination
- portable TrueNAS-Installation und Updatepfad

## [0.21.1]

### Behoben

- SD-Kartenstatistik verwendet jetzt die aktuell eingebundene Wechselquelle
- veraltete Legacy-Mounts werden aufgeräumt
- wiederverwendete SD-Karten werden korrekt neu erkannt

### Vorhanden

- inkrementeller SD-Import
- bereits gesicherte Dateien werden erkannt
- neue Dateien können separat als eigener Sicherungslauf importiert werden
- Schema-Version 22
