# pre.4 – Struktureller Speicher und fachliche Schreibfreigabe

Entwicklungsstand, keine Veröffentlichungsfreigabe. Basis: veröffentlichtes
v1.0.0-pre.3 (f18b377a5d3a6a04aab0d1b51ddd1d4c33dc9793).

## Nachgewiesene Ursache

`startup_database` mischte Schemainitialisierung, Dateisystem-Recovery, Inventar,
Claims und Herkunftsabgleich. Jede Ausnahme setzte `DATABASE_INITIALIZATION_ERROR`.
Middleware und Storage-API interpretierten dieses Feld als globalen Speicherausfall.
Zusätzlich wertete `inspect_storage` offene fachliche F14-Reservationen als globale
Storage-Probleme. Der technische Startup-Lease blieb bei solchen Fehlern ebenfalls
offen. Damit konnte ein einzelner unsicherer Dateiabschluss alle Seiten verdrängen.

Die neue Regel lautet: **Fachmodule dürfen den globalen Speicherzustand nicht allein
wegen fehlender Mediendateien, alter Dateipfade oder gescheiterter Aufträge ändern.**

## Zwei unabhängige Entscheidungen

- `managed_storage_health` / `storage_anchors`: ausschließlich READY oder UNAVAILABLE.
  Prüfen Verwaltungswurzeln, fest erforderliche Metadaten-Unterordner, registrierte
  Bibliotheksanker, Zugriff, Mount-Provenienz, Instanz/F14-Identität, Konfiguration
  und SQLite-Integrität. Eine noch unvollständige technische Einrichtung ist nicht
  READY; ihr Fortschritt wird separat beschrieben.
- `operation_health`: offene, lebende und verwaiste F14-Vorgänge sowie fachliche
  Recovery-Diagnosen. Unbekannte Auswirkungen sperren vorsorglich Workspace-Schreiben.
  Das ist kein zusätzlicher globaler Storage-Zustand. Eine feinere Isolation wird
  ohne belastbaren Nachweis der gesamten Schreibwirkung nicht behauptet.

`DATABASE_INITIALIZATION_ERROR` bleibt technischen Fehlern vorbehalten. Die
Startup-Reservation schützt nur technische Vorbereitung und deren Abschluss.
Fachliche Recovery folgt nach diesem Abschluss mit ihren ursprünglichen Nachweisen.
Unbekannte Altoperationen verhindern gewöhnliche Backfills/Workerfreigabe, nicht
Login und normale Leseoberflächen. Erneute Recovery wartet auf lebende Schreiber.

## Schreibschutz ohne Ersatzoberfläche

Die normale Navigation und die Seiten bleiben erhalten. Ein zusätzlicher Hinweis
zeigt die konkrete Operationsdiagnose. Fachlich gesperrte GET-Anfragen nutzen
SQLite `mode=ro` und `query_only`; sie führen keine Schemainitialisierung oder
opportunistische Bestandsreparatur aus. Nicht rein lesende Ansichtsfunktionen dürfen
mit einer konkreten Operationsdiagnose ablehnen. Sie setzen Storage nicht UNAVAILABLE.

Mutierende HTTP-Aufrufe, F14-Admission/Reservation/Stammänderung/Checkpoints und
registrierte SQLite-/Registry-Schreiber berücksichtigen die Operationssperre.
SQLite-Autorisierung ist eine zusätzliche Barriere, kein Ersatz der bestehenden
Dateisystem-Leases, Hash-, Inode-, Generations-, Journal- und Herkunftsprüfungen.

Explizite Wiederaufnahmezugänge qualifizieren zunächst ihre bisherigen vollständigen
Fachnachweise. Ihre Berechtigung ist an unveränderte ursprüngliche Reservations-IDs
gebunden. Andere ungeklärte Vorgänge bleiben ein Sperrgrund. Keine Bestätigung im UI
setzt Nachweise zurück; kein fehlendes Medium begründet einen neuen Quellbestand.

## Verwaltungsanker und Reparatur

Vorhandene F14-Bindungen bleiben maßgeblich. General/Allgemein und Batch Correction/
Mehrfachkorrektur erhalten zusätzliche erste Identitätsbeobachtungen. Vor dieser
Beobachtung ist eine rückwirkende Inode-Historie nicht beweisbar; es wird keine erfunden.
Gespeicherte Verwaltungsnamen haben Vorrang vor sprachabhängigen Standardpfaden.

Neue Unteranker werden nicht nach ihrem Verlust automatisch erstellt. Die bestehende
explizite Verlustbestätigung, dauerhafte Dokumentation, Mount-Prüfung und Generations-
änderung gelten auch für diese festen Rollen. Unbekannte Kinder, fremde Inhalte,
fehlende Datenträger und offene Operationen verhindern eine Ersatzannahme.
Dynamische Tagesordner, Medien, Staging-Dateien und abgeschlossene Journale sind keine
permanenten globalen Anker. Der private Wechselmedien-Tmpfs behält seine bestehende
Laufzeitqualifikation; seine wechselnde Kernel-Inode ist keine persistente Identität.

## Tatsächlicher General-Weg und Grenze des Fuji-Nachweises

Die UI ruft POST `/api/metadata-correction/general/reintegrate` auf. Die API erstellt
`.general-import/GENERAL_IMPORT_…`, kopiert und verifiziert die Auswahl und legt
`jobs.operation=metadata_general_import` an. Der echte Import-Worker publiziert in
SD Card Backups, dokumentiert `result_json.organization.imported_source_files`,
Manifest, Move-Journal, Katalog und unveränderliche Quellfamilien. Erst nach
verifizierter Veröffentlichung erfolgt die geschützte Quellbereinigung.

Eine zuvor nicht importierte General-Datei braucht vor ihrer Korrektur keinen
Importauftrag. General ist ein Dateisystem-Eingangsbereich; der Importauftrag
entsteht bei der regulären Übernahme. Die Korrektur selbst protokolliert Vor-/Nach-
Hash und Abschluss, bevor ihre F14-Reservation freigegeben werden darf.

`metadata_transfer_admission_missing_or_ambiguous` heißt konkret: null oder mehrere
passende `metadata_general_import`-Ergebniszeilen für Quellrelativpfad, Ausgabedigest
und Größe. Daraus folgt nicht, welcher Weg auf dem realen NAS ausgeführt wurde.
Der getestete echte API-Weg ersetzt keine unabhängig fehlende NAS-Historie. Es
werden keine Ziele anhand von Namen oder gleichartigen Hashes gesucht oder angenommen.

Für die reale Altinstallation werden bei Bedarf die drei Operationsdatensätze,
zugehörige Metadatenzeilen, Job-/Ergebniszeilen und die exakt referenzierten Import-
Protokolle benötigt. `qa/pre3/read_only_diagnosis.py` liest persistente Dateien nur
O_RDONLY und öffnet SQLite ausschließlich auf geprüften Kopien unter /tmp. Es
qualifiziert keine Freigabe und führt keine Recovery aus. Ausführung durch den
Benutzer optional im bestehenden Container als UID568; kein NAS-Zugriff durch Codex:

```sh
docker exec -i --user 568:568 CONTAINERNAME python - < qa/pre3/read_only_diagnosis.py > pre4-diagnosis.json
```

Das Skript liegt im Entwicklungscheckout des Benutzers; Containername muss geprüft
werden. Ausgabe kann private Dateinamen enthalten. Bei laufender Änderung verweigert
das Skript einen inkonsistenten Snapshot. Die App muss für diesen Diagnoseweg nicht
per SQLite/F14 manuell verändert werden.

## Verbleibende Grenzen

Eine nicht eindeutig belegte historische Dateiübernahme wird nicht als abgeschlossen
erfunden. Der Bestand kann dann lesbar sein, während Schreiboperationen bis zur
qualifizierten fachlichen Wiederherstellung geschützt bleiben. Unbekannte
Operationsarten erhalten keine automatische Pauschalbereinigung.

Native TrueNAS/NFSv4, echte DNG-1.7-Schreibunterstützung und physische SD/USB-Hardware
sind nicht durch Linux-Synthesetests belegt. Teststände sind in PROGRESS.md und dem
abschließenden Prüfbericht als bestanden, fehlgeschlagen oder NOT_RUN zu unterscheiden.
