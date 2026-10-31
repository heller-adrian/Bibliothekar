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
