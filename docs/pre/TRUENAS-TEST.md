# Praktische Abnahme nach Freigabe

Diese Anleitung ist vorbereitet; es gibt noch kein pre-Release oder Image.
Native TrueNAS-Abnahme: **NOT RUN**. Keine Änderungen am NAS durch Codex.

## Isolierter Neuaufbau

In TrueNAS eine getrennte Custom-App anlegen. Eigene leere Appdaten → `/appdata`,
eigener Workspace → `/workspace`; keine RW-Pfade einer anderen Instanz verwenden.
Testarchiv → `/main-library` Read Only, zweite unabhängige Archivkopie z. B. →
`/Businessarchiv` Read Only, optionale Importquelle → `/sources/nas` Read Only.
Container-Tmpfs und bisherige Supervisor-/UID568-Einstellungen aus Compose nutzen.
Die Host-ACL muss UID568 tatsächlich Zugriff geben; kein rekursives chmod/chown.

Die normale NAS-/Folder-Import-Installation benötigt keinen Gerätehelper:
Dockerfile, Supervisor und Compose verwenden dafür `false`. Eine fehlende
optionale Helperverbindung verhindert diesen Grundbetrieb nicht. Für physische
SD-/USB-Medien ist ausdrücklich das vorhandene Removable-Profil erforderlich:
Root-Helper, passende Device-/udev-Rechte und ein eigener Kernel-Mount-Namespace.
Seine URL lautet im selben Container `http://127.0.0.1:8090`. Ein pauschal
unprivilegiertes Profil kann keine Kernel-Mounts erzeugen. Keine fremden
Host-Mounts freigeben oder manuell unmounten. Hardwareabnahme separat durchführen.

## Prüffolge

1. Start → Login → vier Verwaltungsordner → erste Bibliothek; Archiv bleibt RO.
2. Zweite Bibliothek mit eigenem Archiv erstellen, Instanz neu starten.
3. 100, danach etwa 3.900 synthetische Dateien importieren; Zähler nach Ende,
   Navigation weg/zurück und Neustart prüfen. Keine alten 88-Dateien-Snapshots.
4. 14 Undated-Dateien mit `+13:00` aus gemeinsamem Metadatenquelltyp korrigieren,
   einsortieren; Zieltag und Uhrzeit unverändert. Einzel- und Mehrfachauswahl prüfen.
5. Allgemein-Übernahme: sichtbarer Busy-Zustand, Doppelclick, Navigation/Reload,
   echtes Auftragsende. Unterbrechung muss weiter ausdrücklich überprüfbar sein.
6. EN/DE bei 390px und Desktop, Undated-/Event-Doppelklick, Keyboard/Checkbox,
   Archivrename-Anleitung und Zurück-von-Verify prüfen.
7. Nur in Testdaten einen Verwaltungsordner verschieben: Original wiederherstellen,
   erneut prüfen; separater Test des ausdrücklich bestätigten leeren Ersatzes.
   Keine tatsächlichen Archivdateien zur Reparatur automatisiert verändern lassen.
8. Archivchecksummen vor/nach Test vergleichen. Bei unbekannten Daten, falschem
   Hash oder verlorener Archivdatei muss die bestehende Schutzsperre bleiben.

Für das Upgrade der vorhandenen RC14-Instanz siehe [UPGRADE-RC14.md](UPGRADE-RC14.md).
