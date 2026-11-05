# Grenzen und offene Anforderungen

Status: Entwicklungskandidat; keine Veröffentlichung freigegeben.

- Native TrueNAS-/OpenZFS-NFSv4-ACL-Abnahme und echte SD-/USB-Geräte: **NOT RUN**.
  Dieser Auftrag greift nicht auf das NAS zu. Linux-POSIX-ACL-Tests sind kein
  Ersatz für native NFSv4-Semantik. Base-Installation und privilegierter optionaler
  Gerätehelper sind getrennte Betriebsarten.
- **DEFERRED: erfolgreicher Abschluss trotz verlorener Archivdateien.** Das
  heutige Modell bietet einen ausdrücklich ungeklärten manuellen Abbruch, keinen
  nachgewiesen erfolgreichen Archivabschluss. Ein neuer Verlustabschluss braucht
  einen eigenen dauerhaft auditierbaren Verluststatus, unveränderte historische
  Claims und Sperren für abhängige Vorgänge. Einfache Umdeutung in verified oder
  complete wäre falsch. Bestehende Verify-/Restoration-Prüfungen bleiben wirksam.
- **DEFERRED: DNG 1.7 Originaldatei.** Das Paket enthält nur die ExifTool-Warnung,
  keine betroffene DNG. JPEG-/XMP-Offsettests beweisen keine DNG-Schreibfähigkeit.
  Der Kandidat unterdrückt keine Warnung, benutzt kein `-m` und meldet den
  unveränderten technischen Fehler innerhalb der lokalisierten Erklärung.
  Zur Formatabnahme wird eine isolierte Kopie einer betroffenen Datei benötigt.
- Die komprimierte Anzeigezwischenspeicherung hängt bei großen Antworten von
  CompressionStream/DecompressionStream ab. Bei fehlender Browserunterstützung
  oder vollem SessionStorage erscheint Laden statt eines alten kleinen Bestands.
  Backend und Dateimutationen vertrauen diesen Anzeigedaten niemals.
- Kompakte Rename-Anleitung ist konservativ: ein eindeutiger Ordnerpräfix,
  vollständiges tatsächliches Inventar, SHA/Größen und beide event.json-Versionen.
  Unbekannte Dateien, Symlinks, Zielkonflikte oder komplexe Änderungen behalten
  die detaillierte Anleitung. Die App führt keine Archivumbenennung aus.
- RC14-Offsetwiederaufnahme verlangt den passenden abgeschlossenen Korrekturbeleg
  mit identischen Mitgliedern, Pfaden, Größen, Hashes, Job und Familie. Bei
  fehlenden/widersprüchlichen Belegen ist ausdrücklich keine automatische
  Zeitzonenvermutung zulässig. Naive mehrdeutige/ungültige Sommerzeit-Uhrzeiten
  verlangen einen expliziten Offset.
