# RC11 Implementierungsnachweis

Ausgangsstand: v1.0.0-rc.10, c8e078ee4c577ee0467fd86264fec6a3131351da. Entwicklungszweig: release/v1.0.0-rc.11. Dieser Bericht bereitet die gesonderte Freigabe vor; native TrueNAS-Abnahme steht aus.

## Implementierte Kontrollkette

`main._coordinate_startup()` qualifiziert Storage und private Autorität, übernimmt gegebenenfalls ausdrücklich geprüfte Format-1-Nachweise, reserviert die ursprüngliche Bootstrapoperation, erstellt technische Ordner und führt `startup_database()` aus. `storage_bootstrap.complete()` prüft Konfiguration, beide echten Datenbankschemata, SQLite-Integrität, Registryhistorie und Rollenbindungen. Erst nach prepared, dauerhaftem Abschlussreceipt, completed, Operationsarchiv und Reservationsabschluss starten die Worker.

`root_operations.reserve()` speichert Bootstrap-ID, Reservations-ID und kanonischen Operationsschlüssel durchgängig. Crash-Wiederaufnahme verwendet den ursprünglichen Schlüssel mit `initialize_storage=true`. `completed` allein ist kein Abschlussnachweis. Die erste Benutzerbibliothek wird anschließend bewusst über das Onboarding registriert.

`private_storage_security` prüft native ACLs, Eigentümer, Dateityp, Linkzahl, Elternrechte und gehaltene Dateisystemidentitäten. `root_operations` bindet private Reads, atomare Veröffentlichungen und Locks an qualifizierte Deskriptoren. Die Sicherheitsgrenze und unterstützten Backends stehen in [SECURITY.md](SECURITY.md).

`trash_selective._operation_lock()` verwendet für alle bisherigen Aufrufer dieselbe private `trash-recovery.lock`. Es erzeugt kein gemeinsames Workspace-Lock mehr. Format 2 sperrt einen unkontrollierten Rückwechsel zu RC10. Ein altes Lock ohne ursprünglichen Kontrollzustand blockiert den Wechsel der Sperrautorität.

`managed_storage_health` ersetzt die bisher unzureichende Bootstrap-Wiederaufnahmeprüfung durch vollständige Reservations-, Historien-, Registry- und Strukturqualifikation. `storage_warning_ui` zeigt Pfad und konkrete Ursache in Deutsch und Englisch. Der bestehende manuelle Verlust-/Ersatzvertrag wird weiter durch Regressionen geprüft.

## RC10 übernehmen

`storage_admin inspect` prüft die reale, aktuell sichere private Autorität und bildet einen Token über genau die beobachteten Originalnachweise einschließlich WAL-sichtbarer Kataloginhalte. `adopt` benötigt denselben Token, eine ausdrückliche Bestätigung und eine dokumentierte konsistente Backupreferenz. Diese Referenz ist eine Betreiberbestätigung, kein maschineller Beweis eines vorhandenen Backups.

Eine frühere fremdbeschreibbare ACL lässt sich nicht nachträglich authentifizieren. Die Übernahme erfordert deshalb eine bewusst dokumentierte administrative Herkunftsentscheidung; alle automatischen Sicherheitsprüfungen bleiben zwingend. Originalbytes, Reservation und Legacy-Lockbeobachtung werden dauerhaft erhalten. Bestehende Installationen verwenden den getrennten Scope `control`, ohne ihre Medienhistorie als Erststart zu behandeln. Siehe [Upgrade-Anleitung](UPGRADE-RC10.md).

Die reale Vorlage vom 27. Oktober ist als Fixture enthalten; nur im isolierten Test werden Pfade und Inodes auf synthetische Verzeichnisse umgesetzt. Produktlogik enthält keine feste produktive Reservations-ID oder Inodezahl.

## Historische Sperrgründe

Zusätzliche offene oder abgeschlossene Operationen, historische Bibliotheksgenerationen, Medien/Jobs, private Retention, nicht exakt technische Registryzeilen, geänderte Rollenidentitäten, unbekannte Dateien/Symlinks, verwaiste Sidecars und widersprüchliche Abschlussbelege bleiben Sperrgründe. Eine fehlende Datenbank oder `is_registered=0` überstimmt diese Nachweise nicht.

Passende eigene, noch nicht atomar veröffentlichte RC11-Dateien bleiben als nicht autorisierende Reste erhalten. Unbekannte Reste oder positive Historie in solchen Dateien blockieren. Ein weiterer Neustart darf sie weder als erfolgreichen Abschluss noch als neue fremde Installation interpretieren.

## Abnahmegrenzen

Die tatsächlich ausgeführten Prüfungen und Quellstände stehen in [TESTING.md](TESTING.md). Native TrueNAS-/OpenZFS-NFSv4-Semantik wurde hier nicht ausgeführt. Insbesondere muss nachgewiesen werden, dass `system.nfs4_acl_xdr` als UID 568 im echten Container die Kernel-ACL liefert. Bei fehlender Abfragemöglichkeit bleibt RC11 gesperrt; kein Ersatz-PASS und kein stiller Modusbit-Fallback.

Auch fachliche Journal-/Retentionabläufe unter der gemeinsamen nativen Workspace-ACL benötigen echte TrueNAS-Abnahme. Strenge Sicherheitsprüfungen dürfen dort eine notwendige Prüfung blockieren; sie dürfen nicht zur bloßen Herstellung eines PASS abgeschaltet werden.

Vor Upgrade: alte Writer stoppen, konsistente Gesamtsicherung, private ACLs und Eltern administrativ absichern und qualifizieren, Herkunft prüfen, exakte Nachweise ausdrücklich übernehmen, dann isoliert vollständigen Webablauf abnehmen. Nach Formatmigration ist ein bloßer Imagewechsel zu RC10 gesperrt. Das [Rollbackkonzept](MIGRATION.md) verlangt die konsistente Gesamtsicherung und eine Bewertung zwischenzeitlicher Arbeit.
