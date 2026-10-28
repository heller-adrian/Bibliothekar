# RC13 → RC14: vorbereitete Upgradeanleitung

Entwurf, noch keine Installationsfreigabe: GitHub-Prerelease und verifizierter
Image-Digest werden erst nach vollständiger automatisierter Abnahme eingetragen.
Keinen ungetesteten Branchcontainer auf TrueNAS installieren.

1. In TrueNAS die bisherige Custom-App stoppen. Beide Instanzen dürfen nicht
   gleichzeitig denselben beschreibbaren Workspace oder dieselben Appdaten nutzen.
2. Bei gestoppter App zusammengehörige Snapshots/Sicherungen von Appdaten und
   Workspace erstellen. SQLite, WAL/SHM, F14, Logs und .incoming vollständig
   erhalten; das externe Fotoarchiv bleibt unverändert RO. Nichts bereinigen.
3. Image auf den später veröffentlichten RC14-Digest umstellen. Alle bisherigen
   Mounts und Umgebungsvariablen beibehalten, insbesondere /appdata, /workspace,
   /main-library, optionale NAS-Quelle RO und zusätzliche Archivmounts RO.
4. App starten, anmelden, Version und Speicherstatus prüfen. Eine reguläre
   Speicherabweichung weiter über den bewährten Reparaturdialog behandeln.
5. Unter Import & Prüfung den fehlgeschlagenen Großimport öffnen. „Import prüfen
   und fortsetzen“ zeigt die serverseitig geprüften Staging-/Zielzahlen. Für den
   belegten NAS-Zustand werden 3892 staged / 0 veröffentlicht erwartet. Bei anderen
   Zahlen zuerst die konkrete Erklärung prüfen. Keine SQL-Dateien editieren.
6. Bestätigung setzt denselben Job fort; Originalfamilien werden nicht neu
   registriert. Alternativ „Staging behalten und Auftrag schließen“: Dateien und
   Nachweise bleiben erhalten und zählen nicht als frei verwendbarer Bestand.
7. Nach Abschluss Bestand, Open Tasks und Protokoll prüfen, zweimal neu starten
   und eine geschützte normale Aktion ausführen. Das Archiv muss bytegleich bleiben.

Fehlen Journal, ursprüngliche Herkunft oder Identitätsnachweise, wird keine
Fortsetzung erfunden. Die UI nennt Job/Pfad und technischen Grund. Protokolle
sichern und den Befund melden; kein Clean Slate und kein manuelles Entfernen von
Staging-/Operationsdateien.

Zusatzbibliothek entfernen: zuerst alle Jobs und Ereignisänderungen abschließen,
Dateien regulär archivieren und den Arbeitsordner vollständig leeren. Unter
Einstellungen → Bibliotheken ausdrücklich „Bibliothek entfernen“ bestätigen.
Archiv, Datenbank, Herkunft und Hülle bleiben erhalten. Für spätere Wiederaufnahme
Archiv zusätzlich als ausdrücklich erlaubte RO-Importquelle bereitstellen und
Folder Import verwenden. Keine Ereignisse werden aus event.json rekonstruiert.

Rollback: App stoppen und zusammengehörige Vor-Upgrade-Snapshots von Appdaten
und Workspace wiederherstellen, bevor RC13 wieder gestartet wird. Ein bloßer
Imagewechsel nach einer RC14-Deregistrierung oder Recoveryentscheidung ist kein
geprüfter Rollback. Archiv und Quellen werden nicht zurückgeschrieben.
