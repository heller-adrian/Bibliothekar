# Bestandsübernahme mit Bibliothekar 1.0.1

Für den ersten Durchlauf eignen sich eine getrennte Installation und eine kleine synthetische Sammlung. Verwende den Image-Digest aus der GitHub-Vorabveröffentlichung. Bewahre für einen Wechsel zurück zu 1.0.0 den damaligen Stand der Bibliotheksdatenbanken und der globalen Registry separat auf.

## Einrichten und inventarisieren

1. Führe die Sammlung unter einem gemeinsamen Quellordner zusammen. Lege diesen Quellordner und das Zielarchiv in getrennte Ordner **desselben ZFS-Datasets**. Zwei Datasets im selben Pool reichen nicht. Liegt die Sammlung anderswo, kopiere sie selbst vor Beginn auf das Dataset des Zielarchivs.
2. Binde die Sammlung unter `/sources/nas` und das Archiv schreibgeschützt in den Container ein. Für die Quelle kannst du [compose.nas-source.yaml](../compose.nas-source.yaml) und `BIBLIOTHEKAR_NAS_SOURCE_DIR` verwenden. Für den Skriptweg braucht Bibliothekar zusätzlich dauerhaft eingebundenes AppData.
3. Lege bei der Ersteinrichtung deine Hauptbibliothek an. Wähle **Bestehende Sammlung übernehmen** und gib den gemeinsamen Quellordner an. Der Ordnerbrowser öffnet die geeignete NAS-Quelle, sofern sie eingebunden ist. Bibliothekar prüft die tatsächlichen Einbindungen und zeigt das gemeinsame ZFS-Dataset am Quellordner an. Überschneidungen mit dem Zielarchiv und weitere Mounts innerhalb der gewählten Ordner blockieren den Start. Mit **Mit einer leeren Bibliothek beginnen** schließt du die Einrichtung ohne Übernahme ab.
4. Starte die Inventur. Bibliothekar liest auch verschachtelte Unterordner und gruppiert erkannte Aufnahmen anhand ihrer Aufnahmezeit in Jahre und Tage. Bei großen Sammlungen können das Lesen, die Planung und die Prüfung mehrere Stunden dauern. Du kannst die Inventur pausieren. Bereits gelesene Dateien, Entwürfe und der aktive Auftrag bleiben nach einem Neustart verfügbar.

Für eine spätere Übernahme öffne **Einstellungen → Bibliotheken** und wähle **Bestehende Sammlung übernehmen** in der Zielbibliothek. Schließe vorher geplante oder angewendete Ereignisse, offene Archivänderungen, laufende Importe und Wiederherstellungen ab.

Lasse Quelle und Archiv während der Planung unverändert. Der Assistent öffnet sich auch bei direktem Aufruf einer anderen Bibliothekar-Seite. Die regulären Arbeitsbereiche sind bis zum Abschluss gesperrt. Solange du die Durchführung noch nicht bestätigt hast, kannst du **Änderungen verwerfen**. Bei der Ersteinrichtung kannst du danach mit einer leeren Bibliothek beginnen.

## Ereignisse und Prüffälle planen

- Wähle einzelne Aufnahmetage per Klick und einen Bereich mit Umschalt. Wähle **+ Ereignis** oder **+ Sammelordner ohne Ereignis**. Der Editor übernimmt die ausgewählten Tage. Du kannst auch ohne Auswahl beginnen. Unterereignisse legst du im Editor eines Hauptereignisses an. Bei einem Sammelordner mit Tagen in mehreren Monaten wird je Monat ein Ordner angelegt. Für jedes Ereignis, Unterereignis und jeden Sammelordner kannst du Standardordner, eigene Ordner oder eine flache Ablage wählen.
- Bei einer späteren Übernahme kannst du einen passenden Aufnahmetag wählen und die Aufnahmen mit **Zu bestehendem Ereignis hinzufügen** dem bereits archivierten Ereignis zuordnen. Bibliothekar verwendet die gespeicherten Zeitgrenzen und Ordner. Aufnahmen außerhalb der geplanten Zeiträume erscheinen als Prüffälle.
- Öffne die Prüffallliste, um widersprüchliche oder fehlende Aufnahmezeiten und betroffene Familien zu sehen. Ungeklärte Familien bleiben ausgenommen. Mit **Zur Metadatenkorrektur kopieren** kannst du eine vollständige Familie nach General kopieren. Dafür benötigt der Workspace zusätzlichen Speicherplatz. Die Originale bleiben an der Quelle. Die geprüften Arbeitskopien bleiben auch beim Verwerfen des Auftrags erhalten und stehen später für die normale Metadatenkorrektur bereit.
- Alle gespeicherten Ereignisse und Sammelordner fließen in den Verschiebeplan ein. Noch nicht zugeordnete Familien erscheinen in der Planung und in der Prüffallliste. Ohne Zuordnung bleiben sie an der Quelle. Pro Auftrag sind bis zu 2.000 Planobjekte möglich. Bei größeren Archiven kannst du zeitlich getrennte Teilbestände nacheinander übernehmen. Die Vorschau zeigt Zielordner, Dateien, Datenmenge und das nachgewiesene Dataset. Doppelte vollständige Familien werden ausgewiesen und bleiben an der Quelle. Bei Zielkonflikten kannst du im Entwurf einen anderen Namen für die gesamte Familie wählen oder die Familie auslassen.
- Bereite die Ereignisdokumente vor. Wähle die Durchführungsmethode und bestätige den aktuellen Plan ausdrücklich. Danach bleibt der Plan eingefroren. Vor der Ausführung empfiehlt sich ein ZFS-Snapshot oder eine andere geeignete Sicherung. Sie ist freiwillig.

## Manuell über SMB durchführen

1. Lade das Ordnergerüst, den Verschiebeplan und die Ereignisdokumente herunter. Die Pfade in der Vorschau sind Containerpfade. Ordne sie deinen SMB-Pfaden zu. Verwende eine Freigabe und ein Werkzeug, das ein echtes Umbenennen innerhalb desselben Dateisystems ausführt. Kopieren mit anschließendem Löschen verändert die Dateiidentität und besteht die Prüfung nicht.
2. Stelle die vorgesehenen Ordner bereit und verschiebe ausschließlich die freigegebenen Dateien. Sammelanweisungen ersetzen die jeweiligen Einzelschritte. Lasse dabei den vorgesehenen Zielordner frei und prüfe vorab, dass sich der ganze Quellordner seit der Inventur nicht verändert hat.
3. Sichere bei einer Erweiterung die bisherigen Ereignisdokumente und lege die vorbereiteten `event.json` an den vorgesehenen Archivpfaden ab. Wähle **Archiv prüfen**, wenn die freigegebenen Schritte erledigt sind.

## Skript in der TrueNAS-Shell ausführen

1. Wähle **Skript vorbereiten**. Bibliothekar legt das Paket unter `/appdata/legacy-adoption/<Auftrags-ID>/` ab.
2. Kopiere den Prüfbefehl in die TrueNAS-Shell. Er liest die Docker-Einbindungen, prüft das gemeinsame Dataset und speichert den Nachweis im Paket. Wähle danach **Hostnachweis einlesen**. Falls Docker die Einbindungen nicht eindeutig zuordnen kann, verwende die manuelle Hostpfadprüfung in den erweiterten Details. Die Prüfung verschiebt keine Medien.
3. Bestätige den Plan. Wähle **Skriptbefehl bereitstellen** und starte den angezeigten Befehl selbst in der TrueNAS-Shell. Verwende ein Konto mit Zugriff auf das private AppData-Paket und den für die geplanten Umbenennungen nötigen Rechten. Das Skript prüft die Zuordnung erneut, überschreibt keine Zieldateien und protokolliert seine Schritte.
4. Der Browser kann während der Ausführung geschlossen bleiben. Bei einer Unterbrechung prüfe den Status im Assistenten. Der freigegebene Befehl kann die noch offenen Schritte anhand des Journals fortsetzen. Lasse währenddessen manuelle Dateioperationen aus.
5. Sobald das Skript fertig ist, wähle **Archiv unabhängig prüfen**. Der Skriptstatus allein reicht für die Registrierung nicht aus.

## Abschließen oder kontrolliert zurücknehmen

Wähle nach erfolgreicher Archivprüfung **Übernahme registrieren**. Bibliothekar prüft Zielpfade, ursprüngliche Dateiidentitäten, SHA-256, den vorhandenen Archivbestand und die Ereignisdokumente erneut. Danach gelten die normalen Funktionen für Archivänderungen.

Vor der Registrierung kannst du **Kontrollierte Wiederherstellung starten**. Im manuellen Modus bringst du die Dateien anhand des Rückwegs an ihre ursprünglichen Pfade und stellst frühere Ereignisdokumente wieder her. Entferne nur Ereignisdokumente, die dieser Auftrag neu bereitgestellt hat. Im Skriptmodus startet der angezeigte Rücknahmebefehl die protokollierte Umkehrung. Der Assistent beendet den Auftrag erst, wenn er die ursprüngliche Anordnung und die Dateiintegrität unabhängig nachgewiesen hat. Bewahre das AppData-Paket und sein Journal für die Wiederaufnahme auf. Wenn Pfade, Rechte oder das Paket selbst verändert wurden, stelle die nachgewiesenen Einbindungen und den ursprünglichen Paketstand wieder her, bevor du die Rücknahme fortsetzt.


## Umstieg von RC1

Bei bestehenden Installationen bleibt die normale Oberfläche nach dem Update verfügbar. Einen bereits aktiven RC1-Auftrag zeigt Bibliothekar mit den gespeicherten Nachweisen an. Verwirf einen unbestätigten Entwurf oder nimm eine bestätigte Durchführung kontrolliert zurück. Hat die Datenbankregistrierung bereits begonnen, kannst du ihren Abschluss über denselben Plan wiederholen. Bewahre dabei die Originalpfade, das Journal und die Datenbanken auf.
