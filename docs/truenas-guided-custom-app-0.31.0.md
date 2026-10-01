# TrueNAS Guided Custom App – Bibliothekar 0.31.0

0.31.0 ist für den formularbasierten TrueNAS-Assistenten **Installieren Custom App**
bzw. die Aktualisierung der bestehenden Bibliothekar-Custom-App ausgelegt.

Der stabile fachliche Kamerakern bleibt 0.28.7. 0.31.0 ergänzt
Mehrbibliotheksbetrieb und den korrigierten direkten SD-Gerätezugriff.

## Image

- Repository: `ghcr.io/heller-adrian/bibliothekar`
- Tag: `patch-0.31.0`
- Container-Port: `8080`
- empfohlener Host-Port: `30044`
- Containerstart: `root`
- Privileged: aktiviert, solange direkt angeschlossene SD-/USB-Medien verwendet werden
- Web-App intern: UID/GID `568:568`

## Umgebungsvariablen

- `TZ=Europe/Berlin`
- `KAMERA_CONFIG=/config/settings.json`
- `KAMERA_WORKSPACE=/workspace`
- `KAMERA_DATABASE_DIR=/database`
- `KAMERA_REGISTRY_DATABASE=/database/bibliothekar-global.sqlite3`
- `KAMERA_LOG_DIR=/logs`
- `KAMERA_POOL_PROBE=/workspace`
- `KAMERA_ARCHIVE_ROOT=/main-library`
- `KAMERA_IMPORT_ROOT=/sources/import`
- `KAMERA_REMOVABLE_ROOT=/sources/removable`
- `KAMERA_NAS_SOURCE_ROOT=/sources/nas`
- `KAMERA_SOURCE_HELPER_URL=http://127.0.0.1:8090`
- `KAMERA_SOURCE_HELPER_ENABLED=true`
- `KAMERA_REMOVABLE_MOUNT_ROOT=/sources/removable`
- `KAMERA_DEVICE_NODE_ROOT=/dev/bibliothekar`
- `KAMERA_WEB_UID=568`
- `KAMERA_WEB_GID=568`

## Bestehende Main-Library-Mounts

Die bestehende Installation wird in-place weiterverwendet:

- `/mnt/apps/appdata/kamera-automatisierung/config` → `/config` (RW)
- `/mnt/apps/appdata/kamera-automatisierung/database` → `/database` (RW)
- `/mnt/apps/appdata/kamera-automatisierung/logs` → `/logs` (RW)
- `/mnt/apps/kamera-arbeitsbereich` → `/workspace` (RW)
- `/mnt/storage/fotos/Kamerabibliothek` → `/main-library` (RO)
- `/mnt/storage/backup/kamera-sd-karten` → `/sources/import` (RO)
- `/mnt/storage` → `/sources/nas` (RO)
- `/mnt/apps/appdata/kamera-automatisierung/removable-sources` → `/sources/removable` (RW als Mountpunkt)
- `/run/udev` → `/run/udev` (RO)

`/tmp` sollte als tmpfs eingebunden werden, z. B. 64 MiB. Wenn der
formularbasierte Assistent diese Option nicht anbietet, ist das für den
Funktionstest kein Blocker.

## Upgrade von 0.30.1

Für das Upgrade der bestehenden Main Library sind keine neuen Main-Mounts und
keine Kopie der vorhandenen SQLite-Datenbank nötig.

Beim Start:

1. bleibt `/database/kamera.sqlite3` die Main Library,
2. wird die globale Registry automatisch auf Schema v2 erweitert,
3. werden vorhandene Familien idempotent inventarisiert,
4. bleiben unzugeordnete Familien frei,
5. werden geplante Familien als `reserved` und angewendete/archivierte Familien
   als `owned` übernommen.

Die bestehende App darf nicht parallel ein zweites Mal mit derselben Datenbank
und demselben Host-Port laufen.

## Zusätzliche Bibliothek vorbereiten

Bibliothekar erzeugt keine TrueNAS-Host-Path-Mounts selbst. Diese werden zuerst
in der Custom App ergänzt.

Beispiel **Business**:

1. Einen persistenten Arbeitsbereich auf dem SSD-Dateisystem anlegen und als
   Host Path read-write in den Container mounten, z. B.
   `/libraries/business/workspace`.
2. Das gewünschte Archiv als Host Path **read-only** mounten, z. B.
   `/libraries/business/archive`.
3. Der Arbeitsbereich muss für Hardlinks auf demselben Dateisystem wie die
   gemeinsamen `/workspace/SD-Kartensicherungen` liegen.
4. Das Archiv darf auf einem anderen Dataset liegen.

Danach in Bibliothekar:

**Menü → Einstellungen → Konfiguration → Bibliotheken → Bibliothek hinzufügen**

Eintragen:

- Anzeigename, z. B. `Business`
- Arbeitsbereich, z. B. `/libraries/business/workspace`
- Archiv, z. B. `/libraries/business/archive`

Zuerst **Prüfen**, danach **Bibliothek hinzufügen**.

Die technische Bibliotheks-ID und die SQLite-Datei werden automatisch erzeugt.
Die neue Datenbank liegt unter
`/database/libraries/<interne-id>.sqlite3`.

## Bibliotheksumschalter

Über **Bibliothek wechseln** kann eine aktive Bibliothek ausgewählt werden.

Die Auswahl wird request-lokal über die Library-ID geführt. Zwei Browser-Tabs
dürfen dadurch gleichzeitig in unterschiedlichen Bibliotheken arbeiten; es
existiert kein globaler „aktuelle Bibliothek“-Schalter im Serverprozess.

## Deaktivieren und Abmelden

- **Deaktivieren** nimmt eine Bibliothek aus dem aktiven Betrieb. Dateien,
  Datenbank, Archiv und globale Besitzstände bleiben erhalten.
- **Aktivieren** nimmt sie wieder in den aktiven Betrieb.
- **Abmelden** entfernt nur die Registrierung aus der sichtbaren Bibliotheksliste.
  Es werden keine Dateien, Datenbanken oder Archive gelöscht.

Die Main Library kann nicht deaktiviert oder abgemeldet werden.

## Globale Familien-Claims

Die Registry verhindert parallele Doppelzuordnung derselben kanonischen
Dateifamilie:

- frei/unzugeordnet: kein Claim
- geplant: `reserved`
- angewendet oder archiviert: `owned`

Eine Familie mit Claim einer anderen Bibliothek wird aus deren sichtbarem freien
Bestand herausgefiltert. Wird ein lediglich geplantes Ereignis wieder
aufgehoben, wird seine Reservierung freigegeben. Ein `owned`-Claim wird durch
einen bloßen Planungsabbruch nicht entfernt.

## Direkter SD-/USB-Zugriff

TrueNAS kann dem privilegierten Container die Geräteinformationen über
`/sys`/`udev` sichtbar machen, ohne für jede neu eingesteckte Partition
bereits einen passenden `/dev/<partition>`-Node im Container anzulegen.

0.31.0 löst diesen Fall wie folgt:

1. `lsblk` erkennt die konkrete Partition.
2. Falls ihr ursprünglicher Geräte-Node im Container vorhanden ist, wird er
   direkt verwendet.
3. Andernfalls liest der Helper Major/Minor ausschließlich für diese erkannte
   Partition aus `/sys/class/block/<kernelname>/dev`.
4. Er erzeugt dafür einen temporären Block-Node unter
   `/dev/bibliothekar/<kernelname>`.
5. Das Dateisystem wird mit `ro,nosuid,nodev,noexec` und den jeweiligen
   Dateisystemoptionen eingebunden.
6. Nach dem Aushängen wird der verwaltete Node wieder entfernt.

Der Webserver selbst läuft weiterhin nicht als root; der Helper ist nur unter
`127.0.0.1:8090` im Container erreichbar.

## Sicherheitsgrenze

0.31.0 ist weiterhin eine privilegierte Custom App, solange direkter
SD-/USB-Zugriff gewünscht ist. Die Discover-Härtung bzw. optionale Auslagerung
der Geräteintegration ist für 0.32 vorgesehen.
