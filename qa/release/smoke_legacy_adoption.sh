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
for method in manual script rollback skip review; do
  install_root="$scratch/$method"
  archive="$media/archive-$method"
  source="$media/source-$method"
  mkdir -m 755 "$archive" "$source"
  workspace="$install_root/workspace"
  if [[ "$method" == review ]]; then
    # Use the second synthetic dataset for the writable Workspace. Source
    # and archive still share the original, independently read-only dataset.
    acl_media="${ADOPTION_ZFS_OTHER:?Use the synthetic ZFS runner}"
    acl_dataset="$(findmnt -n -o SOURCE --mountpoint "$acl_media")"
    [[ "$acl_dataset" == bibliothekar_qa_*/other ]]
    sudo zfs set acltype=posix xattr=sa "$acl_dataset"
    workspace="$acl_media/workspace-review"
  fi
  sudo install -d -m 0750 -o 568 -g 568 "$install_root/appdata" "$workspace"
  if [[ "$method" == review ]]; then
    sudo setfacl -m u:65534:rx,d:u:65534:rwx,d:m::rwx "$workspace"
    printf 'native ZFS review RAW\n' > "$source/undated.raf"
    printf 'native ZFS review JPEG\n' > "$source/undated.jpg"
    printf 'native ZFS review sidecar\n' > "$source/undated.raf.xmp"
  elif [[ "$method" != skip ]]; then
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
    --mount "type=bind,source=$workspace,target=/workspace" \
    --mount "type=bind,source=$archive,target=/main-library,readonly" \
    --mount "type=bind,source=$source,target=/sources/nas,readonly" \
    -e "BIBLIOTHEKAR_ADMIN_PASSWORD=$ADOPTION_SMOKE_PASSWORD" \
    -e KAMERA_APPDATA=/appdata -e KAMERA_WORKSPACE=/workspace \
    -e KAMERA_POOL_PROBE=/workspace -e KAMERA_ARCHIVE_ROOT=/main-library \
    -e KAMERA_NAS_SOURCE_ROOT=/sources/nas "$image")"
  test "$(docker inspect --format '{{range .Mounts}}{{if eq .Destination "/main-library"}}{{.RW}}{{end}}{{end}}' "$container")" = false
  test "$(docker inspect --format '{{range .Mounts}}{{if eq .Destination "/sources/nas"}}{{.RW}}{{end}}{{end}}' "$container")" = false
  python qa/release/smoke_legacy_adoption.py "$container" "$source" "$archive" "$install_root/appdata" "$method"
  if [[ "$method" == review ]]; then
    stage="$(sudo find "$workspace" -type d -name .bibliothekar-legacy-review-stage -print -quit)"
    test -n "$stage"
    test "$(sudo stat -c %a "$stage")" = 700
    # Prove the inherited named principal can reach the parent first.
    stage_container="/workspace${stage#"$workspace"}"
    docker exec --user 65534:65534 "$container" test -x "$(dirname "$stage_container")"
    if docker exec --user 65534:65534 "$container" test -x "$stage_container"; then
      echo "A non-owner could traverse the private working directory." >&2
      exit 1
    fi
    echo "Native ZFS POSIX ACL inheritance preserved private review staging."
  fi
  docker rm -f "$container" >/dev/null
  container=""
done
