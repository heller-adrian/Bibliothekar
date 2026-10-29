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

Erster gezielter Linuxlauf 40903484665: 116 PASS, ein vorhandener Testcontroller
las nach exists() eine noch leere checkpoint.json (JSONDecodeError im Test, nicht
in F14). Die Worker schreiben diesen Testmarker mit create/write/flush/fsync.
Der Controller wartet jetzt innerhalb derselben 15-s-Frist auf vollständiges JSON;
alle anschließenden PID-, SIGKILL-, Reservations- und Identitätsassertionen bleiben
bestehen. Ein deterministischer Test erzwingt die leere Zwischenphase. Unveränderter
Anwendungscode gegenüber 44c31430; lokale gezielte Wiederholung des Controllers und
der neuen Regressionen: **35 PASS**. Der nötige Linux-Nachlauf wird dokumentiert.

Linux-Nachlauf 40904815727: **118 PASS** im gezielten Python-Gate. Beide Starts der
4.000-Dateien-Containerfixture und sämtliche Vorher/Nachher-Bestandsvergleiche
liefen durch. Die abschließende Testlogassertion berücksichtigte nur stdout;
Uvicorn schreibt `Application startup complete` jedoch nach stderr. Nur die
Testauswertung wurde auf beide Streams korrigiert. Der Anwendungscode bleibt
unverändert. Der folgende reine Container-Nachlauf verifiziert und verwendet den
118-PASS-Nachweis anhand exakter App-/Test-/Abhängigkeitsgleichheit, erfolgreichem
Jobschritt und ursprünglichem Artefakt-ZIP-Digest
sha256:32ab7889908039cee4ff4600c721f419a0aadac663aba0fed52b0f71b1f800b0.
Keine unnötige Wiederholung dieser bereits bestandenen Backendtests.

## Abschließendes Ergebnis

**SUCCESS:** [40906773810](https://github.com/heller-adrian/Bibliothekar/actions/runs/40906773810),
getesteter Commit **79ab9c1f3c9906723e328873ad790074e3f7b60c**. Anwendungscode identisch
mit Implementierungscommit 44c314308666cd68cbfe3583d64acbe15682dd77. Die 118 gezielten
Linux-Tests aus 40904815727 wurden per identischem App-/Test-/Abhängigkeitsstand,
erfolgreichem Jobschritt, ZIP-Digest und vollständigem JUnit-XML erneut verifiziert.
Kein kompletter Backend-/Browser-Matrixlauf.

Realer Docker-/Supervisor-Test: Original-RC14-Image
`ghcr.io/heller-adrian/bibliothekar@sha256:86991ef46f1f29a990b63ea3983b1193adfe378247d1202e41fdfd7e21d44b9b`
erzeugte die technische Installation und zwei Bibliotheken. Nach gestopptem
Container wurden ausschließlich künstliche Kataloge und Dateien ergänzt.
4.000 Dateien/Familien, UID 568, eigene RW-Appdaten/Workspace, echte RO-Archive,
network=none mit tatsächlicher HTTP-Anmeldung im Container:

- Erster Hotfixstart inklusive Anmeldung/Speicherprüfung: **5,370 s**.
- Neustart inklusive Anmeldung/Speicherprüfung: **6,291 s**.
- Beide Male ready; vollständige Herkunfts- und Dateikataloge vor/nach identisch.
- 14 künstliche korrigierte +13:00-JPEGs in unveränderten Bytes und Inodes erhalten.
- Archivbytes unverändert, authentifiziertes Storage-Recheck erfolgreich.
- Uvicorn meldet startup complete, tatsächliche Web-UID 568, Helper deaktiviert.

Zusätzliche bestehende originale RC14-Metadatenabnahme: **PASS**. RC14 importiert
14 echte synthetische JPEGs über HTTP, korrigiert +13:00 und reproduziert selbst
den Offset-/Reintegrationsfehler. Nach Hotfix-Upgrade bleiben dieselbe offene
F14-Metadatareservation und sämtliche Herkunfts-/Archivnachweise erhalten. Erst
der explizite Benutzerretry integriert die 14 Dateien mit vollständigem +13:00;
Neustart und zweite Bibliothek bestehen ebenfalls.

QA-Artefakt **pre-startup-hotfix-evidence**, ID 12911557324:
`sha256:3500037d20ac14ad971eee4bdb35fb743b333a98e12488c49673cb307e426daf`.
Das ZIP wurde separat heruntergeladen und gegen diesen Digest geprüft.
Kurzbelege stehen in startup-evidence.json, accepted-targeted-evidence.json und
rc14-metadata-summary.json neben diesem Bericht. Der vollständige Originalbeleg
liegt im Actions-Artefakt. Lokale Kopie unter dem oben dokumentierten tmp-Verzeichnis.

Die Nachläufe korrigierten ausschließlich QA-Probleme: partielle Testmarker,
stdout/stderr-Auswertung, Export des QA-Verzeichnisses und Dockers erforderliche
PID-Spalte bei docker top. Kein Produkt-Sicherheitscheck wurde entfernt;
Anwendungscode blieb bei allen Nachläufen unverändert.

Grenzen: kleine künstliche Mediendateien; kein Durchsatznachweis für viele GiB/TiB
RAW-Daten und kein NAS-Aufrufstapel. Der quadratische CPU-Fehler ist nachgewiesen;
seine konkrete Ausführung auf dem NAS bleibt ohne Stack/Phasenlog indirekt belegt.
Für die Korrektur sind derzeit keine weiteren NAS-Daten nötig. Für die separate
Helperfrage genügt KAMERA_SOURCE_HELPER_ENABLED aus den TrueNAS-App-Einstellungen.
Bei weiterem Stillstand nach Hotfixtest zuerst die letzte neue Startphase samt
Dauer melden; dann gegebenenfalls eine gezielte Stackprobe. Keine Shellpflicht
für die reguläre Diagnose dieses neuen Logs.

v1.0.0-pre bleibt unverändert (Tag erneut geprüft: 9e0fb0a2ff2166d8946c0589c3bc36d052bb03e5).
Keine Veröffentlichung des Hotfixes; nur lokale QA-Images ohne Push. Keine Änderungen
an TrueNAS, produktiven Daten, ACLs oder Datenbanken. Nächster empfohlener Kandidat:
**1.0.0-pre.1**, getrennt zu versionieren und erst nach Freigabe zu veröffentlichen.
