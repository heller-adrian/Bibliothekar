# Bibliothekar 1.0.0-pre.6.1 (Vorabversion)

Vorabversion auf Basis der geprüften Pre.6-Korrekturen für die TrueNAS-Kamerabibliothek.

## Änderungen

- Normale Aufnahme-Dateinamen bleiben unverändert: `JJJJMMTT_HHMMSS_Kamera.JPG`.
- Nur bei mehreren unterschiedlichen Aufnahmen derselben Kamera innerhalb derselben Sekunde ergänzt der neue Import echte drei Millisekundenstellen: `JJJJMMTT_HHMMSSmmm_Kamera.JPG`.
- Millisekunden werden ausschließlich aus vorhandenen Aufnahme-Metadaten gelesen; ohne verlässliche Untersekunden verwendet Bibliothekar einen ausdrücklich nummerierten `_Burst_001`-Ersatz, keine fiktive Uhrzeit.
- Neue Importe berücksichtigen bereits vorhandene, auch archivierte und bibliotheksübergreifend registrierte Aufnahmen derselben Sekunde. Vorhandene Dateien werden nicht nachträglich umbenannt.
- RAF/JPG/XMP gehören weiter zur selben Aufnahmefamilie; eine eindeutige präzise RAF-Zeit kann von zugehörigen Dateien ohne Untersekunden übernommen werden. Widersprüchliche präzise Angaben bleiben zur Prüfung markiert.
- Manuell im Finder oder über SMB umbenannte Fotos werden nicht still übernommen: Die Aufgabenanzeige bietet ausdrücklich Übernehmen oder Rückgängig machen. SHA-256, Speichergrenzen und Lösch-/Überschreibschutz werden geprüft.
- Die zurücklesende Erkennung kanonischer Export-Dateinamen versteht sowohl Sekunden- als auch Millisekunden-Namen.

## Sicherheit und Einschränkungen

Die Kameraarchive bleiben für Bibliothekar schreibgeschützt. Physische Hardware-/TrueNAS-NFSv4-Prüfungen sowie reale DNG-1.7-Schreibfähigkeit sind mit dieser Vorabversion nicht pauschal freigegeben. Die Aktualisierung einer bestehenden Testinstallation sollte erst nach einem Snapshot und anschließendem Clean Slate mit der vorgesehenen isolierten Testumgebung erfolgen.

`latest` und stabile Veröffentlichungen werden von dieser Vorabversion nicht verändert.
