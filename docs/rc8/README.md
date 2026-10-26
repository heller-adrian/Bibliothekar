# RC8 – gezielte Abnahme und Veröffentlichung


Freigegebene Basis: `00b40f68f9d515b0d2b8ab4a84a26781986be307`, Tree `1303bceeea4d9c59b93a99db264978eb0ef7894c`.
[Linux-/Containerabschluss](https://github.com/heller-adrian/Bibliothekar/actions/runs/40392556689): 175 unterschiedliche gezielte Linuxfälle PASS, fünf persistente Containerfälle einschließlich Onboarding, Neustart und Sicherheitssperren PASS; 176 App-Dateien geprüft. Dies ist die dokumentierte kombinierte gezielte Abnahme: Der frühere Lauf mit 169 PASS/6 Fixture-FAIL bleibt als Rohbeleg erhalten. Kein neuer vollständiger Backend-Gesamtlauf und keine finale 1.0.0-Gesamtabnahme.

Der RC8-Veröffentlichungslauf prüft die Versionssubstitutionen gegenüber dieser Basis, die betroffenen Linuxfälle, alle fünf persistenten Containerfälle sowie frisches Onboarding, Authentifizierung, sechs Seiten, JavaScript/CSS, Web-UID/GID568:568, SQLite und alle 176 App-Dateien erneut. Das veröffentlichte Image wird per Registry-Digest abgerufen und isoliert geprüft. Einzelresultate, Quellvertrag und SHA256SUMS liegen als Release-Assets bei.

## Grenzen

Native TrueNAS-/ZFS-/NFSv4-, SMB- und Geräteabnahme bleibt offen. Die private Verwaltungsablage vertraut dem vorgesehenen App-/Administratorbereich einschließlich UID568; keine Isolation gegenüber Administratoren oder weiterer Software derselben UID. Die bestehende manuelle NFSv4-ACL-Voraussetzung des SD-Mountbereichs bleibt erforderlich; automatische Katalogbereitstellung ist offen. Akzeptierte F13-/F24-Restrisiken und B12 bleiben unverändert.

RC7→RC8: `UPDATE-RC7-RC8.md` befolgen, ausschließlich das Image ersetzen und den bestehenden gesperrten Zustand zur Prüfung erhalten. Keine Verzeichnisse oder Belege löschen. Konsistente Sicherungen vor dem Update sind erforderlich, da Startup fehlgeschlagene Restores sicher finalisieren kann.
