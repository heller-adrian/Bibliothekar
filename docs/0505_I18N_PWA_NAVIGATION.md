# Bibliothekar 0.50.5 – English UI and immediate PWA navigation

## Basis, Umfang und Isolierung
Ausgangscommit 0.50.4: `b78f634c4346ab07e990f1de92364ebf254e9142`.
Abgenommenes 0.50.5-Quellcommit vor Release-Anforderung:
`d19c982032469064e59200deb87d565e16981c97`.

Diese Version bleibt **nur ein Patch-Testimage**. Kein Merge auf `main`,
kein Tag `v0.50.5`, keine Veränderung des stabilen `latest` und keine
Tests mit produktiven SQLite-Datenbanken, Archiven oder Kameradateien.

## Verifizierte Ursachen und Korrekturen
1. **Sprach-Flash beim Seitenaufbau:** Der bisherige DOM-Übersetzer lief
   erst nach dem Parsen. Der Head-Bootstrap löst `bibliothekar-language`
   vor dem ersten Paint auf und blendet die englische Seite erst nach dem
   synchronen DOM-Übersetzungsdurchgang ein. Eine begrenzte Notfallfreigabe
   verhindert dauerhaft unsichtbare Seiten bei Skriptfehlern.
2. **Langsamer Hauptreiterwechsel:** `ui_shell.py` verzögerte
   `window.location.assign(href)` absichtlich um 190 ms für eine Animation.
   Diese Wartezeit wurde entfernt. Die sonstige Ladezeit hängt weiterhin
   von Netzwerk, Server und Zielseite ab.
3. **Deutsche Aufgaben und Bibliothekszustände:** Konkret fehlende
   statische/dynamische Texte und Task-Muster ergänzt, einschließlich
   `Geplantes Ereignis anwenden` und `Hauptbibliothek · aktiv`.
4. **Systemsprachige Safari-Dialogbuttons:** Für bestätigungspflichtige
   Kernoperationen gibt es `confirmAsync` mit App-eigenem Dialog:
   englisch `Cancel`/`Confirm` oder deutsch
   `Abbrechen`/`Bestätigen`. Die bisherige Bestätigungs-/Abbruchsemantik
   und alle API-Sicherheitsprüfungen bleiben bestehen.
5. **Versionsstimmigkeit:** Paket, Release, Deployment, Shell,
   Compose-Beispiel, README und historische Versionsprüfungen auf 0.50.5
   angehoben.

## Grenzen und Sicherheitsprinzipien
Die Oberflächensprache ist app-weit im jeweiligen Browser gespeichert.
Bestehende Eventnamen, Nutzernamen, reale Verzeichnisnamen, Importe,
Dateipfade, SQLite-Inhalte und event.json dürfen beim Wechsel nicht
übersetzt oder umbenannt werden. Die Übersetzung historischer und
nutzerspezifischer Ordner wäre eine eigenständige, ausdrücklich bestätigte
Dateisystemmigration und gehört nicht zu diesem Patch.

Textkatalog und dynamische Meldungen werden nach wie vor über begrenzte
Übersetzungstabellen/Reguläre Ausdrücke umgesetzt. Deshalb kann selbst
eine umfangreiche synthetische Regression **nicht beweisen**, dass jeder
zukünftige oder seltene Backend-Fehler übersetzt wurde. Auf einer echten
deutschsprachigen iPhone-PWA bleibt ein abschließender manueller
EN/DE-Bedienungsdurchgang erforderlich. Besonders Browser-eigene
Eingabe-Prompts und ältere Ausnahmezustände können systemsprachige
Schaltflächen haben.

## QA-Gates
- GitHub Actions: https://github.com/heller-adrian/Bibliothekar/actions/runs/38132481433
- Ergebnis: **1.029 Backend-Tests bestanden**, sechs Warnungen.
- Isolierter Archive-Container-Harness: PASS.
- Zusätzliche Regression: erster englischer Paint, stabile deutsche
  Umschaltung, sofortiger Navigationsaufruf und Node-Syntaxprüfung
  der tatsächlich gerenderten Hauptseiten.
- Keine stable/main/latest-Freigabe; PR #19 bleibt Draft.
