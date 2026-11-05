# BA-02 – Löschjournal und Wiederherstellung von Kamera-Sicherungen

Diese Beschreibung gilt für die Entwicklungsfassung 0.50.0. Es werden **nur** vollständig abgeschlossene, nicht von Ereignissen benutzte Kamera-Importsicherungen gelöscht. Die Archivbibliothek und andere Ereignisse sind keine Löschziele.

## Dauerhafter Ablauf

1. Bibliothekar prüft alle freizugebenden Dateipfade, Dateigrößen und SHA-256-Werte.
2. Vor der ersten Verschiebung wird ein per `fsync` gesichertes Manifest in `.deleting-journals/<sha256-der-job-id>.json` geschrieben. Es enthält Sicherungs-ID, Dateien, Prüfsummen, zugehörige Datenbanken und Löschphase.
3. Die Dateien werden **auf demselben Datenträger** nach `.deleting/<job-id>/` verschoben; anschließend werden alle Stagingdateien nochmals geprüft.
4. Zuerst werden die Projektionen in den Nebenbibliotheksdatenbanken entfernt; die Löschung der Sicherung in der Hauptdatenbank ist der **irreversible Commit-Punkt**.
5. Erst danach dürfen Registry-Verknüpfungen und Stagingdateien entfernt werden. Das Journal wird als Letztes gelöscht.

## Neustart und Fehler

- **Hauptdatensatz noch vorhanden:** Bibliothekar prüft vor dem Rückbau die Zugehörigkeit und Integrität aller Dateien, verschiebt sie an ihre Originalorte und stellt fehlende Nebenbibliotheks-Projektionen wieder her. Es werden keine Dateien aus dem Staging gelöscht, solange der Rückbau unvollständig ist.
- **Hauptdatensatz bereits gelöscht:** Bibliothekar darf die Sicherung nicht wiederherstellen. Es vervollständigt ausschließlich die dokumentierte Löschung; das Journal bleibt bis zum Ende vorhanden.
- **Unsichere Zuordnung, beschädigte Dateien, fremde Dateien/Unterordner, geänderte Bibliotheksdatenbanken oder nicht lesbares Journal:** Der automatische Vorgang wird gesperrt, nichts Zweifelhafteres wird gelöscht. Die App meldet eine fehlgeschlagene Wiederherstellung beim Start und startet ihre Worker nicht.
- **Ältere verwaiste `.deleting`-Ordner ohne Journal:** Diese werden **nicht** automatisch gelöscht. Sie benötigen eine gesonderte Bestandsprüfung.

## Sicherheit und Abnahme

Die Wiederherstellung kontrolliert Dateipfade, Dateitypen, Größe, SHA-256, zulässige Unterordner und die aktuelle Bibliotheksregistrierung. Das Journal ist Wiederherstellungsinformation, kein zusätzliches Backup der Fotos.

Die synthetischen CI-Tests in `tests/backend/test_0500_backup_delete_recovery.py` simulieren Prozessabbrüche beim Staging, vor/nach dem Hauptdatenbank-Commit, während der Löschung und bei gestörtem Rückbau. Hinzu kommen eine zweite Bibliothek, fremde Staginginhalte und geänderte Dateiprüfsummen. Ein Live-Test auf TrueNAS mit **rein synthetischen Daten** bleibt Voraussetzung für einen stabilen Release.
