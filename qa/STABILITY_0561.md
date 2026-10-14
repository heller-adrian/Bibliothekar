# Stabilitätspatch 0.56.1

Ausgangsbasis: `patch/0.56.0`, Commit `dcb11ba6c0a4db8e42fe70bc3ad7e8753c226597`.
Umfang: ausschließlich die vier in Audit Phase 2 reproduzierten Fehler, Versionskennzeichnung und notwendige Test-/CI-Dokumentation. Keine Schema- oder Bestandsmigration.

## Korrekturen

- **F1/F2 – Papierkorb:** prepared-Journal vor dem ersten Dateieingriff; atomarer Austausch ohne vorheriges Unlink; Dateihashes und gezielte Sicherung betroffener Katalogzeilen einschließlich FK-CASCADE/SET-NULL-Abhängigkeiten. Einzelne WAL-Commits werden durch idempotente Kompensation zurückgenommen, ohne unabhängige Katalogänderungen zu überschreiben. Snapshot-Abgleich unter `BEGIN IMMEDIATE`, Datenbankidentität und Schemaabgleich verhindern ungeprüfte Rücksicherung. Eine dauerhafte committed-Markierung erlaubt ausschließlich die Entfernung bekannter, geprüfter Staging-Dateien. Dateisicherung und Verzeichnis-fsync gehen dem Entfernen der Quelle voraus. Prozess-/Thread-Sperre verhindert Recovery eines laufenden Löschauftrags; Startup und Inventar führen Recovery vor Reconciliation aus.
- **F3 – allgemeine Metadaten:** bestehendes Swap-Journal und gesicherte Originalbytes; SQLite-Aufgabenstatus entscheidet zwischen Rückbau und Abschluss. Ein unbestätigter Swap stellt die Originalbytes wieder her und macht den Auftrag erneut ausführbar. Recovery läuft auch beim Startup ohne registrierte Bibliothek vor dem Workerstart.
- **F4 – Stammordner:** ursprüngliche Workspace-Komponenten sowie alte und neue Stammordnereinträge werden vor Dateieingriffen auf Symlinks geprüft. Unaufgelöste Pfade bleiben für Umbenennungen erhalten.

## Reproduktion und Regressionen

Die vier Testkörper einschließlich Assertions aus Phase 2 stehen unverändert in `tests/backend/test_0561_audit_regressions.py`; ausschließlich die optionale Evidenzausgabe wurde für reguläre CI-Ausführung angepasst. Kein XFAIL, keine abgeschwächten Assertions. Vorhandene Teständerungen ersetzen ausschließlich erwartete Versionsstrings 0.56.0 durch 0.56.1.

43 gezielte Fälle: vier Audit-Reproduktionen und 39 zusätzliche Prüfungen. Fehlergrenzen: Staging-Link/Unlink, erster/letzter Datenbankcommit, Journalwechsel/-fsync, Cleanup, Unterbrechung der Recovery selbst, CASCADE/SET NULL, echte Familien-/Dateizuordnungen, fremde/veränderte Bytes, Schema-/Zeilenkonflikte, nicht registrierte Datenbanken, alte Journale, gleichzeitige Recovery, Metadaten-Backup/Swap/Commit/Cleanup sowie rohe Symlink-Komponenten und normale Umbenennung.

Nur in einer frischen isolierten Umgebung mit synthetischen Daten ausführen, Python 3.12, Requirements, pytest, httpx, Node.js und ExifTool:

```sh
pytest -q -o addopts='' tests/backend
```

Die Linux-CI führt die vollständige Suite vor Veröffentlichung aus. Der separate Archiv-Containerharness verwendet ausschließlich seine erzeugten CI-Daten und ein separates Workspace-/Archiv-/DB-Verzeichnis.

## Nachweisgrenzen

Unit-Fehlereinfügungen einschließlich BaseException-Unterbrechungen zeigen den Zustandsübergang und wiederholte Recovery. Sie simulieren keinen physikalischen Stromausfall. Tatsächliche ZFS-/WAL-/fsync-Dauerhaftigkeit, TrueNAS-ACLs und Bind-Mounts, Prozessabbrüche an beliebigen Maschineninstruktionen, konkurrierende externe SMB-Schreibzugriffe und Lasttests bleiben Phase 3 beziehungsweise einer ausdrücklich beauftragten isolierten TrueNAS-Prüfung vorbehalten. EXDEV wird gezielt simuliert.

Bei fremden/veränderten Dateien, Katalogkonflikten oder alten prepared-Journalen ohne Katalogsicherung bleibt der Vorgang sichtbar blockiert; Journal und vorhandene Originale werden erhalten. Bereits vor dem Patch verlorene Katalogdaten lassen sich ohne vorhandene Nachweise nicht automatisch rekonstruieren. Es erfolgt kein pauschales Rücksetzen von Datenbanken.
