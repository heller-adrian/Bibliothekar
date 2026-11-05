# Bibliothekar 0.50.3 – Englisch-PWA: Bildschirmbefunde und Quellcode-Nachprüfung

Stand: 11.10.2026. Entwicklung auf `patch/0.50.0-audit`, PR #19 (Draft). Kein Merge und kein Produktiv-Deployment durch diesen Patch.

## Reale Referenz: sechs iPhone-PWA-Aufnahmen von 0.50.2

**Import / Hauptansicht:** Übersetzter Titel, aber deutsch blieben die Statuskarten `Anwendung`, `Bereit`, `Verbunden`, `Beschreibbar`, `Quelle sichern`, die Warnung, `SD-Karte`-Bedienelemente, der komplette Hilfetext und `Zuletzt aktualisiert`. In 0.50.3 wurden die zugehörigen echten UI-Strings und ihre dynamischen Statusbestandteile erfasst.

**Arbeitsbereich / Aufnahmen:** `Tage`, `Sicherungsfilter`, `Neuladen`, Dateizähler, `Unterereignis`, Freigabe- und Metadatenstatus sowie Kameragruppentitel erscheinen auch bei neuen dynamischen DOM-Elementen auf Englisch. Gespeicherte Ereignisnamen wie `Test löschen` und historische physische Verzeichnisnamen sind Nutzdaten und bleiben unverändert.

**Archiv:** `Arbeitsbereich freigeben`, `Gesperrt`, `Erstellt:`, `Status: angewendet`, Ereigniszähler, Aufgabenzähler, Recovery- und Rückänderungsanzeigen sind ergänzt. Archiv-Karten kennzeichnen ihre Ereignis- und Ordnernamen ausdrücklich als von der Übersetzung ausgenommen. Dialoge zum Freigeben bleiben sicherheitssemantisch unverändert.

**Metadatenkorrektur:** Der separat gespeicherte UI-Titel `Metadatenkorrektion` (abweichend von `Metadatenkorrektur`) wurde ergänzt. `Quelle: <Pfad>`, `Ohne-Datum-Bestand`, Zähler, leere Bestände und wichtige Felder/Bedienhandlungen sind ergänzt. **Die Quelle wird nur als Label übersetzt.** Eine bestehende Pfadzeichenfolge wie `/workspace/SD-Kartensicherungen/Ohne_Datum` wird nicht verändert.

**Ordnerimport:** Die standardmäßigen, aus Jobtypen zusammengesetzten Benennungen `Ordnerimport · <Quelle>`, `SD-Kartenimport · <Quelle>`, `Laufwerksimport · <Quelle>` werden als **Folder Import**, **SD Card Import**, **Drive Import** dargestellt. Gespeicherte Quellnamen bleiben im Anschluss an den Trenner unverändert.

## Implementierung

- `app/ui_i18n.py`: mehrere Hundert zusätzliche Übersetzungsbegriffe aus der Quellcode-Sichtung aller relevanten UI-Dateien, einschließlich Anmeldeseite, Import, Arbeitsbereich, Ereignissen, Archiv-/Recovery-Assistent, Metadatenkorrektur und Trash.
- Variable Inhalte werden über **eng begrenzte Muster** mit expliziten statischen UI-Präfixen lokalisiert. Eine generische Übersetzung jedes beliebigen Fragments findet bewusst nicht statt; dies würde echte Aufnahme-, Ereignis- und Quellnamen beschädigen.
- Browser-Tabtitel (`document.title`) werden auch außerhalb von `document.body` mit der Sprache umgeschaltet.
- `MutationObserver` übersetzt dynamisch hinzugefügte Text- und Attributknoten; benutzerdefinierte Ordnernamen und URLs werden weder verändert noch an eine Übersetzungs-API übermittelt.
- `app/transfer_ui.py` schützt Ereignisnamen/Ordnernamen in Archivkarten mit `data-bk-preserve-language`.
- `tests/backend/test_0503_real_world_english_ui.py`: englische Screenshot-Begriffe, zusammengesetzte dynamische Anzeigen, unveränderte Pfade, englischer Dokumenttitel und Wechsel zurück auf Deutsch.
- Im bestehenden QA-System läuft außerdem die vollständige Backend-Regression und der isolierte Archiv-Container-Test.

## Ordnerstruktur und Kompatibilität

Bei wirklich neuer Einrichtung sind die **konfigurierbaren Stammordner** standardmäßig:
`SD Card Backups`, `Library Workspaces`, `Metadata Correction`, `Trash`; neue Monatssammlungen ohne Ereignis standardmäßig `No Event`. Die bereits bestehenden Ordner und benutzerdefinierten Namen einer Installation werden **nicht** umbenannt. Sprachumschaltung und Ausgabeformatierung haben keine Dateisystemwirkung.

Fest kodierte ältere **interne** Ordnerkonventionen (z. B. `Alle`, `Sortiert`, `Ohne_Datum`, `Allgemein`, `Später zuordnen`, `Freigewordene Archivdateien`) bleiben vorerst *physisch* bestehen. Ihr blindes Umbenennen würde Import-, Sortier-, Reassignment- und Archiv-Recovery-Pfade brechen. Eine Umstellung bei Neuinstallationen darf erst nach umfassender Durchgängigkeit aller Pfadkonsumenten erfolgen.

## Freigabegate / offene Punkte

0.50.3 ist eine **wesentlich erweiterte**, nicht mathematisch vollständig nachgewiesene englische UI. Besonders variable Serverfehlermeldungen und selten ausgelöste komplexe Archivzustände können weitere deutsche Fragmente enthalten. Vor einer Stable-/TrueNAS-Discover-Freigabe bleiben ein vollständiger Browser-/iPhone-PWA-Rundgang in beiden Sprachen sowie destruktive Sicherheitsdialoge im echten Testsystem zu prüfen. Wenn hierbei Resttexte auftreten: als klar dokumentierte Folgefehler beheben, nicht die persistenten Dateien oder Geschäftslogik aus kosmetischen Gründen verändern.

`main`, `latest` und `v0.40.3` bleiben unverändert; dieser Patch wird ausschließlich als separater Testtag freigegeben.
