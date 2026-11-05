# Bibliothekar 0.50.6 – English completion, new installs and visible PWA navigation

## Ausgangsstand
Basis ist die separat veröffentlichte Testversion 0.50.5. Version 0.50.6
liegt ausschließlich auf dem Entwicklungsbranch `patch/0.50.0-audit`.
Es erfolgt **kein Merge nach main, kein latest-Push, keine Änderung des
stabilen Images oder produktiver Bibliotheksdaten**.

## Befunde und Korrekturen aus zehn Screenshots
- Workspace: `Zielstruktur-Vorschau` → `Destination structure preview`,
  `Arbeitsbestand` → `Workspace inventory`, `Auswahlzeitraum` →
  `Selection period`, Zeitspanne nun mit Umbruch statt abgeschnitten.
- Workspace: Statistikkarten haben skalierte und umbrechende Beschriftungen
  (insbesondere `Items requiring review`), damit Text nicht über die Karte ragt.
- Ereignis bearbeiten/erstellen: zusätzliche Übersetzungen für Titel,
  Notizen, Unterordner, Unterereignis löschen, Datumsfehler und
  dynamische Statusanzeigen.
- Sortierplan und Pflichtänderung: Zielgruppen, Datenmenge, Sicherheitsstatus,
  Ergebnis, Zielstruktur, Blocker, Hinweise, SHA-256-Warntexte und
  Sortierbestätigung ergänzt; Titel mit tatsächlichem Ereignisnamen
  werden nur in den festen UI-Präfixen übersetzt.
- Archiv, archiviertes Ereignis bearbeiten, manuelle IST→SOLL-Änderung,
  Rückänderung und Notausstieg: Sicherheits-/Finder-Texte, Statusbezeichnungen
  und Gegenprüfungen ergänzt.
- Resttexte in Metadatenkorrektur, Aufgabenbereich und Papierkorb ergänzt.

## Erste Installation vs. vorhandener Bestand
Die bestehenden historischen Ordner-/Layoutkonstanten `Alle`,
`Sortiert`, `Export` bleiben als Rückwärtskompatibilität erhalten.
Die **tatsächliche Neuanlage einer Bibliotheksdatenbank** wird bei der
Initialisierung separat und dauerhaft mit der Vorlage
`All` / `Sorted` / `Export`, Input `All` versehen.
Die bereits seit 0.50.2 englischen Standardstämme in der
Speicherkonfiguration, `No Event` und die standardmäßig englische
UI-Sprache bleiben bestehen. Bei vorhandenen Datenbanken wird die
Layoutkonfiguration nicht überschrieben. Benutzernamen, tatsächliche
Verzeichnis-/Dateinamen, Metadaten, SQLite-Inhalte, event.json und
archivierte Originale werden beim Sprachwechsel niemals verändert.

## PWA: unmittelbar sichtbare Reaktion
In 0.50.5 wurde bereits die alte, künstliche 190-ms-Navigationswartezeit
entfernt. 0.50.6 setzt beim Reiterklick vor dem Wechsel sofort einen
Ladezustand. Ein zweifaches `requestAnimationFrame` lässt zuerst
mindestens einen Frame des Ladeindikators sichtbar werden und startet
direkt anschließend die normale Browsernavigation, **ohne auf Daten oder
einen API-Aufruf zu warten**. Auch bei reduzierter Bewegung wird
die Navigation nicht ohne Feedback umgangen.
Beim Ankommen bleibt die gewählte Sprachinitialisierung vor dem ersten
sichtbaren deutschen DOM erhalten, aber ein Head-CSS-Indikator
zeigt den Ladevorgang statt einer leeren Oberfläche.
Der Indikator ändert nicht die reale Server-/Netzwerklatenz.

## Sprachsichere Dialoge und Vorschautexte
Die relevanten Bestätigungen benutzen app-eigene Schaltflächen;
die seltenen Texteingaben zum Notfallabbruch nutzen nun ebenfalls einen
lokalisierten, asynchronen Dialog. `NOTFALLABBRUCH` bleibt als
exakter technischer Bestätigungstext unverändert.
Für `pre`-Blöcke werden **nur bekannte generierte UI-Zeilen** wie
`Zeitraum`, `Auswahl`, `bis` und feste Fehlermeldungen übersetzt.
Tatsächliche Ordnerstrukturzeilen bleiben unangetastet.

## Testumfang und Grenzen
- Vollständige isolierte Backend-/UI-Regressionssuite mit Node-Syntaxprüfung
  gerenderter Seiten, Sprach-/Vorschau-/Navigations-Regressionen.
- Isolierter Archiv-Container-Harness mit getrennten Testpfaden.
- Keine Tests mit produktiven TrueNAS-Originalen, Datenbanken oder Mounts.
- Die Quelltextüberprüfung umfasste Workspace, Ereignisse, Archiv,
  Import, Papierkorb, Metadatenkorrektur, Bibliotheksverwaltung,
  Login/Setup sowie mehrere Fehler-/Rückänderungsabläufe.
- **Ein automatisierter Katalogtest beweist nicht, dass jede unbekannte
  zukünftige Server-Fehlermeldung bereits übersetzt ist.** Der
  reale Firefox-/Safari-PWA-Abnahmetest der Screenshots steht noch aus,
  ebenso die manuelle Abnahme seltener Archiv-Rückänderungsfälle.
- Sprachwechsel betrifft UI-Texte; die Systemsprache der Browserleiste
  (z. B. „Nicht sicher“) gehört nicht zur App.
