# TrueNAS Guided Custom App – Bibliothekar 0.29.1

0.29.1 ist für den formularbasierten TrueNAS-Assistenten **Installieren Custom App** ausgelegt.

## Image

- Repository: `ghcr.io/heller-adrian/bibliothekar`
- Tag: `patch-0.29.1`
- Container-Port: `8080`
- empfohlener Host-Port: `30044`
- Containerstart: als root
- Privileged: aktiviert, solange direkt angeschlossene SD-/USB-Medien verwendet werden
- Die Web-App selbst wird intern vom Supervisor auf UID/GID `568:568` abgesenkt.

## Umgebungsvariablen

- `TZ=Europe/Berlin`
- `KAMERA_CONFIG=/config/settings.json`
- `KAMERA_WORKSPACE=/workspace`
- `KAMERA_DATABASE_DIR=/database`
- `KAMERA_LOG_DIR=/logs`
- `KAMERA_POOL_PROBE=/workspace`
- `KAMERA_ARCHIVE_ROOT=/main-library`
- `KAMERA_IMPORT_ROOT=/sources/import`
- `KAMERA_REMOVABLE_ROOT=/sources/removable`
- `KAMERA_NAS_SOURCE_ROOT=/sources/nas`
- `KAMERA_SOURCE_HELPER_URL=http://127.0.0.1:8090`
- `KAMERA_SOURCE_HELPER_ENABLED=true`
- `KAMERA_REMOVABLE_MOUNT_ROOT=/sources/removable`
- `KAMERA_WEB_UID=568`
- `KAMERA_WEB_GID=568`

## Persistente Pfade der bestehenden Installation

Diese Hostpfade werden bei der Migration nicht verschoben:

- `/mnt/apps/appdata/kamera-automatisierung/config` -> `/config`
- `/mnt/apps/appdata/kamera-automatisierung/database` -> `/database`
- `/mnt/apps/appdata/kamera-automatisierung/logs` -> `/logs`
- `/mnt/apps/kamera-arbeitsbereich` -> `/workspace`
- `/mnt/storage/fotos/Kamerabibliothek` -> `/main-library` (read-only)
- `/mnt/storage/backup/kamera-sd-karten` -> `/sources/import` (read-only)
- `/mnt/storage` -> `/sources/nas` (read-only)
- `/mnt/apps/appdata/kamera-automatisierung/removable-sources` -> `/sources/removable` (read-write als Mountpunkt; das Wechselmedium selbst wird read-only gemountet)
- `/run/udev` -> `/run/udev` (read-only, für Geräte-Metadaten)

`/tmp` bleibt flüchtig (tmpfs).

## Sicherheitsgrenze 0.29.1

Der privilegierte Containerstart ist nur für den direkten Gerätezugriff nötig. Die fachliche Web-App läuft nicht als root. Der Geräte-Helper ist nur lokal im Container erreichbar. Das endgültige Discover-Modell soll die Geräteintegration weiter härten bzw. optional auslagern.
