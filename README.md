# Bibliothekar

Selbst gehostete Web-App zur sicheren Verarbeitung und Organisation von Kameraaufnahmen auf TrueNAS.

Aktueller Entwicklungsstand: **0.28.1-ui1**\n\nAktuelle TrueNAS-/Container-Ausgabe: **0.30.1**  
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

## TrueNAS Custom App 0.30.1

0.30.1 ist der UI-Regressionsfix auf Basis des Bibliotheksfundaments 0.30.0. 0.30.0 baut auf der formularbasierten Ein-Container-TrueNAS-Custom-App 0.29.1 auf und ergänzt das Bibliotheksfundament. Die Deployment-Version wird weiterhin getrennt vom stabilen fachlichen Kern 0.28.7 geführt.

Die fachliche Ereignis-, Archiv-, Reassignment-, XMP-, Export- und Unterereignislogik bleibt in diesem Schritt unverändert.

Fix in 0.30.1:

- gemeinsames Shell-JavaScript wieder syntaktisch gültig
- gespeichertes Hell-/Dunkel-Theme wird wieder angewendet
- Hamburger-Menü und Dialoge reagieren wieder
- Aufgaben-Zähler lädt wieder aus `/api/tasks`
- CSS/Designstand bleibt identisch zu 0.28.7

Neu in 0.30.0:

- die bestehende `/database/kamera.sqlite3` wird ohne Kopie als **Main Library** adoptiert
- eine kleine globale Registry liegt unter `/database/bibliothekar-global.sqlite3`
- jede Bibliothek besitzt einen stabilen `LibraryContext`
- der Hintergrund-Worker löst den Datenbankpfad über den Bibliothekskontext auf
- gemeinsame Quellen und spätere bibliotheksübergreifende Reservierungen haben eine eigene globale Datenbasis
- bestehende Arbeits- und Archivpfade bleiben unverändert
- für das TrueNAS-Upgrade ist **kein zusätzlicher Storage-Mount** erforderlich

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

Seit 0.29.1 laufen Web-App und Quellen-Helper im selben Container. Der Geräte-Helper bleibt für direkt angeschlossene SD-/USB-Medien privilegiert; die eigentliche Web-App läuft intern als UID/GID 568. Die weitere Discover-Härtung ist für 0.32 vorgesehen.

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
