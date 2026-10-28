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
