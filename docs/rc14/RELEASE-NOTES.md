# Bibliothekar v1.0.0-rc.14 — Prerelease

**Anwendungscode:** `b43d9fb9d957cb817f74e6fee303b6413d91cd38`.
**Vollständige CI-Abnahme:** [GitHub Actions 40751837451](https://github.com/heller-adrian/Bibliothekar/actions/runs/40751837451), erfolgreich.
**Wichtig:** Dies ist keine stabile 1.0.0-Freigabe; native TrueNAS-/OpenZFS-/NFSv4-ACL-Prüfungen bleiben ausdrücklich **NOT_RUN**.

## Neuerungen gegenüber RC13

- Nachweisgebundene Fortsetzung unterbrochener RC13-Importe: Wiederaufnahme nach Journalerzeugung und nach teilweise veröffentlichter Dateiserie ohne Verlust der ursprünglichen Herkunft.
- SQLite-/F14-gebundene Bibliotheksidentitäten; geschützter Lebenszyklus zusätzlicher Bibliotheken einschließlich sicherer Abmeldung und nachfolgendem gewöhnlichem Folder Import aus dem erhaltenen schreibgeschützten Archiv.
- Schutz vor konkurrierenden Schreibzugriffen während Bestandsabgleich; physisch überprüfte Bestandszähler und zurückhaltende Reparatur ohne Erfindung nicht belegter Dateien.
- Englisch-/Deutsch-Navigation und mobile Statusdarstellung geprüft; neue Arbeitsbereiche werden benannt, ohne automatisch einen Bibliotheksordner `main` anzulegen.
- Exklusive, journalgestützte Dateiüberführung: unbekannte oder widersprüchliche Medien- und Wiederherstellungsbelege sperren Änderungen weiterhin.

## Nachweise und Einsatzgrenzen

2.232 Backendtests in acht disjunkten Partitionen, 110 gezielte Sicherheits-/Onboarding-Tests, 147 RC14-Chromiumfälle, 44 unveränderte Chromium-Regressionen und 48 reale Docker-Supervisor-/Migrationsfälle bestanden. Darunter RC12→RC14, RC13→RC14 nach SIGKILL am Journal bzw. nach drei veröffentlichten Dateien, Bibliotheksrückzug nach Registry-Commit, Wiederanlauf, RC10/RC11 und RC12-Reparatur.

Die Release-Anlagen enthalten den exakten Quellcode, unveränderliche Prüfnachweise, Image-Digest, Container-Pull-Beleg und SHA-256-Prüfsummen. Für die betriebliche Einführung die [Upgrade-Anleitung](UPGRADE-RC13.md) und [TrueNAS-Testanleitung](TRUENAS-TEST.md) lesen. **Keine Clean-Slate-Operation zur Fehlerbehandlung verwenden.**
