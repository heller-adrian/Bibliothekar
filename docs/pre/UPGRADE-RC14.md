# RC14 → 1.0.0-pre

**Noch nicht installieren: Kandidat ohne Veröffentlichung.** Erst nach grüner
vollständiger Abnahme, genauer Commitprüfung und ausdrücklicher Freigabe wird
in einem eigenen Schritt ein unveränderliches Image bereitgestellt.

1. App kontrolliert stoppen. Appdaten und Workspace zusammen konsistent sichern
   (z. B. abgestimmte Dataset-Snapshots im gestoppten Zustand). Keine SQLite-,
   WAL-/SHM-, F14- oder Journaldateien einzeln löschen oder ersetzen.
2. Bisherige Mounts, Bibliotheksnamen, Containerpfade, Archiv-RO und UID/GID568
   beibehalten. Bestehende Verzeichnisse werden nicht umbenannt. Kein Clean Slate.
3. Später ausschließlich das freigegebene Image samt geprüftem Digest wechseln.
   Der Kandidat benötigt keine manuelle Datenbankkorrektur und keine neue
   F14-Übernahme. Niemals RC14 und pre parallel auf dieselben RW-Mounts starten.
4. Anmelden, Storage prüfen. In Metadata Correction korrigierte Undated-Familien
   auswählen und einsortieren. Ein bereits abgeschlossener RC14-Korrekturtask kann
   den damals abgeschnittenen Offset nachweisen; Live-Hashes und Tags müssen
   weiterhin exakt passen. Ein unpassender Beleg führt zu einer Diagnose.
5. Bestände und Zieltag kontrollieren, Neustart und zweite Bibliothek prüfen.
   Archive bleiben RO. Bei Sperren Diagnose/Logs sichern, keine Nachweise löschen.

Kein F14-Formatwechsel in diesem Kandidaten. Neue korrigierte Katalogzeiten
bewahren ihren Offset. Ein Rückwechsel nach neuen Schreibvorgängen ist trotzdem
kein pauschal sicherer Rollback: gestoppte vollständige konsistente Sicherung
wiederherstellen oder den Fehler im Kandidaten beheben; keine Einzeldateien mischen.
