# Bibliothekar

Selbst gehostete Web-App zur sicheren Verarbeitung und Organisation von Kameraaufnahmen auf TrueNAS.

Aktueller Entwicklungsstand: **0.33.5**

Aktuelle TrueNAS-/Container-Ausgabe: **0.33.5**  
Stabiler fachlicher Kamerakern als Basis: **0.32.11**

## Ziel

Die App unterstützt den Workflow von einer SD-Karte bis zur langfristigen Kamerabibliothek:

1. SD-Karte oder andere Quelle nur lesend erkennen und sichern
2. Metadaten prüfen
3. JPG/RAF-Dateien als Familien zusammenhalten
4. Aufnahmen Ereignissen oder `Ohne Ereignis` zuordnen
5. Arbeitsbereich strukturiert aufbauen
6. Nachträgliche Änderungen und Neu-Zuordnungen sicher behandeln
7. Archivierung kontrolliert vorbereiten und prüfen

Die App verändert die endgültige Kamerabibliothek nicht unkontrolliert.

## Kernprinzipien

- Originalquellen möglichst nur lesen
- keine stillen automatischen Moves in die endgültige Bibliothek
- Dateifamilien zusammenhalten
- Änderungen nachvollziehbar und prüfbar machen
- keine doppelten Zuordnungen
- offene Neu-Zuordnungen vor Abschluss sichtbar halten
- wiederverwendete SD-Karten inkrementell verarbeiten

## TrueNAS Custom App 0.33.5

0.33.5 stabilisiert die mit 0.33.0 eingeführte Ereignisbenennung und
Metadatenkorrektur auf der Mehrbibliotheks- und Sicherheitsarchitektur von
0.32.x. Die Einzelkorrektur schreibt nach dem bewussten Klick direkt über den
bestehenden Arbeitskopie-/ExifTool-/Verifikationsweg; ein separater
Vorbereitungsauftrag ist im normalen Ablauf nicht mehr nötig. Bestehende Ereignisse behalten ihren gespeicherten Benennungsstand;
neue Ereignisse und Sammelordner verwenden die bibliotheksspezifischen
Standardvorlagen.

### Gemeinsamer Kamera-Arbeitsbereich

TrueNAS bindet standardmäßig genau **einen** gemeinsamen read-write Host Path
als `/workspace` ein. Bibliothekar verwaltet darunter standardmäßig:

- `/workspace/SD-Kartensicherungen` – globaler Sicherungs- und freier Kamerabestand
- `/workspace/Arbeitsbereiche` – Stamm für frei benannte Bibliotheks-Arbeitsbereiche
- `/workspace/Metadatenkorrektur` – verwalteter Stamm für Metadatenkorrekturen
- `/workspace/Metadatenkorrektur/Allgemein` – allgemeine Einzeldatei-Korrektur

Ein technischer Bibliotheks-Identifier wie `main` ist **kein**
Dateisystempfad. Bibliothekar erzeugt daraus weder
`/workspace/Arbeitsbereiche/main` noch
`/workspace/Metadatenkorrektur/Bibliothek/main`. Maßgeblich sind immer die
vom Nutzer gespeicherten Arbeitsbereichs- und Archivpfade.

Die Namen der drei verwalteten Stammordner können unter
**Einstellungen → Pfade** geändert werden. Eigene TrueNAS-Datasets oder
Host-Path-Mounts werden von Bibliothekar weder erzeugt noch umgehängt.

### Bibliotheken

Jede Bibliothek besitzt eine eigene SQLite-Datenbank und einen explizit
gespeicherten Arbeitsbereich. Der Arbeitsbereich kann innerhalb von
`/workspace/Arbeitsbereiche` oder als eigener RW-Host-Path liegen. Sein Name
ist frei wählbar; eine Hauptbibliothek muss nicht `main` heißen.

Archive werden pro Bibliothek separat als read-only Host Path eingebunden. Das
Archiv bleibt für Bibliothekar read-only; physische Archivänderungen bleiben
kontrollierte Nutzeraktionen.

### Ereignisordner und Benennung

Die Ordnerstruktur für neue Ereignisse ist konfigurierbar und wird beim
Erstellen pro Ereignis eingefroren. Für normale Ereignisse sind optional:

- Jahr im Ordnernamen
- Uhrzeit im Ordnernamen
- Von–bis-Darstellung bei mehrtägigen Ereignissen

Sammelordner (intern weiterhin `no_event`) besitzen eine frei wählbare
sichtbare Bezeichnung, standardmäßig `Ohne Ereignis`. Da sie mehrere
getrennte Zeitsegmente eines Monats enthalten können, gibt es dort keine
Von–bis- oder Uhrzeit-Darstellung; optional kann das Jahr vor dem Monat stehen.

Die Einstellungsseite zeigt eine gemeinsame Vorschau für normales Ereignis und
Sammelordner einschließlich der aktuell gewählten Unterordnerstruktur.

### Metadatenkorrektur 0.33.5

Die Seite **Metadatenkorrektur** besitzt den normalen Bibliothekar-Header und
einen zweiten Reiterheader mit:

- **Bibliothek** – zeigt den globalen freien `Ohne_Datum`-Bestand als
  gemeinsame Liste, unabhängig davon, aus welcher Bibliothek der Kameraimport stammt.
- **Allgemein** – verwendet direkt
  `/workspace/Metadatenkorrektur/Allgemein`.
- **Mehrfachkorrektur** – in 0.33.5 bereits als geplanter Reiter sichtbar;
  die Funktion folgt mit 0.34.0.

Für **Allgemein** gibt es keinen Eingang/Ausgang. Ein Klick auf
**Metadaten ändern** friert den Ausgangszustand ein, arbeitet auf einer
geprüften Arbeitskopie, schreibt die gewählte Aufnahmezeit mit ExifTool, liest
die Metadaten erneut und ersetzt die Originaldatei erst nach erfolgreicher
Verifikation atomar am selben Ort. Sekunden werden vollständig übernommen.
Offene oder blockierte Korrekturen werden im globalen Aufgabenbereich pro
Metadaten-Reiter gebündelt statt als eine Aufgabe pro Datei dargestellt.

Bei **Bibliothek** wird eine komplette Ohne-Datum-Dateifamilie eingefroren.
**Metadaten ändern** schreibt die korrigierte Aufnahmezeit auf Arbeitskopien,
liest und prüft die Metadaten erneut und ersetzt erst danach die Dateien
atomar am bisherigen `Ohne_Datum`-Ort. Die Familie bleibt dort sichtbar und
wird als **Bereit zum Einsortieren** markiert. Erst der getrennte Befehl
**In Tagesbestand einsortieren** berechnet denselben kanonischen
Tages-/Zeitbestand wie beim Kameraimport, vergibt den normalen Bibliothekar-
Dateinamen und verschiebt die geprüfte Familie dorthin. Dateipfade, aktuelle
SHA-256-Werte und Aufnahmezeiten werden in alle Bibliotheksprojektionen
gespiegelt; der ursprüngliche Quellfingerprint bleibt erhalten.

Die Bibliotheks-Metadatenkorrektur erzeugt insbesondere **keine** Ordner
`Bibliothek/main/Eingang/Ausgang`. Leere Überreste dieses 0.33.0-Entwurfs
dürfen automatisch entfernt werden; enthalten sie Dateien, werden sie niemals
automatisch gelöscht.

### 0.34.0 – vorgemerkte Mehrfachkorrektur

Für zusammengehörige Kameraaufnahmen mit falsch eingestellter Kamera-Uhr ist
`/workspace/Metadatenkorrektur/Mehrfachkorrektur` vorgesehen. In 0.34.0 wird
eine Referenzaufnahme ein korrektes Datum mit Uhrzeit erhalten; derselbe
Zeitversatz wird anschließend auf die übrigen Aufnahmen übertragen, sodass
deren zeitliche Abstände erhalten bleiben. Vor dem Schreiben wird eine
vollständige Alt→Neu-Vorschau gezeigt. Diese Funktion ist in 0.33.5 noch nicht
aktiv.

### Basis-Containerpfade

- `/config` – Anwendungskonfiguration
- `/database` – Bibliotheksdatenbanken und globale Registry
- `/logs` – Protokolle
- `/workspace` – gemeinsamer Kamera-Arbeitsbereich, read-write
- Bibliotheksarchive – jeweils eigener read-only Host Path
- optionale externe Bibliotheks-Arbeitsbereiche – eigener read-write Host Path
- `/sources/import` – zusätzliche allgemeine Importquelle, read-only
- `/sources/nas` – NAS-Quellen, read-only
- `/sources/removable` – Mountpunkt für Wechselmedien
- `/tmp` – flüchtiges tmpfs

`compose.example.yaml` enthält die Ein-Container-Vorlage.

## Projektstruktur

- `app/` – Anwendung
- `tests/` – automatisierte Backend-Tests
- `tools/` – allgemeine Diagnose- und Hilfswerkzeuge
- `docs/` – Architektur- und Projektdokumentation
- `qa/` – Testmatrix, Fixtures und Testlaufberichte
- `.github/` – CI- und Container-Publishing

## Entwicklungsmodell

Funktionale Regressionen sollen möglichst automatisiert getestet werden.

Drei Ebenen:

1. Unit-/Backend-Tests
2. automatisierte Integrations- und QA-Tests
3. manuelle UI-/UX-Endabnahme

## Roadmap

### 0.30
Bibliotheksfundament mit globaler Registry und getrennten Bibliothekskontexten.

### 0.31
Mehrere Bibliotheken mit eigener SQLite-Datenbank, eigener Archivzuordnung, globalen Familien-Claims und tab-sicherem Bibliothekskontext.

### 0.32
Mehrbibliotheks-Lifecycle, zentraler freier Bestand und TrueNAS-/Archiv-Härtung.

### 0.33
Bibliotheksspezifische Ereignisbenennung sowie sichere Metadatenkorrektur mit
Dateinamenerkennung, getrennten Bereichen „Bibliothek“/„Allgemein“ und
verifiziertem Schreibworkflow.

### 1.0.0
Stabiler Kamera-Kern ohne Immich und ohne KI-Vorsortierung.

### danach
Manuell startbare KI-Vorsortierung mit Open-Weight-Modell auf dem GX10.

### später
Immich-Anbindung.

## Status

Das Projekt befindet sich aktiv in Entwicklung und ist noch nicht für unbegleitete Produktivinstallationen freigegeben.

## Lizenz

Bibliothekar ist freie Open-Source-Software unter der GNU Affero General Public License v3.0.

Siehe [LICENSE](LICENSE).
