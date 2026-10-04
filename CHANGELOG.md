# Changelog

## [Unreleased]
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
