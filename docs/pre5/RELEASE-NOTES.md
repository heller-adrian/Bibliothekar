# Bibliothekar v1.0.0-pre.5 – Entwurf

**Entwicklungskandidat, noch nicht veröffentlicht.** Die vollständige Linux-Abnahme
und die Integritätsprüfung des Release-Images sind zwingende Freigabebedingungen.

## Korrekturen

- Workspace-GETs und Thumbnail-GETs fordern keine schreibende Dateioperation an.
  Persistente Vorschaubilder werden durch Importworker erzeugt; Cache-Misses
  werden lesend im Speicher gerendert. Sichere Katalogansichten
  bleiben bei einem unabhängigen fachlichen Konflikt erreichbar.
- Nur ausdrücklich auditierte, medienlesende Bestandsprüfungen, Archivprüfungen
  und SQL-Planvorbereitungen verwenden kurzlebige F14-Reservationen. Ein solcher
  abgelehnter Scan wird nicht als unterbrochener Medienaustausch interpretiert.
- Historische Beobachtungsreservationen werden ausschließlich nach vollständiger
  Qualifikation behandelt. Ihr ursprünglicher Inhalt bleibt im dauerhaften
  Unterbrechungsnachweis erhalten. Echte ungeklärte Dateiänderungen bleiben geschützt.
- Bereits zentral geführte Importaufträge werden beim Neustart nicht erneut als
  alte Main-Arbeitsbereichsmigration interpretiert. Echte Alt-Migrationen verlangen
  weiterhin vollständige Quell-/Ziel- und Hashnachweise.
- Eine bestätigte Kataloglöschung löscht keine historische Quellenidentität.
  General prüft diese Herkunft einschließlich abgeschlossener Korrekturketten,
  bevor eine Aufnahme irrtümlich eine neue Herkunft erhalten könnte.
- Datenbankdiagnose unterscheidet Verbindung, SQLite-/Fremdschlüsselintegrität und
  vollständiges ausgeliefertes Schema. Keine automatische Datenbankneuanlage,
  pauschale Statusänderung oder Löschung von Journal-/WAL-Dateien.

Globaler Speicherzustand bleibt ausschließlich READY oder UNAVAILABLE.
Dateikonflikte begrenzen die gefährdeten Operationen; technische Identitäts-,
Mount-, Root-, Datenbank-, Hash-, Journal- und Archivkontrollen bleiben verbindlich.

## Grenzen

Der ursprüngliche erste Inventory-Abbruch auf dem realen NAS ist ohne dessen
Erstexception nicht bewiesen. Die nachgewiesenen anschließenden Fehlerketten
werden durch reale API-/Worker-/Containerfälle geprüft.

Die bewusst neue logische Aufnahme einer bereits bekannten Kameraaufnahme aus
General (Variante A) bleibt DEFERRED und wird lokal verständlich abgelehnt.
Ein eigenständiges Verlustabschlussmodell bleibt DEFERRED.

Native TrueNAS-/NFSv4-ACLs, physische SD-/USB-Geräte und echtes DNG-1.7-Schreiben
sind NOT_RUN. Synthetische TIFF-Fixtures mit RAF-Endung beweisen keine native
RAF-Schreibunterstützung. ExifTool-Warnungen werden nicht pauschal unterdrückt.
