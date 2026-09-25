# Changelog

## [Unreleased]

### 0.26.8 – Applied-Reconcile, Zustandsklarheit und Sortierplan

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
