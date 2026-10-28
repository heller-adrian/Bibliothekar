# Praktische TrueNAS-RC14-Abnahme

Vorläufige Anleitung. Erst nach Veröffentlichung mit geprüftem Digest ausführen.
Native TrueNAS-Erstinstallation und ACL-Abnahme sind gesonderte spätere Schritte.
Dieser Auftrag verbindet sich nicht mit dem NAS und ändert dort nichts.

Für einen vollständig isolierten Test eine zweite Custom-App mit eigenen neuen
Appdaten und eigenem Workspace anlegen. Keine beschreibbaren Verzeichnisse mit
der bestehenden App teilen. Externes Testarchiv und NAS-Testquelle ausschließlich
Read Only einhängen. Standardaufbau: Appdaten → /appdata, Arbeitsbereich →
/workspace, Archiv → /main-library, zusätzliche Bibliothek z. B. → /Businessarchiv
RO, ausdrücklich erlaubte NAS-Importquelle → /sources/nas RO. Bisherige RC13-
Supervisor-/UID568-Konfiguration und Einstellungen beibehalten.

Nach veröffentlichter automatischer Abnahme prüfen:

1. Anmeldung, Version RC14, bestehende Bibliotheken und Speicherstatus.
2. Großen Folder Import starten, parallel Aufgaben/Tagesbestand aktualisieren.
   Kein „database is locked“; nur abgeschlossene physisch vorhandene Familien
   dürfen als frei erscheinen. Quellen und Archive unverändert.
3. Für die bestehende Fehl-Testinstanz statt Neuimport die Anleitung
   UPGRADE-RC13.md verwenden. Beim belegten Job zuerst 3892/0 prüfen und denselben
   Import fortsetzen. Nicht manuell nachhelfen, falls eine Gegenprüfung sperrt.
4. Zusatzbibliothek „Business“ mit eigenem RO-Archiv anlegen. Erwartet wird ein
   lesbarer neuer Workspace business; technische ID ist separat. Bestehende
   Ordner bleiben unverändert. Kollisionen müssen verständlich abgelehnt werden.
5. Deaktivieren und Aktivieren prüfen. Entfernen bei offenen Jobs/Restdateien
   muss blockieren. Bei sicher archiviertem, leerem Workspace ausdrücklich
   entfernen; Archiv, DB und Dateien müssen erhalten bleiben.
6. Das erhaltene Archiv über einen expliziten RO-Quellmount per gewöhnlichem
   Folder Import wieder einlesen. Ereignisse bei Bedarf neu zuordnen. Keine
   automatische event.json-Ereignisrekonstruktion erwarten.
7. EN und DE im laufenden Betrieb wechseln. Die 17 Befunde aus SCREENSHOTS.md
   prüfen, mobil besonders beide Statusbadges bei schmalem Bildschirm.
8. Zweimal neu starten, normale geschützte Aktion prüfen. Bewährte Speicher-
   reparatur anschließend nur an separaten Testdaten prüfen: ursprünglichen
   Ordner wieder bereitstellen bzw. bewusst bestätigten Ersatz verwenden.

Bei Fehler: Version/Digest, Job-ID, Zeitpunkt, konkrete UI-Meldung und
Containerlog sichern. Keine Rechte rekursiv ändern, keine SQLite-/WAL-/F14-Dateien
löschen. Bei unbekannten Nachweisen ist eine Sperre das erwartete Verhalten.
