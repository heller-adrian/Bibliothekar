# Changelog

## 0.47.2 – Kompakter PWA-Seitenkopf und einheitliche untere Navigation (09.10.2026)

- Die installierte Handy-Web-App zieht Seitenüberschriften und Bereichsreiter weiter in Richtung Statusleiste. Safe-Area-Reserve bleibt erhalten; das Nachrücken erfolgt im Dokumentfluss.
- Ein für alle Bereiche gleicher, fest an der Gerätekante verankerter Dock ersetzt widersprüchliche Höhen früherer PWA-Regeln.
- Aufgaben erhält die gelbe runde Zahl als Icon und den Schriftzug darunter; Aufgaben und Hamburger-Menü sind rahmenlos. Symbole der drei Hauptbereiche sind größer, das aktive zusätzlich hervorgehoben.
- Menü- und Aufgaben-Panels sitzen oberhalb des Docks, Scrollflächen behalten einen ausreichenden Sicherheitsabstand.
- Logo V2 und weitere 0.47.1-Funktionen bleiben erhalten, ebenso die Desktopansicht und die normale mobile Website. Keine Datenbankmigration.

## 0.47.1 – Aktualisiertes Bibliothekar-Logo (09.10.2026)

- Das vom Nutzer in `patch/0.47.0` ergänzte `app/bibliothekar-logo-v2.svg` wird in der gemeinsamen Kopfzeile und im Dialog „Über Bibliothekar“ angezeigt.
- Die SVG-Geometrie und Proportionen bleiben unverändert; die v2-Kontur verwendet den vom Nutzer gelieferten Farbwert. Die alte SVG bleibt für Version 0.47.0 vorhanden.
- Auslieferung über `/assets/bibliothekar-logo-v2.svg` mit neuer Cachekennung `v=0.47.1`; dynamischer Bibliotheksname und sämtliche Maße des Headers bleiben unverändert.
- Keine Datenbankmigration, keine Änderungen an PWA-Navigation, Kamera- oder Archivfunktionen.

## 0.47.0 – Platzgewinn und Navigation in der iPhone-Web-App (09.10.2026)

- Nur in der installierten Smartphone-Web-App verschwindet der dunkelblaue Kopf mit der Wortmarke. Import-, Arbeitsbereich-, Archiv- und Unterseitenfarben reichen bis unter die iPhone-Statusleiste.
- Import, Archiv, Papierkorb und weitere Seiten beginnen nach dem oberen Sicherheitsabstand mit ihrer Überschrift; Aufnahmen/Ereignisse und Metadatenkorrektion beginnen mit ihren weiterhin fixierbaren Bereichsreitern.
- Keine künstliche Kopfhöhe mehr im Sticky-System. Desktop und mobile Browserseite behalten ihre bisherigen Header.
- PWA-Navigation unten höher, Icons größer, flexibel verteilte Spalten und vollständig lesbare Beschriftungen auch bei Aufgaben; Menü und Aufgaben-Panels stehen darüber. Inhalte bleiben trotz höherem Dock scrollbar.
- Das Dialogfenster „Über Bibliothekar“ enthält jetzt an Stelle des Texttitels die weiße SVG-Wortmarke auf dunkelblauem Hintergrund; übriger Text bleibt unverändert.
- Keine SQLite-Migration oder Änderungen an Fotoverarbeitungsprozessen.

## 0.46.0 – Neues Bibliothekar-Markenlogo (09.10.2026)

- Das vom Designer bereitgestellte weiße SVG (in Pfade konvertierter Schriftzug mit freigestelltem Symbol) ersetzt das bisherige farbige Symbol und den HTML-Schriftzug in der gemeinsamen Hauptnavigation.
- Die aktuelle Bibliotheksbezeichnung bleibt als eigenes, automatisch wechselndes Textelement unter der Wortmarke im freien SVG-Bereich bestehen.
- Gleiches SVG in Desktop, mobiler Website und iPhone-Web-App; jeweils passende Abmessungen, ohne andere Seitenheader individuell zu verändern.
- Auslieferung über `/assets/bibliothekar-logo.svg` mit SVG-Medientyp und Versionscache; keine externen Fonts oder Rasterbilder erforderlich.
- Keine Datenbankmigration und keine Änderungen des Import-, Sortier- und Archivkerns.

## 0.45.6 – UI-Feinschliff (09.10.2026)

- Der Name der aktuellen Importphase steht rechts oben in der aufgeklappten Importkarte beim Erstellungsdatum, unterhalb der Aktionen; der Phasenbalken behält seinen Fortschrittswert.
- Tages- und Ereigniskarten im Hellmodus zeigen einen Zwischenwert zwischen den Hover-Stärken 0.45.4 und 0.45.5; Dunkelmodus bleibt unverändert.
- In der iPhone-Standalone-Schnellauswahl wackeln nur die Karteninhalte, damit WebKit den oberen Kartenrand während der Animation nicht mehr abschneidet.
- Ausschließlich UI/CSS und Versionstexte; keine Datenbankmigration oder Änderung des Importprozesses.

## 0.45.5 – Sicherer Abbruch und Importkontrolle

- Live-Fortschrittsanzeige mit Phasen-Badge und unabhängigem Gesamtfortschritt.
- Noch zurückhaltendere Hover-Effekte bei Tages-, Prüffall- und Ereigniskarten.
- Begrenzte, nicht hashende Speicher-Vorprüfung vor der Jobannahme; NAS-Stammordner und übergroße oder unüberschaubare Quellen werden früh abgewiesen.
- Tatsächlich verfügbarer Platz am Schreibdataset mit Puffer und Sicherheitsreserve; erneute Prüfung im Worker vor dem Kopieren.
- Dauerhafte, auf einen Auftrag beschränkte Abbruchanforderung; 1-MiB-Unterbrechungspunkte beim Hashen und Kopieren, gezielt beendbarer ExifTool-Kindprozess.
- Nach 15 Sekunden offener Abbruchanforderung Bestätigung zum Eskalieren; keine ungeprüften Löschungen. Rollback entfernt nur von diesem Import nachweislich überführte Zieldateien.
- Neue Regressionstests für Speichergrenzen, Abbrüche großer Dateien, Fremddateischutz und Neustartfestigkeit.
- Keine SQLite-Migration und kein Merge nach main.

## 0.45.4 – UI-Feinschliff und stabiler Importverlauf (08.10.2026)

- „Ausgeblendet“ öffnet sofort; Hintergrundabfragen und veraltete Zwischenstände überschreiben keine neueren Zähler. Ein schnelles SQLite-Count-API verhindert unnötige Sicherungsprüfungen für die reine Anzahl.
- Ausgeklappte Importdetails verwenden keinen überholten Bildspalten-Platzhalter mehr; Datum, Beschreibung und technische Daten sind linksbündig.
- Tages-, Prüffall- und Ereigniskarten reagieren in Hell- und Dunkelmodus dezenter mit einem weichen Ein-/Ausblenden. Die Auswahl bleibt unabhängig; reduzierte Bewegung wird berücksichtigt.
- Unbenutzte Statushöhe unter „Ereignisse“ entfernt, damit Kennzahlen unmittelbar unter dem Seitentitel stehen.
- Seitentitel und Bereichstitel zeigen ihre bestehenden Hilfen nur noch per Klick/Tastatur an, als schwebende Hinweise ohne Layoutverschiebung.
- Reine UI-/Anzeigeänderungen; keine Migration und keine Änderung des Kamera-, Ereignis- oder Archiv-Workflows.

## 0.45.3 – Importkartendetails, mobile Aktionen und Ereignissuche (08.10.2026)

- Importkarten: Details ohne doppelten Namen oder Status; technische Angaben ohne leere Vorschau-Spalte, Hellmodus-Farben korrigiert.
- Handy-Website und Web-App: Aktionen unter der Importkarte in einer gemeinsamen Zeile, auch wenn Details aufgeklappt sind.
- „Ausgeblendet“: reduzierte, mittig beschriftete Schaltfläche ohne Dekorationssymbole.
- Tagesordner und Ereignisse: dezente Hoverfarben in beiden Themes; mehr unterer Freiraum für den Desktop-Arbeitsbereich.
- Ereignissuche: sichtbares Label entfernt, barrierefreies Suchfeld mit Lupensymbol und zusätzlichem Abstand zum Titel.
- Alle Datenbank-, Import-, Cache- und Sicherungsfunktionen gegenüber 0.45.2 unverändert.

## Kostenkontrolle der GitHub Actions (0.45.2)

- Bei Zwischen-Commits auf patch/* werden weder doppelte Backendtests noch Container-Builds gestartet.
- Backend-QA lässt sich manuell oder über einen Pull Request auslösen; der Container wird auf Patchbranches ausschließlich per "Run workflow" erzeugt.
- Importquellen und Archivübersichten bleiben nur wenige Sekunden serverseitig gecacht; echte Bearbeitungs- und Dateiprüfungen bleiben verbindlich.
- Alle ausgeblendeten Importverläufe sind auch bei leerer sichtbarer Liste erreichbar.

## 0.45.2 – Schnellere Ansichten, Prüf-Reload und kompakter Importverlauf (08.10.2026)

- Sofortige Bibliotheksbezeichnung, differenzierte hellfarbige Prüffallkarte, bereinigte Tagesordnerübersicht.
- Wiederverwendbare Ansichten für Aufnahmen, Ereignisse und Importquellen; physische Prüfungen beim manuellen Neuladen und vor kritischen Dateioperationen.
- Eigene paginierte SQLite-Sichtbarkeit des Import-/Prüfverlaufs. Kompakte Karten mit aufklappbaren technischen Details, sicherem Ausblenden/Wiederherstellen.
- Regressionstests zur neuen Version und zum Schutz der Dateibestände.

## 0.45.1 – Kontinuierliche Reiteranimation und Theme-First-Paint (08.10.2026)

- Dark-/Light-Mode bereits vor dem ersten Paint synchron aus der gespeicherten Theme-Wahl initialisiert; vermeidet helle Zwischenframes und vorübergehend schwarze inaktive Reiter auf iOS Safari und in der installierten Web-App.
- Bereichswechsel als zusammenhängende Animation: Mobile Tap hebt nur einmal an, Desktop Hover hebt leicht und Pointerdown/Klick etwas weiter an; keine Rückbewegung zwischen Pointerup und Navigation.
- Übergabe des Zielreiters per kurzlebigem SessionStorage-Eintrag an die nächste HTML-Seite: Zielreiter bleibt zunächst angehoben und fährt erst nach dem ersten Paint in die aktive Endlage.
- Browser-History/BFCache bereinigt Presszustände; Reduced-Motion wird berücksichtigt. Frozen-Design und Kamera-/Archivfachlogik bleiben unverändert.
- Gezielte Tests für frühe Theme-Initialisierung, Reiternavigation und Versionsverträge.

## 0.45.0 – Typografie und Navigation (08.10.2026)

- Appweit die Schriftfolge Futura → Helvetica Neue → Helvetica → Arial → sans-serif eingeführt; keine externen Fontdateien erforderlich. Gilt auch für Eingaben, technische Textfelder sowie Import-, Ereignis- und Archivansicht.
- KI-Assistenten-Button im Desktop-Header und Assistenten-Eintrag im mobilen Hamburger-Menü ausgeblendet. Die interne Platzhalterroute bleibt für eine spätere KI-Anbindung erhalten.
- Navigation gegen schriftbedingte Überläufe abgesichert (verkürzte Labels statt ungeplanter Umbrüche, besonders auf schmalen Mobilgeräten).
- Versionsanzeige und fokussierte Regressionstests auf 0.45.0 angehoben; Fachlogik und Bibliotheksdaten bleiben unverändert.


## [Unreleased]

### 0.44.4 – kompakter Desktop-Hinweis für Hintergrundvorgänge

- Der bisherige Hinweis für das Verwerfen wurde vom Header nach rechts unten verlagert; er verdeckt keine obere Navigation mehr.
- Ein kleiner Schließen-Button verkleinert den Hinweis auf ein Statussymbol. Durch Klick wird die Übersicht wieder geöffnet; der eingeklappte Zustand bleibt beim Seitenwechsel erhalten.
- Die Desktop-Übersicht zeigt drei vorhandene serverseitige Prozesse an: laufende Importe, Ereignissortierungen (auch Sammelanwendungen) und persistente Verwerfaufträge. Verlinkungen führen zu den zugehörigen App-Bereichen.
- Sehr schmale bzw. niedrige Fenster und Geräte mit Touch-Zeiger erhalten keinen Overlay-Hinweis. Die eigentlichen Vorgänge bleiben davon unberührt.
- Der Statusabruf ist rein lesend; beim Import, Sortieren und Verwerfen werden keine Abläufe verändert.



### 0.44.3 – Verwerfen als persistenter Hintergrundauftrag

- Applied-Änderungen werden als idempotente SQLite-Aufträge übernommen; der Server-Worker verarbeitet die Wiederherstellung unabhängig vom Browser und stellt nach einem App-Neustart unterbrochene Aufträge erneut zu.
- Dateirücknahmen erkennen nach einem Prozessabbruch vollständig oder halb abgeschlossene sichere Hardlink-Verschiebungen anhand von Dateipfaden, Inode, Größe und SHA-256.
- Alle App-Bereiche zeigen den Status des Hintergrundauftrags an. Nach bestätigter Annahme darf der Browser gewechselt, geschlossen oder neu geladen werden; nicht gleichzeitig dieselben Dateien bearbeiten.
- Archiv-Rückänderungen bleiben bewusst beim separat geführten manuellen Finder-Workflow und werden nicht automatisch abgeschlossen.


### 0.44.2 – unmittelbares Feedback bei Ereignisänderungen

- Das Prüfungsfenster öffnet sich bei angewendeten Ereignissen bereits beim Löschen oder Speichern; ein animierter Fortschrittsindikator informiert während der Berechnung.
- Beim Verwerfen laufender Applied-Änderungen erscheint auf der Ereignisseite sofort ein Ladekreis, bis der ursprüngliche Zustand wiederhergestellt ist.
- Die veralteten gelben Karten „Neu-Zuordnung offen“ und „Nachsortierung offen“ entfallen. Nur tatsächlich unterbrochene Transaktionen bleiben über das aufgeklappte Ereignis fortsetzbar und verwerfbar.
- Archivierte Ereignisse zeigen die Vorbereitung ihres manuellen Löschauftrags ebenfalls sofort im zugehörigen Dialog.


### 0.44.0 – Bibliothekar-Papierkorb

- Der gemeinsame Kamera-Arbeitsbereich besitzt einen vierten verwalteten Stammordner „Papierkorb“. Seine interne Rolle ist stabil; der sichtbare Ordnername kann unter Einstellungen → Pfade unabhängig geändert werden.
- Der Papierkorb ist über das Hamburgermenü erreichbar und gleicht beim Öffnen automatisch den tatsächlichen Dateisystembestand mit SQLite ab. Finder-/SMB-Verschiebungen in den Papierkorb werden als normaler Workflow erkannt.
- Dateien mit physischem Zustand `trash` werden aus aktivem Tagesbestand, Ereignisdateien und Sortierplänen ausgeschlossen. SQLite folgt dem beobachteten Speicherort, bleibt aber als Herkunfts-/Identitätsquelle für eine spätere Wiederherstellung erhalten.
- „Papierkorb entleeren“ ist ausschließlich manuell, verlangt eine Sicherheitsbestätigung, löscht den physischen Bestand ohne Symlink-Folgepfade und bereinigt anschließend die zugehörigen SQLite-Datei-/Familieneinträge.
- Die vorhandene Umbenennungsarchitektur der verwalteten Stammordner wurde gehärtet: Bibliotheks-Kompatibilitätswurzeln verwenden nun die konfigurierten Rollennamen statt sichtbarer Standardnamen.
- Es gibt keine automatische Löschfrist und keinen zweiten Löschmechanismus neben dem Papierkorb.

### 0.43.4 – Unterbrochene Importe bereinigen

- Durch einen App-Neustart unterbrochene Ordnerimporte bleiben als klarer Status „Unterbrochen“ erhalten, berechnen aber keine weiterlaufende Restzeit mehr.
- Fehlgeschlagene und unterbrochene Kamera-/Ordnerimporte erhalten im Importverlauf die Aktion „Import entfernen“.
- Beim Entfernen werden noch vorhandene sichere Importreste im zentralen Arbeitsbestand gegen Größe und SHA-256 geprüft, temporäre `.incoming`-Daten entfernt und anschließend der zugehörige Auftrags-/Verlaufseintrag bereinigt. Die ursprüngliche Importquelle bleibt unverändert.
- Laufende Importe behalten „Import abbrechen“, abgeschlossene Sicherungen behalten die bestehende kontrollierte Aktion „Sicherung löschen“. Damit hat jeder relevante Importzustand eine passende Abschlussaktion, ohne abgeschlossene Provenienz vorschnell zu verwerfen.
- Die vorhandene Neustart-Sicherung bleibt unverändert: laufende Aufträge werden beim Start deterministisch als „interrupted_after_restart“ markiert und können danach sauber entfernt werden.

### 0.43.3 – Feinschliff Importfortschritt

- Laufende Importe zeigen die Prozentzahl nicht mehr doppelt: Die Balken sind nur noch mit „Aktuelle Stufe“ und „Gesamt“ beschriftet; die Prozentangabe bleibt kompakt in „Fortschritt gesamt“ darunter.
- Der Abstand zwischen den beiden laufenden Fortschrittsbalken wurde reduziert.
- Die Restzeitschätzung erscheint bereits nach kurzer Laufzeit. Backend-Zeitstempel werden für iOS/Safari robust normalisiert; bei sehr kurzen Restzeiten wird in Sekunden geschätzt statt nur ein Gedankenstrich gezeigt.
- Abgeschlossene Importe zeigen nur noch den grünen Gesamtbalken mit der Beschriftung „Abgeschlossen“; der Stufenbalken entfällt.

### 0.43.2 – Sticky-Vorschauen, zweistufiger Importfortschritt und Speicher-Loader

- Die Zielstruktur-Vorschau im Arbeitsbereich bleibt auf Desktop beim Scrollen direkt unter dem Secondary-Header. Ihre lange Tages-/Dateiliste besitzt einen eigenen vertikalen Scrollbereich, damit nicht die gesamte Seite verschoben werden muss.
- „Datei prüfen“ und „Referenzaufnahme“ in der Metadatenkorrektur bleiben auf Desktop ebenfalls unter dem Metadaten-Secondary-Header sichtbar und scrollen bei langem Inhalt innerhalb ihres eigenen Panels.
- Die Sticky-Unterkante wird aus tatsächlicher Shell- und Secondary-Header-Höhe berechnet und bei Größenänderungen automatisch aktualisiert.
- Laufende Importe zeigen getrennt den Fortschritt der aktuellen Stufe und den Gesamtfortschritt. Der Stufenbalken beginnt bei jedem Verarbeitungsschritt neu; die Prozentangabe unterhalb der Balken bezieht sich ausschließlich auf den Gesamtfortschritt.
- Zusätzlich wird aus Startzeit und gewichtetem Gesamtfortschritt eine geschätzte verbleibende Gesamtdauer angezeigt.
- Beim Speichern bzw. Anwenden von Ereignisänderungen zeigt der Aktionsbutton einen Loader und verhindert während der laufenden Anfrage Doppelklicks.

### 0.43.1 – Kombinierbare Unterereignisnamen und native Datumsfelder

- Die Benennung von Unterereignissen verwendet jetzt dieselben frei kombinierbaren Optionen wie normale Ereignisse: „Jahr einbeziehen“, „Uhrzeit einbeziehen“ und „Von–bis im Namen“. Der separate Auswahlmodus „Datum/Datumsbereich/Uhrzeit/Jahr/Kein Präfix“ entfällt.
- „Standardmäßig verwenden“ schaltet den Unterereignis-Präfix vollständig ein oder aus; der kompakte Schalter „Präfix: an/aus“ im Ereignisfenster bleibt unverändert erhalten.
- 0.43.0-Ereignisse behalten ihre bereits gespeicherte Unterereignis-Benennung. Alte 0.43.0-Bibliothekseinstellungen werden beim Lesen in das neue kombinierbare Modell überführt.
- Die Vorschau zeigt Unterereignis und dessen Ordnerstruktur jetzt innerhalb des normalen Ereignisbeispiels. Die separate dritte Vorschaukarte entfällt.
- Ereignis- und Unterereignis-Datumsfelder verwenden wieder native Datumsfelder des Browsers. Damit stehen lokalisierte Eingabe, segmentweises Tippen und das native Kalendersymbol wieder zur Verfügung; die zusätzlich eingeführten Kalender-Emoji-Schaltflächen entfallen.

### 0.43.0 – Ereignisplanung und Unterereignisse

- Fotofreie Kalendertage innerhalb eines normalen Ereignis- oder Unterereigniszeitraums gelten nicht als Lücken. Ein normales Ereignis bleibt ein durchgehender Beginn-/Ende-Zeitraum; Tageskarten sind nur Auswahlhilfen.
- Nicht angehakte Tageskarten aus sichtbaren aktiven Sicherungen werden innerhalb des gewählten Zeitraums automatisch mit einbezogen. Die Bestätigung „Weitere Aufnahmen“ erscheint nur noch für zusätzliche freie Aufnahmen aus aktuell ausgeblendeten aktiven Sicherungen.
- Datumswerte für normale Ereignisse und Unterereignisse lassen sich vollständig als `JJJJ-MM-TT` tippen. Der Kalender bleibt als optionaler Button verfügbar; ungültige Kalenderdaten werden serverseitig abgewiesen.
- Jahresübergreifende Ereignisse und Unterereignisse erhalten bei datumsbasierten Präfixen automatisch eindeutige Jahresangaben.
- Einstellungen → Ereignisordner enthält den eigenen Bereich „Unterereignisse“. Für neue Unterereignisordner kann der Namenspräfix auf Datum, Datumsbereich, Uhrzeit, Jahr oder kein Präfix gestellt und standardmäßig ein- oder ausgeschaltet werden.
- Sobald im Erstellfenster mindestens ein Unterereignis angelegt ist, erscheint kompakt „Präfix: an/aus“. Die Entscheidung wird mit dem Ereignis eingefroren; bestehende Ereignisse behalten ihren bisherigen Benennungsstand.
- „Ohne Ereignis“ kann keine semantischen Unterereignisse besitzen. Verschachtelte Unter-Unterereignisse werden ebenfalls nicht zugelassen.
- Bestehende Archiv-/Strukturänderungen laufen weiterhin über den vorhandenen Workflow „Manuelle Ereignisänderung“; für 0.43.0 wurde kein paralleler Änderungsmechanismus eingeführt.

### 0.42.5 – PWA-Auswahlabschluss und Metadaten-Sheet

- In der installierten Handy-Web-App bleiben auswählbare Karten nicht mehr dauerhaft als eigene Transform-/Compositor-Layer vorgemerkt. Die Optimierung gilt nur während des kurzen Wobble-Effekts; dadurch werden die feinen Kartenrahmen auf iOS nicht mehr an Viewport- bzw. Sticky-Layer-Grenzen abgeschnitten.
- Long-Press aus dem normalen Metadatenmodus aktiviert Bibliothek, Allgemein und Mehrfachkorrektur jetzt ohne DOM-Neuaufbau unter dem noch aufliegenden Finger. Der aktuelle Touch-Zielknoten bleibt bestehen, sodass dieselbe Geste unmittelbar in die echte Drag-/Autoscroll-Auswahl übergeht.
- Das nicht-modale mobile Auswahlfenster misst seine tatsächliche Höhe und reserviert entsprechend zusätzlichen Scrollraum am Seitenende. Auch die letzten Metadatenkarten lassen sich dadurch oberhalb des Fensters erreichen und nachträglich aus- oder abwählen.

### 0.42.4 – Reversible PWA-Auswahl und mobile Metadatenfenster

- Die Long-Press-Schnellauswahl arbeitet jetzt als zusammenhängende Range: Beim Zurückwischen werden nur die durch die laufende Geste hinzugekommenen Karten wieder abgewählt; bereits vorher ausgewählte Karten bleiben erhalten.
- Randscrollen während einer laufenden Auswahl wird kontinuierlich per Animation-Frame fortgeführt. Neu in den Viewport kommende Karten werden dadurch ohne erneutes Überstreichen nahtlos in die Auswahl einbezogen.
- Die Wobble-Rückmeldung verzichtet auf Skalierung und wackelt nur horizontal, damit Kartenrahmen am oberen bzw. unteren Viewportrand nicht abgeschnitten erscheinen.
- In Bibliothek, Allgemein und Mehrfachkorrektur aktiviert Long-Press den regulären Auswahlmodus mit sichtbaren Checkboxen. Auswahl und Abwahl werden unmittelbar in den Häkchen und Karten dargestellt.
- Ein gezielter Einzel-Tap öffnet die mobile Dateiprüfung als vollflächige, vollständig scrollbar bleibende Detailansicht.
- Ab zwei ausgewählten Metadateneinträgen erscheint stattdessen ein kompaktes, nicht-modales Auswahlfenster am unteren Rand. Der Hintergrund bleibt ohne Blur sichtbar und weiter bedienbar, sodass zusätzliche Dateien ausgewählt werden können.
- Die Mehrfachkorrektur besitzt jetzt denselben expliziten Auswahlmodus wie Bibliothek und Allgemein; Einzel-Tap bleibt weiterhin die Auswahl einer Referenzaufnahme.

### 0.42.3 – Web-App-Interaktion für Aufnahmen und Metadaten

- In der installierten Handy-Web-App bleibt der `x Prüffälle`-Badge der Ohne-Datum-Karte vollständig innerhalb der Aufnahmen-Karte.
- Metadatenkarten brechen lange Dateinamen, Pfade und Badge-Texte auf kleinen Web-App-Bildschirmen sauber um, statt Inhalt über Status-Tags laufen zu lassen.
- In `Bibliothek`, `Allgemein` und `Mehrfachkorrektur` öffnet ein normaler Dateiklick in der installierten Handy-Web-App die bestehende Detail-/Referenzansicht als eigenes Bottom-Sheet. Es gibt einen expliziten `Schließen`-Button; nach erfolgreicher Metadatenänderung bzw. Mehrfach-Vorschau schließt das Sheet automatisch.
- Long-Press auf eine auswählbare Karte aktiviert ausschließlich in der installierten Handy-Web-App die Schnellauswahl. Gedrücktes Ziehen über weitere Karten fügt sie der Auswahl hinzu; jede neu erfasste Karte erhält ein kurzes Wobble-Feedback.
- Die Schnellauswahl steht bei `Aufnahmen` sowie in den Metadatenbereichen `Bibliothek` und `Allgemein` zur Verfügung. In `Mehrfachkorrektur` begrenzt eine per Geste gewählte Teilmenge Preview und `Anwenden` tatsächlich auf diese Dateien.
- Eine Teilmenge der Mehrfachkorrektur kann bewusst nicht direkt mit `Anwenden und in Tagesbestand übernehmen` importiert werden, weil dieser Importpfad weiterhin den vollständigen Mehrfachkorrektur-Ordner repräsentiert. Ohne Gestenauswahl bleibt das bisherige Verhalten unverändert.
- Die neue Touch-Geste, Animation und mobile Detailansicht sind auf Standalone/Web-App und kleine Displays begrenzt; Desktop und mobile Browser-Website behalten ihr bisheriges Verhalten.

### 0.42.2 – Automatische Metadatenprüfung

- Die Bereiche `Bibliothek`, `Allgemein` und `Mehrfachkorrektur` prüfen ihren jeweiligen Bestand jetzt automatisch beim Öffnen bzw. Reload der Metadatenkorrektur.
- Der vorhandene Button `Bestand prüfen` bleibt für eine manuelle erneute Prüfung erhalten.
- Automatische und manuelle Prüfungen zeigen während des laufenden Scans denselben Busy-Zustand mit Spinner am Button und Ladeindikator in der Statuszeile.

### 0.42.1 – Metadaten-Rücksortierung und Prüffall-UI

- Interne Übernahmen aus `Allgemein` und `Mehrfachkorrektur` bleiben technisch als verifizierte Hintergrundjobs erhalten, werden aber nicht mehr als sichtbare Karten im Import- und Prüfverlauf dargestellt.
- Freie datierte Familien werden in den globalen Aufgaben bibliotheksweit zu einer einzigen Aufgabe `Noch nicht zugeordnet` zusammengefasst. Eine zurücksortierte korrigierte Familie erhöht damit den bestehenden Zähler, statt eine eigene Ein-Familien-Aufgabe zu erzeugen.
- `Ohne Datum` ist im Arbeitsbereich keine auswählbare Tagesgruppe mehr. Prüffälle stehen hervorgehoben am Anfang der Tagesordnerliste, werden von `Alle auswählen` ausgeschlossen und können nicht in die Ereignisplanung übernommen werden.
- Ein Klick auf die Prüffallkarte zeigt in der Zielstruktur-Vorschau einen direkten Einstieg `Metadatenkorrektur`; Doppelklick bzw. der Button öffnen unmittelbar die Bibliotheks-Prüffälle.

### 0.42.0 – Metadatenkorrektur für große Bestände

- Bereits bekannte Kameraoriginale werden beim Reimport zusätzlich über ihre stabile ursprüngliche SHA-256-Identität erkannt. Damit erscheinen ältere, vor der Einführung von `source_size_bytes` korrigierte Dateien nicht wegen einer nachträglich veränderten Dateigröße erneut als neue Prüffälle.
- Die Dateiliste arbeitet standardmäßig ohne Checkboxen. Mehrfachauswahl wird bewusst über `Auswählen` aktiviert und unterstützt Umschalt-/Bereichsauswahl sowie `Alle auswählen`.
- Bei Mehrfachauswahl wird kein gemeinsames Datum/Uhrzeit-Feld mehr angeboten. Stattdessen wählt man einen gemeinsamen Metadaten-Quelltyp; jede Datei übernimmt ihren eigenen aktuellen Wert dieses Tags.
- Mehrfachkorrekturen werden serverseitig gebündelt: Der Metadatenbestand wird pro beteiligtem Bereich bzw. Bibliothek nur einmal vorgeprüft, statt für jede ausgewählte Datei erneut vollständig gescannt zu werden.
- Metadatenkandidaten zeigen deutsche Bezeichnungen, technischen ExifTool-Tag und eine einfache deterministische Vertrauensbewertung. Der bevorzugte Kandidat ist direkt sichtbar; weitere Kandidaten bleiben kompakt aufklappbar.
- Die vor einer Korrektur beobachteten Metadaten bleiben über die vorhandenen persistenten Korrekturaufträge einsehbar.
- Dateien aus `Allgemein` können kontrolliert über den vorhandenen verifizierten Importpfad in den Tagesbestand übernommen werden. Bereits bekannte Kameraaufnahmen werden dabei blockiert, statt künstlich eine neue Sicherung bzw. Provenienz zu erzeugen.
- `FileCreateDate` steht als zusätzlicher niedrig gewichteter Dateisystem-Kandidat zur Verfügung; die Auswahl bleibt vollständig deterministisch und verwendet kein KI-Modell.

### 0.41.4 – Applied-Reparatur, Planned-Performance und konsistentes Loading

- Falsch verschobene Dateien aus angewendeten Ereignissen behalten ihren semantischen Sollpfad persistent und können mit Größen-/SHA-256-Prüfung sicher dorthin zurückgesetzt werden; manuell bereits korrekt zurückgelegte Dateien werden beim erneuten Prüfen ebenfalls verifiziert und übernommen.
- Fehlgeschlagene automatische Reparaturen werden nicht mehr wie Erfolg behandelt: Die Aufgabe bleibt offen, der erwartete Sollort wird angezeigt und „Ignorieren“ bleibt für normale Zuordnungskonflikte möglich.
- Reines Speichern eines geplanten Ereignisses löst beim unmittelbaren UI-Nachladen keinen zweiten vollständigen Inventar-/Reconcile-/Strukturscan mehr aus. Normale Seitenaufrufe und Reloads behalten die vollständige physische IST-Prüfung.
- Speichern, Rückgängig, Arbeitsbereich, Ereignisliste, Archivprüfung sowie Import-/Prüfaktualisierung erhalten konsistente Busy-/Spinner-Zustände ohne künstliche Wartezeiten.
- Der Einstellungsdialog ist gegen bereichsspezifische Import-CSS-Regeln abgeschirmt; Akkordeons und Vorschaukästen verwenden in Hell/Dunkel dieselben Settings-Komponenten wie in Arbeitsbereich und Archiv.
- „Archiv prüfen“ im externen Hinweisdialog erhält einen nicht abgeschnittenen, aber weiterhin tastaturzugänglichen Fokuszustand.

### 0.40.3 – iPhone-Web-App im Hochformat fixieren

- Die installierte Web-App erhält ein echtes Web-App-Manifest. Auf iPhone/iPod wird die bevorzugte App-Ausrichtung auf `portrait-primary` gesetzt, sodass Drehen des Geräts die Web-App nicht mehr in die Querformatansicht umschaltet.
- iPad und andere Tablets bleiben ausdrücklich ungesperrt (`orientation: any`); deren eigene responsive Gestaltung wird weiterhin separat behandelt.
- Die normale mobile Website im Browser bleibt von der Ausrichtungssperre unberührt.
- Manifest-Antworten variieren nach User-Agent und werden nicht dauerhaft gecacht, damit iPhone und iPad dieselbe Bibliothekar-Installation mit unterschiedlicher Ausrichtungsregel verwenden können.
- 0.40.3 ist ein reiner Web-App-/Darstellungs-Patch; Ereignis-, Import-, Archiv- und Dateilogik bleiben unverändert.


### 0.40.2 – mobile Von–Bis-Eingabe vervollständigen

- Tagessegmente von „Ohne Ereignis“ zeigen auf Handybreite nur noch eine gemeinsame Überschrift „Von–Bis“ statt der störenden Einzelbeschriftungen „Tag“, „Von“ und „Bis“.
- Darunter stehen zwei vollständige Zeilen: jeweils Tag, Monat/Jahr und Uhrzeit. Das Enddatum wird als ausgegraute Spiegelzeile des gewählten Tages angezeigt und folgt einer Tagesänderung automatisch.
- Die Darstellung gilt sowohl beim Erstellen/Fortführen von „Ohne Ereignis“ im Arbeitsbereich als auch bei der späteren Ereignisbearbeitung.
- 0.40.2 ist ein reiner Darstellungs-Patch auf Basis von 0.40.1; Ereignislogik und Dateizuordnung bleiben unverändert.

### 0.40.1 – mobile Import- und Ereignisansicht nachschärfen

- Lange Dateipfade und Sicherungsnamen in der Liste übersprungener Importduplikate umbrechen innerhalb ihrer Karte und laufen auf schmalen Displays nicht mehr über den Rahmen.
- „Ohne Ereignis“-Tagessegmente verwenden auf Handybreite eine eigene zweizeilige Eingabe: Tag und Beginn bleiben zusammen sichtbar, „Bis“ erhält eine vollständige zweite Zeile; alle Felder bleiben bedienbar.
- Die drei Ereignis-Kennzahlen „Angezeigte Ereignisse“, „Zugeordnete Familien“ und „Löschbare Planungen“ stehen auf dem Handy kompakt nebeneinander, mit dem Zahlenwert rechts in derselben Karte.
- Die Aktionen aufgeklappter Ereignisse bleiben auf dem Handy in einer Zeile. Die Schaltflächen verkleinern Abstand, Innenabstand und Schrift dynamisch, statt in eine zweite Zeile umzubrechen.
- Desktopdarstellung und Ereignis-/Importlogik bleiben unverändert; 0.40.1 ist ein reiner Darstellungs-Patch auf Basis von 0.40.0.

### 0.40.0 – Import abbrechen und Sicherungen sicher löschen

- Laufende Kameraimporte von SD-Karte, USB-Laufwerk oder Ordner können bis zum Abschluss abgebrochen werden. Der Abbruch erfolgt kooperativ und räumt temporäre bzw. bereits verschobene Importdateien nur nach sicherer Prüfung wieder auf.
- Abgeschlossene Sicherungen können vollständig gelöscht werden, solange sie noch vollständig und unverändert im zentralen Arbeitsbestand liegen und in keiner Bibliothek bereits von einem Ereignis verwendet werden. Vor dem Löschen werden Dateigröße und SHA-256 erneut geprüft; die Oberfläche verlangt zusätzlich eine Browser-Bestätigung.
- Bei „Quelle sichern“ weist die Oberfläche sichtbar und in der Hilfe darauf hin, dass Sicherungen als Kopie angelegt werden, Daten geschrieben werden und zusätzlicher Speicherplatz benötigt wird.
- Das spätere gezielte Verwerfen einzelner Tage oder Dateien innerhalb einer Sicherung gehört ausdrücklich nicht zu 0.40.0.

### 0.35.7 – Erststart-Bibliothek wieder bedienbar

- Die Onboarding-Seite „Erste Bibliothek einrichten“ rendert den Zeilenumbruch in Fehlermeldungen wieder als gültiges JavaScript-Escape statt als echten Zeilenumbruch innerhalb eines String-Literals.
- Dadurch wird der Click-Handler des Buttons „Bibliothek prüfen und anlegen“ wieder registriert; Pfadprüfung, sichtbare Fehlermeldungen und anschließende Bibliotheksanlage können beim ersten Start tatsächlich ausgeführt werden.
- Ein Regressionstest prüft den gerenderten Onboarding-HTML/JavaScript-Block ausdrücklich auf den korrekten Escape und schützt diesen nur beim Erststart sichtbaren Codepfad vor einem erneuten stillen Ausfall.

### 0.35.6 – mobile Website im Hochformat

- Die Web-App bleibt unverändert; alle neuen Layoutregeln sind ausdrücklich auf den Browsermodus begrenzt.
- Arbeitsbereich/Aufnahmen auf der Handy-Website erhält denselben kompakten Sekundärheader wie die Web-App: Aufnahmen/Ereignisse oben, darunter Ohne Ereignis/Ereignis und der Pfeil. Die separate Karte „0 Gruppen ausgewählt“ entfällt auf schmalen Browserfenstern.
- Titel „Aufnahmen“ und der 2×2-Kennzahlenblock sind links und rechts bündig mit Sicherungsfilter und den übrigen Inhaltskarten.
- Responsive Website: bis 920 px fällt die breite Desktop-Anordnung in den kompakten 2×2-Block; bei weiterer Verkleinerung skalieren Abstände, Kartenhöhe und Typografie innerhalb dieses Blocks, ohne die Anordnung erneut zu ändern.
- Desktop in normaler Breite und die installierte Web-App bleiben von diesen Regeln unberührt.

### 0.35.5 – kompakte Aufnahmen-Karten und mehr Safe-Area-Abstand

- Aufnahmen: die vier Kennzahlen werden nun über den tatsächlich verwendeten `section.summary`-Selektor angesprochen. Dadurch greifen die kompakten Regeln zuverlässig: 2×2, 40 px Höhe, kleinere Beschriftung und Zahl in derselben Zeile.
- Der Web-App-Dock bleibt auf allen Seiten identisch, erhält aber deutlich mehr unteren Abstand, damit Aufgaben- und Hamburger-Rahmen auch bei stark abgerundeten iPhone-Ecken vollständig sichtbar bleiben.
- Sicherungsfilter: lange Sicherungsnamen dürfen innerhalb der Auswahlkarte umbrechen und können nicht mehr über den rechten Kartenrand hinausragen.

### 0.35.4 – Aufnahmen-Kennzahlen wie im Archiv

- Aufnahmen: die vier Kennzahlen Tage, Dateien, Familien und Prüffälle stehen auf dem Handy jetzt stabil direkt unter dem Titel Aufnahmen und oberhalb des Sicherungsfilters.
- Die mobile Seitenüberschrift wird ausdrücklich aus dem Desktop-Zweispaltenraster gelöst; dadurch können die Karten nicht mehr nach rechts aus dem sichtbaren Bereich rutschen.
- Größe, 2×2-Anordnung, Abstände, Innenabstände und Typografie der vier Karten entsprechen der kompakten Archivdarstellung. Bezeichnung und Zahl stehen in einer Zeile; die Karten sind fest auf 42 px Höhe verdichtet.
- Der einheitliche Web-App-Dock erhält auf allen Seiten 4 px mehr unteren Abstand, damit Aufgaben- und Menürahmen auch an stärker abgerundeten iPhone-Ecken vollständig sichtbar bleiben.

### 0.35.3 – letzte Web-App-Feinarbeiten

- Web-App-Dock auf allen Bereichen vereinheitlicht: weniger Höhe, weniger Leerraum unter der Leiste und kleinere, gleich hohe Rahmen für Aufgaben und Menü, damit abgerundete iPhone-Ecken nichts abschneiden.
- Sichtbare Fragezeichen an Seiten- und Abschnittstiteln entfallen. Die Erklärung hängt jetzt direkt am Titel: Desktop per Hover/Fokus, Touch/Web-App per Antippen.
- Das gilt für Import & Prüfung, Aufnahmen, Ereignisse, Archiv, Metadatenkorrektion sowie Zur Archivprüfung und Archivverlauf.
- Aufnahmen übernimmt für Tage, Dateien, Familien und Prüffälle exakt die kompakte 2×2-Logik des Archivs.
- Die vier Aufnahmen-Kennzahlen stehen direkt unter dem Titel Aufnahmen; der Sicherungsfilter folgt darunter.
- Die bestehende Hilfe bei Quelle sichern bleibt erhalten.


### 0.35.2 – Kompaktere Web-App und reduzierte Hilfetexte

- Web-App-Kopf weiter verkleinert; aktive Bibliothek steht rechts neben „Bibliothekar“ statt darunter.
- Untere Web-App-Navigation auf allen Seiten vereinheitlicht und etwas kompakter. Der grüne Aufgaben-Haken entfällt; Aufgabenname und Zähler bleiben, der Menübutton erhält mehr Abstand zu abgerundeten Geräteecken.
- Aufnahmen: Kennzahlen bleiben auf dem Handy wieder im Dokumentfluss und erscheinen als vier sehr kompakte Kacheln in einer Zeile. Die Aktionszeile im Sekundärheader ist enger und an den beiden Bereichsreitern ausgerichtet.
- Archiv: vier Kennzahlen sind auf dem Handy deutlich kompakter; erklärende Abschnittstexte wurden in Fragezeichen-Hilfen verschoben.
- Seitenuntertitel von Import, Aufnahmen, Ereignisse, Archiv und Metadatenkorrektion wurden durch Fragezeichen-Hilfen ersetzt.
- Import: „Quelle auswählen …“ liegt nun im vorhandenen Hilfe-Button; „Diagnose & Test“ und der künstliche Testimport wurden aus der Oberfläche entfernt. Lange Statuswerte wie „Beschreibbar“ werden kleiner gesetzt statt abgeschnitten.
- Arbeitsbereich: der Sicherungsfilter besitzt nun ein Filter-Icon. Neutrale Beispiele lauten „Urlaub“ und „Tag 1“ statt persönlicher Bezeichnungen.
- Ereignisse: die große Erklärungskarte „Planung, Prüfung und bestätigte Sortierung“ entfällt.
- Metadatenkorrektion: Reiter wieder in der Reihenfolge Bibliothek · Allgemein · Mehrfachkorrektur; Bereichserklärungen liegen im Fragezeichen, lange Ordnerpfade umbrechen sicher und versteckte Bereichskarten bleiben wirklich ausgeblendet.
- Der bisherige Dateiname in der Zielstruktur-Vorschau bleibt in diesem Patch bewusst unverändert.


### 0.35.1 – Mobile Header, Sekundärnavigation und Dichte

- Aufgaben- und Hamburger-Menü verwenden in Web-App und normaler Website eigene echte Trigger. Das bisherige Weiterreichen eines PWA-Klicks an einen versteckten Desktop-Button entfällt; Popover werden am tatsächlich sichtbaren Auslöser positioniert und nicht sofort wieder geschlossen.
- Der Web-App-Kopf ist kompakter, zeigt wieder die aktive Bibliothek und ist auf iOS fest verankert. Die gemessene Headerhöhe enthält im Standalone-Modus keinen unsichtbaren Seiten-Bridge-Abstand mehr; Pull-to-Overscroll kann dadurch keine helle Lücke oberhalb des Headers erzeugen oder den Kopf teilweise wegziehen.
- Auf Handy bleibt der Sekundärheader sticky. Im Arbeitsbereich werden in der installierten Web-App „Ohne Ereignis“, „Ereignis“ und der Nach-oben-Pfeil aus der bisherigen Auswahlkarte in diesen Header gedockt; die doppelte Karte im Inhalt entfällt.
- Die Metadatenkorrektur nutzt denselben sticky Sekundärheader. Die Bereiche stehen von links nach rechts als „Mehrfachkorrektur · Allgemein · Bibliothek“.
- Die drei Import-Statuskarten sind nochmals verdichtet: ihre Überschrift nutzt die volle Kartenbreite linksbündig über dem Symbol, Statuswerte bleiben einzeilig und die Typografie ist kleiner.
- Mobile Karten, Importquellen, Verlaufszeilen, Überschriften und die untere Web-App-Navigation sind moderat verkleinert, damit mehr Inhalt gleichzeitig sichtbar bleibt.
- Der grüne Aufgaben-Haken in der unteren Web-App-Navigation besitzt eine feste Flex-Breite und kann nicht mehr zusammengedrückt werden.
- Regressionstests sichern Popover-Trigger, Standalone-Kopf, sticky Sekundärnavigation, mobiles Arbeitsbereich-Docking, Metadatenreihenfolge und Versionsvertrag ab.


### 0.35.0 – Eigene Handy-Web-App und responsive Fenster

- Die installierte Handy-Web-App und die normale Website im mobilen Browser erhalten erstmals getrennte Darstellungsmodi. Der Modus wird über `display-mode: standalone` mit iOS-`navigator.standalone`-Fallback erkannt.
- Die Web-App übernimmt die iOS-Referenzaufteilung: ein reduzierter dunkler Kopf mit Bibliothekar-Marke sowie eine feste untere Navigation für Import, Arbeitsbereich, Archiv, Aufgaben und Menü. Die mobile Website behält zunächst den bisherigen oberen Registerheader und kann unabhängig weiterentwickelt werden.
- Der Arbeitsbereich der Web-App ist auf kleine Displays verdichtet: vier Kennzahlen stehen wieder in einer Zeile, Auswahlaktionen sind kompakter und Tageskarten behalten Statusbadges in derselben Zeile.
- Mobile Inhaltskorrekturen gelten bewusst für Web-App und Website: Dialoge und Formfelder bleiben innerhalb des Viewports, Unterereignis-Bedienelemente ragen nicht mehr über den Rahmen und die drei Metadatenbereiche passen ohne abgeschnittenen Reiter in die Breite.
- Die drei Statuskarten im Import stehen auf dem Handy wieder nebeneinander. Datenbankschemata werden dort als kompakter Bereich (zum Beispiel `1–45`) statt als lange Versionsliste dargestellt.
- Aufgaben- und Menü-Popover werden in der Web-App oberhalb der unteren Navigation geöffnet; der Assistent bleibt über das Menü erreichbar.
- Regressionstests sichern die getrennte Standalone-Erkennung, die PWA-Navigation, die mobilen Rahmenkorrekturen und die kompakte Darstellung ab.

### 0.34.0 – Mehrfachkorrektur mit konstantem Zeitversatz

- Der verwaltete Ordner `/workspace/Metadatenkorrektur/Mehrfachkorrektur` wird beim Startup automatisch neben `Allgemein` angelegt.
- Die Mehrfachkorrektur ist als eigenständiges Werkzeug aktiviert: Eine beliebige enthaltene Aufnahme kann als Referenz gewählt und auf das tatsächliche Datum mit Uhrzeit gesetzt werden.
- Aus Referenz alt → Referenz neu wird ein konstanter Zeitversatz berechnet und auf alle unterstützten Dateien im Ordner übertragen. Die zeitlichen Abstände zwischen den Aufnahmen bleiben erhalten.
- Vor jeder Änderung wird eine vollständige Vorschau mit bisherigem und künftigem Zeitstempel je Datei angezeigt. Vorschau und Anwendung sind über SHA-256, Dateigröße und einen Plan-Fingerprint gekoppelt; ein zwischenzeitlich veränderter Bestand muss neu geprüft werden.
- **Anwenden** arbeitet vollständig unabhängig vom Bibliotheksbestand: Alle Dateien werden zunächst auf Arbeitskopien geändert und mit ExifTool verifiziert und erst danach atomar am bisherigen Ort ersetzt.
- **Anwenden und in Tagesbestand übernehmen** führt dieselbe Korrektur aus und legt danach einen verifizierten globalen Importauftrag an. Der bestehende Kamera-Importpfad übernimmt Familienbildung, kanonische Tagesordner, Dateinamen, Duplikatprüfung, Registry und Projektionen.
- Der verwaltete Mehrfachkorrektur-Import darf als eng begrenzte Ausnahme aus dem Workspace lesen. Andere verschachtelte Importquellen bleiben weiterhin gesperrt.
- Nach erfolgreicher Übernahme in den Tagesbestand werden ausschließlich die tatsächlich importierten und erneut per SHA-256 bestätigten Quelldateien aus `Mehrfachkorrektur` entfernt; der Ordner selbst bleibt bestehen. Nicht unterstützte Dateien werden nicht gelöscht.
- Regressionstests sichern Ordneranlage, konstante Offset-Berechnung, Vorschau-ohne-Schreibzugriff, atomare Anwendung, Fingerprint-Invalidierung und den verwalteten Tagesbestand-Import ab.

### 0.33.6 – Reintegration von Prüffällen und Auswahl-Feinschliff

- Korrigierte Prüffälle verwenden beim Einsortieren jetzt den explizit bestätigten Zeitstempel als autoritative Quelle. Sekundäre, noch widersprüchliche EXIF-/XMP-Felder können dadurch nicht mehr dazu führen, dass eine bereits korrigierte Familie erneut unter `Ohne_Datum` landet.
- Vor der Reintegration werden ältere korrigierte Dateien auf einer Arbeitskopie nochmals auf den bestätigten Zeitstempel normalisiert. JPEG-/Bildkorrekturen schreiben dabei sowohl EXIF- als auch XMP-Zeitfelder.
- Ein Reintegrationsplan, der trotz bestätigter Korrektur wieder nach `Ohne_Datum` zeigen würde, wird nun ausdrücklich abgelehnt.
- Die Reintegration ersetzt die Quelle erst nach verifizierter normalisierter Arbeitskopie und hält eine versteckte Rückfallkopie bis zum erfolgreichen SQLite-Commit vor.
- Metadatenkarten verwenden `box-sizing:border-box`, damit Auswahlkarten unabhängig von Fensterbreite und Seitenverhältnis vollständig innerhalb ihres Containers bleiben.
- Ein normaler Klick auf eine weitere Metadatenkarte nimmt diese jetzt unmittelbar in die bestehende Auswahl auf; Shift-Bereichsauswahl und Checkbox-Abwahl bleiben erhalten.
- Regressionstests simulieren den realen Konfliktfall und sichern ab, dass eine bestätigte Familie trotzdem in einen echten Tagesbestand einsortiert wird.

### 0.33.5 – Prüffall-Workflow, Auswahl und kompakter Importverlauf

- Der globale `Ohne_Datum`-Bestand wird in der Metadatenkorrektur als eine gemeinsame Liste dargestellt; die frühere sichtbare Gruppierung nach Main Library, Business und Testbibliothek entfällt.
- Metadatenkorrektur und physische Reintegration sind bewusst getrennt. **Metadaten ändern** schreibt und verifiziert die vollständige Familie atomar, lässt sie danach aber in `Ohne_Datum`. Erst **In Tagesbestand einsortieren** verschiebt sie in den kanonischen Tagesbestand und vergibt dabei den normalen Bibliothekar-Dateinamen.
- Korrigierte Familien bleiben in `Ohne_Datum` sichtbar und tragen den Status **Bereit zum Einsortieren**. Mehrere bereits korrigierte Familien können ausgewählt und gemeinsam einsortiert werden.
- Der globale Aufgabenbereich erzeugt eine einzige fachliche Aufgabe für `Ohne_Datum`: **Prüffälle bearbeiten** bzw. **Korrigierte Aufnahmen einsortieren**. Der Link führt direkt zu `Metadatenkorrektur → Bibliothek`; technische Einzelaufträge werden dort nicht doppelt gezählt.
- Korrigierte, aber noch nicht einsortierte Familien erscheinen nicht parallel als **Noch nicht zugeordnet**.
- Die Metadatenliste unterstützt Mehrfachauswahl über Checkboxen, **Alle auswählen** und Umschalt/Shift-Bereichsauswahl. Die Auswahl kann bereits für gemeinsame Reintegration genutzt werden; die eigentliche Zeitversatz-Mehrfachkorrektur bleibt wie geplant 0.34.0 vorbehalten.
- Tagesgruppen im Arbeitsbereich unterstützen ebenfalls **Alle auswählen/Auswahl aufheben** und Shift-Bereichsauswahl.
- Der Import- und Prüfverlauf zeigt zunächst höchstens fünf Einträge. Weitere Einträge werden über **Mehr anzeigen** in Fünferblöcken eingeblendet.
- Regressionstests sichern den zweistufigen Ohne-Datum-Ablauf, die Aufgabenbündelung, Auswahlbedienung und den kompakten Importverlauf ab.
- Eine Mehrfachauswahl in der Metadatenkorrektur übernimmt denselben bewusst eingegebenen Datum-/Uhrzeitwert jetzt auf alle ausgewählten Einträge; die anschließende Einsortierung wird nur angeboten, wenn die gesamte Auswahl korrigiert und bereit ist. Dadurch kann keine Teilmenge unbemerkt im `Ohne_Datum`-Bestand zurückbleiben.
- Shift-Auswahl funktioniert in Metadatenkorrektur und Tagesordnern über die gesamte Karte, ohne dabei Browser-Text zu markieren.
- Die aktive Metadatenkarte verwendet einen innenliegenden Auswahlrahmen statt eines nach außen überstehenden Outlines.
- Die redundanten Header-Schalter **Alle Tage** und **Auswahl aufheben** wurden aus dem Arbeitsbereich entfernt; die Auswahlsteuerung sitzt direkt bei den Tagesordnern.
- Sichtbare Versionshinweise in den erklärenden Metadaten-Texten wurden entfernt.

### 0.33.4 – Startup-Backfill und Import-Worker stabilisieren

- Der globale Main-Import bleibt beim Registry-Backfill `source_kind="import"`; nur Projektionen in weitere Bibliotheksdatenbanken werden als `existing_library` registriert.
- Bereits korrekt registrierte Main-Importe können beim Neustart nicht mehr mit derselben Backup-ID als anderer Quellentyp kollidieren. Der beobachtete Startup-Fehler „Eine bestehende Backup-ID darf nicht auf einen anderen Quellentyp umgebunden werden.“ ist damit behoben.
- Ältere Main-Registry-Einträge, die vor der globalen Importarchitektur noch als `existing_library` angelegt wurden, werden nur unter eng geprüften Bedingungen auf `import` migriert; die allgemeine Schutzregel gegen Quellentypwechsel bleibt bestehen.
- Ein fehlgeschlagener Startup oder ein nicht laufender Hintergrund-Worker führt bei neuen Ordnerimporten nun zu HTTP 503 statt zu einem dauerhaft auf `queued` stehenden Auftrag.
- Regressionstests reproduzieren den realen Ablauf Importregistrierung → Neustart-Backfill → Queue-Übernahme und sichern den Degraded-/Worker-Guard ab.
- Bereits vor dem Update sauber gespeicherte `queued`-Ordnerimporte bleiben erhalten und werden nach erfolgreichem Neustart vom Worker übernommen.

### 0.33.3 – TrueNAS-sichere Metadaten-Arbeitskopien

- Die Metadatenkorrektur verwendet für ihre drei internen Kopierstellen ausschließlich `shutil.copyfile()` statt `shutil.copy2()`. Damit werden auf TrueNAS/ZFS keine Modus-, ACL- oder Ownership-Metadaten der Quelldatei auf temporäre Arbeitsdateien übertragen.
- Der bei allgemeinen Einzelkorrekturen beobachtete Fehler `[Errno 1] Operation not permitted` beim Erzeugen der versteckten `.bibliothekar-…`-Arbeitsdatei wird dadurch beseitigt.
- Derselbe Schutz gilt für Bibliothekskorrekturen: Sowohl `Ohne_Datum` → Arbeitskopie als auch verifizierte Arbeitskopie → kanonischer Zielbestand verwenden nur Nutzdatenkopien und erben die Zielordnerrechte.
- Regressionstests verbieten `shutil.copy2()` innerhalb der Metadatenkorrektur und simulieren ausdrücklich einen TrueNAS-artigen EPERM-Fehler, während die direkte allgemeine Korrektur weiterhin erfolgreich durchläuft.
- Es werden keine ACLs, Eigentümer oder Rechte gelockert; insbesondere sind keine `chmod`-/`chown`-Workarounds erforderlich.

### 0.33.2 – Direkte Metadatenkorrektur und Aufgabenbereinigung

- Die normale Einzelkorrektur wird mit **Metadaten ändern** direkt ausgeführt. Der sichere Ablauf bleibt unverändert: Ausgangszustand einfrieren, Arbeitskopie erzeugen, mit ExifTool schreiben, erneut lesen und verifizieren und erst danach atomar ersetzen bzw. eine Ohne-Datum-Familie in den kanonischen freien Bestand reintegrieren.
- Ein fehlender Import von `MetadataError` in den API-Fehlerpfaden ist behoben. Erwartbare Metadatenfehler können dadurch nicht mehr beim Exception-Matching selbst in einen nackten `Internal Server Error` kippen.
- Die Uhrzeitfelder übernehmen Sekunden vollständig (`HH:MM:SS`) statt beim Laden auf Minuten zu kürzen und damit unbemerkt `:00` zu setzen.
- Wiederholte Korrekturen derselben Datei ersetzen ältere noch nicht geschriebene Aufträge. Der ursprüngliche Metadatenzustand wird explizit im Korrekturdatensatz als Vorher-Snapshot bewahrt.
- Globale Metadatenaufgaben werden pro Bereich gebündelt. Mehrere Dateien unter **Allgemein** oder **Bibliothek** erhöhen den allgemeinen Aufgabenindikator jeweils nur um eine Bereichsaufgabe; alte vorbereitete Einzelaufträge bleiben auf der Metadatenseite kompakt einklappbar.
- Beim bibliotheksübergreifenden Lesen der Metadatenkorrektur wird das Schema jeder aktiven Bibliotheksdatenbank vor Zugriff sichergestellt. Das verhindert 500er durch noch nicht migrierte Sekundärbibliotheken.
- `0.34.0` bleibt unverändert für die Mehrfachkorrektur mit Referenzaufnahme und konstantem Zeitversatz reserviert.

### 0.33.1 – Einstellungs-UX und Metadaten-Reintegration

- Die Ereignisordner-Einstellungen sind in einklappbare Bereiche für Ordnerstruktur, normale Ereignisse und Sammelordner getrennt. Normale Ereignisse können Jahr, Uhrzeit und Von–bis im Namen unabhängig aktivieren; Sammelordner erhalten eine eigene Bezeichnung sowie optional das Jahr.
- Eine gemeinsame Live-Vorschau zeigt normales Ereignis und Sammelordner mit der aktuell gewählten Unterordnerstruktur. Die Benennungs-Checkboxen verwenden wieder kompakte Steuerelemente.
- Bibliothekskarten in den Einstellungen sind standardmäßig eingeklappt und behalten ihren geöffneten Zustand bei Speichern/Prüfen.
- Die Metadatenkorrektur verwendet wieder die vollständige Bibliothekar-Shell. Bibliothek, Allgemein und die für 0.34.0 vorgemerkte Mehrfachkorrektur liegen im normalen zweiten Reiterheader.
- Der 0.33.0-Entwurf mit `Metadatenkorrektur/Bibliothek/<id>/Eingang/Ausgang` und separatem Allgemein-Host-Path ist verworfen. `Allgemein` liegt verwaltet unter `/workspace/Metadatenkorrektur/Allgemein`; technische IDs wie `main` erzeugen keine Dateisystemordner.
- Der Bereich Bibliothek liest freie Kamera-Familien direkt aus dem globalen `Ohne_Datum`-Bestand und gruppiert sie nach ihrer Herkunftsbibliothek. Korrekturen werden familienweise auf Arbeitskopien geschrieben, erneut gelesen und geprüft und anschließend in den kanonischen Tages-/Zeitbestand zurückgeführt.
- Metadatenkorrekturen aktualisieren aktuelle Dateigröße, SHA-256, Aufnahmezeit und Pfad in sämtlichen Bibliotheksprojektionen, während der ursprüngliche Quellfingerprint über die neue persistente `source_size_bytes`-Spalte stabil bleibt.
- Leere 0.33.0-Metadaten-Unterordner dürfen automatisch bereinigt werden; Ordner mit Nutzerdateien werden niemals automatisch gelöscht.
- Migration 045 konserviert die ursprüngliche Quellgröße für spätere Metadatenänderungen. 0.34.0 bleibt für die Mehrfachkorrektur mit Referenzaufnahme und konstantem Zeitversatz reserviert.

### 0.33.0 – Ereignisbenennung und sichere Metadatenkorrektur

- „Ohne Ereignis“ erhält pro Bibliothek eine frei wählbare sichtbare Bezeichnung. Die Bezeichnung wird beim Erstellen in Button, Monats-Sammlung und Ordnername verwendet; bereits bestehende Ereignisse übernehmen keine neue Vorlage rückwirkend. Vor 0.33 angelegte Ereignisse behalten bei späteren bewussten Bearbeitungen ihre bisherige Benennungslogik.
- Die Benennung neuer normaler Ereignisordner ist bibliotheksspezifisch konfigurierbar: nur Startdatum oder Von–bis, optional mit Jahr sowie optional mit Uhrzeit. Jede neue Planung speichert dafür einen eigenen Benennungs-Snapshot.
- Der Bereich „Metadatenkorrektur“ ist als echte Oberfläche verfügbar und trennt „Bibliothek“ von „Allgemein“. Bibliotheksdateien verwenden einen eigenen Eingang/Ausgang unter dem Bibliothekskontext; „Allgemein“ verlangt einen separaten read-write TrueNAS-Host-Path.
- Dateinamen werden zusätzlich zu EXIF/XMP/QuickTime-Metadaten ausgewertet. Unterstützt werden unter anderem kameraartige `YYYYMMDD_HHMMSS`-Namen, ISO-artige Zeitstempel sowie WhatsApp-/Signal-nahe Datumsnamen. Ein Dateiname mit nur Datum führt bewusst nicht zu einer geratenen Uhrzeit.
- Metadatenänderungen sind zweistufig und transaktional: Vorbereitung friert Pfad, Größe und SHA-256 ein; „Schreiben & prüfen“ arbeitet zunächst auf einer Kopie, schreibt mit ExifTool, liest die Werte erneut, verifiziert sie und ersetzt erst danach atomar den Ausgang. Die Eingangsdatei wird erst nach erfolgreicher Prüfung entfernt.
- Schreib-/Prüffehler hinterlassen die Eingangsdatei unverändert und erzeugen einen sichtbaren blockierten Metadatenauftrag. Offene Metadatenkorrekturen erscheinen außerdem in der globalen Aufgabenliste der aktuellen Bibliothek.
- Neue Migration 044 ergänzt Ereignis-Benennungs-Snapshots und persistente Metadatenkorrektur-Aufträge. Regressionstests decken Benennungsvarianten, benutzerdefinierte Monats-Sammlungen, Dateinamenerkennung, sicheren Erfolgspfad und Fehler-Rollback ab.


### 0.32.11 – Applied-Änderungen über Bibliotheksgrenzen absichern

- Angewendete Ereignisse lösen Quellen bei Bearbeiten, Erweitern, Verkleinern und Löschen konsequent aus dem konfigurierten Bibliotheks-Arbeitsbereich oder dem globalen Central Stock auf. Freier Kamerabestand bleibt unter SD-Kartensicherungen; freigewordener Archivbestand bleibt unter „Freigewordene Archivdateien“.
- Globale Besitz-Claims bleiben während einer noch nicht physisch bestätigten Applied-Änderung erhalten. Ein Neustart oder Claim-Abgleich kann herausfallende bzw. zur Löschung vorgemerkte Familien nicht mehr vorzeitig für eine andere Bibliothek freigeben oder auf „reserviert“ zurückstufen.
- Strukturelle Ereignisänderungen reservieren neu hinzukommende Familien atomar in der globalen Registry, bevor SQLite verändert wird. Damit kann eine zwischen UI-Anzeige und Speichern entstandene Reservierung einer anderen Bibliothek nicht zu einer inkonsistenten Applied-Änderung führen.
- Die Archiv-Lösch-/Änderungswege bleiben getrennt: Erst nach SHA-verifizierter Rückholung in „Freigewordene Archivdateien“ und bestätigtem Abschluss werden dort Besitz-Claims freigegeben.
- Neue Regressionstests durchlaufen eine Sekundärbibliothek vollständig: Apply → Verkleinern → Central Stock → Erweitern → Bibliotheks-Arbeitsbereich → Löschen → vollständiger freier Tagesbestand sowie Claim-Erhalt bis zum physischen Abschluss.
- Der Bearbeiten-Kontext ist jetzt bibliotheksweit statt sicherungsbezogen. Eine Erweiterung eines angewendeten Ereignisses kann deshalb freie Familien aus einer anderen SD-Kartensicherung desselben Bibliotheksbestands aufnehmen; dasselbe gilt für neue Tagessegmente von „Ohne Ereignis“.
- Ein inkonsistenter Altzustand mit freiem Bestand innerhalb eines bereits belegten Ereigniszeitraums lässt den Nachsortierdialog nicht mehr scheinbar hängen: der Read-only-Plan liefert einen eindeutigen Blocker und die Oberfläche zeigt den Fehler sichtbar an.


### 0.32.10 – Kanonischer Tagesbestand über mehrere Sicherungen

- Beim ersten Anwenden eines Teilzeit-Ereignisses wird der freie zentrale Tagesbestand jetzt sicherungsübergreifend normalisiert. Freie Dateien aus weiteren Sicherungen desselben Tages werden in die tatsächlichen Randintervalle verschoben; ein paralleler unspezifischer Ganztagesordner bleibt nicht mehr zurück.
- Später importierte freie Aufnahmen werden bereits beim Import gegen die physische Ereignis-Timeline eingeordnet. Liegen sie außerhalb eines angewendeten/archivierten Ereignisses, landen sie direkt im passenden kanonischen freien Zeitordner statt erneut in einem vollständigen Tagesordner.
- Liegt eine später importierte Aufnahme innerhalb eines bereits belegten Zeitraums, bleibt die bestehende Ereignis-Vorschlags-/Bestätigungslogik maßgeblich; die Datei wird nicht ungefragt einem Ereignis zugeordnet.
- Regressionstests decken den Mehrsicherungs-Apply, den späteren Import in bestehende Randintervalle und die Zuordnungsvorschläge für tatsächlich in den Ereigniszeitraum fallende Folgeaufnahmen ab.
- Wird ein angewendetes Teilzeit-Ereignis wieder gelöscht, löst der Reconcile Quellen nun dateiweise aus Bibliotheks-Arbeitsbereich oder globalem Central Stock auf. Die vorherigen Randintervalle werden wieder in den kanonischen freien Tagesordner zusammengeführt; leer gewordene Intervallordner werden nach verifizierter Verschiebung entfernt.


### 0.28.1-ui1 – Deep-Test UI/Workflow-Zwischenpatch

- Eine aktive Ereignis-Unterordnerstruktur benötigt jetzt serverseitig zwingend einen vorhandenen Input-Ordner; ohne Unterordner ist „Direkt im Ereignis“ der kanonische Input.
- „Manuelle Ereignisänderung“ bündelt Ordner- und Dateiänderungen in zwei einklappbaren Bereichen, damit große Änderungen kompakt bleiben.
- Im Archivworkflow bleibt der beim Vorbereiten gewählte Input-Ordner über die Folgeschritte sichtbar und unveränderlich; er wird nicht mehr scheinbar zurückgesetzt.
- Abgeschlossene Strukturaufgaben verschwinden sofort aus „Aufgaben“; der Struktur-Aufgabenparameter wird aus der URL entfernt und abgeschlossene Aufgaben öffnen sich nach Reload nicht erneut.
- Die Karte „Neue Aufnahmen passen zu bestehenden Ereignissen“ ist bündig zur übrigen Arbeitsbereichsbreite formatiert.


### 0.28.1 – Deep-Test-Korrekturen für Ereignisordner

- Speichern der globalen Ereignisordner-Vorlage funktioniert wieder; die API verwendet die UTC-Zeit korrekt und die Oberfläche zeigt bei unerwarteten Serverantworten keine rohe JSON-Parse-Meldung mehr.
- Umbenennen des aktuell gewählten Input-Ordners hält dessen Pfad in der noch nicht gespeicherten Vorlage synchron.
- Änderungen der globalen Vorlage gelten weiterhin ausschließlich für künftig erzeugte Ereignisse; bestehende Ereignis-Snapshots und deren `event.json` werden nicht rückwirkend verändert.
- Zielstruktur-Vorschauen gespeicherter, geplanter und angewendeter Ereignisse verwenden jetzt deren konkreten Ordner-Snapshot. Bei „Unterordner erstellen“ AUS werden `Alle / Sortiert / Export` nicht mehr fälschlich angezeigt.
- Der Einstellungsdialog stellt „Unterordner standardmäßig erstellen“ und „Direkt im Ereignis“ kompakt einzeilig mit normal großen Checkbox-/Radio-Steuerelementen dar.
- Eine im Einstellungsdialog gespeicherte neue Standardvorlage wird auf der geöffneten Arbeitsbereich-Seite sofort für den nächsten Ereignisdialog übernommen.


### 0.26.9 – verbindliche Applied-Transaktionen und statischer Arbeitsbereich

- Bearbeiten und Löschen bereits angewendeter Ereignisse sind jetzt verbindliche Transaktionen: Nach der Definition öffnet sich unmittelbar der vorhandene SHA-geprüfte Arbeitsbereich-Abgleich. Dieser Zustand kann nicht auf später vertagt werden; oben steht nur „Änderungen verwerfen“, unten wird der Zielplan bestätigt und angewendet.
- Herausfallende Familien müssen vor einer Applied-Änderung nicht mehr neu zugeordnet werden. Der bestätigte Abgleich führt sie direkt in den kanonischen freien Tages-/Zeitbestand zurück. Dort bleiben sie als aus einer Bearbeitung freigewordene Bereiche gelb erkennbar, erzeugen aber keine Neu-Zuordnungs- oder Nachsortierungsaufgabe.
- Das Löschen eines Applied-Ereignisses verwendet denselben verpflichtenden Ablauf. Nach erfolgreicher Bestätigung wird das Ereignis wirklich entfernt und seine Dateien werden in den freien Arbeitsbestand zurückgeführt; ein Verwerfen stellt den vorherigen Zustand wieder her.
- Leere Unterereignisse sind ausdrücklich zulässig. Vor Erstellen oder Bearbeiten warnt die App, wenn aktuell keine passende Dateifamilie vorhanden ist; nach bewusster Bestätigung wird die vollständige leere Zielstruktur mit `Alle`, `Sortiert` und `Export` trotzdem angelegt.
- Zielstruktur-Vorschauen und Ereignis-Inspektor behalten lange Baumzeilen auf einer Zeile und verkleinern die Monospace-Schrift bei Bedarf statt die Ordnerbezeichnung umzubrechen.
- Unterereignisse im Bearbeiten-Dialog zeigen Name, Beginn/Startzeit und Ende/Endzeit wieder in getrennten, ausreichend breiten Feldern.
- Die Scroll-/Morph-Animation der Auswahlleiste entfällt vollständig. Ihr bisheriger Endzustand ist auf Desktop nun von Anfang an der feste Zustand im Workspace-Unterheader; „x Gruppen ausgewählt“ bleibt direkt unter dem Hauptreiter „Arbeitsbereich“ zentriert.
- Die vier Kennzahlen Tage, Dateien, Familien und Prüffälle stehen kompakt neben der Überschrift „Aufnahmen“, sodass Tagesordner und Zielstruktur deutlich früher beginnen.
- Das Aufgaben-Popup wird beim Öffnen in die oberste Dokumentebene verschoben. Dadurch bleiben Workspace-Aktionsbuttons über dem dekorativen Header-Überstand sichtbar, während „Offene Aufgaben“ selbst weiterhin über allen Bedienelementen liegt.
- Die sichere Grundregel bleibt unverändert: Keine physische Applied-Änderung erfolgt ohne den explizit bestätigten, blockerfreien und SHA-256-geprüften Abgleich; 0.26.9 beseitigt lediglich den unsicheren bzw. verwirrenden „später erledigen“-Zwischenzustand.

### 0.26.8 – Applied-Reconcile, Zustandsklarheit und Sortierplan

- Dialogfehler werden nur noch im roten Fehlerfeld gezeigt; die grüne Statusbox ist wieder ausschließlich positiven Meldungen vorbehalten.
- Applied-Ereignisse mit noch offener physischer Nachsortierung zeigen im Arbeitsbereich zusätzlich zum Badge „Angewendet“ den sichtbaren Badge „Nachsortierung ausstehend“.
- Das geöffnete Aufgaben-Popup hebt den App-Header temporär über Sticky-Unterleiste und Auswahl-Morph, damit Aufgaben nie von „Ohne Ereignis“/„Ereignis“ oder anderen Dock-Elementen überdeckt werden.
- Der Text „x Gruppen ausgewählt“ zielt beim Desktop-Morph nicht mehr auf die geometrische Fenstermitte, sondern exakt auf die Mitte des Reiters „Arbeitsbereich“ und bleibt dort auch im eingerasteten Zustand ausgerichtet.
- Der Nur-Lesen-Dialog eines Ereignisses führt „Bearbeiten“ nun oben rechts direkt neben „Schließen“; die zusätzliche untere Aktionszeile entfällt.
- Der Nachsortierplan dedupliziert identische Hinweise. Die Bestätigungskarte ist kompakter: Hilfe steckt im bekannten Fragezeichen-Tooltip, der Anwenden-/Schließen-Button sitzt oben rechts und die Checkbox-Zeile ist vertikal sauber ausgerichtet.
- „Bestehendes Ereignis erweitern“ ist jetzt ein enger Schnellweg statt eines zweiten Bearbeiten-Dialogs: angeboten wird nur unmittelbar nach dem bisherigen Ende angrenzende freie Zeit. Beginn/Start bleiben fest, nur der neue Endpunkt kann innerhalb der ausgewählten freien Zeit gesetzt werden; Zeitmodus, Tagesordnerlogik und Unterereignisse werden unverändert vom bestehenden Ereignis übernommen.
- Dieselbe End-only-Regel wird serverseitig validiert, damit Rückwärts-Erweiterungen oder Lücken nicht über direkte API-Aufrufe umgangen werden können.
- Nach erfolgreicher Applied-Nachsortierung bleiben die verwalteten Standardzweige `Alle`, `Sortiert` und `Export` am aktiven Ziel erhalten. Der Cleanup entfernt leere Standardzweige eines weiterhin aktiven Ereignis-/Tagesziels nicht mehr; fremde oder nichtleere Inhalte werden weiterhin niemals gelöscht.
- Applied-Ereignisse bleiben fachlich „angewendet“. Während einer offenen Änderung unterscheidet die Oberfläche jetzt klar zwischen „Neu-Zuordnung offen“ und „Nachsortierung offen“, statt pauschal „Änderung noch nicht angewendet“ zu melden.
- Neu erzeugte geplante Ziele einer Applied-Neu-Zuordnung werden nicht mehr als unabhängig anzuwendende Planung angeboten. Sie werden als Ziel der gemeinsamen Nachsortierung markiert und führen direkt zum Reconcile des Ursprungsereignisses; die globale Aufgabenliste erzeugt dafür keinen doppelten Planned-Apply-Auftrag.
- „Bestehendes Ereignis erweitern“ bleibt für regulär freie, direkt angrenzende Bereiche erhalten. Bei freigewordenen Bereichen einer Applied-Bearbeitung wird diese Option ausgeblendet, damit die Neu-Zuordnung nicht versehentlich wieder in das gerade verkleinerte Ereignis zurückführt.
- Der gemeinsame Nachsortierplan zeigt eine echte Zielordner-Baumstruktur aus den geplanten Verzeichnissen statt der technischen Zusammenfassung „Gemeinsamer Arbeitsbereich-Abgleich“.
- Das Sortierplan-Modal ist auf Desktop breiter; seine sieben Kennzahlen passen auf eine Zeile. Sicherheitsstatus, Arbeitsbestand und Zielstruktur sind ein-/ausklappbar, die Zielstruktur ist standardmäßig geöffnet.
- Nach erfolgreicher Sortierung/Nachsortierung wird die Ereignisliste sofort vollständig neu geladen. Der veraltete Hinweis auf eine offene Änderung verschwindet ohne Browser-Reload; der untere Anwenden-Button wird anschließend zu „Schließen“.
- Auf der Seite „Ereignisse“ besitzt die sticky Arbeitsbereich-Unterleiste einen deckenden Seitenhintergrund und läuft beim Scrollen nicht mehr transparent über den Seitentitel.
- Die 0.25.1-Sicherheitsarchitektur bleibt unverändert: Applied-Bearbeitungen speichern zunächst SOLL-Zustand und Aufgaben; physische SSD-Bewegungen erfolgen erst im ausdrücklich bestätigten, SHA-geprüften gemeinsamen Reconcile.

### 0.26.7 – Planned-UI-Abschluss und konsistentes Ereignismodell

- „Ohne Ereignis“ zeigt in der Zielstruktur-Vorschau keinen irreführenden Min/Max-Zeitraum mehr, sondern „Datenbank-Zeitraum: komplex“.
- Die doppelte Liste „Gespeicherte Ereignisse“ wurde aus „Aufnahmen“ entfernt; Ereignisse bleiben in der Tagesansicht sichtbar und werden vollständig im Reiter „Ereignisse“ verwaltet.
- Auf Desktop bleibt die Arbeitsbereich-Navigation beim Scrollen unter dem Hauptheader sichtbar. Die Auswahlleiste morpht erst bei ihrer tatsächlichen Annäherung an den Sekundärheader scrollgebunden und kontinuierlich: Abstände/Höhe reduzieren sich über die letzten 128 px, Rahmen und Kartenfläche blenden erst unmittelbar vor dem Einrasten aus. Auf schmaleren Desktopfenstern darf sie umbrechen; mobil bleibt unverändert. Die Aufnahmen-Seite erhält unten zusätzliche Scroll-/Atemreserve. Der Endzustand wird ohne DOM-Umhängen erreicht; die Auswahlleiste bleibt über den gesamten Weg geometrisch kontinuierlich, die 64-px-Pfeilreserve bleibt erhalten und der transparente Endzustand kann nicht mehr durch die globale Kartenregel zurückspringen. Im Arbeitsbereich ist der Seitenfarb-Überstand des Hauptheaders wieder aktiv, um die Registerkante sauber zu maskieren; der Sekundärheader sitzt dafür etwas tiefer und ist etwas höher. Die Auswahlleiste folgt nun einer gekrümmten Bahn: horizontal läuft sie früh voraus, vertikal zieht sie zunächst nur wenig und später stärker nach oben. Rahmen und Kartenfläche beginnen bereits in der mittleren Phase auszufaden. Buttons, Pfeil, Abstände und Schrift werden sanfter und weniger stark verkleinert. Während des Morphs liegt die Auswahlleiste gezielt über der Hauptheader-Bridge, damit Buttons und Pfeil nicht mehr abgeschnitten werden. Die Zusammenfassung „X Gruppen ausgewählt“ endet responsiv exakt in der horizontalen Seitenmitte unter „Arbeitsbereich“; die linke Rahmenkante folgt ihr nun während des gesamten Morphs mit konstantem Innenabstand und endet im Zielzustand direkt vor dem Text.
- „Ohne Ereignis“ verwendet beim Erstellen, Fortführen und Bearbeiten ausschließlich echte Tages-/Zeitsegmente. Die frühere Zeitspannen-/Zeitblock-Auswahlhilfe wurde entfernt.
- Beim Fortführen einer bestehenden „Ohne Ereignis“-Sammlung sind vorhandene Segmente reine Information und können dort weder geöffnet, geändert noch entfernt werden. Änderungen erfolgen ausschließlich über „Ereignisse → Bearbeiten“.
- Der Nur-Lesen-Inspektor zeigt große „Ohne Ereignis“-Sammlungen portionsweise: zunächst zehn Segmente, danach über „Weitere“. Dateifamilien nach Aufnahmetag sind standardmäßig eingeklappt und werden ebenfalls in Zehnerpaketen nachgeladen.
- Fehler beim Speichern eines Ereignisses erscheinen im geöffneten Bearbeitungsdialog statt hinter dem Modal.
- Bei normalen Ereignissen stehen Startzeit direkt neben Beginn und Endzeit direkt neben Ende.
- Neue Ereignisse können bereits beim Erstellen mehrere echte Unterereignisse mit eigenem Namen sowie Beginn/Ende und Uhrzeiten erhalten. Lücken zwischen Unterereignissen bleiben beim Oberereignis; Verschachtelung ist nicht vorgesehen.
- Der Erstellen-Dialog ordnet Beginn/Startzeit und Ende/Endzeit nun in zwei eigenen Zeilen an. Unterereignisse erhalten Name, Beginn/Startzeit sowie Ende/Endzeit in getrennten Zeilen; „Unterereignis entfernen“ sitzt in der Endzeile. Der erklärende Hilfstext entfällt, der Hinzufügen-Button bleibt kompakt einzeilig und der Dialog erhält etwas mehr Breite.
- Die fachliche Planned-Logik bleibt unverändert. 0.26.7 bündelt die im manuellen Planned-Regressionslauf PR1–PR10 vereinbarten UI- und Bedienverbesserungen.


### 0.26.5 – XMP-sichere Nachsortierung und Kartenbewegung

- Nachträglich erzeugte Lightroom-XMPs werden bei der Nachsortierung eines angewendeten Ereignisses live im aktuellen SSD-Ereignisbestand erkannt und über Stem/Familie an ihre Kamerafamilie gebunden.
- Reapply liest den noch physischen Ereignisordner aus dem gespeicherten Ursprungszustand einer offenen Änderung. Damit bleibt die Nachsortierung auch dann sicher, wenn Name oder Ereignisordner im SQLite-SOLL bereits geändert wurden.
- Manuell zwischen `Alle` und `Sortiert` verschobene Kameraoriginale behalten bei einer Nachsortierung ihren aktuellen Arbeitszweig. XMPs folgen dem eindeutigen Ziel ihrer Familie bzw. dem passenden Zweig.
- XMP-Bewegungen erhalten ein eigenes persistentes Reapply-Journal mit Größe, SHA-256, Quell-/Zielpfad und Status. Verifikation, Rollback und Wiederanlauf behandeln sie damit genauso transaktional wie Kameraoriginale, ohne künstliche `files`-Datensätze anzulegen.
- Uneindeutige XMP-Familien oder -Ziele werden nicht geraten, sondern blockieren die Nachsortierung sichtbar.
- Die drei Hauptreiter `Import & Prüfung`, `Arbeitsbereich` und `Archiv` werden beim Hover leicht angehoben und beim Klick noch etwas weiter angehoben. Die bisherige Helligkeitsänderung entfällt; der Zielreiter kommt nach dem Seitenwechsel weich in seine aktive Position.
- Nutzer mit reduzierter Bewegungsdarstellung erhalten weiterhin eine animationsfreie Navigation.


### 0.26.4 – Ereignis-Inspektor und konsistente Karten-UI

- Die Zielstruktur-Vorschau erhält wieder eine echte mehrzeilige Baumdarstellung; gespeicherte Ereignisse zeigen zusätzlich die in SQLite persistierten Zeitgrenzen, Status, Tagesordnerlogik sowie Unterereignis-/Segmentanzahl.
- Vorhandene Ereignisse im Arbeitsbereich sind im Ruhezustand neutral grau und werden erst bei Auswahl blau hervorgehoben. Damit ist eindeutig sichtbar, welches Ereignis die rechte Vorschau steuert.
- Aufklappbare UI-Bereiche verwenden die vorhandene Kartenlogik ohne zusätzliche Disclosure-Dreiecke. Das betrifft insbesondere „Auswahl anpassen“ sowie Zeitspanne, Zeitblöcke und Tagessegmente bei „Ohne Ereignis“.
- Im Reiter „Ereignisse“ klappt die ganze Ereigniskarte die Aktionen auf. Der separate „Öffnen“-Disclosure mit Dreieck entfällt.
- „Öffnen“ zeigt Ereignisse zunächst schreibgeschützt: Datenbank-Beginn/-Ende, Status, Tagesordner, Unterereignisse bzw. „Ohne Ereignis“-Segmente, Zielstruktur und kompakte Dateifamilien nach Aufnahmetag. Erst „Bearbeiten“ wechselt in den bestehenden Editor.
- Der Bearbeitungsmodus erhält einen dezenten rötlichen Hintergrundakzent, damit reine Einsicht und aktive Änderung visuell klar getrennt sind.
- Die Struktur-API liefert neben dem Baum nun die persistierten Ereignisfakten, damit die UI keine Zeitgrenzen aus Dateinamen oder Ordnerpfaden rekonstruieren muss.
- Die fachliche Ereignis-/Zeitlogik bleibt unverändert; 0.26.4 ist ein UI-/Einsehbarkeits-Patch auf Basis von 0.26.3.


### 0.26.3 – Ereignis-Inventur, XMP/Export und aktueller Archiv-IST

- `Alle`, `Sortiert` und `Export` sind keine dauerhaft vorgeschriebenen Dateipositionen mehr. Kameraoriginale werden innerhalb des aktuellen Ereignisordners anhand ihrer Identität wiedergefunden; der konkrete Pfad ist nur der zuletzt beobachtete IST-Ort.
- Vor jeder Bearbeitung eines archivierten Ereignisses wird dessen realer Ordner read-only neu gescannt. Manuell später gelöschte Archivdateien werden nicht zurückgefordert; der aktuelle Bestand ist die Grundlage des neuen IST→SOLL-Auftrags.
- Der Scanner erfasst XMP-Sidecars, Exporte und weitere aktuelle Ereignisdateien. XMP wird bei eindeutigem Stem einer Ursprungsdatei oder – bei RAF+JPEG – der gemeinsamen Kamerafamilie zugeordnet.
- Für neue Bild-/Exportdateien wird die vorhandene Metadatenlogik genutzt: echte Aufnahmeinformationen wie DateTimeOriginal haben Vorrang vor Erstell-/Dateisystemzeiten. Unklare Zuordnungen werden nicht geraten und blockieren den manuellen Abschluss sichtbar.
- Archivänderungsaufträge beziehen aktuelle XMP-/Exportdateien ein und erhalten die vorhandene Arbeitsstruktur `Alle`/`Sortiert`/`Export`, auch bei Neu-Zuordnungen.
- Die SSD-Freigabe prüft jetzt den gesamten aktuellen Ereignisbestand. Kameraoriginale, XMPs, Exporte und weitere reguläre Dateien müssen vor dem Löschen der SSD jeweils als echte SHA-identische Datei im Archiv vorhanden sein; ihre Unterordnerposition darf zwischen SSD und Archiv abweichen.
- Symlinks bleiben in allen Ereignis- und Archivprüfungen strikt unzulässig. Die Kamerabibliothek bleibt bei Archivänderungen vollständig read-only.

### 0.26.2 – Logikhärtung nach vollständigem Konsistenz-Audit

- Archivnachweise akzeptieren keine Symlinks mehr: erwartete Archivpfade und ihre vorhandenen Komponenten werden mit `lstat` geprüft, bevor SHA-Prüfung oder SSD-Freigabe möglich sind.
- Abgeschlossene manuelle Archivänderungen aktualisieren neben dem exakten Archivnachweis auch den allgemeinen aktuellen Dateipfad; Folgeprüfung, weitere Änderung und Löschplanung verwenden dadurch wieder dieselbe Pfadwahrheit.
- Bestätigte manuelle Archivaufträge können nur verworfen werden, wenn der ursprüngliche Archivzustand vollständig per Größe und SHA-256 nachgewiesen ist und am neuen Ziel noch keine manuelle Änderung erkannt wird.
- Fehlende Legacy-SHA-256-Werte reichen auch bei passender Dateigröße nicht mehr für eine erfolgreiche Archivänderungsprüfung.
- Reine Name-/Notizänderungen angewendeter Ereignisse werden anhand einer kanonischen Struktur verglichen und lösen nicht mehr unnötig Mutation und Nachsortierung aus.
- `resort_required` sperrt Archivprüfung und SSD-Freigabe bereits fachlich und wird in der Archivübersicht als Blocker ausgewiesen.
- Spätere Import-Jobs können normale bibliotheksweit belegende Ereignisse als explizites Ziel erreichen. Die Dateien bleiben Eigentum ihres Import-Jobs und werden über einen lokalen verknüpften Nachtrag angebunden.
- Der ältere direkte Reassignment-Pfad übernimmt bei `Ohne Ereignis` die Tagesordneroption wieder korrekt; Cross-Job-Fortführungen erben die Einstellung der kanonischen Monatssammlung.
- Unterbrochene Sortier-/Reconcile-Läufe werden beim Start anhand des persistierten Journals konservativ auf den letzten DB-IST-Zustand zurückgerollt. Eindeutige Fälle werden wieder freigegeben; mehrdeutige Dateizustände bleiben bewusst gesperrt.
- Neue 0.26.2-Regressionstests decken Symlink-Freigabe, Archivpfad-Fortschreibung, sicheren Auftragsabbruch, fehlende Hashes, UI-Metadatenvergleich, Cross-Job-Nachträge, Wiederanlauf sowie Archiv-/Nachsortierungssperren ab.

### 0.26.1 – UI-Feinschliff für Neu-Zuordnung, Unterereignisse und Vorschau

- Neu-Zuordnungsdialog gibt der Aktion „In Aufnahmen öffnen“ mehr Abstand zur Segmentkarte.
- „Öffnen“ auf Ereigniskarten verwendet in geschlossenem und geöffnetem Zustand dieselbe Einrückung und einen stabilen eigenen Marker.
- Unterereignisse im Editor haben konsistente Abstände; ihr Aufklapptitel zeigt live den eingegebenen Namen und der Entfernen-Button ist vom Zeitraumfeld getrennt.
- Die Zielstruktur-Vorschau zeigt Tagesgruppen kompakt und standardmäßig eingeklappt. Familien erscheinen erst nach dem Öffnen eines Tages; Stem und Aufnahmezeit bleiben pro Familie in einer einzeiligen, responsiven Zeile.

### 0.26.0 – Kanonischer freier Bestand und vollständige Ereignis-Nachsortierung

- Freie Aufnahmen erhalten aus der bibliotheksweiten Belegung aller aktiven Ereignisse, auch über mehrere Import-Jobs und „Ohne Ereignis“-Segmente hinweg, kanonische Tages-/Zeitordner. Bestätigte Sortierungen normalisieren betroffene freie Dateien und entfernen nur bekannte leere Altordner; fremde Inhalte bleiben erhalten. Kollisionen und Dateifehler rollen sicher zurück.
- Applied-Verkleinerung, -Erweiterung und vollständige Löschung speichern zunächst nur den SOLL-Zustand. Erst der ausdrücklich bestätigte SHA-geprüfte Reconcile bewegt Dateien. Herausfallende Familien bleiben bis zur fachlichen Neu-Zuordnung als Aufgabe erhalten; interne `pending_delete`-Quellen werden erst nach erfolgreicher Anwendung aller Ziele entfernt.
- Neu-Zuordnungen funktionieren über freie Karten bis zur physischen Anwendung, auch für bestehende Cross-Job-„Ohne Ereignis“-Sammlungen. Neue Ereignisse übernehmen `preserve_day_folders` explizit mit AN oder AUS; die frühere automatische Mehrtages-Sonderregel entfällt.
- `event.json` bleibt während offener Applied-Mutationen am IST-Ort und wechselt erst nach erfolgreichem Reconcile zum neuen Namen, Datum oder Jahr. Ein Mutationsabbruch hinterlässt keine neue SOLL-Struktur.
- Archivänderungen bleiben rein lesende IST→SOLL-Aufträge bis zur manuellen Dateiaktion und Verifikation. Herausfallende Familien benötigen ein explizites Ziel; auch eine vollständige Archivlöschung legt nichts stillschweigend unter „Später zuordnen“ ab. Teilzeit, Segmente und Tagesordner werden berücksichtigt; Konflikte lösen keine Cascade aus.
- Im Arbeitsbereich steht der gelbe Aufgabenpunkt direkt am Tages-/Zeittitel; Aufnahmezeiten mit Familie/Stem stehen in der rechten Vorschau. Ereigniskarten und Editor haben korrigierte Einrückung, Schaltflächen, Dialogschließung und direkte Navigation zu Aufnahmen.

### 0.25.1 – Applied-Dateien erst beim bestätigten Reconcile verschieben

- Behebt F01: Das Verkleinern eines angewendeten Ereignisses verschiebt herausfallende Dateien nicht mehr vorzeitig nach „Nicht zugeordnet“.
- Applied-Bearbeitungen speichern Definition, Freigaben und Neu-Zuordnungsaufgabe; physische Dateibewegungen erfolgen erst im ausdrücklich bestätigten Workspace-Reconcile.
- Regressionen prüfen den unveränderten Dateipfad für normale Ereignisse und „Ohne Ereignis“ sowie den vollständigen Reconcile-Ablauf mit gesetztem Workspace-Pfad.
- Die ältere Neutralisierungs-/Restore-Unterstützung bleibt für bereits begonnene Legacy-Mutationen erhalten.

### 0.25.0 – kontinuierliches Ereignismodell

- Normale Ereignisse belegen exakt einen durchgehenden Start-/Endbereich; Uhrzeiten erzwingen kein Unterereignis. Optionale organisatorische Unterereignisse ändern die Belegung nicht.
- Freie Karten stellen exakte Intervalle dar, übernehmen ihre Grenzen in die Dialoge und zeigen Aufnahmezeiten pro Familie. Angrenzende Bereiche erweitern bestehende geplante oder angewendete Ereignisse.
- „Ohne Ereignis“ erhält alle getrennten Tages-/Zeitsegmente, korrekte Bereichstitel und segmentbasierte Zusammenfassungen.
- Konflikte lösen keine Cascade aus. Neu-Zuordnungsaufgaben informieren und führen zu Aufnahmen; angewendete Änderungen benötigen weiterhin einen ausdrücklich bestätigten Nachsortierplan.
- Archivänderungen bleiben im IST→SOLL-Workflow. Version 2 von event.json enthält alle Unterereignisse, Segmente und exakten Grenzen. Verifizierte Nachsortierung entfernt ausschließlich bekannte, obsolete leere Strukturen.
- Disjunkte Legacy-Ereignisse bleiben unverändert lesbar und werden für unsichere Konvertierungen gesperrt. Positive Aktionen sind blau; destruktive Aktionen rot.

### 0.24.1 – applied-/Neu-Zuordnungsblock aus Astra-Audit

- Mutationsabbruch stellt nur tatsächlich veränderte Ereignisgraphen wieder her und löscht bestehende Root-Ereignisse nicht mehr; unabhängige Sortier- und Archivnachweise bleiben erhalten
- applied-Strukturvergleich erkennt ein vorhandenes Einzel-Unterereignis auch bei altem Parent-Flag sowie Änderungen der Tagesordner bei „Ohne Ereignis“ als strukturell
- „Ohne Ereignis“ darf beim Bearbeiten keine von normalen Ereignissen belegten Zeitsegmente überdecken
- Neu-Zuordnung erzwingt vollständige persistierte Tages-/Zeitsegmente und zeitlich passende bestehende normale Zielereignisse
- globale Neu-Zuordnungsaufgaben öffnen den kanonischen Ereignisdialog mit exakten Segmenten und vollständigen Zielarten
- applied-Nachsortierung wird nicht mehr automatisch ausgeführt: der konkrete Reconcile-Plan wird angezeigt und muss ausdrücklich bestätigt werden
- gezielte Regressionstests für A04, A07, A08, A09, A10 und A11 ergänzt

### 0.24.0 – erster Audit-Sicherheitsblock

- Reconcile prüft unmittelbar vor der Ausführung erneut, ob der aktuelle Plan weiterhin blockerfrei ist
- ein nachträglicher Zielkonflikt kann nicht mehr trotz unverändertem Plan-Token als erfolgreicher Reconcile enden
- Fehler beim nachgelagerten Schreiben von `event.json` lösen nach erfolgreichem DB-Commit keinen Dateisystem-Rollback mehr aus; der konsistente Sortierzustand bleibt bestehen und die Dokumentstörung wird protokolliert
- Neutralisierung protokolliert eine bereits erfolgte Dateibewegung vor der Ziel-SHA-Prüfung, sodass auch ein unmittelbar folgender Prüffehler sicher zurückgerollt wird
- der bisher falsch-grüne Reapply-Erfolgstest verwendet jetzt reale Migrationen, eine reale Datei und verbindliche Assertions
- der dadurch sichtbar gewordene reale Reapply-SQL-Fehler (falsche Bindungszahl beim Anlegen des Nachsortierlaufs) ist behoben
- `Ereignis anwenden` im Arbeitsbereich besitzt einen expliziten blauen UI-Override
- gezielte Regressionstests für die Auditbefunde A01, A02, A03 und C01 ergänzt

### 0.23.1 – kleiner UI-/UX-Patch nach M1 A/B

- positive Hauptaktionen im Arbeitsbereich sind blau: Ereignis speichern/anwenden, Sortierung prüfen und Änderungen speichern
- Karte mit geplanten Ereignissen ist horizontal bündig mit dem restlichen Arbeitsbereich
- sichtbare Statuswerte im Arbeitsbereich werden deutsch angezeigt, insbesondere `Geplant` statt `planned`
- geplante Ereignisse lassen sich unter `Auswahl anpassen` im hellen Theme wieder eindeutig per Checkbox an- und abwählen
- der Ereignis-Editor kennt explizit `Mehrere Zeitbereiche`; beim ersten hinzugefügten Zeitsegment wechselt er automatisch aus `Ganzer Zeitraum`
- Rückwechsel auf `Ganzer Zeitraum` oder `Ein Zeitbereich` entfernt zusätzliche Segmentzeilen konsistent

### 0.23.0 – Funktionsbasis nach M1-Codeaudit

- neuer Funktionsbranch `patch/0.23.0` auf Basis des optisch stabilen 0.22.3-Stands
- Mehrsegment-Ereignisse belegen nur ihre tatsächlichen Unterereignisintervalle; Lücken bleiben frei
- bestätigte Cascades werden bei mehreren Unterereignissen segmentweise statt über den gesamten Elternzeitraum angewendet
- bestehende Unterereignisse werden bei archivierten Strukturwechseln vollständig bereinigt
- archivierte Neu-Zuordnung verhindert eine zweite `Ohne Ereignis`-Monatssammlung
- pro archiviertem Ereignis ist höchstens ein offener IST→SOLL-Änderungsauftrag zulässig
- Zeitbereiche mit identischem Beginn und Ende am selben Tag werden konsistent abgewiesen
- `Alle/Sortiert/Export` bleibt als eigener noch zu klärender M1-Funktionsblock unverändert

### 0.22.3 – Registerbasis stabilisiert

- neuer Entwicklungsbranch `patch/0.22.3` auf dem letzten optisch stabilen Registerstand vor den Schulter-/Ohren-Experimenten
- keine zusätzlichen Schulter-, Ohr- oder Anschlussflächen an aktiven Registern
- Tiefenverlauf liegt wieder direkt in der transformierten Trapezfläche und ist passend zur Registerschräge geneigt
- Verlauf ist an die reale Überdeckungskante gekoppelt, damit er auf Desktop und Mobil sichtbar bleibt
- schmale Hochformatansichten verwenden keine separate 4-px-Überlappung mehr; die responsive gemeinsame Registergeometrie bleibt erhalten

### 0.22.2 – Registergeometrie und Feinschliff

- neuer eigener Entwicklungsbranch `patch/0.22.2` auf Basis von 0.22.1
- aktive Register verwenden browserartige Viertelkreis-Schultern, die direkt in die Seitenfläche auslaufen statt angesetzter Halbkreis-Flächen
- linke und rechte Schulter werden als eigene Dekorationselemente gerendert; die innere Rundung bleibt bei überlappenden Registern verborgen
- inaktive Register behalten eine einheitliche Grundfarbe
- Tiefenwirkung entsteht nur noch seitlich an den Registerkanten; unterhalb der Register wird kein Schlagschatten mehr gezeichnet
- die stärkere trapezförmige Registersilhouette und die bestehende responsive Breitenlogik bleiben erhalten

### 0.22.1 – Desktop-Designpass 2

- Registerkarten wirken als saubere, überlappende Trennblätter mit durchgehendem Farbakzent
- Light Mode übernimmt nun auch die historisch dunklen Arbeitsbereich-/Ereignisflächen
- Header-Menü ist als einheitliches Panel ohne überlappende Einzelrahmen aufgebaut
- Statuskarten in Import & Prüfung besitzen einheitliche Linien-Icons
- Quellenwahl zeigt nur die aktive Quelle und öffnet SD-Karte, Laufwerk oder Ordner/Sicherung als Popover
- SD-Aktionen sind kompakter, rechteckiger und mit eigenen Icons versehen
- „SD-Karte sichern“ ist als grüne Primäraktion ausgezeichnet; Auswerfen bleibt neutral
- Desktop-Komponenten orientieren sich stärker an der Bauhaus-Blaupause
- Desktop und Mobile verwenden dasselbe horizontale Registerprinzip im Header; die frühere mobile Seitenleiste wurde wieder entfernt
- Hauptregister sind abgerundete, gestaffelte Ordnerlaschen: der aktive Bereich liegt sichtbar vor den übrigen Registern und geht ohne dunkle Trennkante in die Seite über
- der Bibliothekar-Assistent ist ein kleines eigenes Header-Feld neben dem Menü und öffnet eine echte eigene Seite
- Mobile Menü- und Aufgaben-Panels liegen als eigene Overlays über der Registerzeile
- Import, Arbeitsbereich und Archiv behalten sehr leichte bereichsspezifische Rot-/Blau-/Gelb-Hintergrundtöne
- Import & Prüfung wiederholt Rot gezielt als linken Akzent an „Quelle sichern“
- Arbeitsbereich verwendet Blau für „Ereignis erstellen“ sowie Rahmen und Schrift von „Metadaten eindeutig“
- offene Archivprüfungen erhalten einen gelben Kartenakzent
- SD-Karte, Laufwerk und Ordner/Sicherung sind wieder als drei gleichwertige, füllende Quellkarten nebeneinander sichtbar
- alte rechteckige Fremdflächen bei „Sicherung auswählen“ und „Metadaten prüfen“ werden neutralisiert; Diagnose und Importverlauf erhalten mehr Abstand
- das Hauptmenü enthält die neue Seite „Metadatenkorrektion“ als vorbereiteten Einstieg für spätere WhatsApp-/Signal-Metadatenpflege

### 0.22.0 – Redesign / Produktschale

- gemeinsamer Bibliothekar-App-Rahmen für Import, Arbeitsbereich und Archiv
- drei überlappende Hauptreiter im Bauhaus-inspirierten Design
- Arbeitsbereich bündelt Aufnahmen und Ereignisse als Unterbereiche
- Aufgaben wandern aus dem Floating-Button in den Header
- Menü mit Einstellungen, Bibliothek wechseln und Über Bibliothekar
- Hell-, Dunkel- und Systemdarstellung
- vorbereiteter, noch inaktiver Bibliothekar-Assistent unten rechts
- Importquellen als kompakte Auswahl für SD-Karte, Laufwerk und Ordner/Sicherung
- Import- und Prüfverlauf mit komprimiertem Vorschaubild aus dem frühesten JPEG
- dateiweise Fortschrittsmeldungen beim Inventarisieren, Kopieren und Verifizieren
- deutsche Statusbegriffe bleiben fachlich nah an geplant / angewendet / archiviert
- bestehende Importwege und Kernfunktionen bleiben erhalten

### 0.21.2 – Patch in Arbeit

- normale Zeitsegmente können ergänzt und vollständig entfernt werden
- Neu-Zuordnung arbeitet auf Tages-/Zeitsegmentebene statt Familien-Drilldown
- bestehende Ereignisse und neue Unterereignisse sind Neu-Zuordnungsziele
- gespeicherte „Ohne Ereignis“-Segmente bleiben kanonische Zeitdefinition
- pending/Nachsortierung wird deutlich als noch nicht angewendet markiert
- freie Restzeiten werden sekundengenau berechnet
- archivierte Ereignisse können mehrere Unterereignisse im manuellen IST→SOLL-Auftrag abbilden
- SD-Wiederverwendung ignoriert Verwaltungsdateien und zeigt 0 neu / 0 verändert als normalen Zustand
- Archiv-E2E-Tests verwenden eine getrennte beschreibbare QA-Testbibliothek

### Weiter geplant / offen

- Zeitsegmente beim Bearbeiten vollständig löschen können
- Reassignment-Dialog ohne Familien-/Datei-Drilldown
- gespeicherte Zeitsegmente von `Ohne Ereignis` korrekt anzeigen
- applied-Erweiterungen klar als noch anzuwendende Änderung kennzeichnen
- freie Restzeit eines Tages nach Löschen eines Ereignisses korrekt berechnen
- archived einfaches Ereignis nachträglich sauber in Ober-/Unterereignisse überführen
- herausfallende Familien auch als Unterereignis eines bestehenden Ereignisses neu zuordnen
- SD-UX bei `0 neu / 0 verändert` verbessern
- Kamera-Verwaltungsdateien nicht dauerhaft als `neu` ausweisen
- skalierbare Listen mit Einklappen und Pagination
- portable TrueNAS-Installation und Updatepfad

## [0.21.1]

### Behoben

- SD-Kartenstatistik verwendet jetzt die aktuell eingebundene Wechselquelle
- veraltete Legacy-Mounts werden aufgeräumt
- wiederverwendete SD-Karten werden korrekt neu erkannt

### Vorhanden

- inkrementeller SD-Import
- bereits gesicherte Dateien werden erkannt
- neue Dateien können separat als eigener Sicherungslauf importiert werden
- Schema-Version 22
