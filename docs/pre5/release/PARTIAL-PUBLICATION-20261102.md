# Pre.5 – gesicherter Veröffentlichungs-Teilzustand, 02.11.2026

Status: **PARTIAL_PUBLICATION_BLOCKED**, kein vollständiges GitHub-Prerelease.

## Unveränderliche Identitäten

- Anwendungscode / vorhandener Git-Tag `v1.0.0-pre.5`: `b4c3a397843567bfe09b35e82c51d0009d0a71bf`.
- Publisher-Commit: `cf8702290f3170250aa134d80d52b52472d7c413`, Branch `codex/publish-1.0.0-pre.5`.
- Lauf: https://github.com/heller-adrian/Bibliothekar/actions/runs/41515697003 – FAILURE ausschließlich beim GitHub-Anlagenupload.
- Bereits gepushtes Image: `ghcr.io/heller-adrian/bibliothekar@sha256:3c36813f69a3e743d703dc573f1f1359c6c059e9f6183a2e73c756e8a2805d60`.
- linux/amd64-Anwendungsmanifest / Docker-29-Image-ID: `sha256:9ff34e7cfe9f5abc68a105dcb06cf15c06b85bf15b9b7fc230fb19a0bb153647`.
- Konfigurationsdigest: `sha256:7c46604928c695005b636d824d3e7dcd3cfed7cede7757891530e209257359b1`.
- Provenance-Attestation: `sha256:1a151628089f66e2fa9e0cb8a683cb370cf5efabab9718d3d1a4396e182e7d58`.

## Tatsächlich bestandene Prüfungen

Akzeptierte QA-ZIPs, exakte Backendabdeckung (2579 Nodes auf dem dokumentierten früheren Stand), Source-Deltas und 191 historische Frontendfälle unabhängig qualifiziert. Elf lokale Publisher-Verträge bestanden. Im Publisher bestanden 21 gezielte Tests für die abschließenden Migrationsänderungen und bestehende negative SQLite-/Recovery-Verträge. Das tatsächlich gebaute Release-Image bestand alle sechs Container-Skripte, Supervisor/UID 568, 90 Medien, historische Recovery/SIGKILL, 4000 Familien, 14 iPhone-JPEGs, Browser und Archivschutz. Build-Quellen und eingebettete Dateien/Modi stimmen überein. Tatsächlicher Digest-Pull und OCI-Graph-/Revisionsprüfung bestanden. Keine erneute vollständige Backendmatrix behauptet.

## Nachgewiesener Fehler und remote Zustand

`gh release create` scheiterte beim Upload von `QA-SOURCE-DIFF.patch` mit `HTTP 400: Bad Content-Length` (temporäre Release-ID 431924706). Die Datei ist exakt null Byte: `git diff BUILD DOC -- app tests qa Dockerfile requirements.txt requirements-rc.constraints.txt` ist bei reinen Dokumentationsänderungen erwartungsgemäß leer. Der Publisher hat diesen gültigen Leerfall nicht für den GitHub-Anlagenupload behandelt. Kein Anwendungs-/Integritätsfehler wurde beobachtet.

Nach dem Fehlschlag liefern sowohl `GET releases/tags/v1.0.0-pre.5` als auch `GET releases/431924706` HTTP 404. Kein nicht-draft Prerelease vorhanden; keine heruntergeladenen Release-Anlagen geprüft. Tag und Image existieren; deshalb ursprünglichen Publisher keinesfalls erneut ausführen.

Unabhängig nach dem Fehlschlag wurden aktueller GHCR-Tag und Indexdigest, alle geschützten früheren Tags/Release-Bodies/Assetmetadaten/Images, `latest`, stabile Release-Kennung und Repository-Privatsphäre erneut lesend geprüft: unverändert. Paket war in den Runner-Vorprüfungen unverändert öffentlich; das lokale OAuth-Token kann Paketmetadaten mangels `read:packages` nicht erneut abfragen. Keine Rechteänderungen. Das private Repository bleibt privat; ein späteres GitHub-Prerelease ist nur für Berechtigte sichtbar.

## Gesicherte Anlagen und Prüfsummen

https://github.com/heller-adrian/Bibliothekar/actions/runs/41515697003/artifacts/13175578019

Artefakt `pre5-publication-evidence`, ID 13175578019, SHA-256 `e2296cdbfcca63bf8c9b5bbd3e23e84edf123ae4727efbbf556d5b14c3348200`. ZIP unabhängig heruntergeladen, Hash geprüft, sicher entpackt. Alle 70 Einträge der vorbereiteten `SHA256SUMS` unabhängig geprüft; insgesamt 71 vorbereitete Anlagen einschließlich Prüfsummenliste. Darunter Original-QA-ZIPs, OCI-Graph, Quellarchiv, Anleitungen, Compose, komplette Release-Laufzeitlogs und JUnit. Das Artefakt ist laut GitHub bis 02.12.2026 verfügbar. Lokale Sicherung `/private/tmp/bibliothekar-pre5-release-20261102/13175578019.zip` und entpacktes Verzeichnis gleicher ID.

## Kontrollierte Fortsetzung – noch nicht ausgeführt

Gemäß Nutzer-Stoppvorgabe kein weiterer Veröffentlichungsversuch. Nur ein separater Abschlussmodus kommt infrage: vorhandene exakte Tag-/Image-Identitäten und alle QA-/Paket-/Protected-Nachweise erneut qualifizieren; weder Build noch Push noch Tagänderung erlauben. Original-Artefakt unverändert lassen. Den leeren Diff für einen neuen Anlagen-Satz durch einen expliziten Nichtleer-Nachweis ersetzen bzw. separat dokumentieren, neue SHA256SUMS bilden, die ursprüngliche leere Datei im Original-ZIP erhalten. Erst nach diesen Kontrollen fehlendes Prerelease erstellen und Anlagen unabhängig erneut herunterladen. Keine alte Anlage ersetzen. Bei vorhandenem oder widersprüchlichem Release stoppen. Der bisherige Publisher ist absichtlich kein Resume-Modus.

Native TrueNAS/NFSv4, physische SD/USB und tatsächliches DNG-1.7-Schreiben bleiben NOT_RUN; eigenständiges Verlustabschlussmodell DEFERRED. Keine TrueNAS-Änderungen.
