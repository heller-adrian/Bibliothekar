# Bibliothekar

Selbst gehostete Web-App zur sicheren Verarbeitung und Organisation von Kameraaufnahmen auf TrueNAS.

Aktueller Entwicklungsstand: **0.31.0**\n\nAktuelle TrueNAS-/Container-Ausgabe: **0.31.0**  
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

## TrueNAS Custom App 0.31.0

0.31.0 baut auf dem Bibliotheksfundament 0.30.0/0.30.1 auf und aktiviert die
Mehrbibliotheks-Nutzung. Der stabile fachliche Kamerakern bleibt **0.28.7**:
Ereignis-, Archiv-, Reassignment-, XMP-, Export- und Unterereignislogik werden
nicht neu definiert, sondern über einen request-lokalen `LibraryContext` auf
die jeweils ausgewählte Bibliothek geroutet.

Neu in 0.31.0:

- Bibliotheksumschalter; verschiedene Browser-Tabs können unabhängig in
  verschiedenen Bibliotheken arbeiten
- Bibliotheksverwaltung unter **Einstellungen → Konfiguration**:
  prüfen, hinzufügen, Anzeigename ändern, deaktivieren, reaktivieren und
  abmelden
- jede zusätzliche Bibliothek erhält automatisch eine eigene SQLite-Datenbank
  unter `/database/libraries/<interne-id>.sqlite3`
- globale Registry v2 mit Datei-/Familieninventar sowie bibliotheksübergreifenden
  Reservierungen und Besitzständen
- eine freie Familie kann in einer Bibliothek geplant werden und verschwindet
  dann unmittelbar aus dem freien Bestand der anderen Bibliotheken
- freie Altbestände der Main Library bleiben beim Registry-Backfill frei;
  nur geplante Bestände werden `reserved`, angewendete/archivierte Bestände
  werden `owned`
- direkte SD-/USB-Medien können bei fehlendem Host-Geräte-Node über einen eng
  begrenzten temporären Block-Node unter `/dev/bibliothekar` eingebunden
  werden; das Medium wird weiterhin ausschließlich read-only gemountet
- der eingefrorene 0.28.7-CSS-Grundstand bleibt bytegenau erhalten; neue
  0.31-Komponenten liegen in einem getrennten Zusatz-CSS

Basis-Containerpfade:

- `/config` – Anwendungskonfiguration
- `/database` – Main-SQLite, globale Registry und Datenbanken weiterer Bibliotheken
- `/logs` – Protokolle
- `/workspace` – gemeinsamer globaler Bestand, insbesondere `SD-Kartensicherungen`
- `/main-library` – Hauptbibliothek, nur lesend eingebunden
- `/sources/import` – zusätzliche allgemeine Importquelle, nur lesend
- `/sources/nas` – NAS-Quellen, nur lesend
- `/sources/removable` – beschreibbarer Mountpunkt für direkt bereitgestellte
  Wechselmedien; das eigentliche Medium wird read-only eingebunden
- `/tmp` – flüchtiges tmpfs

Für zusätzliche Bibliotheken werden in TrueNAS zwei weitere Host-Path-Mounts
angelegt, zum Beispiel:

- `/libraries/business/workspace` – Arbeitsbereich, read-write
- `/libraries/business/archive` – Archiv, read-only

Die Containerpfade sind frei wählbar und werden anschließend in Bibliothekar
unter **Einstellungen → Konfiguration → Bibliotheken** eingetragen. Bibliothekar
löscht beim Deaktivieren oder Abmelden weder Dateien noch Datenbanken noch
Archive.

Der Arbeitsbereich einer Bibliothek muss auf demselben Dateisystem wie die
gemeinsamen `SD-Kartensicherungen` liegen, wenn Bibliothekar Hardlinks zwischen
beiden Bereichen verwenden soll. Das Archiv darf auf einem anderen Dataset
liegen und wird read-only erwartet.

`compose.example.yaml` enthält die aktuelle Ein-Container-Vorlage. Web-App und
Quellen-Helper laufen weiterhin im selben Container; nur der lokale
Geräte-Helper benötigt die privilegierten Mount-/Geräterechte, während die
Web-App intern als UID/GID `568:568` läuft. Die weitere Discover-Härtung bleibt
für 0.32 vorgesehen.

Die vollständige formularbasierte TrueNAS-Konfiguration ist in
`docs/truenas-guided-custom-app-0.31.0.md` dokumentiert.

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
