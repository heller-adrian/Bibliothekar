# RC4 – sicherer Abschluss fehlgeschlagener Papierkorb-Restores

Basis: `c2a0b1faae53c541ad9fae6b34ffa54083dab0f0`, Tree `5c91fa3a60d55bcf0838db3735129d6fc953713a`.

## Tatsächlich implementierter Umfang

Der einzelne ausdrücklich bestätigte Fehlerabschluss funktioniert. Originale und unabhängige, vollständig geprüfte Stagingkopien bleiben erhalten. Der Job bleibt `failed`; Journal und ursprüngliche Fehlermeldung bleiben bestehen. Nach erfolgreichem Abschluss sind die reservierten Papierkorbdateien wieder über die normalen, ausdrücklich bestätigten Löschfunktionen löschbar. Die Rückfallkopien bleiben dabei erhalten.

**Nicht integriert:** automatische Finalisierung aller Altaufträge beim Lesen der Inventur und automatische Worker-Finalisierung nach neuen Fehlern. Die automatische Freigabeprüfung lehnte diese Anbindungen als noch nicht ausreichend validierte Ausweitung ab. Sie wurden nicht über andere Einstiegspunkte nachgebaut. Die Inventur beschreibt den Zustand nur; der einzelne POST erfordert eine ausdrückliche Bestätigung. Dies ist ein nutzbarer kontrollierter Abbruchweg, keine vollständige Umsetzung der gewünschten Automatik.

## Ursache und Unterschied zum alten Entwurf

`known_restored` bezeichnet den bereits behandelten bekannten Anteil; das ist kein Abschlussbeleg für die `files` des unbekannten Anteils. Ein fehlgeschlagener Job ohne Cleanup reserviert diese Dateien weiter. Der echte JPG-/RAF-Zustand wird isoliert nachgestellt. Der alte Entwurf speicherte primär einen terminalen Abbruchbeleg; er belegte die dauerhafte Verfügbarkeit unabhängiger Kopien und deren Schutz vor späterem regulärem Cleanup nicht ausreichend.

Der neue Abschluss erfordert:

- genau einen registrierten fehlgeschlagenen `trash_import` mit erwarteter Quelle, unveränderten Datenbankidentitäten und vollständiger Registry;
- eine vollständige disjunkte Quellauswahl mit Größen/SHA, `status=known_restored`, ausschließlich unbekannte Dateien, `known_paths=[]`, kein Cleanup;
- keine Datei-/Familienzeilen dieses Jobs in irgendeiner betroffenen Bibliothek, keinen `.incoming`-Teilbestand und keine überlappende offene Restore-Recovery;
- vorhandene reguläre Originale und für jede Datei eine vollständige SHA-identische **physisch unabhängige** Stagingkopie; keine Symlinks oder Hardlinks als vermeintliche Rückfallkopie;
- privat gebundenes Staging (App-UID, Modus 0700), sichere No-follow-Directory-FDs, Datei-/Verzeichnisidentität und fsync der Rückfallkopien und Verzeichnisse.

Es wird keine Quelle oder Rückfallkopie neu kopiert, verschoben oder gelöscht. `failure_finalization` ergänzt das bestehende Journal und das Jobresultat. Alle bisherigen Journalfelder und der Fehlerstatus bleiben erhalten. Die bestehende atomare JSON-Veröffentlichung und SQLite-Transaktion schreiben nacheinander: Journal `prepared` → Jobresultat/Audit → Journal `committed`. Zwischenstände erlauben keine Löschung. Ein bestätigter Wiederholungsaufruf prüft alles erneut und vollendet denselben Beleg; es entsteht kein zweiter Import oder Auditabschluss.

Ein gespeicherter Beleg allein berechtigt nie zum Löschen: `protected_trash_paths` verifiziert ihn bei Verwendung erneut gegen die tatsächlichen Rückfallkopien, Journal-/Jobresultat, Datenbanken, Originalidentitäten und Hashes. Bereits ausdrücklich gelöschte Papierkorboriginale werden nicht als vorhanden behauptet. Die normalen Cleanup-/Prepare-/Resume-Funktionen verweigern die erneute Verarbeitung oder Löschung der aufbewahrten Kopien.

## Bedienung und ungeklärte Fälle

Während aktiver oder ungeklärter Wiederherstellung sind Löschaktionen in der Oberfläche gesperrt. Die Server- und physischen Eintrittspunkte prüfen dies zusätzlich innerhalb der bestehenden F11-Sperre. Auch die selektive Löschung unbeteiligter Dateien ist während einer aktiven Wiederherstellung gesperrt.

Auf der Papierkorbseite erscheinen Job-ID und Diagnose. Für einen fehlgeschlagenen Auftrag gibt es **„Fehlgeschlagene Wiederherstellung sicher abbrechen“ / “Safely cancel failed restore”**. Die Bestätigung erläutert den Dateierhalt. Ein erfolgreicher Abschluss zeigt den Ort der behaltenen Rückfallkopien; es wird kein erfolgreicher Import behauptet.

Fehlende/beschädigte Originale oder Kopien, Teilkopien, fehlende Manifestbelege, gemischte bekannte/unbekannte Altaufträge, Teilimporte und widersprüchliche Identitäten bleiben gesperrt. Der Button prüft diese Voraussetzungen erneut und liefert bei verbleibendem Konflikt HTTP 409. Er rekonstruiert keine unbekannten Daten. Benannte Dateien/Belege müssen aus einer nachweislich passenden Sicherung untersucht bzw. wiederhergestellt werden. Kann das nicht bewiesen werden, bleibt die Sperre bestehen; keine Journalentfernung oder Statuskorrektur zur Umgehung.

Die Rückfallkopien belegen weiterhin Speicherplatz im bestehenden privaten `.trash-import/<job_id>`-Bereich. Sie werden absichtlich nicht durch Papierkorbleeren oder reguläres Cleanup entfernt. Eine spätere Bereinigung dieses letzten Sicherungsbestands ist hier nicht implementiert. Kein neues Dateisystem, keine Snapshots und keine Privilegienänderung.

## Abnahme auf TrueNAS für den belegten Altauftrag

1. Erst den geprüften Kandidaten bereitstellen; keine produktive Installation wurde durch diesen Auftrag verändert. Zunächst zwei synthetische JPG/RAF-Dateien und einen synthetischen fehlgeschlagenen Restore erproben.
2. In der Papierkorbseite exakt `TRASH_IMPORT_20261023_205446_538D89094806` identifizieren. Die Anzeige „bereit“ darf nur nach vollständiger Prüfung erscheinen; bloßes Seitenöffnen ändert keinen Abschlussbeleg.
3. Bei Meldung über fehlende Kopie/Original, Hash-, Identitäts-, Katalog- oder Rechtekonflikt stoppen und die konkrete Diagnose sichern. Insbesondere keine ACLs pauschal lockern und keine Journale löschen.
4. Den einzelnen Auftrag ausdrücklich sicher abbrechen. Erwartung: Job weiterhin `failed` mit ursprünglichem Text, neuer konsistenter Abschlussbeleg, zwei erhaltene Papierkorboriginale und zwei unabhängige Rückfallkopien. Deren angezeigten Pfad und SHA-Nachweise dokumentieren.
5. Den Vorgang erneut prüfen und die App neu starten. Erwartung: derselbe Beleg, keine doppelte Arbeit, normale Anzeige. Ein unterbrochener `prepared`-Abschluss wird nur über den erneuten bestätigten Aufruf fortgesetzt; bis dahin bleibt die Sperre bestehen.
6. Erst danach wie gewohnt selektiv oder vollständig leeren. Die zwei Rückfallkopien müssen SHA-identisch erhalten bleiben. Keine zweite unklare Reservation darf dabei verschwinden. Der zweite bereits erfolgreiche NAS-Auftrag bleibt unverändert.
7. Reale TrueNAS-/NFSv4-ACL-/UID-/Mount-Eigenschaften sind noch zu qualifizieren. POSIX-Modus-/UID- und FD-Prüfungen ersetzen diesen Plattformnachweis nicht. Keine Sicherheit gegen einen privilegierten bzw. anderweitig berechtigten externen Schreiber behaupten; die zuvor akzeptierte F24-Grenze bleibt bestehen.

## Nachweise und Grenzen

Gezielte Tests, Matrix und Rohlogs werden im QA-Paket mitgeliefert. Die vier Prozessfälle führen die reale Anwendungsinitialisierung/-Recovery aus; nur parallele Workerthreads werden für die deterministische QA unterdrückt. Danach wird derselbe bestätigte Abschluss ausdrücklich wiederholt. Die Oberfläche wurde über ausgeführte JavaScript-Funktionen und Syntaxprüfung getestet; eine neue echte Browser-/TrueNAS-Abnahme ist offen. Echte SIGKILLs an vier Commitgrenzen, jeweils drei neue Prozesse, Original-SHA, unabhängige Kopien, SQLite-Integrität/Fremdschlüssel, erneute Sperre bei nachträglichen Änderungen sowie F11/F24-/normale Restore-Gegenproben. Keine Gesamtsuite oder Actions. Die SD-Queue und der bestätigte manuelle Archiv-Titelworkflow bleiben unverändert.
