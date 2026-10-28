# RC13: automatisierter Abnahmenachweis

Status: Alle verpflichtenden automatisierten Belegsätze bestanden.
Native TrueNAS-/ACL-Abnahme steht separat aus; RC13 bleibt ein Prerelease.

| Nachweis | Quellstand | Ergebnis |
|---|---|---|
| Vollständiges Backend, acht Gruppen | `fa803ca7e2435f69c6a226e46bccfab528712571` | 2.189 PASS, 0 SKIP |
| Vorgeschaltetes Fehler-/Sicherheitsgate | derselbe Stand | 101 PASS, 0 SKIP |
| Chromium DE/EN, Mobil/Desktop | derselbe Stand | 44 PASS |
| Reale Supervisor-/Containerfälle | `1ceac829fd2481381bd0ac22b407e613ae08c2f1` | 46 PASS (2 RC13 + 25 RC12 + 19 RC11) |

[Backend-/Browserbelege](https://github.com/heller-adrian/Bibliothekar/actions/runs/40661973452),
[Containerabnahme](https://github.com/heller-adrian/Bibliothekar/actions/runs/40667478387).
Die ursprüngliche Gesamtworkflowanzeige bleibt wegen ihrer fehlgeschlagenen
Containerfixture rot. Deren ExifTool-Fehler wurde lokal reproduziert und korrigiert;
er wird nicht als bestandener Test umgedeutet. Die gesonderte Containerprüfung
prüft per Git-Diff, dass App, Tests, Abhängigkeiten und übrige QA gegenüber dem
vollständig bestandenen Backend unverändert sind. Nur die RC13-Bilderzeugung und die Prüfung des bereits bestehenden
RC12-Reparatur-Neustartvertrags weichen in den Containerfixtures ab. Die Releaseprüfung verlangt beide vollständigen Belegsätze.

## Verfahren

Basis: `v1.0.0-rc.12` (`671d7e7eb96ff493ae51720bb2769eccd8f9048f`).
Die vollständige Linuxsammlung läuft auf Ubuntu 24.04 mit Python 3.12,
ExifTool, echten Prozessen und Linux-inotify. Alle gesammelten Backend-IDs
werden auf acht disjunkte Gruppen verteilt. Die Veröffentlichung prüft anhand
von Sammlung, JUnit und inkrementellen Ergebnissen jede ID genau einmal,
keine fehlenden Dateien, keine Fehler, keine ausgelassenen Tests.

Das vorgeschaltete Gate reproduziert die Fehler früherer Läufe einschließlich
Startup-Reihenfolge, Metadaten-Crashes und einer unabhängigen SSD-SIGKILL-Fixture.
Die Ursachen sämtlicher fehlgeschlagener Gruppen aus `40607188501` sowie der
Folgeprüfung stehen in [CI-FAILURES.md](CI-FAILURES.md). Historische Testquellen
bleiben zusätzlich durch ihre SHA-256-Manifeste geschützt.

## Backend und Sicherheit

- Ursprüngliche Quelle nach bestätigtem Teil- und Gesamtverlust; unveränderte
  kanonische Familie und ursprüngliche Memberliste.
- Ablehnung fehlender/falscher Audits, geänderter ursprünglicher Hashes/Größen,
  unzulässiger Neuregistrierung und nicht zugehöriger Reservationsnachweise.
- Zweite Bibliothek mit qualifizierter ursprünglicher Herkunft einschließlich
  schon vor ihrer Projektion bestätigter Fehlbestände.
- Genau gebundene, noch unvollständige Importpublikation nach echtem SIGKILL.
- Atomarer State-Austausch; begrenzte Wiederholung und fortbestehende Ablehnung
  von Symlinks, Hardlinks, Fremdeigentümern und ungültigem JSON.
- Die vollständigen bisherigen F14-, Journal-, Retention-, Mount-,
  Berechtigungs-, Wiederherstellungs- und Verlustbestätigungstests.

`storage_replacement.py` und `managed_storage_health.py` sind gegenüber RC12
unverändert. Die Reparaturdarstellung sendet dieselben Requests und verlangt
weiterhin dieselben Bestätigungen.

## Frontend

44 Chromiumfälle: Deutsch/Englisch, 390/1280 Pixel, tatsächliche gerenderte
Archivänderungs-/Rückänderungsdialoge, verschachtelte Familien, dynamische
Containerpfade, Zähler, Status und geschützte Namen. Echte Sprachwechsel auf der
Reparaturseite sowie der Clipboard-Fallback für normale HTTP-Ursprünge werden
geprüft. Das mobile X blendet nur den Sitzungsstatus aus und sendet keinen
Mutationsrequest. Die einzelnen Originalbefunde stehen in
[SCREENSHOTS.md](SCREENSHOTS.md).

## Reale Docker-/Supervisorabnahme

Die Images werden aus dem exakten Kandidaten und dem veröffentlichten
RC12-Commit gebaut. Die originalen Supervisor-/Webprozesse verwenden UID/GID
568:568, echte RW-/RO-Bindmounts, authentifizierte HTTP-Sitzungen und CSRF.

Die zwei RC13-Fälle erzeugen mit RC12 durch einen echten HTTP-Import eine
JPEG/RAW-Familie, entfernen das JPEG und bestätigen den Verlust durch zwei echte
Abgleiche. Sie reproduzieren den gesperrten RC12-Neustart und aktualisieren
dieselben Volumes auf RC13. Ursprüngliche Registrytabellen, RAW-Inode und
Dateibytes werden verglichen. Danach folgen zweite Bibliothek, wiederholte
Neustarts und geschützte Papierkorboperationen. Der zweite Fall beendet den
Webprozess an der qualifizierten Herkunftsgrenze mit SIGKILL und prüft den
Wiederanlauf unter demselben Supervisor.

Zusätzlich werden alle 25 bestehenden RC12-Speicherreparatur-/Bootstrapfälle und
alle 19 RC11-Migrations-/Crashfälle ausgeführt. Falls der bereits festgeschriebene Ersatz wegen einer belegten
F14-Sperre ausdrücklich einen Neustart verlangt, prüft die QA genau diesen
bestehenden API-/UI-Vertrag: vollständige Identitätsgleichheit vor/nach dem
Neustart, READY und anschließende geschützte Mutation. Andere Startupfehler
bleiben Testfehler. Reine `ready`-Antworten gelten
nicht als Nachweis freigegebener Mutation.

Die Importbilder sind künstlich; die kleine `.RAF`-Testdatei enthält für diesen
Metadaten-/Herkunftsablauf JPEG-kodierte Bilddaten. Echte proprietäre RAW-Decoder
werden durch diese Fixture nicht abgenommen.

## Grenzen und Veröffentlichung

Keine native TrueNAS-/OpenZFS-/NFSv4-Abnahme; keine Änderungen am NAS.
Die separate Erstinstallations-/ACL-Abnahme folgt ausdrücklich später.
Browserfälle prüfen reale Templates mit synthetischen API-Antworten;
Containerfälle prüfen die echten authentifizierten HTTP- und Backendabläufe.
Ein Zugriff auf die tatsächliche TrueNAS-Browseroberfläche wurde nicht behauptet.

Alle Belegsätze wurden zusätzlich heruntergeladen und mit der identischen
Veröffentlichungsprüfung unabhängig validiert: 2.189 Backendfälle genau einmal,
101 Gatefälle, 44 Browserfälle und 46 Containerfälle vollständig PASS.
Die Veröffentlichung verlangt dieselbe Gesamtprüfung erneut.
Sie erstellt das Image aus dem abschließend dokumentierten Quellstand; App-/Testcode müssen zu beiden
geprüften Ständen identisch sein. Sie prüft alle Appdateien,
zieht es anschließend tatsächlich per unveränderlichem Digest aus GHCR und
prüft Version, OCI-Revision und Image-ID. Releaseartefakte enthalten
`IMAGE-DIGEST.txt`, Pullbeleg, vollständige QA-Belege, `CHANGED-FILES.txt`,
Quellpaket, Installationsanleitungen, digestgebundene Compose-Datei und
`SHA256SUMS`. Repository und Paket bleiben privat.
