# v1.0.0-rc.2 – Prerelease zur TrueNAS-Praxisabnahme

Enthält die vollständige RC1-Funktionsbasis und die bisherigen Sicherheitskorrekturen.
Gegenüber RC1:

- Paket A: sicher verifizierte manuelle Archivordnerumbenennungen, konsistente
  EXIF-/XMP-Aufnahmezeiten einschließlich Offsets und verständliche offene Journale.
- B01: kontrollierte Konkurrenz bei Ereignisabfragen statt unkontrollierter Fehler.
- SD-Wiederimport: konsistente Quellenhistorie, inkrementelle Sicherung und
  ausdrücklich bestätigter Wiederimport mit unveränderten Integritätsprüfungen.
- Paket C: verbesserte Ereignisvorschau, getrennte aktuelle Archivzahlen und
  historische Verifikation, DE/EN-Texte, mobile Bedienung und Statusanzeigen.

Geprüfter Produktcommit: 40b97622ba8f89af5db771d2694ae9688cb6c448.
Linux-Backend: **1743 PASS, 0 FAIL/ERROR/SKIP**. Der vollständige Lauf 40108008839
hat Backend und Build bestanden, blieb aber wegen des früheren Smoke-Setups rot.
Der korrigierte echte Container-Onboarding-Smoke bestand separat in 40111803032.
QA-Commit 49bd136704fe273222f8169e8f4037897afd2543 ändert keine Produktdateien.
Der Veröffentlichungsworkflow prüft das tatsächlich veröffentlichte Image per Digest.
Keine erneute Backend-Gesamtsuite. Einzelheiten und Links: QA-NACHWEISE.md.

Installation: INSTALL-TRUENAS.md; bestehende RC1-Testinstallation: UPDATE-RC1-RC2.md.
Das Release-Compose ist auf den überprüften Registry-Manifestdigest festgelegt.
Assets mit SHA256SUMS prüfen. Nur linux/amd64, keine stabile 1.0.0-Freigabe.

Offen: manuelle TrueNAS-/ZFS-/SMB-/NFSv4-ACL-/SD-/Safari-PWA-Abnahme und vollständige
DE/EN-Sprachrunde. Die manuelle geschützte ACL des SD-Mountbereichs ist weiterhin
Voraussetzung; automatische Bereitstellung für eine spätere Kataloginstallation
ist offen. B12 (Papierkorbfortschritt über Seitenwechsel) bleibt zurückgestellt.
Die akzeptierte letzte F13-Race/mmap-Grenze und die akzeptierten extremen externen
F24-Konkurrenzfälle bleiben ausdrücklich bestehen. Keine absolute Datenerhaltungsgarantie
für diese Fälle, keine neue Snapshot-/Rechtearchitektur. Archivdateien während
Arbeitsbereich-Freigaben nicht extern ändern. Keine produktiven Daten für RC-Tests.
