# pre.5: Vorbereitung der späteren TrueNAS-Abnahme

**Entwicklungsstand. Noch kein freigegebenes pre.5-Image.** Erst das veröffentlichte,
vollständig geprüfte Image einschließlich Digest aus den Release-Nachweisen
verwenden. Dieses Dokument erteilt keine vorzeitige Installationsfreigabe.

## Bestehende App aktualisieren

1. Bestehende App geordnet stoppen. Appkonfiguration sowie Appdata und Workspace
   konsistent sichern, bevorzugt über die bestehenden Dataset-Snapshots. SQLite,
   WAL/SHM, private F14-Dateien, Journale und Medien gehören zusammen. Keine
   Reservationsdatei entfernen und keine SQL-Statuswerte korrigieren.
2. In TrueNAS dieselbe Custom App bearbeiten. Nur die neue Imageversion bzw.
   den verifizierten Digest eintragen. Bestehende Appdata-/Workspace-Mounts,
   Bibliotheken, Passwort, UID/GID 568 und die bisherigen Gerätefunktionen erhalten.
   Archive und externe Importquellen weiterhin Read Only einbinden. Keine zweite
   Instanz mit denselben schreibbaren Mounts starten.
3. App starten und anmelden. Die bekannten, exakt qualifizierbaren historischen
   Beobachtungsreservationen werden von der Anwendung behandelt; ihr vollständiger
   Inhalt bleibt im privaten Unterbrechungsbeleg erhalten. Es wird kein erfolgreicher
   Import oder Dateiaustausch erfunden.
4. Unter „Settings and recovery“ Speicherstatus, Datenbankdiagnose und fachliche
   Operationsdiagnose prüfen. Bei intakten Ankern lautet der globale Storagestatus
   `READY`. Eine fehlende einzelne Arbeitsdatei darf diesen Status nicht ändern.
   Eine fachliche Warnung kann dennoch eine konkrete Datei oder einen tatsächlich
   gemeinsamen Wirkungsbereich schützen.
5. Bei einem echten Mount-/Anker-/Datenbankfehler muss `UNAVAILABLE` bestehen bleiben.
   Ursprünglichen Mount/Ordner wieder bereitstellen und erneut prüfen. Keine
   neu angelegten leeren Verzeichnisse als vermeintliche Originale verwenden.

## Praktische Abnahmeschritte mit entbehrlichen Testmedien

- Vor dem Upgrade vorhandene Zähler, Ereignisse und Archivdateien notieren.
- Workspace, Import, Archiv, Ereignisse und Papierkorb öffnen. Angezeigte Fehler
  müssen einen konkreten Pfad und Ursache nennen; sichere Ansichten bleiben nutzbar.
- Eine neue, zuvor nicht importierte JPEG-Datei in General korrigieren und über
  die normale Übernahme importieren. Tagesablage, Hash-/Herkunftsnachweise und
  abgeschlossenen Auftrag kontrollieren.
- Ein unabhängiges Testereignis anlegen und sortieren. Erfolg ist `applied` mit
  vollständigen Prüf-/Verschiebezählern; `completed` ist kein Sortierlaufstatus.
- Zweimal geordnet neu starten. Dateiorte, Ereignisse und Herkunft müssen erhalten
  bleiben. Read-only-Archive dürfen nicht verändert werden.
- An einer separaten Testdatei einen lokalen Fehler prüfen; anschließend einen
  unabhängigen Import und eine Sortierung ausführen. Ein tatsächlich ungeklärter
  gemeinsamer Schreibvorgang darf weiterhin gezielt sperren.
- Papierkorbverschiebung, Wiederherstellung und bestätigte endgültige Löschung
  ausschließlich mit entbehrlichen Testdateien prüfen.

## Bekannte Grenzen

Die erneute General-Übernahme bereits bekannter Kameraaufnahmen ist noch nicht
als eigenständige neue Aufnahme implementiert. Sie bleibt lokal und verständlich
abgelehnt. Archivoriginale werden dadurch nicht umgeschrieben oder ersetzt.

Native TrueNAS-/NFSv4-ACLs, physische SD-/USB-Hardware und echtes DNG-1.7-Schreiben
sind noch nicht abgenommen. ExifTool-Fehler werden nicht pauschal unterdrückt.
Bei unklaren Nachweisen Diagnose sichern und die geschützte Operation belassen.
Ein Rückwechsel des Images stellt keinen Snapshot-Rollback dar: frühere Versionen
können die bereits behobenen Start-/Schreibblockaden erneut auslösen.
