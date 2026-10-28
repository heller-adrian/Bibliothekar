# RC14 Fortschritt

Basis: veröffentlichter RC13-Tag 1f59167e3bfcd38928f0ad32e20d88910a15d53a;
Branch release/v1.0.0-rc.14. Vier Paketunterlagen und alle 17 Originalbilder
vollständig gelesen. Keine NAS-Verbindung oder -Änderung.

Reproduziert: central_stock_reconcile hält den SQLite-WAL-Writer während
SHA-256-Dateiarbeit; deterministischer konkurrierender Writer scheitert im
unveränderten RC13 mit database is locked. Konkreter historischer NAS-Auslöser
bleibt ohne Trace offen. Hashing vor Writer verlagert, SQL-/FS-Snapshots werden
vor Änderungen revalidiert. Weitere Arbeit: nachweisgebundene Stagingfortsetzung,
physische Zähler, sicherer Bibliothekslebenszyklus, UI und vollständige Abnahme.
Budgetziel zunächst 6, maximal 10 Prozentpunkte des Wochenkontingents ab 16 %.

RC14 Implementierung auf 087509ed, Frontendkorrektur e6fc1292. Lokales Gate
mit 53 Backendfällen bestanden; zusätzlicher HTTP-Gegenversuch für die weiterhin
sichtbare Bibliotheksliste bei Identitätsfehler ergänzt. Chromium: 44 bestehende
Fälle und 147 RC14-Lokalisierungs-/Badgefälle lokal bestanden. Linuxlauf
40718962941: Browser bestanden; Backendgate 82 PASS, 1 Testzeitlimit beim NEUEN
3892-Dateien-Fall. Dessen 90-Sekunden-Grenze war für mehrfaches Hash-/Inode-/
fsync-Prüfen unter vollständigem Dateizugriffsaudit zu kurz. Nur dieser neue
Größenfall erhält 300 Sekunden; alle bestehenden Sicherheits-/Recoveryfristen
bleiben bestehen. Weitere echte Gegenprobe: fehlgeschlagene Veröffentlichung
wird auch bei bereits geschriebenen SQL-Zielpfaden nicht als Dateiverlust
reconciled. Open-Tasks-Filter in beiden SQL-Zählern umgesetzt.

Nächster Schritt: korrigiertes Linuxgate, vollständige acht Backendgruppen,
Chromium und Original-Supervisor-Container einschließlich echtem RC13-SIGKILL
nach Journal / nach drei Renames, HTTP-Fortsetzung, Entfernung und Folder Import.
Keine Freigabe bisher. Native TrueNAS-Prüfung weiterhin NOT_RUN. Nutzer hat
Budgetobergrenze ausdrücklich auf 29 % Wochenverbrauch erweitert.
