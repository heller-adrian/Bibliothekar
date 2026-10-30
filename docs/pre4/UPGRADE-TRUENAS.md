# Testupgrade TrueNAS Custom App: v1.0.0-pre.3 → v1.0.0-pre.4
**Prerelease, noch nicht auf deinem echten TrueNAS-Bestand abgenommen.**

1. Vorhandene Test-App kontrolliert stoppen; zusammengehörige Snapshots von **Appdata und Workspace** anlegen. SQLite einschließlich WAL/SHM, F14-Journale, Reservierungen, Mounts und alle Herkunftsnachweise vollständig erhalten.
2. In der bestehenden TrueNAS-Custom-App **nur den Docker-Tag** auf `1.0.0-pre.4` umstellen; Repository `ghcr.io/heller-adrian/bibliothekar` beibehalten. Falls unterstützt, die unveränderliche Referenz aus `IMAGE-DIGEST.txt` verwenden. Bei Tag-Feld keinen Digest als Tag eintragen.
3. UID/GID 568, Bibliotheksregistrierungen, vorhandene Appdata-, Workspace-, Fotoarchiv- und Quellen-Mounts unverändert übernehmen. Unabhängige Archive weiterhin Read Only. **Keine zweite beschreibende Instanz gleichzeitig starten.**
4. Nach Neustart Authentifizierung, `/healthz`, normal erreichbare Oberfläche, `READY` und Operationsdiagnose prüfen. Auch bei `READY` können nicht qualifizierte F14-Vorgänge **Schreiben** blockieren; das ist kein Ausfall der Verwaltungsordner.
5. Historische Fuji-JPEG-Datei und originale drei F14-Reservationsnachweise **nicht manuell verschieben, bearbeiten oder löschen**. Falls Schreiben weiterhin blockiert bleibt, authentifizierte Diagnose sowie rein lesende F14-/Importnachweise sammeln. Die bisherige erfolgreiche Dateiübernahme ist nicht mit einer vollständigen Wiederherstellung aller historischen Operationen gleichzusetzen.
6. Nach Freigabe der tatsächlich qualifizierten Fälle nochmals kontrolliert neu starten; Archiv-Read-Only, Herkunft, Hauptbestand, Papierkorb und 14 iPhone-JPEGs kontrollieren.

**Keine manuelle SQLite-Reparatur, kein Clean Slate und keine Aufweichung von F14-Kontrollen.** Tag-Rückwechsel allein setzt keine Datenbank- und Workspace-Migration zurück; hierfür zusammengehörige Snapshots verwenden.
