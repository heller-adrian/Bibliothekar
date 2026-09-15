#!/usr/bin/env bash
set -Eeuo pipefail

QA_ROOT="${QA_ROOT:-/mnt/storage/ki-workspace/hermes/bibliothekar-qa}"
CONTAINER_NAME="${QA_CONTAINER_NAME:-bibliothekar-hermes-archive-qa}"
CURRENT_RUN_FILE="$QA_ROOT/current-archive-e2e-run"

say() { printf '%s\n' "$*"; }
blocked() { say "BLOCKED: $*" >&2; exit 20; }

command -v docker >/dev/null 2>&1 || blocked "docker fehlt"

if ! docker container inspect "$CONTAINER_NAME" >/dev/null 2>&1; then
  say "SKIPPED: QA-Container $CONTAINER_NAME existiert nicht."
  exit 0
fi

QA_LABEL="$(docker container inspect "$CONTAINER_NAME" --format '{{ index .Config.Labels "bibliothekar.qa" }}' 2>/dev/null || true)"
[[ "$QA_LABEL" == "true" ]] || blocked "Container $CONTAINER_NAME ist nicht als Bibliothekar-QA-Container markiert; wird nicht angefasst."

RUN_LABEL="$(docker container inspect "$CONTAINER_NAME" --format '{{ index .Config.Labels "bibliothekar.qa.run" }}' 2>/dev/null || true)"
PRODUCT_LABEL="$(docker container inspect "$CONTAINER_NAME" --format '{{ index .Config.Labels "bibliothekar.qa.product-revision" }}' 2>/dev/null || true)"

docker stop "$CONTAINER_NAME" >/dev/null
docker rm "$CONTAINER_NAME" >/dev/null

if [[ -f "$CURRENT_RUN_FILE" ]]; then
  RUN_ROOT="$(cat "$CURRENT_RUN_FILE")"
  if [[ "$RUN_ROOT" == "$QA_ROOT/"* && -d "$RUN_ROOT" ]]; then
    printf '%s\n' "container_stopped=true" "container_run=$RUN_LABEL" "product_revision=$PRODUCT_LABEL" > "$RUN_ROOT/container-stopped.txt"
  fi
  rm -f "$CURRENT_RUN_FILE"
fi

say "PASS: isolierter Archiv-QA-Container wurde beendet und entfernt."
say "QA-Dateien, QA-DB und archive-test-library wurden NICHT automatisch gelöscht."
say "Aufräumen darf erst nach Auswertung und ausschließlich innerhalb von $QA_ROOT erfolgen."
