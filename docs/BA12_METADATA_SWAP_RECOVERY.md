# BA-12: Crash-sicherer Austausch von Metadaten-Dateien

**Entwicklungsstand:** Bibliothekar 0.50.0 (Audit-Branch; keine stabile Veröffentlichung).

## Ausgangsrisiko

Bei Metadatenkorrekturen mit mehreren Dateifamilienmitgliedern wurde bisher
`Original → .*-before-*` und anschließend `Korrigierte Arbeitsdatei → Original`
ausgeführt. Ein Prozessabbruch zwischen diesen Dateisystemoperationen ließ das
Original kurzfristig fehlen. Die anschließende Ausnahmebehandlung konnte nach
einem harten Prozessabbruch nicht mehr ausgeführt werden. Dasselbe betraf die
physische Reintegration aus `Ohne_Datum` mit zusätzlichem Zielpfad.

## Umsetzung

`app/metadata_swap_recovery.py` verwaltet einen dauerhaften, atomar
geschriebenen und mit `fsync` bestätigten Journalbestand unter
`<Metadatenstamm>/.swap-journals/`.

Das Journal wird **vor dem ersten physischen Austausch** gespeichert und hält
für jede Datei fest:

- ursprünglichen und geplanten Dateipfad;
- eindeutig bestimmte Pfade der Sicherheitskopie und der vorbereiteten Datei;
- SHA-256 des Originals und der korrigierten Datei;
- für Bibliothekskorrekturen die betroffene SQLite-Datenbank, Familien- und Datei-ID;
- den Umschaltzustand `prepared` oder `committed`.

**Korrektur im Bereich „Ohne Datum“:** Die Änderung von
`files.sha256_current` und Aufnahmedatum ist die SQLite-Commit-Grenze. Vor
dieser Grenze wird ein unterbrochener Austausch vollständig zurückgenommen;
danach werden die korrigierten Dateien erhalten und die alten Sicherheitskopien
nach Inhaltsprüfung entsorgt. Ein unterbrochener Metadatenauftrag wird aus dem
Journal abgeschlossen oder explizit als blockiert markiert.

**Wiedereinsortierung:** Der in SQLite bestätigte neue
`files.current_relative_path` und der korrigierte SHA-256 bestimmen, ob zur
Quelle zurückgerollt oder das neue Ziel beibehalten wird. Auch Abstürze
zwischen `Original → Sicherheitskopie`, `Eingang → Original` und
`Original → Ziel` sind abgedeckt.

**Mehrfachkorrektur:** Ohne eigene SQLite-Transaktion ist das fsync-gesicherte
`committed`-Journal die Commit-Grenze. Vor ihr werden alle Dateien
zurückgesetzt, danach nur noch die verifizierten Sicherheitskopien bereinigt.

## Sicherheitsregeln

1. Vor Änderungen prüft die Wiederherstellung alle vorhandenen Originale,
   Sicherheitskopien, Zwischendateien und Zielpfade gegen ihre Hashwerte.
2. Fehlen nachweislich erforderliche Originalbytes oder existieren
   widersprüchliche beziehungsweise fremde Dateiinhalte, erfolgt **keine**
   automatische Löschung oder Überschreibung. Journal und Dateien bleiben
   zur Prüfung erhalten.
3. Beim Anwendungsstart werden offene Journale vor Beginn der
   Hintergrund-Worker bearbeitet. Eine nicht eindeutig wiederherstellbare
   Operation blockiert die Freigabe des Arbeitszustands.
4. Weitere Metadatenkorrekturen werden gesperrt, solange ein nicht
   erledigtes Journal im Metadatenstamm vorhanden ist.
5. Originalbilder werden nicht zur Fehlerbehandlung aus Bibliotheken
   verschoben oder umbenannt, die nicht im Journal aufgeführt sind.

## Testnachweise und Grenzen

`tests/backend/test_0500_metadata_swap_recovery.py` verwendet ausschließlich
isolierte synthetische Dateien und SQLite-Tabellen. Separate Prozesse werden
unmittelbar nach physischen Swap-Schritten, zwischen mehreren
Familienmitgliedern, nach dem DB-Commit und nach der Journal-Commit-Markierung
beendet. Auch manipulierte Dateien und nicht freigegebene SQLite-Pfade werden
getestet. Die komplette Backend-Suite und der Archiv-Container-Harness sind
zusätzliche Release-Gates.

**Verbleibende Abnahme:** Eine manuelle Ende-zu-Ende-Prüfung auf TrueNAS mit
synthetischen Testdaten, Mehrbibliotheksinstallation, Dateisystemfehlern und
einem realen Wiederanlauf ist für den Stable-Release erforderlich. Ältere
unprotokollierte versteckte Zwischen-/Backup-Dateien werden nicht
automatisch gelöscht; sie benötigen eine separate Bestandsprüfung. Dieser
BA-12-Fix ist kein Ersatz für BA-03 (API-Zugriffsschutz) und löst nicht die
noch offene TrueNAS-Discover-Berechtigungsfrage des SD-Helpers.
