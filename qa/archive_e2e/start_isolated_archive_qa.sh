#!/usr/bin/env bash
set -Eeuo pipefail

QA_ROOT="${QA_ROOT:-/mnt/storage/ki-workspace/hermes/bibliothekar-qa}"
ARCHIVE_ROOT="${KAMERA_QA_ARCHIVE_ROOT:-$QA_ROOT/archive-test-library}"
RUN_ID="${QA_RUN_ID:-$(date '+%Y-%m-%d_%H%M%S')_0.21.2_ARCHIVE}"
RUN_ROOT="$QA_ROOT/runs/$RUN_ID"
SOURCE_ROOT="${1:-/mnt/storage/backup/kamera-sd-karten/DEEPTEST_SD_02}"
QA_PORT="${QA_PORT:-31044}"
CONTAINER_NAME="${QA_CONTAINER_NAME:-bibliothekar-hermes-archive-qa}"

EXPECTED_REVISION="627c5515e533e167e45354ccaa71f988f104ae08"
IMAGE="ghcr.io/heller-adrian/bibliothekar@sha256:27554d9f6cc2b8a67f77cf01e856b837423974dca0cb6d6e03e8bc5cdb5dddb6"
PRODUCTION_ARCHIVE="/mnt/storage/fotos/Kamerabibliothek"
PRODUCTION_DATABASE="/mnt/apps/appdata/kamera-automatisierung/database"
APP_DATABASE="$RUN_ROOT/database"
APP_WORKSPACE="$RUN_ROOT/workspace"
APP_LOGS="$RUN_ROOT/logs"
APP_CONFIG="$RUN_ROOT/config"
APP_IMPORT="$RUN_ROOT/import-sources"
APP_REMOVABLE="$RUN_ROOT/removable-sources"
APP_NAS="$RUN_ROOT/nas-sources"
APP_POOL_PROBE="$RUN_ROOT/pool-probe"
SOURCE_COPY="$APP_IMPORT/$(basename "$SOURCE_ROOT")"

say() { printf '%s\n' "$*"; }
blocked() { say "BLOCKED: $*" >&2; exit 20; }
fail() { say "FAIL: $*" >&2; exit 1; }
canon() { realpath -m -- "$1"; }

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || blocked "Benötigter Befehl fehlt: $1"
}

is_within() {
  local child parent
  child="$(canon "$1")"
  parent="$(canon "$2")"
  [[ "$child" == "$parent" || "$child" == "$parent/"* ]]
}

assert_qa_path() {
  local path="$1"
  is_within "$path" "$QA_ROOT" || blocked "Pfad liegt außerhalb des Hermes-QA-Bereichs: $path"
  ! is_within "$path" "$PRODUCTION_ARCHIVE" || blocked "QA-Pfad kollidiert mit realer Kamerabibliothek: $path"
  ! is_within "$path" "$PRODUCTION_DATABASE" || blocked "QA-Pfad kollidiert mit Produktiv-DB: $path"
}

approved_source() {
  local src root
  src="$(canon "$1")"
  for root in /mnt/storage/backup/kamera-sd-karten /backup/kamera-sd-karten; do
    if is_within "$src" "$root"; then
      return 0
    fi
  done
  return 1
}

wait_for_health() {
  local i
  for i in $(seq 1 30); do
    if docker exec "$CONTAINER_NAME" python -c \
      "import urllib.request; r=urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=2); raise SystemExit(0 if r.status == 200 else 1)" \
      >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  return 1
}

require_cmd docker
require_cmd realpath
require_cmd rsync
require_cmd sha256sum
require_cmd find
require_cmd sort
require_cmd stat

QA_ROOT="$(canon "$QA_ROOT")"
ARCHIVE_ROOT="$(canon "$ARCHIVE_ROOT")"
RUN_ROOT="$(canon "$RUN_ROOT")"
SOURCE_ROOT="$(canon "$SOURCE_ROOT")"
PRODUCTION_ARCHIVE="$(canon "$PRODUCTION_ARCHIVE")"
PRODUCTION_DATABASE="$(canon "$PRODUCTION_DATABASE")"
APP_DATABASE="$(canon "$APP_DATABASE")"
APP_WORKSPACE="$(canon "$APP_WORKSPACE")"
APP_LOGS="$(canon "$APP_LOGS")"
APP_CONFIG="$(canon "$APP_CONFIG")"
APP_IMPORT="$(canon "$APP_IMPORT")"
APP_REMOVABLE="$(canon "$APP_REMOVABLE")"
APP_NAS="$(canon "$APP_NAS")"
APP_POOL_PROBE="$(canon "$APP_POOL_PROBE")"
SOURCE_COPY="$(canon "$SOURCE_COPY")"

[[ "$ARCHIVE_ROOT" == "$(canon "$QA_ROOT/archive-test-library")" ]] || blocked "KAMERA_ARCHIVE_ROOT muss die freigegebene archive-test-library sein: $ARCHIVE_ROOT"
assert_qa_path "$ARCHIVE_ROOT"
assert_qa_path "$RUN_ROOT"
assert_qa_path "$APP_DATABASE"
assert_qa_path "$APP_WORKSPACE"
assert_qa_path "$APP_LOGS"
assert_qa_path "$APP_CONFIG"
assert_qa_path "$APP_IMPORT"
assert_qa_path "$APP_REMOVABLE"
assert_qa_path "$APP_NAS"
assert_qa_path "$APP_POOL_PROBE"

[[ -d "$SOURCE_ROOT" ]] || blocked "Freigegebene SD-Sicherung fehlt: $SOURCE_ROOT"
approved_source "$SOURCE_ROOT" || blocked "SD-Quelle liegt nicht unter einem freigegebenen Sicherungswurzelpfad: $SOURCE_ROOT"

mkdir -p "$ARCHIVE_ROOT"
if find "$ARCHIVE_ROOT" -mindepth 1 -print -quit | grep -q .; then
  blocked "archive-test-library ist nicht leer. Erst vorherigen QA-Lauf innerhalb des QA-Bereichs sauber auswerten/aufräumen: $ARCHIVE_ROOT"
fi

touch "$ARCHIVE_ROOT/.qa-write-test" || blocked "archive-test-library ist für den ausführenden QA-Benutzer nicht beschreibbar"
rm -f "$ARCHIVE_ROOT/.qa-write-test"

[[ ! -e "$RUN_ROOT" ]] || blocked "QA-Laufordner existiert bereits: $RUN_ROOT"
mkdir -p "$APP_DATABASE" "$APP_WORKSPACE" "$APP_LOGS" "$APP_CONFIG" "$APP_IMPORT" "$APP_REMOVABLE" "$APP_NAS" "$APP_POOL_PROBE"

cat > "$APP_CONFIG/settings.json" <<'JSON'
{
  "storage": {
    "processing_buffer_percent": 10,
    "safety_reserve_gib": 0
  }
}
JSON

SOURCE_STAT_BEFORE="$(stat -c '%d:%i:%s:%Y' "$SOURCE_ROOT")"
mkdir -p "$SOURCE_COPY"
rsync -rt --safe-links --no-owner --no-group --protect-args "$SOURCE_ROOT/" "$SOURCE_COPY/"
SOURCE_STAT_AFTER="$(stat -c '%d:%i:%s:%Y' "$SOURCE_ROOT")"
[[ "$SOURCE_STAT_BEFORE" == "$SOURCE_STAT_AFTER" ]] || blocked "Quellverzeichnis änderte sich während des Kopierens; Lauf nicht belastbar"

(
  cd "$SOURCE_COPY"
  find . -type f -print0 | LC_ALL=C sort -z | xargs -0 -r sha256sum
) > "$RUN_ROOT/source-files.sha256"

FILE_COUNT="$(find "$SOURCE_COPY" -type f | wc -l | tr -d ' ')"
[[ "$FILE_COUNT" -gt 0 ]] || blocked "Die Testkopie enthält keine Dateien: $SOURCE_COPY"

say "QA: ziehe unveränderliches Produktimage $IMAGE"
docker pull "$IMAGE" >/dev/null
IMAGE_REVISION="$(docker image inspect "$IMAGE" --format '{{ index .Config.Labels "org.opencontainers.image.revision" }}')"
[[ "$IMAGE_REVISION" == "$EXPECTED_REVISION" ]] || blocked "Image-Revision stimmt nicht: erwartet $EXPECTED_REVISION, erhalten $IMAGE_REVISION"

if docker container inspect "$CONTAINER_NAME" >/dev/null 2>&1; then
  EXISTING_QA_LABEL="$(docker container inspect "$CONTAINER_NAME" --format '{{ index .Config.Labels "bibliothekar.qa" }}' 2>/dev/null || true)"
  [[ "$EXISTING_QA_LABEL" == "true" ]] || blocked "Containername $CONTAINER_NAME ist bereits durch einen Nicht-QA-Container belegt"
  blocked "Ein isolierter Archiv-QA-Container läuft/liegt bereits vor: $CONTAINER_NAME. Erst auswerten und mit stop_isolated_archive_qa.sh beenden."
fi

CURRENT_UID="$(id -u)"
CURRENT_GID="$(id -g)"

docker run -d \
  --name "$CONTAINER_NAME" \
  --label bibliothekar.qa=true \
  --label "bibliothekar.qa.run=$RUN_ID" \
  --label "bibliothekar.qa.product-revision=$EXPECTED_REVISION" \
  --user "$CURRENT_UID:$CURRENT_GID" \
  --read-only \
  --tmpfs /tmp:rw,nosuid,nodev,noexec,size=256m \
  --cap-drop ALL \
  --security-opt no-new-privileges:true \
  -p "127.0.0.1:${QA_PORT}:8080" \
  -e "KAMERA_CONFIG=$APP_CONFIG/settings.json" \
  -e "KAMERA_DATABASE_DIR=$APP_DATABASE" \
  -e "KAMERA_WORKSPACE=$APP_WORKSPACE" \
  -e "KAMERA_LOG_DIR=$APP_LOGS" \
  -e "KAMERA_ARCHIVE_ROOT=$ARCHIVE_ROOT" \
  -e "KAMERA_IMPORT_ROOT=$APP_IMPORT" \
  -e "KAMERA_REMOVABLE_ROOT=$APP_REMOVABLE" \
  -e "KAMERA_NAS_SOURCE_ROOT=$APP_NAS" \
  -e "KAMERA_POOL_PROBE=$APP_POOL_PROBE" \
  -e "KAMERA_SOURCE_HELPER_URL=http://127.0.0.1:9" \
  -e "BIBLIOTHEKAR_QA_MODE=archive-e2e" \
  -e "PYTHONDONTWRITEBYTECODE=1" \
  -v "$ARCHIVE_ROOT:$ARCHIVE_ROOT:rw" \
  -v "$APP_DATABASE:$APP_DATABASE:rw" \
  -v "$APP_WORKSPACE:$APP_WORKSPACE:rw" \
  -v "$APP_LOGS:$APP_LOGS:rw" \
  -v "$APP_CONFIG:$APP_CONFIG:ro" \
  -v "$APP_IMPORT:$APP_IMPORT:ro" \
  -v "$APP_REMOVABLE:$APP_REMOVABLE:ro" \
  -v "$APP_NAS:$APP_NAS:ro" \
  -v "$APP_POOL_PROBE:$APP_POOL_PROBE:ro" \
  "$IMAGE" >/dev/null

INSPECT_FILE="$RUN_ROOT/container-inspect.json"
docker inspect "$CONTAINER_NAME" > "$INSPECT_FILE"

if grep -Fq "$PRODUCTION_ARCHIVE" "$INSPECT_FILE"; then
  docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
  fail "Sicherheitsverletzung: reale Kamerabibliothek taucht in Containerkonfiguration auf"
fi
if grep -Fq "$PRODUCTION_DATABASE" "$INSPECT_FILE"; then
  docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
  fail "Sicherheitsverletzung: Produktiv-DB taucht in Containerkonfiguration auf"
fi

MOUNTS="$(docker inspect "$CONTAINER_NAME" --format '{{range .Mounts}}{{printf "%s\t%s\t%t\n" .Source .Destination .RW}}{{end}}')"
ENVS="$(docker inspect "$CONTAINER_NAME" --format '{{range .Config.Env}}{{println .}}{{end}}')"
printf '%s\n' "$MOUNTS" > "$RUN_ROOT/mounts.txt"
printf '%s\n' "$ENVS" > "$RUN_ROOT/environment.txt"

printf '%s\n' "$ENVS" | grep -Fx "KAMERA_DATABASE_DIR=$APP_DATABASE" >/dev/null || fail "QA-Datenbankvariable fehlt/ist falsch"
printf '%s\n' "$ENVS" | grep -Fx "KAMERA_ARCHIVE_ROOT=$ARCHIVE_ROOT" >/dev/null || fail "QA-Archivvariable fehlt/ist falsch"
printf '%s\n' "$MOUNTS" | grep -Fx "${ARCHIVE_ROOT}"$'\t'"${ARCHIVE_ROOT}"$'\ttrue' >/dev/null || fail "QA-Archiv ist nicht schreibbar gemountet"
printf '%s\n' "$MOUNTS" | grep -Fx "${APP_IMPORT}"$'\t'"${APP_IMPORT}"$'\tfalse' >/dev/null || fail "QA-Testkopien sind nicht read-only gemountet"

if ! wait_for_health; then
  docker logs "$CONTAINER_NAME" > "$RUN_ROOT/app.log" 2>&1 || true
  fail "Isolierte QA-App wurde nicht gesund. Log: $RUN_ROOT/app.log"
fi

docker logs "$CONTAINER_NAME" > "$RUN_ROOT/app.log" 2>&1 || true
[[ -f "$APP_DATABASE/kamera.sqlite3" ]] || fail "Eigene QA-SQLite-DB wurde nicht angelegt: $APP_DATABASE/kamera.sqlite3"

cat > "$RUN_ROOT/isolation.json" <<JSON
{
  "status": "PASS",
  "purpose": "T080-T088 archived E2E",
  "product_revision": "$EXPECTED_REVISION",
  "image": "$IMAGE",
  "archive_root": "$ARCHIVE_ROOT",
  "database": "$APP_DATABASE/kamera.sqlite3",
  "workspace": "$APP_WORKSPACE",
  "source_original": "$SOURCE_ROOT",
  "source_copy": "$SOURCE_COPY",
  "source_file_count": $FILE_COUNT,
  "production_archive_mounted": false,
  "production_database_mounted": false,
  "container": "$CONTAINER_NAME",
  "listen": "127.0.0.1:$QA_PORT"
}
JSON

printf '%s\n' "$CONTAINER_NAME" > "$RUN_ROOT/container.name"
printf '%s\n' "$RUN_ROOT" > "$QA_ROOT/current-archive-e2e-run"

say "PASS: isolierte Archiv-QA ist bereit"
say "Produktrevision: $EXPECTED_REVISION"
say "Image: $IMAGE"
say "QA-DB: $APP_DATABASE/kamera.sqlite3"
say "QA-Archiv: $ARCHIVE_ROOT"
say "Testkopien: $SOURCE_COPY ($FILE_COUNT Dateien)"
say "App: http://127.0.0.1:$QA_PORT"
say "Run: $RUN_ROOT"
say "T080-T088 dürfen erst ab diesem PASS gegen diese Instanz ausgeführt werden."
