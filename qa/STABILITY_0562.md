# Wiederanlauf-Stabilität 0.56.2

Basis: `patch/0.56.1`, `8db2a18d9dc2a26a616207cbf33544ef5bd7f38d`.
Umfang: F5–F10 aus Audit Phase 3. Keine neue Fachfunktion und keine Schema-/Bestandsmigration. Die bestehenden Auditberichte und Nachweise bleiben unverändert.

## Korrekturpakete

1. **F5:** Sortier-/Reconcile-Recovery aller registrierten Datenbanken läuft vor Migration, Inventar, Claims und Hintergrundworkern. Uneindeutige Recovery blockiert den Startup. Offene Reconcile-Familien bleiben bis zur bestätigten Nachsortierung am bisherigen IST-Pfad und werden nicht vorzeitig migriert.
2. **F6/F9:** Bekannte Papierkorb-Restores besitzen vor dem ersten Move einen dauerhaften Plan mit SHA-256, ursprünglichen Katalogidentitäten und DB-Inodes. Neustart setzt Dateibewegungen und getrennte DB-Commits idempotent fort. Exception-Rollback vor dem ersten Katalogcommit ist ebenfalls journalisiert. Queuemanifeste behalten die bekannte Auswahl und können nach einem Move erneut vorbereitet werden. Import-Movejournale erfassen vor dem ersten Rename Quelle, Ziel, Größe, SHA-256 und Inode; Verwerfen prüft sämtliche Kandidaten, bevor ausschließlich nachgewiesene Importkopien entfernt werden.
3. **F7:** Ein offener SSD-Freigabeplan liefert die eingefrorenen Erwartungen für bereits entfernte eigene Dateien. Archivprüfung und anschließend die vollständige Freigabe-Verifikation prüfen weiterhin alle erforderlichen Archivkopien mit Größe und SHA-256, bevor weitere SSD-Dateien entfernt werden. Geänderte Archive und unpassende Freigabepläne sperren die Fortsetzung.
4. **F10:** Der lokale Metadatenaufgabenabschluss speichert `projection_pending` in derselben SQLite-Transaktion. Nach jedem Startup werden ausstehende Propagationen in alle registrierten Datenbanken wiederholt; erst danach wird der Marker entfernt. Wiederholungen bearbeiten keine Mediendateien und erzeugen keine doppelten Katalogzeilen. Fehlende Zieldatenbanken bleiben ein Fehler mit erhaltenem Marker.
5. **F8:** Ein Vorbereitungsjournal entsteht vor der Arbeitskopie. Der exklusiv angelegte Dateieintrag wird mit Geräte-/Inodeidentität erfasst. ExifTool schreibt die Arbeitskopie unter Erhalt des Inodes. Erst danach geht dasselbe Journal atomar in den vorhandenen Swap-Plan über. Recovery bereinigt nur nachgewiesene Arbeitskopien bei unverändertem Original; fremde Einträge bleiben mit Journal sichtbar blockiert.

## Regressionen und Ausführung

`tests/backend/test_0562_process_recovery.py` übernimmt alle 65 originalen Phase-3-Fälle einschließlich ihrer Assertions. Angepasst sind ausschließlich die temporäre Testumgebung und der Ort des externen Workers. Die ursprünglichen BLOCKED-Zweige bleiben als Diagnose erhalten; zur Abnahme müssen beide Fälle tatsächlich PASS liefern. Zusätzliche Fälle unterbrechen die neue Restore-, Import-Verwerf-, SSD-, Metadatenvorbereitungs- und Propagations-Recovery wiederholt mit SIGKILL und prüfen fremde Bytes, Inodes und Symlinks. `test_0562_recovery_guards.py` prüft zusätzlich fsync-Fehler nach Unlink und fehlende Propagationsdatenbanken.

Auf einem kurzlebigen Linux-QA-Runner mit Python 3.12 und ExifTool:

```sh
pip install -r requirements.txt pytest httpx
PYTHONPATH=. pytest -q -o addopts='' tests/backend
PYTHONPATH=. pytest -q -o addopts='' tests/backend/test_0562_process_recovery.py
```

Alle Prozessfixtures erzeugen ausschließlich synthetische Medien, SQLite-Datenbanken und Konfigurationen unter pytest-Temporärpfaden. SIGSTOP definiert den Checkpoint; der Teststeuerprozess beendet ausschließlich seine eigene Prozessgruppe mit SIGKILL und prüft Returncode −9. Drei reguläre ASGI-Lifespan-Neustarts prüfen danach Dateihashes, Herkunft, Familien, Claims, Journale sowie SQLite-Integrität/Fremdschlüssel. Python-Exception-Gegenproben werden getrennt gekennzeichnet.

## Grenzen

Der Patch beweist keine physische Stromausfall-/ZFS-/Controller-Dauerhaftigkeit. Prozessabbrüche innerhalb beliebiger nativer SQLite-/ExifTool-Systemaufrufe, konkurrierende externe SMB-Schreiber, mehrere Webprozesse sowie echte TrueNAS-ACL-/Mountbedingungen bleiben für spätere Phasen offen. Ein unterbrochener exklusiver Datei-Create vor der dauerhaften Inodequittung bleibt im Zweifel mit Journal blockiert; unbekannte Dateien werden nicht automatisch gelöscht. Bereits vor dem Patch unjournalisierte Alt-Arbeitskopien werden nicht heuristisch entfernt. Bereits abgeschlossene Alt-Metadatenaufträge ohne neuen Propagationsmarker benötigen bei nachgewiesener Teilpropagation einen gezielten Replay anhand ihrer Auditnachweise; pauschales Überschreiben historischer Bibliotheksprojektionen erfolgt nicht.

Die einmalige SQLite-Leseauffälligkeit aus Phase 3 wird mit ausdrücklich geschlossenen Read-only-Verbindungen und drei frischen Gegenläufen erneut geprüft. Ohne reproduzierbare Korruption wird daraus kein weiterer Produktdefekt abgeleitet. Den verbindlichen Abnahmestand, Commit, Rohlogs und Container-Digest enthält das externe QA-Paket 0.56.2.
