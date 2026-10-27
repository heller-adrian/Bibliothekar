# 1.0.0-rc.11 – unveröffentlichter Kandidat

- Bestätigten TrueNAS-Erststartfehler durch das geerbte Workspace-Trash-Lock behoben: gemeinsame Workspace-ACL und private Sperrautorität getrennt.
- Native private ACL- und Elternprüfung statt Vertrauen auf Modus 0700 allein; unsichere oder unbekannte Backends blockieren mit konkreter Ursache.
- Kontrollierte Offlineübernahme begonnener RC10-Erststarts mit erhaltener Originalreservation und gesicherten Originalnachweisen.
- F14-Format 2 und dauerhafte Bootstrap-Abschlussbelege schließen die Crash-Lücke zwischen completed und Reservationsfreigabe.
- Wiederaufnahme berücksichtigt zusätzliche Operationen, Bibliotheksgenerationen, Retention, technische Placeholder und unabhängige Kataloghistorie.
- Erneut prüfen kann einen qualifizierten eigenen technischen Start fortsetzen; keine Umdeutung als Reset oder Verlustbestätigung.
- Deutsche/englische Fehlermeldungen enthalten betroffenen Pfad und technische Ursache. Bestehende Ordnerverlust-/Ersatz-/Wiederimportverträge bleiben erhalten.

Keine produktive Upgradefreigabe. Native TrueNAS-ACL-Abnahme, private administrative Voraussetzungen und kontrollierte Übernahme sind verbindliche Gates. Es wurde durch die Implementierung kein NAS verändert und kein Image veröffentlicht.
