# Bibliothekar 0.50.7 – Desktop navigation and English import history

## Grundlage
Weiterentwicklung des gesonderten Testimages 0.50.6, im Draft-PR #19
auf `patch/0.50.0-audit`. Kein Merge nach `main`, kein
`latest`-Image, keine Berührung von produktiven Daten.

## Desktop / PWA
- Die vollflächige Ladefläche mit Spinner ist ausdrücklich auf
  `html[data-bk-display-mode="standalone"]` begrenzt.
- Desktop-Browser navigieren unverzüglich über
  `window.location.assign(href)`, mit dem bisherigen
  `bk-tab-pressing`/`is-navigating`-Klick-, Hover- und
  Ankunftsanimationsvertrag. `bk-nav-loading` wird dort nicht gesetzt.
- Der Desktop-Body wird nicht mehr bis zum Abschluss der
  DOM-Übersetzung unter einer unsichtbaren Ladefläche blockiert.
  Für die installierte PWA bleibt die bisherige Sprach- und
  Ladeinitialisierung mit eigenem Spinner erhalten.
- Mit normaler HTTP-Navigation kann der neue Seitentitel allerdings
  erst erscheinen, sobald der Browser HTML der neuen Seite empfangen hat.
  Ein sofortiger Desktop-Seitenwechsel ohne Wartezeit auf den ersten
  Response-Byte erforderte eine separat zu prüfende SPA-/Caching-Architektur.

## Englische UI
- Datenbankkarte: `Schema 1–52` wird `Schema version 1–52`.
- Importverlauf: separat übersetzte, aus der Datenbank geladene
  `progress_message`- und `error_message`-Texte.
- Zusätzlich Texte und Phasen für SD-Karte, Ordnerimport, SHA-256-Backup,
  ExifTool, Metadatenanalyse, Sortierung und Erfolgsmeldungen.
- Im aufgeklappten technischen Bereich heißen die Überschriften
  `Technical ID` und `Job type`; das rohe JSON bleibt
  unverändert (technische Schlüssel, Werte, gespeicherte Pfade).
- Die Beispielnamen der Einstellungen lauten in EN `Vacation`
  und `City visit`, in DE `Urlaub` und `Stadtbesuch`.
  Es wird ausdrücklich nichts an tatsächlichen Ereignisnamen geändert.
- Der Beispielbaum zeigt weiterhin die konfigurierten *realen*
  Ordnernamen, auch wenn diese in einer älteren Bibliothek deutsch sind.

## Speicherpfade /workspace
Die bereits im Quellstand englischen Standards heißen:
`SD Card Backups`, `Library Workspaces`,
`Metadata Correction`, `Trash`.
Die neuen Regressionstests überprüfen, dass die App diese
Stämme bei leerem `/workspace` erzeugt. Historische deutsche
Stämme und gespeicherte Einstellungen haben Bestandsschutz
und werden nicht automatisch verschoben/umbenannt.

## Prüfung und Veröffentlichung
Geplantes Containerimage:
`ghcr.io/heller-adrian/bibliothekar:patch-0.50.7`.
Veröffentlichung ausschließlich nach vollständiger GitHub Actions QA
(Backend und isolierter Archiv-Harness).
Aktueller CI-Hinweis: neu gestartete Jobs schlagen nach wenigen
Sekunden fehl und melden keine ausgeführten Schritte/keine Logs.
Die Ursache ist daher derzeit **nicht** als Codefehler nachgewiesen.
Ohne erfolgreich abgeschlossene QA gilt 0.50.7 nicht als freigegeben.
