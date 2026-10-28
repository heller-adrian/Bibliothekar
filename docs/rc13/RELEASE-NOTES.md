# Bibliothekar 1.0.0-rc.13 — Prerelease

Automatisierte Linux-Abnahme bestanden: 2.189 Backendtests, 101 gezielte
Gate-Tests, 44 Chromiumfälle und 46 reale Supervisor-/Containerfälle.
Keine native TrueNAS-/ACL-Abnahme und keine stabile 1.0.0-Freigabe.

- Ursprüngliche Quellfamilie bleibt nach bestätigter Einzeldateilöschung erhalten.
  Eine betroffene RC12-Installation kann anhand vorhandener Belege automatisch
  fortsetzen. Fehlende oder widersprüchliche Belege blockieren weiterhin.
- Neue Bibliotheksprojektionen referenzieren dieselbe ursprüngliche Familie.
- Begrenztes, vollständig erneut geprüftes Wiederlesen bei nachgewiesenem
  atomarem Austausch einer geöffneten F14-State-Datei.
- Tatsächliche Bibliothekspfade in Archivänderung und Rückänderung.
- DE/EN-Korrekturen, neutrale Arbeitsbereichsbegriffe, mobile Statusanzeige mit
  rein lokalem Ausblenden, verständlichere Pfad- und Reparaturdarstellung.
- Ganze-Ereignisordner-Anweisung nur bei vollständig geprüftem Bestand und
  verifizierten Rückkehrkopien; unbekannte Inhalte bleiben geschützt.

[Ursachenanalyse](ANALYSE.md) · [Alle 20 Screenshots](SCREENSHOTS.md) ·
[Upgrade](UPGRADE-RC12.md) · [Praktische TrueNAS-Abnahme](TRUENAS-TEST.md)

[Testbericht](TEST-REPORT.md) enthält Quellstände und Abdeckungsgrenzen.
Das Release ergänzt den unveränderlichen Image-Digest, tatsächlichen Pullbeleg,
digestgebundene Compose-Datei, vollständige QA-Belege und SHA256SUMS.
