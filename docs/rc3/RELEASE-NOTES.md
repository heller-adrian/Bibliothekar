# v1.0.0-rc.3 – Prerelease zur manuellen TrueNAS-Abnahme

Enthält die gesamte abgenommene RC2-Funktionsbasis und Sicherheitskorrekturen.
R01–R06 gegenüber RC2:

- Bereits vollständig gesicherte SD-Karten erzeugen bei gewöhnlichem erneutem Sichern keinen leeren Importauftrag. Ausdrückliche SHA-256-Integritätsprüfung und Wiederherstellung nachweislich fehlender Kopien bleiben zugänglich; die schnelle Historien-/Präsenzanzeige ist kein neuer Inhaltsnachweis.
- Deutsche/englische Import-, Fortschritts-, Altauftrags-, Auswurf- und Dialogtexte korrigiert. Reimportbutton „Erneut sichern / Back up again“. Namen, Pfade und Rohprotokolle bleiben erhalten.
- Mobile Media-Vorschau verwendet denselben geplanten/tatsächlichen Strukturbaum im schließbaren Dialog; kompaktere Tageskarten und Archivhistorie mit ausklappbarer historischer Verifikation.
- Katalogname und tatsächlich beobachteter Archivordner werden deutlicher unterschieden; keine automatische Namens-/Datenbereinigung.

Produktcommit d7610205f2c7bc8708e36a130bab896d3ef568d1; Tree 4e722f8bd78365ad437bb918589ffaf6fb3ab7b4.
QA: https://github.com/heller-adrian/Bibliothekar/actions/runs/40146864570
**1751 PASS, 0 FAIL/ERROR/SKIP**, linux/amd64-Build und frischer Onboarding-Smoke PASS;
172 App-Dateien per SHA-256, UID/GID568:568 und SQLite geprüft. Veröffentlichung verwendet ausschließlich diesen Produktcommit und prüft das veröffentlichte Image per Manifestdigest erneut; keine neue Backend-Gesamtsuite.

Bestehende RC2-App: UPDATE-RC2-RC3.md. Frische isolierte Tests: INSTALL-TRUENAS.md.
Release-Compose ist digestgebunden; Assets mit SHA256SUMS prüfen. Kein Stable und kein latest-Update.

Offen bleiben reale TrueNAS-/ZFS-/SMB-/ACL-/SD-/Safari-/Android-Praxisnachweise und die mobile Papierkorbregression. Die geschützte manuelle NFSv4-ACL des SD-Mountbereichs bleibt erforderlich; automatische Katalogbereitstellung ist offen. B12 bleibt zurückgestellt. Akzeptierte letzte F13-Race/mmap-Grenze und extreme externe F24-Konkurrenzfälle unverändert, keine absolute Erhaltungsgarantie. Archivdateien während Arbeitsbereich-Freigabe nicht extern ändern. Nur synthetische Testdaten verwenden.
