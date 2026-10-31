# pre.5: Storage, Beobachtungen und fachliche Schreibwirkungen

Stand: Entwicklung; keine Veröffentlichung oder native TrueNAS-Abnahme.

## Nachgewiesene Fehlerketten

1. Im veröffentlichten pre.4 legt ein GET der Workspace-Ansicht bei Bedarf eine
   Kompatibilitätsansicht unter einer F14-Schreibreservation an. Eine offene
   Operation erzwingt gleichzeitig einen lesenden Request. Daraus entsteht der
   protokollierte `operation_read_only_request` und HTTP 500. Die View-Auflösung
   verwendet jetzt ein pro Prozess privates temporäres Verzeichnis mit explizit
   qualifizierter Bindung an den echten Workspace. Sie benötigt keine fachliche
   Schreibreservation. Temporäre Views sind keine Medien- oder Recovery-Autorität.
2. Reconcile-/Inventory-Funktionen verändern keine Mediendateien. pre.4 behandelt
   ihre Ausnahme dennoch wie einen möglicherweise unterbrochenen Dateiaustausch.
   Die zurückbleibende Reservation sperrt danach unabhängige Schreiboperationen.
   Die neuen Tests führen den tatsächlichen veröffentlichten Code aus und lösen
   gezielt einen Hash-/Zugriffsfehler aus. Der genaue erste Auslöser auf dem NAS
   ist damit **nicht** bewiesen. Drei manuelle Änderungen ohne induzierte Ausnahme
   werden separat geprüft; eine Archivkopie ist kein nachgewiesener Auslöser.
3. Dieselbe Konstruktion betrifft die rein beobachtende Archivverifikation.
   Fehlender Ereignisordner wird lokal abgelehnt; die eigentliche Archivfreigabe
   mit möglichen Dateisystemänderungen behält ihre dauerhaften Schutzmechanismen.
   Auch die drei Sortiervorbereitungen erstellen ausschließlich SQL-Pläne.
   Eine fehlende Bestätigung oder ein veralteter Plan darf keinen vermeintlich
   ungeklärten Medienaustausch erzeugen. Ihre kurzlebige Reservation bewahrt
   dieselben Root-/Lock-Prüfungen. Erst der Executor beginnt die dauerhafte
   Medienoperation; ein committed Plan bleibt über seine SQL-Warteschlange
   wiederaufnehmbar. Historische Vorbereitungsbelege werden nicht als erfolgreich
   ausgeführte Sortierung behandelt.
4. Ein fachlicher Startup-Abbruch ist kein Beweis einer fehlenden DB-Verbindung.
   Diagnose prüft Verbindung, `quick_check`, Fremdschlüssel und das ausgelieferte
   Schema getrennt. SQL-Migrationen werden für den Vergleich ausschließlich in
   `:memory:` ausgeführt. Bestehende Kataloge werden nicht repariert oder ersetzt.
5. Die vollständige 90-Dateien-Fixture hat einen weiteren Fehler tatsächlich
   reproduziert: Nach Verschieben einer Tagesdatei nach General wird beim
   Upgrade die alte Main→Zentralbestandsmigration erneut aufgerufen. Der Auftrag
   verweist bereits auf den Zentralbestand; die Migration erwartet trotzdem
   jede Datei im alten Main-Arbeitsbereich oder am früheren Zentralpfad. Fehlen
   beide, entsteht ohne offene F14-Dateioperation eine Workspace-Schreibsperre.
   Bereits zentral geroutete Aufträge werden jetzt nicht als alte Layoutmigration
   interpretiert. Kein neuer Dateiort wird geraten und kein Hash umgedeutet.
   Tatsächlich noch nicht migrierte Altaufträge bleiben vollständig geprüft;
   fehlende Quellen oder fremde Zielbytes dürfen ihre Migration nicht abschließen.
   Gezielte neue Regressionen und der erneute gesamte Containerablauf stehen
   nach dieser Korrektur noch aus.
6. Die General-Aufnahmeprüfung verwendete nur aktuelle Katalogdateizeilen als
   Liste bekannter Kamera-Hashes. Nach bestätigtem Dateiverlust fehlen diese
   Zeilen, die unveränderliche Quellenmitgliedschaft besteht aber weiter.
   Der echte API-/Worker-Test 41190356694 nahm deshalb eine korrigierte bekannte
   JPEG per HTTP 202 an, schloss den Import ab und erzeugte eine zusätzliche
   Quellenfamilie ohne explizite Kopienherkunft. Datei-Hash, Neustart und Archive
   blieben korrekt; ein bloßes Ändern der erwarteten HTTP-Antwort wäre dennoch
   eine falsche Abnahme gewesen. Die Aufnahmeprüfung liest jetzt zusätzlich
   unveränderliche Mitgliedschaften und verfolgt abgeschlossene Korrekturketten
   linear über alle registrierten Bibliotheken. Diese Hashes verweigern nur eine
   implizite neue Herkunft. Sie werden nicht für Retained-Copy-/Duplikatentscheidungen
   oder zur Autorisierung von Dateioperationen verwendet. Unbekannte neue General-
   Dateien bleiben asynchron importierbar. Frühere bereits erzeugte Herkunftsbelege
   werden nicht gelöscht, zusammengeführt oder rückwirkend umgedeutet.

## Verbindliche Grenzen

Global gibt es ausschließlich `READY` und `UNAVAILABLE`. `READY` bescheinigt die
grundlegende Verwaltungsstruktur, keine erfolgreiche Einzeldateioperation.
Geschützte Anker, Mounts, Generationen, Datenbankintegrität und registrierte
Bibliothekswurzeln bleiben verbindlich. Eine leere, aber identische Wurzel ist
kein verlorenes Dataset. Ein neuer leerer Ordner ist kein Ersatz für einen
verschwundenen registrierten Anker.

Fachliche Wirkungen werden zusätzlich anhand der tatsächlich registrierten
Funktion, Operationsart und unveränderten F14-Reservation geprüft:

| Vorgang | Geschützter Wirkungsbereich |
|---|---|
| General-Korrektur mit privatem Tasknachweis | konkrete General-Datei |
| Unbekanntes oder fremdes Swapjournal | gesamter Metadatenbereich |
| Import/Sortierung/Archivvorgang | betroffene Bibliothek und gemeinsamer Zentralbestand |
| Papierkorb | Papierkorb, betroffene Bibliotheken und Zentralbestand |
| Sicherungslöschung | Bibliotheken und Zentralbestand |
| Unbekannte Funktion, ungültiger Beleg oder unbestimmbare Wirkung | Workspace-Schreibsperre; sichere Leseansichten bleiben erreichbar |

Scope ist **kein** Herkunfts-, Dateiort- oder Abschlussbeweis. Mutable SQL-Felder
allein dürfen historische APPLY-Reservationen nicht verengen. Verschachtelte
Operationen erweitern die äußere Wirkung dauerhaft; sie dürfen keine Wirkung
verschlucken. SQLite-Authorizer schützt auch bereits geöffnete Verbindungen.
Ein laufender Recovery-Kontext darf nicht nebenläufigen Requests seine
Sonderberechtigung vererben.

## Beobachtungen und historische Wiederaufnahme

Nur eine explizite Liste vollständig auditierter Funktionen darf eine transiente
F14-Reservation verwenden. Root-, Generations- und Kernel-Lock-Prüfungen bleiben
aktiv. Ein transienter Beobachter darf keine dauerhafte Medienmutation beginnen.
SQL-Transaktionen werden regulär committed oder von SQLite zurückgerollt.
Fehler werden nach deren Rollback bestmöglich als `observer_failed` protokolliert;
eine gesperrte Datenbank darf dabei weder Erfolg vortäuschen noch die ursprüngliche
Ursache verdecken.

Historische Beobachtungsreservationen werden nur nach exakter Prüfung von
Operationsschlüssel, kompletter Reservation einschließlich Nonce, registrierter
Datenbank, Bibliothek, Generation, Bindungen und SQLite-Konsistenz behandelt.
Der dauerhafte Unterbrechungsbeleg enthält die **vollständige ursprüngliche
Reservation**, `media_writes=false` und die Forderung einer erneuten Beobachtung.
Er wird vor der regulären Retirement-Operation geschrieben und synchronisiert.
Ein Wiederholungsaufruf muss zu demselben Beleg passen. Widersprüche bleiben
gesperrt. Dieser Vorgang erklärt keine Medienoperation für erfolgreich.

Alle echten Dateioperationen behalten ihre Journale, Hashprüfungen und
qualifizierten Abschlussregeln. Die DNG-Schreibverweigerung wird nicht durch `-m`
oder ein ExifTool-Upgrade umgangen. Ein `blocked`-Status alleine ist keine
Wiederherstellungsberechtigung.

## Lesende Oberflächen und aktive Aktualisierung

GET/HEAD lesen Katalog und Dateisystem ohne persistente Katalog-/F14-Schreibwirkung.
`physical_refresh=true` hebt diese Grenze nicht auf. Ein expliziter
`POST /api/workspace/refresh` aktualisiert den Bestand unter den normalen
Schreibgrenzen; ein fehlgeschlagener Refresh verhindert die anschließende sichere
Ansicht nicht. Die Tests vergleichen komplette SQL-Dumps und F14-JSON-Bytes.

## Metadaten-Variante A

Der Reimport bereits bekannter Kameraaufnahmen aus General bleibt derzeit
lokal abgelehnt. Die ursprüngliche Quellenfamilie und globale Claim-/Kopienidentität
lassen sich nicht durch Entfernen eines SHA-Guards ersetzen. Eine neue logische
Aufnahme benötigt ausdrückliche Kopienherkunft, unveränderte echte Inhalts-Hashes,
Zielkollisionsregeln und klare Ereigniszuordnung. Diese Erweiterung ist noch nicht
implementiert. Ein abgelehnter Reimport darf keine neue Reservation hinterlassen
oder unabhängige Aktionen verhindern.

## Datenbankdiagnose und Wiederherstellung

Die Oberfläche bietet Diagnose und konkrete Empfehlungen. Automatische
Neuinitialisierung, pauschales Setzen von `completed`, Löschen von WAL/SHM oder
ein universelles „Repair Database“ sind keine unterstützten Reparaturen.
Vor einer Wiederherstellung App stoppen und Appdata, Workspace, Journale und
F14-Nachweise konsistent zusammen sichern. Ursprünglichen Mount und Rechte prüfen;
anschließend einen bekannten konsistenten Stand als Ganzes wiederherstellen.

## Noch nicht abgenommen

Vollständige Backend-/Frontend-/Container-Abnahme wird in den Workflow-Nachweisen
gesondert geführt. Native TrueNAS-/NFSv4-ACLs, physische SD-/USB-Geräte und echte
DNG-1.7-Originaldateien: `NOT_RUN`. Synthetische TIFF-Daten mit RAF-Endung prüfen
Familienverarbeitung, keine native RAF-Schreibunterstützung. Ein eigenständiges
Verlustabschlussmodell bleibt `DEFERRED`.
