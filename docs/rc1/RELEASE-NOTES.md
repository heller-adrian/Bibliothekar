# Bibliothekar v1.0.0-rc.1

**Pre-release für frische, isolierte TrueNAS-SCALE-Testinstallationen. Keine stabile
1.0.0-Freigabe und noch keine abgeschlossene TrueNAS-/Browser-/Geräteabnahme.**

Die vollständige Entwicklung bis 0.56.2 einschließlich der danach integrierten
Korrekturen F11/F12/F14/R1/F15–F18/F20–F22/F26 sowie der begrenzten F13-/F24-Korrekturen
und F25/F28 bleibt enthalten. Funktionale Basis:
`ac2e7b8df4b8f7bb3a1582b7cb46d250250cd6ed`, Tree
`cd73ec3cd9a6a068682cffb00183d886807e823b`, Linux **1674 PASS, 0 FAIL/ERROR/SKIP**:
https://github.com/heller-adrian/Bibliothekar/actions/runs/39983880339

Der Releasecommit enthält darauf ausschließlich Versions-/Verpackungs-/Dokumentations-
änderungen. Ein automatischer Bytevergleich prüft alle Anwendungsdateien; nur die
Versionssubstitution 0.56.2 → 1.0.0-rc.1 in `app/__init__.py`/`app/main.py` ist zugelassen.
Die 1674er Suite wurde am Basiscommit bestanden und wird nicht als erneut am RC
ausgeführt dargestellt. Der RC wird zusätzlich als echtes Linux-amd64-Image gebaut,
auf Anwendungsbytes/OCI-Revision geprüft und mit frischer synthetischer Konfiguration
auf Health, Authentifizierung und API-Zugang getestet. Der Smoke-Test enthält keine
privilegierten Mount-/Geräteaktionen; diese bleiben Teil der manuellen Abnahme.

## Installation

Assets `INSTALL-TRUENAS.md`, `MANUAL-ACCEPTANCE.md`, `compose.truenas.yaml`,
`IMAGE-DIGEST.txt`, Quellarchiv und optionales Docker-Imagearchiv verwenden.
`SHA256SUMS` prüfen. Image `ghcr.io/heller-adrian/bibliothekar:1.0.0-rc.1` oder den
veröffentlichten Digest verwenden; `latest` und stabile Versionen bleiben unverändert.
Linux/amd64 ist der gebaute RC-Zieltyp; keine ARM-Freigabe. GHCR kann bei privaten
Paketen Registry-Lesezugang erfordern; das Imagearchiv ist eine zusätzliche Bezugsquelle.

Der Docker-Basisdigest und Python-Constraints sind festgeschrieben; konkrete installierte
Debian-/Python-Pakete liegen bei. Der Build ist aus diesem Quellstand nachvollziehbar
wiederholbar. Keine Behauptung dauerhaft bitidentischer Neubuilds aus veränderlichen
Debian-Repositories: der veröffentlichte OCI-Digest bezeichnet das konkrete geprüfte Image.

## Bewusst verbleibende Grenzen

- F13: Externe Archivänderung zwischen letzter Prüfung/Ereignisabfrage und SSD-Unlink
  sowie mmap-Benachrichtigungsgrenze akzeptiert. Bereits entfernte Arbeitskopien werden
  durch einen späteren Konflikt nicht wiederhergestellt. Während Freigabe nicht extern schreiben.
- F24: Extreme externe Änderungen des letzten Dateieintrags oder Verlagerung eines
  bereits geöffneten Elternordners durch berechtigte Fremdprozesse bleiben akzeptiert.
  Die nachgewiesene Symlink-Neuauflösung nach außerhalb des Papierkorbs ist korrigiert.
- F23/F27/F29 sind dokumentierte begrenzte Eingabe-/Parser-/HTTP-Fehler und nicht
  Gegenstand dieses Releases. Parserressourcengrenzen und reale Browser-/Proxywirkung
  bleiben zusätzliche offene Nachweise; keine Sicherheitsgesamtfreigabe behauptet.
- Reale TrueNAS-/ZFS-/SMB-/ACL-/Container-/Hotplugqualifikation steht aus. Der Helper
  benötigt wirksame UID-Trennung und eindeutige Kernel-Mountidentität; ungeklärte
  Zustände werden abgewiesen. Kein beliebiges Mehrreplikaprofil unterstützt.
- Keine automatische Altbestandsmigration für diesen RC erforderlich oder abgenommen.

Kein Merge nach main und keine Veröffentlichung der stabilen Version v1.0.0.
