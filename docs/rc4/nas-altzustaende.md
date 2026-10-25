# RC4 – konkrete NAS-Altzustände

Basis: `9a77caf6c74b54c8154b288a5154d9c907b2abc0`, Tree `7292ae895ba069a43937027a3c9d2ff829f6436b`. Keine Verbindung zum NAS. Nur kleine synthetische Gegenproben; keine Gesamtsuite und keine Actions.

## A: fehlgeschlagener Papierkorb-Restore – Sperre bleibt bestehen

Der gemeldete Auftrag `TRASH_IMPORT_20261023_205446_538D89094806` ist fehlgeschlagen, nicht laufend. `known_restored` bezeichnet nur die abgeschlossene Behandlung des bekannten Anteils; es beweist nicht die Übernahme der übrigen `files` aus dem Staging. `partition_ok=true` beweist die Vollständigkeit der Aufteilung, nicht den erfolgreichen Import oder die Entbehrlichkeit der Originale.

`protected_trash_paths` hält die unbekannten/staged Dateien bis zum nachgewiesenen Cleanup reserviert. Das globale Leeren fragt diese Funktion vor der physischen Löschung ab. Der isoliert nachgestellte Zustand (`known_restored`, zwei unbekannte JPG/RAF-Stagingdateien, `failed`, kein Cleanup) reproduziert die Sperre. Der gespeicherte Fehlertext wurde dabei exakt übernommen. Warum der reale damalige Import keine verarbeitbaren neuen Dateien sah, ist aus diesem gespeicherten Fehler allein nicht beweisbar; Staginginhalt und vollständiger damaliger Pipelinebeleg fehlen. Es wird keine zusätzliche Ursache behauptet.

Eine abgeschlossene Wiederherstellung ist anders: vollständige disjunkte Partition, `cleanup_completed=true`, passende `skipped`-Liste, zugehöriger `completed`-Job mit passendem Stagingpfad und passendem Cleanup-Ergebnis ohne Warnung erlauben die vorhandene eng begrenzte Freigabe. Ein aktives oder ungeklärtes unabhängiges Restorejournal reserviert weiterhin. Ein ausgeblendeter Task oder allein `state=failed/completed` genügt nie.

**Gelieferte Produktänderung:** Die irreführende deutsche Meldung „Wiederherstellung läuft“ wurde durch „Eine Wiederherstellung läuft oder ist ungeklärt. Bitte fehlgeschlagene oder unterbrochene Aufträge prüfen; der Papierkorb bleibt gesperrt.“ ersetzt; EN ist entsprechend vorhanden. Die Sperrentscheidung selbst bleibt unverändert. Kein Journal und keine Datei werden dadurch bereinigt.

**Noch keine Auflösung auf dem NAS ausführen.** Für eine eng begrenzte, ausdrücklich bestätigte Aufgabe „fehlgeschlagenen Restore abbrechen, Originale behalten“ wären mindestens nachzuweisen:

- exakt ein globaler Auftrag mit dieser ID, Operation `trash_import`, unverändert `failed`, erwarteter Stagingpfad;
- vollständiges unverändertes Journal mit konkreten `files`, `known_paths`, Größen und SHA-256; für den kleinsten Weg ausschließlich unbekannte Dateien, `known_paths=[]`;
- beide Originale und beide Stagingkopien regulär und byteidentisch zu den Journalbelegen, keine ungeklärten Pfad-/Identitätswechsel;
- keine bereits übernommenen Datei-/Familienzeilen dieses Auftrags in allen registrierten Datenbanken, kein unvollständiger `.incoming`-Bestand und keine aktive/ungeklärte überlappende Restore-Reservation;
- keine konkurrierenden Dateioperationen, Sperren und Registrybindungen geprüft.

Dann könnte ein neuer dauerhafter **Abbruchbeleg** an genau diesen Journalinhalt und Job gebunden werden. Der ursprüngliche Fehlerstatus bliebe `failed`; das wäre kein erfolgreicher Restore und keine automatische Löschung. Erst ein später vom Benutzer ausdrücklich angefordertes Leeren dürfte die dann nicht mehr reservierten Papierkorbdateien löschen. Fehlende/abweichende Nachweise: Sperre erhalten und konkreten Konflikt anzeigen.

Dieser neue Weg wurde nicht integriert: Die automatische Freigabeprüfung lehnte die dafür erforderlichen Änderungen an Reservierungs- und Katalogpfaden zweimal als unzureichend nachgewiesen ab. Der zweite Versuch erfolgte nach erfolgreichem Sandbox-Selbsttest. Danach wurden keine weiteren Versuche zur Integration dieser Änderungen unternommen. Ein ungetesteter Entwurf ist ausschließlich außerhalb des Repositories gesichert und gehört nicht zum Produkt oder zum getesteten Abnahmepaket. Es ist eine ausdrückliche Entscheidung über diesen konkreten Abbruchweg erforderlich.

## B: Test 2 → Test 6 – vorhandenen manuellen Archiv-Editor verwenden

Die beiden abgeschlossenen Strukturänderungen werden nicht wieder geöffnet. Die isolierte Nachstellung führte zwei reale manuelle Änderungsabläufe mit dem damaligen Titelverhalten aus: Folder-Endstand `Final`, Name in SQLite und event.json noch `Trip`; aktueller JSON-Hash entspricht dem letzten Abschlussbeleg. Dies entspricht fachlich dem gemeldeten Test-2/Test-6-Zustand.

**Ein neuer Produktmechanismus ist für den manuellen Abgleich nicht erforderlich.** Der vorhandene Archiv-Editor kann einen neuen Änderungsauftrag mit dem neuen Titel und dem bereits richtigen Ordner erzeugen. Die neue event.json wird im vorhandenen Hilfsbereich vorbereitet. Ohne die passende manuell eingesetzte Datei verweigert der normale Verifier den Abschluss. Nach erfolgreicher Verifikation synchronisiert der normale Abschluss den Katalog. Die beiden alten abgeschlossenen Strukturänderungen bleiben bytegleich erhalten.

### Manueller Abnahmeweg für genau das gemeldete Ereignis

Diesen Ablauf erst mit bewusst freigegebenem Kandidaten und nach eigener Prüfung auf dem NAS ausführen. Es wird hier nichts auf dem NAS ausgeführt.

1. Andere Datei-/Archivaufträge beenden und während dieses Vorgangs keine parallelen Änderungen vornehmen. Mit der vorhandenen lesenden Diagnose exakt **Bibliothek `main`, Event-ID `EVENT_44A83046287D4403A39E02382E0EADCE`**, aktuelle Revision und beide abgeschlossenen Änderungs-IDs dokumentieren. Der letzte Abschluss muss den aktuellen Ordner und das aktuelle Dokument nachweisen. Erwarteter Hash vor Beginn: `28107680f7ea94daa2ff874b95b9434ce2e74baf4e20776d88ca82b5244f3074`. Abweichung, offene Aufgabe oder neuere Revision: stoppen und neu beurteilen.
2. Im bestehenden Archiv-Ereignis-Editor **dieses Ereignis** öffnen. Nur den Titel von `Test 2` auf `Test 6` setzen. Ordner `07-21 - Test 6`, Datums-/Zeitbereich, Unterereignisse, Ordnerlayout und ausgewählte Familien unverändert lassen. Die Vorschau muss nur den beabsichtigten Titel-/event.json-Abgleich verlangen. Wenn zusätzliche Bildverschiebungen, Familienänderungen oder Löschungen geplant werden: nicht bestätigen; Diagnose liefern.
3. Den **neuen** Archivänderungsauftrag bewusst bestätigen und dessen ID dokumentieren. Alte Journale nicht bearbeiten. Die Anwendung bereitet im vorhandenen Assign-Later-/Legacy-Hilfsbereich eine neue event.json vor; die konkrete Quelle und das konkrete Ziel zeigt der Assistent. Nicht aufgrund eines ähnlich benannten Ordners auswählen.
4. Die bisherige event.json mit dem genannten Hash außerhalb des beobachteten Ereignisordners sichern. Die vorbereitete Datei auf Event-ID, Titel `Test 6`, Folder `07-21 - Test 6`, Revision, Familien und Originalprüfsummen prüfen. Nur diese Datei am vom Assistenten ausgewiesenen Ziel `/main-library/2026/07-21 - Test 6/event.json` **ausdrücklich manuell ersetzen**. Keine Bilddatei verändern und keine fremde event.json übernehmen.
5. Über den vorhandenen Assistenten verifizieren und erst bei vollständiger Prüfung abschließen. Bei Konflikt bleiben Auftrag und Belege offen; kein SQL-UPDATE und keine Statusmanipulation. Die Änderung wird nicht dadurch erfolgreich, dass ein Dialog geschlossen wird.
6. Ereignisverwaltung, Saved Events und Archivhistorie aktualisieren: ID unverändert, Name `Test 6`, Ordner unverändert. Dateifamilien, Dateianzahl, Original-SHA und beide historischen Abschlussbelege vergleichen. Nach einem Prozessabbruch den vorhandenen neuen Auftrag prüfen und über dessen normalen Verifikations-/Abschlussweg fortsetzen; keinen zweiten Auftrag anlegen.

Dieser Weg hat keine neue automatische Hash-/Revision-Vorabfreigabe für historische Datensätze. Die gezielte Identitäts-/Hash-/Revisionsprüfung in Schritt 1 und der ruhende Betrieb sind deshalb verbindliche manuelle Voraussetzungen. Eine vollautomatische Einmalreparatur wird nicht behauptet.

### Gezielte Nachweise

- Kein automatischer Austausch im Archiv; vor dem manuellen Dateiersatz bleibt der alte Titel erhalten und der Abschluss wird abgewiesen.
- Falsche ID, falscher Titel, altes/fehlendes Dokument und veränderte Bildbytes werden abgewiesen; kein falscher Erfolg.
- Nach dem regulären Abschluss stimmen Katalog, event.json und kanonische Ereignis-/Archivansicht. Datei-IDs, Familien, Herkunft, Größe, Original-/aktuelle SHA und Bildpfade bleiben unverändert; alte Abschlussbelege ebenfalls.
- Echte SIGKILL-Proben vor dem Katalog-Commit und nach Commit vor Hilfsbereinigung: vor Commit Rollback und expliziter normaler Wiederabschluss, nach Commit stabiler Abschluss. Je drei neue Prozesse initialisieren SQLite und prüfen/führen den noch offenen normalen Abschluss aus. Das sind gezielte Domain-Recovery-Proben, **keine drei vollständigen TrueNAS-/Appstarts**. SQLite-Integrität und Fremdschlüssel bestehen.

## C: bestehende Legacy-Startsperre

`migrate_main_free_stock_to_central` verwendet `reconcile_migrated_file`. Sind sowohl die erwartete alte Arbeitskopie als auch das verifizierbare Ziel abwesend, fehlt der Nachweis eines abgeschlossenen Transfers. Weiterzumachen könnte Daten als migriert verbuchen, die gar nicht vorhanden sind; deshalb wird der Startup abgewiesen.

Der Mechanismus bestand bereits in `patch/0.56.2` (`35299e9`) und im unveränderten RC4-Vorstand `7f51309`. Die vollständigen Funktionen sind zwischen `7f51309` und `9a77caf` semantisch identisch; im älteren Basisstand gab es bereits dieselbe Quelle-/Ziel-fehlen-Sperre, trotz späterer anderer Schutzergänzungen. Nachweis: `legacy-startup-provenance.json` im QA-Paket, Originalquellstellen und kleine synthetische Gegenprobe. Es wurde kein historischer Gesamtlauf wiederholt.

Beim regulären Wiederimport mit intakten katalogisierten Arbeitskopien/Zielen ist diese Fehlerbedingung nicht erfüllt. Eine fehlende Archivkopie ist ebenfalls nicht automatisch ein fehlender Legacy-Arbeitsbestand. Bei genau diesem vorgeschädigten Legacy-Zustand kommt der Startup vor dem SD-Prüfworker zum Stillstand; die Queue behebt die Datenlücke nicht.

Sichere Benutzerreaktion: App angehalten lassen, zuerst Mounts, Zugänglichkeit und tatsächliche gespeicherte Pfade prüfen. Keine leeren Ersatzordner, Journalbereinigung oder Kataloglöschung. Eine nachweislich passende Original-/Sicherungskopie darf nach gesonderter Prüfung der erwarteten **aktuellen** Größe/SHA am richtigen ursprünglichen Ort manuell wiederhergestellt werden. Existiert keine passende Kopie, bleibt die Sperre bestehen; Datenbank, Journale und Diagnose sichern und die konkrete Datenlücke gesondert entscheiden. Ein beliebiges Original einer früheren Metadatenrevision ist kein Ersatz für die erwartete aktuelle Datei.

## Umfang des Commits

Zwei Produktdateien ändern ausschließlich die DE-/EN-Sperrmeldung. Keine neue Freigabe-, Restore- oder Kataloglogik. Neue synthetische Tests und Prozessadapter dokumentieren die vorhandenen sicheren Wege und verbleibenden Sperren. Keine Änderung der SD-Queue, F11/F24-Regeln, Versionsnummer, NAS-Rechte oder produktiven Daten.
