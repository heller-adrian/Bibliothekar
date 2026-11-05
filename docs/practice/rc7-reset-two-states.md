# RC7: zwei zeitlich getrennte Neueinrichtungszustände

Fall A wird unabhängig vom später entfernten Kontrollordner reproduziert:
volle alte Wurzelbindungen ohne storage_initialization plus unbenutzter
technischer Registryplatzhalter; zusätzlich ein generation-zero F14-Nachweis,
der nur den unveränderten Workspace bindet. Der aktuelle Startup erzeugt keine
Bibliothekszeile. Der Platzhalter ist deshalb eine isolierte historische Variante,
kein Beweis, dass genau diese Zeile auf dem NAS existiert. Aktueller Startup kann
Schema, Standardeinstellungen und F14-Bindungen erzeugen. Frühere unknown_initialization-
Rohbelege aus RC6 bleiben gültig; RC7 löste deren vollständigen Bindungsfall bereits.

Fall B entfernt ausschließlich in der Wegwerffixture anschließend auch den
Kontrollbereich. Bisher scheiterte dessen Qualifikation an FileNotFoundError.
Ein fehlender Kontrollbereich ist keine pauschale Erlaubnis: der gesamte bestehende
Leerheitscheck wird auch vor einer automatischen Erstinitialisierung durchlaufen.
Insbesondere vorhandene private Retention blockiert, selbst wenn DB und Kontrolle
fehlen. Der Verlust historischer Identitäten wird nicht als geprüfte Kontinuität
bezeichnet. Ein bestätigter Abschluss protokolliert den vorher fehlenden Zustand
als {} und die erstmals gebundene aktuelle Workspace-Identität.

Der neue Registryfall ist streng begrenzt: genau eine unregistrierte main-Zeile,
explizite bootstrap/onboarding_required-Marker, exakt gebundene Pfade, keine
Stilllegungszeitpunkte und keine anderen Bestands-/Claim-/Medientabellen. Flags
oder Namen allein reichen nicht. Kataloge, Workspace, Archive, private Retention,
Operationsbelege, FD-/No-follow- und ACL-Prüfungen bleiben zusätzlich erforderlich.
Eine echte oder stillgelegte Bibliothek bleibt geschützt. Registryzeilen werden
nicht gelöscht; ihr vollständiger Stand wird archiviert und in den Bestätigungstoken
aufgenommen. Der normale Bibliotheksanlageweg registriert anschließend ausdrücklich
 die erste echte Bibliothek. Der technische Platzhalter ist kein fehlender
konfigurierter Arbeitsordner und wird beim Bootstrap nicht als solcher verwendet.

Generationszähler >0, teilweise positive Wurzelbindungen, unbekannte F14-Felder,
Widersprüche, aktive Operationen und SQLite-WAL-/Journalreste bleiben gesperrt.
Ein in einer Testfixture offen gebliebener SQLite-Writer wird korrekt abgelehnt;
die Fixture wird regulär committed/checkpointed/geschlossen, keine Produktprüfung
aufgeweicht. Ein echter ungeklärter WAL-Rest benötigt konsistente Recovery bzw.
Wiederherstellung, keine Dateilöschung.

Gezielte Prozess- und Containerprüfungen behandeln beide Zustände getrennt,
einschließlich Bestätigung, tatsächlichem Onboarding, drei Prozessneustarts,
Containerneustart, SIGKILL und negativen Bestandsfällen. Native TrueNAS-/NFSv4-
Qualifikation bleibt offen. Kein Eingriff auf dem NAS, kein Release, keine
Versionsänderung und keine Anweisung zu einem weiteren Clean Slate.

Zusätzlich tatsächlich nachgewiesener Lese-Nebeneffekt: main._onboarding_required()
ruft list_libraries/_connect auf. PRAGMA journal_mode=WAL erzeugt bei fehlender
Registry eine SQLite-Headerdatei; SELECT auf die noch nicht vorhandene Tabelle
schlägt fehl und wird als Onboardingzustand behandelt. Die bisherige Prüfung
wertete diesen nun vorhandenen Header als unbekanntes Schema und sperrte den
anschließenden Reset. Eine spätere generische Datenbankabfrage kann denselben
Headerzustand beim Hauptkatalog hinterlassen.

Behandelt wird ausschließlich die eine leere SQLite-Schemaseite: sqlite_master
enthält keinerlei Objekte, page_count=1, freelist_count=0, application_id=0 und
user_version=0. Benutzerdefinierte Kennungen/Schemata und SQLite-Seitenreste werden
nicht als technische Erstinitialisierung eingestuft. Diese Regeln ersetzen keine
Medien-/Registry-/Mount-/Retentionprüfung. Zwei originale Header-Gegenproben FAIL,
nach der eng begrenzten Ergänzung vier Header-/Kennungsgegenproben PASS.
