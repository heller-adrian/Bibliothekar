# Bibliothekar 0.50.2 – English-first language integration (WIP)

Stand: 10.10.2026, Branch `patch/0.50.0-audit`, PR #19 Draft. Keine Stable-Freigabe, keine Installation in Produktivdaten.

## Vorgehen

Die deutschen Texte des bisherigen UI werden in der Ansicht lokalisiert, nicht in Datenbank, Dateipfaden, Dateifamilien, Portables `event.json` oder technischen Statuswerten. `app/ui_i18n.py` enthält ein lokal ausgeliefertes Deutsch→Englisch-Wörterbuch für UI-Beschriftungen, den Hinweis- und Reassignment-/Archiv-Workflow und dynamische DOM-Textknoten. Ein `MutationObserver` berücksichtigt später hinzugefügte Dialoge. Die Übersetzung betrifft Textknoten sowie bestimmte barrierefreie Beschriftungen/Platzhalter; nicht Eingabewerte, HTML-Code, Dateinamen, persistierte Nutzdaten oder Attribute zur Steuerung der UI.

Der Browser speichert seine Auswahl unter `bibliothekar-language`, standardmäßig `en`, alternativ `de`. HTML-Dokumente erhalten den korrekten Sprachcode.

## Verzeichnisnamen

Für neue Installationen ohne bestehende Daten gelten:
- `SD Card Backups`
- `Library Workspaces`
- `Metadata Correction`
- `Trash`
- neue Monatssammlungen ohne Ereignis: `No Event`

Vorhandene deutsche Hauptverzeichnisse werden erkannt und weiterverwendet. Der Sprachschalter ist ausdrücklich **keine Umbenennungsfunktion**. Weitere historische und teilweise technische Unterordner mit fest eincodiertem Namen (z. B. `Alle`, `Sortiert`, `Ohne_Datum`, `Allgemein`) dürfen nicht rein kosmetisch im Dateisystem umbenannt werden, solange die Operationen nicht vollständig kompatibel gemacht und isoliert getestet wurden. Für diese Stellen besteht weiterhin Internationalisierungsbedarf.

## Ergänzende UI-Absicherung für 0.50.2

- Die Übersetzung läuft auf sichtbaren Beschriftungen und neuen Dialoginhalten; native Browserdialoge (`alert`, `confirm`, `prompt`) werden ebenfalls in der **Anzeige** übersetzt. Ihre Rückgabewerte und vom Benutzer eingegebene Antworten bleiben unverändert. Insbesondere ein abgelehntes Lösch-Confirm darf nicht zu einer Bestätigung werden.
- Datums- und Zahlenformate in Ereignissen, Arbeitsbereich, Import und Archiv verwenden die aktive Browser-UI-Sprache. Interne Status- und Dateipfadvergleiche bleiben sprachunabhängig.
- Der Wechsel Englisch ↔ Deutsch ist ohne Seitenneustart vorgesehen. Der Sprachlayer merkt sich die Originaltexte und stellt auch dynamische Zähler wie `3 Gruppen ausgewählt` beim Wechsel zurück.
- Vorhandene Legacy-Regressionstests verwenden bewusst `BIBLIOTHEKAR_DEFAULT_DIRECTORY_LANGUAGE=de` und behalten ihre deutschen Erwartungen; die frische englische Ordnerbenennung wird separat ohne dieses Opt-in überprüft.
- Neue synthetische Browser-JavaScript-Tests prüfen native Dialoge, Prompt-Eingaben, Warnungs-Cancel und dynamische EN→DE-Umschaltung. Zusätzliche Übersetzungen für Archivänderungsaufträge, Ereignisplanung und Metadatenverwaltung wurden ergänzt.

**Qualitätsgrenze:** Wörterbuch-/DOM-Lokalisierung ist keine formale vollständige Internationalisierung aller Codepfade. Insbesondere benutzerdefinierte Ereignisnamen, weitere nicht katalogisierte API-Fehler und alle kontextabhängigen Interaktionen müssen im echten Browser auf Resttexte und Fehlzuordnungen geprüft werden. Der vollständige englische Umbau historischer innerer Verzeichnisnamen wäre ein eigener, migrationspflichtiger Dateioperations-Patch und ist nicht Teil dieses sicheren UI-Releases.

## Noch erforderlicher Freigabeumfang

Das Wörterbuch ist eine Ausgangsbasis und darf **nicht** als Nachweis betrachtet werden, dass bereits jede Python-Fehlermeldung, jede nachgeladene UI-Meldung und jede variable Archiv-Abfolge in beiden Sprachen vollständig fachgerecht übersetzt ist. Browser-/PWA-Tests mit allen relevanten Zuständen, Prüfung auf deutsche Resttexte sowie neue englische Ende-zu-Ende-Dateipfadtests sind vor einer Qualitätsfreigabe erforderlich. Keine automatische Übersetzung fremder Dateinamen oder Benutzertexte. Benutzerbestätigungen vor destruktiven Aktionen müssen insbesondere geprüft werden.

Die bisherigen 0.50.1-Abnahmekriterien für TrueNAS, iOS, Archiv-Fault-Gates und Discover bleiben unverändert.
