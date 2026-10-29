# Bibliothekar v1.0.0-pre – Prerelease

Geprüfter Anwendungscode: `70c0bb57afa168efec83b1b60245b819b36161ff`.
Freigegebene Dokumentation: `30e492574b02579496fbaece8c3acfe657a70009`.
[Erfolgreiche Linux-Abnahme40840603811](https://github.com/heller-adrian/Bibliothekar/actions/runs/40840603811).

Dies ist ein Prerelease für die anschließende praktische Abnahme. Eine stabile
1.0.0-Freigabe und eine TrueNAS-Discover-Veröffentlichung stehen aus.

## Korrekturen gegenüber RC14

- Zeitzonenoffset bleibt bei Metadatenkorrektur, Katalog, Journal und Einsortierung
  erhalten. Der geprüfte+13:00-Fall verschiebt weder Aufnahmeuhrzeit noch Zieltag.
- Eine passende, nach dem bekannten RC14-Verifikationsfehler erhaltene
  F14-Reservation kann nach strenger Prüfung über den normalen Benutzer-Retry
  fortgesetzt werden. Identitäten, Generationen und Originalnachweise bleiben bis
  dahin erhalten. Kein Clean Slate und keine manuelle SQL-Korrektur erforderlich.
- Große Bestandssnapshots ersetzen ältere kleine Snapshots; überholte Antworten
  überschreiben keine neueren Anzeigen. Reviewfälle und korrigierte, noch nicht
  einsortierte Dateien werden getrennt gezählt.
- Sichtbarer General-Import-Auftrag mit Wiederaufnahme der Statusanzeige nach
  Seitenwechsel; gleiche ausgewählte Bytes erzeugen keinen zweiten Auftrag.
- Geprüfte reine Archivordnerumbenennungen erhalten eine kompakte manuelle
  Anleitung. Rücknavigation von Verify zur frisch geprüften manuellen Arbeit,
  EN/DE-Meldungen und Desktop-Doppelklicks wurden ergänzt.
- Helper-Standardwerte stimmen mit dem normalen NAS-/Folder-Betrieb überein.
  Physische Wechselmedien benötigen weiterhin das gesonderte Removable-Profil.

## Abnahme und Grenzen

177 gezielte Tests,2269 vollständige Backendtests ohne Fehler oder SKIPs,
195 Chromium-Fälle und49 reale Supervisor-/Containerfälle bestanden. Dazu gehören
RC14→pre mit14 Medien, erste/zweite Bibliothek, Neustarts, unveränderte Archive,
RC10–RC14-Migrations-, Speicherreparatur-, Herkunfts- und Crashregressionen.
Alle11 ursprünglichen CI-Artefakte sind per SHA-256 an den Prüflauf gebunden.

**NOT_RUN:** native TrueNAS-/OpenZFS-/NFSv4-ACL-Abnahme und physische SD-/USB-
Hardware. **DNG1.7:** konkrete Originaldatei fehlt; keine Formatfreigabe und keine
Unterdrückung von ExifTool-Warnungen. Ein eigenständiger erfolgreicher Abschluss
bei verlorenen Archivdateien bleibt DEFERRED; bestehende Schutzsperren bleiben aktiv.
Linux-Abnahme ersetzt keine native TrueNAS-Abnahme.

Vor dem Upgrade [UPGRADE-RC14.md](UPGRADE-RC14.md) und vor dem praktischen Test
[TRUENAS-TEST.md](TRUENAS-TEST.md) lesen. Appdaten und Workspace konsistent sichern;
Archive ausschließlich Read Only. Keine SQLite-, WAL-/SHM- oder F14-Dateien löschen.

Das Veröffentlichungspaket ergänzt nach erfolgreicher Ausführung den tatsächlich
gezogenen Image-Digest, OCI-/Registry-Nachweise, digestgebundenes Compose,
exakten getesteten Quellcode und SHA256SUMS. Der Stable-/latest-Kanal wird durch
diesen eigenständigen Prerelease-Publisher nicht aktualisiert.
