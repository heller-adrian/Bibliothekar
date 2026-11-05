# Bibliothekar v1.0.0-rc.1 – frische TrueNAS-Testinstallation

Dies ist ein Pre-release zur manuellen Erprobung, keine Freigabe von 1.0.0.
Nur neue Testdatasets und synthetische Fotos verwenden. Keine bestehende Bibliothek
oder produktive SD-Karte anbinden. Eine einzige App-Instanz verwenden.

## Bezug und Quellnachweis

Release: https://github.com/heller-adrian/Bibliothekar/releases/tag/v1.0.0-rc.1

Image: `ghcr.io/heller-adrian/bibliothekar:1.0.0-rc.1` (Linux amd64).
Für die Installation das Release-Asset `compose.truenas.yaml` verwenden: sein
Imagefeld ist bereits auf den überprüften Digest aus `IMAGE-DIGEST.txt` festgelegt.
`SHA256SUMS` prüft die heruntergeladenen Assets (`sha256sum -c SHA256SUMS`).
`source.txt` enthält Releasecommit und Git-Tree. Die geprüfte funktionale Basis ist
`ac2e7b8df4b8f7bb3a1582b7cb46d250250cd6ed` mit 1674 Linux-PASS.

Falls GHCR einen Login verlangt, in TrueNAS passende Registry-Zugangsdaten mit
Lesezugriff auf dieses Paket hinterlegen. Kein Token in das öffentliche YAML schreiben.
Repository- und Paketberechtigung sind getrennt. Als alternative Bezugsquelle enthält
der Release ein `docker save`-Archiv; auf einem ausdrücklich ausgewählten Testhost mit
`gzip -dc bibliothekar-1.0.0-rc.1-linux-amd64.tar.gz | docker load` laden. Danach den
festen Versionstag verwenden; ein neu geladenes lokales Archiv hat gegebenenfalls
noch keinen Registry-Digest im lokalen Dockerstore. Docker nur verwenden, wo die
TrueNAS-Version diesen administrativen Zugriff zulässt; keine Fremdinstallation
von Docker oder Änderung der TrueNAS-Systempakete erforderlich.

## Voraussetzungen

Docker-basierte TrueNAS SCALE Custom Apps (24.10 oder neuer), x86-64/amd64.
Die automatische Geräteverwaltung benötigt zusätzlich tatsächliche Kernelunterstützung
für `STATX_MNT_ID_UNIQUE` (Linux 6.8+ allein ist noch kein Laufzeitnachweis), geeigneten
Mountnamespace und Gerätezugriff. Bei fehlendem Nachweis lehnt der Helper sicher ab.
Das ist eine offene Plattformabnahme, keine stillschweigende Zusage für jede SCALE-Version.

Der bestehende Supervisor startet als root und senkt ausschließlich die WebApp auf
UID/GID **568:568** ab. Der interne Helper braucht das bisherige privilegierte
Containerprofil. Den Helperport 8090 niemals veröffentlichen; er bindet nur Loopback.
Nur den Webport 8080 als z.B. 30044 im vertrauenswürdigen Testnetz freigeben.

## Leere Datasets und Rechte vorbereiten

Über die TrueNAS-Oberfläche ausschließlich im eigenen Testbereich z.B.
`/mnt/TESTPOOL/bibliothekar-rc1` folgende leeren Unterdatasets/Verzeichnisse anlegen:

| Host-Unterpfad | Container | Zugriff und Eigentümer |
|---|---|---|
| `config` | `/config` | RW für 568:568; enthält Settings und Passwortdatei |
| `database` | `/database` | RW für 568:568; SQLite, Registry und Journale persistent |
| `logs` | `/logs` | RW für 568:568 |
| `workspace` | `/workspace` | RW für 568:568; ausreichender freier Speicher |
| `archive` | `/main-library` | Im Container RO, Verzeichnisse lesbar/traversierbar für 568 |
| `nas-source` | `/sources/nas` | Im Container RO, lesbar/traversierbar für 568 |
| `removable` | `/sources/removable` | RW-Mount für root; Wurzel root:root, z.B. 0755; **keine Schreib-ACL für 568** |

Auch Eltern des Helpernamensraums müssen vor Schreibzugriff der WebUID geschützt
sein. Darin wird der bestehende private 0700-Eigentumsnachweis angelegt. Nicht die
gesamte Teststruktur pauschal auf 568 umstellen. Effektive NFSv4-/POSIX-ACLs prüfen;
ein angezeigtes Modebit allein ist kein vollständiger ACL-Nachweis. Nie bestehende
NAS-Datasetrechte rekursiv ändern. Das Image ändert keine Host-ACLs automatisch.

Alle Hostpfade müssen vor dem Start vorhanden und tatsächlich eingebunden sein.
Das YAML verwendet `create_host_path: false`; ein fehlender Mount darf nicht durch
einen automatisch erzeugten leeren Hostordner verdeckt werden. Die tatsächliche
Datasetbindung muss der Betreiber zusätzlich prüfen. Ein vorhandener leerer Ordner
beweist keinen korrekten Mount.

Vor Start `/config/admin-password` im Host-`config`-Dataset als normale Datei
bereitstellen, lesbar nur für den vorgesehenen Appbenutzer (z.B. 568:568, 0600).
Langes eigenes Passwort verwenden (mindestens 16 Zeichen), kein Symlink. Das Passwort
nicht ins YAML, einen Screenshot oder einen QA-Bericht schreiben. Fehlendes oder
schwaches Passwort sperrt die Anmeldung.

## App installieren

1. `compose.truenas.yaml` herunterladen, Prüfsumme prüfen und **alle**
   `/mnt/TESTPOOL/bibliothekar-rc1/...`-Beispielpfade durch die eigenen leeren
   Testpfade ersetzen. Weitere Bibliotheken später mit eigenen expliziten Mounts
   und Archivpfaden anlegen; keine pauschale Freigabe von `/mnt` oder `/`.
2. In TrueNAS **Apps → Discover → Install via YAML** wählen, Namen z.B.
   `bibliothekar-rc1` eingeben und das angepasste YAML einfügen.
3. Bestehendes Profil beibehalten: root-Supervisor, privilegierter Helper,
   read-only Containerroot, `/tmp`-tmpfs, persistente getrennte Datasets,
   `/run/udev` nur lesend. Keine zusätzlichen Ports, Host-Netzwerk oder Mounts
   des Docker-Sockets hinzufügen.
4. App starten und `http://TESTNAS:30044` öffnen. Nur im Testnetz betreiben.
   Für HTTPS hinter dem eigenen Reverse-Proxy
   `BIBLIOTHEKAR_COOKIE_SECURE: "true"` setzen und dessen tatsächlich vertrauenswürdige
   Proxykonfiguration gesondert prüfen. Keine beliebigen Forwarded-Header freigeben.
5. Einloggen, erste Testbibliothek mit explizitem Workspace-/Archivpfad anlegen.
   Neuinstallationen verwenden feste englische Verwaltungsnamen:
   `SD Card Backups`, `Library Workspaces`, `Metadata Correction`, `Trash`.
   Einstellungen können diese Verwaltungsstämme nicht mehr umbenennen.

Archiv bleibt innerhalb der App RO. Der vorhandene Archivablauf bereitet Bestand/
Staging vor; den vorgesehenen externen Kopierschritt mit synthetischen Daten über
SMB/TrueNAS ausführen und danach in Bibliothekar vollständig verifizieren. Keine
Arbeitskopien freigeben, bevor die Archivprüfung bestanden ist. Archivdateien während
der Freigabe nicht extern bearbeiten. Die akzeptierten F13/F24-Grenzen stehen in den
Release Notes. Nach unterbrochener Freigabe nur den ausdrücklichen erneuten Versuch
verwenden, keine Journale manuell löschen.

## Neustart und Fehler

Container-/Appneustart darf Datenbank, Settings, Workspace und Helpernachweise nicht
verlieren. Unbekannte Mountzuordnungen nach Namespace-/Bootwechsel werden gesperrt,
nicht automatisch als eigener Mount übernommen. Keine fremden Mounts auswerfen.
Bei fehlendem bekannten Verwaltungsordner Warnung beachten, den tatsächlichen Mount/
Ordner manuell wiederherstellen und **Erneut prüfen** wählen. Keine leere Ersatzstruktur
über einen ungeklärten Bestand legen. Bei Fehler stoppen und Containerlogs/Version/
Digest ohne Passwörter sichern.

Die vollständige praktische Prüfung steht in `MANUAL-ACCEPTANCE.md`.
Historische Upgrades sind für diesen RC nicht abgenommen; frische Testinstallation.

Offizielle Installation via YAML:
https://apps.truenas.com/managing-apps/installing-custom-apps/
