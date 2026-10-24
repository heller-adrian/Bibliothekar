# v1.0.0-rc.2 – Veröffentlichung noch nicht freigegeben

Gegenüber RC1: verifizierte manuelle Archivumbenennungen und konsistente Metadatenzeiten (Paket A), kontrollierte Konkurrenz bei Ereignisabfragen (B01), konsistente SD-Quellenhistorie und ausdrücklich bestätigter sicherer Wiederimport, UI-/Sprach-/Vorschau-/Archivstatuskorrekturen (Paket C).

Der Kandidat wird einmal vollständig unter Linux geprüft und danach aus demselben Commit gebaut. Build und Smoke verändern keine TrueNAS-Daten; das Testimage wird nicht in eine Registry gepusht. Abnahmeresultate und Image-ID werden im QA-Bericht festgehalten. Keine bitidentische Neubaugarantie für später veränderte Debian-Paketquellen: Dockerbasis und Pythonconstraints sind festgelegt; das tatsächlich installierte Paketmanifest wird gesichert.

Offen: manuelle TrueNAS-/ZFS-/SMB-/NFSv4-ACL-/SD-/Safari-PWA-Abnahme, vollständige DE-/EN-Sprachrunde und spätere Katalogbereitstellung des geschützten SD-Mountbereichs. B12-Fortschritt über Seitenwechsel bleibt zurückgestellt. Akzeptierte F13-/F24-Restrisiken gelten unverändert. Keine stabile 1.0.0-Freigabe.
