# Bibliothekar RC11 auf TrueNAS testen

RC11 ist ein **Prerelease für die eigene TrueNAS-Abnahme**, keine stabile 1.0.0. Linux-Prüfungen und native TrueNAS-Prüfungen sind unterschiedliche Nachweise. Diese Anleitung verändert nichts automatisch auf Ihrem NAS. Sie gilt für die Docker-basierte Apps-Oberfläche ab TrueNAS SCALE 24.10; Beschriftungen können je nach Version/Sprache abweichen.

Release: https://github.com/heller-adrian/Bibliothekar/releases/tag/v1.0.0-rc.11

Image: `ghcr.io/heller-adrian/bibliothekar:1.0.0-rc.11`, Linux/amd64. Für einen unveränderlichen Stand verwenden Sie die vollständige Referenz aus dem Release-Anhang **IMAGE-DIGEST.txt**. Die Release-Anhänge enthalten außerdem `compose.rc11.yaml`, Quellcode und `SHA256SUMS`. Der Digest wird erst beim tatsächlichen Registry-Push bestimmt; es gibt hier keinen erfundenen Platzhalterdigest.

## Vorbereitungen und privater Registryzugriff

Das GitHub-Repository bleibt privat. Melden Sie sich für Release und Downloads bei GitHub an. Für private GHCR-Images benötigt TrueNAS eigene Leseberechtigungen:

1. In GitHub unter Settings → Developer settings → Personal access tokens → Tokens (classic) einen eigenen, befristeten Token mit `read:packages` erstellen. Das Konto muss Leserecht am Bibliothekar-Paket besitzen; gegebenenfalls muss Organisations-SSO freigeschaltet werden.
2. In TrueNAS unter Apps → Configuration → Manage Container Images → Pull Image die Registry `ghcr.io`, das Image und Tag `1.0.0-rc.11` eintragen. Bei Registry Authentication den GitHub-Benutzernamen und den Token als Passwort verwenden. Auch die App-Konfiguration muss diese Registry-Anmeldedaten für spätere Neustarts/Pulls verwenden. Ein bereits zwischengespeichertes Image ersetzt keine dauerhafte Zugriffskonfiguration.
3. Tokens nicht in Bibliothekar-Umgebungsvariablen, Logs, Screenshots oder Supportnachrichten kopieren. Kein Schreib- oder Löschrecht für den NAS-Pulltoken anfordern.

Die Registry muss für den tatsächlichen NAS-Benutzer zugänglich sein. Der automatisierte Release-Test weist den Pull aus GHCR mit dem Workflowkonto nach, nicht bereits die Rechte Ihres NAS-Kontos.

## A. Neue, getrennte RC11-Testinstallation

### 1. Isolierte Speicherorte anlegen

Unter Datasets neue Test-Datasets anlegen. Keine Verzeichnisse der bestehenden RC10-Installation wiederverwenden. Ein eigener Workspace und private Appdaten sind erforderlich. Ein Testarchiv mit einigen kopierten Testfotos reicht; das echte Archiv muss für diesen Ersttest nicht verwendet werden.

Private Appdaten (`config`, `database`, `logs`) und gemeinsamer Foto-Workspace erfüllen unterschiedliche Aufgaben. Unter `database` werden SQLite, F14-State und die private Sperre dauerhaft gespeichert. `/database` darf kein flüchtiger Tmpfs sein.

TrueNAS bietet auch **ixVolume** an: Damit wird ein App-Dataset automatisch angelegt. Für diesen isolierten Test ist das eine mögliche Option. Die aktuelle TrueNAS-Dokumentation empfiehlt ixVolumes jedoch nicht als dauerhaften Produktionsspeicher und weist auf erschwerte Backups hin. ixVolume ist außerdem **kein automatischer Beweis**, dass seine tatsächliche ACL RC11 genügt. Beim Löschen einer Test-App dürfen deren Volumes nur dann mitgelöscht werden, wenn sie sicher ausschließlich Testdaten enthalten.

### 2. Private Berechtigungen in der Oberfläche prüfen

Datasets → das ausschließlich für Bibliothekar bestimmte private Dataset → Permissions / Edit ACL:

- UID **568** (`apps`) muss als einzelner Benutzer die benötigten Rechte besitzen und Eigentümer der von Bibliothekar verwalteten Kontrollobjekte sein.
- RC11 vertraut UID 0 und der tatsächlichen Web-UID sowie den ausdrücklich definierten Administratorgruppen 0/544. Ein Grant an die gesamte Gruppe `apps` ist kein Grant ausschließlich an UID 568.
- Andere Benutzer und Gruppen dürfen im privaten Bereich nicht schreiben, löschen, Objekte ersetzen oder ACL/Eigentümer ändern. Entfernen Sie breite geerbte Schreib-Grants dort bewusst; Namen wie `adrian`, `hermes` oder `builtin_users` werden nicht automatisch als Administrator akzeptiert.
- Relevante Eltern dürfen keinen Austausch der privaten Dateien erlauben. Rechte müssen auch für neu angelegte private Kinder passend vererben. Neue F14-Kontrolldateien/-verzeichnisse werden mit privaten Modi angelegt.
- Auf ZFS muss eine für UID 568 tatsächlich lesbare native NFSv4-ACL vorhanden sein. Modus `0700` allein genügt nicht.

**Nicht** die gemeinsame Workspace-ACL pauschal ändern. Keine Freigabevorlage blind auf vorhandene Fotos anwenden. Bei unsicherem Ergebnis zunächst den getrennten privaten Testbereich korrigieren. RC11 repariert ACLs nicht automatisch und bietet keine Umgehungsvariable.

### 3. Custom App über die TrueNAS-Oberfläche einrichten

Apps → Discover Apps → Custom App / Install Custom App. Name beispielsweise `bibliothekar-rc11-test`.

Image Repository: `ghcr.io/heller-adrian/bibliothekar`; Tag: `1.0.0-rc.11`. Wenn die Oberfläche eine vollständige Imagereferenz erlaubt, die Digestreferenz aus IMAGE-DIGEST.txt verwenden. Alternativ unter Install via YAML die Release-Datei `compose.rc11.yaml` verwenden und ausschließlich die bezeichneten Hostpfade und Zugangsdaten eintragen. Der Digest gehört nicht in ein reines Tag-Feld, das keine Digestsyntax unterstützt.

Den originalen Entrypoint und Command für den normalen Betrieb beibehalten. Der Container-Supervisor startet als **root (0:0)** und setzt den Webprozess auf **568:568** herab. Nicht den gesamten normalen Supervisor auf Benutzer 568 umstellen. Die bestehenden Helper-/Geräteoptionen aus der Compose-Vorlage sind für Quellenzugriff vorgesehen; insbesondere sind Privilegien und Gerätezugriff vor einer stabilen Paketierung noch zu reduzieren und abzusichern.

Port: Host **30044**, Container **8080**, TCP. Für eine parallele Test-App einen anderen freien Hostport, etwa 30045, verwenden.

Speichermounts:

| Test-Speicher | Containerpfad | Zugriff |
|---|---|---|
| privates Config-Dataset | `/config` | RW |
| privates Datenbank-Dataset | `/database` | RW |
| privates Log-Dataset | `/logs` | RW |
| gemeinsamer Test-Workspace | `/workspace` | RW |
| separates Testfotoarchiv | `/main-library` | **Read Only** |
| optionale NAS-Importquelle | `/sources/nas` | Read Only |
| temporärer RAM-Speicher | `/tmp` | Tmpfs, 64 MiB, Modus 1777 |

Umgebungsvariablen in der App-Oberfläche setzen:

| Name | Wert |
|---|---|
| `BIBLIOTHEKAR_ADMIN_PASSWORD` | eigenes langes Testpasswort |
| `KAMERA_CONFIG` | `/config/settings.json` |
| `KAMERA_DATABASE_DIR` | `/database` |
| `KAMERA_REGISTRY_DATABASE` | `/database/bibliothekar-global.sqlite3` |
| `KAMERA_WORKSPACE` | `/workspace` |
| `KAMERA_LOG_DIR` | `/logs` |
| `KAMERA_ARCHIVE_ROOT` | `/main-library` |
| `KAMERA_POOL_PROBE` | `/workspace` |
| `KAMERA_WEB_UID` / `KAMERA_WEB_GID` | jeweils `568` |

Weitere Helper-/Quellenvariablen wie in der Compose-Vorlage übernehmen. Für den regulären Neuaufbau sind weder SQL-Befehle noch `storage_admin adopt` nötig. `settings.json` wird automatisch angelegt. Als Alternative zum Passwort in der App-Konfiguration unterstützt die Vorlage eine bereits administrativ bereitgestellte Passwortdatei; diese Datei wird nicht automatisch mit einem Standardpasswort erzeugt.

### 4. Erfolgreichen Erststart erkennen

1. App starten und Logs öffnen. Bei einer ACL-Sperre den **genauen Pfad und Code** notieren. `acl_backend_unavailable` bedeutet, dass RC11 die native ACL nicht ausreichend prüfen konnte; das ist kein erfolgreicher Start. Keine zusätzlichen pauschalen Containerprivilegien zum Verdecken des Fehlers setzen.
2. `http://NAS-IP:HOSTPORT` aufrufen und mit dem gesetzten Passwort anmelden.
3. Die vier Verwaltungsordner entstehen automatisch: `SD Card Backups`, `Library Workspaces`, `Metadata Correction`, `Trash`. Allein deren Existenz ist noch kein Erfolgsnachweis.
4. Es muss die Einrichtung der **ersten Bibliothek** erscheinen. Namen eingeben, den vorgeschlagenen Arbeitsordner verwenden und das RO-Testarchiv bewusst auswählen. Ein gefülltes Archiv darf vorher nicht automatisch registriert worden sein.
5. Bibliothek tatsächlich erstellen, die Anwendung erneut öffnen und in der TrueNAS-Oberfläche neu starten. Bibliothek muss erhalten bleiben. Anschließend eine weitere geschützte Aktion durchführen, beispielsweise eine zweite Testbibliothek mit eigenem RO-Testarchiv erstellen.
6. Archivdateien und deren Prüfsummen müssen unverändert bleiben. Bei Fehlern Logs, Storage-Health-Ausgabe und Versions-/Digestangabe sichern; keine Reparaturdateien löschen.

## B. Bereits blockierte RC10-Installation erhalten

Diese Schritte betreffen den bekannten Stand mit `initializing`, Generation 0 und passender offener Startupreservation. **Kein Clean Slate. Keine Inodes oder Reservationsdateien manuell umschreiben.**

### 1. Stoppen und konsistent sichern

1. TrueNAS → Apps → Bibliothekar → Stop. Warten, bis alle zugehörigen Container beendet sind. Andere Writer auf diese privaten Daten ebenfalls anhalten.
2. Vorherige App-Konfiguration, Image/Digest, Mountzuordnung und ACL-Anzeigen dokumentieren. Tokens/Passwörter nicht in Supportunterlagen aufnehmen.
3. Unter Data Protection / Snapshots beziehungsweise Datasets konsistente Snapshots der zugehörigen Datasets erstellen. Wenn mehrere Datasets beteiligt sind, während der gesamten Sicherung alle Writer angehalten lassen und die zusammengehörigen Snapshotnamen dokumentieren. Ein rekursiver Snapshot eines passenden gemeinsamen Eltern-Datasets kann die Verwaltung vereinfachen; keine fremden Datasets zurückrollen.
4. Sichern müssen Sie Config, Datenbankverzeichnis **einschließlich WAL/SHM, verborgenem `.bibliothekar-root-control` und Retention**, Logs und den Workspace mit seinen technischen Artefakten. Eine zusätzliche konsistente Sicherung auf anderem Speicher ist empfehlenswert. Nur `kamera.sqlite3` zu kopieren reicht nicht.
5. Sicherungs-/Snapshotreferenz aufschreiben. Die spätere CLI verlangt diese Referenz als ausdrückliche Betreiberbestätigung; sie beweist nicht selbst, dass das Backup vollständig ist.

Eine Dateikopie oder ein Datasetklon kann Geräte-/Inodeidentitäten verändern. Eine solche Kopie ist nicht automatisch eine wiederaufnehmbare Installation. Produktive Bindings dürfen nicht zur Anpassung an eine Kopie editiert werden.

### 2. Private ACLs bewusst absichern

Ihr gemeldeter privater F14-Bereich ist trotz Modus 0700 wegen zusätzlicher Schreib-ACEs nicht qualifiziert. Deshalb wird RC11 ihn zunächst blockieren.

In der Dataset-/ACL-Oberfläche ausschließlich die privaten Appdaten und deren relevante Eltern prüfen. Die Anforderungen aus A.2 gelten auch für vorhandene F14-Dateien, Sperren und Receipts. Geerbte Grants an `adrian`, `hermes`, allgemeine Gruppen und `apps` als Gruppe dürfen dort keine fremde Kontrollautorität erlauben. Die gemeinsame Workspace-ACL und das alte Workspace-Lock bleiben erhalten.

Kein blindes „Force“, keine pauschale rekursive Rechtevorlage und kein `chmod -R`/`chown -R`. Vorhandene private Kinder müssen gezielt mitgeprüft werden; nur die Datasetwurzel zu ändern genügt nicht. Wenn die Oberfläche das nicht eindeutig ermöglicht, die ACL-Prüfung mit einem TrueNAS-Administrator durchführen. Dies ist eine **RC11-Übergangsanforderung** für die bereits potenziell fremdbeschreibbaren Nachweise.

Nachträgliches Absichern beweist nicht, dass vorher niemand die Dateien verändert hat. Sie müssen die Herkunft anhand Ihrer Sicherungen und Diagnose bewerten. Die gemeldeten übereinstimmenden Rollenidentitäten sind ein positiver Befund, ersetzen diese Entscheidung aber nicht.

### 3. Offline-Prüfung mit dem RC11-Migrationswerkzeug

Die Original-App bleibt gestoppt. Für RC11 ist hier einmalig eine Shell erforderlich. Sie dient ausschließlich der Prüfung und ausdrücklichen Übernahme, nicht dem Editieren von SQLite oder F14.

Praktischer Weg über die Apps-Oberfläche: eine **separate temporäre Wartungs-App** mit dem RC11-Image erstellen. Ihr Supervisor/Webserver darf nicht starten. Setzen Sie Entrypoint auf `sleep`, Command auf `infinity`, Benutzer/Gruppe auf **568:568**. Die bestehenden Original-Hostpfade unter denselben Containerpfaden mounten: `/workspace`, `/config`, `/database`, `/logs`, Archiv RO. Die gleichen `KAMERA_*`-Pfadvariablen wie in der Original-App setzen. Keine neuen ixVolumes als Ersatz für die ursprünglichen Appdaten verwenden. Kein veröffentlichter Port ist für diese Wartungs-App nötig.

Nur diese Wartungs-App starten. Unter Workloads → Shell den Wartungscontainer öffnen. Bei `id` müssen UID/GID 568 erscheinen. Dann:

```sh
python -m app.storage_admin inspect
```

Wirkung: aktuelle private Autorität, exakte Reservation, Schlüssel/ID, Generation, alle Rollenbindungen, Kataloge, Registry, Jobs, Retention und weitere Operationsnachweise prüfen. Kein Reset. Bei einer Sperre stoppen und die konkrete Ursache klären. Ein Native-ACL-Abfragefehler darf nicht ignoriert werden.

Die Ausgabe enthält den `token` für den genau beobachteten Zustand. Erst nach Prüfung, Sicherung und bewusster Herkunftsentscheidung:

```sh
python -m app.storage_admin adopt \
  --token 'TOKEN_AUS_DER_EIGENEN_INSPECT_AUSGABE' \
  --confirmation 'ADOPT RC10 BOOTSTRAP' \
  --backup-reference 'EIGENE_KONSISTENTE_SNAPSHOT_ODER_BACKUPREFERENZ'
```

Die drei gekennzeichneten Texte durch die eigenen Angaben ersetzen. **Keine** Reservations-ID aus dieser Anleitung eintippen. Das Werkzeug verändert keine ACL, löscht keine historischen Daten und übernimmt keine widersprüchliche Historie. Es schreibt einen dauerhaften Übernahmebeleg mit Originalnachweisen. SQLite-Inspektion ist WAL-sichtbar und kann technische SHM-Dateien erzeugen; deshalb zuerst sichern.

Für eine tatsächlich schon vollständig eingerichtete Format-1-Bestandsinstallation wäre der getrennte Scope `--scope control` erforderlich. **Für Ihren beschriebenen offenen Erststart bleibt es bei den obigen Befehlen ohne diesen Zusatz.**

### 4. Original-App auf RC11 umstellen und fortsetzen

1. Wartungs-App vollständig stoppen. Nie RC10 und RC11 oder Wartungs- und Original-App gleichzeitig auf dieselben Daten schreiben lassen.
2. In der gestoppten Original-App nur die Imagereferenz auf den veröffentlichten RC11-Tag bzw. Digest umstellen. Vorhandene Hostpfade, Containerpfade, Passwort, Port und Web-UID/GID beibehalten. Kein neues Datenbankvolume anlegen.
3. App starten. RC11 setzt nach erfolgreicher Qualifikation die **ursprüngliche Reservation** fort, erhält Generationen/Bindings und schließt die technische Einrichtung mit neuen dauerhaften Belegen ab.
4. Anmelden, erste Bibliothek tatsächlich erstellen, Neustart und weitere geschützte Aktion prüfen. Danach Logs und Storage-Health sichern. Das alte `.trash-deletions/.lock` darf unverändert als Legacy-Artefakt bestehen bleiben; die aktive Sperre liegt privat.
5. Bei einer Ablehnung die konkrete Meldung sichern. Nicht manuell `completed` setzen, keinen Operationsnachweis entfernen und keine SQLite-/WAL-Dateien löschen.

### 5. Rollbackgrenze

Nach Format-2-Migration ist ein bloßer Imagewechsel zurück zu RC10 **kein gültiger Rollback**. RC10 soll den neuen Kontrollzustand ablehnen. Ein Rückweg erfordert angehaltene Writer, eine konsistente Gesamtsicherung und eine Bewertung aller seitdem entstandenen Arbeiten. Neue Bibliotheken/Medienarbeit dürfen dabei nicht verschwinden. Geänderte Inodes durch Restore benötigen das bestehende ausdrückliche Recoveryverfahren; keine Bindings blind umschreiben.

## Was für 1.0.0 noch fehlt

Normale Neuinstallation soll über den TrueNAS-App-Dialog ohne Shell, ACL-Befehle, SQL oder Reservationsbearbeitung möglich sein. Dafür fehlen noch native Abnahme und ein passendes Paketprofil:

- Ein vom Installationsdialog angelegter bzw. ausgewählter privater persistenter Speicher mit nachgewiesen passenden ACLs, UID/GID und Vererbung. ixVolume kann das Testen vereinfachen, ist laut TrueNAS keine pauschale Empfehlung für dauerhaften Produktionsspeicher.
- Wiederholbar getestete Neuinstallation über die tatsächlich unterstützten TrueNAS-Versionen und ACL-Backends; kein Modusbit-Fallback.
- Verständliche Speicherprüfung und nötigenfalls geführte administrative Übernahme in der Weboberfläche. Der RC11-Shellpfad ist ein Übergang für historische Nachweise.
- Gesicherte Backup-/Upgrade-/Rollback-Lebenszyklen, auch bei App-Entfernung und privaten Volumes.
- Minimale Helper-/Geräteprivilegien und Registry-Zugang im regulären App-Paket.

Das ist als offenes Paketierungsziel dokumentiert. Es ist kein Grund, einen automatisch abgenommenen RC11-Test-Prerelease als stabile oder bereits nativ freigegebene Version darzustellen.

## Offizielle Referenzen

- [TrueNAS Custom Apps und Oberfläche](https://www.truenas.com/docs/scale/26/apps/installcustomappscreens/)
- [TrueNAS App-Speicher und ixVolume-Grenzen](https://apps.truenas.com/getting-started/app-storage/)
- [TrueNAS private Images verwalten](https://apps.truenas.com/managing-apps/managing-installed-apps/)
- [GitHub Container Registry und Lesetokens](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry)
