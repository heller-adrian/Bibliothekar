# Bibliothekar 0.53.1 – Testnotizen und Wiederherstellung

Basis: patch/0.53.0, Commit c9332d5073e53bc5633c620f761adc124b8c1bf9.

## Neue Bedienung
- „Physical actual inventory“ bleibt als einzige Zielstrukturvorschau. Nur wenn physische und gespeicherte Layouts differieren, erscheint der begrenzte Abweichungshinweis.
- Die globale Aufgabenansicht verwendet die tatsächlich ausgewählte Bibliothek. Angewendete, nicht archivierte Ereignisse erhalten eine Archivierungsaufgabe.
- Das Dialogfenster für manuelle Ereignisänderungen bietet „Änderungen rückgängig machen“. Nur überprüfbare Applied-Änderungen werden automatisch zurückgeführt. Für das read-only Archiv erscheinen manuelle Rückführungsschritte; das Archiv wird niemals beschrieben.
- Papierkorb ohne Auswahl: „Alle wiederherstellen“ und „Gesamten Papierkorb leeren“. Mit Auswahl: „Auswahl wiederherstellen“ und „Auswahl leeren“.

## Bekannte und unbekannte Papierkorbdateien
- Katalogisierte, freie Dateien behalten ihre bisherige Provenienz und werden ohne Überschreiben in den zentralen Tagesbestand zurückgeführt.
- Nicht katalogisierte Dateien werden in einem vom Papierkorb getrennten, SHA-256-geprüften Zwischenbestand abgelegt. Ein versteckter „trash_import“-Hintergrundauftrag verarbeitet sie mit der bestehenden regulären Import-Pipeline. Nur erfolgreich importierte und überprüfte Originaldateien werden aus dem Papierkorb entfernt. Bei Importabbruch bleiben die Originaldateien im Papierkorb.
- Betriebssystemdateien wie .DS_Store werden nicht als Kameraaufnahmen eingespielt. Sie können mit der selektiven Löschfunktion explizit gelöscht werden.
- Die neuen Herkunftssicherungen erscheinen im Sicherungsfilter, nicht im Import & Review-Verlauf. Ein bereits bekanntes archiviertes Original mit weiterhin aktiver Ereigniszuordnung wird nicht stillschweigend von seinem Ereignis gelöst. Hier ist der sichere Ereignisworkflow notwendig.

## Nach Installation manuell abnehmen
1. Papierkorb: eine katalogisierte freie Datei auswählen und wiederherstellen, übrigen Bestand prüfen.
2. Eine nicht katalogisierte JPG mit Aufnahmedatum wiederherstellen, Hintergrundauftrag abwarten, Tagesbestand und Sicherungsfilter prüfen.
3. Eine unbekannte JPG ohne Aufnahmedatum prüfen: Sie muss den üblichen Metadaten-Prüfweg nutzen.
4. Zwei Dateien aus dem Papierkorb löschen, nicht ausgewählte Dateien und Ordner unverändert prüfen.
5. Applied-Ereignisordner manuell ändern, vor und nach Reload Vorschau und Aufgabe prüfen, Undo anwenden.
6. Bereits bekanntes archiviertes Ereignis nur lesend prüfen. Keine Dateien im Kamerarchiv durch Bibliothekar ändern.
7. Deutsche und englische Einstellung mit Dateinamen, Bestätigungen, Papierkorbfehlern und Aufgaben prüfen.

**Keine automatische Freigabe für produktive Dateisystemoperationen:** Das CI prüft isolierte Testbestände; ein menschlicher NAS-Abnahmetest ist Voraussetzung für die produktive Nutzung.
