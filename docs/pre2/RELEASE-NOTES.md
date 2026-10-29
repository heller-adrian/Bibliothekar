# Bibliothekar v1.0.0-pre.2

Eigenständiges Prerelease für die praktische TrueNAS-Abnahme. Keine stabile 1.0.0.

Dieser Hotfix behebt die dauerhafte Startsperre nach einer gescheiterten allgemeinen
Metadatenkorrektur, etwa einer von ExifTool verweigerten DNG-1.7-Schreiboperation.
Bibliothekar kann den verifizierten Rückbau jetzt fachlich abschließen und die exakt
zugehörige F14-Reservation regulär beenden. Der ursprüngliche Metadatenauftrag bleibt
mit seiner Fehlermeldung erhalten und wird nicht als erfolgreiche Korrektur umgedeutet.
Die ursprüngliche Reservation bleibt im dauerhaften Recovery-Nachweis dokumentiert.

Historische pre.1-Zustände und neue Fehlversuche werden qualifiziert. Originalhash,
Dateityp und Identität, Journalzustand, Datenbankfelder, Bibliothek, Rollenbindungen und
Generationen müssen konsistent sein. Unbekannte Arbeitskopien oder widersprüchliche
Inhalte bleiben gesperrt. Es gibt keine pauschale Freigabe blockierter Aufgaben.

Die Startup-Leistungsverbesserung aus pre.1, die Speicherreparatur, Herkunftssicherung,
F14-Identitätsprüfung und der Archivschutz bleiben erhalten.

Abnahme: 148 Linux-Regressionstests, darunter 32 neue Recovery-Fälle, plus reale
Supervisor-/UID-568-Container mit historischem pre.1-Fehler, Anmeldung, Neustart,
SIGKILL-Wiederaufnahme, Fremdbytesperre, zwei Bibliotheken/4.000 Dateien und den
14 RC14-korrigierten iPhone-JPEGs mit +13:00. Das versionierte Release-Image wird
zusätzlich vor Veröffentlichung durch dieselben gezielten Containerfälle geprüft.

**Keine allgemeine DNG-1.7-Schreibfreigabe.** ExifTool bleibt 12.57; kein Upgrade und
kein pauschales Ignorieren von Fehlern oder Warnungen mit `-m`.

Offen: native TrueNAS-/NFSv4-Abnahme **NOT_RUN**, echte DNG-1.7-Originaldatei **NOT_RUN**,
physische SD-/USB-Hardware **NOT_RUN**, eigenständiges Verlustabschlussmodell **DEFERRED**.

[Upgrade und praktische TrueNAS-Abnahme](https://github.com/heller-adrian/Bibliothekar/releases/download/v1.0.0-pre.2/UPGRADE-TRUENAS.md)
und [Prüfbericht](https://github.com/heller-adrian/Bibliothekar/releases/download/v1.0.0-pre.2/TEST-REPORT.md)
liegen als Release-Anlagen bei. Maßgeblich ist die unveränderliche Referenz in
`IMAGE-DIGEST.txt`; `SHA256SUMS` deckt sämtliche übrigen Release-Anlagen ab.
