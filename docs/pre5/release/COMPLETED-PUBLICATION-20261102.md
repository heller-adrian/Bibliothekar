# Pre.5 – Veröffentlichung vollständig abgeschlossen, 02.11.2026

**PUBLISHED_AND_INDEPENDENTLY_VERIFIED.**

- Prerelease: https://github.com/heller-adrian/Bibliothekar/releases/tag/v1.0.0-pre.5 (ID431942748, draft=false, prerelease=true, nicht latest).
- Vorhandener Tag und Anwendungscode: `b4c3a397843567bfe09b35e82c51d0009d0a71bf`.
- Erfolgreicher Abschlusslauf: https://github.com/heller-adrian/Bibliothekar/actions/runs/41520516048 – SUCCESS auf `12ef4338d20481a55016b0f74f31a6458bd20355`.
- Vorhandenes Image unverändert: `ghcr.io/heller-adrian/bibliothekar@sha256:3c36813f69a3e743d703dc573f1f1359c6c059e9f6183a2e73c756e8a2805d60`.
- OCI-Manifest / Docker-29-Image-ID: `sha256:9ff34e7cfe9f5abc68a105dcb06cf15c06b85bf15b9b7fc230fb19a0bb153647`; Konfigurationsdigest `sha256:7c46604928c695005b636d824d3e7dcd3cfed7cede7757891530e209257359b1`.

## Abschluss und Integrität

Der separate Abschlussmodus hatte ausschließlich contents:write, packages:read und actions:read. Keine Docker-Befehle, kein Build, kein Registry-Push und kein Git-Ref-Schreibvorgang. Originalartefakt13175578019 wurde anhand SHA256 `e2296cdbfcca63bf8c9b5bbd3e23e84edf123ae4727efbbf556d5b14c3348200` erneut qualifiziert. Alle70 ursprünglichen Anlagen-Prüfsummen und sechs akzeptierten QA-ZIPs stimmen. Der ursprüngliche Publisherlauf beweist erfolgreiche Build-/Byte-/Mode-/Container-/Digest-Pull-Prüfungen; dessen fehlgeschlagener Upload wurde nicht als erfolgreicher Lauf umgedeutet.

Die leere QA-SOURCE-DIFF.patch wurde ausschließlich im neuen Einzelanlagen-Satz durch QA-SOURCE-IDENTITY.md ersetzt. Die leere Originaldatei und ursprüngliche Prüfsummenliste bleiben im zusätzlich hochgeladenen original-publication-evidence.zip unverändert erhalten. Kein Anwendungsunterschied zwischen Build und Dokumentationscommit; exakter Diff erneut geprüft.

**73 Anlagen hochgeladen und anschließend vollständig unabhängig heruntergeladen**, im Runner und zusätzlich über den lokalen authentifizierten GitHub-API-Zugang. Bytes, Größen, API-SHA256 und alle72 Einträge der neuen SHA256SUMS stimmen. SHA256SUMS selbst wurde ebenfalls gegen den GitHub-Asset-Digest geprüft; ihr SHA256 ist `b6b12c7ba09514d1983b40d7c970301a361b34dca388d3d2402a697f5989f075`. Alle ursprünglichen nicht ersetzten Anlagen sind bytegleich. Originalnachweise sind erhalten.

Vor/nach Veröffentlichung: vollständiger OCI-Graph, Revision/Plattform, Image-Tag und Indexdigest unverändert; alle früheren Tags, Release-Bodies, Assetmetadaten, Images, latest und Stable unverändert. Repository bleibt privat, GHCR-Paket bleibt öffentlich. Das Prerelease ist für berechtigte Repositorybenutzer sichtbar. Keine TrueNAS-Änderungen.

Abschlussartefakt13177856469, SHA256 `2646d0a30f17699422508c45269a50be7a955ed7c0e1f125642e52e1cb4c474e`, enthält Anlagen und finalen Runner-PASS-Nachweis. Lokale unabhängige Downloads: `/private/tmp/bibliothekar-pre5-release-20261102/final-release-downloads`.

## Nutzung und Grenzen

Für das bestehende TrueNAS-Custom-App-Upgrade ausschließlich das oben gepinnte Image verwenden; bestehende App, Datenbanken, Workspace, UID/GID und Read-only-Archive erhalten. Keine zweite Instanz mit denselben beschreibbaren Mounts. UPGRADE-TRUENAS.md und digestgepinntes compose.pre5.yaml sind Release-Anlagen.

Keine Wiederholung vollständiger Tests in diesem Abschluss. Es gelten die dokumentierten akzeptierten Quellstände plus abschließende Delta-/Image-Prüfungen. Native TrueNAS/NFSv4, physische SD-/USB-Hardware, tatsächliches DNG-1.7- und RAF-Schreiben: NOT_RUN. Eigenständiges Verlustabschlussmodell und bekannte Herkunfts-Metadatenvariante A: DEFERRED. Prerelease, keine stabile1.0.0.
