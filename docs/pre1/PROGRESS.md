# pre.1 Veröffentlichung — Fortschritt

Freigabe zur eigenständigen Prerelease-Veröffentlichung liegt vor.
Branch codex/publish-1.0.0-pre.1. Freigegebener Hotfix 79ab9c1f; gefrorener
versionierter Build 282aeba2dd8464f30c8484034759cbb0fd8e0823. Einzige Appänderung:
Versionskennung, lokal 12 Versions-/Startregressionen bestanden. Der finale
Dokumentationsstand 3fb14e6b enthält denselben Hotfix-Anwendungscode.

Der versionsgebundene neue Publisher verwendet die bewährte OCI-Index-Prüfung
aus dem erfolgreichen Publisher a72aaed4. Keine Verwendung des auf pre
festgelegten alten Writers. Neun gezielte Publisher-Tests mit zahlreichen
Negativ-Unterfällen, Actionlint und Bash-/Python-Syntaxprüfung bestehen.
Der Registry- und GitHub-Schreibteil ist ausschließlich manuell mit expliziter
Bestätigung PUBLISH v1.0.0-pre.1 auf dem vorbereiteten Zweig möglich.

Nächster Schritt: minimale Registrierung des manuellen Workflows auf main
unter bestehenden Regeln, dann einmaliger Dispatch. Der Publisher prüft die
akzeptierten ZIP-Digests und alle Tests, den Versionsdiff, alle eingebetteten
Appbytes und Modi und den erneut gestarteten echten Supervisor vor dem ersten
Tag-/Image-Schreibvorgang. Bei Fehler oder Teilveröffentlichung sicher stoppen.
Keine automatische Löschung oder Wiederholung. Vorhandenes pre, latest,
stabile Releasekennungen, Repository-/Paketsichtbarkeit werden geschützt.

Keine TrueNAS-Änderungen. Native TrueNAS/NFSv4, SD/USB und DNG 1.7 bleiben NOT_RUN;
Verlustabschlussmodell DEFERRED. Ein erfolgreicher Prerelease ermöglicht erst
die anschließende praktische TrueNAS-Abnahme.

## Erfolgreich abgeschlossen

GitHub-Prerelease: https://github.com/heller-adrian/Bibliothekar/releases/tag/v1.0.0-pre.1
Publisherlauf: https://github.com/heller-adrian/Bibliothekar/actions/runs/40935551438
SUCCESS, 2m28s, ausschließlich Self-Hosted bibliothekar-safe.
Minimale Workflowregistrierung auf main: a83ca36c2c3edc4370317b1bdb72548c86bb5302,
eine neue Datei, keine gestarteten Stable-/Hosted-Runner-Jobs.
Publisherstand: 2e75fc925e9fdf4e39b74b261cc2d7dddb077ae3.

Tag v1.0.0-pre.1 zeigt auf den versionierten Build-Commit
282aeba2dd8464f30c8484034759cbb0fd8e0823. Funktionaler Hotfix bleibt exakt
79ab9c1f3c9906723e328873ad790074e3f7b60c; einzige Appdifferenz Versionskennung.
Die dokumentationsbezogene Abweichung wurde geprüft. Vor Push: 9 Publisher-Tests
plus Negativ-Unterfälle, eingefrorene QA-ZIPs, 118 JUnit-Fälle und alle originalen
Containerbedingungen verifiziert. Das gebaute App-Payload wurde vollständig in
Dateibytes und Dateimodi verglichen; Version, Labels und Plattform stimmen.

Veröffentlichtes Image:
`ghcr.io/heller-adrian/bibliothekar:1.0.0-pre.1`
Unveränderliche Referenz:
`ghcr.io/heller-adrian/bibliothekar@sha256:cbaa863fb6173736bcd43e917de994fadba3d05cc69c1688c618fad21d8a17b8`

Tatsächlicher Docker-Pull per Digest, wiederholter Byte-/Modivergleich,
OCI-Index-/Descriptor-/Attestations-/Konfigurations-/Image-ID-/Revisionsprüfung PASS.
linux/amd64-Plattformmanifest und tatsächliche Docker-Plattform-Image-ID:
`sha256:0089a9cd537d208e5d2abee510bcbb92b3502128f189118a582912fc8e70d517`.
Konfigurationsdigest:
`sha256:ea170bcf27dee628cf807d3301bd3a8051d3a8047c4ee3fb59f7dc5d792aba2d`.

Der neue versionierte Container wurde vor Veröffentlichung erneut getestet:
4.000 Dateien, zwei Bibliotheken, UID568, echte HTTP-Anmeldung, Start 6,192 s,
Neustart 5,458 s. Originale RC14-14-Dateien-Korrektur/+13:00-Recovery PASS;
ursprüngliche Reservation bis zum bewussten Retry erhalten, Herkunft und
Archivbytes unverändert. Kleine synthetische Dateien, keine native NAS-Abnahme.

40 Release-Anlagen einschließlich Quellarchiv, Versionsdiff, Compose,
Upgradeanleitung, Testbericht, Original-QA-ZIPs und SHA256SUMS veröffentlicht.
Alle Anlagen im Publisher unabhängig erneut heruntergeladen und byteweise sowie
gegen GitHubs Asset-Digests verglichen. Zusätzlich lokale Nachprüfung der
veröffentlichten Prüfsummenliste gegen sämtliche 39 enthaltenen Asset-Digests
und der heruntergeladenen OCI-/Quellidentitäten erfolgreich.
SHA256SUMS selbst:
`sha256:e68d055844c9337b2935a9addbbf4603611879812ef0016a4dae846d7ea7f13c`.

Repo weiterhin privat, GHCR-Paket weiterhin wie zuvor öffentlich. Tag/Image
v1.0.0-pre, sämtliche bisherigen pre-Anlagen, latest und stabile Releaseidentitäten
im Publisher vor/nach verglichen und unverändert. Keine TrueNAS-Änderung.

Nächster Schritt: bestehende App gemäß UPGRADE-TRUENAS.md durch den Benutzer
aktualisieren und praktisch abnehmen. Native TrueNAS/NFSv4, SD/USB und DNG1.7
bleiben NOT_RUN, Verlustabschlussmodell DEFERRED.
