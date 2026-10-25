# v1.0.0-rc.4 – Prerelease zur manuellen TrueNAS-Erprobung

Enthält die vollständige geprüfte RC3-Funktionsbasis und bestehende Sicherheitskorrekturen.

- SD-Wiederimportprüfung läuft in der vorhandenen persistenten Queue mit Fortschritt und Mehrfachklickschutz. Browser-/Prozessneustart werden berücksichtigt; vollständig gesicherte Karten erzeugen keinen leeren Import und keinen zusätzlichen Importhistorieneintrag.
- Mobile Workspace-Vorschau, EN/DE-Texte und kompakte Archivhistorie verbessert; verifizierte manuelle Archivumbenennungen synchronisieren den aktuellen Titel. Historische Altzustände werden nicht automatisch migriert.
- Fehlgeschlagene Papierkorb-Restores können einzeln ausdrücklich sicher abgebrochen werden, wenn Originale, unabhängige Rückfallkopien, Identität, SHA und Katalogzustand vollständig nachgewiesen sind. Journale und Rückfallkopien bleiben erhalten; keine automatische Finalisierung.
- Aktive Restores sperren alle Löschungen. Inaktive Einzelreservationen schützen ihre Dateien; unabhängige Dateien bleiben selektiv löschbar. Vollständiges Leeren bleibt bei Reservationen gesperrt. F11-/F24- und Recoveryprüfungen bleiben erhalten.

Produktcommit `7122afa8864258cba6d1d5500b78413ded7acae7`, Git-Tree `eb49870426748bc4b7722dadf531a841471ebb3d`.
QA: https://github.com/heller-adrian/Bibliothekar/actions/runs/40225974384
**1849 PASS,0 FAIL/ERROR/SKIP**, linux/amd64-Build und Onboarding-Smoke PASS,174 App-Dateihashes,UID/GID568:568 und SQLite geprüft. Keine Backend-Wiederholung zur Veröffentlichung. Der tatsächliche veröffentlichte Registrydigest wird erneut abgerufen und geprüft.

Für bestehende RC3-App: UPDATE-RC3-RC4.md. Digestgebundenes compose.truenas.yaml, IMAGE-DIGEST.txt und SHA256SUMS sind Release-Assets. Bestehende Mounts/Registrypfade/Passwortdatei und geschützte manuelle NFSv4-SD-ACL erhalten; automatische Katalogbereitstellung bleibt offen. Kein Stable und kein latest-Update.

Offen: reale TrueNAS-/ZFS-/SMB-/ACL-/SD-/Smartphone-Abnahme, einschließlich manueller Papierkorbregression. B12 bleibt zurückgestellt. Akzeptierte F13-Race/mmap-Grenze und extreme F24-Konkurrenzrestrisiken unverändert; keine absolute Erhaltungsgarantie. Archivdateien während Arbeitsbereich-Freigabe nicht extern ändern.
