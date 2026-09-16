# Historical QA Milestones

Dieses Dokument bewahrt wichtige Projektgeschichte, damit neue Chats nicht auf alte Telegram-/Chatverläufe angewiesen sind. Historische Befunde sind nur dann aktueller Fehlerstatus, wenn sie im aktuellen QA-Lauf erneut bestätigt wurden.

## 0.16.x

- 0.16.2: UI-/Header-Mismatch auf Import & Prüfung / Ereignisse; Archiv-Hintergrund passte visuell besser.
- 0.16.3: Applied-Rename erzeugte JSON.parse-Fehler; planned rename funktionierte; Archiv-Zeitraumverkürzung zeigte Reassignment-Problem.
- 0.16.4: Applied-Änderungen grundsätzlich funktionsfähig; persistenter globaler Neu-zuordnen-Zugang gewünscht; planned Einzelentnahme erzeugte unerwünschtes Duplikat; `Ohne Ereignis` als eigener segmentbasierter Fall präzisiert.
- 0.16.5: weiterer stabilisierter Stand; Workflow-Anforderungen blieben Grundlage der Folgeversionen.

## 0.19.x / 0.21.1 Deep-Test

Wichtige Anforderungen aus späteren Deep-Tests:

- `Ohne Ereignis`-Fortführung nach Monat/Segmenten funktionierte grundsätzlich.
- Archivbearbeitung muss strukturelle Änderungen korrekt behandeln: aus einem einfachen Ereignis kann nachträglich ein Oberereignis mit Unterereignissen/Zeitsegmenten werden.
- Herausfallende Familien müssen unter anderem als neues Unterereignis des gerade bearbeiteten Oberereignisses zugeordnet werden können.
- Gleiches Grundprinzip gilt für Bearbeitung von `Ohne Ereignis`.

## 0.21.2 QA-Harness

Produkt-Commit `627c5515e533e167e45354ccaa71f988f104ae08` wurde durch QA-/Harness-Commits bis `9cfd760663b512dcf2ef57aed71bb3169edb6932` ergänzt. Der QA-Branch enthält Test-/Harness-Material nach dem unveränderten Produkt-Commit.

### Run 19

Ein früher großer nas-agent-Lauf degenerierte nach sehr langem Kontext in eine Retry-Schleife mit ad-hoc-Python-Helfern. Das war kein belegter Produktfehler, sondern ein Agenten-/Kontextproblem. Run 19 wurde beendet und als Diagnose-Evidence erhalten.

Konsequenz:
- keine gigantische Ein-Worker-Matrix mehr
- Phasen A–F
- frischer Kontext je Worker
- kein endloses Retry derselben Strategie

### Phase A, erster Lauf

Der Executor meldete ursprünglich 6 PASS / 2 BLOCKED. Spätere Prüfung zeigte jedoch drei methodisch unzulässige PASS-Wertungen:

- T004: neue Quelle statt „dieselbe SD“
- T007: neue Quelle + `_002` statt echter Change-Erkennung
- T008: kein echter Neustart

### Einführung qa-thinker

Ein erster Canary scheiterte technisch, weil der Thinker keinen Kanban-Zugriff hatte und deshalb Taskinhalt/Completion-Protokoll nicht bedienen konnte. Das Profil wurde minimal korrigiert: Kanban-only, Reasoning medium, keine operativen NAS-Tools.

Canary 2 bewertete T004/T007/T008 anschließend korrekt dreimal als `RETEST_REQUIRED`.

Damit wurde die verbindliche Architektur eingeführt:

`PLAN -> EXECUTE -> REVIEW`

Der Executor ist nicht mehr sein eigener endgültiger Prüfer.
