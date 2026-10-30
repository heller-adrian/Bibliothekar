# Technischer Prüfbericht – Bibliothekar v1.0.0-pre.4
Unveränderter, geprüfter Anwendungsstand: `cd074b76e208fc05932d1afa172eb18b7fc0ddda`
[Lauf 41049302266](https://github.com/heller-adrian/Bibliothekar/actions/runs/41049302266): **SUCCESS**, Versuch 1. Source/Artefakte sind in `docs/pre4/EVIDENCE.json` referenziert.

- 39 neue Sicherheits-/Architektur-Vertragstests: PASS.
- 148 bisherige Metadaten-/Identitäts-/RC12-/F14-Regressionen: PASS.
- Echte General-JPEG-Korrektur/Übernahme, Historien-/Hash-/F14-Prüfungen, zwei Neustarts: PASS.
- Chromium als isolierter Browsercontainer: 8 Kombinationen Deutsch/Englisch, Mobil/Desktop, normale App/Papierkorb: PASS.
- pre.2/pre.3- und RC14-Altzustände, Fremdbytes, drei offene F14, SIGKILL-Fälle: PASS.
- Zwei Bibliotheken, 4.000 Dateien, zwei Starts (5,23 s / 5,38 s): PASS.
- 14 korrigierte iPhone-JPEGs mit +13:00, Herkunft unverändert, schreibgeschützte Archive: PASS.

Die abschließende Veröffentlichung baut denselben Anwendungscode mit **ausschließlich geändertem `__version__`**, verifiziert jeden eingebetteten Quell-Bytewert und Dateimodus, prüft Isolation und Containerverhalten erneut und kontrolliert nach dem GHCR-Push den echten unveränderlichen OCI-Graphen. Vorherige Tags, Releases, `latest` und echte TrueNAS-Bestände dürfen sich dabei nicht ändern.

NOT_RUN: native TrueNAS-/NFSv4, physische SD/USB, reale DNG-1.7-Metadaten-Schreibfähigkeit; tatsächliche drei F14 auf dem NAS nicht einzeln vollständig klassifiziert.
