# Veröffentlichung und öffentliche Quellcodefreigabe – Checkliste

Diese Checkliste ist für die öffentliche Freigabe des Projekts bestimmt. Sie enthält **keine** privaten Infrastrukturinformationen.

## Vor Änderung der Repository-Sichtbarkeit

- [ ] Quellbaum auf eingecheckte Zugangsdaten, Token, Zertifikate, private Schlüssel, interne IP-Adressen und installationsspezifische Pfade prüfen.
- [ ] **Die gesamte erreichbare Git-Historie**, alle Tags, Branches, Releases, Action-Artefakte und hochgeladenen Dateien mitprüfen. Ein neuer Commit entfernt ältere Angaben **nicht** aus der Historie.
- [ ] Versehentlich enthaltene Geheimnisse unabhängig von späteren Lösch-Commits sperren bzw. austauschen.
- [ ] Öffentliche Dokumentation auf Funktionen, Systemanforderungen, Einrichtung, Grenzen und Support konzentrieren. Entwicklungsspezifische QA-Unterlagen ohne privaten Infrastrukturbezug bereitstellen.
- [ ] Lizenz, Drittanbieter-Lizenzen, Sicherheitskontakt und Release-Hinweise überprüfen.
- [ ] Test- und Image-Publishing für öffentliches Repository kontrollieren; GHCR-Sichtbarkeit und Rechte separat prüfen.
- [ ] Bestehende Pull Requests und Commit-/Issue-Kommentare ebenfalls auf private Angaben prüfen.

## Gate für einen stabilen 0.50.0-Release

- [ ] BA-01: Datenbank- und Ereignisdokumente bei Fehler/Neustart konsistent halten.
- [ ] BA-02: Sichere, wiederanlauffähige Löschtransaktionen.
- [ ] BA-03: Schreibende APIs vor unberechtigtem Zugriff schützen.
- [ ] BA-08: Zielzuordnung und Ursprungs-Warteschlange atomar und idempotent fortschreiben.
- [ ] BA-12: Recovery nach Abbruch während der Metadatenkorrektur.
- [ ] BA-07/10: vollständige dynamische Fehlerfall- und Neustartabnahme.
- [ ] Sämtliche Backend-Tests, aktuelle Archiv-E2E, Upgrade- und Mehrbibliothekstests bestanden.
- [ ] Verifizierten Commit einmalig als stabilen Release markieren; keine Force-Retags.
- [ ] Versionstag und Build-Digest dokumentieren; erst dann `latest` veröffentlichen.

## Separates Discover-Gate

Der direkte SD-Kartenimport bleibt eine Produkteigenschaft. Die für eine TrueNAS-Community-Katalog-App zulässigen Geräteberechtigungen werden gesondert abgestimmt und getestet. Die Discover-Entscheidung blockiert nicht die Entwicklung der selbst gehosteten Custom-App; sie rechtfertigt aber auch keine Umgehung der Sicherheitsprüfung.
