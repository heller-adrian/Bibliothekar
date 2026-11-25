# Bibliothekar 1.1.2 RC8

Ausgangspunkt ist RC7 (`b05488660af4939db763294952b554d2da50ff06`).

## RC7-Paket

Die unabhängige statische Prüfung des ZIP bestätigte 10.166 eindeutige
Verschiebungen, 6.278 Familien, 35 konsistente Ereignisdokumente und 562
XMP-Umschreibungen. Die Archivbelege verwenden bei XMP die Zielprüfsummen
und Zielgrößen. Die 180 Ausschlüsse entsprechen exakt den gegenüber RC6
entfallenen Quellpfaden. Die enthaltenen Hostskripte stimmen mit RC7 überein.
Das Paket enthält eine an das Manifest gebundene Apply-Freigabe und ein leeres
Journal. Der Test hat das Paket ausschließlich gelesen. Für drei große
XMP-Patches sind die Quellbytes für eine unabhängige Nachrechnung der
Zielprüfsumme nicht im ZIP enthalten.

## RC8-Änderung

Der vorhandene Planungsdialog zeigt konkrete XMP- und RAW/DNG-Pfade samt
betroffenen Familienmitgliedern an. „Alle auswählen“ erfasst Fälle mit genau
einer Option. Konkurrierende Kandidaten benötigen eine Einzelauswahl.
Bestätigungen werden im Entwurf mit Pfaden, Dateisystemidentitäten und
SHA-256 gespeichert. Bei einer Neuplanung wird ein bestätigtes einzelnes
XMP der bereits inventarisierten Familie seines Masters zugeordnet. Der
Verschiebeplan, das Ereignisdokument und die Registrierung verwenden dieselbe
Familie. Weitere XMP-Bearbeitungsstände erhalten eigene Ziele. Ein vorhandener
`RawFileName` muss zum gewählten Master passen. Ein fehlender Verweis wird
nicht ergänzt.

Bestehende RC7-Ausschlüsse lassen sich im Entwurf aufheben. Eine ungestartete
Skriptfreigabe kann entzogen werden. Nach kontrollierter Skriptrücknahme kann
der Entwurf ausdrücklich weiterbearbeitet werden. Dabei wird die alte
Freigabe entzogen. Die Methodenüberschrift zeigt die gewählte Durchführung
auch während der wiederhergestellten Skriptvorbereitung an.

## Metadatenbefund

ExifTool 13.30 liest das Standardfeld in einer synthetischen JPEG-Datei und
ihren XMP-Daten als `EXIF:ExifIFD:SerialNumber` bzw.
`XMP:XMP-exifEX:SerialNumber`. Die RC7-Abfrage und Auswertung verwenden
`BodySerialNumber`. Dadurch kann ein vorhandener Seriennummernbeleg fehlen.
Der Vergleich akzeptiert exakt gleichwertige Dezimalzahlen und Brüche.
`FNumber=undef` liefert gegenüber einem Zahlenwert keine Übereinstimmung.
Gleiche lesbare Anzeigen belegen keine exakte Gleichheit der Rohwerte.

RC8 ändert den automatischen Matcher nicht. Neue Seriennummernquellen oder
Toleranzen würden auch andere Zuordnungen beeinflussen. Die produktiven
RAW- und XMP-Dateien waren kein Bestandteil der statischen Prüfung.

## Qualifizierung

Die Integrationstests decken Einzel- und Mehrfachbestätigung, einen
konkurrierenden DNG-Kandidaten, falsche Auswahl, Aufheben, gemischten Ausschluss,
Neustart, 35 gespeicherte Planobjekte, veränderte Bytes, Skriptausführung,
Registrierung und bytegenaue Rücknahme ab. 63 gezielte lokale Tests waren erfolgreich. Der Chromium-Test prüfte Auswahl,
konkurrierende Optionen und Methodenüberschriften bei 390 und 1050 px.
Die Linux-Freigabe fordert beide
neuen Lebenszyklustests auf nativem ZFS an. Der nächste Schritt nach der
Backend-QA ist die Containerqualifizierung desselben Commits.

Der erste GitHub-Lauf 45632838850 bestätigte den Container-Smoketest
und beide neuen Lebenszyklen auf nativem ZFS. Zwei Upgrade-Tests
erwarteten noch Migration 73 als letzte Version. Die Erwartungen sind
auf Migration 74 aktualisiert. Ein zusätzlicher Test prüft den Erhalt
eines RC7-Entwurfs, seines Plans und der XMP-Prüfsummen nach dem Upgrade.
