# Technische Freigabegrundlage Bibliothekar v1.0.0-pre.3

Geprüfter Anwendungscode: `7733c64bc7c555e7dc416ed7b953a00b6cf911b2`.
Dokumentationsstand: `400487b791af646f110c4a3746ade4bc66526c63`.
Zulässige zusätzliche Änderung an `app/`: Versionszeichenfolge in `app/__init__.py` von `1.0.0-pre.2` auf `1.0.0-pre.3`.

Entwicklungsabnahme: [GitHub Actions 40969680973](https://github.com/heller-adrian/Bibliothekar/actions/runs/40969680973), SUCCESS.
QA-Artefakt: 12939434627, SHA-256 `e8f17247f477d46e115e4bdc351258451b829fd8734cf63c080e4ede08f94a03`.

Ergebnisse: 181 gezielte Python-Regressionen bestanden, sechs pre3-Container-Szenarien erfolgreich (historisches pre.2, tatsächlicher RC14-Import, manipulierte Bytes, drei offene F14-Operationen, SIGKILL nach Metadatenabschluss und SIGKILL beim Import), drei pre2-DNG-Rollbackprüfungen erfolgreich, 4.000-Dateien-Test mit zwei Bibliotheken, zwei Starts von rund sechs Sekunden, alle 14 iPhone-JPEGs mit +13:00 sowie Herkunfts- und Archivnachweise unverändert.

Vor Veröffentlichung muss die eingecheckte Publisher-Pipeline den SHA-256-Artefakt-Digest erneut prüfen, alle eingebetteten Anwendungsbytes und Dateimodi mit dem eingefrorenen Quellcommit vergleichen, das versionsgebundene Image unter UID 568 mit echten Containerfällen prüfen und nach dem Push einen echten Digest-Pull, vollständige OCI-Prüfung, Repository/Registry- und GitHub-Asset-Kontrollen bestehen. Der vollständige Nachweis wird in Release-Anlagen gespeichert.

Drei ursprüngliche NAS-F14-Operationen nicht vollständig klassifiziert. Native TrueNAS/NFSv4, physische SD/USB, reale DNG-1.7-Schreibfähigkeit: NOT_RUN. Eigenständige Verlustabschlüsse: DEFERRED. Keine Veröffentlichung einer stabilen 1.0.0.
