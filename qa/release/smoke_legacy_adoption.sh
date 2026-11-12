#!/usr/bin/env bash
set -euo pipefail

image="$1"
revision="$2"
scratch="$(mktemp -d "${RUNNER_TEMP:?}/legacy-adoption-smoke.XXXXXXXX")"
media="${ADOPTION_ZFS_ROOT:?Use the synthetic ZFS runner}"
container=""
cleanup() {
  if [[ -n "$container" ]]; then
    docker logs "$container" >&2 || true
    docker rm -f "$container" >/dev/null || true
  fi
  sudo rm -rf -- "$scratch"
}
trap cleanup EXIT

docker pull "$image"
test "$(docker image inspect "$image" --format '{{index .Config.Labels "org.opencontainers.image.revision"}}')" = "$revision"
export ADOPTION_SMOKE_PASSWORD=synthetic-legacy-adoption-smoke-password
for method in manual script rollback skip; do
  install_root="$scratch/$method"
  archive="$media/archive-$method"
  source="$media/source-$method"
  mkdir -m 755 "$archive" "$source"
  sudo install -d -m 0750 -o 568 -g 568 "$install_root/appdata" "$install_root/workspace"
  if [[ "$method" != skip ]]; then
    if [[ "$method" == manual ]]; then day=21; else day=22; fi
    directory="$source/first/old-folders/camera/import"
    mkdir -p "$directory"
    printf 'synthetic raw for %s\n' "$method" > "$directory/sample.raf"
    cat > "$directory/sample.xmp" <<XML
<x:xmpmeta xmlns:x="adobe:ns:meta/">
  <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
    <rdf:Description xmlns:xmp="http://ns.adobe.com/xap/1.0/" xmp:CreateDate="2026-07-${day}T12:34:56+02:00"/>
  </rdf:RDF>
</x:xmpmeta>
XML
  fi
  container="$(docker run -d --read-only --tmpfs /tmp:size=64m,mode=1777 --security-opt no-new-privileges \
    -p 127.0.0.1::8080 \
    --mount "type=bind,source=$install_root/appdata,target=/appdata" \
    --mount "type=bind,source=$install_root/workspace,target=/workspace" \
    --mount "type=bind,source=$archive,target=/main-library,readonly" \
    --mount "type=bind,source=$source,target=/sources/nas,readonly" \
    -e "BIBLIOTHEKAR_ADMIN_PASSWORD=$ADOPTION_SMOKE_PASSWORD" \
    -e KAMERA_APPDATA=/appdata -e KAMERA_WORKSPACE=/workspace \
    -e KAMERA_POOL_PROBE=/workspace -e KAMERA_ARCHIVE_ROOT=/main-library \
    -e KAMERA_NAS_SOURCE_ROOT=/sources/nas "$image")"
  test "$(docker inspect --format '{{range .Mounts}}{{if eq .Destination "/main-library"}}{{.RW}}{{end}}{{end}}' "$container")" = false
  test "$(docker inspect --format '{{range .Mounts}}{{if eq .Destination "/sources/nas"}}{{.RW}}{{end}}{{end}}' "$container")" = false
  python qa/release/smoke_legacy_adoption.py "$container" "$source" "$archive" "$install_root/appdata" "$method"
  docker rm -f "$container" >/dev/null
  container=""
done
