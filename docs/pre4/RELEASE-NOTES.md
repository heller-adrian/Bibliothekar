# Bibliothekar v1.0.0-pre.4 (Prerelease)
Dieses **Testrelease** trennt die strukturelle Storage-Verfügbarkeit von fachlichen Dateioperationen. Global gibt es ausschließlich `READY` und `UNAVAILABLE`. Fehlende oder regulär bewegte einzelne Mediendateien lösen keine globale Storage-Unavailable-Seite mehr aus. Nicht eindeutig abgeschlossene F14-Operationen schützen weiterhin die betroffenen Schreibzugriffe; die normale Weboberfläche und sichere Lesezugriffe bleiben erreichbar, sofern die Verwaltungsstruktur intakt ist.

Wichtige Änderungen:
- Technische Startup-Vorbereitung und fachliche Recovery sind getrennt.
- Identität und Mounts der festgelegten Verwaltungsanker bleiben geschützt.
- Authentifizierte Operationsdiagnose und reine Lesezugriffe bei ungeklärten Vorgängen.
- General-Metadatenkorrektur und Übernahme, zweimaliger Neustart sowie RC14-Sammelreintegrationen einschließlich ursprünglicher F14-Reservation qualifiziert.
- Papierkorb, SD-Kartensicherungen, DNG-Rückbau und historische iPhone-JPEGs regressionsgeprüft.

Die isolierte Linux-Abnahme ist vollständig grün: **39 neue Vertragsprüfungen, 148 historische Regressionen, acht Chromium-Browserprüfungen, alle sechs bisherigen pre.3-Wiederherstellungsszenarien, 14 iPhone-JPEGs und 4.000 Dateien in zwei Bibliotheken**. Die Versionierung wird für das veröffentlichte Image nochmals eigens geprüft.

**Grenzen:** Die drei ursprünglichen F14-Operationen des tatsächlichen TrueNAS-Bestands sind nicht vollständig klassifiziert. Damit kann die App beim ersten Start trotz global `READY` weiterhin Schreibvorgänge aus Sicherheitsgründen ablehnen. **Kein Clean Slate, keine Journalbereinigung, kein Verändern historischer Dateien oder Datenbanken.** Native TrueNAS-/NFSv4-, physische SD-/USB- und reale DNG-1.7-Schreibtests bleiben ausstehend.

Zum verifizierten Docker-Digest siehe `IMAGE-DIGEST.txt`; zur Umstellung `UPGRADE-TRUENAS.md`.
