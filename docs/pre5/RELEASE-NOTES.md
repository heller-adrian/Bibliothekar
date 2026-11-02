# Bibliothekar v1.0.0-pre.5

**Prerelease für die anschließende praktische TrueNAS-Abnahme.** Keine stabile 1.0.0.
Anwendungscode: `b4c3a397843567bfe09b35e82c51d0009d0a71bf`. Die Quellenidentität, die Linux-Prüfkette und das konkrete Release-Image werden vor Veröffentlichung verifiziert.

## Korrekturen

- Historische RC14-Reintegration der 14 korrigierten iPhone-JPEGs mit `+13:00`: Die ursprüngliche F14-Reservation bleibt beim Start erhalten. Erst ein authentifizierter, ausdrücklicher Reintegrationsauftrag darf einen vollständig qualifizierten, nachweislich vor dem ersten Austausch abgebrochenen RC14-Vorgang abschließen. Der dauerhafte Nachweis erhält die Originalreservation. Kein nachträglicher Eigentumsbeleg und keine Freigabe aus bloßer Journal-Abwesenheit.
- Die historische RC14-EXIF-Prüfung wird exakt einschließlich ihrer Offset- und ungültigen Sekundärtag-Semantik ausgewertet. Geänderte Dateien, fremde Inodes, Hardlinks, Symlinks und widersprüchliche Belege bleiben geschützt.
- Originale F14-Abschlussbelege werden nach einem Crash zuverlässig unter erneuter Root-/Generationsprüfung abgeschlossen. Abgewiesene neue Restore-Auswahlen erzeugen keine zusätzliche verwaiste Reservation. Unterbrochene reine SD-Prüfungen werden von tatsächlichen Medienänderungen unterschieden.
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
