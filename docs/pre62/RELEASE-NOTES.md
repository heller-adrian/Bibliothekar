# Bibliothekar 1.0.0-pre.6.2 (Vorabversion)

**Geprüfter Quellstand:** Weiterentwicklung von `1.0.0-pre.6.1` mit der Sicherheitskorrektur `694d4cedeca9b6efa7b64cfad574af10bad0bbc3`. Die ursprüngliche Veröffentlichung `pre.6.1` bleibt unverändert.

## Änderung gegenüber pre.6.1

- **Schutz der Bestätigungspflicht bei manuellen Dateiumbenennungen:** Bei einer gleichzeitig beobachteten Änderung an der Ereignis-Ordnerstruktur kann eine noch offene Aufgabe zur Dateiumbenennung nicht mehr durch Annahme der Strukturänderung unbeabsichtigt umgangen werden. Der Strukturvorgang bleibt blockiert, bis die Umbenennung ausdrücklich bestätigt oder rückgängig gemacht wurde.

## Enthaltene Funktionen aus pre.6.1

- Normale Kameraaufnahmen behalten das Format `JJJJMMTT_HHMMSS_Kamera.JPG`, ohne Zusatz.
- Nur bei tatsächlichen Namenskollisionen derselben Kamera und Sekunde erhalten neu importierte Dateien drei **echte Millisekundenstellen**, z. B. `20260719_171137425_Fuji-X-E5.JPG`.
- Fehlt eine verlässlich nachgewiesene Untersekunde, wird die eindeutige `_Burst_001`-Nummerierung verwendet. Keine Millisekunden werden erfunden.
- Bereits importierte und archivierte Medien bleiben unangetastet; auch ein späterer Import benennt sie nicht um.
- RAW/JPG/XMP werden als eine Aufnahmefamilie behandelt, soweit die Medienidentität eindeutig ist. Unvereinbare EXIF-Zeitangaben bleiben prüfpflichtig.
- Manuelle Finder-/SMB-Dateiumbenennungen sind unter **Aufgaben** mit **Übernehmen** oder **Rückgängig machen** zu bearbeiten. Übernahme und Wiederherstellung sind durch SHA-256-/Größen- und Überschreibschutz gesichert.

## Verwendung und Einschränkungen

Nur als Vorabversion für die TrueNAS-Testinstallation. Kameraarchive bleiben für Bibliothekar schreibgeschützt. Die native TrueNAS-Abnahme nach einem kontrollierten Clean Slate steht noch aus. Ein erfolgreiches CI-Ergebnis ersetzt keine Testabnahme auf dem konkreten NAS.

Die stabilen Releases, frühere Vorabversionen und `latest` werden nicht verändert.
