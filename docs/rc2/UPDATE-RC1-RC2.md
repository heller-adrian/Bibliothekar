# Bestehende TrueNAS-RC1-Testinstallation auf RC2 aktualisieren

1. Laufende Aufträge regulär beenden, Testkarte sicher auswerfen und die App stoppen.
   Aktuelle App-Konfiguration/YAML sichern. Bei gestoppter App config/database als
   zusammengehörigen Teststand sichern, einschließlich vorhandener SQLite-WAL-Dateien.
   Kein Clean Slate, keine Datenbanklöschung, keine Ordnerumbenennung.
2. Release-Assets und SHA256SUMS herunterladen und prüfen. In TrueNAS die bestehende
   App bearbeiten und **nur das Image** auf den Inhalt von IMAGE-DIGEST.txt umstellen.
   Keine neue App mit denselben schreibbaren Datasets parallel starten.
3. Alle bisherigen Datasetpfade, Mounts, Umgebungsvariablen, Port, Passwortdatei und
   insbesondere den tatsächlichen Registry-Datenbankpfad unverändert behalten.
   Das beigefügte Compose ist eine Vorlage für frische Tests; es darf deine bisherige
   Konfiguration nicht blind ersetzen. Keine Smoke-Pfade wie /database/global.sqlite3
   aus QA-Logs übernehmen. Die funktionierende manuelle NFSv4-ACL des SD-Mountbereichs
   erhalten; Web-UID/GID 568:568 bleibt ohne Schreibrecht auf diesem Bereich.
4. App starten, Browser neu laden, anmelden und Version 1.0.0-rc.2 prüfen. Vorhandene
   Bibliotheken müssen mit ihren bisherigen Pfaden erscheinen. Bei Storagewarnung,
   unerwartetem Onboarding oder DB-Fehler stoppen und Logs sichern; keine neue leere
   Bibliothek über den vorhandenen Bestand anlegen und keine Journale entfernen.
5. MANUAL-ACCEPTANCE.md mit synthetischen Daten abarbeiten: insbesondere Archiv-
   umbenennung/event.json, manuelle Metadatenzeiten, SD-Wiederimport und DE/EN/Mobil.

Keine TrueNAS-Systempakete installieren, keine Datasetrechte pauschal ändern und
keine produktiven Fotobestände verwenden. Ein Zurückwechseln des Image-Tags allein
ist nach Datenbankänderungen kein nachgewiesenes Rollback; dafür den konsistenten
vorher gesicherten Teststand verwenden. RC1 und seine Image-Tags bleiben verfügbar.
