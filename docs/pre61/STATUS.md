# Bibliothekar 1.0.0-pre.6.1 — Patchkandidat

Status: **Entwicklungsbranch, nicht veröffentlicht**. Basis: Pre.6 TrueNAS-Abnahmecode aus
`codex/pre6-truenas-acceptance`. Keine Änderungen an `main`, GHCR oder TrueNAS.

## Fachliche Änderungen

- Normale Aufnahmen behalten `YYYYMMDD_HHMMSS_Geraet.EXT`.
- Mehrere neue Familien desselben Geräts und derselben Sekunde erhalten bei
  belastbarer EXIF-Untersekunde `YYYYMMDD_HHMMSSmmm_Geraet.EXT` (`mmm` =
  **drei echte Millisekundenstellen**, keine Hundertstel- oder Seriennummer).
- Die Millisekunden werden aus EXIF-SubSecTimeOriginal bzw. den ohnehin
  verarbeiteten präzisen Aufnahmedaten übernommen. RAF/JPG/XMP behalten den
  *gleichen Familiennamen*, selbst wenn nur das RAW Untersekunden enthält.
- Ist keine vertrauenswürdige Untersekunde vorhanden oder sind mehrere Dateien
  auch millisekundengenau gleich, wird eine ausdrücklich numerische,
  kollisionsgeprüfte Ergänzung verwendet. Es werden keine Zeiten erfunden.
- Die Kollisionserkennung berücksichtigt im Zielordner bereits liegende Dateien
  und die in registrierten Bibliotheksdatenbanken bekannten, auch bereits
  archivierten Kameraaufnahmen.
- Eine extern umbenannte bekannte Datei erzeugt in angewendeten Ereignissen
  einen dauerhaften Aufgabenhinweis. „Übernehmen“ prüft Größe, SHA-256, Pfad,
  Symlinkfreiheit und den erwarteten Katalogstand; danach werden Pfad und
  dauerhafte event.json-Synchronisation aktualisiert. „Rückgängig machen“
  verwendet den vorhandenen geprüften No-Overwrite-Dateitransfer.
- Verschiebungen mit unverändertem Dateinamen zwischen erlaubten
  Organisationsordnern bleiben weiterhin automatisch übernehmbar.
- Archive bleiben read-only: Dateiumbenennungen dort können nicht durch
  eine heimliche Änderung von Bibliothekar korrigiert werden.

## Wichtige verbleibende Grenze

Wenn eine **früher** importierte Datei noch den normalen Sekunden-Dateinamen
trägt und erst ein **späterer** Import die Mehrfachaufnahme erkennen lässt,
wird die alte Datei nicht automatisch umbenannt. Dies ist insbesondere für
bereits archivierte Fotos zwingend: die App schreibt Archive nicht um.
Eine spätere Normalisierung dieses Altbestands bleibt gesondert zu prüfen.
Die neue Aufnahme erhält — soweit echte Untersekunden vorhanden sind —
bereits den Millisekunden-Zusatz. Die automatische vollständige Umbenennung
aller zuvor bestehenden Aufnahmen wird ausdrücklich **nicht** behauptet.

## Prüf- und Freigabegrenzen

Die separate GitHub-Actions-Pipeline `qa-pre61.yml` prüft alle neuen
Backendfälle, den alten Pre.6-No-Event-Regressionspfad sowie Syntax von Python
und des integrierten JavaScript-Aufgabendialogs. Der gesonderte Containerlauf
mit dem Marker `[pre61-container]` testet Supervisor, HTTP, Import, No-Event,
Hashintegrität und Neustarts gegen das tatsächliche neue Image.

Noch nicht durch diesen Branch ausgeführt: TrueNAS Clean Slate,
echte Fujifilm-40-fps-Testserie und manuelle UI-Abnahme von „Übernehmen“ und
„Rückgängig machen“ nach realer Finder-Umbenennung. Für die Veröffentlichung
ist eine bewusste gesonderte Freigabe erforderlich.
