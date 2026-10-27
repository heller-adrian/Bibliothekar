# RC12 auf TrueNAS SCALE isoliert testen

RC12 ist ein Test-Prerelease für Docker-basierte TrueNAS Apps (ab SCALE 24.10), keine native TrueNAS-Freigabe. Das produktive RC10-/RC11-Setup für diesen Test unverändert lassen. Der neue Aufbau ist ein eigener Installationsweg; alte Mounts werden nicht automatisch verschoben.

## 1. Getrennte Speicherorte in der Oberfläche

Unter Datasets ausschließlich neue Test-Datasets anlegen, beispielsweise:

| Host-Dataset | Container | Zugriff |
|---|---|---|
| `/mnt/apps/appdata/bibliothekar-rc12-test` | `/appdata` | RW |
| `/mnt/apps/bibliothekar-rc12-workspace` | `/workspace` | RW |
| eigenes Archiv mit kopierten Testfotos | `/main-library` | **Read Only** |

**Den bisherigen `/mnt/apps/kamera-arbeitsbereich` nicht verwenden.** Dort bestehen RC10-Nachweise. Neue Appdaten machen diesen Workspace nicht zu einer Neuinstallation.

Für Appdaten und Workspace muss der Benutzer `apps` UID568 tatsächlich lesen, schreiben und Verzeichnisse betreten können. Im Custom-App-Speicherdialog lässt sich dies über Enable ACL → User → ID568 → passende Schreib-/Leserechte oder über die vorhandene Dataset-ACL konfigurieren. Auf den neuen Datasets auch passende Vererbung für Kinder vorsehen. Eigentümer UID3000 und weitere ACL-Berechtigte sind im neuen Profil erlaubt. Wenn diese Rechte schon vorhanden sind, ist keine ACL-Änderung nötig. Keine rekursiven Rechtebefehle, Force-Vorlagen oder Shellinstallation erforderlich. Der Datenspeicher bleibt administrativ vom NAS verwaltet; alle dort schreibberechtigten Hostbenutzer gehören zur Vertrauensgrenze.

Der Appdatenstamm muss bereits als Dataset/Hostpfad existieren. Config, Database, Logs und Removable Sources werden **von der App** darunter angelegt. Sie benötigen keine vier separaten Host-Mounts.

## 2. Imagezugriff

GitHub-Repository und private GHCR-Berechtigungen bleiben unverändert. In der TrueNAS-Imageverwaltung Registry Authentication für ghcr.io mit einem berechtigten GitHub-Konto und befristetem Token `read:packages` konfigurieren. Token nicht in App-Logs oder Supportnachrichten kopieren.

Repository `ghcr.io/heller-adrian/bibliothekar`, Tag `1.0.0-rc.12`. Für den exakt veröffentlichten Stand die vollständige Referenz aus dem Release-Anhang **IMAGE-DIGEST.txt** verwenden; einen Digest nicht in ein reines Tag-Feld eintragen. Alternativ Install via YAML mit **compose.rc12.yaml** aus dem Release und den eigenen Hostpfaden/Passwortwerten verwenden. Die Vorlage verweigert fehlende Hostpfade statt sie automatisch zu erzeugen.

Release und Belege: https://github.com/heller-adrian/Bibliothekar/releases/tag/v1.0.0-rc.12

## 3. Neue Custom App

Apps → Discover / Custom App / Install Custom App, Name `bibliothekar-rc12-test`.

- Image wie oben; originalen Entrypoint/Command beibehalten.
- Container-Supervisor **0:0**; er startet die Webanwendung als **568:568**. Den gesamten Supervisor nicht auf 568 umstellen.
- Für diesen ersten NAS-/Ordner-Test **Privileged deaktiviert**, Quellenhelper deaktiviert.
- TCP Containerport8080 auf freien Hostport, etwa30045, veröffentlichen.
- Rootdateisystem Read Only; Tmpfs `/tmp`, 64MiB, Modus1777.
- Die drei obigen Mounts eintragen. Kein alter `/sources/removable`-Hostpfad nötig.

Umgebungsvariablen:

| Variable | Wert |
|---|---|
| `KAMERA_APPDATA` | `/appdata` |
| `KAMERA_WORKSPACE` | `/workspace` |
| `KAMERA_ARCHIVE_ROOT` | `/main-library` |
| `KAMERA_POOL_PROBE` | `/workspace` |
| `KAMERA_WEB_UID` / `KAMERA_WEB_GID` | jeweils `568` |
| `KAMERA_SOURCE_HELPER_ENABLED` | `false` |
| `BIBLIOTHEKAR_ADMIN_PASSWORD` | eigenes Passwort, mindestens16Zeichen |

Alte Variablen `KAMERA_CONFIG=/config/...`, `KAMERA_DATABASE_DIR=/database` oder `KAMERA_LOG_DIR=/logs` nicht aus RC11 übernehmen. Sie stehen im Widerspruch zum neuen Ein-Mount-Profil. Die richtigen Pfade sind automatisch `/appdata/config/settings.json`, `/appdata/database`, `/appdata/logs`, `/appdata/removable-sources`. Eine bereits vorbereitete Passwortdatei unter `/appdata/config` kann alternativ genutzt werden; dann `BIBLIOTHEKAR_ADMIN_PASSWORD_FILE` entsprechend setzen.

Optional eine eigene NAS-Testquelle als `/sources/nas` **Read Only** hinzufügen (YAML: compose.nas-source.yaml). Ein Archiv allein wird noch nicht automatisch als Bibliothek registriert.

## 4. Vollständige Abnahme

1. Starten und `http://NAS-IP:30045` öffnen; mit dem eigenen Passwort anmelden.
2. Vier Verwaltungsordner entstehen automatisch. Die erste Bibliothekseinrichtung muss erscheinen. Eine zusätzliche UID- oder Host-ACL-Exklusivitätsreparatur darf bei bereits vorhandenem tatsächlichem Schreibzugriff nicht verlangt werden.
3. Erste Testbibliothek mit Namen und bewusst ausgewähltem RO-Testarchiv erstellen. Die Archiveingabe wird weiterhin auf tatsächlichen Read-only-Mount geprüft.
4. In TrueNAS App neu starten, erneut anmelden, Bibliothek und normale Funktionen prüfen.
5. Zum Reparaturtest App stoppen. Nur im neuen Test-Workspace den **leeren Trash-Ordner** über eine geeignete Dateiverwaltung umbenennen. Keine Datenbank, Journale oder Appdaten verändern.
6. App starten: Diagnosezustand DEGRADED, betroffener Pfad und erwartete Ordneridentität müssen erscheinen. Anmeldung und Reparaturbereich müssen funktionieren; Dateioperationen bleiben gesperrt.
7. App stoppen, denselben ursprünglichen Ordner zurückbenennen, starten und „Erneut prüfen“. Regulärer Betrieb muss wieder funktionieren. Einzelne Dateien in einen neuen Ordner zu kopieren ist keine Wiederherstellung der alten Identität.
8. Für den zweiten Test denselben leeren Test-Trash nochmals umbenennen. App starten und „Ersatzordner anlegen“ wählen. Verlusthinweis lesen, Bestätigung und `REPLACE` eingeben. Ein neuer leerer Ordner und dauerhafter Verlustnachweis entstehen. Vorhandene Historie bleibt erhalten.
9. Anschließend weitere geschützte Aktion prüfen, etwa eine zweite Testbibliothek mit einem anderen separaten RO-Testarchiv anlegen, und erneut starten.
10. Archivdateien bytegleich halten; eigene Prüfsummen vor/nach dem Test vergleichen. Version, Digest, genaue Meldungen und Logs für den Ergebnisbericht sichern.

Bei fehlendem Dataset oder Appdaten-/Katalogverlust wird **kein** Ersatz auf dem darunterliegenden Dateisystem angelegt. Ursprüngliche Einbindung bzw. konsistente Gesamtsicherung wiederherstellen. Ungeklärte Operationsnachweise verhindern einen Ordnerersatz. Ein unbekannter Zustand bietet keinen Resetknopf. Ein fehlendes Passwort benötigt die App-Konfiguration; es gibt keinen anonymen Recovery-Zugang.

## 5. Optional: SD-/USB-Wechselmedien

Erst nach erfolgreichem Grundtest. compose.removable.yaml bzw. entsprechende Custom-App-Optionen aktivieren: `KAMERA_SOURCE_HELPER_ENABLED=true`, benötigte Geräte-/Mountprivilegien (derzeit privilegierter Helpercontainer), `/run/udev:/run/udev:ro`. Appdaten/Workspace bleiben dieselben, keine zusätzliche Removable-Hostfreigabe.

Die App richtet einen **containerprivaten rootkontrollierten Tmpfs** unter `/appdata/removable-sources` ein; Host-ACLs werden nicht geändert. Dort dürfen auf dem Host keine unbekannten Daten liegen. Root-/Kernel-Helperjournale sind für UID568 nicht schreibbar. Die physischen Quellen werden mit RO/nosuid/nodev/noexec gemountet. Helper/Web teilen denselben Containermountnamespace. Mountpropagation bleibt rprivate; keine Mounts werden auf dem NAS oder in anderen Apps veröffentlicht.

Der Kernel muss den eindeutigen statx-Mountnachweis unterstützen. Wenn der Runtime-Mount/Helper nicht sicher eingerichtet werden kann, bleibt die Webanwendung erreichbar und Wechselmedien sind nicht verfügbar. Kein Import über eine unbewiesene Mountidentität. Reales SD-/USB-Mounten, Neustart und sicheres Auswerfen sind **eigene noch erforderliche native Abnahmeschritte**. Privilegienminimierung bleibt ein offener Punkt vor stabiler1.0.0.

## 6. Bestehendes RC10/RC11-Layout

Keinen neuen `/appdata`-Mount auf die alten Einzelmounts draufsetzen. Für eine bestehende Installation bleiben `/config`, `/database`, `/logs`, der Workspace und ihre ursprünglichen Pfadvariablen erhalten; `KAMERA_APPDATA` bleibt ungesetzt. Die [Legacy-Compose](compose.legacy.yaml) enthält den bisherigen Aufbau. Die bisherige RC11-Sicherheitsqualifikation und die dokumentierte RC10-inspect/adopt-Übernahme bleiben wirksam. RC12 umgeht diese Herkunftsentscheidung nicht.

Ein Wechsel vorhandener Nutzerdaten in das neue Ein-Mount-Profil ist kein automatischer RC12-Upgradevorgang. Insbesondere Dateien zu kopieren und neue Inodes in F14 einzutragen wäre keine sichere Migration. Erst konsistente Snapshots/Backups bei gestoppten Schreibern; geplanter Umzug mit ursprünglichen Bindings und Recovery muss gesondert qualifiziert werden. Für den hier gewünschten RC12-Ersttest ausschließlich neue Datasets verwenden.

F14-Format3 und Workspace-Claim verhindern unkontrollierten Rückwechsel. Ein Imagewechsel zu RC11/RC10 ist **kein** gültiger Rollback der neuen Installation. Für einen Rückweg die neue Test-App stoppen und eine getrennte, konsistente Vorher-Sicherung nach Prüfung aller neuen Arbeiten verwenden. Keine alten Daten/WAL/SHM/Receipts/Claims löschen, um einen Start zu erzwingen.

## Prüfumfang und Referenzen

Automatisierte Linux-Ergebnisse und veröffentlichter Quellstand stehen im Release-Anhang TEST-REPORT.md. Native TrueNAS-/OpenZFS-/NFSv4-Abnahme wird erst durch diese Tests erbracht, nicht durch Linux-POSIX-ACLs oder synthetische ACL-Bytes.

- [TrueNAS Custom App und ACL-Eingabe](https://apps.truenas.com/managing-apps/installing-custom-apps/)
- [TrueNAS Custom-App-Speicherfelder](https://www.truenas.com/docs/scale/26/apps/installcustomappscreens/)
- [Docker Bind-Mounts und rprivate](https://docs.docker.com/engine/storage/bind-mounts/)
- [GHCR-Zugriffsrechte](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry)
