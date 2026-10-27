# Bibliothekar 1.0.0-rc.11 – TrueNAS-Testprerelease

RC11 behebt den bestätigten RC10-Erststartfehler: Das technische Trash-Lock wird im qualifizierten privaten F14-Bereich geführt. Eine gemeinsam beschreibbare Workspace-ACL verhindert dadurch nicht mehr allein den Bootstrap. Unsichere private ACLs bleiben ein ausdrücklicher Sperrgrund.

Dokumente:

- [Praktische TrueNAS-Testanleitung: Neuinstallation und blockierter RC10-Erststart](TRUENAS-TEST.md)

- [Neue TrueNAS-Installation](INSTALL-TRUENAS.md)
- [RC10 sicher übernehmen](UPGRADE-RC10.md)
- [Sicherheitsmodell und ACL-Voraussetzungen](SECURITY.md)
- [Formatmigration und Rollbackgrenze](MIGRATION.md)
- [Abnahme und Testgrenzen](TESTING.md)
- [Release Notes](RELEASE-NOTES.md)

Release und unveränderliche Imagereferenz: https://github.com/heller-adrian/Bibliothekar/releases/tag/v1.0.0-rc.11. Automatisierte Linux-Abnahme bestanden; native TrueNAS-Abnahme steht aus. Dies ist keine stabile 1.0.0-Freigabe.
