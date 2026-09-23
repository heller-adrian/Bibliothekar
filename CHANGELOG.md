# Changelog

## [Unreleased]

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
