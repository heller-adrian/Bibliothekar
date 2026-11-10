# Bibliothekar 1.0.1 · Bestandsübernahme

- **Phase** · Inventur implementiert und lokal geprüft. Planung und Abschluss offen.
- **Basis** · Öffentliches `main` bei `1499720f8f29e3200cfdfa9b979784216fd3cfe4` enthält `v1.0.0` bei `bba1614c1a5bbbbf46767790f3ba8928bd4099b1` und liegt 15 Commits voraus. Arbeitsbranch `patch/1.0.1-legacy-adoption`.
- **Geprüfter Stand** · Der Commit, der diesen ersten Eintrag anlegt, enthält Migration 056, lesende Pfadbindung und persistente Inventur. Der Commit ist mit `git log -1 -- app/legacy_adoption_inventory.py` auffindbar.
- **Tests** · `PYTHONPATH=. python -m pytest -q tests/backend/test_legacy_adoption_inventory.py` mit synthetischen Daten und lokalem ExifTool. Vier Tests bestanden.
- **Offen** · Jahresansicht, Ereignisplanung, Gerüst, Prüfung, atomare Registrierung über Bibliothek und globale Besitzregistry, Oberfläche und Archivregressionen. Mount mit echten Read-only-Berechtigungen und Containerprüfung stehen aus.
- **CI und Release** · Kein Lauf. Die Auftragsdatei nennt GitHub-Standardrunner, die direkte AGENTS.md-Anweisung nennt `bibliothekar-safe`. Klärung ausstehend. Bestehende QA nutzt `ubuntu-24.04`. Kein PR und kein Image.
- **Weiterarbeit** · Fortschrittsdatei und letzte Commits lesen. Als Nächstes Planung auf bestehenden Ereignisregeln und Dateifamilien aufbauen. Lokaler Worktree unter `/private/tmp/bibliothekar-legacy-1.0.1`. Testumgebung unter `/private/tmp/bibliothekar-legacy-venv`.
