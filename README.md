# Bibliothekar

Selbst gehostete Web-App zur sicheren Verarbeitung und Organisation von Kameraaufnahmen auf TrueNAS.

Aktuelle veröffentlichte Version: **0.47.1**

Container für TrueNAS: **`ghcr.io/heller-adrian/bibliothekar:latest`**

Aktuelles Testimage: **`ghcr.io/heller-adrian/bibliothekar:patch-0.47.1`**

## Updates

Für normale Installationen wird in TrueNAS als Image-Version **`latest`** verwendet. `latest` zeigt ausschließlich auf den zuletzt freigegebenen Stand von `main`.

Ein Update besteht damit nur noch daraus, in TrueNAS nach einem neuen Image zu suchen bzw. die App zu aktualisieren. Für reproduzierbare Installationen und Rollbacks bleiben zusätzlich feste Versionstags wie `0.40.2` erhalten.

Entwicklungsstände auf `patch/*` werden weiterhin separat als Testimages veröffentlicht, verändern aber **niemals** `latest`.

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

## TrueNAS Custom App

0.34.0 aktiviert die Mehrfachkorrektur auf der stabilen 0.33.x-
Metadatenarchitektur. Eine Aufnahme dient als Referenz: Aus ihrer vorhandenen
Aufnahmezeit und der vom Nutzer eingetragenen tatsächlichen Zeit berechnet
Bibliothekar einen konstanten Zeitversatz und zeigt vor jeder Änderung eine
vollständige Alt→Neu-Vorschau für den gesamten verwalteten Ordner. Erst nach
Bestätigung werden die Dateien über Arbeitskopien mit ExifTool geschrieben und
erneut verifiziert.

### Gemeinsamer Kamera-Arbeitsbereich

TrueNAS bindet standardmäßig genau **einen** gemeinsamen read-write Host Path
als `/workspace` ein. Bibliothekar verwaltet darunter standardmäßig:

- `/workspace/SD-Kartensicherungen` – globaler Sicherungs- und freier Kamerabestand
- `/workspace/Arbeitsbereiche` – Stamm für frei benannte Bibliotheks-Arbeitsbereiche
- `/workspace/Metadatenkorrektur` – verwalteter Stamm für Metadatenkorrekturen
- `/workspace/Papierkorb` – verwalteter Papierkorb ohne automatische Löschfrist
- `/workspace/Metadatenkorrektur/Allgemein` – allgemeine Einzeldatei-Korrektur
- `/workspace/Metadatenkorrektur/Mehrfachkorrektur` – unabhängige Korrektur zusammengehöriger Aufnahmen mit konstantem Zeitversatz

Ein technischer Bibliotheks-Identifier wie `main` ist **kein**
Dateisystempfad. Bibliothekar erzeugt daraus weder
`/workspace/Arbeitsbereiche/main` noch
`/workspace/Metadatenkorrektur/Bibliothek/main`. Maßgeblich sind immer die
vom Nutzer gespeicherten Arbeitsbereichs- und Archivpfade.

Die Namen der vier verwalteten Stammordner können unter
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

### Metadatenkorrektur 0.34.0

Die Seite **Metadatenkorrektur** besitzt den normalen Bibliothekar-Header und
einen zweiten Reiterheader mit:

- **Bibliothek** – zeigt den globalen freien `Ohne_Datum`-Bestand als
  gemeinsame Liste, unabhängig davon, aus welcher Bibliothek der Kameraimport stammt.
- **Allgemein** – verwendet direkt
  `/workspace/Metadatenkorrektur/Allgemein`.
- **Mehrfachkorrektur** – verwendet direkt
  `/workspace/Metadatenkorrektur/Mehrfachkorrektur` und korrigiert alle
  enthaltenen unterstützten Mediendateien relativ zu einer Referenzaufnahme.

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

### Mehrfachkorrektur

Der Ordner `/workspace/Metadatenkorrektur/Mehrfachkorrektur` wird beim
Anwendungsstart automatisch angelegt. Der Workflow ist bewusst unabhängig von
einer Bibliothek:

1. Dateien in den Ordner legen und **Bestand prüfen**.
2. Eine Datei als Referenzaufnahme wählen und ihr tatsächliches Datum mit
   Uhrzeit eintragen.
3. **Vorschau berechnen** zeigt für jede Datei den bisherigen und den neuen
   Zeitstempel. Der Abstand zwischen den Aufnahmen bleibt unverändert.
4. **Anwenden** schreibt die Korrektur sicher in die Dateien; sie bleiben im
   Ordner und können anschließend auch außerhalb von Bibliothekar verwendet
   oder verschoben werden.
5. **Anwenden und in Tagesbestand übernehmen** führt dieselbe geprüfte
   Korrektur aus und übergibt den Ordner anschließend an den verifizierten
   zentralen Import. Nach erfolgreicher Übernahme werden nur die tatsächlich
   importierten Quelldateien aus dem Mehrfachkorrektur-Ordner entfernt; der
   Ordner selbst bleibt bestehen.

Zwischen Vorschau und Anwendung werden Dateigröße und SHA-256 erneut geprüft.
Hat sich der Bestand verändert, muss die Vorschau neu berechnet werden.

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
