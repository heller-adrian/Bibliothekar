#!/usr/bin/env bash
set -euo pipefail

image="$1"
revision="$2"
scratch="$(mktemp -d "${RUNNER_TEMP:?}/legacy-adoption-smoke.XXXXXXXX")"
container=""
cleanup() {
  if [[ -n "$container" ]]; then
    docker logs "$container" >&2 || true
    docker rm -f "$container" >/dev/null || true
  fi
  sudo rm -rf -- "$scratch"
}
trap cleanup EXIT

mkdir -m 755 "$scratch/archive" "$scratch/source"
sudo install -d -m 0750 -o 568 -g 568 "$scratch/appdata" "$scratch/workspace"
mkdir -p "$scratch/source/2026/07/2026-07-21"
day="$scratch/source/2026/07/2026-07-21"
printf 'synthetic raw without JPEG\n' > "$day/sample.raf"
cat > "$day/sample.xmp" <<'XML'
<x:xmpmeta xmlns:x="adobe:ns:meta/">
  <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
    <rdf:Description xmlns:xmp="http://ns.adobe.com/xap/1.0/" xmp:CreateDate="2026-07-21T12:34:56+02:00"/>
  </rdf:RDF>
</x:xmpmeta>
XML

docker pull "$image"
test "$(docker image inspect "$image" --format '{{index .Config.Labels "org.opencontainers.image.revision"}}')" = "$revision"
export ADOPTION_SMOKE_PASSWORD=synthetic-legacy-adoption-smoke-password
container="$(docker run -d --read-only --tmpfs /tmp:size=64m,mode=1777 --security-opt no-new-privileges   -p 127.0.0.1::8080   --mount "type=bind,source=$scratch/appdata,target=/appdata"   --mount "type=bind,source=$scratch/workspace,target=/workspace"   --mount "type=bind,source=$scratch/archive,target=/main-library,readonly"   --mount "type=bind,source=$scratch/source,target=/sources/nas,readonly"   -e "BIBLIOTHEKAR_ADMIN_PASSWORD=$ADOPTION_SMOKE_PASSWORD"   -e KAMERA_APPDATA=/appdata -e KAMERA_WORKSPACE=/workspace   -e KAMERA_POOL_PROBE=/workspace -e KAMERA_ARCHIVE_ROOT=/main-library   -e KAMERA_NAS_SOURCE_ROOT=/sources/nas "$image")"
test "$(docker inspect --format '{{range .Mounts}}{{if eq .Destination "/main-library"}}{{.RW}}{{end}}{{end}}' "$container")" = false
test "$(docker inspect --format '{{range .Mounts}}{{if eq .Destination "/sources/nas"}}{{.RW}}{{end}}{{end}}' "$container")" = false
python qa/release/smoke_legacy_adoption.py "http://$(docker port "$container" 8080/tcp)" "$scratch/source" "$scratch/archive"
