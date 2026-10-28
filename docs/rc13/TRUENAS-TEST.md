# RC13 praktisch auf TrueNAS abnehmen

RC13 ist ein Prerelease. Die Linux-/Containerbelege stehen im Release zusammen
mit `TEST-REPORT.md`, `IMAGE-DIGEST.txt` und `SHA256SUMS`. Eine native
TrueNAS-/OpenZFS-/NFSv4-Abnahme wird dadurch nicht behauptet. Die gesonderte
Erstinstallations-/ACL-Abnahme folgt später.

## Bestehende gesperrte RC12-Testinstanz aktualisieren

1. Unter **Apps** Bibliothekar stoppen. App-Einstellungen und bisheriges Image
   notieren. Keine zweite App mit denselben beschreibbaren Mounts starten.
2. Über **Datasets / Snapshots** den gesamten Appdatenstamm und Workspace im
   gestoppten Zustand sichern. Bei mehreren Datasets dasselbe gestoppte
   Zeitfenster verwenden. Konfiguration, SQLite einschließlich WAL/SHM, Registry,
   F14 und Journale gehören zusammen. Nicht einzelne Datenbanken austauschen.
3. In **Apps → Bibliothekar → Edit** das Image auf
   `ghcr.io/heller-adrian/bibliothekar:1.0.0-rc.13` ändern. Falls die Oberfläche
   vollständige Image-Referenzen unterstützt, die Referenz aus
   `IMAGE-DIGEST.txt` verwenden. Ein Digest gehört nicht in ein reines Tag-Feld.
   Alternativ ist `compose.rc13.yaml` im Release bereits auf diesen Digest
   voreingestellt. Ein gesetztes `BIBLIOTHEKAR_IMAGE` überschreibt die Vorgabe.
4. Alle Mounts, Umgebungsvariablen, Passworteinstellungen und RO-Häkchen der
   vorhandenen RC12-Instanz beibehalten. Insbesondere `/appdata` und `/workspace`
   wieder an dieselben Hostpfade binden. Kein SQL, `storage_admin adopt`,
   Zurücksetzen von Reservations oder Rechteänderung ist für den
   Quellfamilienfehler vorgesehen.
5. Die App starten, Weboberfläche öffnen und anmelden. Die Fußzeile muss
   `1.0.0-rc.13` anzeigen. Der Start prüft die ursprünglichen Quellfamilien und
   vorhandenen bestätigten Löschbelege automatisch. Ein fehlendes JPEG wird
   dadurch nicht wieder erzeugt; seine ursprüngliche Herkunft bleibt erhalten.
6. Bei erneuter Sperre den vollständigen technischen Code, betroffenen Pfad und
   die App-Logs sichern. Widersprüchliche oder fehlende Herkunftsbelege werden
   weiterhin gesperrt. Keine Belege löschen, um eine Freigabe zu erzwingen.

Das Repository und das GHCR-Paket bleiben privat. Falls der Imageabruf abgelehnt
wird, die vorhandene Registry-Anmeldung für `ghcr.io` mit einem berechtigten
GitHub-Konto und einem Token mit `read:packages` verwenden. Keine Zugangsdaten
in Logs oder Supportberichte kopieren.

## Abnahmefolge mit ausschließlich entbehrlichen Testfotos

| Schritt | Erwartung |
|---|---|
| Gesperrte RC12-Instanz aktualisieren | Anmeldung und bisherige Bibliothek erreichbar, verbliebene RAW-Datei vorhanden |
| Zweimal neu starten | Bibliotheken, Namen, Archivpfade und Bestand bleiben konsistent |
| Zusätzliches Testarchiv als `/Businessarchiv` RO einbinden | Der Zusatzmount allein verursacht keine Startsperre |
| Settings → Libraries → zweite Bibliothek anlegen | Eigenes RO-Archiv und eigener Arbeitsordner; beide Bibliotheken nach Neustart nutzbar |
| Kleine Testquelle importieren und Ereignis sortieren | Reguläre Operationen funktionieren; Archiv bleibt ausschließlich lesbar |
| EN und DE, Desktop und Smartphone prüfen | Alle 20 Befunde aus `SCREENSHOTS.md` nachvollziehen; tatsächliche Containerpfade, keine SSD-/Finder-Prozesslabels |
| Archivänderung, Verwerfen und schnelles erneutes Öffnen | Kein transienter Kontrollfehler; technische Diagnose bei Fehler sichern |
| Vollständigen Testereignis-Löschauftrag vorbereiten | Ganzen Ordner einschließlich `event.json` nur bei vollständig geprüfter Rückkehrkopie und bekanntem Inventar manuell entfernen |
| Mobilen Aufgabenhinweis mit X schließen | Nur die Anzeige verschwindet; Serverauftrag läuft weiter, Desktop zeigt keine doppelte Leiste |
| Unbekannte Testdatei im Trash wiederherstellen versuchen | Verständliche Ablehnung ohne künstlichen Importauftrag; ausdrücklich bestätigtes Leeren bleibt möglich |
| Testdatei aus einem JPG/RAW-Paar entfernen, zweimal vollständig abgleichen und neu starten | Aktueller Fehlbestand bestätigt; ursprüngliche Familie erhalten; Neustart möglich |

Für die Darstellung der bewährten Speicherreparatur: App stoppen und ausschließlich
den **leeren Test-Trash** umbenennen. Nach Start müssen betroffener Pfad,
erwarteter kopierbarer Ordnername und beide bisherigen Reparaturwege erscheinen.
Zuerst denselben ursprünglichen Ordner zurückbenennen und erneut prüfen.
Anschließend mit einem erneuten simulierten Verlust den ausdrücklich bestätigten
leeren Ersatz prüfen. Ein neu angelegter Ordner mit hineinkopierten Dateien ist
keine Wiederherstellung der ursprünglichen Ordneridentität. Datenbank-,
Workspace-Mount- oder ungeklärte Journalverluste sind keine beliebig ersetzbaren
leeren Trash-Ordner.

Manuelle Archivänderungen während dieser Abnahme nur an Kopien entbehrlicher
Testfotos durchführen. Die App bindet das Archiv RO ein; vom Benutzer manuell
ausgeführte Schritte sind eigene, ausdrücklich angezeigte Dateisystemaktionen.

## Optional: vollständig isolierte neue RC13-Testinstanz

Eine neue Instanz ist für die spätere praktische Arbeit möglich. Sie ersetzt
nicht den automatisierten RC12-Upgrade-Nachweis. Bestehende Datasets müssen dafür
nicht gelöscht werden.

1. Eigene neue Test-Datasets für Appdaten und Workspace anlegen. Keinen Workspace
   mit einer anderen laufenden oder früheren Instanz teilen. Ein eigenes Archiv
   mit kopierten Testfotos verwenden.
2. Eine **Custom App** mit eigenem Namen und freiem Hostport, zum Beispiel 30046,
   anlegen. Image wie oben, Original-Entrypoint, Supervisor `0:0`, Webprozess
   `568:568`, Containerport `8080`. Für den isolierten NAS-Test Quellenhelper und
   Privileged deaktivieren. Rootdateisystem RO, `/tmp` als eigenes Tmpfs.
3. Mounts: neuer Appdatenstamm RW → `/appdata`; neuer Workspace RW → `/workspace`;
   eigenes Testarchiv **RO** → `/main-library`; optional eigene Importquelle
   **RO** → `/sources/nas`. Ein zusätzliches Archiv erhält einen eigenen
   RO-Containerpfad. Die Release-Compose-Vorlage verweigert fehlende Hostpfade.
4. Variablen: `KAMERA_APPDATA=/appdata`, `KAMERA_WORKSPACE=/workspace`,
   `KAMERA_POOL_PROBE=/workspace`, `KAMERA_ARCHIVE_ROOT=/main-library`,
   `KAMERA_WEB_UID=568`, `KAMERA_WEB_GID=568`,
   `KAMERA_SOURCE_HELPER_ENABLED=false` und eigenes
   `BIBLIOTHEKAR_ADMIN_PASSWORD` mit mindestens 16 Zeichen. Keine alten
   `/config`-/`/database`-Overrides in das Ein-Mount-Profil übernehmen.
5. `apps` benötigt tatsächlichen Lese-, Schreib- und Verzeichniszugriff auf die
   beiden neuen RW-Datasets einschließlich neu angelegter Kinder. Bereits
   passende Dataset-ACLs beibehalten. Zusätzliche berechtigte Hostbenutzer werden
   im hostverwalteten Profil als Administratoren des Speichers vertraut.
   Dieser Test ist keine neue native ACL-Freigabe und verlangt keine pauschalen
   Shell-, chmod-, chown- oder rekursiven ACL-Befehle.
6. Starten und anmelden. Die vier Verwaltungsordner und technischen Appdaten
   entstehen automatisch. Die erste Bibliothek bewusst mit dem RO-Testarchiv
   einrichten und anschließend neu starten.

## Rückkehr und Protokoll

Ein bloßer Imagewechsel zurück zu RC12 ist nach RC13-Arbeiten kein belastbarer
Rollback. Bei Bedarf stoppen, aktuellen Stand sichern und ausschließlich einen
vollständig zusammengehörigen früheren Appdaten-/Workspace-Sicherungsstand mit
seinem damaligen Image wiederherstellen. RC13 behält das F14-Format 3 bei;
RC12 versteht jedoch die ergänzten Projektionsnachweise nicht.

Für die Rückmeldung je Schritt PASS/FAIL, Version, Sprache, Bildschirmgröße,
genauen technischen Code und relevante Logs festhalten. Persönliche Testdaten
können nach erfolgreicher Abnahme durch eine separate neue Testinstanz ersetzt
werden; die Sicherheitsregeln gelten für jede Instanz weiterhin.
