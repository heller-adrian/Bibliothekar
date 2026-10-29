# Releaseprüfung v1.0.0-pre.2

Freigegebener Hotfix: `ff1cdf3557b87e5f390f8c1f71abe179ac9d4a52`.
Dokumentationsstand: `a953461979a9a91880347fc31c6a04b778867c65` (nur drei Dokumentationsdateien).
Versionierter Build: `f8e128c9e5aec462d16f987d2e71dbe0d02f1549`.
Einzige Änderung an Anwendungsdateien: Versionszeichenfolge in `app/__init__.py`.
Abhängigkeiten, Dockerfile, Migrationen, Tests und akzeptierte QA-Skripte sind unverändert.

Akzeptierte Linux-Abnahme:
https://github.com/heller-adrian/Bibliothekar/actions/runs/40957407776

148 Regressionstests bestanden, null Fehler und null übersprungene Tests, darunter
32 neue Recovery-Fälle. Artefakt 12933834151, SHA-256:
`46a5015aaacf31c5307bfa2a5c9d2b34efe3594ba88073121748e60a4f201668`.
Der Publisher lädt es erneut herunter und prüft zusätzlich alle 14 enthaltenen Dateien
gegen den freigegebenen Nachweis. Original-ZIP und Metadaten liegen als Release-Anlagen bei.

Das versionierte Release-Image muss vor dem ersten Tag-/Registry-Schreibvorgang bestehen:

- Byteweiser Vergleich aller eingebetteten Anwendungsdateien und ihrer Modi; keine
  fehlenden, zusätzlichen oder symbolisch verknüpften Anwendungsdateien.
- Version 1.0.0-pre.2, OCI-Revision exakt der Build-Commit, Plattform linux/amd64.
- Reale Supervisor-Container unter UID 568, isolierte RW-Binds, RO-Testarchive,
  deaktiviertes Containernetzwerk und authentifizierte HTTP-Anmeldung.
- Historischer veröffentlichter pre.1-Schreibfehler mit Startsperre und anschließender
  Wiederaufnahme derselben Reservation; ursprünglicher Fehlerauftrag unverändert.
- Neue Schreibverweigerung, verifizierter Rückbau, Neustart und Bibliothekszugriff.
- Fremde Originalbytes bleiben gesperrt; echter Webserver-SIGKILL wird sicher wiederaufgenommen.
- Zwei Bibliotheken/4.000 Dateien sowie die 14 RC14-korrigierten JPEGs mit +13:00;
  Herkunftsnachweise und Archivbytes bleiben erhalten.
- ExifTool unverändert 12.57.

Nach Push: echter Docker-Pull über den Index-Digest, erneuter byteweiser Vergleich,
vollständige OCI-Index-/Plattform-/Konfigurationsprüfung einschließlich Attestation,
Docker-ID-/RootFS-Zuordnung und Tagzuordnung. Attestation ist ein digestgebundener
Build-Nachweis, keine unabhängig signierte Vertrauenswurzel.

Die JSON-Anlagen `pre2-*-evidence.json`, `APP-PAYLOAD.json`, `OCI-VERIFICATION.json`,
`SOURCE-IDENTITY.json` und die Registry-Dokumente enthalten die tatsächlich geprüften
Werte. Veröffentlichung erfolgt ausschließlich nach ihren erfolgreichen Prüfungen.
Alle Release-Anlagen werden anschließend unabhängig heruntergeladen, byteweise,
gegen die GitHub-Asset-Digests und gegen SHA256SUMS überprüft.

Alte pre-/pre.1-Releases, deren Anlagen und Images, sämtliche bestehenden Tags, latest,
neueste stabile Veröffentlichung und Sichtbarkeiten werden vor/nachher verglichen.
Repository bleibt privat, GHCR-Paket behält seine bestehende Sichtbarkeit.

Keine vollständige fachlich unveränderte Testmatrix wurde erneut gestartet.
Kein Zugriff auf produktive NAS-Daten und keine globalen Docker-Bereinigungen.

Testgrenzen: native TrueNAS/NFSv4 **NOT_RUN**, echte DNG-1.7-Originaldatei **NOT_RUN**,
physische SD/USB **NOT_RUN**, eigenständiges Verlustabschlussmodell **DEFERRED**.
Die DNG-Verweigerung wird auf einer kontrollierten Arbeitskopie simuliert; dies ist
kein Beleg für das erfolgreiche Schreiben eines DNG-1.7-Originals.
