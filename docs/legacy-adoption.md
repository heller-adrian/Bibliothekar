# Bestandsübernahme mit Bibliothekar 1.0.1

Für den ersten Durchlauf eignen sich eine getrennte Installation und eine kleine synthetische Sammlung. Verwende den Image-Digest aus der GitHub-Vorabveröffentlichung. Bewahre für einen Wechsel zurück zu 1.0.0 den damaligen Stand der Bibliotheksdatenbanken und der globalen Registry separat auf.

## Einrichten und inventarisieren

1. Führe die Sammlung unter einem gemeinsamen Quellordner zusammen. Lege diesen Quellordner und das Zielarchiv in getrennte Ordner **desselben ZFS-Datasets**. Zwei Datasets im selben Pool reichen nicht. Liegt die Sammlung anderswo, kopiere sie selbst vor Beginn auf das Dataset des Zielarchivs.
2. Binde die Sammlung unter `/sources/nas` und das Archiv schreibgeschützt in den Container ein. Für die Quelle kannst du [compose.nas-source.yaml](../compose.nas-source.yaml) und `BIBLIOTHEKAR_NAS_SOURCE_DIR` verwenden. Für den Skriptweg braucht Bibliothekar zusätzlich dauerhaft eingebundenes AppData.
3. Lege bei der Ersteinrichtung deine Hauptbibliothek an. Wähle **Bestehende Sammlung übernehmen** und gib den gemeinsamen Quellordner an. Bibliothekar prüft die tatsächlichen Einbindungen. Überschneidungen mit dem Zielarchiv und weitere Mounts innerhalb der gewählten Ordner blockieren den Start. Mit **Mit einer leeren Bibliothek beginnen** schließt du die Einrichtung ohne Übernahme ab.
4. Starte die Inventur. Bibliothekar liest auch verschachtelte Unterordner und gruppiert erkannte Aufnahmen anhand ihrer Aufnahmezeit in Jahre und Tage. Bei großen Sammlungen können das Lesen, die Planung und die Prüfung mehrere Stunden dauern. Du kannst die Inventur pausieren. Bereits gelesene Dateien, Entwürfe und der aktive Auftrag bleiben nach einem Neustart verfügbar.

Lasse Quelle und Archiv während der Planung unverändert. Der Assistent öffnet sich auch bei direktem Aufruf einer anderen Bibliothekar-Seite. Die regulären Arbeitsbereiche sind bis zum Abschluss gesperrt. Solange du die Durchführung noch nicht bestätigt hast, kannst du **Änderungen verwerfen** und anschließend ausdrücklich mit einer leeren Bibliothek beginnen.

## Ereignisse und Prüffälle planen

- Wähle einzelne Aufnahmetage per Klick und einen Bereich mit Umschalt. Mit Plus kannst du auch ohne vorherige Auswahl Ereignisse, Unterereignisse und Sammelordner planen. Für jedes Ereignis, Unterereignis und jeden Sammelordner kannst du Standardordner, eigene Ordner oder eine flache Ablage wählen.
- Öffne die Prüffallliste, um widersprüchliche oder fehlende Aufnahmezeiten und betroffene Familien zu sehen. Ungeklärte Familien bleiben ausgenommen. Mit **Zur Metadatenkorrektur kopieren** kannst du eine vollständige Familie nach General kopieren. Dafür benötigt der Workspace zusätzlichen Speicherplatz. Die Originale bleiben an der Quelle. Die geprüften Arbeitskopien bleiben auch beim Verwerfen des Auftrags erhalten und stehen später für die normale Metadatenkorrektur bereit.
- Speichere den Entwurf und erstelle den Verschiebeplan. Die Vorschau zeigt Zielordner, Dateien, Datenmenge und das nachgewiesene Dataset. Doppelte vollständige Familien werden ausgewiesen und bleiben an der Quelle. Bei Zielkonflikten kannst du im Entwurf einen anderen Namen für die gesamte Familie wählen oder die Familie auslassen.
- Bereite die Ereignisdokumente vor. Wähle die Durchführungsmethode und bestätige den aktuellen Plan ausdrücklich. Danach bleibt der Plan eingefroren. Vor der Ausführung empfiehlt sich ein ZFS-Snapshot oder eine andere geeignete Sicherung. Sie ist freiwillig.

## Manuell über SMB durchführen

1. Lade das Ordnergerüst, den Verschiebeplan und die Ereignisdokumente herunter. Die Pfade in der Vorschau sind Containerpfade. Ordne sie deinen SMB-Pfaden zu. Verwende eine Freigabe und ein Werkzeug, das ein echtes Umbenennen innerhalb desselben Dateisystems ausführt. Kopieren mit anschließendem Löschen verändert die Dateiidentität und besteht die Prüfung nicht.
2. Stelle die vorgesehenen Ordner bereit und verschiebe ausschließlich die freigegebenen Dateien. Sammelanweisungen ersetzen die jeweiligen Einzelschritte. Lasse dabei den vorgesehenen Zielordner frei und prüfe vorab, dass sich der ganze Quellordner seit der Inventur nicht verändert hat.
3. Lege die vorbereiteten `event.json` an den vorgesehenen Archivpfaden ab. Wähle **Archiv prüfen**, wenn die freigegebenen Schritte erledigt sind.

## Skript in der TrueNAS-Shell ausführen

1. Gib die tatsächlichen absoluten TrueNAS-Pfade für AppData, Quelle und Zielarchiv an. Verwende für Quelle und Archiv die nativen Pfade innerhalb desselben ZFS-Mounts. Containerpfade wie `/appdata` und `/main-library` sind in der TrueNAS-Shell nur gültig, wenn sie tatsächlich dieselben Verzeichnisse bezeichnen.
2. Kopiere den Prüfungsbefehl in die TrueNAS-Shell und lies anschließend den Hostnachweis im Assistenten ein. Diese Prüfung verschiebt keine Medien. Du kannst beide Python-Dateien im Assistenten einsehen.
3. Bestätige den Plan. Wähle **Skriptbefehl bereitstellen** und starte den angezeigten Befehl selbst in der TrueNAS-Shell. Verwende ein Konto mit Zugriff auf das private AppData-Paket und den für die geplanten Umbenennungen nötigen Rechten. Das Skript prüft die Zuordnung erneut, überschreibt keine Zieldateien und protokolliert seine Schritte.
4. Der Browser kann während der Ausführung geschlossen bleiben. Bei einer Unterbrechung prüfe den Status im Assistenten. Der freigegebene Befehl kann die noch offenen Schritte anhand des Journals fortsetzen. Lasse währenddessen manuelle Dateioperationen aus.
5. Sobald das Skript fertig ist, wähle **Archiv unabhängig prüfen**. Der Skriptstatus allein reicht für die Registrierung nicht aus.

## Abschließen oder kontrolliert zurücknehmen

Wähle nach erfolgreicher Archivprüfung **Übernahme registrieren**. Bibliothekar prüft Zielpfade, ursprüngliche Dateiidentitäten, SHA-256, den vorhandenen Archivbestand und die Ereignisdokumente erneut. Danach gelten die normalen Funktionen für Archivänderungen.

Vor der Registrierung kannst du **Kontrollierte Wiederherstellung starten**. Im manuellen Modus bringst du die Dateien anhand des Rückwegs an ihre ursprünglichen Pfade und stellst frühere Ereignisdokumente wieder her. Entferne nur Ereignisdokumente, die dieser Auftrag neu bereitgestellt hat. Im Skriptmodus startet der angezeigte Rücknahmebefehl die protokollierte Umkehrung. Der Assistent beendet den Auftrag erst, wenn er die ursprüngliche Anordnung und die Dateiintegrität unabhängig nachgewiesen hat. Bewahre das AppData-Paket und sein Journal für die Wiederaufnahme auf. Wenn Pfade, Rechte oder das Paket selbst verändert wurden, stelle die nachgewiesenen Einbindungen und den ursprünglichen Paketstand wieder her, bevor du die Rücknahme fortsetzt.


## Umstieg von RC1

Bei bestehenden Installationen bleibt die normale Oberfläche nach dem Update verfügbar. Einen bereits aktiven RC1-Auftrag zeigt Bibliothekar mit den gespeicherten Nachweisen an. Verwirf einen unbestätigten Entwurf oder nimm eine bestätigte Durchführung kontrolliert zurück. Hat die Datenbankregistrierung bereits begonnen, kannst du ihren Abschluss über denselben Plan wiederholen. Bewahre dabei die Originalpfade, das Journal und die Datenbanken auf.
