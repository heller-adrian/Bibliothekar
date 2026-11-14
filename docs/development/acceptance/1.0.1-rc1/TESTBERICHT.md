# Bibliothekar 1.0.1-rc.1 – TrueNAS-Praxisabnahme und Fehler-/UX-Bericht

**Datum:** 11. November 2026  
**Geprüfte Vorabversion:** `v1.0.1-rc.1`  
**Release-Commit:** `165da30f8350c07319ccce6d5bef22670e5d1030`  
**Repository:** <https://github.com/heller-adrian/Bibliothekar>  
**Entwicklung:** `patch/1.0.1-legacy-adoption`, Draft-PR #41  
**Prüfumgebung:** Bibliothekar-Testinstallation unter TrueNAS, vorhandene Testbibliothek **Main Library**; keine produktiven Originaldaten.  
**Material:** Zwölf chronologisch nummerierte Screenshots in `screenshots/` (siehe Anhang).  
**Status:** **Abnahme NICHT bestanden / RC1 nicht freigeben.** Kritischer Blocker bei Abschluss einer archivierten Ereignislöschung; neue Bestandsübernahme fachlich teilweise funktionsfähig, aber Gestaltung und Benutzerführung nicht abgenommen. Python-Skriptweg **nicht getestet**.

## 1. Management-Zusammenfassung

Die neue Funktion *Adopt an existing photo collection* ist in TrueNAS erreichbar. Quellordnerauswahl und lesende Inventur funktionieren im beobachteten Test zügig: **31 Dateien, 15 Dateifamilien, 0 Pfadfehler**, zwei erkannte Aufnahmetage (**2026-07-19: 9 Familien**; **2026-07-21: 6 Familien**). Virtuelle Ereignisentwürfe lassen sich anlegen, speichern, bearbeiten bzw. entfernen; ein bestehendes archiviertes Ereignis wird angeboten, um es zu ergänzen. Damit sind wichtige Kernfunktionen sichtbar vorhanden.

Nicht bestanden sind die gestalterische Integration in die bestehende Bibliothekar-Oberfläche und ein unabhängiger Archiv-Änderungsworkflow: Eine testweise **Löschung eines archivierten Ereignisses** gelang bis zur physischen Prüfung (**16/16 Dateien verifiziert**), scheiterte aber anschließend bei **„Complete change and release SSD“** mit `operation_recovery_required: workspace writes paused; storage may remain READY`. Das kann schreibende Operationen blockieren und ist ein **Release-Blocker**, unabhängig davon, ob die Ursache schon vor RC1 existierte. Ob ein Datenverlust eingetreten ist, lässt sich aus Screenshots nicht ableiten; es gibt dafür keinen Nachweis.

Die neue Oberfläche wirkt wie eine technisch separate HTML-Seite statt wie ein Bibliothekar-Workflow: Dark/Browser-Default-Farben, kleine flache Buttons, unruhige Anordnung, scrollbar untereinanderliegende Phasen, unpassender Dateifamilien-Detaillist statt der bekannten Tagesordnerauswahl. Für die nächste Vorabversion ist eine deutliche Vereinheitlichung mit **Workspace → Media**, **Settings → Event folders** und dem **Archive-change-Assistenten** nötig – nicht nur kosmetisches CSS, sondern eine sinnvollere Interaktion.

**Abnahmeziel:** Reparatur der Archivlöschung **vor** weiteren riskanten Praxisversuchen; anschließend UX-Rework der Bestandsübernahme und erneute TrueNAS-E2E-Abnahme inklusive Skriptweg. Nächste sinnvolle Vorabversion: `v1.0.1-rc.2` (nicht `v1.0.1` Stable).

## 2. Beobachtete Umgebung und Ablauf

1. In **Settings → Libraries** erscheint der neue Einstieg „Bestehende Fotosammlung übernehmen“ (Screenshot 01).
2. Der Assistent öffnet eine gesonderte dunkle Seite mit Zeit-/ZFS-Hinweisen und NAS-Quellenwahl (02).
3. Der Ordnerbrowser erreicht `/sources/nas/fotos/Testarchiv` und zeigt die Jahresstruktur (03).
4. Lesende Inventur: **31 Files / 15 Families / 0 Path errors** (04); 2026 enthält die Tage 19.07. und 21.07.
5. Ein neuer Ereignisentwurf „Test einlesen 1“ für **21.07.2026** wird einschließlich Struktur-Auswahl angelegt (05–07).
6. Die benutzerdefinierte Ordnerstruktur wird momentan als mehrzeiliges Textfeld bearbeitet (06).
7. Ein bestehendes archiviertes Ereignis **„07 - No Event Umbenannt“** für **19.07.2026** wird korrekt als Erweiterungsziel angezeigt; eine Erweiterung lässt sich dem Entwurf hinzufügen und wieder entfernen (08–09).
8. Zusätzlich wird ein Ereignis „Test einlesen 2“ für 19.07.2026 angelegt. Eine Meldung weist auf eine **Zeitüberschneidung mit „07-21 - Test“** hin (10). Dass Überschneidungen verhindert werden, kann fachlich richtig sein. Zu prüfen ist, welche geplante Zuordnung den Konflikt ausgelöst hat und wie der Benutzer ihn komfortabel behebt.
9. Der Benutzer verwirft die noch unverbindliche Planung und versucht, die vorhandenen Testereignisse aufzuräumen. Die Löschung des bereits archivierten Ereignisses „07 - No Event Umbenannt“ führt zum Problem (11–12).
10. Die Archivänderung meldet zuerst einen Fehler bei der Verifikation bzw. Wiederherstellungssperre (11); beim späteren Prüfen **„Verification successful – 16/16 files verified“**, anschließend bleibt jedoch `operation_recovery_required` sichtbar und der Abschluss ist blockiert (12).

**Nicht beobachtet / nicht behaupten:** Es liegt noch **kein** erfolgreicher vollständiger Übernahmeabschluss mit Datenbankregistrierung vor. Der externe Python-Skriptweg, die tatsächliche Verschiebung von Altbestandsdateien, Neuaufnahme nach Archivverifikation, Reboot-/Recovery-Szenarien und große Bestände wurden in dieser Praxisabnahme **nicht getestet**.

## 3. Befunde, Prioritäten und konkrete Erwartungen

### P0 / RC-Blocker: ARC-001 – Archivierte Ereignislöschung kann nicht finalisiert werden

**Belege:** `screenshots/11_archive_delete_verification_error.png`, `screenshots/12_archive_delete_verification_success_but_recovery_block.png`.

**Reproduktion nach Beobachtung:** Bestehendes **archiviertes** Ereignis auswählen → Lösch-/Archivänderungsauftrag anlegen → manuelle Schritte wie im bestehenden Assistenten ausführen → **Verify & complete** → Ergebnis **16/16** → **Complete change and release SSD** → Fehler `operation_recovery_required: workspace writes paused; storage may remain READY`.

**Ist:** Physische Dateiprüfung besteht, die eigentliche Abschluss-/Datenbankoperation bleibt gesperrt. Ein ausführliches internes Dictionary mit AppData-Pfad, Reservierungsinformationen, Scope und Funktionsbezug erscheint im Benutzerinterface. Abbruch bzw. unproblematische Rückkehr ist aus Anwendersicht nicht möglich.

**Soll:** Nach vollständiger Dateiprüfung führt der Abschluss transaktions- und recovery-sicher zur korrekten Datenbank-/Registry-Übernahme und zum Freigeben des Arbeitsbestands. Wenn eine echte Recovery-Sperre besteht, muss der Assistent den präzisen Status verständlich anzeigen und einen **sicheren, tatsächlich funktionierenden Wiederaufnahme-/Reparaturweg** bereitstellen. Keine vorgetäuschte Gesamt-Erfolgsmeldung und keine dauerhafte Sackgasse. Archiv original read-only lassen.

**Codehinweise (verifizierter Release-Quellcode, keine abgeschlossene Ursachenanalyse):**

- `app/operation_health.py`, um Zeile **179**: `require_write()` wirft `operation_recovery_required`, wenn konfliktierende verwaiste bzw. problematische Reservierungen erkannt werden. Die Meldung ist ein Schutzmechanismus und darf nicht einfach ausgeschaltet werden.
- `app/event_change_apply.py`, ab **`finish_event_change()` / Zeile 714**: Dateiüberprüfung und DB-Abschluss folgen nacheinander. Die Funktion ist ausdrücklich als Archiv-read-only ausgelegt.
- Screenshot-Fehler nennt eine **nicht lebende** (`live: False`), **qualifizierte** (`qualified: True`) Operationsreservierung, mit `kind: archive`, Bibliothek `main` und Funktionsbezug `app.event_change_apply.finish_event_change`. Prüfen, ob Reservierung vorzeitig oder nach Crash/Retry übrig blieb, und weshalb qualifizierter Retry/Recovery nicht zum Abschluss gelangt.

**Untersuchungsauftrag:** Release-Commit und reale Testkonstellation nachvollziehen; betroffene Persistenz-/Reservierungszustände und Operation-Scopes **lesend** erfassen; zuerst isoliert reproduzieren. Mögliches Problem an Grenze zwischen erfolgreicher Archivprüfung und `finish_event_change`/`operation_health`/Root-Operation-Lease untersuchen; keine Vermutung als bewiesene Ursache ausgeben. Zulässige qualifizierte Wiederaufnahme und idempotenten Abschluss für Crash/Retry testen. Keine direkte Manipulation von AppData, JSON-Leases, SQLite oder Originalarchiv ohne validierten Recovery-Pfad. Keine Schutzmechanismen zum Grünmachen deaktivieren.

**Abnahmekriterien:** Erfolgreicher Abschluss und korrekter Archiv-/Registry-Zustand; sicherer Retry bei verwaister Reservierung; kein Verlust/Nachladen/Überregistrieren; klarer UI-Status; normale Funktionen danach verfügbar; künstlicher Reboot-/Crash-Test; Prüfung mit zwei Archivereignissen und 16 Dateien entsprechend Praxisfall. **RC2 darf ohne Reparatur nicht freigegeben werden.**

### P1: NAV-001 – Eigenständige Adoptionsseite bricht Bibliothekar-Designsystem

**Belege:** 01–04, 07–10. In `app/legacy_adoption_ui.py` ist der Assistent ein eigenständiges HTML-Dokument mit browsernaher `Canvas`/`CanvasText`-Stylingregel; `app/ui_shell.py` und `app/workspace_ui.py` verwenden die bestehende Design-/Layoutlogik.

**Ist:** Dunkle, weitgehend monochrome Seite, zu geringe visuelle Hierarchie, schmale Elemente, leere Flächen, andere Header-/Form-/Karten-/Buttonsprache als der Rest der App. Abweichung von Light-/Dark-Theme, spacing, Schrift, Icons, responsivem Verhalten.

**Soll:** Ein vollwertiger **Bibliothekar-Workflow mit derselben visuellen Sprache**: bestehender Header, Breadcrumb/Zurück-Navigation, konsistente Typografie, Flächen, Rahmen, Schatten, Kontrast, Buttons, Fokus- und Hoverzustände; Theme und Sprache übernehmen. **Der Assistent darf die volle nutzbare Seitenbreite einnehmen** (kein winziger Dialog). Designkomponenten aus bestehender App **wiederverwenden**, nicht unabhängig neu nachbauen. Screenshots der bestehenden **Workspace → Media**, **Settings → Event folders** und **Archive change** als Referenz über den aktuellen Quellcode/die bestehende UI einsehen.

**Abnahmekriterien:** Visuelle Vergleichsprüfung Desktop plus mindestens schmaler Viewport; korrekte Light-/Dark-Theme-Wiedergabe; keine angeschnittenen Fieldsets, Labels oder Spalten; alle Schritte wirken als Teil derselben App.

### P1: NAV-002 – Falsche Einbettung, Einstieg und unklare Navigation

**Belege:** 01–03.

**Ist:** In englischer Settings-Oberfläche steht der deutsche Einstieg **„Bestehende Fotosammlung übernehmen“** direkt an die aktuelle Bibliothekskarte gequetscht. Auf der neuen Seite fungiert ein kleiner Textlink **„Bibliothekar“** oben als Rückweg in die App. Der Wizard zeigt sämtliche Schritte als vertikalen, langen Scroll-Workflow statt als fokussierte Bildschirmansichten.

**Soll:** In **Settings → Libraries** zunächst Bibliothekskarte(n), danach **Add library**, darunter mit Abstand ein sauber gestalteter Action-Bereich mit **„Adopt existing photo collection“** (bei englischer UI). Vor/Zurück und Verwerfen sollen klare, semantische Funktionen haben. Keinen versteckten „Zurück zur App“-Link, der während eines aktiven Auftrags die Exklusivität unterläuft. **Eine klar bezeichnete Wizard-Seite pro Phase**: Setup → Inventory → Plan events → Review → Choose execution → Execute → Verify/complete; Header/Stepper, „Back“/„Next“/kontextabhängige Buttons. Der Wechsel darf den Entwurf nie verlieren. „Discard changes“ vor Verbindlichkeit **rot, gut sichtbar im Seitenkopf**, mit Bestätigung; danach durch sichere Recovery-Option statt Verwerfen ersetzen. „Restart inventory“ als primär verständliche Aktion im Inventur-Kontext **blau** und mit angemessener Warnung.

**Abnahmekriterien:** Englisch vollständig konsistent; Eingangsbutton unter Add library mit Luft; kein unautorisierter Escape per URL, Logo, Browser-Reload oder Back; alle Schritte und Rücksprünge funktionieren, Zustand bleibt persistent.

### P1: PLAN-001 – Ereignisplanung an Workspace → Media ausrichten (Hauptanforderung)

**Belege:** 04, 07–10.

**Ist:** Links werden Tagesbuttons angezeigt, darunter lange Dateifamilien-/Pfadlisten (`2026/Alt/.../All/...`), die bei vielen Fotos die Seite überfrachten. Rechts gleichzeitig ein kleines Formular für Event und Draft. Einzeldateien sind für die eigentliche **Zuordnung ganzer Aufnahmetage** nicht die Hauptinformation.

**Soll:** Planung **im Aufbau, Gefühl und in der Bedienung wie „Workspace → Media“**. Im Hauptbereich Jahres-/Monatsgruppen und **Tagesordner-/Tageskarten** mit Datumsangabe und Anzahl; Übersicht auch bei vielen Tagen. **Klick** wählt Tag, **Shift-Klick** wählt zusammenhängende Bereiche, **Ctrl-/Cmd-Klick** schaltet Einzelauswahl um (identische bestehende Semantik); sichtbare Selektion und „alle auswählen/abwählen“ nach geltendem Bibliothekar-Verhalten. Oben eine **Aktionsleiste mit Plus**: neues Ereignis, Unterereignis oder „Ohne Ereignis“/Sammelordner anlegen, auch **ohne** vorherige Tagesauswahl. Bei Auswahl geeignete Datumsspanne vorbelegen; ansonsten manuell Von/Bis wählen. Korrekte Verteilung von Dateifamilien zu Tagen muss intern weiterlaufen, aber Pfad-/Einzeldetails nur **auf Wunsch als aufklappbare Diagnostik**, nicht als Dauersicht. Die vorhandene Erkennung archivierter Ereignisse und „Add to existing event“ gehört in dieselbe intuitive Tages-/Ereignisübersicht. Skalierung auf hunderte/tausende Tagesordner sicherstellen; keine überlange unstrukturierte Liste.

**Abnahmekriterien:** Neue, bestehende, erweiterte Ereignisse sowie No-event-Sammelordner mit Tagesauswahl und ohne Auswahl; Mehrfachselektion samt Tastatur; klare Datumsvorgaben und Konfliktanzeigen; vergleichbarer Workflow wie Media-Bereich.

### P1: PLAN-002 – Zeitkonflikte verständlich auflösen

**Belege:** 08–10.

**Ist:** Beim Versuch eines zusätzlichen Ereignisses erscheint **„Zeitüberschneidung mit ‚07-21 - Test‘. Wähle das vorhandene Archivereignis oder passe den Zeitraum an.“** Der Konfliktschutz an sich kann korrekt sein, aber der Benutzer erreicht keinen intuitiven nächsten Schritt, und die zeitlichen Zuordnungen mehrerer Entwürfe sind schwer zu überblicken.

**Soll:** Konflikte vor dem Speichern klar markieren: betroffene Tage bzw. Zeitspanne, kollidierendes vorhandenes oder virtuell geplantes Ereignis, eindeutige Handlung **„Vorhandenes Ereignis ergänzen“**, **„Zeitraum ändern“**, **„Planung korrigieren“**. Keine stillschweigende Doppelzuordnung. Der Nutzer muss eindeutig erkennen, ob eine Warnung fachlich erwartetes Verhalten ist oder ein Implementierungsfehler. Eine fehlgeschlagene Planung darf vorhandene gültige Drafts nicht verlieren.

**Abnahmekriterien:** Synthetische Tests für Überschneidungen mit Archiv-Ereignis, zwei Drafts, Sammelordner und überschneidungsfreie Fälle; UI gibt konkrete Korrekturaktion.

### P1: PLAN-003 – Individuelle Ereignisordner wie Settings → Event folders bearbeiten

**Belege:** 05–06.

**Ist:** Bei „Custom folder layout“ müssen `All`, `Sorted`, `Export` usw. als **Zeilen eines großen Textfelds** eingegeben werden. Zusätzlich gibt es Textfelder für Originals und Export. Das ist uneinheitlich, fehleranfällig und schlechter als der bestehende Einstellungseditor.

**Soll:** **Denselben Editor bzw. dieselbe Interaktion wie Settings → Event folders** verwenden: einzelne Ordnerzeilen als kontrollierte Eingabefelder/Chips, Hinzufügen, Umbenennen, Entfernen; Default übernehmen, per Ereignis anpassen; klare Rollen für **Ordner der Originale** und **Exportordner**; gültige verschachtelte Pfade visuell und sicher abbilden. „Library default“, individuelle Struktur und keine Unterordner weiterhin unterstützen. Bestehende Events nicht unbeabsichtigt neu strukturieren.

**Abnahmekriterien:** Pro Event/No-event getrennt gespeichertes Layout; reload-fest; konsistente Vorschau, Move-Plan und Skript verwenden exakt dieselbe Struktur; keine freien fehleranfälligen Roh-Textarea-Pfadsammlungen als Haupteditor.

### P2: PLAN-004 – Form- und Kartenlayout korrigieren

**Belege:** 04–07, 09–10.

**Ist:** „Keep day folders“ und Checkbox stehen optisch getrennt, ungünstige Lücke; Überschriften/Legenden „Draft“ und „New event or collection folder“ wirken über die Karte hinaus bzw. schlecht eingepasst; Eingaben zu klein/eng; Datepicker und Buttons unstimmig; zu wenig klare Flächen/Kontraste.

**Soll:** Checkbox unmittelbar **neben** ihrem Label als gemeinsame anklickbare Einheit; Legenden/Fieldsets korrekt; angenehme Eingabebreiten, Abstände und Zeilenhöhen; Datumsauswahl mit bestehenden Komponenten; konsistente Groupings und Aktionstasten. Kein visuelles Überlaufen auf schmalen Viewports.

### P2: PLAN-005 – Entwürfe als aufklappbare Karten

**Belege:** 07, 09–10.

**Ist:** Gespeicherte Drafts erscheinen als schlichte Textzeilen; „Edit“ und „Remove“ werden ständig nebeneinander angezeigt. Viele Ereignisse würden zu einer unübersichtlichen Spalte führen.

**Soll:** **Je Entwurf eine eigenständige Event-Karte**, initial kompakt: Titel, Datum/Spanne, Typ, Anzahl zugeordneter Tage/Familien, ggf. Layout/Status. **Klick auf Karte** öffnet Detail-/Bearbeitungsoptionen einschließlich Edit/Remove. Standardmäßig nicht bei jedem Entwurf dauerhaft alle Aktionen anzeigen. Bestehende Archivevent-Erweiterungen klar von neuen Ereignissen trennen. Eindeutige Rückmeldung beim Speichern („Saved“), bei Bearbeiten/Entfernen, Konflikt und beim Wiederladen. Kein Draftverlust durch Tab-Wechsel, Browser-Reload oder Container-Neustart.

### P2: LABEL-001 – Abschlussbutton darf keinen SSD-Zwang suggerieren

**Belege:** 11–12.

**Ist:** **„Complete change and release SSD“**.

**Soll:** Terminologie **Workspace/Arbeitsbereich**, nicht SSD als physisches Speichermedium. Beispielsweise **„Complete archive change and release workspace“**, falls sachlich korrekt; gegebenenfalls kürzer **„Complete archive change“** und im Hilfetext die Freigabe des Workspace erklären. Änderung in allen zugehörigen Views/Tests/i18n konsistent durchführen. Keine nur kosmetische Änderung, wenn der Button tatsächlich andere Ressourcentypen freigibt.

### P1: ERR-001 – Technische Recovery-Fehler nicht ungefiltert im UI ausgeben

**Belege:** 11–12.

**Ist:** Ein schwer lesbares internes Python-Dictionary und technisch interner Operation-Lease-Status überlagern die Nutzerführung; „Verification successful“ wird ohne Differenzierung zur noch blockierten Finalisierung angezeigt.

**Soll:** Zwei klar getrennte Fortschritte **(a) Datei-/Ordnerprüfung erfolgreich** und **(b) Datenbank-/Recovery-Abschluss offen/fehlgeschlagen**. Nutzerfreundliche lokalisierte Fehlermeldung mit kurzen nächsten Schritten, technische Details in ein kontrolliertes, aufklappbares Panel bzw. exportierbaren Diagnosebericht. Keine Roh-Ausgabe von sensitiven Hostpfaden/IDs in der Hauptmeldung. Sicherer erneuter Abschluss nach Wiederherstellung; vorab Integrität erneut prüfen.

## 4. Übergreifende Architektur-/Qualitätsvorgaben

- **Bestehenden Code und UI-Strukturen wiederverwenden** (`app/workspace_ui.py`, `app/ui_shell.py`, relevanter Event-Folder-Settings-Editor, Archive-change-Assistent). Keine bloße großflächige CSS-Kopie und kein dritter separater Design-Stack.
- **Nur dasselbe ZFS-Dataset** für Quell- und Zielarchiv; keine cross-dataset-Kopier-Fallbacks im Auto-Verschiebeskript.
- Archiv-Mounts der Bibliothekar-Web-App bleiben **read-only**; nur ein vom Benutzer bewusst extern gestartetes TrueNAS-Skript führt die freigegebenen Moves aus.
- Exklusiver, persistenter Übernahmeassistent: kein Umgehen des aktiven Auftrags über Logo, URL, Browser-Reload, API oder zweiten Tab; **Verwerfen nur bis zum verbindlichen Übergang**, danach Recovery statt unkontrollierter Löschung.
- Schrittweise Seitenführung; Daten und Drafts serverseitig dauerhaft speichern; korrekter Intro-/Warnhinweis auf jeder Seite (keine Änderungen am Altarchiv außer beim ausdrücklich freigegebenen manuellen Schritt).
- Keine Änderungen an produktiven Archivdateien oder an einer produktiven Datenbank durch Entwicklungstests. Alle gefährlichen Tests synthetisch/isoliert.
- Stable `v1.0.0`, `main`, `latest` unverändert; PR #41 als bestehender Entwicklungszweig fortführen. RC1 nicht überschreiben.

## 5. Erforderliche Tests und Nachweise für die nächste RC

### A. Kritische Archivlöschung – zuerst

1. Synthetisches Archiv mit mindestens zwei archivierten Ereignissen, etwa 16 relevanten File-Operationen; archiviertes Ereignis löschen; die manuelle Archivprüfung meldet 16/16; **Abschluss erfolgreich**; erwartete DB-/Registry- und Workspace-Resultate beweisen.
2. Reproduziere `operation_recovery_required` mittels gezielt injizierter zulässiger Recovery-/Orphan-Situation; **kein** pauschales Abschalten der Schreibschutzprüfung.
3. Unterbruch/Neustart exakt vor/nach Finish, Retry mit identischer Reservierungsidentität und idempotenter Finalisierung; kein Deadlock, keine Doppelregistrierung, keine fehlenden Dateien.
4. Bei wirklicher nicht auflösbarer Sperre: korrekter abgesicherter Recovery-Pfad und verständliche UI-Meldung; Test, dass Nutzer keine gefährlichen „Discard“-Operationen ausführen kann.
5. Bestehende Archiv-Änderungs-, Archiv-Rücknahme- und Event-Deletion-Regressionen weiterhin grün.

### B. Neue Bestandsübernahme UX

1. Screenshot-/DOM-Vergleich mit Workspace → Media und Event folders (gleiche Header-/Theme-/Spacing-/Button-Familie).
2. Auswahl von Tagesordnern: Klick, Shift-Bereich, Ctrl/Cmd-Toggle, Auswahlindikatoren, Plus-Aktion, Ereignis **mit und ohne Auswahl**.
3. Neue Events, Unterevents, ohne-Ereignis-Sammlungen, vorhandenes Archivereignis ergänzen; gute Konfliktbehandlung.
4. Individuelle Unterordner wie im Settings-Editor; Default, Custom und keine Unterordner; konsistente Plan-/Skriptausgabe.
5. Draft-Karten einklappbar, Edit/Remove erst nach Öffnen; Speichern, Entfernen, Neuladen, Container-Neustart.
6. Wizard-Schritte als separate ganze Ansichten, Back/Next, erlaubtes Verwerfen, endgültige Sperr- und Recovery-Zustände; direkte alte URL und Logo müssen serverseitige Exklusivregel einhalten.
7. i18n und Design in Englisch und Deutsch; Light/Dark; Desktop, Tablet und kleines Browserfenster; Tastaturbedienung und klare Fokusmarkierung.
8. Schnelle Quellen-/Ordnerwahl, kein überladener Einzelfamilien-Dump in der Hauptplanung; Skalierung mit vielen Tagen und vielen Drafts.

### C. Vollständigkeit / Release-Gate

1. In synthetischer ZFS-Testumgebung tatsächlich **manuelle** und **skriptgestützte** Übernahme mit identischem bestätigtem Plan ausführen; SHA-256 verifizieren; Registrierungsstatus beweisen; danach Ereignisse bearbeiten und in normalen Workflows verwenden.
2. Reale TrueNAS-Abnahme anschließend **erneut** mit kleinen, austauschbaren Daten, vor dem 600-GB-Einsatz.
3. Gezielte lokale/Container-/ZFS-Tests zuerst; umfangreiche Backend-Regression **einmal auf dem exakten RC2-Freigabecommit**. Keine laufenden unsinnigen QA-Schleifen.
4. Image und Digest, Workflow-Läufe, Testprotokoll, Abschlussbericht dokumentieren; Stable 1.0.0 und `latest` unangetastet.

## 6. Screenshotverzeichnis – zeitliche Reihenfolge

| Nr. | Datei | Aussage |
|---:|---|---|
| 01 | `screenshots/01_settings_entry.png` | Settings → Libraries: deutscher, zu dicht platzierter Einstieg oberhalb „Add library“ |
| 02 | `screenshots/02_adoption_intro.png` | Abweichende dunkel/browsernahe Wizard-Seite; Intro, Quellenwahl, kleiner Bibliothekar-Rücklink |
| 03 | `screenshots/03_source_folder_browser.png` | Schnelle Quellordnerauswahl `/sources/nas/fotos/Testarchiv` mit Jahresordner 2026 |
| 04 | `screenshots/04_inventory_event_editor.png` | 31 Dateien, 15 Familien, 0 Pfadfehler; Tagesbuttons und unnötiger Dateifamilien-Detailblock |
| 05 | `screenshots/05_event_form_closeup.png` | Unpassende Formularfelder, Checkbox-Ausrichtung, Überschrift-/Fieldset-Gestaltung |
| 06 | `screenshots/06_custom_folder_layout.png` | Custom Folder Layout als unkomfortables mehrzeiliges Textfeld |
| 07 | `screenshots/07_saved_draft.png` | Gespeicherter Event-Draft, dauerhaft sichtbare Edit/Remove-Aktionen |
| 08 | `screenshots/08_existing_archive_event.png` | Vorhandenes Archivereignis „07 - No Event Umbenannt“ wird erkannt |
| 09 | `screenshots/09_extension_draft.png` | Erweiterung vorhandenen Ereignisses als Draft gespeichert |
| 10 | `screenshots/10_overlap_warning.png` | Zeitüberschneidung mit „07-21 - Test“; Konflikt-UX unkomfortabel |
| 11 | `screenshots/11_archive_delete_verification_error.png` | Archivlöschung: technische Recovery-Sperre, Verifikation zunächst fehlgeschlagen |
| 12 | `screenshots/12_archive_delete_verification_success_but_recovery_block.png` | 16/16 geprüft, aber Datenbank-/Abschlussoperation weiterhin blockiert |

### Verwendete Quellcode-Nachweise (separate Codeprüfung, nicht allein Screenshots)

- [`app/legacy_adoption_ui.py`, Oberfläche ab Zeile 16](https://github.com/heller-adrian/Bibliothekar/blob/v1.0.1-rc.1/app/legacy_adoption_ui.py#L16)
- [`app/workspace_ui.py`, bestehende Workspace-Interaktion](https://github.com/heller-adrian/Bibliothekar/blob/v1.0.1-rc.1/app/workspace_ui.py)
- [`app/ui_shell.py`, vorhandenes Designsystem](https://github.com/heller-adrian/Bibliothekar/blob/v1.0.1-rc.1/app/ui_shell.py)
- [`app/operation_health.py`, Recovery-Schreibsperre um Zeile 179](https://github.com/heller-adrian/Bibliothekar/blob/v1.0.1-rc.1/app/operation_health.py#L174-L180)
- [`app/event_change_apply.py`, `finish_event_change()` ab Zeile 714](https://github.com/heller-adrian/Bibliothekar/blob/v1.0.1-rc.1/app/event_change_apply.py#L714)
- [Release `v1.0.1-rc.1`](https://github.com/heller-adrian/Bibliothekar/releases/tag/v1.0.1-rc.1)

**Hinweis zur Beweiskraft:** Screenshots sind Sichtbefunde. Der Mechanismus hinter der liegen gebliebenen Operationsreservierung ist noch nicht bewiesen. Erfolgreiche Backend-/ZFS-Tests sind wichtig, ersetzen aber diese fehlgeschlagene reale TrueNAS-Praxisabnahme nicht.
