# RC4 – begrenzte Abschlusskorrekturen

Basis f26a7ac604b5564118a86c4ebf754a274a43b4f9. Die sechs Compose-Fehler werden ausschließlich durch den RC4-Image-Default korrigiert. DOM-/Lokalisierungstests verwenden die aktuellen echten JS-Funktionen; Originaldaten und Escaping bleiben geprüft. Die zwei Papierkorbfixtures erhalten vollständige eigene Registries; der vorherige String/Path-Fehler wird korrigiert.

Die R1-Produktregression wird auswahlbezogen korrigiert: aktive Restores sperren alle Löschungen; inaktive/ungeklärte Reservationen schützen ihre eigenen Dateien. Vollständiges Leeren bleibt gesperrt. Physischer Einstieg, HTTP und Button verwenden denselben Vertrag. Unmittelbar vor FD-Staging werden Restorepfade, aktive Jobs und Reservationen unter derselben F11-Sperre erneut geprüft. Kein automatischer Abschluss und keine Löschung von Konfliktjournalen.

Exakt drei Produktdateien werden geändert: main.py (HTTP-Auswahl), trash_selective.py (Auswahl/Recheck), trash_ui.py (Buttonzustand). Ihre vollständigen SHA-256 stehen im RC4-Quellvertrag. Alle weiteren App-Dateien entsprechen weiterhin dem angenommenen Stand mit den vorgesehenen Versionssubstitutionen. Keine pauschalen Dateiausnahmen.

Gezielte lokale Abnahme: 185 unterschiedliche aktuelle Fälle PASS. Der erste breite gezielte Prozesslauf wurde nach 1.200 Sekunden durch den lokalen Launcher beendet; 162 PASS und ein noch fehlerhafter neuer Onboardingadapter waren bis dahin im Rohfortschritt belegt. Die genaue unveränderte Sammlungsreihenfolge wurde separat erfasst. Nur die fehlenden Fälle und der korrigierte Adapter wurden danach geprüft; kein erneuter Gesamtlauf. Sämtliche Zwischenfehler bleiben roh erhalten. Das ist kein nachträglich grüner Gesamtprozess oder vollständiges JUnit dieses unterbrochenen Laufs.

Die Registry-Onboardinggegenprobe verwendet explizite RW-/RO-Probeantworten und führt die echte API-Anlage aus. Sie qualifiziert keinen Mount. Der spätere Container-Smoke verwendet den tatsächlichen read-only Bind und die unveränderte Linux-Mountabfrage. Reale TrueNAS-/NFSv4-ACL-/SD-/Smartphone-Abnahme bleibt gesondert erforderlich.
