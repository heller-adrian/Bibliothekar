# TrueNAS-Testupgrade: 1.0.0-pre.1 → 1.0.0-pre.2

Prerelease zur praktischen Abnahme. Native TrueNAS-/NFSv4- und DNG-1.7-Abnahme sind
NOT_RUN. Die hier beschriebenen Schritte wurden nicht auf deinem NAS ausgeführt.

1. Halte die bestehende App an. Sichere den Zustand konsistent, bevor die neue Version
   startet: bevorzugt über TrueNAS/ZFS-Snapshots der beteiligten Appdaten- und
   Workspace-Datasets bei gestoppter App. Behalte die SQLite-Dateien einschließlich
   WAL/SHM, Konfiguration, gesamten F14-Kontrollbereich, Journale und Metadatenordner.
   Kein Clean Slate, keine Datenbankkorrektur, keine Entfernung der DNG-Reservation.
2. Öffne in **Apps** die vorhandene Bibliothekar-Custom-App und deren Bearbeitung.
   Verwende die bestehende App weiter. Behalte alle App-Einstellungen und Mounts:
   `/appdata` (oder das tatsächlich konfigurierte kompatible Layout), `/workspace`,
   Bibliotheks-Arbeitsverzeichnisse und sämtliche Archive. Archive bleiben **Read Only**.
   Web-UID/GID bleiben **568:568**. Den Gerätehelfer nicht ohne Prüfung seiner benötigten
   Funktionen umstellen. Keine zweite Instanz mit denselben beschreibbaren Mounts starten.
3. Ändere ausschließlich die Image-Auswahl auf `ghcr.io/heller-adrian/bibliothekar`
   mit Tag `1.0.0-pre.2` und passendem SHA-256-Digest. Falls das Formular ein separates
   Digest-Feld anbietet, verwende den Wert aus `IMAGE-DIGEST.txt` einschließlich `sha256:`.
   Bei YAML-Konfiguration oder einem Feld für die vollständige Referenz verwende die
   komplette `ghcr.io/heller-adrian/bibliothekar@sha256:…`-Zeile aus dieser Anlage.
   Trage die vollständige Referenz nicht in ein Feld ein, das nur einen Tag erwartet.
   Die beiliegende `compose.pre2.yaml` enthält ebenfalls das per Digest gepinnte Image.
   Übertrage daraus keine neuen Mount- oder Rechtevorgaben auf deine vorhandene App.
4. Speichere und starte die App. Prüfe, dass TrueNAS das neue Image verwendet. Je nach
   TrueNAS-Version zeigt die Oberfläche Tag/Digest unterschiedlich an; vergleiche den
   angezeigten Repository-Digest mit `IMAGE-DIGEST.txt`. Falls die Oberfläche nur den Tag
   zeigt, ist das allein kein Digest-Nachweis. Optional kann die App-Shell/administrative
   Diagnose den tatsächlich laufenden Container identifizieren; eine lokale Docker-ID
   ist nicht zwingend der OCI-Index-Digest. Keine Host- oder Datenbankänderung ist dafür nötig.
5. Beobachte die App-Logs. Die Phase `general-metadata-outcomes` qualifiziert den alten
   Auftrag vor dem Start der Hintergrund-Worker. Bei vollständigem Nachweis wird die
   ursprüngliche Reservation regulär abgeschlossen. Ihr Originalinhalt, ihre ID und die
   Auftragssnapshots bleiben im dauerhaften `metadata-outcome-<ID>.json` erhalten.
6. Melde dich an und öffne die vorhandenen Bibliotheken. Erwartet: keine bisherige
   Startsperre durch diese qualifizierte Reservation. Der DNG-Auftrag bleibt **blocked**
   mit seinem ursprünglichen Fehler; er gilt nicht als erfolgreich geschrieben.
   Prüfe die vorhandenen Bestände sowie die 14 korrigierten JPEGs und deren +13:00-Zeit.
   Starte die App kontrolliert erneut und prüfe Anmeldung und Bibliothekszugriff nochmals.

## Wenn die Schutzsperre bestehen bleibt

Nicht die Reservation löschen, SQLite auf completed setzen oder Journale bereinigen.
`metadata_outcome_<Grund>: <Pfad>` nennt fehlende oder widersprüchliche Nachweise.
Sichere die Diagnose und Logs; halte weitere Dateioperationen an. Für die Prüfung sind
gegebenenfalls der aktuelle Quellenhash/Größe, vollständige Aufgabenfelder, ursprüngliche
Reservation/Bindings sowie Journal-, Backup- und Arbeitskopieninventar nötig. Nicht jedes
historische `blocked` ist sicher auflösbar.

## DNG und Rollback

Der Hotfix heilt den Folgefehler, ersetzt aber keinen nachgewiesenen DNG-1.7-Writer.
Nicht mit `-m` erzwingen. Eine erneute Korrektur kann weiterhin verständlich abgelehnt werden.

Ein Rückwechsel des Images auf pre.1 ist keine automatische Rückabwicklung der bereits
abgeschlossenen Recovery. Bewahre die konsistenten Snapshots auf. Eine Wiederherstellung
muss Appdaten und Workspace zusammengehörig bei gestoppter App zurückführen; niemals
alte SQLite-/F14-Dateien in einen inzwischen weitergeführten Bestand mischen. Archive
bleiben unverändert und schreibgeschützt.

## Praktische Abnahme notieren

Erfasse verwendeten Image-Digest, Startzeit, Ergebnis der Qualifikation, ursprüngliche
Fehlermeldung des DNG-Auftrags, Anmeldung/Bibliothekszugriff vor und nach Neustart sowie
unerwartete Meldungen. Eine echte DNG-1.7-Datei erst in einem gesonderten, kontrollierten
Test prüfen. Diese Ergebnisse sind noch keine stabile 1.0.0-Freigabe.

Oberflächenreferenz: [TrueNAS Custom App Screens](https://www.truenas.com/docs/scale/apps/installcustomappscreens/)
und [Managing Installed Apps](https://apps.truenas.com/managing-apps/managing-installed-apps/).
Der reguläre Wizard dokumentiert Repository, Tag und Pull Policy; Digest-Feld/Anzeige
sind versionsabhängig. Verwende für ein Tag-Upgrade bei Bedarf die vorhandene Pull Policy
„Always pull“, ohne sonstige App-Einstellungen zu verändern. Für eine YAML-Referenz ist
der vollständige `@sha256:`-Wert maßgeblich.
