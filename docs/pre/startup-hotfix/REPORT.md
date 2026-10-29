# Startzeitkorrektur nach v1.0.0-pre

Basis: Tag v1.0.0-pre, Commit 9e0fb0a2ff2166d8946c0589c3bc36d052bb03e5;
Anwendungscode unverändert gegenüber 70c0bb57afa168efec83b1b60245b819b36161ff.
Entwicklung: codex/pre-startup-performance. Kein Release, Image-Push oder NAS-Zugriff.

## Reproduktion und Ursache

Startup: `_coordinate_startup` → `startup_database` → sekundäre Bibliothek →
`backfill_library_inventory` → `qualify_origins` → pro projizierter Familie erneut
`_database_family_rows(main)` + `qualify_origins(main)` + `registry_origins(main)`.
Das wiederholt die vollständige Hauptprüfung N-mal und liest die Haupt-Herkunft
2N-mal. Bei einer neu erzeugten Projektion wiederholt auch `projection_origin`
diese Arbeit pro Familie. Es ist keine Endlosschleife: der Datenumfang erzeugt
quadratische Arbeit und eine weitgehend ausgelastete CPU ohne Traceback.
Der Benutzer bestätigte eine weitere registrierte Bibliothek. Ein CPU-Stack
vom betroffenen NAS liegt weiterhin nicht vor; die konkrete Code-Fehlbedingung
ist isoliert reproduziert, ihre Ausführung im realen Prozess nicht direkt gemessen.

Lokales cProfile (macOS, Python 3.13, künstliche SQLite-Kataloge, bestehende zweite
Projektion, keine NAS-Dateien):

| Stand | Familien je Katalog | Wandzeit | CPU-Zeit | Haupt-Herkunftslesevorgänge |
|---|---:|---:|---:|---:|
| unveränderter pre-Code | 100 | 1,846 s | 1,739 s | 200 |
| unveränderter pre-Code | 1.000 | 108,295 s | 105,574 s | 2.000 |
| korrigiert | 4.000 | 0,768 s | 0,762 s | 2 |

Bei 1.000 Familien lagen 108,266 von 108,294 Profilsekunden in qualify_origins;
2.021.013 SQLite-execute-Aufrufe und 1.001 Qualifikationsaufrufe. Nach Korrektur
mit 4.000 Familien: 12.033 execute-Aufrufe, zwei Qualifikationsaufrufe (sekundär
und main). Die Zeiten messen den Backfill, nicht die vollständige NAS-Startzeit.
Messskript/-daten und Profile: /private/tmp/bibliothekar-pre-startup-evidence/.
Ein neuer Regressionstest scheiterte vor Korrektur bereits bei 20 Familien:
40 Hauptlesevorgänge statt höchstens zwei.

## Korrektur und Sicherheitsgrenzen

Eine lokale `_ProjectionAuthority` pro Backfill lädt und qualifiziert die GESAMTE
Haupt-Herkunft einmal und ordnet ihre Familien per Dictionary zu. Bestehende
Projektionen und die erstmalige Projektionsregistrierung verwenden dieselbe
Aufrufansicht. Es gibt keinen Prozesscache; jeder neue Backfill liest frische
Nachweise. Ein beschädigter Hauptbestand blockiert auch dann, wenn die betreffende
Familie nicht lokal projiziert wird. Unveränderte Prüfungen: Namespace, originale
Hashes/Größen/Medientypen, vollständiger kanonischer Fingerprint, Verlustaudits,
Projektionsreferenz und ursprünglich fehlende Mitglieder. Keine Datenbankmigration,
kein Zurücksetzen und keine Umdeutung historischer Nachweise.
F14-Exklusion, Generationen, Nonces und Recoveryreihenfolge bleiben erhalten.

Neue Startphasenprotokolle zeigen Beginn, Ende und Dauer von Storage-Preflight,
Schema-/Registryinitialisierung, Sortier-/Metadatenrecovery, Layoutmigration,
Bestandsprüfung, Claims und Synchronisierung. Fehler werden unverändert weitergereicht.
Insbesondere bleibt die vollständige SHA-256-Prüfung bereits zentral liegender
Dateien in `migrate_main_free_stock_to_central` / `reconcile_migrated_file`
erhalten. Große reale RAW-Bestände können dort zusätzliche, lineare I/O-/Hashzeit
benötigen; die neue Phase `central-stock-migration` macht dies sichtbar.

## Gerätehelfer separat

Dockerfile und Standard-Compose setzen KAMERA_SOURCE_HELPER_ENABLED=false.
Der Supervisor aktiviert ihn nur bei explizitem Umgebungswert 1/true/yes/on.
Das optionale compose.removable.yaml setzt true. Ein laufender Helper deutet
somit beim regulären Supervisor auf einen übernommenen Umgebungs-Override hin;
die konkrete gespeicherte TrueNAS-Appkonfiguration wurde nicht gelesen.
Neue Supervisorlogzeile nennt die Aktivierung bzw. das Standardprofil eindeutig.
Die Funktion und die Rechte des Helpers werden nicht verändert. Für die
Zuordnung auf dem NAS genügt vorerst die Anzeige dieses einzelnen Werts in den
TrueNAS-App-Einstellungen; keine Zugangsdaten oder vollständige Umgebungsdatei senden.

## Abnahmeplan und Fortschritt

Gezielt: vollständige und neue Projektion, 4.000 Familien mit begrenzter Anzahl
vollständiger Scans, frische Wiederholungsprüfung, beschädigte nicht projizierte
Hauptfamilie, bestehende RC12/RC13-Verlustnachweise, Metadatenoffset-/Intent-Recovery,
F14-SIGKILL und konkurrierende Operationen. Lokale Erstläufe zeigten korrigierte
Fixturefehler und fehlendes PYTHONPATH für externe F14-Testprozesse; keine
Sicherheitsprüfung wurde entfernt. Der finale Lauf setzt PYTHONPATH explizit.

Ein einzelner Self-Hosted-Linuxlauf prüft die gezielten Tests und einen echten
Supervisorstart mit zwei Bibliotheken und 4.000 physischen Testdateien, 14
synthetischen korrigierten JPEGs, echter HTTP-Anmeldung, UID 568, Neustart und
RO-Archiven. Zusätzlich läuft die bestehende echte RC14-Korrektur-/Upgradeabnahme
mit 14 +13:00-JPEGs und ursprünglicher offener Metadata-Reservation.
Ergebnisse werden nach Abschluss ergänzt. Kein vollständiger CI-Neulauf.

Nächster Teststand nach erfolgreicher gezielter Linuxabnahme: Kandidat
1.0.0-pre.1 (noch nicht veröffentlicht). Vor NAS-Test konsistente Sicherung von
Appdaten UND Workspace bei gestoppter App erstellen; unveränderte Mounts erhalten.
Weder SQLite/WAL/SHM noch F14-/Swapdateien löschen. Die 14 korrigierten Originale
für den anschließenden Reintegrationstest erhalten. Bei weiterem Stillstand:
letzte neue Startphasenmeldung und Dauer prüfen; erst danach gezielte Stackprobe
anfragen. Native TrueNAS-/NFSv4-Abnahme ist NOT_RUN.

Lokaler finaler gezielter Lauf: **117 passed**, Python 3.13/macOS, 135,22 s.
Die neuen Tests prüfen zusätzlich die explizite Helper-Aktivierung und die
Weitergabe ursprünglicher Fehler durch die Startphasenprotokollierung.
Actionlint (mit vorhandenem Self-Hosted-Labelvertrag) und Python-Kompilierung bestanden.
Die Profilzusammenfassungen liegen neben diesem Bericht. Linux-Containerabnahme folgt
als einzelner gezielter Lauf auf bibliothekar-safe; keine Publikationsrechte.
