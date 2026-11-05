# RC13: Herkunft und aktueller Bestand

Basis ist ausschließlich v1.0.0-rc.12, Commit
671d7e7eb96ff493ae51720bb2769eccd8f9048f.

## Nachgewiesener P0

`central_stock_reconcile.reconcile_central_free_stock` bestätigt einen Fehlbestand
nach zwei vollständigen Scans, schreibt `central_file_deletion_confirmed` und
entfernt die lokale `files`-Zeile. `main.startup_database` ruft beim nächsten Start
`global_library_inventory.backfill_library_inventory` auf. RC12 berechnet dort
`family_content_fingerprint` erneut aus den verbliebenen Mitgliedern und übergibt
ihn an `library_registry.register_source_family`. Die bestehende Registry lehnt
zu Recht einen neuen kanonischen Inhalt für denselben Quellschlüssel ab.

Die isolierte RC12-Reproduktion scheitert bei partiellem Verlust am Neustart.
Eine zusätzliche negative Reproduktion zeigt: vollständig gelöschte Familien
werden von diesem Backfill gar nicht mehr geprüft, auch wenn ihre Audits fehlen.
Die Reproduktion befindet sich in `test_rc13_provenance.py`. Ihre Dateien sind
synthetisch; produktive Fotos oder Datenbanken wurden nicht verwendet.

## Korrektur und unveränderte Belege

`source_provenance.qualify_origins` liest die vorhandenen ursprünglichen Member
und den kanonischen Fingerprint als zusammenhängenden Registry-Snapshot. Aktuelle
Mitglieder müssen nach ursprünglichem Pfad, ursprünglichem Hash, Quellgröße und
Medientyp dazugehören. Ein Fehlbestand braucht einen passenden, bestätigten
Löschbeleg zu Job und Familie. Historische RC12-Belege ohne ursprünglichen Pfad
sind nur bei eindeutigem Hash innerhalb der passenden Herkunft zulässig.
Papierkorbbelege ohne Familie benötigen einen innerhalb der Sicherung eindeutigen
Hash. Widersprüche bleiben `source_inventory_conflict`.

Bestehende Herkunftszeilen werden bei diesem Abgleich nicht neu geschrieben.
Auch vollständig verlorene Familien werden anhand ihrer Registry-Historie
geprüft. Neue Löschbelege erhalten zusätzlich ursprünglichen Pfad/Hash/Quellgröße
in derselben SQLite-Transaktion wie die Entfernung der aktuellen Bestandszeile.
Es gibt keine SQL-Migration, keine Datenbereinigung und kein Reset von F14.

Eine neu angelegte zweite Bibliothek darf den Rest einer Familie nicht als neue
Kameraherkunft registrieren. Ihre Projektion referenziert die qualifizierte
ursprüngliche Main-Familie. Die schon bei dieser Projektion fehlenden Member
werden ausdrücklich als Verweise auf diese Herkunft festgehalten. Spätere lokale
Verluste benötigen eigene Belege; dieser Verweis erlaubt keine allgemeine
Ausnahme für fehlende Dateien.

Die Registry-APIs weisen Änderungen an bereits registrierten Memberlisten,
Quellhashes, Quellgrößen und Medientypen zurück. Es werden keine kanonischen IDs,
ursprünglichen Memberlisten oder Retentiondaten verkürzt.

## `control_file_invalid`

Ein eigener deterministischer Test reproduziert folgende Interleaving-Sequenz:
State öffnen → JSON lesen → paralleles atomisches Publizieren eines neuen State
→ zweite ACL-/Typ-/Linkprüfung des inzwischen entkoppelten alten Deskriptors.
Der alte Inode besitzt jetzt Linkanzahl 0. Im Appdatenprofil lautet der Fehler
`control_file_invalid`, im privaten Legacy-Profil `private_file_invalid`.

`root_operations._read` wiederholt ausschließlich einen solchen State-Leseversuch:
passender Fehlercode, `state.json`, alter gehaltener FD nachweislich entkoppelt,
aktueller Pfad nachweislich anderer Inode. Der neue FD durchläuft sämtliche
Prüfungen erneut. Nach drei Versuchen wird gesperrt. Symlinks, Hardlinks,
ACL-Fehler und kaputtes JSON erhalten keine allgemeine Ausnahme.

Damit ist eine passende Codeursache belegt. Ohne damaligen Trace lässt sich nicht
beweisen, dass ausschließlich diese Interleaving-Sequenz den einmaligen
TrueNAS-Screenshot ausgelöst hat.

## Grenzen

Die Reparaturentscheidungen in `storage_replacement.py` und
`managed_storage_health.py` werden nicht geändert. Die UI erhält ausschließlich
Darstellungskorrekturen. RC12- und Legacy-Containerabnahme werden erneut ausgeführt.
Native TrueNAS-Erstinstallation und ACL-Abnahme sind nicht Teil dieses Auftrags.
Ein fehlender oder widersprüchlicher Audit wird nicht als Freigabe interpretiert.

## Unterbrochene Herkunftspublikation

Der vollständige Crashlauf ergänzt einen tatsächlich erreichten Fall: SIGKILL
nach `register_source_family`, bevor lokale Dateien oder Registry-Member
veröffentlicht sind. Hier darf die leere Memberliste weder als fertig behandelt
noch gelöscht werden. Nur ein noch nicht abgeschlossener passender Importjob,
seine exakte F14-Importreservation (`app.main.process_claimed_job`, Job-ID),
Reservationsschlüssel/-ID, Datenbankpfad, Generation, Workspace und sämtliche
Bindings qualifizieren diesen erhaltenen Zwischenstand. Es werden dadurch keine
Member ergänzt, kein Abschlussbeleg geschrieben und keine ungeklärte Operation
freigegeben. Der bestehende Appdaten-Startaudit offener Operationen bleibt aktiv.
