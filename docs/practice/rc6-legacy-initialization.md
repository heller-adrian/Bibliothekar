# RC6: bestätigte Neueinrichtung mit unvollständigen F14-Belegen

## Ursache und Umfang

Der veröffentlichte RC6-Stand verlangt für `setup_again_evidence` ein vollständiges
`storage_initialization`. Historische F14-Zustände können dagegen bereits alle
vier Verwaltungsordner gebunden haben, ohne dieses spätere Feld zu besitzen.
Nach Verlust der Ordner und Kataloge bleibt die Installation deshalb korrekt als
benutzt erkannt, aber der bisherige explizite Neueinrichtungsweg scheitert mit
`unknown_initialization`. Mehrere unabhängige Katalogprüfungen erzeugten außerdem
den gleichen `catalog_unavailable`-Eintrag zweimal. Der Dialog zeigte keinen
konkreten Grund für die fehlende Aktion.

Die NAS-Ausgabe belegt überlebende Bindungen, nicht deren genaue Entstehung.
Versteckte Dateien, offene Deskriptoren oder spätere Veröffentlichung sind anhand
dieser Ausgabe nicht unterscheidbar. Die Prozessreproduktion erhält gezielt die
privaten F14-Belege und entfernt die öffentlichen Daten während eines tatsächlichen
Workers mit offener SQLite-Lesetransaktion. Sie behauptet keine Rekonstruktion
bereits gelöschter Daten.

## Begrenzte Freigabe

Eine fehlende Datenbank allein qualifiziert niemals die neue Einrichtung.
Der bestehende authentifizierte und CSRF-geschützte POST bleibt erforderlich,
einschließlich `SET UP AGAIN` und aktuellem Zustandstoken. Nur wenn alle folgenden
Nachweise vorliegen, darf der historische Sonderfall zusätzlich angeboten werden:

- Unveränderte Workspace-Identität und gültiger privater F14-Verwaltungsbereich.
- Vollständige historische Geräte-/Inode-Bindungen aller vier englischen Wurzeln;
  keine widersprüchlichen Namen oder deutschen Alternativbindungen.
- Keine F14-Bibliotheksregistrierungen, keine Registryhistorie, Katalogdaten,
  privaten Retentionsdaten oder offenen Operationsbelege.
- Nur die erlaubte leere technische Workspace-Struktur; keine Medien oder
  unbekannten Einträge. Keine Symlinks, unsicheren Verwaltungsdateien oder
  verwaisten SQLite-WAL-/Journalbestände.
- Die aktuelle Datenbank liegt im bereits qualifizierten privaten F14-Bereich.
  Vorhandene abweichende Datenbankbindungen bleiben widersprüchlich.
- Konfiguriertes Archiv ist durch No-follow-Verzeichnisdeskriptoren erreichbar
  und leer; historische externe Bindungen sind unverändert und leer.

Die Ausführung wiederholt die Prüfung unter den bestehenden Workspace-/Shared-/
State-Sperren. Aktive Worker verhindern den Reset. Der vollständige alte Zustand
bleibt mit SHA-256-Bezug als `setup-history-*.json` erhalten. Die neue Generation
merkt sich Qualifikation und Datenbankpfad. Danach initialisiert der vorhandene
Startupablauf die vier Wurzeln und erreicht das reguläre Bibliotheks-Onboarding.
Ein Abbruch vor oder nach Veröffentlichung bleibt über diesen Ablauf wiederaufnehmbar.

Eine wirklich frische Installation nutzt weiterhin die automatische Erstinitialisierung.
Ein unbekannter oder belegter Altzustand erhält eine konkrete DE/EN-Sperrbegründung
und Hinweise zum Stoppen aller Schreiber, Sichern von DB/WAL, Konfiguration,
Journalen und Retention sowie Wiederherstellen der ursprünglichen Einbindungen
und zusammengehörigen Sicherungen. Die App entfernt keine Operationsnachweise.

## Nachweise und Plattformgrenze

Neue gezielte Tests decken Legacy-Varianten, erhaltene Daten und Bibliotheksbelege,
Archive, Identitätswechsel, ACL-Ablehnung, Symlinks/Hardlinks, konkurrierende
Änderungen, Auth/CSRF, echte SIGKILLs, drei unabhängige Neustarts und tatsächliches
Onboarding ab. Vorherige rote Reproduktionen und der korrigierte neue Fixturefehler
bleiben in den lokalen QA-Rohbelegen erhalten.

Acht Offline-Chromium-Proben prüfen DE/EN, 390/1280 Pixel und erlaubte/gesperrte
Aktionen. Die vorhandenen Prüfungen für frische Initialisierung sowie F11/F14/F24
werden gezielt mitgeführt. Keine Gesamtsuite und keine Veröffentlichung.

Lokal steht kein Docker zur Verfügung. Echte Prozessabbrüche ersetzen keinen
Containerneustart oder native TrueNAS-/ZFS-/NFSv4-Abnahme. Diese bleibt mit isolierten
Testdaten erforderlich: frische gemountete Installation, leere historische Bindungen,
bestätigte Einrichtung, erste Bibliothek, danach Neustart; außerdem belegte Archive,
fehlende Mounts und beschädigte Bestandsinstallation weiterhin blockiert. Vorher
App/Schreiber stoppen und alle erhaltenen DB/WAL-/Konfigurations-/Retentiondaten
konsistent sichern. Gelöschte Daten kann dieser Patch nicht wiederherstellen.

Lokaler Abschluss: 193 unterschiedliche gezielte Backendfälle mit PASS; letzter
Lauf 39 PASS; acht Browserproben PASS. Rohes Zwischenergebnis 189 PASS/3 Fixture-FAIL
bleibt dokumentiert. Native Container-/TrueNAS-Abnahme weiterhin offen.
