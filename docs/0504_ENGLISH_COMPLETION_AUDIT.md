# Bibliothekar 0.50.4 – English UI source and screenshot audit

**Stand:** 11. Oktober 2026. Entwicklungsbranch `patch/0.50.0-audit`, Draft-PR #19. Kein Stable-Release, kein Merge nach `main`, keine Änderung an `latest` oder produktiven NAS-Daten.

## Ausgangspunkt

Version 0.50.3 ist ein separat veröffentlichtes Testimage. Die acht iPhone-PWA-Screenshots aus der englischen Spracheinstellung belegen weitere deutschsprachige UI-Texte in Import, Import- und Prüfverlauf, Ereignisübersicht, Ereigniseditor, Foto-Arbeitsbereich, Sicherungsfilter und Papierkorb.

## Korrekturen

- **Import und Verlauf:** „Ausblenden“, „Ausgeblendet (n)“, der zusammengesetzte Titel für mehrere Aufnahmegeräte, „Abgeschlossen · n Dateien“, Benutzer-/Speicherdetails und weitere dynamische Zähler.
- **Ereignisverwaltung:** „Gespeicherte Ereignisse“, Statistikfelder, Statusbezeichnungen, Ereignisanzahl und die Formulierung von Start- bis Enddatum.
- **Ereignisfenster:** „Startzeit“, „Endzeit“, Unterereignisse, Beibehaltung von Tagesordnern, Vorschau, Speichern.
- **Papierkorb:** Leeren, Prüfstatus mit bekannten bzw. unregistrierten Dateien, Dateizahl, Ordnerzahl, Inhaltsübersicht, Fehlermeldungen.
- **Foto-Arbeitsbereich:** Planzahl und kompletter Standardhinweis, Auswahl anpassen, Archivfilter, Status-/Fehlermeldungen.
- **Seltene Zustände:** zahlreiche sichtbare Texte aus Import-/Backup-, Archiv-/Reversal-, Reassignment-, Sortier-, Metadaten- und Bibliotheksmodulen.

Das neue Modul `app/ui_i18n_0504.py` ergänzt das bestehende zentrale Wörterbuch um statische Übersetzungen und eng begrenzte, vollständig verankerte Muster für zusammengesetzte Meldungen. `app/ui_i18n.py` bindet die Ergänzungen ein.

## Sicherheits- und Datenvertrag

Weder Quellcode für Dateiverschiebungen noch Datenbank-/Sicherungslogik werden für die Übersetzung geändert. Ereignisnamen und gespeicherte Ordnernamen in den Ereigniskarten und im Planungsbereich werden ausdrücklich als Nutzdaten geschützt; Dateipfade und Benutzertexte bleiben unverändert. Ältere physische Ordnerkonventionen werden nicht umbenannt. Der Wechsel zurück auf Deutsch muss funktionieren.

## Regressionen

`tests/backend/test_0504_english_ui_completion.py` enthält konkret aus den Bildern abgeleitete Übersetzungsfälle, dynamische Texte, den EN/DE-Wechsel und Tests gegen die Veränderung vorhandener Namen/Pfade. Bestehende Versions-Pin-Regressionen sind auf 0.50.4 nachgeführt; historische fachliche Testinhalte bleiben bestehen.

## Freigabe

Ein statischer Quellcodescan beweist keine hundertprozentige Vollständigkeit bei allen möglichen seltenen dynamischen Servertexten. Für das Testimage sind vollständige Backend-QA und isolierter Archiv-Harness erforderlich; eine reale iPhone-PWA-Abnahme sämtlicher Interaktionen und Fehlermeldungen bleibt als eigener Schritt nötig.

**Keine Freigabe für Stable/TrueNAS Discover, kein `latest`, kein produktiver Upgrade-Auftrag durch diesen Patch.**
