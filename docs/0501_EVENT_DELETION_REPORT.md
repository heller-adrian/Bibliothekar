# Bibliothekar 0.50.1 – Extern gelöschte Ereignisordner

**Basis:** `patch/0.50.0-audit`, Prüfstand 0.50.0. **Ziel:** separates `patch-0.50.1`-Testimage. PR #19 bleibt Draft, `main`, Stable `v0.40.3` und `latest` bleiben unverändert.

## Ausgangsfehler und Reparatur

Der bestehende passive Inventarscanner (`app/live_inventory.py`) konnte gelöschte komplette Ereignisordner nicht als leeren tatsächlichen Bestand erfassen: `scan_event_inventory()` brach vorher mit `Ereignisordner wurde nicht gefunden` ab. Deshalb blieb das bereits seit 0.28.x vorhandene zweifache Löschprüfungssystem in `app/physical_state.py` unerreichbar. Einzelne externe Löschungen und freie Tagesordner besaßen schon entsprechende Mechanismen.

- `scan_event_inventory(allow_missing_root=True)` ist **nur** für die passive Beobachtung erlaubt. Der Standard bleibt strikt (insbesondere bei Archivprüfung, Archiv-Änderungsaufträgen und sonstigen mutierenden Pfaden). Ein nicht erreichbarer Root, falscher Dateityp oder Symlink wird nicht als Löschung akzeptiert.
- Bei angewendeten Ereignissen prüft Bibliothekar **zuerst** die mögliche manuelle Archivübernahme. Ist die Datei dort wiedergefunden, bleibt die bestehende Archiv-Recovery vorrangig.
- Eine tatsächlich fehlende Ereigniswurzel erzeugt ein leeres physisches IST-Inventar. Erst **zwei aufeinanderfolgende Prüfungen** ohne positiven Orts-/Konfliktbefund dürfen vorhandene SQLite-Dateizeilen entfernen. Beim vollständig gelöschten Ereignis erzeugt die bestehende Strukturprüfung den nicht blockierenden Hinweis `event_root_deleted` und bereinigt danach die Ereigniszuordnung.
- Bei **teilweise** entfernten, zuvor mit Kameraoriginalen belegten Unterordnern werden nur die bestätigten fehlenden Dateiidentitäten bereinigt. Die entfernten Ordner werden als `event_directory_deleted` informativ vermerkt und nicht als erforderliche neue Ereignisstruktur-Änderung erzwungen. Quittierte unveränderte Hinweise öffnen sich nach Reload nicht erneut.
- Ein andernorts beobachtetes Foto, ein belegter alternativer Pfad, eine mehrdeutige Position oder eine noch von einem fremden Ereignis beanspruchte Familie wird **nicht** als Löschung übernommen: Die bestehenden Platzierungskonflikte bleiben vorrangig. Bei `archived` wird ausschließlich lesend geprüft.
- Die Benutzer-Quittierung läuft über die bereits existierenden `external_change_notices`; kein neues fachliches Zustandsmodell, keine Datenbankschemamigration, keine Wiederherstellung absichtlich gelöschter Medien.

## Regression und Umfang

`tests/backend/test_0501_external_event_deletion.py` prüft synthetisch vollständige und teilweise gelöschte Ereignisse, angewendet/archiviert, zwei Scans, bestätigte Dateien/Familien/Zahlen, Quittierung und erneute Prüfung, Fehlverschiebung in fremdes Ereignis, umbenannte Ereignisordner mit gültigem portablem `event.json`, unerreichbare Workspace-Wurzel und fremde Zuordnungsansprüche.

Die bestehende Suite umfasst unter anderem: externe gelöschte freie Tagesordner, frühere Archivübernahme, manuell falsch verschobene archivierte Dateien, BA-01/02/03/07/08/09/10/11/12/13. Gesamte GitHub-Actions-QA und der isolierte Archiv-Containertest werden für den endgültigen 0.50.1-Quellstand erneut ausgeführt. Alle Testdateien und Datenbanken sind künstlich und unter Test-Verzeichnissen.

## Bewusste Sicherheitsgrenzen

1. Zwei Beobachtungen ersetzen **keinen** Nachweis einer absichtlichen Löschung. Wird ein Ordner ohne mitgenommenes `event.json` an einen nicht inventarisierten Ort verschoben, ist die Suche eventuell nicht eindeutig. Die eindeutige Wiedererkennung durch `event.json` gilt für die vom Inventarscanner untersuchten benachbarten Ereignisordner. Für unerkannte Sonderwege ist weiterhin eine unabhängige TrueNAS-Praxisabnahme erforderlich.
2. Die Sicherheitsprüfung verlangt eine erreichbare Speicherwurzel; einen fälschlicherweise leer gemounteten, formal erreichbaren Ordner kann die Anwendung nicht in allen Betriebsumgebungen zuverlässig von einem bewussten externen Löschen unterscheiden. Das tatsächliche Mount-/ACL-Verhalten ist separat unter TrueNAS zu prüfen.
3. Der Patch gibt **weder** die Version 1.0.0 **noch** die TrueNAS-Discover-Integration frei. Die offenen Punkte aus `docs/0500_RELEASE_GATE_REPORT.md` gelten weiterhin (TrueNAS, iOS-PWA, BA-10-Fault-Matrix und Discover-Direkt-SD-Rechte).
