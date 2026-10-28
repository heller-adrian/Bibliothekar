# Auswertung des fehlgeschlagenen RC13-Laufs 40607188501

Ausgewertet wurden alle acht Joblogs und die verfügbaren JUnit-/inkrementellen
Artefakte des Quellstands `b14729c5`. Ein abgebrochener Gesamtjob wurde dabei
nicht als bloß ein einzelner Testfehler behandelt.

| Alte Gruppe | Befund | Korrektur |
|---|---|---|
| 0 | Alte SSD-UI-Erwartung; Reihenfolge neuer gegenüber historischen Übersetzungsregeln; echte unvollständige Übersetzung dynamischer Sätze | Bewusst neue Begriffe prüfen, relative Reihenfolge historischer Regeln erhalten, allgemeine Zählerregeln auf vollständige passende Texte begrenzen |
| 1 | F11-Tests überschritten wiederholt 90 Sekunden; Gesamtjob nach 2.400 Sekunden beendet | Wiederholte Mounttabellenabfragen durch frische Kernelabfrage am gehaltenen FD ersetzen; lange Crashfälle auf Testebene verteilen |
| 2 | Zwei F14-Lifecycle- und zwei kombinierte Restoretests zu langsam; Inventory-Konfliktantwort über der bestehenden Drei-Sekunden-Grenze | Dieselbe Deskriptoroptimierung; bestehende Konflikt-, Journal- und Zeitgrenzen beibehalten |
| 3 | DOM-Stub kannte die neue rein lokale Schließen-Schaltfläche nicht | Stub um die tatsächlich benutzten DOM-Funktionen ergänzen; leere Statusanzeige erzeugt keine Schaltfläche |
| 4 | Gesamtdeadline; alte UI-Verträge; Metadaten-SIGKILL-Hook vertrug die bereits verwendeten `src_dir_fd`-/`dst_dir_fd`-Argumente nicht | UI-Verträge aktualisieren; Hook leitet Argumente weiter und stoppt weiterhin an derselben realen Mediengrenze; Laufzeiten wie oben korrigieren |
| 5 | Finder statt Manual erwartet; sechs reale Starts im Reconcile-Fall überschritten das aggregierte Limit | Gewünschtes Prozesslabel prüfen; Deskriptoroptimierung, keine Lockerung des F14-Ausschlusses |
| 6 | Alte Versions-/README-Erwartungen, alte SSD-Texte; historischer F20-Worker lief in seine eigene Deadline | Aktuellen unabhängigen Releasevertrag prüfen; vollständigen historischen Test unverändert erneut ausführen; Laufzeitursache beheben |
| 7 | Zwei Lifecycle-Timeouts; neue Race-Fixture verglich absoluten Namen mit deskriptorrelativ geöffnetem Namen; anfängliches `O_NOFOLLOW`-Versagen war ungeklassifiziert | Tatsächlichen relativen Öffnungspunkt instrumentieren; nur sichere State-Austausche erneut lesen; Öffnungsfehler mit konkretem Pfad als Kontrollfehler melden |

Zusätzlich aus den echten SIGKILL-Nachweisen: Ein Import kann nach kanonischer
Familienanlage und vor Member-/Katalogpublikation sterben. Der erhaltene
Zwischenstand wird ausschließlich anhand seiner exakt passenden ursprünglichen
offenen F14-Importreservation qualifiziert. Dadurch werden weder Member ergänzt
noch ungeklärte Operationen abgeschlossen. Siehe `ANALYSE.md`.

Das erste vollständige Folgeexperiment auf `ad73cf38` bestätigte das gezielte
Gate mit 64 PASS und Chromium mit 44 PASS. Fünf vollständige Backendgruppen
bestanden bereits; der Lauf wurde für weitere tatsächlich gefundene
Darstellungskorrekturen ersetzt. Er gilt nicht als vollständige Abnahme des
späteren Quellstands.

Der letzte UI-Abgleich ergänzte verbliebene englische SSD-Begriffe, echte Tests
beider Sprachwechsel auf der Reparaturseite und den Kopierfallback für normale
HTTP-Ursprünge. Die vorherige Sprachfassung reproduziert im Browser englischen
Text nach DE-Auswahl. Reparaturbestätigungen und Reparaturrequests bleiben
unverändert.

Die abschließende Abnahme und ihre tatsächlichen Ergebnisse stehen in
`TEST-REPORT.md` und den unveränderten CI-Artefakten. Die Testpartitionierung muss
alle gesammelten IDs genau einmal nachweisen; fehlende Gruppen, Überschneidungen,
ausgelassene Tests, Fehler und Skips verhindern die Veröffentlichung.

## Vollständiger Folgelauf 40658249648

Gezieltes Gate 67 PASS, Browser 44 PASS; Backendgruppen 1, 2 und 6 bestanden.
Die übrigen Gruppen lieferten sieben Fehler bei insgesamt 2.188 gesammelten IDs:

- Gruppe 0: Ein direkt aufgerufenes Startup mit absichtlich fehlender Datenbank
  hinterließ seinen globalen Fehler im nächsten unabhängigen HTTP-Test.
  Isolierte Appfixtures erhalten nun eigene Laufzeitobjekte; gestartete echte
  Worker werden vor Rücknahme ihrer Testpfade beendet. Persistierte Nachweise
  und externe Crashprozesse werden dabei nicht verändert.
- Gruppe 3: Der SSD-Gegenversuch las Dateien eines anderen Tests, der jetzt in
  einer anderen Partition läuft. Er erzeugt seinen eigenen identischen
  SIGKILL-Ausgangszustand und prüft vier echte Startup-/Retry-Sequenzen.
  Der F15-Sammelfall führte zwei unabhängige Dreifach-Startfälle unter einer
  gemeinsamen 80-Sekunden-Grenze aus. Beide unveränderten Phasen werden jetzt
  einzeln mit derselben Grenze ausgeführt; kein Sicherheitsdeadline erhöht.
- Gruppe 4: Die synthetische HTTP-Fixture übersprang den technischen Startup.
  Ohne dessen Lockformat-Fence kollidierte die erstmalige exklusive Fenceanlage
  korrekt mit dem bereits gehaltenen Shared-Admission-Lock. Die Fixture erzeugt
  den echten Fence vor dem Request. Der fremde Papierkorbeintrag wird danach
  mit derselben Herkunftsprüfung abgewiesen; keine Produktlockprüfung geändert.
- Gruppe 5: Historische Übersetzungserwartungen verlangten weiter SSD-Begriffe.
  Erwartet wird nun die ausdrücklich verlangte Arbeitsbereichsterminologie.
- Gruppe 7: Der alte DOM-Stub kannte den lokalen Schließen-Knopf nicht.
  Der Stub berücksichtigt ihn; Statussymbole und unveränderte Benutzernamen
  werden weiterhin geprüft.

Lokale Gegenprüfungen: beide getrennten F15-Phasen bestanden; der SSD-Fall
benötigt natives Linux-inotify und wird ausschließlich im Linuxgate bewertet.
Die drei korrigierten RC1-Package-C-Fälle bestanden einzeln. Alle genannten
Fehlerfälle wurden zusätzlich ins vorgeschaltete Linuxgate aufgenommen.
