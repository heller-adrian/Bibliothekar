# Bibliothekar v1.0.0-pre.1 — Prerelease

Behebt den reproduzierten quadratischen Herkunftsvergleich beim Start mit einer
weiteren Bibliothek. Die vollständige Haupt-Herkunft wird pro Backfill einmal
qualifiziert; jede neue Ausführung prüft die Nachweise frisch. Herkunfts-, Hash-,
Verlust-, F14- und Archivschutz bleiben erhalten. Keine Datenbankmigration.

Der abgenommene Anwendungscode ist 79ab9c1f3c9906723e328873ad790074e3f7b60c.
Buildgrundlage 282aeba2dd8464f30c8484034759cbb0fd8e0823 unterscheidet sich im
Anwendungscode ausschließlich durch die Versionskennung 1.0.0-pre.1.

Nachgewiesen: 118 gezielte Linux-Regressionen; echter Supervisorstart mit zwei
Bibliotheken und 4.000 Testdateien (5,37 s; Neustart 6,29 s im ursprünglichen Gate);
originale RC14-Wiederaufnahme mit 14 korrigierten JPEGs und +13:00, erhaltener
Reservation bis zum bewussten Retry und unveränderten Archivbytes. Der Publisher
prüft diese akzeptierten Belege kryptografisch und testet den versionierten
Container erneut vor Veröffentlichung. Neue Startphasenprotokolle zeigen die
jeweilige Arbeit und ihre Dauer. Der optionale Gerätehelfer bleibt konfigurierbar.

Upgrade-Anleitung: https://github.com/heller-adrian/Bibliothekar/releases/download/v1.0.0-pre.1/UPGRADE-TRUENAS.md
Testbericht: https://github.com/heller-adrian/Bibliothekar/releases/download/v1.0.0-pre.1/TEST-REPORT.md

Keine stabile 1.0.0 und keine TrueNAS-Discover-Veröffentlichung.
NOT_RUN: native TrueNAS-/NFSv4-ACL-Abnahme, physische SD-/USB-Hardwaretests,
DNG-1.7-Originaldateitest. DEFERRED: eigenständiges Verlustabschlussmodell.
Die Dateizahl ist repräsentativ; kleine synthetische Dateien belegen keinen
Durchsatz für große RAW-Bestände. Vollständige Medienhashprüfungen bleiben aktiv.
Das bestehende v1.0.0-pre, seine Anlagen und latest werden nicht verändert.
