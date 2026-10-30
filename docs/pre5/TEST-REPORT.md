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
| 41123293238, Quelle 08cee415 | Nachlauf läuft; Ergebnis offen. Container und vollständige Matrix starten nur nach erfolgreichen Vorstufen. |

## Verifizierte Belege

ZIP-SHA-256 und Artefakt-IDs stehen in EVIDENCE.json. Ziel-/Frontend-Artefakte von
41116260923 und 41119010880 sowie beide dortigen Containerartefakte wurden erneut
heruntergeladen und gegen den GitHub-Digest geprüft. Nicht verifizierte neuere
Downloads sind entsprechend markiert.

## Noch verbindlich offen

- Seed-Nachlauf und vollständige fokussierte Stufe ohne ungeklärte Fehler.
- Gesamter 90er Ablauf nach Migrationskorrektur einschließlich Korrekturen,
  lokaler Ablehnung bekannter Reimporte, unabhängiger Sortierung und Neustarts.
- Vollständige Backend-Ausführung mit disjunkten Nodes und passenden JUnit-Zahlen.
  Collection/Auswahl ist kein Ausführungsnachweis; BLOCKED-Skips sind kein PASS.
- Abschließende Container-/Chromium-Abnahme einschließlich bedienbarer DB-Diagnose.
- 4.000-Familien-/14-iPhone-JPEG-Stufen auf dem endgültigen Anwendungscode. In den
  jüngsten Containerläufen wegen vorheriger Fehler nicht ausgeführt.
- Versionierter Publisher, Source/Image-Bytevergleich, OCI-/Digest-Pull und
  Release-Anlagen erst nach gesamter Abnahme.

Native TrueNAS-/NFSv4-, physische SD-/USB-, echte DNG-1.7- und native RAF-Schreibtests:
**NOT_RUN**. Bekannte-Aufnahme-Variante A und eigenständiges Verlustabschlussmodell:
**DEFERRED**. Fehlgeschlagene echte Dateioperationen behalten ihre F14-/Hash-/
Journalprüfungen. Keine Sicherheitsprüfung zum Bestehen einer Fixture entfernt.
