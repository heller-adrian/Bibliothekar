# Pre.5 – Veröffentlichungsprüfkette 02.11.2026

Freigegebener Anwendungscode: `b4c3a397843567bfe09b35e82c51d0009d0a71bf`.

| Stufe | Unabhängig verifiziertes Ergebnis | Tatsächlicher Quellstand |
|---|---|---|
| Vollständiges Backend | [41457182080](https://github.com/heller-adrian/Bibliothekar/actions/runs/41457182080):2579 PASS,0 FAIL/ERROR/SKIP; acht disjunkte Partitionen und exakte JUnit-Nodegleichheit |18c01fe6730eb4c102c9085eb648325eda2b6622|
| Vollständige Containerabnahme |[41508993713](https://github.com/heller-adrian/Bibliothekar/actions/runs/41508993713): API, Supervisor, Neustarts, Browser,90 Dateien,4000 Familien und14 iPhone-JPEGs PASS |93bb7da6d43570759b7428683f073a7f7244ddff|
| Finale Original-RC14-Migration |[41509736127](https://github.com/heller-adrian/Bibliothekar/actions/runs/41509736127):14 JPEGs, Originalreservation bis POST erhalten, Herkunft/RO-Archive unverändert PASS |b4c3a397843567bfe09b35e82c51d0009d0a71bf|
| Finale Ziel-/Negativtests |41509736127:62 Pre.5-,82 fokussierte und2 unabhängige RC14-Negativfälle PASS; Gruppen überschneiden sich |b4c3a397843567bfe09b35e82c51d0009d0a71bf|
| Vollständiges Frontend |Frontendjob von41363591064 SUCCESS:44 RC13-/147 RC14-Fälle; damaliger Gesamtlauf war wegen später separat behobener Backend-/Containerfehler FAILURE |da042bc96eb40a383c6ecae2b9ab70fe87e4b1c6|

Die2579 Backendtests wurden ausdrücklich nicht auf dem späteren Finalcommit ausgeführt. Die Anwendung unterscheidet sich danach nur in `main.py`, `metadata_scoped_recovery.py` und der neuen `metadata_legacy_rc14_recovery.py`; Datenbankschemata, Abhängigkeiten und Containerkonfiguration sind unverändert. Diese begrenzte Änderung ist durch finale Zieltests und die Original-RC14-Containerprüfung abgedeckt. Der Publisher führt zusätzlich die betroffenen alten F14-Retry-/Scoped-Recovery- und SQL-Negativverträge auf dem eingefrorenen Finalcode sowie die komplette Laufzeitabnahme auf dem tatsächlich gebauten Release-Image aus. Ohne deren PASS wird kein Tag/Image/Release geschrieben. Eine erneute mehrstündige Vollmatrix ist bei dieser dokumentierten Quellgleichheits-/Deltaqualifikation nicht erforderlich.

Alle akzeptierten ZIPs wurden erneut gegen die GitHub-SHA256-Digests geprüft. Die unveränderlichen Artefakte und ihre tatsächlichen Quell-Commits werden in `release/ACCEPTANCE.json` gebunden; erfolgreiche Einzeljobs aus einem roten älteren Gesamtlauf sind dort ausdrücklich als solche gekennzeichnet, niemals als grüner Gesamtlauf.

NOT_RUN: native TrueNAS/NFSv4, physische SD/USB, echte DNG1.7- und native RAF-Schreibunterstützung. DEFERRED: bekannte-Aufnahme-Variante A und eigenständiges Verlustabschlussmodell. Keine DNG-Warnunterdrückung, kein `-m`.

Die vollständige Image-, OCI-, Pull- und Release-Artefakt-Verifikation ergänzt der veröffentlichte Prüfbericht. Die folgenden Abschnitte bleiben als historische Entwicklungschronik erhalten.

---

# pre.5 – Zwischenbericht der isolierten Linux-Abnahme

**Keine Freigabe durch Testergebnisse, nicht veröffentlicht.**
Die Zahlen einzelner Stufen überschneiden sich; sie sind keine aufsummierte
Anzahl unterschiedlicher Regressionen. Kein Zugriff auf TrueNAS.

| Lauf | Tatsächliches Ergebnis |
|---|---|
| 41080385540 | Container erwartete fälschlich `completed` statt des vollständig erfolgreichen Sortierstatus `applied`. QA korrigiert, Produktstatus beibehalten. |
| 41113291699 | 236/237 historische Tests bestanden. Veraltete Idle-Claim-Erwartung über initialen state.json korrigiert; unveränderte Belege und keine neuen Operationsjournale bleiben Pflicht. |
| 41116260923, Quelle c548e308 | 42 neue + 46 fokussierte + 237 historische Tests bestanden, jeweils ohne Fehler/Skips. General-API, zwei Neustarts, Import/Ereignissortierung trotz erhaltenem Einzelkonflikt, Chromium und sechs historische Containerfälle bestanden. 90er Fixture scheiterte vor Appstart am Erzeugen synthetischer RAF-Dateien. |
| 41119010880, Quelle 64645b5f | 46 neue + 46 fokussierte Tests bestanden. Frontend: 44 RC13-/147 RC14-Fälle bestanden. Backend: keine Tests ausgeführt, Collection scheiterte am gruppenbeschreibbaren Runner-Elternpfad. Private Testumgebung nach /tmp verlegt, Rechteprüfung beibehalten. |
| 41119010880, Container | General-/Scoped-/historische Containerfälle bestanden. Echter 90-Dateien-/47-Familien-/8-Tage-Import mit Applied-/Archiv-Ereignis und drei manuellen Änderungen aufgebaut. pre.4-GETs jeweils 200, keine offene Reservation. Nach Upgrade neue Schreibsperre wegen unnötig wiederholter Legacy-Zentralmigration nachgewiesen. Keine Behauptung, der erste NAS-Inventory-Abbruch sei damit erklärt. |
| 41121252978, Quelle 83b11dad | 49 neue Tests bestanden, darunter tatsächliche pre.4-Migrationsreproduktion, positive Fortsetzung und Ablehnung fehlender/fremder Bytes bei echter Alt-Migration. Fokussiert 67 PASS / 13 FAIL: zwei alte Versionsvorgaben, ein unvollständiger Ankeraufbau, zehn Seed-Fehler. |
| 41122388040, Quelle 96d538fa | 49 neue Tests bestanden. Fokussiert 70 PASS / 10 FAIL: verbliebene Prozess-Seeds scheitern an noch nicht angelegten Katalogen/Registry vor dem Legacy-Layoutcheck. Pflichtschemata werden in der Fixture jetzt vorher erzeugt. Originale signierte QA-Dateien bleiben unverändert. |
| 41123293238, abgeschlossen | 49 Zieltests und 80 fokussierte Tests PASS; Frontend PASS. Container erreichte General-Reintegration und erhielt unerwartet 202; vor Auswertung des Auftrags gestoppt. |
| 41190356694, Quelle cefeb5cb | Strikte Diagnose gegen unveränderte Anwendung: unerwarteten 202-Auftrag bis completed/organized_verified verfolgt. Zieldatei hat korrekten Ergebnis-Hash; ursprüngliche Herkunftsbelege und Read-only-Archive bleiben erhalten; nach Neustart READY und keine offene Reservation. Dennoch neue Herkunft erzeugt: Quellenfamilien 47→48, Medien/Mitgliedschaften 90→91. Diagnose bleibt korrekt FAIL. |

| 41191231150, Quelle d05c6189 | 56 neue + 80 fokussierte Tests PASS, Frontend PASS. pre5/pre4-Livecontainer und vier historische Fälle PASS; historischer sigkill-Seed scheitert beim Polling unter veröffentlichtem pre.2 im Importabschlussfenster. 90er-/4.000-/iPhone-Stufen deshalb NOT_RUN. |
| 41192396662, Quelle 5f741f93 | 59 neue +80 fokussierte PASS, historisch236 PASS/1 FAIL/0 SKIP. General-Unit-Fixture ohne eigene Registry; korrigiert durch echte isolierte Registry und genaue Prüfung des erwarteten Staging-Fehlers. Kein Anwendungscode geändert. |
| 41193453760, Quelle c692190c | Vollständiger Nachlauf läuft. 59 Zieltests und82 fokussierte Fälle; historische Fälle zusätzlich in der vollständigen Backendmatrix. |

| 41193453760 und41193996176 | 59 neue +82 fokussierte PASS; Frontend PASS. Alle fünf pre5-Live-API-/Recovery-/Archivprüfungen PASS, neuer Browsercheck zunächst zu pauschal für den ausdrücklich deaktivierten Gerätehelfer; danach Response-Body bei Navigation verloren. Beide QA-Ursachen werden exakt geprüft, andere5xx bleiben Fehler. Weitere Containerstufen und gesamte Backendmatrix noch NOT_RUN. |
| 41194643144, Quelle2908eacb | 60 neue +82 fokussierte PASS/0 SKIP; Frontend44+147 PASS. Neuer nur-lesender BytesIO-Vorschautest mit gleichen SQL-/F14-/Originalbytes PASS. Container vollständig PASS: pre5/pre4-Live, sechs historische Recovery-/SIGKILL-Fälle,90 Dateien,4.000 Familien und14 iPhones. Kalt-/Neustart5,374/5,366s. Vollständige Backendmatrix läuft. |

## Verifizierte Belege

ZIP-SHA-256 und Artefakt-IDs stehen in EVIDENCE.json. Ziel-/Frontend-Artefakte von
41116260923 und 41119010880 sowie beide dortigen Containerartefakte wurden erneut
heruntergeladen und gegen den GitHub-Digest geprüft. Nicht verifizierte neuere
Downloads sind entsprechend markiert.

## Noch verbindlich offen

- Vollständige Backend-Ausführung mit disjunkten Nodes und passenden JUnit-Zahlen.
  Collection/Auswahl ist kein Ausführungsnachweis; BLOCKED-Skips sind kein PASS.
- Versionierter Publisher, Source/Image-Bytevergleich, OCI-/Digest-Pull und
  Release-Anlagen erst nach gesamter Abnahme.

Native TrueNAS-/NFSv4-, physische SD-/USB-, echte DNG-1.7- und native RAF-Schreibtests:
**NOT_RUN**. Bekannte-Aufnahme-Variante A und eigenständiges Verlustabschlussmodell:
**DEFERRED**. Fehlgeschlagene echte Dateioperationen behalten ihre F14-/Hash-/
Journalprüfungen. Keine Sicherheitsprüfung zum Bestehen einer Fixture entfernt.

## Vollständiger Backendbefund und erste Korrektur

41194643144: alle2444 Nodes in acht disjunkten Partitionen ausgeführt,2204 PASS,
240 FAIL,0 ERROR/SKIP. Vollständiges heruntergeladenes ZIP13044081687, SHA256
7838e1590c892d24deb7a071276353ec35447e985c98b42da050806eacf6b996 verifiziert.
BACKEND-FAILURES.md und .json erfassen jeden roten Node in19 Ursachen-/Prüfgruppen,
mit Partition, Trace-Digest, Prüfstatus und noch ungeklärten Zuordnungen.

Erste Korrektur3404ddcf: vorhandene Versionstabellen werden ohne DDL gelesen;
neue Migrationen bleiben durch denselben Authorizer gesperrt. RC11-Snapshot
modelliert vorbereitete Schemas vor dem Absturz. Acht neue Sicherheitsfälle.
Lokale Syntax/Actionlint PASS. Gezielter Linuxlauf41207207207 gestartet, Ergebnis
noch offen; kein neuer voller Backend-/Container-/Frontendlauf gestartet.
Keine Behebung aller240 Fälle behaupten und keine Veröffentlichung.
