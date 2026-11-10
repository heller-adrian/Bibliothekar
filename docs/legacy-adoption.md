# Erste Bestandsübernahme mit Bibliothekar 1.0.1

Teste die Vorabversion mit einer getrennten Installation und einer kleinen synthetischen Sammlung. Verwende für `BIBLIOTHEKAR_IMAGE` den Digest des geprüften Patch-Images aus dem GitHub-Pre-Release. Die Vorabversion migriert die Bibliotheksdatenbanken und die globale Besitzregistry. Bewahre für einen Versionswechsel zurück die Datenbanken aus 1.0.0 separat auf.

## Quelle und Bibliothek auswählen

1. Binde die Sammlung lesend unter `/sources/nas` ein. Für Compose steht [compose.nas-source.yaml](../compose.nas-source.yaml) mit `BIBLIOTHEKAR_NAS_SOURCE_DIR` zur Verfügung. Das Zielarchiv bleibt in Bibliothekar schreibgeschützt. Du benötigst für die manuellen Schritte einen eigenen Schreibzugang, etwa über SMB.
2. Öffne **Einstellungen → Bibliotheken → Bestehende Fotosammlung übernehmen**. Wähle die Zielbibliothek oder richte sie über **Bibliothek einrichten** ein. Wähle dann den Quellordner.
3. Starte die Inventur. Sie erfasst Originalpfade, Metadaten und SHA-256. Beim Pausieren oder Neustart bleiben bereits untersuchte Dateien gespeichert. Eine erneute Inventur liest unveränderte Dateien aus diesem Zwischenstand.

## Ereignisse planen

4. Wähle ein Jahr und einen Tag. Öffne Familien mit **Prüfen** und bestätige die Aufnahmezeit anhand der angezeigten Metadaten oder deiner eigenen Aufzeichnungen. Ein RAW ohne JPEG ist eine reguläre Familie.
5. Wähle ein vorgeschlagenes Archivereignis, um es zu ergänzen, oder lege ein Ereignis mit Zeitraum und optionalen Unterereignissen an. Sammelordner bündeln freie Zeitabschnitte innerhalb eines Monats. Tagesordner und die in der Bibliothek konfigurierte Ordnerstruktur lassen sich für neue Ereignisse verwenden.
6. Speichere den Entwurf und erstelle den Verschiebeplan. Für eine Teilübernahme beschränke den Entwurf auf die gewünschten Zeiträume. Exakte bereits registrierte Dateien erscheinen als Duplikate. Wenn nur ein Teil einer Familie doppelt ist, meldet die Planung den Konflikt zur Prüfung. Bei Zielkollisionen kannst du im Entwurf einen neuen Zielnamen für die ganze Familie festlegen oder die Familie auslassen.

## Dateien manuell verschieben und prüfen

7. Lade das leere ZIP-Ordnergerüst und den JSONL-Verschiebeplan herunter. In der ersten Zeile stehen die eingebundenen Wurzeln. Jede Datei erhält den Quellpfad, das Ziel, die Prüfsumme und den Rückweg. Übersetze bei SMB die angezeigten Containerpfade in deine Freigabepfade. Nutze Sammelanweisungen nur für unveränderte Tagesordner und lass deren jeweilige Zielordner im Gerüst frei.
8. Vor größeren Dateiänderungen wird ein ZFS-Snapshot oder eine andere Sicherung empfohlen. Diese zusätzliche Sicherung ist freiwillig. Bei unklaren Dateisystemgrenzen kann das manuelle Verschieben eine vollständige Kopie über SMB auslösen.
9. Bereite die Ereignisdokumente vor. Lade die früheren Dokumente zur Rücknahme separat herunter. Stelle die neuen `event.json` aus dem ZIP manuell unter den angegebenen Archivpfaden bereit. Verschiebe die geplanten Dateien ohne Überschreiben. Prüfe nach jedem Teil, wenn du die Arbeit unterbrechen möchtest.
10. Wähle **Archiv prüfen** und korrigiere gemeldete Abweichungen. Sobald Medien und Ereignisdokumente geprüft sind, wähle **Übernahme registrieren**. Bibliothekar prüft dabei die Archivdateien erneut und nimmt sie als normale archivierte Dateien auf.

Bei einer Unterbrechung öffnest du den gespeicherten Auftrag erneut. Für eine Rücknahme vor der Registrierung bringst du die Dateien anhand der Rückwege manuell an die Quelle und stellst die vorherigen Ereignisdokumente wieder her. Entferne neue Ereignisdokumente und leere Ordner nur dann, wenn sie zu diesem Auftrag gehören. Öffne anschließend den Plan wieder zur Bearbeitung. Nach der Registrierung gelten die regulären Funktionen für Archivänderungen.
