# Bibliothekar v1.0.0-pre.3

Eigenständiges, vorläufiges TrueNAS-Testrelease; keine stabile Version 1.0.0.

Dieser Hotfix behebt den Folgefehler nach einer erfolgreich abgeschlossenen allgemeinen Metadatenkorrektur, deren Datei anschließend regulär in den Tagesbestand übernommen wurde. Ein offener historischer F14-Nachweis kann nun nur anhand der vollständigen, überprüften Import-, Manifest-, Verschiebe-, Katalog-, Hash-, Inode- und Herkunftskette abgeschlossen werden. RC14-Zeitstempel-Importkennungen sind ausschließlich mit derselben vollständigen Nachweiskette qualifizierbar.

Erfolgreiche neue Metadatenkorrekturen persistieren vor dem F14-Abschluss einen nachprüfbaren Ergebnisnachweis. Der Übernahmepfad serialisiert Korrektur und Quellbereinigung; bei unbekannten Vorgängen oder fremden Bytes bleiben vorhandene Daten und Reservationsnachweise geschützt. Die authentifizierte Diagnoseansicht ist rein lesend. **Es gibt keine pauschale Entsperrung einzelner oder gemeinsamer Vorgänge.**

Freigegebene Entwicklungsabnahme: 181 Regressionstests; sechs echte pre.3-Containerfälle mit pre.2- und RC14-Rückwärtsprüfung, negativen Fällen und SIGKILL; drei pre.2-DNG-Rollbackfälle; zwei Bibliotheken mit 4.000 Dateien; 14 iPhone-JPEGs mit +13:00; schreibgeschützte Archive und Herkunftsnachweise unverändert. Das versionierte Image wird vor der Veröffentlichung erneut geprüft.

**Achtung:** Die drei echten F14-Operationen auf dem TrueNAS sind noch nicht vollständig klassifiziert. Nach dem Upgrade können weitere berechtigte Sperren bestehen. Kein Clean Slate, keine manuelle SQLite-Reparatur, keine Löschung von F14-Journalen. 

Native TrueNAS-/NFSv4-Abnahme, reale DNG-1.7-Schreibprüfung und physische SD-/USB-Tests: NOT_RUN. Eigenständiges Verlustabschlussmodell: DEFERRED.

[TrueNAS-Upgrade-Anleitung](https://github.com/heller-adrian/Bibliothekar/releases/download/v1.0.0-pre.3/UPGRADE-TRUENAS.md) · [Technischer Prüfbericht](https://github.com/heller-adrian/Bibliothekar/releases/download/v1.0.0-pre.3/TEST-REPORT.md).

Das unveränderliche Image steht nach Abschluss der Veröffentlichung in `IMAGE-DIGEST.txt`; `SHA256SUMS` sichert die übrigen Anlagen ab.
