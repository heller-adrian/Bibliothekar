# Bibliothekar v1.0.0-rc.6 — Pre-release

RC6 dient der weiteren manuellen TrueNAS-SCALE-Erprobung. Keine stabile 1.0.0-Freigabe.

## Änderungen gegenüber RC5

- Echte leere Erstinstallationen erstellen und binden ihre vier englischen
  Verwaltungsordner automatisch. Ein ausdrücklich bestätigter, streng qualifizierter
  Wiederanfang ist für vollständig leere historische Zustände möglich. Beschädigte
  Bestandsinstallationen und ungeklärte Dataset-/Identitätswechsel bleiben gesperrt.
- Ordner-/Laufwerksquellen werden vollständig in der vorhandenen persistenten Queue
  geprüft. Bekannte Medien erzeugen keinen regulären Null-Dateien-Import. Zwei
  überlappende gleiche Quellen werden am Übergabepunkt gegen laufende Publikation
  und geänderte Katalogzustände abgesichert; erforderliche Prüfung wird frisch wiederholt.
- Einheitlicher Prozenthintergrund eingeklappter Hintergrundaufträge auf Desktop/Mobil.
- RC5-Praxis- und Sicherheitskorrekturen einschließlich privater Papierkorb-Retention,
  SD-Queue, Archivumbenennung und UID/GID-Trennung bleiben erhalten.

## Transparente technische Abnahme

- [Originalgesamtlauf40326767389](https://github.com/heller-adrian/Bibliothekar/actions/runs/40326767389): **1.993 PASS /17 FAIL /0 ERROR/SKIP**.
- Die17 Fehler lagen in der fehlenden Lifecycle-Fixture des neuen Praxis-Testmoduls.
  Bestehende Fixture wiederverwendet; keine Assertions oder Produktguards abgeschwächt.
- [Gezielte Linux-Nachprüfung40335487988](https://github.com/heller-adrian/Bibliothekar/actions/runs/40335487988): **56 PASS**, einschließlich sämtlicher48 Fälle des betroffenen Moduls, P1-Konkurrenz-, Worker- und unverändertem /dev/shm-Test. Dieser Workflow blieb durch einen späteren Container-Testadapterfehler insgesamt rot.
- **2.010 unterschiedliche Backendfälle insgesamt mit Linux-PASS belegt.**
- [Containerabschluss40337033762](https://github.com/heller-adrian/Bibliothekar/actions/runs/40337033762): **SUCCESS**, linux/amd64-Build,176App-Dateihashes, frisches Onboarding, Authentifizierung, sechs Seiten samt JS/CSS, UID/GID568:568, SQLite/Fremdschlüssel, private Recovery, bestätigter Reset, beschädigte Bestandsinstallation und Duplikatordner.
- **Kein einzelner vollständig grüner Gesamtlauf.** Der Auftraggeber hat diese kombinierte Abnahme ausdrücklich zur Veröffentlichung genehmigt. Rote Originale bleiben unverändert als Assets nachweisbar. Die Veröffentlichung startet keine neue Backend-Suite.

Anwendungs- und Verpackungsbytes des Originalprüfstands und Abschlusscommits sind
identisch. Nachträglich wurden ausschließlich fünf dokumentierte Test-/QA-Pfade geändert.
Das veröffentlichte Image wird per Registry-Digest erneut abgerufen und auf Version,
Commit, Tree, alle176Apphashes sowie isoliertes Onboarding und Recovery geprüft.

## Installation und verbleibende Grenzen

`IMAGE-DIGEST.txt`, digestgebundene `compose.truenas.yaml`, `INSTALL-TRUENAS.md`,
`UPDATE-RC5-RC6.md`, `MANUAL-ACCEPTANCE.md`, `QA-NACHWEISE.md` und `SHA256SUMS` sind
Bestandteile dieses Releases. Vor einem bestehenden Update App und alle Schreiber
stoppen und konsistente DB-/WAL-/Registry-/Config-/Workspace-/Retentionssicherungen
prüfen: Startup kann fehlgeschlagene Restores automatisch finalisieren.

**Native TrueNAS-/ZFS-/NFSv4-/SMB-/SD-Geräteabnahme bleibt offen.** Private Appdaten
benötigen die dokumentierte ACL-Vertrauensgrenze gegenüber fremden Schreibern;
Administratoren und andere Prozesse mit derselben UID sind nicht isoliert.
Der SD-Helper benötigt weiterhin den manuell korrekt bereitgestellten geschützten
NFSv4-Mountnamensraum samt Eltern; Web568:568 liest/durchquert, schreibt dort nicht.
Keine pauschale Rechteänderung oder Helperumgehung. Automatische Katalog-Provisionierung
bleibt ein separates Deployment-Thema.

Akzeptierte F13-Grenze: externe Archivänderung zwischen letzter Prüfung und SSD-Löschung
(einschließlich mmap) kann weiterhin Verlust verursachen; keine absolute Erhaltungsgarantie.
Akzeptierte F24-Grenze: extreme gleichzeitige berechtigte Fremdeingriffe bleiben ein
Restrisiko. B12 (dauerhafte Papierkorb-Fortschrittsanzeige) bleibt zurückgestellt.
