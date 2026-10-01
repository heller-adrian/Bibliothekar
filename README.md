# Bibliothekar

Selbst gehostete Web-App zur sicheren Verarbeitung und Organisation von Kameraaufnahmen auf TrueNAS.

Aktuelle TrueNAS-/Container-Ausgabe: **0.29.0**  
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

## TrueNAS Custom App 0.29.0

0.29.0 ist die erste portable TrueNAS-Custom-App-Stufe auf Basis des stabilen 0.28.7-Kerns. Die Deployment-Version wird getrennt vom fachlichen Kern geführt, damit der eingefrorene 0.28.7-Regressionsvertrag unverändert bleibt.

Die fachliche Ereignis-, Archiv-, Reassignment-, XMP-, Export- und Unterereignislogik bleibt in diesem Schritt unverändert.

Containerpfade:

- `/config` – Anwendungskonfiguration
- `/database` – SQLite-Datenbank
- `/logs` – Protokolle
- `/workspace` – gemeinsamer Arbeitsbestand einschließlich `SD-Kartensicherungen` und `Arbeitsbereich`
- `/main-library` – erste bzw. Hauptbibliothek, nur lesend eingebunden
- `/sources/import` – zusätzliche allgemeine Importquelle, nur lesend
- `/sources/nas` – NAS-Quellen, nur lesend
- `/sources/removable` – direkt bereitgestellte Wechselmedien, nur lesend
- `/tmp` – flüchtiges tmpfs

Der tatsächliche Hostpfad auf TrueNAS ist frei wählbar. Workspace und Archiv dürfen auf unterschiedlichen Datasets liegen. Nur die intern vom Workspace verwendeten Arbeits- und Sicherungsbereiche müssen gemeinsam unter demselben `/workspace`-Mount liegen, weil Bibliothekar dort atomare Dateisystemoperationen verwendet.

`compose.example.yaml` ist die Vorlage für die TrueNAS-Custom-App-Installation.

Der aktuelle `source-helper` für direkt angeschlossene SD-Karten/USB-Datenträger bleibt in 0.29.0 als optionaler, privilegierter Begleitdienst erhalten. Er ist ausdrücklich noch nicht die endgültige Discover-/Katalog-Lösung.

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
Mehrere Bibliotheken mit eigener SQLite-Datenbank und eigener Archivzuordnung.

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
