# Ergebnis der Veröffentlichungsvorbereitung – 29. Oktober 2026

## Ergebnis

Der eigenständige manuelle Publisher ist vorbereitet und lokal geprüft.
Zur sofortigen Ausführung fehlt noch die GitHub-Registrierung auf dem
Standardzweig. Runner und Dockerzugriff sind inzwischen durch den kurzen Smoke-Test bestätigt.
Lesender GitHub-/Paket-Zugriff funktioniert; Veröffentlichungsschreibaktionen
bleiben bis zur ausdrücklichen Freigabe ausstehend. Es wurde kein Veröffentlichungsjob gestartet. Ein zunächst von GitHub erzeugter
Validierungsdatensatz ohne Jobs meldete einen unzulässigen runner.temp-Kontext
im Job-env. Der Pfad wird jetzt erst im initialen Runner-Schritt gesetzt.

Die technische Grundlage ist unverändert:

- Anwendung70c0bb57afa168efec83b1b60245b819b36161ff.
- Dokumentation30e492574b02579496fbaece8c3acfe657a70009.
- Aktueller freigegebener Branchcodex/1.0.0-pre zeigte weiterhin genau30e49257.
- QA40840603811 ist erfolgreich; sämtliche elf Jobs success.
- Elf Originalartefakte: Live-Metadaten erneut geprüft, ZIP-Bytes erneut gegen
  die im genehmigten Commit gespeicherten Digests geprüft und sicher extrahiert.
- Erneut nachgewiesen:2269 eindeutige Backendknoten ohne Lücke/Duplikat,
  177 gezielte Tests,195 Browserfälle und49 Containerfälle. XML enthält keine
  Fehler, Exceptions oder SKIPs. Alle Containerberichte nennen den Prüfcommit.
- app-, tests-, qa-, Dockerfile-, Requirements- und Compose-Stände zwischen
  Anwendungscode und Dokumentationscommit sind identisch. Seitdem enthält der
  Vorbereitungszweig ausschließlich Publisher-/Releaseunterlagen.
- Repository weiterhin privat. Der Runner-Smoke-Job bestätigt direkten lesenden
  Zugriff mit GITHUB_TOKEN. Vorhandenes GHCR-Paket: public, unverändert.
  Keine Zugriffsrechte wurden verändert.

## Lokale Prüfungen

13 Release-only-Unittests mit Positiv- und Negativvarianten bestanden:
fehlende Freigabe, falscher Branch/Event/Runner, veränderte oder fehlende
Artefakte, ZIP-Pfadflucht/Symlinks, Weitergabe von Authentifizierung bei Redirects,
zusätzliche/fehlende/veränderte Image-Appdateien und Dateimodi, falsche OCI-
Revision/Architektur, belegte Tags/Releases, Registry-Fehler, falsche Digest-/
Manifest-/Config-Nachweise und geänderte Sichtbarkeit.

Beide YAML-Dateien geparst und zusätzlich mit dem per offizieller Prüfsumme
verifizierten Actionlint1.7.12 geprüft. Die vorgeschriebene eigene Runnerbezeichnung
ist explizit als Custom-Label konfiguriert; Workflow-Lintregeln werden nicht
ignoriert. Die externen Zusatzprogramme ShellCheck/Pyflakes sind hier nicht
verfügbar; Shellsyntax und Python wurden zusätzlich separat geprüft.
Sämtliche Shellblöcke mit bash -n geprüft; nur
workflow_dispatch und ausschließlich die vorgeschriebenen Self-Hosted-Labels.
Checkout und Artefaktupload sind auf gelesene offizielle Commit-SHAs gepinnt.
Keine vollständige CI-Abnahme wiederholt. Kein lokaler Docker-/GHCR-Test behauptet:
Docker und gh sind auf dieser macOS-Arbeitsumgebung nicht verfügbar.

## Vorbereitete Anlagen

Release Notes, freigegebener Testbericht, TrueNAS-/Upgrade-Anleitung, Restrisiken,
CI-/Quellidentität, Composevarianten, Dockerfile und Requirements, überprüfter
Original-QA-Nachweis und deterministisches git-archive des Prüfcodes liegen lokal
unter /private/tmp/bibliothekar-pre-release-preparation/release-assets.
Alle vorhandenen Anlagen sind in SHA256SUMS erfasst und erfolgreich geprüft.
Das zukünftige finale Image-Digest kann vor dem erlaubten Build/Push/Pull noch
nicht feststehen. Der Workflow setzt es erst nach dessen tatsächlicher Prüfung
in Compose, Releaseunterlagen und die abschließenden Prüfsummen ein.

## Sicherheitsgrenzen und nächste Schritte

Die Details stehen in ../PUBLISHING.md. Nach ausdrücklicher Freigabe:
Registrierung unter bestehenden Branchregeln ohne Stable-Push klären; Runner
und Berechtigungen bestätigen; bewusster Dispatch auf dem Vorbereitungszweig.
Der Workflow prüft erneut alle Belege und belegten Namen, baut ausschließlich
geprüften Code, vergleicht alle eingebetteten Appdateien, reserviert einen neuen
Tag atomar, pusht ausschließlich1.0.0-pre, zieht per Digest und prüft Manifest,
Image-ID, OCI-Revision und Paket-/Repositorysichtbarkeit. Erst danach entsteht
mit latest=false der GitHub-Prerelease samt erneut heruntergeladenen Anlagen.

Ein unklarer Teilzustand nach Tag-/Imageanlage bleibt zur manuellen Untersuchung
stehen. Es gibt keine Überschreib-, Lösch- oder automatische Reparaturfunktion.
Unabhängige externe Registry-Schreiber müssen diesen Versionsnamen freihalten;
GHCR bietet für sie keine transaktionale Tagreservierung durch diesen Workflow.

Native TrueNAS-/NFSv4-, SD-/USB-Hardware- und DNG1.7-Abnahme bleiben NOT_RUN.
Kein Tag, kein Release, kein GHCR-Push, keine NAS-Änderung in dieser Vorbereitung.

## Fortschritt nach Runner-Ergänzung

[Smoke40886496425](https://github.com/heller-adrian/Bibliothekar/actions/runs/40886496425):
SUCCESS, ein Job/6 Sekunden, bibliothekar-truenas, Labels exakt wie vorgeschrieben.
Alle angeforderten Tools, lokaler Dockerzugriff, Container ohne Netzwerk/Hostmounts
und lesende Veröffentlichungsvoraussetzungen bestätigt. Nur runner-smoke.yml
wurde auf ci/runner-smoke-test geändert; der Backend-Pfadfilter blieb unberührt.
Nächster Schritt: manuelle Workflowregistrierung auf main unter bestehenden
Branchregeln klären; ausdrückliche Veröffentlichungsfreigabe abwarten.
