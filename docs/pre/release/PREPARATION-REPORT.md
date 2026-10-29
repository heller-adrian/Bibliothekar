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

## Veröffentlichungsversuch vom 29. Oktober 2026

Nach ausdrücklicher Freigabe wurde ausschließlich der vorbereitete
Registrierungsworkflow auf main angelegt (Commit
2a060b92b704f457fdb0e6653df757b461f95ce6). Der Publisher lief auf dem
Self-Hosted-Runner im [Lauf 40891738442](https://github.com/heller-adrian/Bibliothekar/actions/runs/40891738442).
Quellvergleich, die elf akzeptierten QA-Artefakte, Build und wiederholter
Vergleich sämtlicher eingebetteter Anwendungsdateien bestanden. Anwendungscode:
70c0bb57afa168efec83b1b60245b819b36161ff.

Der Lauf wurde vor der GitHub-Releaseanlage gestoppt: registry_manifest()
akzeptiert bisher nur einzelne OCI-/Docker-Manifeste. Docker 29 erzeugte einen
OCI-Index mit Anwendungsmanifest und Provenance-Attestation; die eingeschränkte
Accept-Aushandlung erhielt HTTP 404. Ein tatsächlicher Docker-Pull über den
unveränderlichen Digest sowie die erneute Prüfung von Appdateien, Version und
OCI-Revision waren zuvor erfolgreich. Die vollständige abschließende
Registry-/Image-ID-/Berechtigungsprüfung und Releaseartefaktprüfung sind NICHT
abgeschlossen; der Veröffentlichungsversuch gilt als fehlgeschlagen.

Erhaltener Teilzustand (keine Löschung, kein Überschreiben, kein zweiter Lauf):

- Git-Tag v1.0.0-pre: 9e0fb0a2ff2166d8946c0589c3bc36d052bb03e5.
- Image ghcr.io/heller-adrian/bibliothekar:1.0.0-pre:
  sha256:9e055cb8103285cf59da9e5c4f6c0ae697778e14441658f2ade6f877bd6b335b.
- GitHub-Release: nicht angelegt.
- Repository weiterhin privat; GHCR-Paket weiterhin anonym lesbar wie zuvor.
- latest unverändert:
  sha256:b2a523e09730fd28e6c3178182a15fb1a47e5a529790b7c9ba09f413377aeff1.

Die anschließende ausschließlich lesende Diagnose konnte den OCI-Index mit
geeigneter Accept-Aushandlung abrufen und dessen sowie der enthaltenen Manifeste
SHA-256-Digests prüfen. Das ersetzt nicht den fehlgeschlagenen Abschlussgate.
Der Lauf enthält das Diagnoseartefakt pre-publication-evidence, ID 12906075241,
ZIP-Digest sha256:433839bee6b3482cc655cd539fc2f859d9d3ba3f58fffd251a20de07982adf47.
Lokale Registrydiagnose: /private/tmp/bibliothekar-pre-publication-40891738442/.

Nächster kontrollierter Schritt: OCI-Index-Unterstützung und Image-ID-Zuordnung
im Publisher prüfen, anschließend ausschließlich die fehlenden Prüfungen und
Releaseanlagen auf Grundlage des vorhandenen Tags/Images planen. Gemäß
Stopregel wurde dies noch nicht ausgeführt. Keine NAS-Änderung.
Native TrueNAS-/NFSv4-, SD-/USB- und DNG-1.7-Abnahme: NOT_RUN;
eigenständiges Verlustabschlussmodell: DEFERRED.

## Kontrollierte Fortsetzung vorbereitet

Auf ausdrücklichen Folgeauftrag ergänzt: strenge OCI-Index-/Manifestlistenprüfung
mit Plattform-, Descriptor-, Konfigurations-, Docker-ID- und Attestationszuordnung;
getrennter `complete-existing`-Job mit ausschließlich lesenden GHCR-Rechten.
Actionlint sowie Python- und Bash-Syntaxprüfung bestanden. Die korrigierte Prüfung
hat den bereits vorhandenen OCI-Index samt Plattformmanifest, Konfiguration und
Provenance ausschließlich lesend erfolgreich geprüft. Keine Anwendungscodeänderung.
Nächster Schritt: gezielte Tests auf dem committed Quellstand und kontrollierter
Dispatch mit `COMPLETE v1.0.0-pre`; keine neue erste Veröffentlichung.
