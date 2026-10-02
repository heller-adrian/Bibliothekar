# Bibliothekar

Selbst gehostete Web-App zur sicheren Verarbeitung und Organisation von Kameraaufnahmen auf TrueNAS.

Aktueller Entwicklungsstand: **0.28.1-ui1**

Aktuelle TrueNAS-/Container-Ausgabe: **0.31.0**  
Stabiler fachlicher Kamerakern: **0.28.7**

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

## TrueNAS Custom App 0.32.8

0.32.8 vereinfacht die Speicherarchitektur der Mehrbibliotheks-Nutzung, ohne
bestehende Bibliotheken automatisch zu verschieben. Der fachliche Kamerakern
bleibt kompatibel; neue Speicherpfade werden zentral aufgelöst.

### Gemeinsamer Kamera-Arbeitsbereich

TrueNAS bindet standardmäßig genau **einen** gemeinsamen read-write Host Path
als `/workspace` ein. Das kann ein eigenes Dataset oder auch ein normaler Ordner
innerhalb eines vorhandenen Datasets sein.

Bibliothekar verwaltet darunter standardmäßig:

- `/workspace/SD-Kartensicherungen` – globaler Sicherungs- und Rückkehrbestand
- `/workspace/Arbeitsbereiche` – Stamm für Bibliotheks-Arbeitsbereiche
- `/workspace/Metadatenkorrektur` – vorbereiteter allgemeiner Arbeitsbereich
- `/workspace/Arbeitsbereiche/main` – Standard-Arbeitsbereich der Main Library

Die Namen der drei von Bibliothekar verwalteten Stammordner können unter
**Einstellungen → Pfade** geändert werden. Dabei werden ausschließlich
App-eigene Ordner innerhalb des bereits gemounteten `/workspace` verwaltet.
TrueNAS-Datasets oder Host-Path-Mounts werden niemals von Bibliothekar erzeugt
oder umgehängt.

Bestehende Installationen mit einem echten `/workspace/Arbeitsbereich` werden
nicht automatisch verschoben. Auf frischen Installationen existiert dieser Name
nur als Kompatibilitätsalias auf `/workspace/Arbeitsbereiche/main`.

### Bibliotheken

Jede zusätzliche Bibliothek erhält weiterhin eine eigene SQLite-Datenbank unter
`/database/libraries/<interne-id>.sqlite3`.

Standardmäßig erzeugt Bibliothekar ihren Arbeitsbereich selbst unter:

`/workspace/Arbeitsbereiche/<interne-id>`

Damit ist für einen normalen zusätzlichen Bibliotheks-Arbeitsbereich kein
weiterer TrueNAS Host Path nötig.

Soll eine Bibliothek bewusst auf einem anderen Dataset oder an einem anderen
Speicherort arbeiten, wird dieser Ort zuerst in TrueNAS als zusätzlicher
read-write Host Path in den Container eingebunden. Anschließend kann der
Containerpfad unter **Einstellungen → Bibliotheken** als Arbeitsbereich
eingetragen werden. Pfadänderungen verschieben keine Dateien automatisch.

### Archive

Archive werden absichtlich **nicht** unter einem gemeinsamen Archiv-Mount
zentralisiert. Jede Bibliothek erhält in TrueNAS ihren eigenen read-only Host
Path. Dadurch kann jedes Archiv unabhängig auf einem anderen Dataset, Pool oder
Ordner liegen.

Beispiel:

- Host-Archiv A → `/main-library` (RO)
- Host-Archiv B → `/libraries/test/archive` (RO)

Den jeweiligen Containerpfad speichert Bibliothekar pro Bibliothek. Die
Bibliotheksverwaltung erlaubt Anzeigename, Arbeitsbereich und Archivpfad später
erneut zu prüfen und anzupassen. Das Archiv bleibt für Bibliothekar read-only;
physische Archivänderungen bleiben kontrollierte Nutzeraktionen.

### Hardlinks

Bibliothekar entscheidet nicht anhand des Pfadnamens, ob ein Hardlink möglich
sein müsste. Entscheidend ist das tatsächliche Dateisystem. Liegen globaler
Bestand und Bibliotheks-Arbeitsbereich auf demselben Dateisystem, wird ein
Hardlink verwendet. Meldet das Betriebssystem `EXDEV`, zeigt Bibliothekar
ausdrücklich die Wahl **Kopieren** oder **Verschieben**.

Ein gemeinsamer `/workspace`-Mount erleichtert Hardlinks, garantiert sie aber
nicht, wenn darunter wiederum unterschiedliche ZFS-Datasets eingehängt sind.

### Basis-Containerpfade

- `/config` – Anwendungskonfiguration
- `/database` – Main-SQLite, globale Registry und Bibliotheksdatenbanken
- `/logs` – Protokolle
- `/workspace` – gemeinsamer Kamera-Arbeitsbereich, read-write
- `/main-library` – Main-Archiv, read-only
- weitere Bibliotheksarchive – jeweils eigener read-only Host Path
- optionale externe Bibliotheks-Arbeitsbereiche – eigener read-write Host Path
- `/sources/import` – zusätzliche allgemeine Importquelle, read-only
- `/sources/nas` – NAS-Quellen, read-only
- `/sources/removable` – Mountpunkt für direkt bereitgestellte Wechselmedien
- `/tmp` – flüchtiges tmpfs

`compose.example.yaml` enthält die Ein-Container-Vorlage. Die detaillierte
Speicherarchitektur für 0.32.8 ist in `docs/truenas-storage-0.32.8.md`
beschrieben.

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
TrueNAS-Discover-Härtung und Katalogstruktur.

### 1.0.0
Stabiler Kamera-Kern ohne Immich, Problembilder und KI-Vorsortierung.

### 2.0
Problembilder / Metadaten-Reparatur für WhatsApp, Signal und ähnliche Quellen.

### 3.0
Manuell startbare KI-Vorsortierung mit Open-Weight-Modell auf dem GX10.

### später
Immich-Anbindung.

## Status

Das Projekt befindet sich aktiv in Entwicklung und ist noch nicht für unbegleitete Produktivinstallationen freigegeben.

## Lizenz

Bibliothekar ist freie Open-Source-Software unter der GNU Affero General Public License v3.0.

Siehe [LICENSE](LICENSE).
