# Bibliothekar 1.0.0-pre.6.1 – Entwicklungsstand

Basis: `codex/pre6-truenas-acceptance`, Commit `953f32c366208387b8c0cb914ff9df6ce2ded650`.

Der produktive Ordnerimport benennt einzelne Familien weiterhin nach `YYYYMMDD_HHMMSS_Kamera`.
Falls für dieselbe Kamera und Sekunde weitere verschiedene Familien im aktuellen Import
oder im bereits physisch vorhandenen Tagesbestand auftauchen, verwendet er ausschließlich
tatsächlich aus EXIF übernommene Millisekunden direkt hinter den Sekunden:
`YYYYMMDD_HHMMSSmmm_Kamera`. Eine nicht belegte Untersekunde wird **nie erfunden**.
Identische Millisekunden und fehlende Untersekunden behalten sichere, sichtbare
`_NNN`-Kollisionssuffixe. RAW und JPEG derselben Quellfamilie bleiben zusammen.

**Offener Übergangsfall:** Ein bereits früher importiertes unnummeriertes Original
wird beim späteren Burst-Import nicht eigenmächtig umbenannt. Die neu hinzukommende
Aufnahme erhält den millisekundengenauen Namen, die ältere bleibt unverändert.
Archivierte Namen werden nicht automatisch verändert. Diese Einschränkung ist
vor Veröffentlichung ausdrücklich zu entscheiden.

Dies ist ein Entwicklungskandidat, weder ein freigegebenes Image noch eine Version
für ein unkontrolliertes Clean Slate.
