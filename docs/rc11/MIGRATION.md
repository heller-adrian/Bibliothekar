# F14-Format 2, Belege und Rollbackgrenze

RC11 verwendet für private Kontrollzustände Format 2. Format 1 wird lesend geprüft und nur im qualifizierten Übergang übernommen. Alte Root-/Bibliotheksgenerationen und Bindings werden nicht zurückgesetzt. Ein alter RC10-Prozess lehnt Format 2 ab; damit darf er keine zweite Workspace-Lockwelt betreiben. Der erste Übergang setzt trotzdem den vollständigen Stillstand von RC10 und exklusiven F14-Ausschluss voraus.

Ein neuer oder übernommener Bootstrap speichert `bootstrap_id`, `reservation_id`, ursprünglichen `operation_key`, Namen, Datenbank und Herkunft. Die Phasen sind `initializing`, `prepared`, `completed`. Onboarding ist unabhängig davon der Zustand ohne registrierte Benutzerbibliothek.

Abschlussreihenfolge: erfolgreiche technische Schritte → Wurzel-/Historien-/Registryprüfung → prepared → dauerhaftes `bootstrap-completed-<ID>.json` → completed mit Referenz → dauerhaft archivierter Operationsnachweis → aktive Reservation freigeben → Worker und Benutzerbetrieb. Der endgültige Beleg wird nicht als temporäres Receipt entfernt. Ein Crash zwischen diesen Veröffentlichungen setzt dieselbe Reservation fort; er erzeugt keinen unabhängigen Startup mit `ids={}`.

Alte RC10-completed-Zustände mit noch offener Initialisierungsoperation werden nach ausdrücklicher Übernahme nicht ungeprüft als fertig geglaubt. RC11 prüft die technischen Postbedingungen erneut und schließt die Originalreservation mit einem echten Receipt ab.

RC11-temporäre Veröffentlichungen enthalten im Dateinamen den Hash ihres konkreten Zielnamens. Unter einer exakt qualifizierten eigenen Bootstrapreservation werden passende uncommitted Reste als solche beobachtet und unverändert erhalten; sie autorisieren keinen Abschluss. Fremde Zielnamen, unbekannte alte Reste und positive Historie blockieren. Kein partielles JSON wird als committed State interpretiert.

## Rollback

Vor einer Formatmigration ist eine konsistente Gesamtsicherung obligatorisch. Nach Migration genügt ein Imagewechsel zu RC10 nicht: Das unbekannte Format soll RC10 ausdrücklich stoppen. State, DBs, WAL/SHM, Registry, Config, Nachweise und Dateisystembindungen gehören zusammen.

Eine Wiederherstellung der alten Gesamtsicherung ist nur nach Stillstand aller Writer und mit gesonderter Bewertung seitdem entstandener Bibliotheken/Medienarbeit zulässig. Neue Arbeit darf nicht durch einen technischen Rollback verschwinden. Ein Inodewechsel bei Kopie/Restore ist kein Anlass, Bindings blind umzuschreiben; er benötigt das bestehende explizite Recoveryverfahren.

Das Zurücksetzen von `format`, `completed`, Generation oder einzelnen Reservationsdateien ist kein unterstützter Rollback.
