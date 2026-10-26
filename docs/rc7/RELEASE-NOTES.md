# v1.0.0-rc.7 – historische leere Installation wieder einrichten

Prerelease für die praktische TrueNAS-Erstinstallationsprüfung. Keine stabile 1.0.0.

- Eindeutig leere Altzustände mit vollständig gebundenen vier F14-Verwaltungswurzeln können nach ausdrücklicher Bestätigung neu eingerichtet werden, auch wenn storage_initialization fehlt oder unvollständig ist.
- Frische Installationen erzeugen die englischen Verwaltungsordner automatisch und erreichen das reguläre Bibliotheks-Onboarding.
- Vorhandene Medien, Bibliotheken, Registryhistorie, private Retention, offene Operationsbelege oder widersprüchliche Mountbindungen bleiben geschützt. Alte F14-Belege werden archiviert.
- Speicherwarnung erklärt DE/EN den Grund und den sicheren Wiederherstellungsweg. Doppelte catalog_unavailable-Einträge entfallen.

Diese Veröffentlichung beruht auf einer gezielten RC7-Linux-/Containerprüfung sowie den dokumentierten RC6-Nachweisen, nicht auf einer neuen vollständigen Backend-Suite oder finalen 1.0.0-Gesamtabnahme. Die tatsächlichen RC7-Ergebnisse liegen in den Prüfassets. Historische rote Zwischenläufe bleiben dokumentiert.

Native TrueNAS-/ZFS-/NFSv4-, SMB- und Gerätequalifikation bleibt offen. Private Daten vertrauen dem vorgesehenen App-/Administratorbereich einschließlich UID568; keine absolute Isolation gegenüber Administratoren oder anderer Software derselben UID. Die bekannte manuelle SD-Mount-ACL-Voraussetzung bleibt erforderlich; automatische Katalogbereitstellung ist separat. Akzeptierte F13-/F24-Restrisiken und B12 bleiben unverändert.
